"""The maths book read during a voyage (Justin, 2026-11-08: the 1m's primary objective, "pass De Morgan"): the 72
sums of ships/lists/tricks/maths-book.csv (nine chapters after De Morgan's Elements of Arithmetic, eight sums each),
read as the Scoring > Maths page reads them, so Augustus is measured as it sails.

- **Right:** the answer reads more likely than its rival after the sum (bits per byte, as the logic deck compares
  an idea with its rival: thorp/evaluators/logic.py `_bpb`), and the answer's first piece is among the ten
  likeliest next pieces. (The page asks for the answer among its ten likeliest next *words*; pieces are what a
  voyage reads quickly, and they agree where the answer is one piece, as most of the book's are.)
- **First:** the answer's first piece is its likeliest next piece (the stricter bar).
- **Learnt:** a chapter at six of its eight sums right; the book learnt up to the first chapter that is not.

Metrics: `maths/right` and `maths/first` (shares of the 72), `maths/chapters` (learnt, of nine, up to the first
not), `maths/ch<n>` (each chapter's sums right, of eight); artifact `maths`: every sum's verdict.
"""

from __future__ import annotations

import csv
import hashlib
import json

import numpy as np

from thorp import paths
from thorp.evaluators import EvalContext, EvalResult

BOOK = "lists/tricks/maths-book.csv"
MARK = 6  # a chapter learnt: six of its eight sums
TOP = 10


def load_book(path: str = BOOK) -> list[dict]:
    p = paths.resolve(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_sum(model, tok, r: dict) -> dict:
    from thorp.evaluators.logic import _bpb
    from thorp.models import ops

    ids = [tok.eos_id] + tok.encode(r["prompt"])
    ans, riv = _bpb(model, tok, ids, [r["answer"], r["rival"]])
    lp = ops.log_probs(model, np.array([ids]))[0, -1]
    top = np.argsort(-lp)[:TOP]
    first_piece = (tok.encode(" " + r["answer"]) or [None])[0]
    rank = int(np.where(top == first_piece)[0][0]) + 1 if first_piece in top else None
    return {"item": r["item"], "chapter": int(r["chapter"]), "answer_bpb": float(ans), "rival_bpb": float(riv),
            "rank": rank, "right": bool(ans < riv and rank is not None), "first": rank == 1}  # fmt: skip


def evaluate(ctx: EvalContext) -> EvalResult:
    rows = load_book()
    if not rows:
        return EvalResult()
    read = [read_sum(ctx.model, ctx.tokeniser, r) for r in rows]
    by: dict[int, list[dict]] = {}
    for x in read:
        by.setdefault(x["chapter"], []).append(x)
    learnt = 0
    for n in sorted(by):
        if sum(x["right"] for x in by[n]) >= MARK:
            learnt = n
        else:
            break
    metrics = {
        "maths/right": sum(x["right"] for x in read) / len(read),
        "maths/first": sum(x["first"] for x in read) / len(read),
        "maths/chapters": float(learnt),
        **{f"maths/ch{n}": float(sum(x["right"] for x in by[n])) for n in sorted(by)},
    }
    text = json.dumps(read)
    return EvalResult(metrics=metrics, artifacts=[{"kind": "maths", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text}])
