"""The hooked model (thorp/hooked.py) and Inside rebuilt on it (thorp/inside.py), on tiny mlx-lm models built
from their configs with random weights: a Qwen3-style pure-attention model, a Llama, and a Qwen3.5 hybrid
(linear, attention, linear, attention). Nothing is downloaded. On the CPU, where a cached pass and a full
pass agree to ~1e-6 in float32 (on the GPU they differ by ~1e-3 with no edit at all)."""

from __future__ import annotations

import sys

import numpy as np
import pytest

mx = pytest.importorskip("mlx.core")
pytest.importorskip("mlx_lm")

from thorp import hooked  # noqa: E402
from thorp.inside import Inside  # noqa: E402


@pytest.fixture(autouse=True)
def _store_clean():
    """These tests never touch the store: the conftest's truncate (which waits on any other session's open
    transaction) is not needed here."""


@pytest.fixture(autouse=True)
def _on_the_cpu():
    """The CPU's kernels: on the GPU the fused attention and its cached form differ from each other by
    ~1e-3 in float32 with no edit at all, which would hide what these tests compare."""
    was = mx.default_device()
    mx.set_default_device(mx.cpu)
    try:
        yield
    finally:
        mx.set_default_device(was)


def _f32(m):
    from mlx.utils import tree_map

    m.update(tree_map(lambda p: p.astype(mx.float32), m.parameters()))
    mx.eval(m.parameters())
    return m


def _qwen3(seed=0):
    from mlx_lm.models import qwen3

    mx.random.seed(seed)
    return _f32(qwen3.Model(qwen3.ModelArgs(
        model_type="qwen3", hidden_size=32, num_hidden_layers=3, intermediate_size=64, num_attention_heads=4,
        rms_norm_eps=1e-6, vocab_size=64, num_key_value_heads=2, max_position_embeddings=256, head_dim=8,
        tie_word_embeddings=False, rope_theta=10000.0)))


def _llama(seed=1):
    from mlx_lm.models import llama

    mx.random.seed(seed)
    return _f32(llama.Model(llama.ModelArgs(
        model_type="llama", hidden_size=32, num_hidden_layers=2, intermediate_size=64, num_attention_heads=4,
        num_key_value_heads=4, rms_norm_eps=1e-5, vocab_size=64)))


def _hybrid(seed=2):
    from mlx_lm.models import qwen3_5

    mx.random.seed(seed)
    tc = dict(model_type="qwen3_5_text", hidden_size=32, intermediate_size=64, num_hidden_layers=4,
              num_attention_heads=4, num_key_value_heads=2, head_dim=8, linear_num_value_heads=4,
              linear_num_key_heads=2, linear_key_head_dim=8, linear_value_head_dim=8, linear_conv_kernel_dim=4,
              vocab_size=64, full_attention_interval=2, tie_word_embeddings=True, rms_norm_eps=1e-6,
              max_position_embeddings=256)
    return _f32(qwen3_5.Model(qwen3_5.ModelArgs.from_dict({"model_type": "qwen3_5", "text_config": tc})))


IDS = [3, 17, 5, 41, 9, 3, 17, 22, 8, 30, 12]
X = mx.array([IDS])


def _last(model, x=X):
    return np.array(model(x)[0, -1].astype(mx.float32))


def _stepwise(model, ids=IDS):
    from mlx_lm.models.cache import make_prompt_cache

    cache, step = make_prompt_cache(model), None
    for t in ids:
        step = model(mx.array([[t]]), cache=cache)
    return np.array(step[0, -1].astype(mx.float32))


# ---------------------------------------------------------------- the map and the patterns
def test_the_hybrid_is_mapped_by_real_layer():
    h = hooked.HookedModel(_hybrid())
    assert h.n_layers == 4
    assert h.attention_layers == [1, 3] and h.linear_layers == [0, 2]
    assert [m["kind"] for m in h.layer_map] == ["linear", "attention", "linear", "attention"]
    assert h.heads_of(1) == 4 and h.heads_of(0) == 4


