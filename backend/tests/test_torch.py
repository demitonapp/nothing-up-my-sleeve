"""The PyTorch backend (thorp/models/gpt_torch.py, thorp/train_torch.py, thorp/models/ops.py), on the CPU.

The torch GPT given the MLX GPT's weights computes the same logits, residual streams and attention; the
optimiser, the clip and every loss rule are MLX's; a tiny torch voyage trains, resumes within tolerance of
an uninterrupted one and records the scaffold's metrics; its checkpoints load in MLX; the evaluators score
the same weights alike on either backend; and nothing on the torch path needs MLX.
"""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import mlx.core as mx  # noqa: E402
import mlx.optimizers as optim  # noqa: E402
from mlx.utils import tree_flatten  # noqa: E402

from thorp import evaluators, paths, train, train_torch  # noqa: E402
from thorp.ledger import Ledger  # noqa: E402
from thorp.models import ops, registry  # noqa: E402
from thorp.models.backend import backend_of  # noqa: E402


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    import dataclasses

    from thorp import vsm

    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.delenv("THORP_BACKEND", raising=False)
    # these tests are the loop's, not the gate's: the standard rule (every voyage names an SOP version) is advisory
    # here, as in test_scaffold's voyages. Until 11 November every voyage in this file was refused at the gate, so
    # no torch voyage was being tested at all.
    monkeypatch.setitem(vsm.POLICIES, "standard", dataclasses.replace(vsm.POLICIES["standard"], enforced=False))
    torch.manual_seed(0)
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


SHAPE = {"preset": "300k", "layers": 2, "width": 64, "heads": 2}  # the registry's "tiny" is gone: its shape, by override


@pytest.fixture
def spec(spec):
    """conftest's spec in a shape the registry still builds (two layers of two 32-wide heads)."""
    spec["model"].update(SHAPE)
    return spec


def twins(positions="learned", layers=2, width=64, heads=2, vocab=97, context=32, kv_heads=0, seed=3):
    """An MLX GPT and a torch GPT holding the same fp32 weights."""
    cfg = registry.GPTConfig(
        layers=layers, width=width, heads=heads, vocab=vocab, context=context, positions=positions, kv_heads=kv_heads
    )
    from thorp.models.gpt_mlx import GPT as MGPT
    from thorp.models.gpt_torch import GPT as TGPT

    mx.random.seed(seed)
    m = MGPT(cfg)
    t = TGPT(cfg)
    flat = {k: np.array(v) for k, v in tree_flatten(m.parameters())}
    assert set(flat) == {k for k, _ in t.named_parameters()}, "the two backends name their weights alike"
    train_torch.set_weights(t, {k: torch.from_numpy(v) for k, v in flat.items()})
    return m, t


def toks(B=3, T=24, vocab=97, seed=0):
    return np.random.default_rng(seed).integers(0, vocab, (B, T)).astype(np.int32)


@pytest.mark.parametrize("positions", ["learned", "rope"])
def test_the_torch_gpt_is_the_mlx_gpt(positions):
    m, t = twins(positions)
    x = toks()
    assert m.parameter_counts() == t.parameter_counts()
    with torch.no_grad():
        np.testing.assert_allclose(np.array(m(mx.array(x))), t(x).numpy(), atol=2e-5, rtol=1e-4)
        for a, b in zip(m.hidden(mx.array(x)), t.hidden(x), strict=True):
            np.testing.assert_allclose(np.array(a), b.numpy(), atol=2e-5, rtol=1e-4)
    # the attention patterns match the reference (MLX's), every layer and head
    for a, b in zip(ops.attention_patterns(m, x), ops.attention_patterns(t, x), strict=True):
        assert a.shape == b.shape == (3, 2, 24, 24)
        np.testing.assert_allclose(a, b, atol=1e-5)
        np.testing.assert_allclose(b.sum(axis=-1), 1.0, atol=1e-5)
        assert np.allclose(np.triu(b, 1), 0.0), "causal"
    # forward_attending's picked heads are the full readout's, and its logits the plain forward pass's
    picks = {0: [1], 1: [0, 1]}
    logits, pats = t.forward_attending(torch.as_tensor(x).long(), picks)
    full = t.attention_patterns(x)
    for (li, h), p in pats.items():
        torch.testing.assert_close(p, full[li][:, h])
    torch.testing.assert_close(logits, t(x))


def test_ops_agree_across_backends():
    m, t = twins("rope")
    x = toks()
    np.testing.assert_allclose(ops.token_ce(m, x[:, :-1], x[:, 1:]), ops.token_ce(t, x[:, :-1], x[:, 1:]), atol=1e-4)
    np.testing.assert_allclose(ops.log_probs(m, x), ops.log_probs(t, x), atol=1e-4)
    np.testing.assert_allclose(ops.pooled_hidden(m, x), ops.pooled_hidden(t, x), atol=1e-5)
    mask = (np.arange(24)[None, :, None] < np.array([24, 10, 5])[:, None, None]).astype(np.float32)
    np.testing.assert_allclose(ops.pooled_hidden(m, x, mask), ops.pooled_hidden(t, x, mask), atol=1e-5)
    for a, b in zip(ops.lens_log_probs(m, x), ops.lens_log_probs(t, x), strict=True):
        np.testing.assert_allclose(a, b, atol=1e-4)
    qm = np.zeros(97, bool)
    qm[[3, 5]] = True
    for a, b in zip(ops.token_stats(m, x[:, :-1], x[:, 1:], qm), ops.token_stats(t, x[:, :-1], x[:, 1:], qm), strict=True):
        np.testing.assert_allclose(a, b, atol=1e-4)
    pm, tm = ops.softmax_top(m, x[:1], 5), ops.softmax_top(t, x[:1], 5)
    np.testing.assert_allclose(pm[0], tm[0], atol=1e-5)


