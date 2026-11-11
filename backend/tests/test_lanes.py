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
def harbour(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_QUEUE_PG", "0")  # these tests exercise the file queue, not the store
    specs = tmp_path / "specs"
    specs.mkdir()
    return {"root": tmp_path, "specs": specs, "queue": specs / "queue.txt", "done": specs / "queue-done.txt"}


def _sail(h, lines, key=True, secs=0.3):
    """Run the coordinator over `lines`; returns the events (lane, line, start, end) and its log."""
    h["queue"].write_text("\n".join(lines) + "\n")
    events, said = [], []

    def launch(ln):
        events.append({"lane": ln.lane, "line": ln.text, "start": time.time()})
        return subprocess.Popen(["sleep", str(secs)])

    lanes.run(queue=h["queue"], done=h["done"], root=h["root"], poll_s=0.05,
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
    # what is at sea is a list of lines since a lane took seats (9 November); these two tests still passed
    # the older {lane: line} and failed on it
    assert lanes.blocked(b, [], [a]) == "the same run is at sea in the other lane"
    assert lanes.blocked(b, [], []) is None


def test_a_lane_waits_at_its_first_line(harbour):
    _spec(harbour["specs"], "big", "big")
    _spec(harbour["specs"], "small", "small", seeded_from={"run": "big"})
    _spec(harbour["specs"], "other", "other")
    ls = [lanes.parse(t, harbour["specs"]) for t in ("vast: big", "small", "other")]
    ln, why = lanes.next_for("mac", ls, [], key=True)
    assert ln is None and "reads from big" in why  # "other" does not jump the queue


def test_s2_lanes_names_what_is_out(harbour):
    _spec(harbour["specs"], "m1", "m1")
    p = subprocess.Popen(["sleep", "5"])
    try:
        lanes._write_state({"mac": [{"line": lanes.parse("m1", harbour["specs"]), "proc": p, "since": "now"}], "vast": []})
        st = lanes.state()
        assert st["mac"]["line"] == "m1" and st["vast"] is None
    finally:
        p.kill()
        p.wait()
    assert lanes.state()["mac"] is None  # its process gone: in port


def test_a_cmd_line_really_runs_from_the_root(harbour):
    harbour["queue"].write_text("cmd: echo docked > here.txt; exit 3\n")
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"],
              poll_s=0.05, key=lambda: False, outside=lambda: False, log=lambda m: None)  # fmt: skip
    assert (harbour["root"] / "here.txt").read_text().strip() == "docked"
    assert harbour["done"].read_text().strip().endswith("cmd: echo docked > here.txt; exit 3 3")


def test_only_one_coordinator_at_a_time(tmp_path):
    with lanes.one_coordinator(tmp_path / "lanes.lock"):
        with pytest.raises(lanes.AlreadyRunning):
            with lanes.one_coordinator(tmp_path / "lanes.lock"):
                pass
    with lanes.one_coordinator(tmp_path / "lanes.lock"):  # free again once the first has gone
        pass


# ---------------------------------------------------------------- what is at sea is a row (11 November)
#
# The architecture audit's item 2: a line at sea is a row in s2.at_sea from the step that takes it to the step
# that writes its history, a restarted coordinator adopts the rows it finds, and a line is launched in its own
# session so that the coordinator's death is not its own.


def _orphan(cmd: str) -> int:
    """A process that is not this test's child, as a restarted coordinator's lines are not its children: the
    shell that starts it exits at once, so it is launchd's (or init's) to reap and its pid really dies."""
    out = subprocess.run(["sh", "-c", f"{cmd} >/dev/null 2>&1 & echo $!"], capture_output=True, text=True)
    return int(out.stdout)


def _dead_pid() -> int:
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


def _history(h) -> dict:
    """queue-done.txt as {line: status}."""
    rows = h["done"].read_text().splitlines() if h["done"].exists() else []
    return {r.split(" ", 1)[1].rsplit(" ", 1)[0]: r.rsplit(" ", 1)[1] for r in rows}


def _restart(h, lines=(), launch=None, **kw):
    """A coordinator starting over what is already in the store; returns its log."""
    h["queue"].write_text("".join(f"{x}\n" for x in lines))
    said = []
    lanes.run(queue=h["queue"], done=h["done"], root=h["root"], poll_s=0.05, key=lambda: True,
              outside=lambda: False, log=said.append, **({"launch": launch} if launch else {}), **kw)  # fmt: skip
    return said


def test_a_line_at_sea_is_a_row_until_its_history_is_written(harbour):
    from thorp.viable.s2_coordination import queue_store

    _spec(harbour["specs"], "m1", "m1")
    seen = {}

    def launch(ln):
        seen["at launch"] = queue_store.at_sea()  # the row is written with the take, before the process exists
        seen["queued"] = harbour["queue"].read_text().strip()
        return subprocess.Popen(["sleep", "0.4"])

    harbour["queue"].write_text("m1\n")
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"], poll_s=0.05,
              key=lambda: True, outside=lambda: False, launch=launch, log=lambda m: None)  # fmt: skip
    (row,) = seen["at launch"]
    assert (row["text"], row["lane"], row["kind"], row["name"], row["pid"]) == ("m1", "mac", "spec", "m1", None)
    assert row["run_id"] == lanes.parse("m1", harbour["specs"]).run_id and row["started"] and row["seat"] == 0
    assert seen["queued"] == ""  # in the queue or at sea, never both
    assert queue_store.at_sea() == [] and _history(harbour) == {"m1": "0"}  # the row left with the history