def test_patterns_come_back_by_real_layer():
    m = _hybrid()
    h = hooked.HookedModel(m)
    p = h.attention_patterns(X)
    assert sorted(p) == [1, 3]
    for w in p.values():
        w = np.array(w)
        assert w.shape == (1, 4, len(IDS), len(IDS))
        assert np.allclose(w.sum(-1), 1.0, atol=1e-5)
        assert np.allclose(np.triu(w[0], 1), 0.0)  # causal
    assert sorted(h.attention_patterns(X, layers=[3])) == [3]
    seen = []
    assert h.attention_patterns(X, on_layer=lambda i, w: seen.append(i)) == {}
    assert seen == [1, 3]
    with pytest.raises(ValueError):
        h.attention_patterns(X, layers=[0])  # a linear layer has no softmax map
    # Inside's list form: one entry per attention layer, named by pattern_layers
    inner = Inside(m)
    lst = inner.attention_patterns(X)
    assert len(lst) == 2 and inner.pattern_layers == [1, 3]
    assert np.array_equal(np.array(lst[1]), np.array(p[3]))
    got = []
    inner.attention_patterns(X, on_layer=lambda i, w: got.append(i))
    assert got == [1, 3]


def test_the_explicit_attention_is_the_models_own():
    # reading the weights must not change what the model computes
    m = _hybrid()
    base = _last(m)
    h = hooked.HookedModel(m)
    with h.silenced({}):
        same = _last(m)
    assert np.array_equal(base, same)  # nothing edited, the fused kernel: the very same numbers
    inner = Inside(m)
    with inner.silenced({}):
        explicit = _last(m)  # Inside's explicit float32 attention
    assert np.abs(explicit - base).max() < 1e-4


# ---------------------------------------------------------------- silencing by real layer
@pytest.mark.parametrize("cls", [hooked.HookedModel, Inside])
def test_silencing_hits_the_named_layer_and_no_other(cls):
    m = _hybrid()
    h = cls(m)
    with h.silenced({}):  # the baseline in the same arithmetic (Inside's is the explicit attention)
        base = h.hidden(X)
    with h.silenced({3: [0]}):
        late = h.hidden(X)
    with h.silenced({1: [0]}):
        early = h.hidden(X)
    f = lambda a: np.array(a.astype(mx.float32))  # noqa: E731
    # layer 3's head 0 changes nothing before layer 3 (the old counter would have called it layer 1)
    for i in range(3):
        assert np.abs(f(late[i]) - f(base[i])).max() < 1e-5
    assert np.abs(f(late[3]) - f(base[3])).max() > 1e-4
    assert np.abs(f(early[0]) - f(base[0])).max() < 1e-5
    assert np.abs(f(early[1]) - f(base[1])).max() > 1e-4
    with pytest.raises(ValueError):
        h.silenced({0: [0]})  # a linear layer
    with pytest.raises(ValueError):
        with h.silenced({1: [4]}):  # no such head
            pass


@pytest.mark.parametrize("cls", [hooked.HookedModel, Inside])
def test_silencing_a_head_zeroes_its_slice_of_the_output_projection(cls):
    m = _qwen3()
    h = cls(m)
    attn = m.model.layers[1].self_attn
    seen = {}
    real = attn.o_proj

    class Spy:
        def __call__(self, x):
            seen["x"] = np.array(x.astype(mx.float32))
            return real(x)

    with h.silenced({1: [2]}):
        attn.o_proj._inner = Spy()  # the wrapper's inner: see what reaches the projection
        try:
            h(X)
        finally:
            attn.o_proj._inner = real
    x = seen["x"]  # (1, T, heads * head_dim)
    assert np.all(x[..., 16:24] == 0.0) and np.abs(x[..., :16]).max() > 0 and np.abs(x[..., 24:]).max() > 0


def test_the_same_head_index_in_another_layer_is_another_head():
    m = _qwen3()
    h = hooked.HookedModel(m)
    base = _last(m)
    with h.silenced({0: [1]}):
        a = _last(m)
    with h.silenced({2: [1]}):
        b = _last(m)
    assert np.abs(a - base).max() > 1e-4 and np.abs(b - base).max() > 1e-4
    assert np.abs(a - b).max() > 1e-4


# ---------------------------------------------------------------- through the cache and mlx_lm's generators
@pytest.mark.parametrize("make", [_qwen3, _llama, _hybrid])
@pytest.mark.parametrize("cls", [hooked.HookedModel, Inside])
def test_silencing_holds_through_cached_generation(make, cls):
    m = make()
    h = cls(m)
    base = _last(m)
    heads = {h.attention_layers[0]: [0, 3], h.attention_layers[-1]: [1]}
    with h.silenced(heads):
        full = _last(m)
        cached = _stepwise(m)
        again = _last(m)  # a second pass after many: no counter left to drift
    assert np.abs(full - base).max() > 1e-3
    assert np.abs(cached - full).max() < 1e-4
    assert np.array_equal(again, full)


