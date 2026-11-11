"""The linear-attention instrument (thorp/deltanet.py): its effective attention is exact, by mlx-lm's own
reference recurrence, on made-up layers. The check on a real model is `python -m thorp.deltanet MODEL`."""

import numpy as np
import pytest

from thorp import deltanet

mx = pytest.importorskip("mlx.core")
gd = pytest.importorskip("mlx_lm.models.gated_delta")


def _layer(T=23, Hk=4, Hv=4, Dk=8, Dv=6, seed=0):
    rng = np.random.default_rng(seed)
    q = rng.normal(size=(T, Hk, Dk))
    k = rng.normal(size=(T, Hk, Dk))
    k /= np.linalg.norm(k, axis=-1, keepdims=True)  # as the layer normalises its keys
    v = rng.normal(size=(T, Hv, Dv))
    g = rng.uniform(0.5, 1.0, size=(T, Hv))
    beta = rng.uniform(0.0, 1.0, size=(T, Hv))
    f = lambda x: mx.array(x[None].astype(np.float32))  # noqa: E731
    y, _ = gd.gated_delta_ops(f(q), f(k), f(v), f(g), f(beta))
    return q, k, v, g, beta, np.array(y[0])


def test_effective_attention_rebuilds_the_layers_own_output():
    q, k, v, g, beta, y = _layer()
    w = deltanet.effective_attention(q, k, g, beta)
    assert w.shape == (4, 23, 23)
    assert np.allclose(deltanet.reconstruct(w, v), y, atol=1e-4)


def test_it_is_causal_and_not_a_softmax():
    q, k, v, g, beta, _ = _layer()
    w = deltanet.effective_attention(q, k, g, beta)
    assert np.allclose(np.triu(w, 1), 0.0)  # nothing from the future
    assert (w < 0).any()  # signed
    assert not np.allclose(w.sum(axis=-1), 1.0)  # rows do not sum to one
    s = deltanet.shares(w)
    assert (s >= 0).all() and np.allclose(s.sum(axis=-1), 1.0)


def test_value_heads_share_a_key_head():
    # the 27B's shape in small: three value heads to a key head
    q, k, v, g, beta, y = _layer(Hk=2, Hv=6)
    w = deltanet.effective_attention(q, k, g, beta)
    assert w.shape[0] == 6
    assert np.allclose(deltanet.reconstruct(w, v), y, atol=1e-4)
    assert deltanet.value_heads_of(1, 2, 6) == [3, 4, 5]
    assert deltanet.value_heads_of(15, 16, 48) == [45, 46, 47]


def test_chosen_positions_match_the_full_map():
    q, k, v, g, beta, _ = _layer()
    full = deltanet.effective_attention(q, k, g, beta)
    some = deltanet.effective_attention(q, k, g, beta, positions=[22, 5, 11])
    assert np.allclose(some, full[:, [22, 5, 11], :])