def test_the_row_carries_the_pid_while_the_line_is_out(harbour):
    from thorp.viable.s2_coordination import queue_store

    pids = {}

    def launch(ln):
        if ln.payload.startswith("sleep"):
            pids["launched"] = p = subprocess.Popen(["sleep", "0.5"])
            return p
        pids["row"] = [r["pid"] for r in queue_store.at_sea() if r["text"] == "cmd: sleep 0.5"]
        return subprocess.Popen(["true"])

    # two lanes (the Mac's starts first), so the second line's launch reads the first line's row while it is out
    _restart(harbour, ["cmd: sleep 0.5", "vast: cmd: echo look"], launch=launch)
    assert pids["row"] == [pids["launched"].pid]
    assert queue_store.at_sea() == []


def test_a_launch_that_fails_leaves_no_row_and_is_retried_as_before(harbour):
    from thorp.viable.s2_coordination import queue_store

    rows_at_launch = []

    def launch(ln):
        rows_at_launch.append([r["text"] for r in queue_store.at_sea()])
        raise OSError("no such ship")

    said = _restart(harbour, ["cmd: echo never"], launch=launch)
    assert rows_at_launch == [["cmd: echo never"]] * 3  # each try has its own row and no stale one beside it
    assert queue_store.at_sea() == [] and harbour["queue"].read_text().strip() == ""
    assert _history(harbour) == {"cmd: echo never": "1"}
    assert sum("could not start (attempt" in m for m in said) == 2 and any("after 3 attempts" in m for m in said)


def test_with_the_store_as_the_queue_the_take_and_the_row_are_one_step(harbour, tmp_thorp, monkeypatch):
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.s2_coordination import queue_store

    monkeypatch.setenv("THORP_QUEUE_PG", "1")
    queue_store.add("cmd: sleep 0.3", require_goal=False)
    seen = {}

    def launch(ln):
        seen.update(rows=queue_store.at_sea(), queued=queue_store.pending_texts())
        return subprocess.Popen(["sleep", "0.3"])

    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"], poll_s=0.05,
              key=lambda: True, outside=lambda: False, launch=launch, log=lambda m: None)  # fmt: skip
    assert [r["text"] for r in seen["rows"]] == ["cmd: sleep 0.3"] and seen["queued"] == []
    with store.session() as s:
        hist = [(r.text, r.status) for r in s.scalars(select(queue_store.QueueHistory))]
    assert hist == [("cmd: sleep 0.3", "0")] and queue_store.at_sea() == []
    assert not harbour["done"].exists()  # the store took the history: nothing fell back to the file


