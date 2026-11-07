"""Grow a trained smaller model into a bigger one that starts out predicting exactly what the smaller
one did (2026-11-07; DECISIONS.md, "Seeding"). For the keel into the pilot (300k into 1m) and,
when widths are whole multiples, any class into a bigger one with the same head size, vocabulary
and context.

- Width (D to r x D): every number in the residual stream is duplicated r times, [x, x], so every
  LayerNorm sees the same mean and variance. Weights that read the stream are tiled and divided by
  r (W' [x, x] = W x); weights that write to it are tiled along their output, so they write [y, y].
  The final LayerNorm's weight is divided by r, so the tied output (the embedding, tiled) gives the
  same logits.
- Heads (same head size): the smaller model's heads become the first heads of each layer; the new
  heads keep their fresh initial weights, but their columns of the output projection start at zero,
  so they add nothing until they learn to.
- Feed-forward units likewise: the old units first, the new ones with zero output columns.
- Layers: the smaller model's layers become the bottom layers; the new layers on top start as
  pass-throughs (their attention output projection and feed-forward output at zero).

`grow` returns the new weights and an inherit mask (1 where a weight came from the smaller model,
0 where it is new), which training uses to freeze or slow the inherited part.
"""

from __future__ import annotations

import numpy as np


def _tile_in(w: np.ndarray, r: int) -> np.ndarray:
    return np.tile(w, (1, r)) / r  # (out, in) -> (out, r*in), reads [x]*r as x


def _tile_out(w: np.ndarray, r: int) -> np.ndarray:
    return np.tile(w, (r, 1)) if w.ndim == 2 else np.tile(w, r)  # writes y as [y]*r


def grow(src: dict, src_cfg, dst: dict, dst_cfg) -> tuple[dict, dict]:
    """src, dst: flat {name: np.ndarray} weights (dst is the bigger model's fresh initialisation).
    cfgs: GPTConfig-like with layers, width, heads, vocab, context."""
    D1, D2 = src_cfg.width, dst_cfg.width
    if D2 % D1:
        raise ValueError(f"width {D2} is not a whole multiple of {D1}")
    hd1, hd2 = D1 // src_cfg.heads, D2 // dst_cfg.heads
    if hd1 != hd2 or src_cfg.vocab != dst_cfg.vocab or src_cfg.context != dst_cfg.context:
        raise ValueError("seeding needs the same head size, vocabulary and context")
    if dst_cfg.layers < src_cfg.layers:
        raise ValueError("the bigger model needs at least as many layers")
    r = D2 // D1
    out = {k: v.copy() for k, v in dst.items()}
    mask = {k: np.zeros_like(v) for k, v in dst.items()}

    def put(name: str, value: np.ndarray, region: tuple):
        out[name][region] = value
        mask[name][region] = 1.0

    put("tok.weight", _tile_out(src["tok.weight"].T, r).T, (slice(None), slice(None)))
    if "pos.weight" in src:  # rotary positions have no table to carry
        put("pos.weight", _tile_out(src["pos.weight"].T, r).T, (slice(None), slice(None)))
    put("ln_f.weight", _tile_out(src["ln_f.weight"], r) / r, (slice(None),))
    H = 4 * D1  # feed-forward units in the smaller model
    for i in range(dst_cfg.layers):
        p = f"layers.{i}."
        if i >= src_cfg.layers:  # a new layer on top: a pass-through to begin with
            out[p + "attn.proj.weight"][:] = 0.0
            out[p + "mlp.down.weight"][:] = 0.0
            continue
        for ln in ("ln1", "ln2"):
            put(p + f"{ln}.weight", _tile_out(src[p + f"{ln}.weight"], r), (slice(None),))
        qkv = src[p + "attn.qkv.weight"]  # (3*D1, D1): q, k, v blocks
        for b in range(3):
            block = _tile_in(qkv[b * D1 : (b + 1) * D1], r)  # (D1, D2): the old heads
            put(p + "attn.qkv.weight", block, (slice(b * D2, b * D2 + D1), slice(None)))
        proj = src[p + "attn.proj.weight"]  # (D1, D1): heads -> stream
        out[p + "attn.proj.weight"][:, D1:] = 0.0  # the new heads write nothing at first
        put(p + "attn.proj.weight", _tile_out(proj, r), (slice(None), slice(0, D1)))
        up = src[p + "mlp.up.weight"]  # (4*D1, D1)
        put(p + "mlp.up.weight", _tile_in(up, r), (slice(0, H), slice(None)))
        down = src[p + "mlp.down.weight"]  # (D1, 4*D1)
        out[p + "mlp.down.weight"][:, H:] = 0.0  # the new units write nothing at first
        put(p + "mlp.down.weight", _tile_out(down, r), (slice(None), slice(0, H)))
    return out, mask
