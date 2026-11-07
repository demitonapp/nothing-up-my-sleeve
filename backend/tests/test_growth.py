"""Growing a smaller model into a bigger one: it starts out predicting what the smaller one did."""

import mlx.core as mx
import numpy as np
from mlx.utils import tree_flatten, tree_unflatten

from thorp.growth import grow
from thorp.models.gpt_mlx import GPT
from thorp.models.registry import GPTConfig


def test_grown_model_predicts_like_its_seed():
    mx.random.seed(3)
    small = GPTConfig(layers=2, width=64, heads=2, vocab=300, context=64)
    big = GPTConfig(layers=4, width=128, heads=4, vocab=300, context=64)
    a, b = GPT(small), GPT(big)
    # give the small model non-trivial weights in every slot, LayerNorms included
    a.update(
        tree_unflatten(
            [(k, v + 0.05 * mx.random.normal(v.shape)) for k, v in tree_flatten(a.parameters())]
        )
    )
    src = {k: np.array(v) for k, v in tree_flatten(a.parameters())}
    dst = {k: np.array(v) for k, v in tree_flatten(b.parameters())}
    grown, mask = grow(src, small, dst, big)
    b.update(tree_unflatten([(k, mx.array(v)) for k, v in grown.items()]))
    x = mx.array(np.random.default_rng(0).integers(0, 300, size=(2, 40)).astype(np.int32))
    assert np.abs(np.array(a(x)) - np.array(b(x))).max() < 2e-3  # equal up to kernel rounding
    # the inherited share: the old heads and units, not the new ones or the new layers
    assert (
        mask["layers.0.attn.qkv.weight"][:64].all()
        and not mask["layers.0.attn.qkv.weight"][64:128].any()
    )
    assert not mask["layers.3.attn.proj.weight"].any()


def test_a_seeded_run_starts_from_its_seed_and_freezes_it(library, spec):
    import copy

    from mlx.utils import tree_flatten

    from thorp import ledger, train

    quiet = lambda *a: None  # noqa: E731
    rec = ledger.Ledger()
    seed_spec = copy.deepcopy(spec)
    seed_spec["name"] = "seedling"
    prep = train.prepare(seed_spec, resolver=library["resolver"], log=quiet)
    train.train(seed_spec, prep, rec=rec, log=quiet)  # the tiny preset: 2 layers x 64, 2 heads
    grown = copy.deepcopy(spec)
    grown["name"] = "grown"
    grown["model"]["preset"] = "1m"  # 4 layers x 128, 4 heads of 32
    grown["seeded_from"] = {"run": "seedling", "mode": "freeze"}
    grown["checkpoint"] = {"every_steps": 10}  # so the interrupted run leaves a checkpoint
    out = train.train(grown, prep, rec=rec, stop_after=20, log=quiet)
    assert out["step"] == 20
    ck = train.load_master(train.latest_checkpoint(train.run_id(grown)))
    src = dict(tree_flatten(train.load_master(train.latest_checkpoint(train.run_id(seed_spec)))))
    w = dict(tree_flatten(ck))
    # frozen: the old heads' query weights are still the seedling's, tiled and halved
    assert np.allclose(
        np.array(w["layers.0.attn.qkv.weight"])[:64, :64],
        np.array(src["layers.0.attn.qkv.weight"])[:64] / 2,
        atol=1e-6,
    )


def test_transplant_hands_over_the_donors_heads(library, spec):
    import copy

    from mlx.utils import tree_flatten

    from thorp import ledger, train

    quiet = lambda *a: None  # noqa: E731
    rec = ledger.Ledger()
    donor = copy.deepcopy(spec)
    donor["name"] = "magician"
    donor["eval"]["evaluators"] = ["ce_bpb", "stars"]
    prep = train.prepare(donor, resolver=library["resolver"], log=quiet)
    train.train(donor, prep, rec=rec, log=quiet)
    apprentice = copy.deepcopy(spec)
    apprentice["name"] = "apprentice"
    apprentice["seed"] = 7
    apprentice["transplant"] = {"from_run": "magician", "star": "duplicate_word", "pos": True}
    model = train.build_model(apprentice, prep.tokeniser.vocab_size)
    fresh = {k: v.astype(mx.float32) for k, v in tree_flatten(model.parameters())}
    from mlx.utils import tree_unflatten

    new, handed = train.transplant_heads(apprentice, tree_unflatten(list(fresh.items())), quiet)
    got = dict(tree_flatten(new))
    src = dict(tree_flatten(train.load_master(train.latest_checkpoint(train.run_id(donor)))))
    layer, h = handed["layer"], handed["heads"][0]
    hd = 64 // 2  # the tiny preset: width 64, two heads
    rows = slice(h * hd, (h + 1) * hd)
    qkv = f"layers.{layer}.attn.qkv.weight"
    assert np.allclose(
        np.array(got[qkv])[rows], np.array(src[qkv])[rows]
    )  # the head's queries came over
    assert np.allclose(
        np.array(got["pos.weight"]), np.array(src["pos.weight"])
    )  # and its sense of position
    other = 1 - h
    if other not in handed["heads"]:
        orow = slice(other * hd, (other + 1) * hd)
        assert np.allclose(
            np.array(got[qkv])[orow], np.array(fresh[qkv])[orow]
        )  # the rest stays the apprentice's


def test_a_transplant_is_recorded_in_the_ledger(library, spec):
    import copy

    from thorp import ledger, train

    quiet = lambda *a: None  # noqa: E731
    rec = ledger.Ledger()
    donor = copy.deepcopy(spec)
    donor["name"] = "magician2"
    donor["eval"]["evaluators"] = ["ce_bpb", "stars"]
    prep = train.prepare(donor, resolver=library["resolver"], log=quiet)
    train.train(donor, prep, rec=rec, log=quiet)
    rx = copy.deepcopy(spec)
    rx["name"], rx["seed"] = "apprentice2", 9
    rx["transplant"] = {"from_run": "magician2", "star": "duplicate_word", "pos": True}
    train.train(rx, prep, rec=rec, stop_after=5, log=quiet)
    assert rec.query(
        "select 1 from artifacts where run_id=? and kind='transplant'", [train.run_id(rx)]
    )


def test_a_student_learns_from_its_teacher(library, spec):
    import copy

    from thorp import ledger, train

    quiet = lambda *a: None  # noqa: E731
    rec = ledger.Ledger()
    t = copy.deepcopy(spec)
    t["name"] = "teacher"
    prep = train.prepare(t, resolver=library["resolver"], log=quiet)
    train.train(t, prep, rec=rec, log=quiet)
    s = copy.deepcopy(spec)
    s["name"], s["seed"] = "student", 5
    s["optim"]["teacher"] = {"run": "teacher", "alpha": 0.5, "temperature": 2.0}
    out = train.train(s, prep, rec=rec, stop_after=15, log=quiet)
    assert out["step"] == 15
    losses = [
        r["value"]
        for r in rec.query(
            "select value from metrics where run_id=? and name='loss' order by step",
            [train.run_id(s)],
        )
    ]
    assert losses and all(
        v == v and v > 0 for v in losses
    )  # the logged loss stays the plain cross-entropy
