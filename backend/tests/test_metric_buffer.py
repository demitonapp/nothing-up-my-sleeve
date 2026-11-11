"""The trainers' per-step metrics, written many steps at a time (ledger.MetricBuffer, 11 November, the audit's item 4).

The rows are the rows an unbuffered voyage wrote; only when they reach the store moves. Every evaluation and every
checkpoint sees every step before it; an exception writes what waits on its way out; a resume from a checkpoint ends
with the same rows as an uninterrupted voyage; a store out of reach for a while keeps the rows for the next flush, and
one out of reach too long stops the voyage loudly.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections import Counter

import mlx.core as mx
import pytest

from thorp import ledger, paths, train
from thorp.ledger import BufferFull, Ledger, MetricBuffer


@pytest.fixture
def cpu():
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


quiet = lambda *a: None  # noqa: E731


def rows(rec, rid: str) -> Counter:
    """Every (step, name) the ledger holds for a run, counted (a doubled row counts twice)."""
    return Counter((r["step"], r["name"]) for r in rec.query("select step, name from metrics where run_id=?", [rid]))


def max_loss_step(rec, rid: str) -> int:
    return rec.query("select max(step) m from metrics where run_id=? and name='loss'", [rid])[0]["m"] or 0


# ---------------------------------------------------------------- the buffer by itself


class Flaky:
    """A recorder whose batch write fails `down` times with the given error, then writes to a real ledger."""

    def __init__(self, inner, down: int, error: Exception):
        self.inner, self.down, self.error, self.calls = inner, down, error, 0

    def metrics_many(self, rows):
        self.calls += 1
        if self.down > 0:
            self.down -= 1
            raise self.error
        self.inner.metrics_many(rows)


def test_the_buffer_writes_every_n_steps_with_each_steps_time(tmp_thorp):
    rec = Ledger(tmp_thorp / "b.sqlite")
    buf = MetricBuffer(rec, every=4, seconds=3600)
    for s in range(1, 4):
        buf.add("r", s, {"loss": 1.0 / s, "lr": 0.1})
    assert rows(rec, "r") == Counter() and len(buf) == 3  # nothing visible until the fourth step
    buf.add("r", 4, {"loss": 0.25, "lr": 0.1})
    assert len(buf) == 0 and sum(rows(rec, "r").values()) == 8 and buf.flushes == 1
    got = rec.query("select step, name, value, ts from metrics where run_id='r' order by rowid")
    assert [(g["step"], g["name"]) for g in got[:2]] == [(1, "loss"), (1, "lr")]  # in step order, as before
    assert got[0]["ts"] <= got[-1]["ts"]  # each row keeps the time its step was read, not the flush's
    buf.add("r", 5, {})  # an empty step writes nothing and waits for nothing
    assert len(buf) == 0


def test_a_store_out_of_reach_keeps_the_rows_for_the_next_flush(tmp_thorp):
    from sqlalchemy.exc import OperationalError

    rec = Ledger(tmp_thorp / "b.sqlite")
    said = []
    flaky = Flaky(rec, down=1, error=OperationalError("insert", {}, Exception("server closed the connection")))
    buf = MetricBuffer(flaky, every=2, seconds=3600, log=said.append)
    buf.add("r", 1, {"loss": 1.0})
    buf.add("r", 2, {"loss": 0.9})  # due: the store refuses, the rows are kept
    assert len(buf) == 2 and buf.failures == 1 and "kept" in said[0]
    buf.add("r", 3, {"loss": 0.8})  # not due again until `every` more steps have waited
    assert flaky.calls == 1
    buf.add("r", 4, {"loss": 0.7})
    assert len(buf) == 0 and sorted(s for s, _ in rows(rec, "r")) == [1, 2, 3, 4]  # all of them, once each


def test_a_long_outage_stops_the_voyage_and_a_fault_is_raised_at_once(tmp_thorp):
    from thorp.store import StoreDown

    rec = Ledger(tmp_thorp / "b.sqlite")
    buf = MetricBuffer(Flaky(rec, down=10**6, error=StoreDown("the store cannot be reached")), every=2, cap=6,
                       seconds=3600, log=quiet)  # fmt: skip
    with pytest.raises(BufferFull, match="more than the 6"):
        for s in range(1, 100):
            buf.add("r", s, {"loss": 1.0})
    assert len(buf) == 8  # it stopped at the first flush due past the cap, not after eating the voyage
    bad = MetricBuffer(Flaky(rec, down=1, error=ValueError("a bug in the write")), every=1, log=quiet)
    with pytest.raises(ValueError, match="a bug"):  # not the store's absence: raised, as the write always was
        bad.add("r", 1, {"loss": 1.0})


def test_a_strict_flush_tries_again_then_raises(tmp_thorp):
    rec = Ledger(tmp_thorp / "b.sqlite")
    naps = []
    locked = sqlite3.OperationalError("database is locked")
    ok = MetricBuffer(Flaky(rec, down=2, error=locked), every=100, tries=3, wait=1.5, sleep=naps.append, log=quiet)
    ok.add("r", 1, {"loss": 1.0})
    assert ok.flush(strict=True) and naps == [1.5, 1.5] and len(ok) == 0
    gone = MetricBuffer(Flaky(rec, down=5, error=locked), every=100, tries=3, wait=0, sleep=naps.append, log=quiet)
    gone.add("r", 2, {"loss": 1.0})
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        gone.flush(strict=True)
    assert len(gone) == 1  # kept: the caller decides (the trainer raises before its checkpoint)
    gone.flush_quietly()  # on the way out of an exception: said, never raised over the exception leaving


def test_a_recorder_without_a_batch_write_is_written_a_step_at_a_time(tmp_thorp):
    rec = Ledger(tmp_thorp / "b.sqlite")

    class OneAtATime:
        def metrics(self, rid, step, values):
            rec.metrics(rid, step, values)

    buf = MetricBuffer(OneAtATime(), every=3, seconds=3600)
    for s in (1, 2, 3):
        buf.add("r", s, {"loss": 1.0})
    assert len(buf) == 0 and sorted(s for s, _ in rows(rec, "r")) == [1, 2, 3]


def test_the_store_takes_many_steps_in_one_transaction(tmp_thorp):
    from thorp.ledger_store import PgLedger

    pg = PgLedger()
    try:
        pg.metrics_many([("r", 1, {"loss": 1.0, "lr": 0.1}, 10.0), ("r", 2, {"loss": 0.5}, 11.0)])
        got = pg.query("select step, name, value, ts from metrics where run_id='r' order by id")
        assert [(g["step"], g["name"], g["value"], g["ts"]) for g in got] == [
            (1, "loss", 1.0, 10.0), (1, "lr", 0.1, 10.0), (2, "loss", 0.5, 11.0)]  # fmt: skip
        with pytest.raises(Exception):  # noqa: B017  a row the table refuses: none of the batch is written
            pg.metrics_many([("r", 3, {"loss": 0.4}, 12.0), ("r", 4, {"loss": "not a number"}, 13.0)])
        assert len(pg.query("select 1 from metrics where run_id='r'")) == 3
        pg.metrics_many([("r", 3, {"loss": 0.4}, 12.0)])  # and the session is clean to write again
        assert len(pg.query("select 1 from metrics where run_id='r'")) == 4
    finally:
        pg.close()


# ---------------------------------------------------------------- in the voyage


def test_an_evaluation_and_a_checkpoint_see_every_step_before_them(library, spec, tmp_thorp, cpu, monkeypatch):
    spec["eval"]["every_steps"] = 30  # not a multiple of the flush (25): without a flush the store would hold 25
    spec["checkpoint"]["every_steps"] = 40
    spec["data"]["passes"] = 3  # the synthetic library is about 90 steps a pass
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
    rec, rid, seen = Ledger(tmp_thorp / "v.sqlite"), train.run_id(spec), {}
    real_eval, real_ckpt = train.run_evaluators, train.save_checkpoint

    def evaluate(spec_, rid_, step, *a, **k):
        seen[f"eval {step}"] = max_loss_step(rec, rid_)
        return real_eval(spec_, rid_, step, *a, **k)

    def checkpoint(rid_, step, *a, **k):
        seen[f"ckpt {step}"] = max_loss_step(rec, rid_)
        return real_ckpt(rid_, step, *a, **k)

    monkeypatch.setattr(train, "run_evaluators", evaluate)
    monkeypatch.setattr(train, "save_checkpoint", checkpoint)
    train.train(spec, prep, rec, stop_after=83, log=quiet)
    assert seen == {"eval 30": 30, "eval 60": 60, "ckpt 40": 40, "ckpt 80": 80}
    assert max_loss_step(rec, rid) == 83  # and the stop wrote the last three


def test_an_exception_writes_what_waits_on_its_way_out(library, spec, tmp_thorp, cpu, monkeypatch):
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
    rec, rid = Ledger(tmp_thorp / "x.sqlite"), train.run_id(spec)
    real = train.lr_at

    def lr_at(step, *a, **k):
        if step == 37:  # the 38th step fails before it is read: 37 were read, 25 of them written
            raise FloatingPointError("a step that went wrong")
        return real(step, *a, **k)

    monkeypatch.setattr(train, "lr_at", lr_at)
    with pytest.raises(FloatingPointError):
        train.train(spec, prep, rec, log=quiet)
    assert max_loss_step(rec, rid) == 37


@pytest.mark.parametrize("every", [1, 25])
def test_a_resumed_voyage_ends_with_the_rows_of_an_uninterrupted_one(library, spec, tmp_thorp, cpu, every):
    """The first leg stops at 73, past its checkpoint at 50 and past two flushes: its rows after 50 are in the store,
    and the resume forgets them and writes them again. Every (step, name) is there once, as on the straight run, and
    the values after the resume agree with it; buffered (25) or a commit a step (1, today's), the same.

    One difference is not the buffer's and predates it: the heading sieve (heading/<group>, the cosine between this
    window's move and the last one's) needs the previous window's move, which no checkpoint carries, so the first
    window after a resume (step 100 here) has no heading rows. It is asserted exactly, so a change to it is seen."""
    spec["data"]["passes"] = 3
    spec["ledger"] = {"flush_every": every}
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
    rid = train.run_id(spec)
    straight = Ledger(tmp_thorp / "straight.sqlite")
    assert train.train(spec, prep, straight, stop_after=120, log=quiet)["step"] == 120
    shutil.rmtree(paths.checkpoints_dir() / rid)

    resumed = Ledger(tmp_thorp / "resumed.sqlite")
    assert train.train(spec, prep, resumed, stop_after=73, log=quiet)["step"] == 73
    assert max_loss_step(resumed, rid) == 73 and train.latest_checkpoint(rid).name == "step-50"
    assert train.train(spec, prep, resumed, stop_after=120, log=quiet)["step"] == 120
    a, b = rows(straight, rid), rows(resumed, rid)
    assert max(a.values()) == 1 and max(b.values()) == 1, "no row doubled"
    assert b - a == Counter(), "nothing the straight run has not"
    assert {k for k in a - b} == {k for k in a if k[0] == 100 and k[1].startswith("heading/")} != set()
    va = {(r["step"], r["name"]): r["value"] for r in straight.query("select * from metrics where run_id=?", [rid])}
    vb = {(r["step"], r["name"]): r["value"] for r in resumed.query("select * from metrics where run_id=?", [rid])}
    timing = ("step_ms", "tokens_per_s", "mem_gb")
    assert max(abs(va[k] - vb[k]) for k in vb if k[1] not in timing and k[0] > 50) < 1e-3


def test_flush_every_is_read_from_the_spec_and_moves_nothing_else(library, spec, tmp_thorp, cpu):
    assert ledger.flush_every(spec) == 25 and ledger.flush_every({**spec, "ledger": {"flush_every": 1}}) == 1
    one = {**spec, "ledger": {"flush_every": 1}}  # today's behaviour, a commit a step
    prep = train.prepare(one, resolver=library["resolver"], log=quiet)
    a_rec, b_rec = Ledger(tmp_thorp / "one.sqlite"), Ledger(tmp_thorp / "many.sqlite")
    train.train(one, prep, a_rec, stop_after=60, log=quiet)
    train.train(spec, prep, b_rec, stop_after=60, log=quiet)
    assert {n for _, n in rows(a_rec, train.run_id(one))} == {n for _, n in rows(b_rec, train.run_id(spec))}
    assert sum(rows(a_rec, train.run_id(one)).values()) == sum(rows(b_rec, train.run_id(spec)).values())