def test_the_optimiser_and_the_clip_are_mlx_s():
    rng = np.random.default_rng(1)
    w = {"a.weight": rng.normal(size=(4, 3)).astype(np.float32), "b.weight": rng.normal(size=(5,)).astype(np.float32)}
    gs = [{k: (rng.normal(size=v.shape) * 3).astype(np.float32) for k, v in w.items()} for _ in range(3)]
    opt_m = optim.AdamW(learning_rate=1e-2, betas=[0.9, 0.95], weight_decay=0.1)
    pm = {k: mx.array(v) for k, v in w.items()}
    opt_t = train_torch.AdamW(1e-2, [0.9, 0.95], 0.1)
    pt = {k: torch.from_numpy(v.copy()) for k, v in w.items()}
    for g in gs:
        gm, nm = optim.clip_grad_norm({k: mx.array(v) for k, v in g.items()}, 1.0)
        pm = opt_m.apply_gradients(gm, pm)
        gt = {k: torch.from_numpy(v.copy()) for k, v in g.items()}
        nt = train_torch.clip_grad_norm(gt, 1.0)
        opt_t.apply(gt, pt)
        assert float(nm) == pytest.approx(float(nt), rel=1e-5)
    for k in w:
        np.testing.assert_allclose(np.array(pm[k]), pt[k].numpy(), atol=1e-6)
    # and the optimiser state is MLX's own layout, round-tripped
    flat = opt_t.state_flat()
    assert set(flat) == {k for k, _ in tree_flatten(opt_m.state)}
    again = train_torch.AdamW(1e-2, [0.9, 0.95], 0.1)
    again.load_flat(flat, torch.device("cpu"))
    assert again.step == 3 and torch.equal(again.v["a.weight"], opt_t.v["a.weight"])


@pytest.mark.parametrize(
    "card", ["previous_word", "words_back", "induction", "duplicate_word", "sink", "delimiter", "rare_word"]
)
def test_the_metre_rules_are_train_s(card):
    x = np.array([[4, 7, 4, 7, 1, 4, 9, 1], [2, 2, 2, 3, 3, 0, 1, 2]], dtype=np.int32)
    fl_np = {"delimiter": np.arange(10) % 3 == 0, "rare_word": np.linspace(0, 2, 10).astype(np.float32)}
    tm, hm = train.metre_target(mx.array(x), card, {k: mx.array(v) for k, v in fl_np.items()})
    tt, ht = train_torch.metre_target(torch.as_tensor(x).long(), card, {k: torch.as_tensor(v) for k, v in fl_np.items()})
    np.testing.assert_allclose(np.array(tm), tt.numpy(), atol=1e-6)
    np.testing.assert_array_equal(np.array(hm), ht.numpy())


@pytest.mark.parametrize("kind", ["induction", "duplicate", "conclusion"])
def test_the_copy_masks_are_train_s(kind):
    x = toks(2, 40, vocab=6, seed=4)
    y = toks(2, 40, vocab=6, seed=5)
    mk = np.array([2, 5], dtype=np.int32)
    a = train.copy_mask(mx.array(x), mx.array(y), kind, mx.array(mk))
    b = train_torch.copy_mask(torch.as_tensor(x).long(), torch.as_tensor(y).long(), kind, torch.as_tensor(mk).long())
    np.testing.assert_array_equal(np.array(a), b.numpy())


def test_the_scaffold_loss_is_train_s():
    m, t = twins("rope")
    x = toks()
    sc = {"heads": [{"layer": 0, "head": 1, "card": "previous_word"}, {"layer": 1, "head": 0, "card": "induction"}]}
    _, pm = m.forward_attending(mx.array(x), train.scaffold_picks(sc))
    _, pt = t.forward_attending(torch.as_tensor(x).long(), train.scaffold_picks(sc))
    a = train.scaffold_loss(pm, mx.array(x), sc, on=mx.array([1.0, 0.0]))
    b = train_torch.scaffold_loss(pt, torch.as_tensor(x).long(), sc, on=torch.tensor([1.0, 0.0]))
    assert float(a) == pytest.approx(float(b.detach()), rel=1e-4)


def test_the_heads_own_weights_are_train_s():
    """A head's own hold, fade, floor and release (train.scaffold_weights, shared) weigh its distance in the torch
    loss as in MLX's, with and without staged starts, and the distances themselves are MLX's (11 November: the torch
    loss took no weights, so every head followed the scaffold's schedule)."""
    m, t = twins("rope")
    x = toks()
    sc = {
        "weight": 1.0, "hold": 0.5, "fade": 0.9, "probes": [{"at": 0.3, "steps": 10, "to": 0.5}],
        "heads": [{"layer": 0, "head": 1, "card": "previous_word"},
                  {"layer": 1, "head": 0, "card": "induction", "hold": 0.0, "fade": 0.2, "floor": 0.3},
                  {"layer": 1, "head": 1, "card": "duplicate_word", "hold": 0.0, "fade": 0.1, "release": 0.2}],
    }  # fmt: skip
    train.check_scaffold(sc, 2, 2)
    xm, xt = mx.array(x), torch.as_tensor(x).long()
    _, pm = m.forward_attending(xm, train.scaffold_picks(sc))
    _, pt = t.forward_attending(xt, train.scaffold_picks(sc))
    dm, dt = train.scaffold_head_losses(pm, xm, sc), train_torch.scaffold_head_losses(pt, xt, sc)
    assert len(dm) == len(dt) == 3
    for a, b in zip(dm, dt, strict=True):
        assert float(a) == pytest.approx(float(b.detach()), rel=1e-4)
    seen = set()
    for step in (0, 50, 150, 300, 400, 950):  # full, fading, the probe's pulse, past the release, the content phase
        w = train.scaffold_weights(step, 1000, sc)
        seen.add(tuple(round(v, 6) for v in w))
        for on in (None, [1.0, 0.0, 1.0], [0.0, 0.0, 0.0]):
            a = train.scaffold_loss(pm, xm, sc, on=None if on is None else mx.array(on), weights=mx.array(w), per_head=dm)
            b = train_torch.scaffold_loss(
                pt, xt, sc, on=None if on is None else torch.tensor(on), weights=torch.tensor(w), per_head=dt
            )
            assert float(a) == pytest.approx(float(b.detach()), rel=1e-4, abs=1e-7), (step, on)
    assert len(seen) == 6 and (0.5, 0.15, 0.0) in seen, "the schedule the weights were read at is not a flat one"
    # the weights reach the gradient: a head at weight 0 is not pulled, a head at weight 1 is
    for p in t.parameters():
        p.grad = None
    _, pt = t.forward_attending(xt, train.scaffold_picks(sc))
    train_torch.scaffold_loss(pt, xt, sc, weights=torch.tensor([0.0, 1.0, 0.0])).backward()
    g0, g1 = t.layers[0].attn.qkv.weight.grad, t.layers[1].attn.qkv.weight.grad
    assert float(g0.abs().sum()) > 0  # layer 1's head reads layer 0's stream
    hd = 32
    assert float(g1[hd : 2 * hd].abs().sum()) == 0.0 and float(g1[:hd].abs().sum()) > 0  # head 1's queries; head 0's