def test_a_restart_adopts_a_live_cmd_and_watches_it_home(harbour):
    from thorp.viable.s2_coordination import queue_store

    pid = _orphan("sleep 1.2")
    queue_store.to_sea("cmd: sleep 1.2", lane="mac", kind="cmd", pid=pid, started="2026-11-11T10:00:00", started_ts=time.time())
    t0, starts = time.time(), []

    def launch(ln):
        starts.append(time.time() - t0)
        return subprocess.Popen(["true"])

    said = _restart(harbour, ["cmd: echo next"], launch=launch)
    assert any(f"adopted cmd: sleep 1.2 (pid {pid})" in m for m in said)
    assert starts and starts[0] > 0.8  # the adopted line held the Mac lane's one seat until it ended
    assert _history(harbour) == {"cmd: sleep 1.2": "adopted:exit-unknown", "cmd: echo next": "0"}
    assert "2026-11-11T10:00:00 cmd: sleep 1.2" in harbour["done"].read_text()  # started when it really started
    assert queue_store.at_sea() == []


def test_a_restart_adopts_a_live_voyage_and_reads_its_outcome_from_the_ledger(harbour, monkeypatch):
    from thorp.viable.s2_coordination import queue_store

    _spec(harbour["specs"], "fitouts/big", "big")
    pid = _orphan("sh -c 'sleep 0.8; true' thorp.train ships/specs/fitouts/big.yaml")
    queue_store.to_sea("fitouts/big", lane="mac", kind="spec", name="big", run_id="r-big", pid=pid, seat=1,
                       started="2026-11-11T10:00:00", started_ts=time.time())  # fmt: skip
    asked = []
    monkeypatch.setattr(lanes, "_ledger_status", lambda rid, name=None, since=None: asked.append(rid) or "finished")
    said = _restart(harbour)
    assert any("adopted fitouts/big" in m for m in said) and asked == ["r-big"]  # the id it sailed under
    assert _history(harbour) == {"fitouts/big": "adopted:finished"} and queue_store.at_sea() == []
    assert pid not in lanes._children


def test_an_adopted_voyage_that_died_is_unfinished_not_a_success(harbour, monkeypatch):
    ln = lanes.parse("cmd: echo x", harbour["specs"])
    assert lanes._outcome(ln) == "adopted:exit-unknown" and lanes._outcome(ln, gone=True) == "lost"
    v = lanes.Line("fitouts/big", "mac", "spec", "fitouts/big", run_id="r-big")
    for status, alive_then_gone, found_dead in [
        ("finished", "adopted:finished", "adopted:finished"),  # it docked while no coordinator watched
        ("running", "adopted:unfinished", "lost"),
        ("chartered: lost contact", "adopted:chartered:-lost-contact", "lost"),
        (None, "adopted:exit-unknown", "lost"),
    ]:
        monkeypatch.setattr(lanes, "_ledger_status", lambda rid, name=None, since=None, s=status: s)
        assert (lanes._outcome(v), lanes._outcome(v, gone=True)) == (alive_then_gone, found_dead)


def test_the_ledger_is_where_an_adopted_voyages_outcome_is_read(harbour):
    from thorp.ledger import reader

    reader().run({"run_id": "r-home", "name": "home", "status": "finished", "started": "2026-11-11T08:43:46+00:00"})
    assert lanes._ledger_status("r-home") == "finished"
    assert lanes._ledger_status("r-nowhere") is None and lanes._ledger_status(None) is None
    # a row with the wrong id (the raw YAML's, before 11 November's fix) is answered by the voyage's name,
    # but only by a run that started with the line or after it, never an older voyage of that name
    assert lanes._ledger_status("r-wrong", "home", "2026-11-11T08:43:29+00:00") == "finished"
    assert lanes._ledger_status("r-wrong", "home", "2026-11-11T09:43:29+00:00") is None
    assert lanes._ledger_status("r-wrong", "elsewhere", "2026-11-11T08:43:29+00:00") is None