def test_both_kinds_edited_at_once_hold_through_the_cache():
    m = _hybrid()
    h = hooked.HookedModel(m)
    base = _last(m)
    with h.edited({0: {"zero": [0, 1, 2, 3]}, 3: {"zero": [2]}}):
        full = _last(m)
        cached = _stepwise(m)
    assert np.abs(full - base).max() > 1e-3
    assert np.abs(cached - full).max() < 1e-4
    with h.edited({0: {"zero": [0, 1, 2, 3]}}):
        lin_only = _last(m)
    assert np.abs(lin_only - full).max() > 1e-5  # the attention edit counted too


def test_edited_refuses_the_wrong_kind():
    h = hooked.HookedModel(_hybrid())
    for bad in ({1: {"kind": "linear", "zero": [0]}}, {0: {"kind": "attention", "zero": [0]}},
                {7: {"zero": [0]}}, {1: {"patch": {}}}):
        with pytest.raises(ValueError):
            with h.edited(bad):
                pass
    h2 = hooked.HookedModel(_qwen3())
    with pytest.raises(ValueError):
        with h2.deltanet.edited({0: {"zero": [0]}}):  # no linear layers on a pure-attention model
            pass


def _greedy_by_full_passes(model, ids, n):
    ids = list(ids)
    out = []
    for _ in range(n):
        t = int(np.argmax(np.array(model(mx.array([ids]))[0, -1].astype(mx.float32))))
        out.append(t)
        ids.append(t)
    return out


@pytest.mark.parametrize("make", [_qwen3, _hybrid])
@pytest.mark.parametrize("cls", [hooked.HookedModel, Inside])
def test_silencing_holds_through_mlx_lm_generation(make, cls):
    from mlx_lm.generate import batch_generate, generate_step

    m = make()
    h = cls(m)
    heads = {h.attention_layers[0]: [0, 1, 2], h.attention_layers[-1]: [0, 3]}
    prompts = [IDS, IDS[2:] + [7, 7]]
    n = 8
    with h.silenced(heads):
        want = [_greedy_by_full_passes(m, p, n) for p in prompts]
        # mlx_lm.generate's own engine, token by token through the cache
        got_step = [int(t) for t, _ in generate_step(mx.array(prompts[0]), m, max_tokens=n,
                                                     sampler=lambda x: mx.argmax(x, axis=-1))]

        class Tok:  # batch_generate wants stop tokens and a decoder; these prompts are token ids already
            eos_token_ids: list = []

            def decode(self, ids):
                return " ".join(map(str, ids))

        got_batch = batch_generate(m, Tok(), prompts, max_tokens=n, return_token_ids=True,
                                   sampler=lambda x: mx.argmax(x, axis=-1)).token_ids
    unsilenced = [_greedy_by_full_passes(m, p, n) for p in prompts]
    assert got_step == want[0]
    assert [list(map(int, g)) for g in got_batch] == want
    assert want != unsilenced or make is _qwen3  # the edit mattered (a tiny model may ignore it on one prompt)


# ---------------------------------------------------------------- mean-ablation
def test_mean_ablation_puts_the_heads_mean_in_its_place():
    m = _qwen3()
    h = hooked.HookedModel(m)
    one = mx.array([[5]])
    means = h.means([one], layers=[1])
    assert means[1].shape == (4, 8)
    base = _last(m, one)
    with h.silenced({1: [0, 2]}, means=means):
        same = _last(m, one)  # on the text it was taken from, a one-token mean is the head itself
    assert np.abs(same - base).max() < 1e-5
    means2 = h.means([X, mx.array([IDS[::-1]])])
    assert sorted(means2) == [0, 1, 2]
    with h.silenced({1: [0]}, means=means2):
        mean_out = _last(m)
    with h.silenced({1: [0]}):
        zero_out = _last(m)
    base = _last(m)
    assert np.abs(mean_out - base).max() > 1e-5 and np.abs(mean_out - zero_out).max() > 1e-5
    hy = hooked.HookedModel(_hybrid())
    mh = hy.means([X], layers=[0, 1])
    assert mh[0].shape == (4, 8) and mh[1].shape == (4, 8)  # value heads; attention heads