def test_the_teachers_attention_is_the_target_as_in_train():
    """A head that names a teacher_layer and teacher_head is pulled toward the teacher's attention on the same tokens
    (train.py's scaffold_targets), the others toward their card's rule; no gradient reaches the teacher."""
    m, t = twins("rope")
    tm, tt = twins("rope", layers=3, heads=4, seed=11)  # a teacher of another shape, as the 50m is to Pan
    x = toks()
    xm, xt = mx.array(x), torch.as_tensor(x).long()
    sc = {"heads": [{"layer": 0, "head": 1, "card": "previous_word", "teacher_layer": 2, "teacher_head": 3},
                    {"layer": 1, "head": 0, "card": "induction"}]}  # fmt: skip
    assert train_torch.teacher_targets(None, xt, sc) is None
    assert train_torch.teacher_targets(tt, xt, {"heads": [sc["heads"][1]]}) is None
    tt.requires_grad_(False)
    targets_t = train_torch.teacher_targets(tt, xt, sc)
    assert set(targets_t) == {"previous_word"} and not targets_t["previous_word"][0].requires_grad
    # MLX's targets, built as train.py's loop builds them
    _, tp = tm.forward_attending(xm, {2: [3]})
    a = mx.stop_gradient(tp[(2, 3)].astype(mx.float32))
    targets_m = {"previous_word": (a, mx.ones(a.shape[:-1], dtype=mx.float32))}
    np.testing.assert_allclose(np.array(a), targets_t["previous_word"][0].numpy(), atol=1e-5)
    assert targets_t["previous_word"][1].shape == (3, 24) and bool((targets_t["previous_word"][1] == 1).all())
    _, pm = m.forward_attending(xm, train.scaffold_picks(sc))
    _, pt = t.forward_attending(xt, train.scaffold_picks(sc))
    dm = train.scaffold_head_losses(pm, xm, sc, targets_m)
    dt = train_torch.scaffold_head_losses(pt, xt, sc, targets_t)
    rule = train_torch.scaffold_head_losses(pt, xt, sc)
    for a_, b_ in zip(dm, dt, strict=True):
        assert float(a_) == pytest.approx(float(b_.detach()), rel=1e-4)
    assert float(dt[0].detach()) != pytest.approx(float(rule[0].detach()), rel=1e-2), "the teacher's target is not the rule's"
    assert float(dt[1].detach()) == pytest.approx(float(rule[1].detach()), rel=1e-6), "a head with no teacher keeps its rule"
    a_ = train.scaffold_loss(pm, xm, sc, targets=targets_m, weights=mx.array([1.0, 0.5]))
    b_ = train_torch.scaffold_loss(pt, xt, sc, targets=targets_t, weights=torch.tensor([1.0, 0.5]))
    assert float(a_) == pytest.approx(float(b_.detach()), rel=1e-4)


@pytest.mark.parametrize("positions", ["learned", "rope"])
@pytest.mark.parametrize("kv_heads", [2, 1])
def test_the_grouped_torch_gpt_is_the_mlx_gpt(positions, kv_heads, tmp_path):
    """Grouped-query attention (model.kv_heads): the same three projections under the same names, the same logits,
    streams and attention, and a checkpoint file written by either backend read by the other."""
    m, t = twins(positions, heads=4, kv_heads=kv_heads)
    names = {k for k, _ in t.named_parameters()}
    assert {"layers.0.attn.q_proj.weight", "layers.0.attn.k_proj.weight", "layers.0.attn.v_proj.weight"} <= names
    assert not any("qkv" in k for k in names)
    assert t.layers[0].attn.k_proj.weight.shape == (kv_heads * 16, 64)
    assert m.parameter_counts() == t.parameter_counts()
    x = toks()
    with torch.no_grad():
        np.testing.assert_allclose(np.array(m(mx.array(x))), t(x).numpy(), atol=2e-5, rtol=1e-4)
        for a, b in zip(m.hidden(mx.array(x)), t.hidden(x), strict=True):
            np.testing.assert_allclose(np.array(a), b.numpy(), atol=2e-5, rtol=1e-4)
    for a, b in zip(ops.attention_patterns(m, x), ops.attention_patterns(t, x), strict=True):
        assert a.shape == b.shape == (3, 4, 24, 24)
        np.testing.assert_allclose(a, b, atol=1e-5)
    picks = {0: [1, 3], 1: [0, 2]}
    _, pm = m.forward_attending(mx.array(x), picks)
    logits, pt = t.forward_attending(torch.as_tensor(x).long(), picks)
    for key, p in pt.items():
        np.testing.assert_allclose(np.array(pm[key]), p.detach().numpy(), atol=1e-5)
    torch.testing.assert_close(logits, t(x))
    # the checkpoint file, both ways: MLX's into a fresh torch model, torch's into a fresh MLX model
    spec = {"seed": 5, "optim": {"precision": "fp32"},
            "model": {"family": "gpt", "preset": "300k", "context": 32, "positions": positions,
                      "layers": 2, "width": 64, "heads": 4, "kv_heads": kv_heads}}  # fmt: skip
    (tmp_path / "from-mlx").mkdir()
    mx.save_safetensors(str(tmp_path / "from-mlx" / "model.safetensors"), dict(tree_flatten(m.parameters())))
    t2 = train_torch.load_model(spec, 97, tmp_path / "from-mlx")
    assert t2.layers[0].attn.kv_heads == kv_heads
    (tmp_path / "from-torch").mkdir()
    train_torch.save_flat(
        tmp_path / "from-torch" / "model.safetensors", {k: p.detach().numpy() for k, p in t2.named_parameters()}
    )
    m2 = train.build_model(spec, 97)
    before = np.array(m2(mx.array(x)))
    m2.update(train.load_master(tmp_path / "from-torch"))
    with torch.no_grad():
        np.testing.assert_allclose(np.array(m2(mx.array(x))), t2(x).numpy(), atol=2e-5, rtol=1e-4)
        np.testing.assert_allclose(np.array(m2(mx.array(x))), np.array(m(mx.array(x))), atol=2e-5, rtol=1e-4)
    assert np.abs(before - np.array(m2(mx.array(x)))).max() > 1e-3, "the file's weights, not the fresh model's"
    # a spec without kv_heads still builds the fused projection every other checkpoint was written with
    plain = train_torch.build_model({**spec, "model": {k: v for k, v in spec["model"].items() if k != "kv_heads"}}, 97)
    assert hasattr(plain.layers[0].attn, "qkv") and not hasattr(plain.layers[0].attn, "q_proj")


