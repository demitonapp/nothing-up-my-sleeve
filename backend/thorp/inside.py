"""The inside view of an outside model (2026-11-07, Justin: "validate the cards first"): attention
patterns and the residual stream, layer by layer, for any MLX-LM model, so the cards (thorp/evaluators/
cards.py) read Qwen, Llama, Phi, Gemma, SmolLM3 and Pythia exactly as they read Nothing up my sleeve.

`Inside(model)` offers what Nothing up my sleeve's own GPT offers:
- `attention_patterns(tokens)`: per layer, every head's attention weights (batch, heads, T, T). MLX-LM
  computes attention in one fused kernel that does not return its weights, so while a pattern is read
  the shared `scaled_dot_product_attention` (in mlx_lm.models.base, and wherever a model module imported
  it) is swapped for an explicit softmax(q k^T * scale + mask) v that records the weights; grouped
  key-value heads are repeated to the query heads. A model whose attention does not call the shared
  function (Gemma 2, with its soft-capping) records nothing: `attention_readable` is False and the
  attention cards are not read for it.
- `hidden(tokens)`: the residual stream after each block, recorded by wrapping each block.
- `ln_f(h)` and `tok.as_linear(x)`: the final norm and the unembedding, for the logit lens.
"""

from __future__ import annotations

import sys

import mlx.core as mx

_record: list | None = None
# the knockout (2026-11-07): {layer: [heads]} silenced while set; the layer is counted call by call
_silence: dict[int, list[int]] | None = None
_call = [0]


