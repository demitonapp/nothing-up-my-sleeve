"""What the evaluators ask of a model, on either backend: numpy in, numpy out.

Each function's MLX branch is the code the evaluators ran before the PyTorch backend existed, moved here
unchanged, so an MLX voyage's scores are what they were; the torch branch computes the same quantity in
PyTorch, under no_grad, on the model's device. A model is torch when it says so (`backend = "torch"`,
thorp/models/gpt_torch.py); anything else (Nothing up my sleeve's MLX GPT, the outside models of smoking_qwen.py and
outside_deck.py) is MLX. MLX is imported only when an MLX model is read, so a CUDA box needs none.
"""

from __future__ import annotations

import contextlib

import numpy as np


def is_torch(model) -> bool:
    return getattr(model, "backend", "mlx") == "torch"


@contextlib.contextmanager
def _reading(model):
    import torch

    was = model.training
    model.eval()
    try:
        with torch.no_grad():
            yield torch
    finally:
        model.train(was)


def _np(t) -> np.ndarray:
    return t.detach().float().cpu().numpy()


def attention_patterns(model, toks) -> list[np.ndarray]:
    """Every head's attention weights: a list per layer of (batch, heads, time, time)."""
    if is_torch(model):
        with _reading(model):
            return [_np(p) for p in model.attention_patterns(toks)]
    import mlx.core as mx

    out = []
    for p in model.attention_patterns(mx.array(toks)):
        mx.eval(p)
        out.append(np.array(p))
    return out


def hidden(model, toks) -> list[np.ndarray]:
    """The residual stream after each layer, float32: a list of (batch, time, width)."""
    if is_torch(model):
        with _reading(model):
            return [_np(h) for h in model.hidden(toks)]
    import mlx.core as mx

    hs = model.hidden(mx.array(toks))
    mx.eval(hs)
    return [np.array(h.astype(mx.float32)) for h in hs]


def pooled_hidden(model, toks, mask: np.ndarray | None = None) -> np.ndarray:
    """(batch, layers, width): the residual stream after each layer, averaged over time (over the positions
    where `mask`, (batch, time, 1), is 1, when given)."""
    if is_torch(model):
        with _reading(model) as torch:
            hs = model.hidden(toks)
            if mask is None:
                f = torch.stack([h.float().mean(dim=1) for h in hs], dim=1)
            else:
                mm = torch.as_tensor(mask, dtype=torch.float32, device=model.device)
                f = torch.stack([(h.float() * mm).sum(dim=1) / mm.sum(dim=1) for h in hs], dim=1)
            return _np(f)
    import mlx.core as mx

    hs = model.hidden(mx.array(toks))
    if mask is None:
        feats = mx.stack([h.astype(mx.float32).mean(axis=1) for h in hs], axis=1)
    else:
        mm = mx.array(mask)
        feats = mx.stack(
            [(h.astype(mx.float32) * mm).sum(axis=1) / mm.sum(axis=1) for h in hs], axis=1
        )
    mx.eval(feats)
    return np.array(feats)


def token_ce(model, x, y) -> np.ndarray:
    """(batch, time) nats: the cross-entropy of each target y[b, t] after x[b, :t + 1]."""
    if is_torch(model):
        with _reading(model) as torch:
            logits = model(x).float()
            yt = torch.as_tensor(np.asarray(y), dtype=torch.long, device=model.device)
            ce = torch.nn.functional.cross_entropy(logits.transpose(1, 2), yt, reduction="none")
            return _np(ce)
    import mlx.core as mx
    import mlx.nn as nn

    logits = model(mx.array(x)).astype(mx.float32)
    ce = nn.losses.cross_entropy(logits, mx.array(y), reduction="none")
    mx.eval(ce)
    return np.array(ce)


def log_probs(model, x) -> np.ndarray:
    """(batch, time, vocab) log-probabilities of the next piece."""
    if is_torch(model):
        with _reading(model) as torch:
            return _np(torch.log_softmax(model(x).float(), dim=-1))
    import mlx.core as mx

    logits = model(mx.array(x)).astype(mx.float32)
    lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    mx.eval(lp)
    return np.array(lp)