def losses(rec: Ledger, rid: str) -> dict[int, float]:
    rows = rec.query("select step, value from metrics where run_id=? and name='loss'", [rid])
    return {r["step"]: r["value"] for r in rows}


def torch_spec(spec):
    spec["model"]["backend"] = "torch"
    spec["optim"]["precision"] = "fp32"
    return spec


def test_backend_is_chosen_by_spec_or_environment(spec, monkeypatch):
    assert backend_of(spec) == "mlx"
    mlx_id = train.run_id(spec)
    monkeypatch.setenv("THORP_BACKEND", "torch")
    assert backend_of(spec) == "torch" and train.run_id(spec) == mlx_id  # the environment moves no id
    monkeypatch.delenv("THORP_BACKEND")
    assert backend_of(torch_spec(spec)) == "torch" and train.run_id(spec) != mlx_id
    spec["model"]["backend"] = "jax"
    with pytest.raises(ValueError):
        backend_of(spec)


def test_a_torch_voyage_trains_and_resumes(library, spec, tmp_thorp):
    torch_spec(spec)
    spec["data"]["passes"] = 3
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    quiet = lambda *a: None  # noqa: E731
    rid = train.run_id(spec)

    straight = Ledger(tmp_thorp / "straight.sqlite")
    assert train.train(spec, prep, straight, stop_after=100, log=quiet)["step"] == 100
    ck = train.latest_checkpoint(rid)
    # a torch checkpoint loads in the MLX model, and computes the same logits
    mm = train.build_model({**spec, "model": {**spec["model"], "backend": "mlx"}}, prep.tokeniser.vocab_size)
    mm.update(train.load_master(ck))
    tm = train_torch.load_model(spec, prep.tokeniser.vocab_size, ck)
    x = toks(2, 16, vocab=prep.tokeniser.vocab_size)
    with torch.no_grad():
        np.testing.assert_allclose(np.array(mm(mx.array(x))), tm(x).numpy(), atol=1e-4, rtol=1e-4)
    shutil.rmtree(paths.checkpoints_dir() / rid)

    resumed = Ledger(tmp_thorp / "resumed.sqlite")
    assert train.train(spec, prep, resumed, stop_after=50, log=quiet)["step"] == 50
    assert train.latest_checkpoint(rid).name == "step-50"
    assert train.train(spec, prep, resumed, stop_after=100, log=quiet)["step"] == 100

    a, b = losses(straight, rid), losses(resumed, rid)
    assert sorted(b) == list(range(1, 101)), "resume must not duplicate or drop metric rows"
    worst = max(abs(a[s] - b[s]) for s in range(51, 101))
    assert worst < 1e-3, worst
    assert np.mean([a[s] for s in range(91, 101)]) < np.mean([a[s] for s in range(1, 11)]) - 0.5, "it learns"
    names = {r["name"] for r in straight.query("select distinct name from metrics where run_id=?", [rid])}
    for k in ("grad_norm", "param_norm", "mem_gb", "grad_norm/layer_0/attn", "update_ratio/layer_1", "heading/tok"):
        assert k in names, k
    assert "torch" in straight.get_run(rid)["hardware"]


def test_a_torch_voyage_resumes_an_mlx_checkpoint(library, spec, tmp_thorp):
    """A voyage started on MLX continues on torch under THORP_BACKEND (same run id, same files)."""
    spec["optim"]["precision"] = "fp32"
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rid = train.run_id(spec)
    rec = Ledger(tmp_thorp / "l.sqlite")
    train.train(spec, prep, rec, stop_after=50, log=lambda *a: None)
    os.environ["THORP_BACKEND"] = "torch"
    try:
        out = train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)
    finally:
        del os.environ["THORP_BACKEND"]
    assert out["step"] == 60 and train.latest_checkpoint(rid).name == "step-50"
    ls = losses(rec, rid)
    assert sorted(ls) == list(range(1, 61)) and abs(ls[51] - ls[50]) < 0.2


@pytest.mark.parametrize("sampled", [False, True])
def test_a_torch_scaffolded_voyage_records_the_scaffold(library, spec, tmp_thorp, monkeypatch, sampled):
    """The metre scaffold with a staged start, every kind of rule, and both riddles (test_scaffold's full deck),
    read on the whole batch or on a sample of it, on torch."""
    from thorp import logic_tutor

    monkeypatch.setattr(logic_tutor, "invented_words", lambda n, seed=1, exclude=None: [f"{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}ol" for i in range(n)])
    torch_spec(spec)
    spec["optim"]["scaffold"] = {
        "weight": 1.0, "hold": 0.2, "fade": 0.5, "floor": 0.2, "release": 0.5,
        "heads": [{"layer": 0, "head": 0, "card": "previous_word"}, {"layer": 0, "head": 1, "card": "delimiter"},
                  {"layer": 1, "head": 0, "card": "induction", "from": 0.1}, {"layer": 1, "head": 1, "card": "rare_word"}],
        "riddles": {"comparator": {"layer": 1, "head": 1, "items": 4, "pool": 32},
                    "bridge": {"layer": 1, "items": 4, "pool": 32}},
    }  # fmt: skip
    if sampled:
        spec["optim"]["scaffold"]["sample"] = {"windows": 2, "length": 64}
    spec["model"]["positions"], spec["model"]["context"] = "rope", 256
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / "l.sqlite")
    rid = train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)["run_id"]
    got = {
        r["name"]: r["n"]
        for r in rec.query("select name, count(*) n from metrics where run_id=? group by name", [rid])
    }
    for k in ("scaffold/weight", "scaffold/loss", "scaffold/phase", "scaffold/started",
              "scaffold/riddle/bridge", "scaffold/riddle/comparator"):  # fmt: skip
        assert got.get(k) == 60, k
    sl = [r["value"] for r in rec.query("select value from metrics where run_id=? and name='scaffold/loss' order by step", [rid])]
    assert sl[-1] < sl[0], "the pull moves the heads toward their cards"
    started = [r["value"] for r in rec.query("select value from metrics where run_id=? and name='scaffold/started' order by step", [rid])]
    assert started[0] < started[-1]
    ph = [r["value"] for r in rec.query("select value from metrics where run_id=? and name='scaffold/phase' order by step", [rid])]
    w = [r["value"] for r in rec.query("select value from metrics where run_id=? and name='scaffold/weight' order by step", [rid])]
    assert ph[-1] == 3.0 and w[-1] == 0.0, "the release stage (the 21m's) on torch: the pull off, past the floor"


