"""A voyage stopped by SIGTERM or SIGHUP checkpoints the step under way and resumes as if never stopped; checkpoint
retention (checkpoint.keep_last / keep_every) keeps what it should and nothing a waiting voyage reads; and
`thorp checkpoints prune` only prints unless told to delete (11 November, the audit's item 10)."""

from __future__ import annotations

import json
import os
import shutil
import signal

import mlx.core as mx
import pytest

from thorp import cli, data, paths, train
from thorp.ledger import Ledger


@pytest.fixture
def cpu():
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


def losses(rec: Ledger, rid: str) -> dict[int, float]:
    rows = rec.query("select step, value from metrics where run_id=? and name='loss'", [rid])
    return {r["step"]: r["value"] for r in rows}


def signal_during(monkeypatch, step: int, sig=signal.SIGTERM, again: bool = True):
    """Send `sig` to this process while step `step` (1-based) is under way, and, with `again`, a second one while
    its checkpoint is being written. Returns a function that takes the patches off."""
    batch, save = data.Stream.batch, train.save_checkpoint

    def sending_batch(self, s):
        if s == step - 1:
            os.kill(os.getpid(), sig)
        return batch(self, s)

    def sending_save(*a, **k):
        if again:
            os.kill(os.getpid(), signal.SIGTERM)
        return save(*a, **k)

    monkeypatch.setattr(data.Stream, "batch", sending_batch)
    monkeypatch.setattr(train, "save_checkpoint", sending_save)

    def off():
        monkeypatch.setattr(data.Stream, "batch", batch)
        monkeypatch.setattr(train, "save_checkpoint", save)

    return off


def test_a_signal_checkpoints_the_step_and_the_resume_is_exact(library, spec, tmp_thorp, cpu, monkeypatch):
    spec["data"]["passes"] = 3  # about 90 steps a pass
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    quiet = lambda *a: None  # noqa: E731
    rid = train.run_id(spec)

    straight = Ledger(tmp_thorp / "straight.sqlite")
    assert train.train(spec, prep, straight, stop_after=100, log=quiet)["step"] == 100
    shutil.rmtree(paths.checkpoints_dir() / rid)

    before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)
    stopped, said = Ledger(tmp_thorp / "stopped.sqlite"), []
    off = signal_during(monkeypatch, 37)
    out = train.train(spec, prep, stopped, stop_after=100, log=said.append)
    off()
    assert out == {"run_id": rid, "step": 37, "status": "stopped", "signal": "SIGTERM"}
    assert train.exit_code(out) == 143 and train.exit_code({"status": "finished"}) == 0
    assert stopped.get_run(rid)["status"] == "stopped: SIGTERM at step 37"
    assert train.latest_checkpoint(rid).name == "step-37"  # not a checkpoint step: written for the stop
    assert any("again" in line and "ignored" in line for line in said), "the second signal is logged and ignored"
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)) == before, "the handlers are put back"
    assert sorted(losses(stopped, rid)) == list(range(1, 38)), "every step up to the stop is in the store"

    assert train.train(spec, prep, stopped, stop_after=100, log=quiet)["step"] == 100
    a, b = losses(straight, rid), losses(stopped, rid)
    assert sorted(b) == list(range(1, 101))
    assert max(abs(a[s] - b[s]) for s in range(38, 101)) < 1e-3


def test_sighup_stops_too_and_a_checkpoint_step_is_written_once(library, spec, tmp_thorp, cpu, monkeypatch):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rid = train.run_id(spec)
    rec = Ledger(tmp_thorp / "l.sqlite")
    saves = []
    off = signal_during(monkeypatch, 50, signal.SIGHUP, again=False)
    real = train.save_checkpoint
    monkeypatch.setattr(train, "save_checkpoint", lambda *a, **k: saves.append(a[1]) or real(*a, **k))
    out = train.train(spec, prep, rec, log=lambda *a: None)
    off()
    assert out["status"] == "stopped" and out["step"] == 50 and out["signal"] == "SIGHUP"
    assert saves == [50] and rec.get_run(rid)["status"] == "stopped: SIGHUP at step 50"


def test_no_handler_is_set_off_the_main_thread():
    import threading

    got = {}

    def run():
        with train.stoppable() as flag:
            got["flag"] = flag
            got["installed"] = signal.getsignal(signal.SIGTERM)

    before = signal.getsignal(signal.SIGTERM)
    t = threading.Thread(target=run)
    t.start()
    t.join()
    assert got["installed"] is before and got["flag"].signal is None
    assert train.stop_flag().signal is None  # outside, a flag no signal raises


# ---------------------------------------------------------------- retention


def fake_checkpoints(rid: str, steps) -> None:
    for s in steps:
        d = train.checkpoint_root(rid) / f"step-{s}"
        d.mkdir(parents=True)
        (d / "state.json").write_text(json.dumps({"step": s}))
        (d / "model.safetensors").write_bytes(b"x" * 10)


def test_no_retention_keeps_everything(spec):
    assert train.retention(spec) is None
    assert train.retention({**spec, "checkpoint": {"every_steps": 50, "keep_every": 1000}}) == (1, 1000)
    assert train.retention({**spec, "checkpoint": {"every_steps": 50, "keep_last": 3}}) == (3, 0)
    assert train.retention({**spec, "checkpoint": {"every_steps": 50, "keep_last": 0}}) == (1, 0)


