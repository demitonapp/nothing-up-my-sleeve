"""The inside view of an outside model (2026-11-07, Justin: "validate the cards first"): attention
patterns and the residual stream, layer by layer, for any MLX-LM model, so the cards (thorp/evaluators/
cards.py) read Qwen, Llama, Phi, Gemma, SmolLM3 and Pythia exactly as they read Nothing up my sleeve.

`Inside(model)` offers what Nothing up my sleeve's own GPT offers:
- `attention_patterns(tokens)`: per attention layer, every head's attention weights (batch, heads, T, T).
  MLX-LM computes attention in one fused kernel that does not return its weights, so while a pattern is
  read the shared `scaled_dot_product_attention` (in mlx_lm.models.base, and wherever a model module
  imported it) is swapped for an explicit softmax(q k^T * scale + mask) v that records the weights; grouped
  key-value heads are repeated to the query heads. A model whose attention does not call the shared
  function (Gemma 2, with its soft-capping) records nothing: `attention_readable` is False and the
  attention cards are not read for it.
- `hidden(tokens)`: the residual stream after each block, recorded by wrapping each block.
- `ln_f(h)` and `tok.as_linear(x)`: the final norm and the unembedding, for the logit lens.
- `silenced({layer: [heads]})`: the knockout (7 November), every pass through the explicit attention with
  those heads' outputs zeroed.

Since 11 November (the architecture audit's item 9) Inside is `thorp.hooked.HookedModel` with the explicit
attention kept on for the knockout, so its arithmetic is what it was, and two things fixed:
- a silenced head is found by a wrapper on its own layer's attention module, not by counting calls. The
  count was reset only by `Inside.__call__`, so a `hidden` pass, a pattern read or generation through
  `mlx_lm.batch_generate` under `silenced` zeroed the wrong heads (or none) after the first pass.
- layers are real layer indices. On a hybrid model (Qwen3.5/3.8, Gated DeltaNet layers between the
  attention layers) `silenced` and the streaming `on_layer(layer, w)` take and give the real index, and a
  linear layer is refused. The list `attention_patterns(tokens)` returns has one entry per attention
  layer, in order, because the evaluators stack it into (layers, heads) matrices; `pattern_layers` gives
  each entry's real layer (on a pure-attention model, list position and layer are the same).
"""

from __future__ import annotations

from thorp.hooked import HookedModel, _explicit_sdpa, _find, _Tap  # noqa: F401  (_find: thorp.deltanet)


class Inside(HookedModel):
    # the knockout's baseline and its silenced passes run the same explicit float32 attention, as the
    # knockout of 7 November was measured
    explicit = True

    @property
    def pattern_layers(self) -> list[int]:
        """The real layer of each entry of `attention_patterns(tokens)`, and of each row of a (layers,
        heads) matrix an evaluator builds from it."""
        return list(self.attention_layers)

    def attention_patterns(self, tokens, on_layer=None) -> list:  # type: ignore[override]
        """Every attention layer's weights, in order (`pattern_layers` names their real layers), or, with
        `on_layer(layer, weights)` given, each layer handed to the caller by its real index as it is
        computed and nothing kept (see HookedModel.attention_patterns)."""
        got = HookedModel.attention_patterns(self, tokens, on_layer=on_layer)
        if on_layer is not None:
            return []
        return [got[i] for i in sorted(got)]