OGDEN = ["ce_bpb", "stars", "nevermore", "cards", "shapes", "pips", "logic", "discovery", "bpb_split", "probes", "successor"]


def test_the_evaluators_score_the_same_weights_alike(library, spec, tmp_thorp):
    """Every evaluator the Ogden voyages run, on an MLX model and a torch model with its weights."""
    spec["optim"]["precision"] = "fp32"
    spec["model"]["context"] = 256  # the decks' prompts fit (MLX reads a learned position past the end silently)
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    vocab = prep.tokeniser.vocab_size
    mm = train.build_model(spec, vocab)
    tm = train_torch.build_model(torch_spec(dict(spec, model=dict(spec["model"]))), vocab)
    train_torch.set_weights(tm, {k: torch.from_numpy(np.array(v)) for k, v in tree_flatten(mm.parameters())})

    def ctx(model, init):
        return evaluators.EvalContext(
            run_id="r", step=5, model=model, tokeniser=prep.tokeniser, context=spec["model"]["context"],
            sets=prep.eval_sets, languages={"loc-hole": "en"}, recipe=list(prep.recipe), init_model=init,
        )  # fmt: skip

    cm, ct = ctx(mm, lambda: mm), ctx(tm, lambda: tm)
    compared = 0
    for name in OGDEN:
        a, b = evaluators.get(name)(cm), evaluators.get(name)(ct)
        assert set(a.metrics) == set(b.metrics), name
        for k, v in a.metrics.items():
            if isinstance(v, float) and np.isfinite(v):
                assert b.metrics[k] == pytest.approx(v, rel=2e-3, abs=2e-3), (name, k)
                compared += 1
        for ra, rb in zip(a.evals, b.evals, strict=True):
            assert rb["bpb"] == pytest.approx(ra["bpb"], rel=1e-4)
    assert compared > 20
    # the samplers draw from their own generator, but write text of the right length
    s = evaluators.get("samples")(ct)
    assert {x["kind"] for x in s.artifacts} == {"samples", "top10"}


def test_the_torch_path_needs_no_mlx(tmp_path):
    """With MLX unimportable (a CUDA box), the loop, the model and the evaluators still import and run."""
    code = """
import sys
sys.modules['mlx'] = None
sys.modules['mlx.core'] = None
import numpy as np, torch
from thorp import train, train_torch, evaluators
from thorp.models import ops, registry
for name in ["ce_bpb", "stars", "nevermore", "cards", "shapes", "pips", "logic", "discovery", "successor",
             "probes", "curiosity", "samples", "laws", "soundings", "bpb_split"]:
    evaluators.get(name)
m = registry.build("gpt", "300k", 50, 16, "rope", backend="torch", layers=2, width=64, heads=2)
x = np.random.default_rng(0).integers(0, 50, (2, 12))
assert ops.token_ce(m, x[:, :-1], x[:, 1:]).shape == (2, 11)
assert len(ops.attention_patterns(m, x)) == 2
from thorp.evaluators import nevermore, samples, soundings
s, a, b = nevermore.measure(m, x, 5)
assert s.shape == (2, 2)
print("ok")
"""
    env = {**os.environ, "THORP_DATA": str(tmp_path / "d"), "THORP_LEDGER": str(tmp_path / "l.sqlite"), "THORP_DEVICE": "cpu"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=paths.BACKEND)
    assert r.returncode == 0 and r.stdout.strip().endswith("ok"), r.stderr[-2000:]


def test_rescore_reads_a_torch_run(library, spec, tmp_thorp, monkeypatch):
    import json

    monkeypatch.setenv("THORP_SHIP_LOG", "1")  # as aboard a hired box: the readers answer from its own SQLite log
    torch_spec(spec)
    quiet = lambda *a: None  # noqa: E731
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
    rec = Ledger()
    train.train(spec, prep, rec, stop_after=50, log=quiet)
    rid = train.run_id(spec)
    rec.run({"run_id": rid, "name": "test", "spec_json": json.dumps(spec), "status": "finished", "started": "x"})
    assert not rec.query("select bpb from evals where run_id=?", [rid])
    step = train.rescore(rid, evaluators=["ce_bpb"], resolver=library["resolver"], rec=rec, log=quiet)
    after = rec.query("select bpb from evals where run_id=? and step=?", [rid, step])
    assert step == 50 and after and after[0]["bpb"] > 0


# ---------------------------------------------------------------- refuse, never ignore (11 November)


def every_key(spec: dict) -> dict:
    """conftest's spec with every key the torch loop honours switched on."""
    full = copy.deepcopy(spec)
    full.update(
        sop="0.0.6", departures=[{"field": "content", "why": "a shelf of its own"}], ship="s", experiment="e",
        question="q", charter={"gpu": "RTX 4090", "anything": 1},
        seeded_from={"run": "a", "mode": "slow", "lr_scale": 0.1, "step": 50},
        transplant={"from_run": "b", "star": "induction", "pos": True, "tok": False, "below": True, "ln": True},
    )  # fmt: skip
    full["model"].update(kv_heads=1, positions="rope", backend="torch", cache_gb=4)
    full["tokeniser"]["symbols"] = ["<question>"]
    full["data"].update(stages=[{"name": "one", "recipe": "recipe.csv", "passes": 1}], first="recipe.csv",
                        first_repeats=2, opt_in="because", turns="marks")  # fmt: skip
    full["eval"].update(light={"every_steps": 10, "evaluators": ["nevermore"]}, options={"stars": {"windows": 4}})
    full["optim"].update(
        copy_weight={"alpha": 1.0, "kind": "induction"},
        teacher={"run": "t", "alpha": 0.0, "temperature": 2.0},
        scaffold={
            "weight": 1.0, "hold": 0.2, "fade": 0.5, "floor": 0.1, "release": 0.6,
            "sample": {"windows": 2, "length": 32}, "probes": [{"at": 0.3, "steps": 5, "to": 0.5}],
            "heads": [{"layer": 0, "head": 0, "card": "previous_word", "from": 0.1, "hold": 0.1, "fade": 0.3,
                       "floor": 0.0, "release": 0.4, "teacher_layer": 1, "teacher_head": 0}],
            "riddles": {"comparator": {"layer": 1, "head": 1, "weight": 1.0, "items": 4, "pool": 32, "seed": 1, "from": 0.2},
                        "bridge": {"layer": 1, "items": 4, "pool": 32, "kinds": "all"}},
        },
    )  # fmt: skip
    return full