def test_a_voyages_run_id_is_the_one_it_sails_under(harbour):
    """train.load_spec adds the ladder's evaluators before the id is computed; the queue's id must be that one,
    or an adopted voyage's outcome is read from no row at all (11 November, the live 9m@v0.0.6)."""
    from thorp import paths, train

    real = paths.resolve("specs/fitouts/9m@v0.0.6.yaml")
    raw = yaml.safe_load(real.read_text())
    p = harbour["specs"] / "fitouts" / "nine.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(yaml.safe_dump(raw))
    ln = lanes.parse("fitouts/nine", harbour["specs"])
    assert ln.run_id == train.run_id(train.load_spec(p)) != train.run_id(raw)  # the ladder adds to this one
    assert ln.spec == raw  # the spec as written is kept; only the id is the sailed one


def test_a_restart_records_a_dead_line_as_lost_and_does_not_requeue_it(harbour, monkeypatch):
    from thorp.viable.s2_coordination import queue_store

    _spec(harbour["specs"], "fitouts/big", "big")
    _spec(harbour["specs"], "m1", "m1")
    monkeypatch.setattr(lanes, "_ledger_status", lambda rid, name=None, since=None: "running")
    queue_store.to_sea("fitouts/big", lane="mac", kind="spec", name="big", run_id="r-big", pid=_dead_pid(), started="2026-11-11T10:00:00")
    queue_store.to_sea("vast: m1", lane="vast", kind="spec", name="m1", run_id="r-m1", pid=None, started="2026-11-11T10:05:00")
    launched = []

    def launch(ln):
        launched.append(ln.text)
        return subprocess.Popen(["true"])

    said = _restart(harbour, ["cmd: echo next"], launch=launch)
    assert launched == ["cmd: echo next"]  # its seat was free at once, and the lost voyages were not sailed again
    assert _history(harbour) == {"fitouts/big": "lost", "vast: m1": "lost", "cmd: echo next": "0"}
    assert queue_store.at_sea() == [] and harbour["queue"].read_text().strip() == ""
    big = next(m for m in said if "fitouts/big was at sea" in m)
    assert "is gone" in big and "recorded as lost, not requeued" in big
    m1 = next(m for m in said if "vast: m1 was at sea" in m)
    assert "never given a pid" in m1 and "thorp charter attach r-m1" in m1  # its box may still be hired


def test_a_pid_that_is_now_another_process_is_not_adopted(harbour):
    import os

    from thorp.viable.s2_coordination import queue_store

    queue_store.to_sea("cmd: sleep 9999", lane="mac", kind="cmd", pid=os.getpid(), started="2026-11-11T10:00:00")
    said = _restart(harbour)  # this test's own pid is alive, and is not `sleep 9999`
    assert not any("adopted" in m for m in said)
    assert _history(harbour) == {"cmd: sleep 9999": "lost"} and queue_store.at_sea() == []


