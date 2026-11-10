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
