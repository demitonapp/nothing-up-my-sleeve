"""Cross-entropy per token and bits per byte on each held-out book.

Each book is the sequence [EOS] + tokens + [EOS], so every token of the book (and the closing EOS)
is predicted once and every byte is paid for. The sequence is cut into non-overlapping windows of
`context` predictions; the last window is padded and the padding masked out.
bits per byte = ce_nats * tokens / (bytes * ln 2), with the bytes of the text as the voyage read it
(the manifest's for raw text; tokeniser.text_bytes for a cleaned one).
"""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult

EVAL_BATCH = 16


def book_losses(model, tokens: np.ndarray, eos: int, context: int) -> np.ndarray:
    """Nats for each prediction of [EOS] + tokens: entry i is the loss on tokens[i]."""
    seq = np.concatenate([[eos], np.asarray(tokens, dtype=np.int32)])
    n_pred = len(seq) - 1
    n_win = math.ceil(n_pred / context)
    padded = np.zeros(n_win * context + 1, dtype=np.int32)
    padded[: len(seq)] = seq
    x = padded[:-1].reshape(n_win, context)
    y = padded[1:].reshape(n_win, context)
    out = np.zeros(n_win * context, dtype=np.float64)
    for i in range(0, n_win, EVAL_BATCH):
        xb, yb = mx.array(x[i : i + EVAL_BATCH]), mx.array(y[i : i + EVAL_BATCH])
        logits = model(xb).astype(mx.float32)
        ce = nn.losses.cross_entropy(logits, yb, reduction="none")
        mx.eval(ce)
        out[i * context : i * context + ce.size] = np.array(ce, dtype=np.float64).reshape(-1)
    return out[:n_pred]


def book_ce(model, tokens: np.ndarray, eos: int, context: int) -> tuple[float, int]:
    losses = book_losses(model, tokens, eos, context)
    return float(losses.sum()) / len(losses), len(losses)


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    tok = ctx.tokeniser
    for set_name, book_ids in ctx.sets.items():
        rows = []
        for b in book_ids:
            arr = shards.load(tok.id, b, tok)
            ce, n = book_ce(ctx.model, arr, tok.eos_id, ctx.context)
            nbytes = tok.text_bytes(b)  # the text as read (cleaned or raw), not always the manifest's
            rows.append(
                {
                    "run_id": ctx.run_id,
                    "step": ctx.step,
                    "set": set_name,
                    "book_id": b,
                    "ce_nats": ce,
                    "bpb": ce * n / (nbytes * math.log(2)),
                    "tokens": n,
                    "bytes": nbytes,
                }
            )
        out.evals.extend(rows)
        if rows:
            out.metrics[f"eval/{set_name}/bpb_mean"] = float(np.mean([r["bpb"] for r in rows]))
            out.metrics[f"eval/{set_name}/ce_mean"] = float(np.mean([r["ce_nats"] for r in rows]))
            en = [r for r in rows if ctx.languages.get(r["book_id"]) == "en"]
            if en:
                out.metrics[f"eval/{set_name}/bpb_mean_en"] = float(np.mean([r["bpb"] for r in en]))
                out.metrics[f"eval/{set_name}/ce_mean_en"] = float(
                    np.mean([r["ce_nats"] for r in en])
                )
    return out