# ---------------------------------------------------------------- random controls
def test_random_controls_draw_only_from_the_kind_asked_for():
    h = hooked.HookedModel(_hybrid())
    rng = np.random.default_rng(1859)
    att = h.random_heads(6, rng=rng)
    assert len(set(att)) == 6 and all(la in (1, 3) and 0 <= x < 4 for la, x in att)
    lin = h.random_heads(5, kind="linear", rng=rng)
    assert all(la in (0, 2) and 0 <= x < 4 for la, x in lin)
    rest = h.random_heads(6, rng=rng, exclude=[(1, 0), (1, 1)])
    assert not {(1, 0), (1, 1)} & set(rest)
    assert len(h.head_pool()) == 8 and len(h.head_pool("linear")) == 8
    with pytest.raises(ValueError):
        h.random_heads(9)


def test_on_a_pure_model_the_draws_are_the_old_draws():
    # the old knockout pool, layer by layer and head by head, and its seeded draw
    inner = Inside(_qwen3())
    taken = {(0, 1), (2, 3)}
    old_pool = [(la, x) for la in range(3) for x in range(4) if (la, x) not in taken]
    assert inner.head_pool(exclude=taken) == old_pool
    a = np.random.default_rng(1859)
    b = np.random.default_rng(1859)
    for _ in range(3):
        old = [old_pool[j] for j in a.choice(len(old_pool), 4, replace=False)]
        assert inner.random_heads(4, rng=b, exclude=taken) == old


# ---------------------------------------------------------------- Inside, as it was, on a pure model
_OLD = {"record": None, "silence": None, "call": [0]}