def test_the_torch_loop_refuses_what_it_would_ignore(spec, monkeypatch):
    refuse = train_torch.refuse_unsupported
    refuse(spec)  # a plain spec
    full = every_key(spec)
    refuse(full)  # and every key the loop honours, the labels and the shared blocks among them
    # absent, null and switched-off values are never refused, even of a key the loop does not know
    off = copy.deepcopy(spec)
    off["model"].update(kv_heads=0, wobble=None)
    off["optim"].update(scaffold=None, teacher=None, lookahead=None)
    refuse(off)
    # a key the loop was never taught, wherever it sits: every one is named, and nothing it does honour is
    bad = copy.deepcopy(full)
    bad["model"]["wobble"] = 2
    bad["optim"]["lookahead"] = True
    bad["optim"]["teacher"]["heads_only"] = True
    bad["optim"]["scaffold"]["jitter"] = 0.1
    bad["optim"]["scaffold"]["heads"][0]["sway"] = 0.5
    bad["optim"]["scaffold"]["probes"][0]["shape"] = "cosine"
    bad["optim"]["scaffold"]["riddles"]["comparator"]["twist"] = 1
    bad["optim"]["scaffold"]["riddles"]["sphinx"] = {"layer": 0}
    bad["data"]["mixture"] = {"a": 0.5}
    bad["data"]["stages"][0]["blend"] = 0.5
    bad["seeded_from"]["blend"] = 0.5
    bad["transplant"]["graft"] = True
    bad["curriculum"] = {"rungs": 3}
    named = ["model.wobble", "optim.lookahead", "optim.teacher.heads_only", "optim.scaffold.jitter",
             "optim.scaffold.heads[].sway", "optim.scaffold.probes[].shape", "optim.scaffold.riddles.comparator.twist",
             "optim.scaffold.riddles.sphinx", "data.mixture", "data.stages[].blend", "seeded_from.blend",
             "transplant.graft", "curriculum"]  # fmt: skip
    with pytest.raises(train_torch.UnsupportedSpec) as e:
        refuse(bad)
    said = str(e.value)
    for k in named:
        assert f"{k} (" in said, k
    assert said.count("has not been taught") == len(named), said
    for k in ("model.kv_heads", "optim.scaffold.heads[].fade", "optim.scaffold.probes[].at", "sop", "charter", "ship"):
        assert f"{k} (" not in said, k
    # a key known to be beyond the loop: refused with its reason when switched on, never at its off value
    monkeypatch.setitem(train_torch.UNSUPPORTED, "model.kv_heads", ("no grouped attention here", (0,)))
    monkeypatch.setitem(train_torch.UNSUPPORTED, "optim.scaffold.probes", ("no probe phase here", ()))
    refuse(off)
    refuse({**spec, "optim": {**spec["optim"], "scaffold": {"heads": [{"layer": 0, "head": 0, "card": "sink"}], "probes": []}}})
    with pytest.raises(train_torch.UnsupportedSpec) as e:
        refuse(full)
    assert "model.kv_heads (no grouped attention here)" in str(e.value)
    assert "optim.scaffold.probes (no probe phase here)" in str(e.value) and "taught" not in str(e.value)
    # a family with no torch model
    with pytest.raises(train_torch.UnsupportedSpec, match="model.family"):
        refuse({**spec, "model": {**spec["model"], "family": "deltanet"}})


def test_the_refusal_comes_before_any_work(spec):
    """The loop reads the spec against what it honours first: with no preparation and no ledger to touch, a spec it
    would have passed over is refused, by name, through train.train as a hired box calls it."""
    torch_spec(spec)["optim"]["lookahead"] = True
    with pytest.raises(train_torch.UnsupportedSpec, match="optim.lookahead"):
        train_torch.train(spec, None)
    with pytest.raises(train_torch.UnsupportedSpec, match="optim.lookahead"):
        train.train(spec, None)
    assert train.latest_checkpoint(train.run_id(spec)) is None


def test_the_charter_asks_before_a_box_is_hired(spec, tmp_thorp):
    """`thorp charter` reads the spec against the torch loop at the quote: refused before the voyage is prepared (the
    resolver is never called), so before the market is read or a box hired."""
    import yaml

    from thorp.viable.s1_operations import charter

    def never(path):
        raise AssertionError("the voyage was prepared before the spec was read against the torch loop")

    torch_spec(spec)["model"]["wobble"] = 2
    f = tmp_thorp / "wobble.yaml"
    f.write_text(yaml.safe_dump(spec))
    with pytest.raises(train_torch.UnsupportedSpec, match="model.wobble"):
        charter.quote(str(f), resolver=never, log=lambda *a: None)


def test_no_key_is_left_unsupported():
    """Each key refused on 11 November was taken out of UNSUPPORTED as its gap was closed and tested; the tests above
    and below are those tests. A key put back here needs its reason beside it."""
    assert train_torch.UNSUPPORTED == {}
    for k in ("model.kv_heads", "optim.scaffold.probes", "optim.scaffold.probes[].to", "sop",
              *(f"optim.scaffold.heads[].{x}" for x in ("hold", "fade", "floor", "release", "from", "teacher_layer", "teacher_head"))):  # fmt: skip
        assert k in train_torch.HONOURED, k