def test_is_that_job_reads_the_command_line(harbour, monkeypatch):
    import os

    _spec(harbour["specs"], "fitouts/big", "big")
    spec, cmd = lanes.parse("fitouts/big", harbour["specs"]), lanes.parse('cmd: echo "a  b" > out.txt', harbour["specs"])

    def ps(line, code=0):
        monkeypatch.setattr(lanes.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=line + "\n", stderr=""))

    ps("/x/backend/.venv/bin/python -m thorp.train ships/specs/fitouts/big.yaml")
    assert lanes._is_that_job(1, spec) and not lanes._is_that_job(1, cmd)
    ps("uv run --no-sync --project backend --group torch thorp charter sail ships/specs/fitouts/big.yaml")
    assert lanes._is_that_job(1, spec)
    ps("/x/python -m thorp.train ships/specs/fitouts/other.yaml")
    assert not lanes._is_that_job(1, spec)
    ps('/bin/sh -c echo "a  b" > out.txt')
    assert lanes._is_that_job(1, cmd)
    ps("echo a b")  # the shell exec'd the command, its quotes gone
    assert lanes._is_that_job(1, cmd)
    # a command's leading assignments go to the environment and never show in ps (12 November: the ARC
    # investigation at sea would have been called lost by a restarted coordinator)
    env = lanes.parse("cmd: PYTHONPATH=backend X_Y=1 backend/.venv/bin/python -m thorp.investigate run arc", harbour["specs"])
    ps("backend/.venv/bin/python -m thorp.investigate run arc")
    assert lanes._is_that_job(1, env)
    ps("backend/.venv/bin/python -m thorp.investigate run other")
    assert lanes._is_that_job(1, env)  # the same program: held, as a bare command's first word always was
    ps("/usr/bin/caffeinate -dimsu")
    assert not lanes._is_that_job(1, env)
    ps("", code=1)  # it answers a signal and ps shows nothing: hold the seat
    assert lanes._is_that_job(os.getpid(), spec)

    def blocked(*a, **k):
        raise PermissionError("ps is not allowed here")

    monkeypatch.setattr(lanes.subprocess, "run", blocked)  # a sandbox that blocks ps: hold the seat
    assert lanes._is_that_job(1, spec) and lanes._is_that_job(1, cmd)


def test_the_old_pid_file_is_still_adopted_and_given_a_row(harbour):
    """A coordinator from before the rows leaves only data/queue-procs.json: a live line in it is adopted, a
    `cmd:` as before and now a voyage too, and given a row so that the next restart finds it there."""
    import json

    from thorp.viable.s2_coordination import queue_store

    _spec(harbour["specs"], "fitouts/big", "big")
    live, voyage = _orphan("sleep 1.1"), _orphan("sh -c 'sleep 0.9; true' ships/specs/fitouts/big.yaml")
    procs = harbour["root"] / "data" / "queue-procs.json"
    procs.parent.mkdir(parents=True)
    procs.write_text(json.dumps([
        {"lane": "mac", "text": "cmd: sleep 1.1", "kind": "cmd", "pid": live, "since": "2026-11-11T09:00:00", "since_ts": time.time(), "slot": 0},
        {"lane": "mac", "text": "fitouts/big", "kind": "spec", "pid": voyage, "since": "2026-11-11T09:01:00", "since_ts": time.time(), "slot": 1},
        {"lane": "mac", "text": "cmd: echo gone", "kind": "cmd", "pid": _dead_pid(), "since": "2026-11-11T09:02:00", "slot": 0},
    ]))  # fmt: skip
    rows = []

    def log(m):
        if "] adopted " in m:
            rows.append(sorted((r["text"], r["pid"], r["seat"]) for r in queue_store.at_sea()))

    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"], poll_s=0.05,
              key=lambda: True, outside=lambda: False, log=log)  # fmt: skip
    assert rows[-1] == [("cmd: sleep 1.1", live, 0), ("fitouts/big", voyage, 1)]
    got = _history(harbour)
    assert got["cmd: sleep 1.1"] == "adopted:exit-unknown" and got["cmd: echo gone"] == "lost"
    assert got["fitouts/big"].startswith("adopted:")
    assert queue_store.at_sea() == [] and json.loads(procs.read_text()) == []


