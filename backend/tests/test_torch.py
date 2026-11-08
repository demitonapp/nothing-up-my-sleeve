"""The PyTorch backend (thorp/models/gpt_torch.py, thorp/train_torch.py, thorp/models/ops.py), on the CPU.

The torch GPT given the MLX GPT's weights computes the same logits, residual streams and attention; the
optimiser, the clip and every loss rule are MLX's; a tiny torch voyage trains, resumes within tolerance of
an uninterrupted one and records the scaffold's metrics; its checkpoints load in MLX; the evaluators score
the same weights alike on either backend; and nothing on the torch path needs MLX.
"""

from __future__ import annotations

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
    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.delenv("THORP_BACKEND", raising=False)
    torch.manual_seed(0)
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


def twins(positions="learned", layers=2, width=64, heads=2, vocab=97, context=32):
    """An MLX GPT and a torch GPT holding the same fp32 weights."""
    cfg = registry.GPTConfig(layers=layers, width=width, heads=heads, vocab=vocab, context=context, positions=positions)
    from thorp.models.gpt_mlx import GPT as MGPT
    from thorp.models.gpt_torch import GPT as TGPT

    mx.random.seed(3)
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
        "weight": 1.0, "hold": 0.2, "fade": 0.5, "floor": 0.2,
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
m = registry.build("gpt", "tiny", 50, 16, "rope", backend="torch")
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


def test_rescore_reads_a_torch_run(library, spec, tmp_thorp):
    import json

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
