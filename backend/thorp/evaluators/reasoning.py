"""The reasoning leg's reading (12 November 2026, kipling:14): held-out chains, answered thinking and answered at once.

Each held-out item (`lists/reasoning-heldout-v1.jsonl`, written by backend/scripts/make_reasoning_corpus.py from a
stock of invented words the training lessons never use) is asked twice, in the turn the ship was taught
(thorp/turns.py `thought`), and its answer read greedily:

- **thinking** (`reasoning/on`): the ship is given `<question>Q<think>` and writes its own steps, then `<answer>`
  and its answer;
- **at once** (`reasoning/off`): the ship is given `<question>Q<think><answer>`, the empty pair, and answers.

An answer is right when it matches the item's (case, spaces and the closing full stop aside). `reasoning/gain` is
on less off: what writing the steps buys. `reasoning/thought` is the share of thinking answers that wrote any steps
at all, and `reasoning/stopped` the share that closed their turn: a ship that copies the format without the content
reads a high `thought` and no `gain`. Each is also read by the number of facts in the chain (`reasoning/on/h2` ...).

eval.options.reasoning: `heldout` (the items), `limit` (items read; all by default), `max_new` (a written answer's
cap, 160 pieces), `clean` (the voyage's cleaning, marks-v1 by default).

The artifact is the receipt: a row an item.
"""

from __future__ import annotations

import json
import re

from thorp import cleaning, turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import greedy
from thorp.evaluators.tools import spread
from thorp.paths import resolve

HELDOUT = "lists/reasoning-heldout-v1.jsonl"
MAX_NEW = 160
_SENT = "ZQXJ"


def norm(a: str) -> str:
    return re.sub(r"\s+", " ", a.strip().rstrip(".").strip().lower())


def asked(question: str, think: bool, clean: str) -> str:
    """The text a ship is given: the turn up to where it writes, cleaned as its lessons were."""
    lesson = turns.thought(question, _SENT, "x") if think else turns.thought(question, "", _SENT)
    return cleaning.clean(lesson, clean).split(_SENT)[0]


def answer_of(written: str, think: bool) -> tuple[str, bool]:
    """The answer in what a ship wrote, and whether it wrote any steps first (thinking only)."""
    if think:
        steps, _, rest = written.partition("<answer>")
        return turns.cut("marks", rest), bool(steps.strip())
    return turns.cut("marks", written), False


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("reasoning") or {}) if isinstance(ctx.options, dict) else {}
    path = resolve(str(opts.get("heldout") or HELDOUT))
    if not path.exists():
        return EvalResult()
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    limit = opts.get("limit")
    if limit:
        items = spread(items, int(limit))  # evenly through the set, as the tool evaluator reads it
    clean = str(opts.get("clean") or "marks-v1")
    max_new = int(opts.get("max_new") or MAX_NEW)
    tok, model = ctx.tokeniser, ctx.model
    end = tok.encode("<end>")
    stop = end if len(end) == 1 else ()
    rows = []
    for it in items:
        row = {"key": it["key"], "kind": it.get("kind"), "hops": it.get("hops"), "answer": it["answer"]}
        for think in (True, False):
            ids = [tok.eos_id] + tok.encode(asked(it["prompt"], think, clean))
            if len(ids) + max_new > ctx.context:
                ids = ids[-(ctx.context - max_new) :]
            out, ended = greedy(model, tok, ids, max_new, ctx.context, stop)
            ans, thought = answer_of(tok.decode(out), think)
            k = "on" if think else "off"
            row[k] = norm(ans) == norm(it["answer"])
            row[f"{k}_said"] = ans[:80]
            row[f"{k}_stopped"] = bool(ended)
            if think:
                row["thought"] = thought
        rows.append(row)
    n = len(rows) or 1
    on, off = sum(r["on"] for r in rows) / n, sum(r["off"] for r in rows) / n
    metrics = {
        "reasoning/on": on, "reasoning/off": off, "reasoning/gain": on - off, "reasoning/n": float(len(rows)),
        "reasoning/thought": sum(r["thought"] for r in rows) / n,
        "reasoning/stopped": sum(r["on_stopped"] and r["off_stopped"] for r in rows) / n,
    }  # fmt: skip
    for h in sorted({r["hops"] for r in rows if r["hops"]}):
        part = [r for r in rows if r["hops"] == h]
        metrics[f"reasoning/on/h{h}"] = sum(r["on"] for r in part) / len(part)
        metrics[f"reasoning/off/h{h}"] = sum(r["off"] for r in part) / len(part)
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "reasoning", "path": "", "sha1": "",
                    "text": json.dumps({"step": ctx.step, "clean": clean, "n": len(rows), "items": rows})}],  # fmt: skip
    )