def _explicit_sdpa(queries, keys, values, cache=None, scale=1.0, mask=None, sinks=None):
    B, Hq, T, D = queries.shape
    Hk = keys.shape[1]
    if Hk != Hq:
        keys = mx.repeat(keys, Hq // Hk, axis=1)
        values = mx.repeat(values, Hq // Hk, axis=1)
    # in float32 from the start: a float16 model (Pythia) overflows q k^T before any later cast
    s = (queries.astype(mx.float32) @ keys.astype(mx.float32).transpose(0, 1, 3, 2)) * scale
    S = keys.shape[2]
    if isinstance(mask, str) or mask is None:
        if T > 1:
            causal = mx.triu(mx.full((T, S), -mx.inf), k=S - T + 1)
            s = s + causal
    elif mask.dtype == mx.bool_:
        s = mx.where(mask, s, -mx.inf)
    else:
        s = s + mask.astype(mx.float32)
    w = mx.softmax(s, axis=-1)
    if _record is not None:
        _record.append(w)
    out = w @ values.astype(mx.float32)  # (batch, heads, time, head_dim)
    if _silence is not None:
        layer = _call[0]
        _call[0] += 1
        heads = _silence.get(layer)
        if heads:
            keep = mx.array([0.0 if h in heads else 1.0 for h in range(out.shape[1])])[
                None, :, None, None
            ]
            out = out * keep
    return out.astype(queries.dtype)


class _Tap:
    """A block, as its parent sees it, that also records what it writes (a plain wrapper, not a Module,
    so the block's own attributes, such as use_sliding, read straight through)."""

    def __init__(self, inner, sink: list):
        self._inner = inner
        self._sink = sink

    def __getattr__(self, key):
        return getattr(self._inner, key)

    def __call__(self, *a, **k):
        out = self._inner(*a, **k)
        self._sink.append(out[0] if isinstance(out, tuple) else out)
        return out


def _find(model, _depth: int = 0):
    """(the module holding the blocks, the blocks' attribute name, the final norm, the unembedding)."""
    for inner_name in ("model", "gpt_neox", "transformer"):
        inner = getattr(model, inner_name, None)
        if inner is None:
            continue
        for blocks in ("layers", "h"):
            if isinstance(getattr(inner, blocks, None), list):
                norm = next(
                    (
                        getattr(inner, n)
                        for n in ("norm", "final_layer_norm", "final_layernorm", "ln_f")
                        if hasattr(inner, n)
                    ),
                    None,
                )
                head = next(
                    (
                        getattr(owner, n)
                        for owner in (model, inner)
                        for n in ("lm_head", "embed_out")
                        if hasattr(owner, n)
                    ),
                    None,
                )
                if head is None:
                    emb = next(
                        getattr(inner, n)
                        for n in ("embed_tokens", "embed_in", "wte")
                        if hasattr(inner, n)
                    )
                    head = emb.as_linear
                return inner, blocks, norm, head
    lm = getattr(model, "language_model", None)  # a multimodal wrapper (Gemma 3): its text model
    if lm is not None and _depth == 0:
        return _find(lm, 1)
    raise ValueError("cannot find the blocks of this model")


class Inside:
    def __init__(self, model):
        self.model = model
        self._inner, self._blocks, self._norm, self._head = _find(model)
        self.attention_readable = True

        class _Tok:
            def __init__(s, head):
                s.as_linear = head if callable(head) else head.__call__

        # final-logit soft-capping (Gemma 2) applied to the lens as the model applies it
        args = getattr(model, "args", None)
        cap = getattr(args, "final_logit_softcapping", None) if args is not None else None
        head = self._head
        if cap:

            def head(x, _h=self._head, _c=cap):  # noqa: E306
                return mx.tanh(_h(x) / _c) * _c

        self.tok = _Tok(head)

    @property
    def layers(self):
        return getattr(self._inner, self._blocks)

    def ln_f(self, h):
        return self._norm(h) if self._norm is not None else h

    def hidden(self, tokens) -> list:
        sink: list = []
        blocks = getattr(self._inner, self._blocks)
        taps = [_Tap(b, sink) for b in blocks]
        setattr(self._inner, self._blocks, taps)
        try:
            out = self.model(tokens)
            mx.eval(out)
        finally:
            setattr(self._inner, self._blocks, blocks)
        return sink

    def silenced(self, heads: dict[int, list[int]]):
        """A context in which the given heads (layer -> heads) write nothing: every forward pass runs
        the explicit attention with their outputs zeroed (the knockout)."""
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            global _silence
            mods = [
                m
                for name, m in sys.modules.items()
                if name.startswith("mlx_lm.models") and hasattr(m, "scaled_dot_product_attention")
            ]
            saved = {m: m.scaled_dot_product_attention for m in mods}
            _silence = heads

            def counted(*a, **k):
                return _explicit_sdpa(*a, **k)

            try:
                for m in mods:
                    m.scaled_dot_product_attention = counted
                yield self
            finally:
                for m, f in saved.items():
                    m.scaled_dot_product_attention = f
                _silence = None

        return ctx()

    def __call__(self, tokens):  # noqa: F811
        _call[0] = 0  # each forward pass counts its layers from the first
        return self.model(tokens)

    def attention_patterns(self, tokens, on_layer=None) -> list:
        """Every layer's attention weights, or, with `on_layer(layer, weights)` given, each layer handed to
        the caller as it is computed and nothing kept. The streaming form matters for a long sequence: 36
        layers of (1, 32, T, T) float32 is 18 GB at T = 1,100, so a trace that is summarised layer by layer
        never holds more than one. The weights arrive layer by layer in the forward pass's order."""
        global _record
        mods = [
            m
            for name, m in sys.modules.items()
            if name.startswith("mlx_lm.models") and hasattr(m, "scaled_dot_product_attention")
        ]
        saved = {m: m.scaled_dot_product_attention for m in mods}
        _record = []
        n = [0]

        def counted(*a, **k):
            out = _explicit_sdpa(*a, **k)  # appends the weights to _record
            if on_layer is not None and _record:
                on_layer(n[0], _record[-1])  # read the weights now, hold nothing
                n[0] += 1
                _record.clear()
            return out

        try:
            for m in mods:
                m.scaled_dot_product_attention = counted
            out = self.model(tokens)
            mx.eval(out)
            got = list(_record)
        finally:
            for m, f in saved.items():
                m.scaled_dot_product_attention = f
            _record = None
        if on_layer is None and not got:
            self.attention_readable = False
        if on_layer is not None:
            return []
        return got
