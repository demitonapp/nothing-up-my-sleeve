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


def shaped(logits: np.ndarray, written: list[int], temperature: float, top_k: int | None, top_p: float | None,
           repetition_penalty: float | None, window: int = 64) -> np.ndarray:
    """The next-token scores as a small model should be sampled from (11 November, the talk leg): a piece
    written in the last `window` is made less likely (`repetition_penalty`, the usual rule: a positive score
    divided, a negative one multiplied), then everything outside the `top_k` likeliest and outside the
    smallest set holding `top_p` of the probability at this temperature is struck. Sampling the whole
    vocabulary lets a weak model draw from its long tail, and a greedy one loops ("the man of the man of
    the man"); this keeps both the likeliest pieces and a little choice among them."""
    z = np.array(logits, dtype=np.float64)
    if repetition_penalty and repetition_penalty != 1.0 and written:
        seen = np.unique(np.asarray(written[-window:], dtype=np.int64))
        z[seen] = np.where(z[seen] > 0, z[seen] / repetition_penalty, z[seen] * repetition_penalty)
    if top_k and 0 < top_k < z.size:
        z[z < np.partition(z, -top_k)[-top_k]] = -np.inf
    if top_p and 0 < top_p < 1 and temperature > 0:
        order = np.argsort(-z)
        zs = z[order] / temperature
        probs = np.exp(zs - zs[0])
        probs /= probs.sum()
        keep = np.cumsum(probs) - probs < top_p  # the likeliest piece is always kept
        z[order[~keep]] = -np.inf
    return z.astype(np.float32)


def generate(model, tok, prompt: str, temperature: float, n: int, context: int, key, stop_at_eos: bool = False,
             *, top_k: int | None = None, top_p: float | None = None, repetition_penalty: float | None = None,
             stop_ids: tuple[int, ...] = ()) -> str:  # fmt: skip
    """`key` is an MLX random key for an MLX model, an integer seed for a torch one (whose draws are
    numpy's, so the two backends' samples differ even from the same weights). With `stop_at_eos`,
    generation ends at the model's end-of-text mark (ARC-AGI-2 reads the answer, not the padding).
    `top_k`, `top_p` and `repetition_penalty` shape the scores first (`shaped`); with none of them the
    draws are exactly what they always were. A piece in `stop_ids` ends the writing and is not returned."""
    ids = tok.encode(prompt)
    out = []
    eos = getattr(tok, "eos_id", None)
    shaping = bool(top_k or top_p or (repetition_penalty and repetition_penalty != 1.0))
    if ops.is_torch(model):
        rng = np.random.default_rng(key)
        for _ in range(n):
            logits = ops.last_logits(model, [(ids + out)[-context:]])[0]
            if shaping:
                logits = shaped(np.asarray(logits), out, temperature, top_k, top_p, repetition_penalty)
            nxt = _pick(logits, temperature, rng)
            if (stop_at_eos and eos is not None and nxt == eos) or nxt in stop_ids:
                break
            out.append(nxt)
        return tok.decode(out)
    import mlx.core as mx

    for i in range(n):
        x = mx.array([(ids + out)[-context:]])
        logits = model(x)[0, -1].astype(mx.float32)
        if shaping:
            logits = mx.array(shaped(np.array(logits), out, temperature, top_k, top_p, repetition_penalty))
        if temperature == 0:
            nxt = mx.argmax(logits)
        else:
            nxt = mx.random.categorical(logits / temperature, key=mx.random.split(key, n)[i])
        token = int(nxt.item())
        if (stop_at_eos and eos is not None and token == eos) or token in stop_ids:
            break
        out.append(token)
    return tok.decode(out)


def greedy(model, tok, ids: list[int], n: int, context: int, stop_ids=()) -> tuple[list[int], bool]:
    """The model's own continuation of `ids`, most likely piece by most likely piece, for at most `n` pieces:
    the pieces written, and whether it stopped itself (the end-of-text mark, or one of `stop_ids`, which is
    not kept) rather than running into the cap. The same on both backends."""
    stops = {int(i) for i in stop_ids}
    eos = getattr(tok, "eos_id", None)
    if eos is not None:
        stops.add(int(eos))
    out: list[int] = []
    torch = ops.is_torch(model)
    if not torch:
        import mlx.core as mx
    dec = ops.Decoder(model, context)  # the key/value cache (11 November): one position a piece
    for _ in range(n):
        if torch:
            token = int(np.argmax(dec([ids + out])[0]))
        else:
            token = int(mx.argmax(dec([ids + out])[0]).item())
        if token in stops:
            return out, True
        out.append(token)
    return out, False


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