def token_stats(model, x, y, qmask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per predicted position: the entropy, the loss on y, and the probability on the pieces in qmask."""
    if is_torch(model):
        with _reading(model) as torch:
            logp = torch.log_softmax(model(x).float(), dim=-1)
            p = logp.exp()
            qm = torch.as_tensor(qmask.astype(np.float32), device=model.device)
            yt = torch.as_tensor(np.asarray(y), dtype=torch.long, device=model.device)
            h = -(p * logp).sum(dim=-1)
            ce = -logp.gather(-1, yt[..., None])[..., 0]
            return _np(h), _np(ce), _np((p * qm).sum(dim=-1))
    import mlx.core as mx

    qm = mx.array(qmask.astype(np.float32))
    lg = model(mx.array(x)).astype(mx.float32)
    logp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
    p = mx.exp(logp)
    h = -(p * logp).sum(axis=-1)
    ce = -mx.take_along_axis(logp, mx.array(y)[..., None], axis=-1)[..., 0]
    pq = (p * qm).sum(axis=-1)
    mx.eval(h, ce, pq)
    return np.array(h), np.array(ce), np.array(pq)


def lens_log_probs(model, toks, pos: int = -1) -> list[np.ndarray]:
    """Per layer, the logit lens at one position: log-probabilities (batch, vocab) read off the residual
    stream after that layer through the final norm and the tied output layer."""
    if is_torch(model):
        with _reading(model) as torch:
            return [
                _np(torch.log_softmax(model.lens(h[:, pos, :]).float(), dim=-1))
                for h in model.hidden(toks)
            ]
    import mlx.core as mx

    out = []
    for h in model.hidden(mx.array(toks)):
        lg = model.tok.as_linear(model.ln_f(h[:, pos, :])).astype(mx.float32)
        lp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
        mx.eval(lp)
        out.append(np.array(lp))
    return out


def softmax_top(model, x, top: int) -> tuple[np.ndarray, np.ndarray]:
    """For one sequence (1, time): the next-piece probabilities (time, vocab) and the `top` likeliest
    pieces at each position (time, top), likeliest first."""
    if is_torch(model):
        with _reading(model) as torch:
            probs = torch.softmax(model(x)[0].float(), dim=-1)
            return _np(probs), torch.argsort(-probs, dim=-1)[:, :top].cpu().numpy()
    import mlx.core as mx

    logits = model(mx.array(x))[0].astype(mx.float32)
    probs = mx.softmax(logits, axis=-1)
    top_ = mx.argsort(-probs, axis=-1)[:, :top]
    mx.eval(probs, top_)
    return np.array(probs), np.array(top_)


def last_logits(model, x) -> np.ndarray:
    """(batch, vocab) float32: the logits at the last position (torch only; the MLX samplers keep their
    own code, keyed by MLX's generator)."""
    with _reading(model):
        return _np(model(x)[:, -1])


# ---------------------------------------------------------------- generation with a key/value cache
#
# 11 November (the architecture audit, item 5): every evaluator that writes (samples, laws, arc, ifeval, answers)
# ran one full forward pass over the whole window for every piece it wrote, at batch 1, the logits copied to numpy
# each time. The Decoder below gives the same last-position logits from a key/value cache: the prompt is read once,
# in one forward pass, and each later piece costs one position. The samplers keep their own code and their own draws
# (MLX's keys, numpy's generator), so only where the logits come from changes.
#
# Used for GREEDY writing only. On a tiny model the cached and full passes give the same pieces, greedy and sampled,
# on both backends (tests/test_offline_eval.py). On the 1m's own checkpoint in bf16 the logits differ by up to 0.3
# (a unit or two in bf16's last place at that size): greedy still wrote the same 7 x 200 pieces, but 6 of 7
# temperature-0.8 continuations parted within 200 pieces. So a sampled loop (laws, samples at 0.8, ARC's second
# attempt) keeps the full pass, `Decoder(..., cache=False)`, and its numbers stay what they were.
#
# The cache is exact only while the whole sequence fits the context: past it the old code slides a window, so every
# position moves and nothing cached is valid. There, and for any model that is not our GPT (the outside models), it
# falls back to the old full forward pass on the window, call for call. THORP_GENERATE_CACHE=0 forces that path.


def _cacheable(model) -> bool:
    import os

    if os.environ.get("THORP_GENERATE_CACHE", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    if is_torch(model):
        from thorp.models.gpt_torch import GPT
    else:
        from thorp.models.gpt_mlx import GPT
    return isinstance(model, GPT)


class Decoder:
    """seqs -> the logits after each sequence's last piece, (batch, vocab) float32: an mx.array for an MLX model,
    numpy for a torch one, exactly what the old loops computed from `model(window)[:, -1]` (to float tolerance:
    one query against the cache is not the same kernel as the full causal pass, so the last bits can differ).

    Call it with the sequences grown by one piece each since the last call (all the same length), as a writing
    loop does; anything else (the first call, a new batch, sequences that do not extend the last ones) reads the
    sequences afresh. `cached` says whether the cache is in use at all."""

    def __init__(self, model, context: int, cache: bool = True):
        self.model, self.context = model, int(context)
        self.cached = cache and _cacheable(model)
        self.kv: list | None = None
        self.n = 0
        self.last: list[int] = []

    def __call__(self, seqs):
        lens = {len(s) for s in seqs}
        n = lens.pop() if len(lens) == 1 else 0
        if not self.cached or n == 0 or n > self.context:
            self.kv = None
            return self._full([list(s)[-self.context:] for s in seqs])
        grown = (
            self.kv is not None
            and n == self.n + 1
            and len(seqs) == len(self.last)
            and all(s[self.n - 1] == t for s, t in zip(seqs, self.last, strict=True))
        )
        if grown:
            out = self._step([[s[-1]] for s in seqs], self.n)
        else:
            self.kv = None
            out = self._step([list(s) for s in seqs], 0)
        self.n, self.last = n, [s[-1] for s in seqs]
        return out

    def _full(self, windows):
        if is_torch(self.model):
            return last_logits(self.model, windows)
        import mlx.core as mx

        return self.model(mx.array(windows))[:, -1].astype(mx.float32)

    def _step(self, toks, offset: int):
        return (self._step_torch if is_torch(self.model) else self._step_mlx)(toks, offset)

    def _step_mlx(self, toks, offset: int):
        """GPT.__call__ of gpt_mlx.py, the new positions only, their keys and values joined to the cache's."""
        import mlx.core as mx

        m = self.model
        t = mx.array(toks)
        B, T = t.shape
        x = m.tok(t)
        if not m.rotary:
            x = x + m.pos(mx.arange(offset, offset + T))
        kv = []
        for i, b in enumerate(m.layers):
            a = b.attn
            h = b.ln1(x)
            if a.kv_heads == a.heads:
                q, k, v = mx.split(a.qkv(h), 3, axis=-1)
            else:
                q, k, v = a.q_proj(h), a.k_proj(h), a.v_proj(h)
            q = q.reshape(B, T, a.heads, a.head_dim).transpose(0, 2, 1, 3)
            k = k.reshape(B, T, a.kv_heads, a.head_dim).transpose(0, 2, 1, 3)
            v = v.reshape(B, T, a.kv_heads, a.head_dim).transpose(0, 2, 1, 3)
            if a.rope is not None:
                q, k = a.rope(q, offset=offset), a.rope(k, offset=offset)
            if self.kv is not None:
                pk, pv = self.kv[i]
                k, v = mx.concatenate([pk, k], axis=2), mx.concatenate([pv, v], axis=2)
            y = mx.fast.scaled_dot_product_attention(
                q, k, v, scale=a.head_dim**-0.5, mask="causal" if T > 1 else None
            )
            x = x + a.proj(y.transpose(0, 2, 1, 3).reshape(B, T, -1))
            x = x + b.mlp(b.ln2(x))
            kv.append((k, v))
        logits = m.tok.as_linear(m.ln_f(x))[:, -1].astype(mx.float32)
        mx.eval(logits, kv)
        self.kv = kv
        return logits

    def _step_torch(self, toks, offset: int):
        """GPT.forward of gpt_torch.py, the new positions only, their keys and values joined to the cache's."""
        import torch.nn.functional as F

        m = self.model
        with _reading(m) as torch:
            t = m._tokens(toks)
            B, T = t.shape
            x = m.tok(t)
            if not m.rotary:
                x = x + m.pos(torch.arange(offset, offset + T, device=t.device))
            kv = []
            for i, b in enumerate(m.layers):
                a = b.attn
                h = b.ln1(x)
                if a.kv_heads == a.heads:
                    q, k, v = a.qkv(h).split(h.shape[-1], dim=-1)
                else:
                    q, k, v = a.q_proj(h), a.k_proj(h), a.v_proj(h)
                q = q.reshape(B, T, a.heads, a.head_dim).transpose(1, 2)
                k = k.reshape(B, T, a.kv_heads, a.head_dim).transpose(1, 2)
                v = v.reshape(B, T, a.kv_heads, a.head_dim).transpose(1, 2)
                if a.rope is not None:
                    q, k = _rope_torch(a.rope, q, offset), _rope_torch(a.rope, k, offset)
                if a.kv_heads != a.heads:
                    g = a.heads // a.kv_heads
                    k, v = k.repeat_interleave(g, dim=1), v.repeat_interleave(g, dim=1)
                if self.kv is not None:
                    pk, pv = self.kv[i]
                    k, v = torch.cat([pk, k], dim=2), torch.cat([pv, v], dim=2)
                y = F.scaled_dot_product_attention(q, k, v, is_causal=T > 1, scale=a.head_dim**-0.5)
                x = x + a.proj(y.transpose(1, 2).reshape(B, T, -1))
                x = x + b.mlp(b.ln2(x))
                kv.append((k, v))
            self.kv = kv
            return _np(m.tok.as_linear(m.ln_f(x))[:, -1])


def _rope_torch(rope, x, offset: int):
    """gpt_torch.RoPE.forward for positions offset .. offset + time - 1 (the same angles, the same casts)."""
    import torch

    T, half = x.shape[-2], rope.dims // 2
    inv = rope.base ** (-torch.arange(half, dtype=torch.float32, device=x.device) * 2 / rope.dims)
    pos = torch.arange(offset, offset + T, dtype=torch.float32, device=x.device)
    ang = pos[:, None] * inv[None, :]
    cos, sin = ang.cos().to(x.dtype), ang.sin().to(x.dtype)
    x1, x2 = x[..., :half], x[..., half : rope.dims]
    out = torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)
    return out if rope.dims == x.shape[-1] else torch.cat([out, x[..., rope.dims :]], dim=-1)
