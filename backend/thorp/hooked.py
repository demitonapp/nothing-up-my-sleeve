"""One hooked model for every outside model (11 November, the architecture audit's item 9: "the
outside-model tooling cannot read Qwen3.8 27B").

Before this, the only hook was `thorp.inside`, which swapped mlx-lm's shared attention function for an
explicit softmax and silenced a head by counting calls. That counter was reset only by `Inside.__call__`, so
generation through `mlx_lm.generate`/`batch_generate` silenced the wrong head after the first pass, and on a
hybrid model (Qwen3.5/Qwen3.8: three Gated DeltaNet layers, then one full-attention layer) "layer n" meant
"the n-th attention call", not layer n.

`HookedModel(model)` reads and edits a model by **real layer index**:

- `layer_map` (from `thorp.deltanet.layer_map`): every block's index, kind ("attention" | "linear") and head
  counts, read from the model; `attention_layers`, `linear_layers`, `n_layers`.
- `attention_patterns(tokens, layers=None, on_layer=None)`: {real layer: (batch, heads, T, T)}, or each
  layer handed to `on_layer(layer, weights)` as it is computed and nothing kept. The weights come from the
  explicit softmax(q k^T * scale + mask) that replaces the shared attention function while they are read,
  only on the layers asked for; a model whose attention does not call the shared function (Gemma 2, which
  soft-caps its scores inside the module) records nothing and `attention_readable` turns False.
- `silenced({layer: [heads]})`, `edited({layer: {...}})`: the edit is applied inside each attention module,
  on the input to its output projection (o_proj, or `dense` in Phi-2 and GPT-NeoX), where every family
  holds the heads side by side as (batch, time, heads * head_dim). A wrapper on that layer's own module
  knows its layer, so there is no call counter: the edit holds through cached, token-by-token generation and
  through `mlx_lm.generate`. Zeroing and mean-ablation (`means`) for attention heads; linear-attention layers
  are passed to `thorp.deltanet.DeltaNet`, so one `edited` edits both kinds, and a layer of the wrong kind
  is refused rather than silently left alone.
- `head_pool(kind)` and `random_heads(n, kind, rng)`: random controls drawn only from layers of that kind,
  with each layer's real head count, in the order the old pools listed them (layer, then head), so a draw
  on a pure-attention model with the same seed is the same draw as before.
- `hidden`, `ln_f`, `tok`, `layers`, `__call__`: as `thorp.inside.Inside` offered them.

By default the attention runs mlx-lm's own fused kernel and only the edit is added; `explicit = True` (as
`thorp.inside.Inside` sets it) runs the explicit float32 softmax on every attention call while an edit is in
force, so a knockout's baseline and its silenced passes share one arithmetic, as the knockout of 7 November
was measured.

`load(model_id)` is the one loader: mlx-lm's, then the ports of `scripts/mlx_ports.py` the scorers fall back
on for a model mlx-lm cannot build (Maincoder).
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import numpy as np

# the attribute a block keeps its attention module under, and the module's output projection, by family:
# self_attn/o_proj (Llama, Qwen2/3, Qwen3-Next/3.5 full attention, Phi-3, Gemma 2/3/4, SmolLM3, gpt-oss),
# self_attn/dense (Phi-2), attention/dense (GPT-NeoX, Pythia)
ATTENTION_ATTRS = ("self_attn", "attention", "attn")
OUTPUT_ATTRS = ("o_proj", "dense", "out_proj", "c_proj", "wo")


def load(model_id: str, **kw):
    """(model, tokenizer): mlx-lm's loader, then the hand ports for a model it cannot build."""
    from mlx_lm import load as _load

    try:
        return _load(model_id, **kw)
    except Exception:
        scripts = str(Path(__file__).resolve().parents[1] / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import mlx_ports  # models mlx-lm cannot load (Maincoder), built from their weights alone

        port = mlx_ports.port_for(model_id)
        if port is None:
            raise
        return port()


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
                # a multimodal wrapper whose `model` property reaches the text model (Qwen3.5/3.8) keeps
                # an untied head on its language model
                owners = (model, inner, getattr(model, "language_model", None))
                head = next(
                    (
                        getattr(owner, n)
                        for owner in owners
                        if owner is not None
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


def _explicit_sdpa(queries, keys, values, cache=None, scale=1.0, mask=None, sinks=None):
    """softmax(q k^T * scale + mask) v, and the weights: (out, (batch, heads, T, S))."""
    import mlx.core as mx

    if hasattr(cache, "bits"):
        raise ValueError("the explicit attention does not read a quantised KV cache")
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
    if sinks is None:
        w = mx.softmax(s, axis=-1)
    else:  # gpt-oss: a learned per-head logit that takes a share of the softmax and writes nothing
        sk = mx.broadcast_to(sinks.astype(mx.float32)[None, :, None, None], (B, Hq, T, 1))
        w = mx.softmax(mx.concatenate([s, sk], axis=-1), axis=-1)[..., :S]
    out = w @ values.astype(mx.float32)  # (batch, heads, time, head_dim)
    return out.astype(queries.dtype), w


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


class _Probe:
    """A layer's attention module, as its block sees it, that says which layer is running (so the explicit
    attention knows whose weights it is computing)."""

    def __init__(self, inner, layer: int, owner: HookedModel):
        self._inner, self._layer, self._owner = inner, layer, owner

    def __getattr__(self, key):
        return getattr(self._inner, key)

    def __call__(self, *a, **kw):
        prev, self._owner._current = self._owner._current, self._layer
        try:
            return self._inner(*a, **kw)
        finally:
            self._owner._current = prev


class _OutProj:
    """A layer's output projection, whose input is every head's output side by side, (batch, time,
    heads * head_dim): where a head is recorded, removed or replaced by its mean."""

    def __init__(self, inner, layer: int, owner: HookedModel):
        self._inner, self._layer, self._owner = inner, layer, owner

    def __getattr__(self, key):
        return getattr(self._inner, key)

    def __call__(self, x, *a, **kw):
        return self._inner(self._owner._edit(self._layer, x), *a, **kw)


class HookedModel:
    """An MLX-LM model read and edited by real layer index (see the module's docstring)."""

    explicit = False  # True: the explicit float32 attention on every call while an edit is in force

    def __init__(self, model):
        import mlx.core as mx

        from thorp import deltanet

        self.model = model
        self._inner, self._blocks, self._norm, self._head = _find(model)
        self.layer_map = deltanet.layer_map(model)
        self.n_layers = len(self.layer_map)
        self.attention_layers = [m["layer"] for m in self.layer_map if m["kind"] == "attention"]
        self.linear_layers = [m["layer"] for m in self.layer_map if m["kind"] == "linear"]
        self.attention_readable = True
        self._modules: dict[int, str] = {}  # layer -> the block's attribute for its attention module
        self._hooks: dict[int, str] = {}  # layer -> that module's output projection, where edits apply
        for i in self.attention_layers:
            b = self.layers[i]
            a_name = next((n for n in ATTENTION_ATTRS if getattr(b, n, None) is not None), None)
            if a_name is None:
                continue
            self._modules[i] = a_name
            a = getattr(b, a_name)
            o_name = next((n for n in OUTPUT_ATTRS if getattr(a, n, None) is not None), None)
            if o_name and self.layer_map[i].get("heads"):
                self._hooks[i] = o_name
        self._delta = None
        self._depth = 0
        self._current: int | None = None
        self._edits: dict[int, dict] = {}
        self._explicit_on = False
        self._recorder = None  # (layers wanted or None, callback(layer, weights))
        self._outputs: dict | None = None  # layer -> [sum over positions (heads * head_dim), count]

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

    # ------------------------------------------------------------------ the model as Inside offered it
    @property
    def layers(self):
        return getattr(self._inner, self._blocks)

    def ln_f(self, h):
        return self._norm(h) if self._norm is not None else h

    def __call__(self, tokens, *a, **kw):
        return self.model(tokens, *a, **kw)

    def hidden(self, tokens) -> list:
        """The residual stream after each block, every layer by its real index."""
        import mlx.core as mx

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

    @property
    def deltanet(self):
        """The linear-attention instrument on the same model (thorp.deltanet.DeltaNet)."""
        if self._delta is None:
            from thorp import deltanet

            self._delta = deltanet.DeltaNet(self.model)
        return self._delta

    def heads_of(self, layer: int) -> int:
        """A layer's real head count: query heads for attention, value heads for linear attention."""
        m = self.layer_map[layer]
        return int(m.get("heads") or 0) if m["kind"] == "attention" else int(m.get("value_heads") or 0)

    # ------------------------------------------------------------------ the wrappers
    @contextlib.contextmanager
    def _installed(self):
        """The probes, the output-projection wrappers and the shared attention function swapped, once
        however deeply the contexts nest; each context sets only the state the wrappers read."""
        if self._depth:
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
            return
        blocks = self.layers
        saved = []
        for i, a_name in self._modules.items():
            b = blocks[i]
            a = getattr(b, a_name)
            o_name = self._hooks.get(i)
            o = getattr(a, o_name) if o_name else None
            if o_name:
                setattr(a, o_name, _OutProj(o, i, self))
            setattr(b, a_name, _Probe(a, i, self))
            saved.append((b, a, o, a_name, o_name))
        mods = [
            m
            for name, m in list(sys.modules.items())
            if name.startswith("mlx_lm.models") and hasattr(m, "scaled_dot_product_attention")
        ]
        orig = {m: m.scaled_dot_product_attention for m in mods}
        for m in mods:
            m.scaled_dot_product_attention = self._sdpa(orig[m])
        self._depth = 1
        try:
            yield
        finally:
            self._depth = 0
            for m, f in orig.items():
                m.scaled_dot_product_attention = f
            for b, a, o, a_name, o_name in reversed(saved):
                if o_name:
                    setattr(a, o_name, o)
                setattr(b, a_name, a)

    def _sdpa(self, fused):
        def sdpa(queries, keys, values, cache=None, scale=1.0, mask=None, sinks=None, **kw):
            layer, rec = self._current, self._recorder
            want = rec is not None and layer is not None and (rec[0] is None or layer in rec[0])
            if not (want or self._explicit_on):
                return fused(queries, keys, values, cache=cache, scale=scale, mask=mask, sinks=sinks, **kw)
            out, w = _explicit_sdpa(queries, keys, values, cache=cache, scale=scale, mask=mask, sinks=sinks)
            if want:
                rec[1](layer, w)
            return out

        return sdpa

    def _edit(self, layer: int, x):
        import mlx.core as mx

        if self._outputs is not None:
            flat = x.astype(mx.float32).reshape(-1, x.shape[-1])
            got = self._outputs.setdefault(layer, [0.0, 0])
            got[0] = got[0] + np.array(flat.sum(axis=0))
            got[1] += flat.shape[0]
        e = self._edits.get(layer)
        if not e:
            return x
        W = x.shape[-1]
        H = self.heads_of(layer)
        D = W // H
        zero = set(e.get("zero") or ())
        if zero:
            keep = np.repeat(np.array([0.0 if h in zero else 1.0 for h in range(H)], np.float32), D)
            x = x * mx.array(keep).astype(x.dtype)
        mean = e.get("mean") or {}
        if mean:
            sel = np.zeros(W, np.float32)
            rep = np.zeros(W, np.float32)
            for h, vec in mean.items():
                sel[h * D:(h + 1) * D] = 1.0
                rep[h * D:(h + 1) * D] = np.asarray(vec, np.float32).reshape(D)
            sel_ = mx.array(sel).astype(x.dtype)
            x = x * (1 - sel_) + sel_ * mx.array(rep).astype(x.dtype)
        return x

    # ------------------------------------------------------------------ reading
    def attention_patterns(self, tokens, layers=None, on_layer=None) -> dict:
        """{real layer: (batch, heads, T, T) float32} for the attention layers asked for (all by default),
        or, with `on_layer(layer, weights)`, each handed over as it is computed and nothing kept. The
        streaming form matters for a long sequence: 36 layers of (1, 32, T, T) float32 is 18 GB at
        T = 1,100, so a trace summarised layer by layer never holds more than one."""
        import mlx.core as mx

        want = None if layers is None else set(layers)
        bad = sorted(set(want or ()) - set(self.attention_layers))
        if bad:
            raise ValueError(f"not attention layers: {bad} (attention: {self.attention_layers})")
        got: dict = {}
        seen = [0]

        def keep(layer, w):
            seen[0] += 1
            if on_layer is not None:
                on_layer(layer, w)  # read the weights now, hold nothing
            else:
                got[layer] = w

        prev, self._recorder = self._recorder, (want, keep)
        try:
            with self._installed():
                out = self.model(tokens)
                mx.eval(out)
        finally:
            self._recorder = prev
        if not seen[0]:
            self.attention_readable = False
        return got

    def means(self, tokens_list, layers=None) -> dict[int, np.ndarray]:
        """Each head's mean output over some texts: (heads, head_dim) an attention layer, as its output
        projection reads it, and (value heads, value dim) a linear layer (DeltaNet.means). What
        mean-ablation puts in a head's place. Pass unpadded sequences: every position is counted."""
        import mlx.core as mx

        want = set(self.attention_layers if layers is None else layers)
        bad = sorted(i for i in want if i not in self._hooks and i not in self.linear_layers)
        if bad:
            raise ValueError(f"no head outputs to average on layers {bad}")
        att = [i for i in want if i in self._hooks]
        lin = [i for i in want if i in self.linear_layers]
        out: dict[int, np.ndarray] = {}
        if att:
            prev, self._outputs = self._outputs, {}
            try:
                with self._installed():
                    for tokens in tokens_list:
                        mx.eval(self.model(tokens))
                got = self._outputs
            finally:
                self._outputs = prev
            for i in att:
                s, n = got[i]
                out[i] = (s / n).reshape(self.heads_of(i), -1)
        if lin:
            out.update(self.deltanet.means(tokens_list, lin))
        return out

    # ------------------------------------------------------------------ editing
    def _check_attention(self, edits: dict[int, dict]) -> None:
        for i, e in edits.items():
            if i not in self.attention_layers:
                kind = self.layer_map[i]["kind"] if 0 <= i < self.n_layers else "no such layer"
                raise ValueError(f"layer {i} is not an attention layer ({kind}; attention: {self.attention_layers})")
            if i not in self._hooks:
                raise ValueError(
                    f"layer {i}: no attention module with an output projection this tool knows "
                    f"({'/'.join(ATTENTION_ATTRS)} with {'/'.join(OUTPUT_ATTRS)}) in "
                    f"{type(self.layers[i]).__module__}"
                )
            unknown = set(e) - {"zero", "mean", "kind"}
            if unknown:
                raise ValueError(f"layer {i}: an attention head is zeroed or set to its mean, not {sorted(unknown)}")
            H = self.heads_of(i)
            heads = list(e.get("zero") or ()) + list((e.get("mean") or {}).keys())
            out = [h for h in heads if not 0 <= int(h) < H]
            if out:
                raise ValueError(f"layer {i} has {H} heads; no head {out}")

    @contextlib.contextmanager
    def edited(self, edits: dict[int, dict]):
        """A context in which the named layers' heads are changed on every pass, cached or not.

        `edits` is {real layer: spec}. An attention layer's spec is {"zero": [heads], "mean": {head:
        (head_dim,) vector}}; a linear layer's is DeltaNet's ({"zero": [value heads], "mean": {...},
        "patch": {...}}). A spec may say {"kind": "attention" | "linear"}, and a layer of the other kind is
        refused, as is a layer of neither: silently doing nothing is how a control comes out too narrow."""
        edits = {int(i): dict(e) for i, e in edits.items()}
        for i, e in edits.items():
            if not 0 <= i < self.n_layers:
                raise ValueError(f"no layer {i}: the model has {self.n_layers}")
            kind = self.layer_map[i]["kind"]
            if e.get("kind", kind) != kind:
                raise ValueError(f"layer {i} is {kind}, not {e['kind']}")
        att = {i: e for i, e in edits.items() if self.layer_map[i]["kind"] == "attention"}
        lin = {i: {k: v for k, v in e.items() if k != "kind"} for i, e in edits.items() if i not in att}
        self._check_attention(att)
        prev = (self._edits, self._explicit_on)
        self._edits = {**self._edits, **att}
        self._explicit_on = self.explicit
        try:
            with contextlib.ExitStack() as stack:
                if lin:
                    stack.enter_context(self.deltanet.edited(lin))
                stack.enter_context(self._installed())
                yield self
        finally:
            self._edits, self._explicit_on = prev

    def silenced(self, heads: dict[int, list[int]], means: dict[int, np.ndarray] | None = None):
        """A context in which these attention heads ({real layer: [heads]}) write nothing on every pass, or,
        with `means` (from `means()`), write their mean output instead. A linear layer is refused: its value
        heads are edited through `edited` (or `deltanet.removed`)."""
        bad = [i for i in heads if i not in self.attention_layers]
        if bad:
            raise ValueError(f"not attention layers: {sorted(bad)} (attention: {self.attention_layers}); "
                             "a linear layer's value heads go through edited()")
        if means is None:
            return self.edited({i: {"zero": list(h)} for i, h in heads.items()})
        return self.edited({i: {"mean": {x: means[i][x] for x in h}} for i, h in heads.items()})

    # ------------------------------------------------------------------ controls
    def head_pool(self, kind: str = "attention", exclude=()) -> list[tuple[int, int]]:
        """Every (layer, head) of that kind, layer by layer and head by head, less `exclude`."""
        if kind not in ("attention", "linear"):
            raise ValueError(f"kind is attention or linear, not {kind!r}")
        ex = {(int(a), int(b)) for a, b in exclude}
        return [
            (m["layer"], h)
            for m in self.layer_map
            if m["kind"] == kind
            for h in range(self.heads_of(m["layer"]))
            if (m["layer"], h) not in ex
        ]

    def random_heads(self, n: int, kind: str = "attention", rng=None, exclude=()) -> list[tuple[int, int]]:
        """n distinct random (layer, head) from layers of that kind only, each with its real head count,
        none in `exclude`; drawn as `rng.choice(len(pool), n, replace=False)`, as the knockouts drew."""
        pool = self.head_pool(kind, exclude)
        if n > len(pool):
            raise ValueError(f"{n} heads asked for; the {kind} pool holds {len(pool)}")
        rng = rng if rng is not None else np.random.default_rng()
        return [pool[int(i)] for i in rng.choice(len(pool), n, replace=False)]


def as_layers(heads) -> dict[int, list[int]]:
    """[(layer, head), ...] as {layer: [heads]}."""
    out: dict[int, list[int]] = {}
    for layer, head in heads:
        out.setdefault(int(layer), []).append(int(head))
    return out
