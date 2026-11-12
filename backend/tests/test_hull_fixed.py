"""What every hull is built with and no spec can change (registry.HULL, 12 November): the master charter signs
these words, so a small ship is built in each kernel and the words are checked against its weights."""

from __future__ import annotations

import pytest

from thorp import launch
from thorp.models import registry

W, V = 16, 50  # a vocabulary no other weight has on a side (4 x 16 is 64)


def _cfg():
    return registry.GPTConfig(layers=2, width=W, heads=2, vocab=V, context=32, positions="rope")


def _check(shapes: dict[str, tuple[int, ...]]) -> None:
    hull = registry.HULL
    # the feed-forward layer: one matrix up to 4x the width and one down, nothing gating it
    assert "4x" in hull["feed_forward"] and "GELU" in hull["feed_forward"]
    assert shapes["layers.0.mlp.up.weight"] == (4 * W, W) and shapes["layers.0.mlp.down.weight"] == (W, 4 * W)
    assert not any(".mlp.gate" in k for k in shapes)
    # normalisation: a LayerNorm before each sublayer and one at the end, each a weight alone
    assert "LayerNorm" in hull["norm"]
    assert shapes["layers.0.ln1.weight"] == (W,) and shapes["layers.0.ln2.weight"] == (W,) and shapes["ln_f.weight"] == (W,)
    # tied: the one table is the only matrix with the vocabulary on a side
    assert hull["embeddings"].startswith("tied")
    assert [k for k, s in shapes.items() if V in s] == ["tok.weight"]
    assert hull["biases"] == "none" and not any(k.endswith(".bias") for k in shapes)


def test_the_mlx_hull_is_what_the_charter_says():
    mx = pytest.importorskip("mlx.core")
    from mlx.utils import tree_flatten

    model = registry.FAMILIES["gpt"](_cfg())
    _check({k: tuple(v.shape) for k, v in tree_flatten(model.parameters())})
    assert mx.array(1).item() == 1


def test_the_torch_hull_is_what_the_charter_says():
    pytest.importorskip("torch")
    model = registry.TORCH_FAMILIES["gpt"](_cfg())
    _check({k: tuple(v.shape) for k, v in model.state_dict().items() if "rope" not in k.lower()})


def test_the_charter_has_a_row_for_each_and_reads_it_for_any_fitout():
    rows = {"ship.ffn": "feed_forward", "ship.norm": "norm", "ship.embeddings": "embeddings", "ship.biases": "biases"}
    v = launch.charter_values({"300k": {"base": {"model": {"layers": 6}}, "leg": None}})
    for row, part in rows.items():
        assert v[row]["300k"] == registry.HULL[part] and v[row]["50m"] is None  # a class with no fitout reads nothing
