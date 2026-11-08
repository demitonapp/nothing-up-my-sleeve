"""Nevermores (induction heads): the attention patterns match the model, and the score is sane."""

import mlx.core as mx
import numpy as np

from thorp import evaluators, train


def test_patterns_reproduce_the_attention_output(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    x = mx.array(
        np.random.default_rng(0)
        .integers(3, prep.tokeniser.vocab_size, size=(2, 20))
        .astype(np.int32)
    )
    pats = model.attention_patterns(x)
    b = model.layers[0]
    a = b.attn
    h = model.tok(x) + model.pos(mx.arange(20))
    _, _, v = mx.split(a.qkv(b.ln1(h)), 3, axis=-1)
    v = v.reshape(2, 20, a.heads, a.head_dim).transpose(0, 2, 1, 3)
    mine = a.proj((pats[0] @ v).transpose(0, 2, 1, 3).reshape(2, 20, -1))
    theirs = a(b.ln1(h))
    assert np.allclose(np.array(mine), np.array(theirs), atol=1e-4)
    assert np.allclose(np.array(pats[0]).sum(-1), 1.0, atol=1e-5)


def test_evaluator_reports_scores(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
    )
    res = evaluators.get("nevermore")(ctx)
    m = res.metrics
    assert 0 <= m["nevermore/max_score"] <= 1
    assert m["nevermore/count"] == 0  # an untrained model has no Nevermores
    assert abs(m["nevermore/copy_gain"]) < 0.5
    assert {a["kind"] for a in res.artifacts} == {"nevermore"}


def test_star_tests_report_both_stars(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
    )
    m = evaluators.get("stars")(ctx).metrics
    assert 0 <= m["stars/duplicate_word/max_score"] <= 1
    assert m["stars/duplicate_word/count"] == 0  # untrained: nothing lit


def test_shared_score_is_the_best_layers_top_two_heads():
    from thorp.evaluators.stars import shared

    scores = np.array(
        [[0.01, 0.02, 0.01, 0.02], [0.08, 0.34, 0.08, 0.29], [0.05, 0.01, 0.24, 0.09]]
    )
    s, layer = shared(scores)
    assert layer == 1 and abs(s - 0.63) < 1e-9


def test_soundings_end_at_the_models_own_score(library, spec):
    from thorp.evaluators.soundings import evaluate as soundings

    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
    )
    m = soundings(ctx).metrics
    layers = len(model.layers)
    assert f"soundings/layer_{layers}/bpb" in m and f"soundings/layer_{layers - 1}/mlp_turn" in m
    assert all(v >= 0 for k, v in m.items() if k.endswith("_write"))


def test_successor_trick_scores_every_series(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets={},
    )
    m = evaluators.get("successor")(ctx).metrics
    assert 0 <= m["tricks/successor/score"] <= 1 and "tricks/successor/days" in m


def test_discovery_tests_score_every_written_list(library, spec):
    from thorp import fleet

    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=1,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets={},
        init_model=lambda: train.build_model(spec, prep.tokeniser.vocab_size),
    )
    m = evaluators.get("discovery")(ctx).metrics
    for k in ("breeders_test", "smiths_test", "gap_test"):
        assert fleet.TRICKS[k].leads_to in fleet.TRICKS
        assert 0 <= m[f"tricks/{k}/score"] <= 1 and f"tricks/{k}/floor_lift" in m
    assert not any(
        k.startswith("tricks/origin_test") for k in m
    )  # the explorer's pairs are not written yet
