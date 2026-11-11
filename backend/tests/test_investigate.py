"""Investigations queue beside voyages (thorp/investigate.py): a spec is checked, its queue line is a command
the coordinator already sails, and the line is read back as the investigation it runs."""

import sys

import pytest

from thorp import investigate
from thorp.viable.s2_coordination import lanes, queue_store

GOOD = """kind: investigation
name: tiny
expedition: arc_de_triomphe
question: does it run
subject: some/model
run: [-c, "import sys; print('read', sys.argv[1]); sys.exit(int(sys.argv[2]))", "{subject}", "0"]
timeout: 30s
readings: ["arc-{subject}"]
"""


@pytest.fixture
def specs(tmp_path, monkeypatch):
    d = tmp_path / "investigations"
    d.mkdir()
    monkeypatch.setattr(investigate, "folder", lambda: d)
    monkeypatch.setattr(investigate, "_put", lambda name, rec: seen.append(dict(rec)))
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    seen.clear()
    return d


seen: list[dict] = []


def test_a_good_spec_loads_and_fills_in_its_subject(specs):
    (specs / "tiny.yaml").write_text(GOOD)
    spec = investigate.load("investigations/tiny")
    assert investigate.argv(spec)[0] == sys.executable
    assert investigate.argv(spec)[3:] == ["some/model", "0"]
    assert investigate.readings_of(spec) == ["arc-some/model"]
    assert investigate.seconds("14h") == 50400 and investigate.seconds("90") == 5400 and investigate.seconds(None) is None


def test_a_broken_spec_is_refused_with_its_reasons(specs):
    (specs / "bad.yaml").write_text("kind: voyage\nname: other\nexpedition: nowhere\nrun: go\ntimeout: soon\n")
    with pytest.raises(ValueError) as e:
        investigate.load("bad")
    msg = str(e.value)
    for part in ("kind must be", "does not match", "not in fleet.EXPEDITIONS", "run must be a list", "question", "timeout"):
        assert part in msg


def test_its_queue_line_is_a_command_and_reads_back(specs):
    (specs / "tiny.yaml").write_text(GOOD)
    line = investigate.queue_line("investigations/tiny")
    assert line.startswith("cmd: ") and line.endswith("-m thorp.investigate run tiny")
    assert queue_store.parse_line(line)["kind"] == "cmd"  # the coordinator at sea needs no new kind
    assert investigate.of_line(line)["expedition"] == "arc_de_triomphe"
    assert investigate.of_line("cmd: echo hello") is None
    assert investigate.of_line("fitouts/1m@v0.0.6") is None
    ln = lanes.parse(line)
    assert (ln.kind, ln.lane, ln.name) == ("cmd", "mac", "tiny")


def test_run_keeps_the_exit_the_log_and_the_standing(specs, tmp_path):
    (specs / "tiny.yaml").write_text(GOOD)
    assert investigate.run("tiny") == 0
    assert [r["status"] for r in seen] == ["running", "finished"]
    assert seen[-1]["exit"] == 0 and seen[-1]["expedition"] == "arc_de_triomphe"
    assert "read some/model" in (tmp_path / "data/runs/investigations/tiny.out").read_text()
    (specs / "tiny.yaml").write_text(GOOD.replace('"0"]', '"3"]'))
    assert investigate.run("tiny") == 3 and seen[-1]["status"] == "failed"


def test_the_deadline_stops_it(specs):
    (specs / "tiny.yaml").write_text(
        GOOD.replace("sys.exit(int(sys.argv[2]))", "__import__('time').sleep(60)").replace("30s", "1s")
    )
    assert investigate.run("tiny") == 124
    assert seen[-1]["status"] == "timed out"