def test_the_reaper_leaves_a_run_with_a_live_row_or_a_hired_box(harbour, tmp_thorp, monkeypatch):
    """A chartered voyage's row comes home 'running' and never holds this Mac's helm: the reaper, which closes
    'running' rows with no helm, must not close one that an at-sea row or the spend log still covers."""
    import os

    from thorp.ledger import reader
    from thorp.viable.s2_coordination import queue_store
    from thorp.viable.s3_control import charter as s3

    monkeypatch.setenv("THORP_QUEUE_PG", "1")
    old = "2026-11-01T00:00:00"
    for rid in ("r-row", "r-hired", "r-ghost"):
        reader().run({"run_id": rid, "name": rid, "status": "running", "started": old})
    queue_store.to_sea("vast: x", lane="vast", kind="spec", run_id="r-row", pid=os.getpid())
    s3.record("hired", instance=7, run_id="r-hired", dph=0.4, started=time.time())
    said = []
    assert lanes._reap_runs(said.append) == 1
    assert {rid: reader().get_run(rid)["status"] for rid in ("r-row", "r-hired", "r-ghost")} == {
        "r-row": "running", "r-hired": "running", "r-ghost": "stopped"}  # fmt: skip


def test_the_vast_lane_waits_while_a_ship_is_hired_that_it_is_not_sailing(harbour):
    """A charter that died leaves its ship in the spend log. The gate would refuse every Vast line in turn
    ("already hired") and the lane would empty its queue into the history as failures: it waits instead."""
    from thorp.viable.s3_control import charter as s3

    _spec(harbour["specs"], "big", "big", seed=1)
    _spec(harbour["specs"], "m1", "m1", seed=2)
    s3.record("hired", instance=77, run_id="r-dead", name="orphaned", dph=0.4, started=time.time())
    launched, said = [], []

    def launch(ln):
        launched.append(ln.text)
        return subprocess.Popen(["sleep", "0.3"])

    def log(m):
        said.append(m)
        if "m1 exited" in m:  # while the Mac sailed, the ship was taken up and released (attach, or the audit)
            s3.record("released", instance=77, run_id="r-dead", status="home", ended=time.time(), cost=0.1)

    harbour["queue"].write_text("vast: big\nm1\n")
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"], poll_s=0.05,
              key=lambda: True, outside=lambda: False, launch=launch, log=log)  # fmt: skip
    assert launched == ["m1", "vast: big"]  # the Vast line waited in the queue, was not failed, and then sailed
    why = next(m for m in said if "[vast] in port" in m)
    assert "instance 77 (orphaned) is still hired" in why and "thorp charter attach r-dead" in why
    assert _history(harbour) == {"m1": "0", "vast: big": "0"}


# ---------------------------------------------------------------- a coordinator's death is not its children's


def test_a_line_is_launched_in_its_own_session(harbour):
    import os

    harbour["queue"].write_text("cmd: ps -o pid=,pgid= -p $$ > ids.txt; true\n")
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"],
              poll_s=0.05, key=lambda: False, outside=lambda: False, log=lambda m: None)  # fmt: skip
    pid, pgid = (int(x) for x in (harbour["root"] / "ids.txt").read_text().split())
    assert pgid == pid and pgid != os.getpgrp()  # it leads its own group: a signal to ours does not reach it


def test_a_timed_out_cmd_is_stopped_with_everything_it_started(harbour):
    harbour["queue"].write_text("cmd:[timeout=1s] sleep 41 & echo $! > kid.pid; sleep 42\n")
    said = []
    lanes.run(queue=harbour["queue"], done=harbour["done"], root=harbour["root"],
              poll_s=0.05, key=lambda: False, outside=lambda: False, log=said.append)  # fmt: skip
    kid = int((harbour["root"] / "kid.pid").read_text())
    assert any("timed out after 1 s" in m for m in said)
    for _ in range(20):  # the group was signalled: the shell's child went with it, orphaned by nothing
        if not lanes._alive(kid):
            break
        time.sleep(0.1)
    assert not lanes._alive(kid)
    assert harbour["done"].read_text().strip().endswith(" -15")


