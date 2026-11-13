"""BFCL's single-turn splits in the ladder (14 November): the Berkeley Function-Calling Leaderboard's simple, multiple,
parallel, parallel-multiple, irrelevance and live-simple items, each asked once in the ship's marked turn and its
calls checked against the item's possible answers (thorp/bfcl.py: the data, the rendering and the check).

**A reimplemented, single-turn subset.** The check is ours, in the spirit of BFCL's AST checker; the multi-turn,
web-search and memory splits are not read. Never set ``bfcl/single_turn`` beside BFCL's official overall score.

Metrics, for each split read: ``bfcl/<split>/accuracy``, ``bfcl/<split>/n``, ``bfcl/<split>/skipped`` (the prompt and
the answer room did not fit the window: counted, never scored wrong) and ``bfcl/<split>/opened`` (the share
where it opened a marked turn at all). Irrelevance credits any item with no call, so a ship that rambles scores well
on it; ``bfcl/irrelevance/answered`` is the strict reading: no call, and an answer written instead. Then ``bfcl/single_turn`` (the unweighted mean
of the splits read, as BFCL averages its categories), ``bfcl/calls`` (the same over the splits that want a call) and,
for a ship that thinks before it acts, ``bfcl/thought`` (the share of items it opened with thinking).

    eval:
      evaluators: [bfcl]
      options:
        bfcl: {splits: [simple_python, irrelevance], limit: 100, max_new: 160, clean: marks-v1}

`limit` takes that many items evenly through each split (a pilot, marked ``bfcl/pilot``). The receipt is a row an
item: what the ship wrote, the calls read from it, the verdict and why.
"""

from __future__ import annotations

import json

from thorp import bfcl, turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import greedy
from thorp.evaluators.tools import asked, spread

MAX_NEW = 160


def _calls_in(text: str) -> list[str]:
    """The calls a ship wrote, in order: each body between <call> and <result> (or the end of what it wrote)."""
    out = []
    for part in text.split(turns.CALL)[1:]:
        body = part
        for u in (turns.RESULT, "<answer>", "<end>", "<eos>"):
            body = body.split(u)[0]
        out.append(body.strip())
    return out


def ask(model, tok, ids: list[int], context: int, max_new: int, parallel: int, stops: list[int]) -> str:
    """What the ship writes after its question: one round, or (for a parallel item) one round a call, each call
    answered `<result>done`, up to `parallel` calls."""
    text, left, rounds = "", max_new, max(1, parallel)
    for _ in range(rounds):
        out, _ = greedy(model, tok, ids + tok.encode(text), left, context, stops)
        piece = tok.decode(out)
        text += piece
        left -= len(out)
        last = text.rsplit(turns.CALL, 1)
        pending = len(last) == 2 and not any(m in last[1] for m in ("<answer>", "<end>", turns.RESULT))
        if not pending or left <= 8 or rounds == 1:
            break
        text += turns.RESULT + "done"
    return text


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("bfcl") or {}) if isinstance(ctx.options, dict) else {}
    splits = [s for s in (opts.get("splits") or bfcl.SPLITS) if s in bfcl.SPLITS]
    limit = int(opts.get("limit") or 0)
    clean = str(opts.get("clean") or "marks-v1")
    max_new = int(opts.get("max_new") or MAX_NEW)
    base = bfcl.ensure()
    tok, model = ctx.tokeniser, ctx.model
    stops = [i for m in (turns.RESULT, "<end>") if len(ids := tok.encode(m)) == 1 for i in ids]
    metrics: dict[str, float] = {}
    rows: list[dict] = []
    read: dict[str, float] = {}
    thought = asked_n = 0
    for split in splits:
        items = bfcl.load(split, base)
        if limit:
            items = spread(items, limit)
        right = n = skipped = opened = answered = 0
        for it in items:
            ids = [tok.eos_id] + tok.encode(asked(bfcl.rendered(it), clean))
            if len(ids) + max_new > ctx.context:
                skipped += 1
                rows.append({"split": split, "id": it["id"], "skipped": len(ids)})
                continue
            want_n = len(it.get("answers") or []) + 1 if split in bfcl.PARALLEL else 1
            text = ask(model, tok, ids, ctx.context, max_new, want_n, stops)
            steps, rest = turns.after_thought(text)
            if steps is not None:
                thought += 1
            asked_n += 1
            written = _calls_in(rest)
            calls = [bfcl.parse_call(c, it.get("function")) for c in written]
            ok, why = bfcl.score(split, calls, it)
            move = turns.first_move(rest)[0]
            opened += move != "none"
            answered += move == "answer" and not written
            right += ok
            n += 1
            rows.append({"split": split, "id": it["id"], "right": ok, "why": why, "wrote": rest[:160],
                         "calls": written[:4], **({"thought": steps[:120]} if steps else {})})  # fmt: skip
        acc = right / n if n else 0.0
        metrics[f"bfcl/{split}/accuracy"] = acc
        metrics[f"bfcl/{split}/n"] = float(n)
        metrics[f"bfcl/{split}/skipped"] = float(skipped)
        # did it open a marked turn at all (a call, an answer or its thinking)? A ship that rambles writes no call,
        # so plain irrelevance credits it; `answered` asks it to have answered instead, the strict reading
        metrics[f"bfcl/{split}/opened"] = opened / n if n else 0.0
        if split in bfcl.NO_CALL:
            metrics[f"bfcl/{split}/answered"] = answered / n if n else 0.0
        if n:
            read[split] = acc
    if read:
        metrics["bfcl/single_turn"] = sum(read.values()) / len(read)
        call_splits = [v for k, v in read.items() if k not in bfcl.NO_CALL]
        if call_splits:
            metrics["bfcl/calls"] = sum(call_splits) / len(call_splits)
    if thought:
        metrics["bfcl/thought"] = thought / max(1, asked_n)
    if limit:
        metrics["bfcl/pilot"] = 1.0
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "bfcl", "path": "", "sha1": "",
                    "text": json.dumps({"step": ctx.step, "commit": bfcl.COMMIT, "clean": clean, "limit": limit,
                                        "note": "a reimplemented single-turn subset, not BFCL's official scorer",
                                        "items": rows})}],  # fmt: skip
    )
