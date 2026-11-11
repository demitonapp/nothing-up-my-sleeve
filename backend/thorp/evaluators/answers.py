"""The return leg's reading (11 November 2026, Kipling): held-out questions, and the answer's own loss.

For each question-and-answer pair the voyage never trained on (`lists/return-heldout-v1.jsonl`: IFEval prompts
split off by key, each with a response the official checker passes), the ship is asked in the turn format it
was taught (thorp/turns.py) and read two ways:

- **the answer's loss** (`answers/bpb`): the bits per byte of the answer text alone, given the question. The
  marks themselves are in neither the count nor the bytes, so a marked ship and a plain ship are scored on
  identical text. This is the control-token proof's deciding number: the marked ships must read lower than the
  plain ones on both seeds, by more than the plain seeds differ.
- **the answer it writes** (greedy, capped): whether it ended its own turn (`answers/stopped`), and whether
  what it wrote passes the official checkers (`answers/prompt_strict`, `answers/instruction_strict`): IFEval on
  prompts it was never shown, reported beside the loss and not deciding.

eval.options.answers: `format` (marks or plain; required), `clean` (the voyage's cleaning), `heldout` (the
pairs), `limit` (pairs read; all by default), `max_new` (the cap on a written answer, 160 pieces).

The artifact is the receipt: a row a pair.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from thorp import turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import greedy
from thorp.evaluators.successor import _logprob
from thorp.paths import resolve

HELDOUT = "lists/return-heldout-v1.jsonl"
MAX_NEW = 160

os.environ.setdefault("NLTK_DATA", str(resolve("lists/nltk_data")))


def _pairs(path: str, limit: int | None) -> list[dict]:
    rows = [json.loads(line) for line in resolve(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["key"])
    return rows if not limit or limit >= len(rows) else rows[:: max(1, len(rows) // limit)][:limit]


def evaluate(ctx: EvalContext) -> EvalResult:
    from thorp.evaluators.ifeval import _check

    opts = ((ctx.options or {}).get("answers") or {}) if isinstance(ctx.options, dict) else {}
    fmt = opts.get("format")
    if fmt not in turns.FORMATS:
        return EvalResult()  # a voyage that was taught no turns has no answer to read
    clean = str(opts.get("clean") or "raw")
    max_new = int(opts.get("max_new") or MAX_NEW)
    pairs = _pairs(str(opts.get("heldout") or HELDOUT), opts.get("limit"))
    cases = {r["key"]: r for r in (json.loads(line) for line in resolve("lists/ifeval-input-v1.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}  # fmt: skip
    tok, model = ctx.tokeniser, ctx.model
    end = tok.encode("<end>") if fmt == "marks" else []
    stop_ids = end if len(end) == 1 else ()
    rows, bits, nbytes = [], 0.0, 0
    stopped = strict = instr_ok = instr_n = 0
    for p in pairs:
        asked = turns.prompt(fmt, p["prompt"], clean)
        ids = [tok.eos_id] + tok.encode(asked)
        answer = p["response"].strip()
        # the answer as it follows the question in a taught turn: straight after the mark, or after "Answer:"
        cand = tok.encode(answer if fmt == "marks" else " " + answer)
        room = ctx.context - len(cand) - 1
        if room < 8:  # the answer alone fills the window: not read
            continue
        lp = float(_logprob(model, tok, ids[-room:], [cand])[0])
        b = len(answer.encode("utf-8"))
        bpb = -lp / math.log(2) / b
        bits, nbytes = bits - lp / math.log(2), nbytes + b
        out, ended = greedy(model, tok, ids, max_new, ctx.context, stop_ids)
        written = turns.cut(fmt, tok.decode(out))
        row = cases.get(p["key"])
        checks = _check(row, written) if row else []
        ok = bool(checks) and all(c["followed"] for c in checks)
        stopped += int(ended)
        strict += int(ok)
        instr_ok += sum(c["followed"] for c in checks)
        instr_n += len(checks)
        rows.append({"key": p["key"], "bpb": round(bpb, 4), "bytes": b, "stopped": bool(ended), "passed": ok,
                     "chars": len(written)})  # fmt: skip
    n = len(rows) or 1
    metrics = {
        "answers/bpb": float(np.mean([r["bpb"] for r in rows])) if rows else 0.0,
        "answers/bpb_pooled": bits / nbytes if nbytes else 0.0,
        "answers/n": float(len(rows)),
        "answers/stopped": stopped / n,
        "answers/prompt_strict": strict / n,
        "answers/instruction_strict": (instr_ok / instr_n) if instr_n else 0.0,
    }
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "answers", "path": "", "sha1": "",
                    "text": json.dumps({"step": ctx.step, "format": fmt, "clean": clean, "n": len(rows), "pairs": rows})}],  # fmt: skip
    )
