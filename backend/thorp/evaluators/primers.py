"""The two primers read during a voyage (DECISIONS.md, "Four positions at the 1m"; thorp/primers.py): Plato's held-out items
(ships/lists/tricks/plato-primer.csv, metaphysics) and Francis's (francis-primer.csv, empirical knowledge), read as the
maths book is: the answer reads more likely than its rival after the prompt, and its first piece is among the ten
likeliest next pieces. Every ship reads both, and the maths book beside them, so the four positions are measured as a
four by four.

Metrics, for `<who>` = plato or francis: `<who>/right` and `<who>/first` (shares of the items), `<who>/ch<n>` (each chapter's
items right) and, for Plato, `plato/right_not_seems`: the share right without the "seems and is" chapter, the one
contestable chapter (Justin took that recommendation, 2026-11-08), so it cannot decide a verdict. Artifact `<who>`:
every item's verdict.
"""

from __future__ import annotations

import hashlib
import json

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.maths import load_book, read_sum

SEEMS = {"plato": 4}  # the chapter of "seems and is" in Plato's primer


def evaluate_for(who: str, ctx: EvalContext) -> EvalResult:
    rows = load_book(f"lists/tricks/{who}-primer.csv")
    if not rows:
        return EvalResult()
    read = [read_sum(ctx.model, ctx.tokeniser, r) for r in rows]
    by: dict[int, list[dict]] = {}
    for x in read:
        by.setdefault(x["chapter"], []).append(x)
    metrics = {
        f"{who}/right": sum(x["right"] for x in read) / len(read),
        f"{who}/first": sum(x["first"] for x in read) / len(read),
        **{f"{who}/ch{n}": float(sum(x["right"] for x in by[n])) for n in sorted(by)},
    }
    if who in SEEMS:
        rest = [x for x in read if x["chapter"] != SEEMS[who]]
        metrics[f"{who}/right_not_seems"] = sum(x["right"] for x in rest) / max(1, len(rest))
    text = json.dumps(read)
    return EvalResult(metrics=metrics, artifacts=[{"kind": who, "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text}])


def evaluate_plato(ctx: EvalContext) -> EvalResult:
    return evaluate_for("plato", ctx)


def evaluate_francis(ctx: EvalContext) -> EvalResult:
    return evaluate_for("francis", ctx)
