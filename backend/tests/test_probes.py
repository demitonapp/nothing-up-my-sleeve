"""Trait probes: a separable trait is found, a shuffled one is not, and thin held-out sets refuse."""

import numpy as np

from thorp import evaluators, train
from thorp.evaluators import probes


def _feats(rng, books, layers=3, width=8, windows=6, shift=None):
    out = {}
    for b in books:
        f = rng.normal(size=(windows, layers, width)).astype(np.float32)
        if shift is not None:
            f[:, 1, :] += shift  # the trait lives in layer 1 only
        out[b] = f
    return out


def test_separable_trait_is_found_at_the_right_layer():
    rng = np.random.default_rng(0)
    pos, neg = [f"p{i}" for i in range(6)], [f"n{i}" for i in range(6)]
    feats = {**_feats(rng, pos, shift=3.0), **_feats(rng, neg, shift=-3.0)}
    labels = {**{b: 1 for b in pos}, **{b: 0 for b in neg}}
    r = probes.probe(feats, labels, train=pos[:4] + neg[:4], test=pos[4:] + neg[4:])
    assert r["status"] == "found" and r["best_layer"] == 1
    assert r["auc"][1] > 0.95 and r["n_test"] == [2, 2]


def test_shuffled_trait_is_not_found():
    rng = np.random.default_rng(1)
    books = [f"b{i}" for i in range(12)]
    feats = _feats(rng, books)
    labels = {b: i % 2 for i, b in enumerate(books)}
    r = probes.probe(feats, labels, train=books[:8], test=books[8:])
    assert r["status"] == "not_found" and max(r["auc"]) < 0.8


def test_thin_held_out_set_is_untestable():
    rng = np.random.default_rng(2)
    books = [f"b{i}" for i in range(6)]
    feats = _feats(rng, books, shift=2.0)
    labels = {"b0": 1, "b1": 1, "b2": 0, "b3": 0, "b4": 1, "b5": 0}
    r = probes.probe(feats, labels, train=books[:4], test=books[4:])
    assert r["status"] == "untestable" and "held-out" in r["reason"]
    r = probes.probe(feats, labels, train=["b0", "b1"], test=books[2:])
    assert r["status"] == "untestable" and "shelf" in r["reason"]


def test_auc_is_the_rank_statistic():
    assert probes.auc(np.array([3.0, 4.0]), np.array([1.0, 2.0])) == 1.0
    assert probes.auc(np.array([1.0, 2.0]), np.array([3.0, 4.0])) == 0.0
    assert probes.auc(np.array([1.0]), np.array([1.0])) == 0.5


def test_evaluator_writes_an_artifact_and_every_trait_has_a_status(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
        languages={},
        recipe=prep.recipe,
    )
    res = evaluators.get("probes")(ctx)
    (art,) = [a for a in res.artifacts if a["kind"] == "probes"]
    import json

    data = json.loads(art["text"])
    assert data["traits"], "the family traits exist even without lists/traits.csv rows"
    for t in data["traits"].values():
        assert t["status"] in ("found", "not_found", "untestable")
    # one hole card: no family can have two held-out books a side
    assert all(t["status"] == "untestable" for t in data["traits"].values())
