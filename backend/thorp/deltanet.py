"""The instrument for linear-attention layers (11 November, Justin: "we need a new instrument for the 48
before we do the audit").

Qwen3.8 27B is 64 layers, of which 48 are Gated DeltaNet and 16 are full attention. A DeltaNet layer has
no attention map: each value head keeps a state matrix S, decays it, erases along the new key, writes the
new value, and reads it out with the query (mlx_lm.models.gated_delta):

    S_t = g_t * S_{t-1} (I - beta_t k_t k_t^T) + beta_t v_t k_t^T          y_t = S_t q_t

`thorp.inside` reads attention by swapping the shared attention function, so it sees none of this: the cards
and the head census read 16 of the 64 layers. This module reads the other 48, three ways.

1. **Effective attention.** Unrolling the recurrence, the readout is an exact weighted sum of the values
   written so far:

       y_t = sum_{j <= t} w[t, j] v_j        w[t, j] = beta_j k_j^T M_{j+1} ... M_t q_t
       M_i = g_i (I - beta_i k_i k_i^T)

   `effective_attention` returns w. It is what an attention map is for an attention head (how much of the
   value written at j reaches the output at t), with two differences to keep in mind when a card reads it:
   the weights are **signed** and a row does **not sum to one**. `shares` gives |w| normalised by row, which
   is the form the cards expect. `reconstruct` rebuilds y from w and v; the test of this module is that it
   matches what the layer itself computed.

2. **Removal and patching, by real layer index.** `edited({layer: {...}})` zeroes value heads, replaces them
   with a mean, or patches in another run's outputs at chosen positions. The edit is applied inside the
   layer, on each head's own output just before it is projected into the residual stream, by a wrapper on
   that layer's own module. There is no call counter, so the edit holds through cached, token-by-token
   generation, which the attention knockout in `thorp.inside` does not.

3. **A map of the model.** `layer_map` gives every layer's real index and kind, so a census can cover all
   of them and draw its random controls from the kind it is testing.

Value heads are grouped under key heads: the 27B has 16 key heads and 48 value heads a layer, three value
heads to a key head (`value_heads_of`). The 0.8B of the same family has one to one, and is the small model
this instrument is tested on (`python -m thorp.deltanet MODEL`).
"""

from __future__ import annotations

import contextlib
import sys

import numpy as np

from thorp import inside as _inside


def layer_map(model) -> list[dict]:
    """Every block of the model in order: its real index, its kind ("linear" or "attention") and its head
    counts. A model with no linear-attention layers is all "attention"."""
    inner, blocks, _, _ = _inside._find(model)
    out = []
    for i, b in enumerate(getattr(inner, blocks)):
        if getattr(b, "is_linear", False) and hasattr(b, "linear_attn"):
            d = b.linear_attn
            out.append({"layer": i, "kind": "linear", "key_heads": int(d.num_k_heads),
                        "value_heads": int(d.num_v_heads)})
        else:
            a = getattr(b, "self_attn", None) or getattr(b, "attention", None) or getattr(b, "attn", None)
            heads = next((int(getattr(a, n)) for n in ("num_attention_heads", "n_heads", "num_heads")
                          if a is not None and hasattr(a, n)), None)
            out.append({"layer": i, "kind": "attention", "heads": heads})
    return out


def value_heads_of(key_head: int, key_heads: int, value_heads: int) -> list[int]:
    """The value heads that read and write through one key head (mlx-lm repeats each key head in place)."""
    r = value_heads // key_heads
    return list(range(key_head * r, (key_head + 1) * r))