def test_only_a_group_of_its_own_is_ever_signalled():
    import os
    import signal

    own = subprocess.Popen(["sleep", "30"], start_new_session=True)
    shared = subprocess.Popen(["sleep", "30"])  # in this test's own group, as a launcher without a session leaves it
    try:
        assert lanes._group_of(own.pid) == own.pid
        assert lanes._group_of(shared.pid) is None and lanes._group_of(os.getpid()) is None
        lanes._signal(shared.pid, signal.SIGTERM)  # the process alone: this test is still here to say so
        assert shared.wait(timeout=5) == -signal.SIGTERM
        assert lanes._stop(own) == -signal.SIGTERM
        adopted = lanes._Adopted(_orphan("sleep 30"))
        adopted.terminate()
        for _ in range(30):
            if adopted.poll() is not None:
                break
            time.sleep(0.1)
        assert adopted.poll() == -1  # no outcome given: the old answer
    finally:
        for p in (own, shared):
            p.kill()
            p.wait()


def test_a_killed_coordinator_leaves_its_line_sailing_and_the_next_one_adopts_it(harbour):
    """The whole of item 2 on the Mac lane: the coordinator's process group is killed, as launchd kills a job;
    the line, in its own session, sails on; the next coordinator finds its row, holds its seat and writes its
    history when it ends."""
    import os
    import signal
    import sys

    from thorp.viable.s2_coordination import queue_store

    harbour["queue"].write_text("cmd: sleep 4\n")
    code = (
        "import sys; from pathlib import Path; from thorp.viable.s2_coordination import lanes;"
        "q, d, r = (Path(x) for x in sys.argv[1:4]);"
        "lanes.run(queue=q, done=d, root=r, poll_s=0.05, key=lambda: False, outside=lambda: False)"
    )
    first = subprocess.Popen([sys.executable, "-c", code, str(harbour["queue"]), str(harbour["done"]), str(harbour["root"])],
                             env={**os.environ, "THORP_QUEUE_PG": "0"}, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # fmt: skip
    try:
        row = None
        for _ in range(300):
            row = next((r for r in queue_store.at_sea() if r["pid"]), None)
            if row or first.poll() is not None:
                break
            time.sleep(0.05)
        assert row and row["text"] == "cmd: sleep 4" and row["coordinator"] == first.pid
    finally:
        os.killpg(first.pid, signal.SIGKILL)
        first.wait()
    assert lanes._alive(row["pid"]), "the line outlived its coordinator"
    assert not harbour["done"].exists()  # nothing recorded its exit: it has not exited
    said = _restart(harbour)
    assert any(f"adopted cmd: sleep 4 (pid {row['pid']})" in m for m in said)
    assert _history(harbour) == {"cmd: sleep 4": "adopted:exit-unknown"}
    assert queue_store.at_sea() == [] and not lanes._alive(row["pid"])


def test_a_hold_stops_the_lane_until_it_is_released(harbour):
    """`hold: <what is signed>` (11 November): the lane waits at it, nothing behind it starts, and once the line
    is gone the lane goes on."""
    s = harbour["specs"]
    for n in ("before", "after"):
        _spec(s, n, n)
    lines = [lanes.parse(t, s) for t in ("hold: Justin signs the candidate", "after")]
    assert (lines[0].kind, lines[0].payload, lines[0].lane) == ("hold", "Justin signs the candidate", "mac")
    ln, why = lanes.next_for("mac", lines, [], True)
    assert ln is None and why == "held: Justin signs the candidate"
    ln, why = lanes.next_for("mac", lines[1:], [], True)  # released: the line has left the queue
    assert ln is lines[1] and why is None
    # a line above the hold still sails; the one below does not
    above = [lanes.parse(t, s) for t in ("before", "hold: wait", "after")]
    assert lanes.next_for("mac", above, [], True)[0] is above[0]
    assert lanes.next_for("mac", above[1:], [above[0]], True) == (None, "held: wait")
