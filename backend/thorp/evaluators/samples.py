"""Fixed prompts -> greedy and temperature-0.8 continuations, plus the top-10 after the first prompt.

The first prompt asks for a law of physics rather than the capital of France (2026-11-06): a law
does not move with the date, and no book on the hundred-by-reach shelf states it, so the bar for
"reaction" is a tracer for the day a textbook shelf arrives. The other three are first lines of
books on the shelf, so a perfect continuation there is memory, not prediction; they stay as a
memory check. The top-10 artifact carries its prompt, so the page never assumes which it was.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops

PROMPTS = [
    "For every action there is an equal and opposite",
    "It is a truth universally acknowledged",
    "The Master said",
    "In the beginning",
]
PROBE = PROMPTS[0]
NEW_TOKENS = 60
TEMPERATURE = 0.8


def generate(model, tok, prompt: str, temperature: float, n: int, context: int, key) -> str:
    """`key` is an MLX random key for an MLX model, an integer seed for a torch one (whose draws are
    numpy's, so the two backends' samples differ even from the same weights)."""
    ids = tok.encode(prompt)
    out = []
    if ops.is_torch(model):
        rng = np.random.default_rng(key)
        for _ in range(n):
            out.append(_pick(ops.last_logits(model, [(ids + out)[-context:]])[0], temperature, rng))
        return tok.decode(out)
    import mlx.core as mx

    for i in range(n):
        x = mx.array([(ids + out)[-context:]])
        logits = model(x)[0, -1].astype(mx.float32)
        if temperature == 0:
            nxt = mx.argmax(logits)
        else:
            nxt = mx.random.categorical(logits / temperature, key=mx.random.split(key, n)[i])
        out.append(int(nxt.item()))
    return tok.decode(out)


def _pick(logits: np.ndarray, temperature: float, rng) -> int:
    """The torch models' sampler: greedy at temperature 0, else a draw from softmax(logits / T)."""
    if temperature == 0:
        return int(np.argmax(logits))
    z = logits.astype(np.float64) / temperature
    p = np.exp(z - z.max())
    return int(rng.choice(len(p), p=p / p.sum()))


def top10(model, tok, prompt: str) -> list[dict]:
    if ops.is_torch(model):
        lg = ops.last_logits(model, [tok.encode(prompt)])[0].astype(np.float64)
        p = np.exp(lg - lg.max())
        p /= p.sum()
        order = np.argsort(-p)[:10].tolist()
        return [{"token": tok.sp.id_to_piece(i), "id": i, "p": float(p[i])} for i in order]
    import mlx.core as mx

    logits = model(mx.array([tok.encode(prompt)]))[0, -1].astype(mx.float32)
    probs = mx.softmax(logits)
    order = mx.argsort(-probs)[:10].tolist()
    return [{"token": tok.sp.id_to_piece(i), "id": i, "p": probs[i].item()} for i in order]


def evaluate(ctx: EvalContext) -> EvalResult:
    if ops.is_torch(ctx.model):
        key = ctx.step
    else:
        import mlx.core as mx

        key = mx.random.key(ctx.step)
    samples = []
    for p in PROMPTS:
        for t in (0.0, TEMPERATURE):
            text = generate(ctx.model, ctx.tokeniser, p, t, NEW_TOKENS, ctx.context, key)
            samples.append({"prompt": p, "temperature": t, "text": text})
    s = json.dumps(samples, ensure_ascii=False)
    t10 = json.dumps(
        {"prompt": PROBE, "top": top10(ctx.model, ctx.tokeniser, PROBE)}, ensure_ascii=False
    )
    sha = lambda x: hashlib.sha1(x.encode()).hexdigest()  # noqa: E731
    return EvalResult(
        artifacts=[
            {"kind": "samples", "path": "", "sha1": sha(s), "text": s},
            {"kind": "top10", "path": "", "sha1": sha(t10), "text": t10},
        ]
    )
