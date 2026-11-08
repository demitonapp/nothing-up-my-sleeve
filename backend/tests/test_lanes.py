"""The S2 coordinator (thorp/viable/s2_coordination/lanes.py): one standing queue, two lanes, this Mac and a GPU
hired from Vast.ai. The voyages here are short shell sleeps standing in for `thorp run` and `thorp charter sail`."""

import subprocess
import time

import pytest
import yaml

from thorp.viable.s2_coordination import lanes


def _spec(specs, rel, name, **extra):
    p = specs / f"{rel}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    s = {"name": name, "ship": "Fitout: Ogden test", "model": {"family": "gpt", "preset": "9m"}, **extra}
    p.write_text(yaml.safe_dump(s))


@pytest.fixture
def harbour(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    return {"root": tmp_path, "specs": specs, "queue": specs / "queue.txt", "done": specs / "queue-done.txt",
            "state": tmp_path / "lanes.json"}  # fmt: skip


def _sail(h, lines, key=True, secs=0.3):
    """Run the coordinator over `lines`; returns the events (lane, line, start, end) and its log."""
    h["queue"].write_text("\n".join(lines) + "\n")
    events, said = [], []

    def launch(ln):
        events.append({"lane": ln.lane, "line": ln.text, "start": time.time()})
        return subprocess.Popen(["sleep", str(secs)])

    lanes.run(queue=h["queue"], done=h["done"], root=h["root"], state_path=h["state"], poll_s=0.05,
              key=lambda: key, outside=lambda: False, launch=launch, log=said.append)  # fmt: skip
    ends = {}
    for row in h["done"].read_text().splitlines() if h["done"].exists() else []:
        ends[row.split(" ", 1)[1].rsplit(" ", 1)[0]] = row
    return events, said, ends


def test_lines_are_routed_to_their_lanes(harbour):
    _spec(harbour["specs"], "fitouts/cuda", "cuda", model={"family": "gpt", "preset": "9m", "backend": "torch"})
    _spec(harbour["specs"], "fitouts/here", "here")
    s = harbour["specs"]
    assert lanes.parse("vast: fitouts/here", s).lane == "vast"
    assert lanes.parse("fitouts/cuda", s).lane == "vast"  # written for CUDA: never on the Mac's CPU
    assert lanes.parse("fitouts/here", s).lane == "mac"
    assert (lanes.parse("cmd: echo hi", s).kind, lanes.parse("cmd: echo hi", s).lane) == ("cmd", "mac")
    w = lanes.parse("wait: cuda", s)
    assert (w.kind, w.payload, w.lane) == ("wait", "cuda", "mac")
    assert lanes.command(lanes.parse("vast: fitouts/here", s))[-3:] == ["charter", "sail", "ships/specs/fitouts/here.yaml"]


def test_the_mac_sails_while_a_hired_ship_is_out(harbour):
    for n in ("big", "m1", "m2"):
        _spec(harbour["specs"], n, n)
    ev, _, ends = _sail(harbour, ["vast: big", "m1", "m2"], secs=0.4)
    by = {e["line"]: e for e in ev}
    assert by["vast: big"]["lane"] == "vast" and by["m1"]["lane"] == "mac"
    assert by["m1"]["start"] - by["vast: big"]["start"] < 0.3  # side by side, not one after the other
    assert by["m2"]["start"] > by["m1"]["start"]  # the Mac lane in order
    assert set(ends) == {"vast: big", "m1", "m2"} and all(r.endswith(" 0") for r in ends.values())
    assert harbour["queue"].read_text().strip() == ""


def test_without_a_key_the_vast_lines_wait_in_the_queue(harbour):
    for n in ("big", "m1"):
        _spec(harbour["specs"], n, n)
    ev, said, _ = _sail(harbour, ["vast: big", "m1"], key=False)
    assert [e["line"] for e in ev] == ["m1"]
    assert harbour["queue"].read_text().strip() == "vast: big"
    assert any("no Vast.ai key" in m for m in said)


def test_a_voyage_waits_for_the_run_it_is_seeded_from_in_the_other_lane(harbour):
    _spec(harbour["specs"], "big", "big")
    _spec(harbour["specs"], "small", "small", seeded_from={"run": "big", "mode": "free"})
    ev, said, _ = _sail(harbour, ["vast: big", "small"], secs=0.3)
    by = {e["line"]: e for e in ev}
    assert by["small"]["start"] >= by["vast: big"]["start"] + 0.3
    assert any("reads from big" in m for m in said)


def test_wait_holds_the_mac_lane_until_the_voyage_docks(harbour):
    for n in ("big", "after"):
        _spec(harbour["specs"], n, n)
    ev, _, ends = _sail(harbour, ["vast: big", "wait: big", "cmd: echo scored", "after"], secs=0.3)
    by = {e["line"]: e for e in ev}
    assert by["cmd: echo scored"]["start"] >= by["vast: big"]["start"] + 0.3
    assert "wait: big" in ends and ends["wait: big"].endswith(" 0")


def test_the_same_run_never_sails_on_both_lanes(harbour):
    _spec(harbour["specs"], "twin", "twin")
    a, b = lanes.parse("vast: twin", harbour["specs"]), lanes.parse("twin", harbour["specs"])
    a.run_id = b.run_id = "r1"
    assert lanes.blocked(b, [], {"mac": None, "vast": a}) == "the same run is at sea in the other lane"
    assert lanes.blocked(b, [], {"mac": None, "vast": None}) is None


def test_a_lane_waits_at_its_first_line(harbour):
    _spec(harbour["specs"], "big", "big")
    _spec(harbour["specs"], "small", "small", seeded_from={"run": "big"})
    _spec(harbour["specs"], "other", "other")
    ls = [lanes.parse(t, harbour["specs"]) for t in ("vast: big", "small", "other")]
    ln, why = lanes.next_for("mac", ls, {"mac": None, "vast": None}, key=True)
    assert ln is None and "reads from big" in why  # "other" does not jump the queue


def test_lanes_json_names_what_is_out(harbour):
    _spec(harbour["specs"], "m1", "m1")
    p = subprocess.Popen(["sleep", "5"])
    try:
        lanes._write_state(harbour["state"], {"mac": {"line": lanes.parse("m1", harbour["specs"]), "proc": p, "since": "now"}, "vast": None})
        st = lanes.state(harbour["state"])
        assert st["mac"]["line"] == "m1" and st["vast"] is None
    finally:
        p.kill()
        p.wait()
    assert lanes.state(harbour["state"])["mac"] is None  # its process gone: in port


def test_a_cmd_line_really_runs_from_the_root(harbour):
    harbour["queue"].write_text("cmd: echo docked > here.txt; exit 3\n")
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"], state_path=harbour["state"],
              poll_s=0.05, key=lambda: False, outside=lambda: False, log=lambda m: None)  # fmt: skip
    assert (harbour["root"] / "here.txt").read_text().strip() == "docked"
    assert harbour["done"].read_text().strip().endswith("cmd: echo docked > here.txt; exit 3 3")