def test_the_loop_prunes_to_the_last_and_the_milestones(library, spec, tmp_thorp, cpu):
    spec["data"]["passes"] = 2
    spec["checkpoint"] = {"every_steps": 10, "keep_last": 2, "keep_every": 40}
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rid = train.run_id(spec)
    said = []
    assert train.train(spec, prep, Ledger(tmp_thorp / "l.sqlite"), stop_after=100, log=said.append)["step"] == 100
    assert train.checkpoint_steps(rid) == [40, 80, 90, 100]
    assert not [p for p in train.checkpoint_root(rid).iterdir() if p.name.startswith(".")], "nothing half-deleted"
    assert any(line.startswith("checkpoints: pruned") for line in said)


def test_a_step_a_waiting_voyage_seeds_from_is_kept(tmp_thorp):
    rid = "a" * 40
    fake_checkpoints(rid, (10, 20, 30, 40, 50))
    specs = [
        {"seeded_from": {"run": "parent", "step": 20}},  # by name
        {"seeded_from": {"run": rid, "step": 30}},  # by id
        {"seeded_from": {"run": "another", "step": 10}},  # another run's
        {"seeded_from": {"run": "parent"}},  # the newest, kept anyway
        {"optim": {"teacher": {"run": "parent"}}},
    ]
    pinned = train.pinned_steps(rid, "parent", specs)
    assert pinned == {20, 30}
    assert [p.name for p in train.prune_plan(rid, 1, 0, pinned)] == ["step-10", "step-40"]
    assert [p.name for p in train.prune_plan(rid, 2, 20, set())] == ["step-10", "step-30"]


def test_the_waiting_voyages_are_read_from_the_queue(tmp_thorp, monkeypatch):
    from thorp.viable.s2_coordination import queue_store

    specs = tmp_thorp / "specs"
    (specs / "fitouts").mkdir(parents=True)
    (specs / "fitouts" / "leg.yaml").write_text("name: leg\nseeded_from: {run: parent, step: 20}\n")
    (specs / "fitouts" / "box.yaml").write_text("name: box\nseeded_from: {run: parent, step: 30}\n")
    real = paths.resolve
    monkeypatch.setattr(paths, "resolve", lambda p: specs if str(p) == "specs" else real(p))
    monkeypatch.setattr(queue_store, "pending_texts", lambda: ["fitouts/leg", "cmd: echo hi", "fitouts/missing"])
    monkeypatch.setattr(queue_store, "at_sea", lambda: [{"text": "vast: fitouts/box"}])
    assert train.pinned_steps("b" * 40, "parent") == {20, 30}


def test_an_unscored_deferred_step_is_kept(tmp_thorp):
    rid = "c" * 40
    fake_checkpoints(rid, (10, 20, 30))
    rec = Ledger(tmp_thorp / "l.sqlite")
    rec.artifact(rid, 10, "eval_offline", "step-10", "", json.dumps({"evaluators": ["stars"], "weights": "step-10"}))
    rec.artifact(rid, 20, "eval_offline", "step-20", "", json.dumps({"evaluators": ["stars"], "weights": "step-20"}))
    rec.metrics(rid, 20, {"eval/seconds/stars": 1.0})  # step 20 scored, step 10 not
    for snap in ("eval-15", "eval-25.tmp"):  # item 5's weights-only snapshots, finished and being written
        (train.checkpoint_root(rid) / snap).mkdir()
        (train.checkpoint_root(rid) / snap / "state.json").write_text("{}")
    assert train.unscored_steps(rid, rec) == {10}
    assert [p.name for p in train.prune_checkpoints(rid, 1, 0, apply=True, look=rec)] == ["step-20"]
    assert train.checkpoint_steps(rid) == [10, 30]
    assert (train.checkpoint_root(rid) / "eval-15").exists() and (train.checkpoint_root(rid) / "eval-25.tmp").exists()


class _Reader:
    def __init__(self, row):
        self.row = row

    def find_run(self, ref):
        return self.row if ref in (self.row["run_id"], self.row["name"]) else None

    def query(self, sql, params=()):
        return []


def test_the_cli_prints_unless_told_to_delete(tmp_thorp, monkeypatch, capsys):
    rid = "d" * 40
    fake_checkpoints(rid, (100, 200, 300, 400, 500))
    row = {"run_id": rid, "name": "done", "status": "finished"}
    monkeypatch.setattr(train, "reader", lambda: _Reader(row))
    monkeypatch.setattr(train, "_voyages_waiting", lambda: [])
    assert cli.main(["checkpoints", "prune", "done", "--keep-last", "1", "--keep-every", "200"]) == 0
    out = capsys.readouterr().out
    assert "would delete" in out and "step-100" in out and "step-300" in out and "--apply" in out
    assert train.checkpoint_steps(rid) == [100, 200, 300, 400, 500], "a dry run deletes nothing"
    assert cli.main(["checkpoints", "prune", "done", "--keep-every", "200", "--dry-run", "--apply"]) == 0
    assert train.checkpoint_steps(rid) == [100, 200, 300, 400, 500], "--dry-run wins"
    assert cli.main(["checkpoints", "prune", "done", "--keep-every", "200", "--apply"]) == 0
    assert train.checkpoint_steps(rid) == [200, 400, 500]
    row["status"] = "running"
    assert cli.main(["checkpoints", "prune", "done", "--apply"]) == 2
    assert train.checkpoint_steps(rid) == [200, 400, 500]
