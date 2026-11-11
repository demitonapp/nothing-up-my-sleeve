"""The newest value of every metric, kept by the database (11 November, the audit's item 7): s1.metric_latest and
its triggers on s1.metrics, its backfill, the set-based dashboard readers that read it (the same payloads as the
per-run readers, value for value), and /api/metrics's bounds."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from thorp import ledger_store, store


@pytest.fixture(autouse=True)
def _reader_closed():
    """The ledger's per-thread Postgres reader holds a transaction open; closed after each test so the next test's
    truncate is not left waiting on it."""
    yield
    from thorp.ledger import close_reader

    close_reader()


def _latest(run_id: str) -> dict[str, tuple[int, float]]:
    with store.session() as s:
        rows = s.execute(text("select name, step, value from s1.metric_latest where run_id=:r"), {"r": run_id}).all()
    return {n: (st, v) for n, st, v in rows}


def _sql(q: str, **params) -> None:
    with store.session() as s:
        s.execute(text(q), params)


# ---------------------------------------------------------------- the triggers


def test_an_insert_keeps_the_newest_by_step_then_id():
    pg = ledger_store.PgLedger()
    pg.metrics("r1", 5, {"a": 1.0, "b": 10.0})
    assert _latest("r1") == {"a": (5, 1.0), "b": (5, 10.0)}
    pg.metrics("r1", 3, {"a": 2.0})  # an older step written later does not replace the newer one
    assert _latest("r1")["a"] == (5, 1.0)
    pg.metrics("r1", 5, {"a": 3.0})  # a re-score at the same step does: its id is larger
    assert _latest("r1")["a"] == (5, 3.0)
    # one statement, steps out of order: the batch's newest row stands
    _sql("insert into s1.metrics (run_id, step, name, value, ts) values"
         " ('r1', 9, 'a', 4, 0), ('r1', 7, 'a', 5, 0), ('r1', 9, 'c', 6, 0), ('r1', 8, 'c', 7, 0)")  # fmt: skip
    assert _latest("r1") == {"a": (9, 4.0), "b": (5, 10.0), "c": (9, 6.0)}
    assert ledger_store.latest_mismatches(["r1"]) == []
    pg.close()


def test_a_delete_falls_back_and_a_reinsert_brings_the_newest_back():
    pg = ledger_store.PgLedger()
    for step in (1, 2, 3, 4, 5):
        pg.metrics("r2", step, {"loss": float(10 - step), "lr": 0.1 * step})
    pg.metrics("r2", 2, {"rare": 1.0})
    pg.truncate_after("r2", 3)  # a resume, or the fold's delete past the leg start
    assert _latest("r2") == {"loss": (3, 7.0), "lr": (3, pytest.approx(0.3)), "rare": (2, 1.0)}
    for step in (4, 5, 6):  # the fold's re-insert
        pg.metrics("r2", step, {"loss": float(20 - step), "lr": 0.2 * step})
    assert _latest("r2")["loss"] == (6, 14.0)
    pg.clear_step("r2", 2, tables=("metrics",))  # the only row of `rare` goes, so its latest goes
    assert "rare" not in _latest("r2")
    _sql("delete from s1.metrics where run_id='r2' and step >= 5")  # deleting rows that were not newest is a no-op
    assert _latest("r2")["loss"] == (4, 16.0)
    assert ledger_store.latest_mismatches(["r2"]) == []
    _sql("update s1.metrics set value = 99 where run_id='r2' and name='loss' and step = 4")
    assert _latest("r2")["loss"] == (4, 99.0)
    _sql("truncate s1.metrics")
    assert _latest("r2") == {}
    pg.close()


def test_the_backfill_repairs_and_is_idempotent():
    pg = ledger_store.PgLedger()
    for step in (1, 2, 3):
        pg.metrics("r3", step, {"x": float(step), "y": -float(step)})
    _sql("delete from s1.metric_latest where run_id='r3' and name='x'")  # a pair missing
    _sql("update s1.metric_latest set step=1, value=-1, metric_id=-5 where run_id='r3' and name='y'")  # a stale one
    _sql("insert into s1.metric_latest values ('r-gone', 'z', 1, 1, 0, -6)")  # a run with no rows left
    assert ledger_store.latest_mismatches(["r3", "r-gone"])
    got = ledger_store.backfill_latest(log=None)
    assert got["pruned"] == 1
    assert ledger_store.latest_mismatches(["r3", "r-gone"]) == []
    assert ledger_store.backfill_latest(log=None)["upserted"] == 0  # nothing newer the second time
    pg.close()


# ---------------------------------------------------------------- the downsampler


def test_downsample_keeps_the_ends_and_the_extremes():
    from thorp.dash.batched import downsample

    steps = list(range(100))
    values = [float((i * 37) % 101) for i in steps]
    values[41], values[73] = -5.0, 500.0
    s, v = downsample(steps, values, 10)
    assert len(s) <= 10 and s[0] == 0 and s[-1] == 99
    assert 41 in s and 73 in s and min(v) == -5.0 and max(v) == 500.0
    assert s == sorted(s) and all(values[i] == x for i, x in zip(s, v, strict=True))
    assert downsample(steps[:5], values[:5], 10) == [steps[:5], values[:5]]  # under the cap: as it is
    assert downsample(steps, values, 0) == [steps, values]  # no cap
    s, _ = downsample(steps, [float("nan")] * 100, 3)  # no finite value: the ends and the spacing
    assert s[0] == 0 and s[-1] == 99


def test_wanted_reads_a_comma_list_with_prefixes():
    from thorp.dash.batched import cap_of, wanted

    have = ["loss", "lr", "eval/a/bpb_mean", "eval/b/bpb_mean", "grad_norm/layer_0"]
    assert wanted("loss,eval/*", have) == ["loss", "eval/a/bpb_mean", "eval/b/bpb_mean"]
    assert wanted("nope", have) == []
    assert cap_of("40") == 40 and cap_of("") == 0 and cap_of("x") == 0 and cap_of("-3") == 0


# ---------------------------------------------------------------- the readers: set-based = per run, on Postgres


def _spec(preset: str, seed: int) -> str:
    return json.dumps({"model": {"preset": preset}, "seed": seed, "eval": {"sets": ["lists/hole.csv"]},
                       "optim": {"batch_tokens": 1024, "lr": 0.001}, "data": {"recipe": "lists/r.csv", "passes": 1}})  # fmt: skip


def _write(led, ship: str) -> None:
    """A small ledger: two runs, steps written out of order, a re-score at the newest step, per-layer pushes (and a
    part of one, which the readers skip), held-out sets, laws, the bridge card and a star with and without its
    shared metric."""
    led.run({"run_id": "aa", "name": "one", "ship": f"{ship}: one", "status": "finished", "started": "2026-11-01",
             "spec_json": _spec("9m", 1)})  # fmt: skip
    led.run({"run_id": "bb", "name": "two", "ship": f"{ship}: two", "status": "finished", "started": "2026-11-02",
             "spec_json": _spec("21m", 2)})  # fmt: skip
    for rid, k in (("aa", 1.0), ("bb", 2.0)):
        led.metrics(rid, 0, {"plan/tokens_total": 1e6 * k, "plan/total_steps": 100.0, "lr": 0.0})
        for step in (10, 30, 20):  # out of step order
            led.metrics(rid, step, {
                "lr": 0.01 * step, "grad_norm/layer_0": k * step, "grad_norm/layer_1": k + step,
                "grad_norm/layer_0/attn": 3.0, "eval/hole/bpb_mean": 2.0 - step / 100 / k,
                "eval/hole/bpb_mean_en": 1.9 - step / 100, "eval/hole/split/space/bpb_mean": 1.0 + step,
                "eval/other/bpb_mean": 3.0 - step / 50, "laws/model/zipf": k / step,
                "eval/hole-cards-unseen/bpb_mean_en": 2.5 - step / 100,
                "stars/bridge/layer_0": step / 10, "stars/bridge/layer_2": k, "stars/bridge/max_score": step * k,
                "stars/mover/max_score": step / 100 * k,
            })  # fmt: skip
            if rid == "aa":
                led.metrics(rid, step, {"stars/mover/shared_score": step / 50})
            else:  # no shared metric: worked out from the stars artifact
                led.artifact(rid, step, "stars", text=json.dumps({"mover": [[0.1, step / 100, 0.05]]}))
        led.metrics(rid, 30, {"eval/hole/bpb_mean": 1.5, "lr": 0.5, "stars/mover/max_score": 0.9})  # a re-score
        led.artifact(rid, 0, "recipe", text=json.dumps([{"book_id": "x"}, {"book_id": "y"}]))
        led.artifact(rid, 30, "recipe", text=json.dumps([{"book_id": "x"}]))


def _same(monkeypatch, f, module, guards: set[str]):
    """f() through the per-run readers (the guards named, which now hand Postgres to the set-based readers, answer
    "not Postgres" so the old loop runs; the helpers it calls still read Postgres) and through the set-based ones,
    as JSON: the first difference, with its context, is the failure."""
    import sys

    real = getattr(module, "_ledger_pg" if hasattr(module, "_ledger_pg") else "_use_pg")
    name = "_ledger_pg" if hasattr(module, "_ledger_pg") else "_use_pg"

    turned: list[str] = []

    def legacy() -> bool:
        caller = sys._getframe(1).f_code.co_name
        if caller in guards:
            turned.append(caller)
            return False
        return real()

    monkeypatch.setattr(module, name, legacy)
    old = json.dumps(f(), sort_keys=True, default=str)
    monkeypatch.setattr(module, name, real)
    assert turned, "the per-run path never ran"
    new = json.dumps(f(), sort_keys=True, default=str)
    at = next((i for i, (a, b) in enumerate(zip(old, new, strict=False)) if a != b), min(len(old), len(new)))
    assert old == new, f"per run: ...{old[max(at - 150, 0):at + 80]}\nset-based: ...{new[max(at - 150, 0):at + 80]}"
    return json.loads(new)


def test_the_set_based_readers_answer_what_the_per_run_readers_did(tmp_thorp, monkeypatch):
    from thorp import expeditions, fleet, ledger
    from thorp.dash import server

    monkeypatch.setenv("THORP_LEDGER_PG", "1")
    v = fleet.EXPEDITIONS["first_light"]
    pg = ledger_store.PgLedger()
    _write(pg, v.ship)
    pg.close()
    assert ledger_store.latest_mismatches(["aa", "bb"]) == []
    got = _same(monkeypatch, lambda: server._last_scores(["aa", "bb", "none"]), server, {"_last_scores"})
    assert got["aa"]["laws/model/zipf"] == 1 / 30 and got["none"] == {}
    got = _same(monkeypatch, server.api_compare, server, {"api_compare", "api_runs"})
    assert got[0]["n_books"] == 2 and got[0]["bpb"][-1] == 1.5 and "grad_norm/layer_0/attn" not in got[0]["push"]
    got = _same(monkeypatch, server.api_bridge, server, {"api_bridge"})
    assert [r["curve"] for r in got["runs"]] == [[3.0, None, 1.0], [3.0, None, 2.0]] and got["runs"][0]["step"] == 30
    keys = ("run_id", "name", "preset", "seed", "hole_bpb_mean")
    got = _same(monkeypatch, lambda: [{k: r[k] for k in keys} for r in server.api_runs()], server, {"api_runs"})
    assert got[0]["hole_bpb_mean"] == 1.5
    assert _same(monkeypatch, lambda: server._run_row_by_name("two")["run_id"], server, {"_run_row_by_name"}) == "bb"
    got = _same(monkeypatch, lambda: expeditions.summary("first_light")["runs"], ledger, {"summary"})
    mover = {r["run_id"]: next(x for x in r["stars"] if x["star"] == "mover") for r in got}
    assert mover["aa"]["shared_steps_to_lit"] == 10 and mover["bb"]["shared_best"] == pytest.approx(0.4)
    assert got[0]["ft_en"] == pytest.approx(2.2)


def test_api_metrics_bounds(tmp_thorp, monkeypatch):
    from thorp.dash import server

    monkeypatch.setenv("THORP_LEDGER_PG", "1")
    pg = ledger_store.PgLedger()
    _write(pg, "Ship")
    pg.close()
    assert server.api_metrics("aa") == ledger_store.metrics_series("aa")  # no bounds: as before
    got = server.api_metrics("aa", "lr,eval/hole/*", "3")
    assert set(got) == {"lr", "eval/hole/bpb_mean", "eval/hole/bpb_mean_en", "eval/hole/split/space/bpb_mean"}
    full = ledger_store.metrics_series("aa")
    assert got["eval/hole/bpb_mean"] == full["eval/hole/bpb_mean"]  # three points: under the cap
    assert got["lr"][0][0] == 0 and got["lr"][0][-1] == 30 and len(got["lr"][0]) <= 4
    monkeypatch.setenv("THORP_LEDGER_PG", "0")  # the SQLite path takes the same bounds
    from thorp.ledger import Ledger

    _write(Ledger(), "Ship")
    assert set(server.api_metrics("aa", "lr,eval/hole/*", "3")) == set(got)