def test_every_spec_on_disk_is_one_the_torch_loop_knows():
    """The alarm for the next drift: a key taught to train.py and written into a spec under ships/specs, and not
    taught to the torch loop, fails here on the Mac rather than on a hired box. (A key in UNSUPPORTED is a known
    refusal, with its reason, and does not fail this.)"""
    import yaml

    root = paths.ROOT / "ships" / "specs"
    if not root.exists():
        pytest.skip("no ships/specs here")
    untaught, n = {}, 0
    for f in sorted(root.rglob("*.yaml")):
        s = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(s, dict) or "model" not in s or "optim" not in s:
            continue
        n += 1
        try:
            train_torch.refuse_unsupported(s)
        except train_torch.UnsupportedSpec as e:
            if "has not been taught" in str(e):
                untaught[f.name] = str(e)
    assert n > 0 and not untaught, untaught


# ---------------------------------------------------------------- the same objective on both loops (11 November)


def series(rec: Ledger, rid: str, steps) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    lo, hi = min(steps), max(steps)
    for r in rec.query("select step, name, value from metrics where run_id=? and step>=? and step<=? order by rowid", [rid, lo, hi]):
        out.setdefault(r["name"], {})[r["step"]] = r["value"]
    return out


def twin_legs(spec, prep, tmp, monkeypatch, at=50, more=3):
    """One spec, one checkpoint (MLX's, at step `at`), and the next `more` steps sailed by each loop from it: the
    metrics of those steps, MLX's and torch's. Step at+1 is the same weights and the same batch on both, so every
    loss term must agree closely; the steps after it also carry the gradient of the whole objective and the
    optimiser's move, so a term weighed otherwise on one backend shows there even where it is not logged."""
    quiet = lambda *a: None  # noqa: E731
    rid = train.run_id(spec)
    mlx_log, torch_log = Ledger(tmp / "legs-mlx.sqlite"), Ledger(tmp / "legs-torch.sqlite")
    assert train.train(spec, prep, mlx_log, stop_after=at, log=quiet)["step"] == at
    assert train.train(spec, prep, mlx_log, stop_after=at + more, log=quiet)["step"] == at + more
    assert train.latest_checkpoint(rid).name == f"step-{at}"
    monkeypatch.setenv("THORP_BACKEND", "torch")
    assert train.train(spec, prep, torch_log, stop_after=at + more, log=quiet)["step"] == at + more
    monkeypatch.delenv("THORP_BACKEND")
    steps = range(at + 1, at + more + 1)
    total = int(mlx_log.query("select value from metrics where run_id=? and name='plan/total_steps'", [rid])[0]["value"])
    return series(mlx_log, rid, steps), series(torch_log, rid, steps), total


TIMING = ("step_ms", "tokens_per_s", "mem_gb")


def agree(a: dict, b: dict, at: int, more: int, first=1e-5, later=1e-4):
    """Every metric MLX recorded over the legs, torch recorded too, and they agree: closely at the first step, within
    `later` after the loops have each taken their own optimiser steps. (Measured on 11 November, fp32 on the CPU:
    under 1e-6 on every term at all three steps; a tack weighed otherwise on one backend moved the loss 4e-3.)"""
    assert {k for k in a if k not in TIMING} == {k for k in b if k not in TIMING}
    worst = {}
    for name in a:
        if name in TIMING or name.startswith(("grad_norm", "param_norm", "update_", "heading", "data/", "loss/book")):
            continue
        assert sorted(a[name]) == sorted(b[name]) == list(range(at + 1, at + more + 1)), name
        for step in a[name]:
            tol = first if step == at + 1 else later
            assert b[name][step] == pytest.approx(a[name][step], rel=tol, abs=tol), (name, step)
            worst[name] = max(worst.get(name, 0.0), abs(a[name][step] - b[name][step]))
    return worst


@pytest.mark.parametrize("kv_heads", [0, 2])
def test_both_loops_sail_the_same_scaffold(library, spec, tmp_thorp, monkeypatch, kv_heads):
    """A head's own hold, fade, floor and release, a staged start, a probe and a riddle (and, grouped, shared K/V
    heads): from one checkpoint both loops record the same weights, distances and losses, and move the same way."""
    from thorp import logic_tutor

    monkeypatch.setattr(logic_tutor, "invented_words", lambda n, seed=1, exclude=None: [f"{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}ol" for i in range(n)])
    spec["optim"]["precision"] = "fp32"
    spec["data"]["passes"] = 3
    spec["model"].update(positions="rope", context=256, heads=4)
    if kv_heads:
        spec["model"]["kv_heads"] = kv_heads
    spec["optim"]["scaffold"] = {
        "weight": 1.0, "hold": 0.9, "fade": 1.0,
        "probes": [{"at": 0.0, "steps": 52, "to": 0.5}],  # the pulse ends between the second and third step compared
        "heads": [{"layer": 0, "head": 0, "card": "previous_word"},
                  {"layer": 0, "head": 3, "card": "duplicate_word", "hold": 0.0, "fade": 0.02, "floor": 0.3},
                  {"layer": 1, "head": 2, "card": "induction", "hold": 0.0, "fade": 0.02, "release": 0.03},
                  {"layer": 1, "head": 1, "card": "sink", "from": 0.9}],
        "riddles": {"comparator": {"layer": 1, "head": 3, "items": 4, "pool": 32}},
    }  # fmt: skip
    sc = spec["optim"]["scaffold"]
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    a, b, total = twin_legs(spec, prep, tmp_thorp, monkeypatch)
    worst = agree(a, b, 50, 3)
    # what was compared is the schedule the test means: three heads at three weights and one not started, the
    # pulse on for two steps and off for the third, each head's distance read at every step
    for step in (51, 52, 53):
        want = train.scaffold_weights(step - 1, total, sc)
        got = [b[f"scaffold/weight/{h['card']}"][step] for h in sc["heads"]]
        assert got == pytest.approx(want)
    assert [b[f"scaffold/weight/{h['card']}"][51] for h in sc["heads"]] == pytest.approx([0.5, 0.15, 0.0, 0.5])
    assert [b[f"scaffold/weight/{h['card']}"][53] for h in sc["heads"]] == pytest.approx([1.0, 0.3, 0.0, 1.0])
    assert [b["scaffold/probe"][s] for s in (51, 52, 53)] == [1.0, 1.0, 0.0]
    assert b["scaffold/started"][51] == 4.0  # three heads and the comparator; the sink waits for its `from`
    dist = [b[f"scaffold/distance/{h['card']}/l{h['layer']}h{h['head']}"][51] for h in sc["heads"]]
    assert all(d > 0 for d in dist)
    # the pull recorded is the weighted one: the three started heads at their own weights, over the three started
    assert b["scaffold/loss"][51] == pytest.approx((0.5 * dist[0] + 0.15 * dist[1] + 0.0 * dist[2]) / 3, rel=1e-4)
    assert b["scaffold/loss"][51] != pytest.approx(0.5 * sum(dist[:3]) / 3, rel=0.05), "not one weight for every head"
    assert worst["loss"] < 1e-4 and worst["scaffold/riddle/comparator"] < 1e-4