def _old_sdpa(queries, keys, values, cache=None, scale=1.0, mask=None, sinks=None):
    # thorp/inside.py's explicit attention as it stood before 11 November, with its call counter
    B, Hq, T, D = queries.shape
    Hk = keys.shape[1]
    if Hk != Hq:
        keys = mx.repeat(keys, Hq // Hk, axis=1)
        values = mx.repeat(values, Hq // Hk, axis=1)
    s = (queries.astype(mx.float32) @ keys.astype(mx.float32).transpose(0, 1, 3, 2)) * scale
    S = keys.shape[2]
    if isinstance(mask, str) or mask is None:
        if T > 1:
            s = s + mx.triu(mx.full((T, S), -mx.inf), k=S - T + 1)
    elif mask.dtype == mx.bool_:
        s = mx.where(mask, s, -mx.inf)
    else:
        s = s + mask.astype(mx.float32)
    w = mx.softmax(s, axis=-1)
    if _OLD["record"] is not None:
        _OLD["record"].append(w)
    out = w @ values.astype(mx.float32)
    if _OLD["silence"] is not None:
        layer = _OLD["call"][0]
        _OLD["call"][0] += 1
        heads = _OLD["silence"].get(layer)
        if heads:
            keep = mx.array([0.0 if x in heads else 1.0 for x in range(out.shape[1])])[None, :, None, None]
            out = out * keep
    return out.astype(queries.dtype)


def _old_patched(fn):
    mods = [mod for name, mod in sys.modules.items()
            if name.startswith("mlx_lm.models") and hasattr(mod, "scaled_dot_product_attention")]
    saved = {mod: mod.scaled_dot_product_attention for mod in mods}
    for mod in mods:
        mod.scaled_dot_product_attention = _old_sdpa
    try:
        return fn()
    finally:
        for mod, f in saved.items():
            mod.scaled_dot_product_attention = f


@pytest.mark.parametrize("make", [_qwen3, _llama])
def test_inside_is_unchanged_for_one_pass_on_a_pure_model(make):
    m = make()
    inner = Inside(m)
    # the patterns
    _OLD["record"] = []
    try:
        old_p = _old_patched(lambda: (mx.eval(m(X)), list(_OLD["record"]))[1])
    finally:
        _OLD["record"] = None
    new_p = inner.attention_patterns(X)
    assert len(new_p) == len(old_p) == len(m.model.layers)
    assert all(np.array_equal(np.array(a), np.array(b)) for a, b in zip(old_p, new_p, strict=True))
    # one silenced pass, bit for bit, and the unsilenced explicit baseline
    for heads in ({}, {0: [1]}, {1: [0, 3], 0: [2]}):
        _OLD["silence"], _OLD["call"][0] = heads, 0
        try:
            old = _old_patched(lambda: _last(m))
        finally:
            _OLD["silence"] = None
        with inner.silenced(heads):
            new = np.array(inner(X)[0, -1].astype(mx.float32))
        assert np.array_equal(old, new), heads
    # the residual stream and the lens
    hs = inner.hidden(X)
    assert len(hs) == len(m.model.layers)
    lens = inner.tok.as_linear(inner.ln_f(hs[-1]))
    assert np.allclose(np.array(lens[0, -1]), _last(m), atol=1e-5)


def test_inside_silencing_no_longer_drifts_after_the_first_pass():
    # the old counter, reset only by Inside.__call__, ran on into layers that do not exist on a second raw
    # pass, so the second pass was silenced nowhere
    m = _qwen3()
    inner = Inside(m)
    with inner.silenced({1: [0]}):
        a = _last(m)
        b = _last(m)
        inner.hidden(X)
        c = _last(m)
    with inner.silenced({}):
        base = _last(m)
    assert np.array_equal(a, b) and np.array_equal(a, c) and np.abs(a - base).max() > 1e-4


def test_the_lens_reads_an_untied_head_on_a_multimodal_wrapper():
    from mlx_lm.models import qwen3_5

    mx.random.seed(3)
    tc = dict(model_type="qwen3_5_text", hidden_size=32, intermediate_size=64, num_hidden_layers=2,
              num_attention_heads=4, num_key_value_heads=2, head_dim=8, linear_num_value_heads=4,
              linear_num_key_heads=2, linear_key_head_dim=8, linear_value_head_dim=8, vocab_size=64,
              full_attention_interval=2, tie_word_embeddings=False, rms_norm_eps=1e-6)
    m = _f32(qwen3_5.Model(qwen3_5.ModelArgs.from_dict({"model_type": "qwen3_5", "text_config": tc})))
    inner = Inside(m)
    lens = inner.tok.as_linear(inner.ln_f(inner.hidden(X)[-1]))
    assert np.allclose(np.array(lens[0, -1]), _last(m), atol=1e-5)


# ---------------------------------------------------------------- the callers, on the tiny models
class _Tok:
    """Token ids as their own pieces: what the traces need of a tokenizer."""

    def encode(self, s):
        return [int(x) % 64 for x in s.split()]

    def decode(self, ids):
        return " ".join(str(i) for i in ids)


def test_the_maths_trace_ranks_only_real_attention_heads():
    from thorp import math_heads as M

    for make, layers in ((_qwen3, [0, 1, 2]), (_hybrid, [1, 3])):
        inner = Inside(make())
        seqs = [IDS + [4, 9, 4, 9, 2], IDS[:6] + [4, 9, 4]]
        out = M.trace_batch(inner, _Tok(), seqs, [len(IDS), 6])
        for rec in out:
            assert rec["concentration"].shape == (inner.n_layers, 4)
            assert {d["layer"] for d in rec["top"]} <= set(layers)
            for li in inner.linear_layers:  # a linear layer has no softmax map and nothing is made up for it
                assert not rec["concentration"][li].any()
            assert all(rec["concentration"][li].any() for li in layers)


def test_the_census_features_are_rows_of_attention_layers():
    from thorp import head_census as C

    prompt = " ".join(str(i) for i in IDS + IDS)
    pure = C._feature_block(Inside(_qwen3()), _Tok(), prompt)
    assert pure["sink"].shape == (3, 4)  # as before: one row a layer
    inner = Inside(_hybrid())
    hy = C._feature_block(inner, _Tok(), prompt)
    assert hy["sink"].shape == (2, 4) and inner.pattern_layers == [1, 3]
    assert hy["sink"].any(axis=1).all()


def test_the_face_audits_targets_are_named_by_real_layer():
    from thorp import face_audit as F

    m = np.zeros((2, 4))
    m[1, 2] = 5.0  # row 1 is layer 3 on the hybrid
    m[0, 0] = 4.0
    assert F._top(m, 2) == [(1, 2), (0, 0)]
    assert F._top(m, 2, [1, 3]) == [(3, 2), (1, 0)]
    t = F._targets({"mover": m}, [], {}, ("mover",), 1, [1, 3])
    assert t == {"mover": [(3, 2)]}
