"""Re-scoring a checkpoint on a new held-out list keeps the scores it already has on another."""

from thorp.ledger import Ledger
from thorp.sources.gutenberg import set_for_list


def row(rid, step, s, b):
    return {
        "run_id": rid,
        "step": step,
        "set": s,
        "book_id": b,
        "ce_nats": 1.0,
        "bpb": 1.0,
        "tokens": 10,
        "bytes": 30,
    }


def test_clear_step_scoped_to_sets(tmp_thorp):
    rec = Ledger()
    rec.evals(
        [row("r", 9, "hole-cards", "a"), row("r", 9, "truths", "b"), row("r", 9, "truths", "c")]
    )
    rec.clear_step("r", 9, tables=("evals",), sets=["truths"])
    left = rec.query('select "set", book_id from evals where run_id=?', ["r"])
    assert left == [{"set": "hole-cards", "book_id": "a"}]


def test_clear_step_unscoped_clears_the_step(tmp_thorp):
    rec = Ledger()
    rec.evals([row("r", 9, "hole-cards", "a"), row("r", 9, "truths", "b")])
    rec.clear_step("r", 9)
    assert rec.query("select * from evals where run_id=?", ["r"]) == []


def test_manifest_set_for_lists():
    assert set_for_list("lists/hole-cards-v2.csv") == "hole-card"
    assert set_for_list("lists/truths.csv") == "truth"
    assert set_for_list("lists/pool-400.csv") == "recipe"


def test_rescore_on_a_new_list_keeps_the_old_scores(library, spec, tmp_thorp, monkeypatch):
    monkeypatch.setenv("THORP_LEDGER_PG", "0")  # the runs it rescores are written to its SQLite ledger
    import mlx.core as mx

    from tests.conftest import make_text, register_local
    from thorp import train

    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    try:
        register_local("loc-truth", make_text(77, 3000), "truth")
        library["lists"]["truths.csv"] = ["loc-truth"]
        quiet = lambda *a: None  # noqa: E731
        rec = Ledger()
        prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
        out = train.train(spec, prep, rec, stop_after=50, log=quiet)
        rid = train.run_id(spec)
        rec.run(
            {
                "run_id": rid,
                "name": "test",
                "spec_json": __import__("json").dumps(spec),
                "status": "finished",
                "started": "x",
            }
        )
        step = train.rescore(
            rid,
            sets=["hole.csv", "truths.csv"],
            evaluators=["ce_bpb"],
            resolver=library["resolver"],
            rec=rec,
            log=quiet,
        )
        assert step == out["step"] == 50
        sets = {
            r["set"] for r in rec.query('select "set" from evals where run_id=? and step=50', [rid])
        }
        assert sets == {"hole", "truths"}
        names = {r["name"] for r in rec.query("select name from metrics where run_id=?", [rid])}
        assert "eval/truths/bpb_mean" in names
        arts = rec.query("select step from artifacts where run_id=? and kind='eval_sets'", [rid])
        assert 50 in {a["step"] for a in arts}
        # a re-score on the truths alone replaces only the truths rows at that step
        train.rescore(
            rid,
            sets=["truths.csv"],
            evaluators=["ce_bpb"],
            resolver=library["resolver"],
            rec=rec,
            log=quiet,
        )
        # a run can be named instead of given by id (queue lines are written by name)
        by_name = train.rescore(
            "test", evaluators=["nevermore"], resolver=library["resolver"], rec=rec, log=quiet
        )
        assert by_name == 50
        n = rec.query(
            'select "set", count(*) n from evals where run_id=? and step=50 group by "set"', [rid]
        )
        assert {r["set"]: r["n"] for r in n} == {"hole": 1, "truths": 1}
    finally:
        mx.set_default_device(before)