def test_both_loops_learn_from_the_teachers_heads(library, spec, tmp_thorp, monkeypatch):
    """A teacher kept for its attention only (alpha 0, the Pan arms): one head pulled toward the teacher's head, one
    toward its rule, the copy-weighted tack still applied. Both loops, from one checkpoint, record the same pull."""
    monkeypatch.setenv("THORP_SHIP_LOG", "1")  # the teacher is looked up in this ledger, as aboard a hired box
    quiet = lambda *a: None  # noqa: E731
    spec["optim"]["precision"] = "fp32"
    spec["data"]["passes"] = 3
    spec["model"]["positions"] = "rope"
    teacher = copy.deepcopy(spec)
    teacher["name"] = "the-teacher"
    teacher["model"].update(layers=3, heads=4)
    prep = train.prepare(teacher, resolver=library["resolver"], log=quiet)
    home = Ledger()
    train.train(teacher, prep, home, stop_after=50, log=quiet)
    home.run({"run_id": train.run_id(teacher), "status": "finished"})
    spec["name"] = "the-student"
    spec["optim"]["teacher"] = {"run": "the-teacher", "alpha": 0.0, "temperature": 2.0}
    spec["optim"]["copy_weight"] = {"alpha": 4.0, "kind": "duplicate"}
    spec["optim"]["scaffold"] = {
        "weight": 1.0, "hold": 0.9, "fade": 1.0,
        "heads": [{"layer": 0, "head": 1, "card": "previous_word", "teacher_layer": 2, "teacher_head": 3},
                  {"layer": 1, "head": 0, "card": "induction", "hold": 0.0, "fade": 0.02, "floor": 0.5}],
    }  # fmt: skip
    a, b, _ = twin_legs(spec, prep, tmp_thorp, monkeypatch)
    worst = agree(a, b, 50, 3)
    assert worst["loss"] < 1e-4 and worst["scaffold/loss"] < 1e-4
    assert b["scaffold/weight/previous_word"][51] == 1.0 and b["scaffold/weight/induction"][51] == 0.5
    # the target was the teacher's head, not the previous-word rule: the same student, weights and batch, scored
    # against the rule, gives another pull
    rid = train.run_id(spec)
    ck = train.latest_checkpoint(rid)
    student = train_torch.load_model({**spec, "model": {**spec["model"], "backend": "torch"}}, prep.tokeniser.vocab_size, ck)
    batch = next(iter(_stream(spec, prep).iter_from(50)))
    x = torch.as_tensor(np.asarray(batch.tokens), dtype=torch.long)[:, :-1]
    sc = spec["optim"]["scaffold"]
    with torch.no_grad():
        _, pats = student.forward_attending(x, train.scaffold_picks(sc))
        rule = train_torch.scaffold_loss(pats, x, sc, weights=torch.tensor([1.0, 0.5]))
        t_model = train_torch.load_model(teacher, prep.tokeniser.vocab_size, train.latest_checkpoint(train.run_id(teacher)))
        taught = train_torch.scaffold_loss(
            pats, x, sc, targets=train_torch.teacher_targets(t_model, x, sc), weights=torch.tensor([1.0, 0.5])
        )
    assert float(taught) == pytest.approx(b["scaffold/loss"][51], rel=1e-4)
    assert float(taught) == pytest.approx(a["scaffold/loss"][51], rel=1e-4)
    assert abs(float(rule) - b["scaffold/loss"][51]) > 0.02, "a hundred times the tolerance the two loops agree to"


def _stream(spec, prep):
    from thorp import data

    books = prep.books()
    return data.stream(
        prep.recipe, prep.tokeniser.id, spec["seed"], spec["optim"]["batch_tokens"], spec["model"]["context"],
        spec["data"]["passes"], {b: books[b].family for b in books}, first=prep.first,
        first_repeats=spec["data"].get("first_repeats", 1),
    )  # fmt: skip


# ---------------------------------------------------------------- the SOP version on the run row (11 November)


def test_a_torch_voyage_writes_its_sop_version(library, spec, tmp_thorp):
    """As train.py does: the run row carries the SOP version the spec names, in the box's own SQLite log (whose
    `runs` table was not made with the column), where the charter's bring_home reads the whole row from."""
    quiet = lambda *a: None  # noqa: E731
    torch_spec(spec)
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet, known=True)  # the loop's test, not the gate's
    box = Ledger(tmp_thorp / "box.sqlite")
    assert "sop_version" not in {r[1] for r in box.con.execute("pragma table_info(runs)")}
    plain = train.train(spec, prep, box, stop_after=2, log=quiet)["run_id"]
    assert "sop_version" not in box.get_run(plain), "a voyage that names no version leaves the file as it was made"
    spec["sop"] = "0.0.6"
    rid = train.train(spec, prep, box, stop_after=2, log=quiet)["run_id"]
    assert rid != plain and box.get_run(rid)["sop_version"] == "0.0.6" and box.get_run(plain)["sop_version"] is None
    assert train.train(spec, prep, box, stop_after=3, log=quiet)["step"] == 3  # and again, the column there already
    assert box.get_run(rid)["sop_version"] == "0.0.6" and box.get_run(rid)["status"] == "running"
    # the view of the table still reads, and a second connection to the same file sees the column
    assert box.query("select voyage_id, sop_version from voyages where run_id=?", [rid])[0]["sop_version"] == "0.0.6"
    again = Ledger(tmp_thorp / "box.sqlite")
    again.run({"run_id": rid, "status": "finished"})  # a later write that carries no version keeps the one written
    assert again.get_run(rid)["sop_version"] == "0.0.6" and again.get_run(rid)["status"] == "finished"
