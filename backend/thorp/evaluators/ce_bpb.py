"""Cross-entropy per token and bits per byte on each held-out book.

Each book is the sequence [EOS] + tokens + [EOS], so every token of the book (and the closing EOS)
is predicted once and every byte is paid for. The sequence is cut into non-overlapping windows of
`context` predictions; the last window is padded and the padding masked out.
bits per byte = ce_nats * tokens / (bytes * ln 2), with the bytes of the text as the voyage read it
(the manifest's for raw text; tokeniser.text_bytes for a cleaned one).
"""

from __future__ import annotations

import math

import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops

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
        ce = ops.token_ce(model, x[i : i + EVAL_BATCH], y[i : i + EVAL_BATCH])
        out[i * context : i * context + ce.size] = np.array(ce, dtype=np.float64).reshape(-1)
    return out[:n_pred]


def book_ce(model, tokens: np.ndarray, eos: int, context: int) -> tuple[float, int]:
    losses = book_losses(model, tokens, eos, context)
    return float(losses.sum()) / len(losses), len(losses)


def losses_of(ctx: EvalContext, book: str, tokens: np.ndarray) -> np.ndarray:
    """book_losses for one of the step's books, kept on the context: ce_bpb and bpb_split read the same windows
    of the same books, so whichever comes second at a step reads what the first worked out (11 November: the
    forward passes were run twice, about 9 s of a 300k's full evaluation). Not to be written to."""
    key = ("book_losses", book)
    if key not in ctx.cache:
        ctx.cache[key] = book_losses(ctx.model, tokens, ctx.tokeniser.eos_id, ctx.context)
    return ctx.cache[key]


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    tok = ctx.tokeniser
    for set_name, book_ids in ctx.sets.items():
        rows = []
        for b in book_ids:
            arr = shards.load(tok.id, b, tok)
            losses = losses_of(ctx, b, arr)
            ce, n = float(losses.sum()) / len(losses), len(losses)
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
