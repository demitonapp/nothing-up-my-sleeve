"""The question gain (12 November 2026, Kipling): how much of a held-out reply the ship gets from what it was asked, read as the reply's bits per byte after another conversation's words, less its bits per byte after its own.

Why it exists: `answers/bpb` fell from 1.93 to 1.71 over the talk leg while this number stood at 0.037 from step
50 to step 816. The leg had learned what a line of a play sounds like and nothing about using the question, and
the reading it was judged on could not tell the two apart. A ship that answers must read lower after its own
question than after someone else's; by how much is the gain.

For each held-out row (`lists/conversation-heldout-v1.jsonl`: the exchanges so far as `history`, the speech to
answer as `prompt`, the reply that followed as `response`; a row with no history, as in
`lists/talk-heldout-v1.jsonl`, is a single exchange) the reply is read three ways, in the turn format the voyage
was taught (thorp/turns.py) and through its cleaning:

- **after its own words** (`gain/bpb_own`): the history and the prompt, as the conversation was;
- **after another row's** (`gain/bpb_other`): row `i + shift` of the same file, its history and prompt whole, so
  the ship still reads a conversation of the same kind and only the subject is wrong;
- **after its prompt alone** (`gain/bpb_alone`), where the row has history: what the earlier exchanges add.

`gain/question` is other less own, and `gain/history` is alone less own: bits per byte of the reply's text, pooled
over the rows, the marks in neither the count nor the bytes. `gain/own_wins` is the share of rows read lower after
their own words (a half is chance). Nothing is written by the ship: this is a reading of its losses, a few
hundred short passes, each asked alone (never batched: in bf16 a batch's shape moves the rounding).

eval.options.question_gain: `format` (marks or plain; required), `clean` (the voyage's cleaning), `heldout` (the
rows), `limit` (rows read; all by default), `shift` (which other row lends its words; 37).

The artifact is the receipt: a row a reply.
"""

from __future__ import annotations

import json
import math

from thorp import turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.successor import _logprob
from thorp.paths import resolve

HELDOUT = "lists/conversation-heldout-v1.jsonl"
SHIFT = 37


def _rows(path: str, limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in resolve(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows if not limit or limit >= len(rows) else rows[:: max(1, len(rows) // limit)][:limit]


def _history(row: dict) -> list[tuple[str, str]]:
    return [(str(q), str(a)) for q, a in row.get("history") or []]


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("question_gain") or {}) if isinstance(ctx.options, dict) else {}
    fmt = opts.get("format")
    if fmt not in turns.FORMATS:
        return EvalResult()  # a voyage that was taught no turns has no question to gain from
    clean = str(opts.get("clean") or "raw")
    rows = _rows(str(opts.get("heldout") or HELDOUT), opts.get("limit"))
    shift = int(opts.get("shift") or SHIFT)
    if len(rows) < 2:
        return EvalResult()
    if shift % len(rows) == 0:
        shift += 1  # a row must never lend its words to itself
    tok, model = ctx.tokeniser, ctx.model

    def bits(history: list[tuple[str, str]], prompt: str, cand: list[int]) -> float:
        ids = [tok.eos_id] + tok.encode(turns.conversation(fmt, history, prompt, clean))
        room = ctx.context - len(cand) - 1
        return -float(_logprob(model, tok, ids[-room:], [cand])[0]) / math.log(2)

    out = []
    own = other = nbytes = 0.0
    alone = alone_own = alone_bytes = 0.0
    wins = 0
    for i, r in enumerate(rows):
        reply = str(r["response"]).strip()
        # the reply as it follows the prompt in a taught turn: straight after the mark, or after "Answer:"
        cand = tok.encode(reply if fmt == "marks" else " " + reply)
        if not cand or ctx.context - len(cand) - 1 < 8:  # the reply alone fills the window: not read
            continue
        lend = rows[(i + shift) % len(rows)]
        b = len(reply.encode("utf-8"))
        hist = _history(r)
        a = bits(hist, str(r["prompt"]), cand)
        o = bits(_history(lend), str(lend["prompt"]), cand)
        row = {"key": r.get("key"), "lent": lend.get("key"), "bytes": b, "exchanges_before": len(hist),
               "own": round(a / b, 4), "other": round(o / b, 4)}  # fmt: skip
        own, other, nbytes = own + a, other + o, nbytes + b
        wins += int(a < o)
        if hist:
            z = bits([], str(r["prompt"]), cand)
            alone, alone_own, alone_bytes = alone + z, alone_own + a, alone_bytes + b
            row["alone"] = round(z / b, 4)
        out.append(row)
    if not out or not nbytes:
        return EvalResult()
    metrics = {
        "gain/bpb_own": own / nbytes,
        "gain/bpb_other": other / nbytes,
        "gain/question": (other - own) / nbytes,
        "gain/own_wins": wins / len(out),
        "gain/n": float(len(out)),
    }
    if alone_bytes:
        metrics["gain/bpb_alone"] = alone / alone_bytes
        metrics["gain/history"] = (alone - alone_own) / alone_bytes
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "question_gain", "path": "", "sha1": "",
                    "text": json.dumps({"step": ctx.step, "format": fmt, "clean": clean, "shift": shift,
                                        "n": len(out), "rows": out})}],  # fmt: skip
    )
