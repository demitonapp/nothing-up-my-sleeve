"""The tool leg's reading (12 November 2026, kipling:14): held-out questions, and the first move a ship makes.

Each held-out item (`lists/tools-heldout-v1.jsonl`: `prompt`, `call`, the call the lesson makes or null when no tool
is wanted, and `tool`, its name) is asked in the turn the ship was taught (thorp/turns.py `called`): the ship is
given `<question>Q` and writes greedily until it reaches `<result>` (where a harness would run the tool) or ends its
turn. Its first move (`turns.first_move`) is read:

- `tools/exact`: of the items that want a call, the share where it called with exactly the lesson's call (the name
  and its arguments, spaces aside);
- `tools/tool`: of those, the share where it named the right tool, whatever the arguments;
- `tools/none_right`: of the items that want no call, the share it answered at once (the builders of small tool
  callers report that without such lessons a model calls a tool on everything);
- `tools/score`: exact calls and right refusals over every item, the one number to set beside a target.

The standard test (the Berkeley Function-Calling Leaderboard) is written in wide English with tool definitions in
the prompt; a ship of 2,048 pieces taught a fixed set is read on its own simple-English questions instead.

eval.options.tools: `heldout`, `limit`, `max_new` (60 pieces), `clean` (marks-v1 by default).
"""

from __future__ import annotations

import json
import re

from thorp import cleaning, turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import greedy
from thorp.paths import resolve

HELDOUT = "lists/tools-heldout-v1.jsonl"
MAX_NEW = 60
_SENT = "ZQXJ"


def squash(call: str) -> str:
    return re.sub(r"\s+", "", call or "").lower()


def name_of(call: str) -> str:
    return squash(call).split("(", 1)[0]


def asked(question: str, clean: str) -> str:
    return cleaning.clean(turns.called(question, [], _SENT), clean).split(_SENT)[0].removesuffix("<answer>")


def spread(items: list, n: int) -> list:
    """`n` items taken evenly through the set, not its first `n` (13 November: the v2 set lists its 78 no-tool
    questions last, from item 300, so a limit of 200 read none of them and `tools/none_right` was 0 of nothing)."""
    if n <= 0 or n >= len(items):
        return items
    return [items[i * len(items) // n] for i in range(n)]


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("tools") or {}) if isinstance(ctx.options, dict) else {}
    path = resolve(str(opts.get("heldout") or HELDOUT))
    if not path.exists():
        return EvalResult()
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if opts.get("limit"):
        items = spread(items, int(opts["limit"]))
    clean = str(opts.get("clean") or "marks-v1")
    max_new = int(opts.get("max_new") or MAX_NEW)
    tok, model = ctx.tokeniser, ctx.model
    stops = [i for m in ("<result>", "<end>") if len(ids := tok.encode(m)) == 1 for i in ids]
    rows = []
    for it in items:
        ids = [tok.eos_id] + tok.encode(asked(it["prompt"], clean))
        out, _ = greedy(model, tok, ids, max_new, ctx.context, stops)
        kind, body = turns.first_move(tok.decode(out))
        want = it.get("call")
        row = {"key": it["key"], "want": want, "move": kind, "wrote": body[:80]}
        if want:
            row["exact"] = kind == "call" and squash(body) == squash(want)
            row["tool"] = kind == "call" and name_of(body) == name_of(want)
        else:
            row["none_right"] = kind == "answer"
        rows.append(row)
    calls = [r for r in rows if r["want"]]
    nones = [r for r in rows if not r["want"]]
    share = lambda part, k: (sum(r[k] for r in part) / len(part)) if part else 0.0  # noqa: E731
    metrics = {
        "tools/exact": share(calls, "exact"), "tools/tool": share(calls, "tool"),
        "tools/none_right": share(nones, "none_right"),
        "tools/score": (sum(r.get("exact", False) for r in calls) + sum(r.get("none_right", False) for r in nones)) / (len(rows) or 1),
        "tools/n": float(len(rows)),
    }  # fmt: skip
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "tools", "path": "", "sha1": "",
                    "text": json.dumps({"step": ctx.step, "clean": clean, "n": len(rows), "items": rows})}],  # fmt: skip
    )