def effective_attention(q, k, g, beta, positions=None) -> np.ndarray:
    """w[h, p, j]: how much of the value written at j reaches value head h's readout at positions[p].

    q, k: (T, Hk, Dk), already normalised as the layer normalises them; g, beta: (T, Hv). Key heads are
    repeated to the value heads. `positions` defaults to every position. Float64 on the CPU, so a long
    trace read at a few positions costs one backward sweep and holds no T x T x heads array."""
    q, k = np.asarray(q, np.float64), np.asarray(k, np.float64)
    g, beta = np.asarray(g, np.float64), np.asarray(beta, np.float64)
    T, Hk, _ = q.shape
    Hv = g.shape[-1]
    if Hv != Hk:
        q, k = np.repeat(q, Hv // Hk, axis=1), np.repeat(k, Hv // Hk, axis=1)
    pos = np.arange(T) if positions is None else np.asarray(list(positions), int)
    w = np.zeros((Hv, len(pos), T))
    r = q[pos]  # (P, Hv, Dk): each position's query, carried back through the erasures and decays
    for i in range(int(pos.max()), -1, -1):
        on = pos >= i
        if not on.any():
            continue
        dot = np.einsum("phd,hd->ph", r[on], k[i])  # k_i^T r
        w[:, on, i] = (beta[i][None, :] * dot).T
        r[on] = g[i][None, :, None] * (r[on] - (beta[i][None, :] * dot)[..., None] * k[i][None])
    return w


def shares(w: np.ndarray) -> np.ndarray:
    """|w| normalised by row: the share of a readout that each earlier position supplies. The form a card
    reads (rows sum to one, nothing negative); the sign and the size are in `w`."""
    a = np.abs(w)
    return a / np.maximum(a.sum(axis=-1, keepdims=True), 1e-30)


def reconstruct(w: np.ndarray, v) -> np.ndarray:
    """y[p, h, :] rebuilt from the effective attention and the values (T, Hv, Dv)."""
    return np.einsum("hpj,jhd->phd", w, np.asarray(v, np.float64))


class _Probe:
    """A layer's linear attention, as its block sees it, that says which layer is running."""

    def __init__(self, inner, layer: int, owner: DeltaNet):
        self._inner, self._layer, self._owner = inner, layer, owner

    def __getattr__(self, key):
        return getattr(self._inner, key)

    def __call__(self, *a, **kw):
        prev, self._owner._current = self._owner._current, self._layer
        try:
            return self._inner(*a, **kw)
        finally:
            self._owner._current = prev


class _Norm:
    """The layer's gated norm, whose output is each value head's own contribution (batch, time, Hv, Dv)
    just before the projection into the residual stream: where a head is recorded, removed or patched."""

    def __init__(self, inner, layer: int, owner: DeltaNet):
        self._inner, self._layer, self._owner = inner, layer, owner

    def __getattr__(self, key):
        return getattr(self._inner, key)

    def __call__(self, *a, **kw):
        out = self._inner(*a, **kw)
        return self._owner._edit(self._layer, out)


class DeltaNet:
    """The linear-attention layers of an MLX-LM model, by real layer index."""

    def __init__(self, model):
        self.model = model
        self._inner, self._blocks, _, _ = _inside._find(model)
        self.map = layer_map(model)
        self.linear = [m["layer"] for m in self.map if m["kind"] == "linear"]
        self._current: int | None = None
        self._capture: dict | None = None
        self._outputs: dict | None = None
        self._edits: dict[int, dict] = {}
        self._seen: dict[int, int] = {}  # tokens each edited layer has written since the edit began

    @property
    def readable(self) -> bool:
        return bool(self.linear)

    # ------------------------------------------------------------------ the wrappers
    @contextlib.contextmanager
    def _installed(self, capture: bool = False):
        import mlx.core as mx

        blocks = getattr(self._inner, self._blocks)
        saved, mods = [], set()
        for i in self.linear:
            d = blocks[i].linear_attn
            saved.append((blocks[i], d, d.norm))
            d.norm = _Norm(d.norm, i, self)
            blocks[i].linear_attn = _Probe(d, i, self)
            mods.add(sys.modules[type(d).__module__])
        patched = []
        if capture:
            for mod in mods:
                orig = mod.gated_delta_update

                def recording(q, k, v, a, b, A_log, dt_bias, state=None, mask=None, _o=orig, **kw):
                    from mlx_lm.models import gated_delta as gd

                    y, st = _o(q, k, v, a, b, A_log, dt_bias, state, mask, **kw)
                    if self._capture is not None and self._current is not None:
                        lb = kw.get("lower_bound")
                        g = gd.compute_g(A_log, a, dt_bias) if lb is None else gd.compute_lower_bound_g(
                            A_log, a, dt_bias, lb)
                        beta = mx.sigmoid(b) * (2.0 if kw.get("allow_neg_eigval") else 1.0)
                        f = lambda x: np.array(x[0].astype(mx.float32))  # noqa: E731 - batch 0
                        self._capture[self._current] = {
                            "q": f(q), "k": f(k), "v": f(v), "g": f(g), "beta": f(beta), "y": f(y)}
                    return y, st

                mod.gated_delta_update = recording
                patched.append((mod, orig))
        try:
            yield
        finally:
            for mod, orig in patched:
                mod.gated_delta_update = orig
            for block, d, norm in saved:
                d.norm = norm
                block.linear_attn = d

    def _edit(self, layer: int, out):
        import mlx.core as mx

        if self._outputs is not None:
            self._outputs[layer] = np.array(out[0].astype(mx.float32))
        e = self._edits.get(layer)
        if not e:
            return out
        S = out.shape[1]
        start = self._seen.get(layer, 0)  # this call writes positions start .. start + S - 1
        self._seen[layer] = start + S
        Hv = out.shape[2]
        heads = [h for h in e.get("zero", ()) if 0 <= h < Hv]
        if heads:
            keep = mx.array([0.0 if h in heads else 1.0 for h in range(Hv)])[None, None, :, None]
            out = out * keep.astype(out.dtype)
        for h, vec in (e.get("mean") or {}).items():
            m = np.zeros((1, 1, Hv, 1), np.float32)
            m[0, 0, h, 0] = 1.0
            m = mx.array(m).astype(out.dtype)
            out = out * (1 - m) + m * mx.array(np.asarray(vec, np.float32))[None, None, None, :].astype(out.dtype)
        p = e.get("patch")
        if p:
            # another run's outputs at chosen absolute positions and heads: {"from": (T, Hv, Dv), "positions": [...],
            # "heads": [...] or None for all}
            src = np.asarray(p["from"], np.float32)
            hs = list(range(Hv)) if p.get("heads") is None else list(p["heads"])
            sel = np.zeros((1, S, Hv, 1), np.float32)
            rep = np.zeros((1, S, Hv, out.shape[3]), np.float32)
            for t in p["positions"]:
                if start <= t < start + S and t < len(src):
                    sel[0, t - start, hs, 0] = 1.0
                    rep[0, t - start, hs, :] = src[t, hs, :]
            sel = mx.array(sel).astype(out.dtype)
            out = out * (1 - sel) + sel * mx.array(rep).astype(out.dtype)
        return out

    # ------------------------------------------------------------------ reading
    def read(self, tokens, layers=None) -> dict[int, dict]:
        """One cache-less pass over the tokens (a prompt, or a prompt with its finished trace): for each
        linear layer, its q, k, v, g, beta and y as the layer computed them, and `out`, each value head's
        contribution after the gated norm. Arrays are (T, heads, dim) for the first row of the batch."""
        import mlx.core as mx

        self._capture, self._outputs = {}, {}
        try:
            with self._installed(capture=True):
                mx.eval(self.model(tokens))
        finally:
            cap, outs, self._capture, self._outputs = self._capture, self._outputs, None, None
        want = set(self.linear if layers is None else layers)
        return {i: {**cap[i], "out": outs[i]} for i in cap if i in want}

    def attention(self, tokens, positions=None, layers=None, on_layer=None) -> dict[int, np.ndarray]:
        """The effective attention of every linear layer, (value heads, positions, T) each. With
        `on_layer(layer, w)` the maps are handed over one at a time and nothing is kept."""
        out = {}
        for i, rec in self.read(tokens, layers).items():
            w = effective_attention(rec["q"], rec["k"], rec["g"], rec["beta"], positions)
            if on_layer is not None:
                on_layer(i, w)
            else:
                out[i] = w
        return out

    def means(self, tokens_list, layers=None) -> dict[int, np.ndarray]:
        """Each value head's mean contribution over some texts, (Hv, Dv) a layer: what mean-removal puts
        in a head's place, so the removal takes away what the head says about this input and not its bias."""
        tot: dict[int, np.ndarray] = {}
        n: dict[int, int] = {}
        for tokens in tokens_list:
            for i, rec in self.read(tokens, layers).items():
                tot[i] = tot.get(i, 0) + rec["out"].sum(axis=0)
                n[i] = n.get(i, 0) + rec["out"].shape[0]
        return {i: tot[i] / n[i] for i in tot}

    # ------------------------------------------------------------------ editing
    @contextlib.contextmanager
    def edited(self, edits: dict[int, dict]):
        """A context in which the named layers' value heads are changed on every pass, cached or not.

        `edits` is {real layer index: {"zero": [value heads], "mean": {value head: vector},
        "patch": {"from": outputs, "positions": [...], "heads": [...]}}}. A layer that is not linear
        attention is refused: silently doing nothing is how a control comes out too narrow."""
        bad = [i for i in edits if i not in self.linear]
        if bad:
            raise ValueError(f"not linear-attention layers: {sorted(bad)} (linear: {self.linear})")
        self._edits, self._seen = dict(edits), {}
        try:
            with self._installed():
                yield self
        finally:
            self._edits, self._seen = {}, {}

    def removed(self, heads: dict[int, list[int]], means: dict[int, np.ndarray] | None = None):
        """`edited`, for the common case: these value heads zeroed, or set to their means when given."""
        if means is None:
            return self.edited({i: {"zero": list(h)} for i, h in heads.items()})
        return self.edited({i: {"mean": {x: means[i][x] for x in h}} for i, h in heads.items()})


def check(model_id: str, text: str = "The cat sat on the mat. The dog sat on the") -> dict:
    """The instrument's own test on a real model: the effective attention rebuilds what each layer computed,
    an empty edit changes nothing, a real one does, and it holds through cached generation."""
    import mlx.core as mx
    from mlx_lm import load
    from mlx_lm.models.cache import make_prompt_cache

    model, tok = load(model_id)
    d = DeltaNet(model)
    ids = tok.encode(text)
    x = mx.array([ids])
    out = {"model": model_id, "layers": len(d.map), "linear": len(d.linear), "tokens": len(ids)}
    if not d.readable:
        return {**out, "ok": False, "why": "no linear-attention layers"}
    rec = d.read(x)
    worst, row_sums = 0.0, []
    for r in rec.values():
        w = effective_attention(r["q"], r["k"], r["g"], r["beta"])
        y = reconstruct(w, r["v"])
        scale = float(np.abs(r["y"]).max()) or 1.0
        worst = max(worst, float(np.abs(y - r["y"]).max()) / scale)
        row_sums.append(float(w.sum(axis=-1).mean()))
    out["reconstruction_error"] = worst  # relative to the largest value the layer wrote
    out["mean_row_sum"] = float(np.mean(row_sums))  # not 1: these are not softmax weights
    base = np.array(model(x)[0, -1].astype(mx.float32))

    def stepwise():  # token by token through the cache: the last step's logits
        cache, step = make_prompt_cache(model), None
        for t in ids:
            step = model(mx.array([[t]]), cache=cache)
        return np.array(step[0, -1].astype(mx.float32))

    # a bf16 model's cached and full passes differ a little with no edit at all: the yardstick
    out["cache_noise"] = float(np.abs(stepwise() - base).max())
    with d.edited({}):
        same = np.array(model(x)[0, -1].astype(mx.float32))
    first = d.linear[0]
    heads = list(range(d.map[first]["value_heads"]))
    with d.removed({first: heads}):
        gone = np.array(model(x)[0, -1].astype(mx.float32))
        cached = stepwise()  # the same edit through the cache must match the full pass
    out["empty_edit_changes"] = float(np.abs(same - base).max())
    out["removal_changes"] = float(np.abs(gone - base).max())
    out["cached_matches_full"] = float(np.abs(cached - gone).max())
    try:
        with d.edited({d.map[[m["kind"] for m in d.map].index("attention")]["layer"]: {"zero": [0]}}):
            out["refuses_attention_layer"] = False
    except ValueError:
        out["refuses_attention_layer"] = True
    out["ok"] = bool(
        worst < 1e-2 and out["empty_edit_changes"] == 0.0 and out["removal_changes"] > 1e-3
        and out["cached_matches_full"] < max(2 * out["cache_noise"], 0.1 * out["removal_changes"])
        and out["refuses_attention_layer"]
    )
    return out


if __name__ == "__main__":
    import json

    print(json.dumps(check(sys.argv[1] if len(sys.argv) > 1 else "mlx-community/Qwen3.5-0.8B-bf16"), indent=1))
