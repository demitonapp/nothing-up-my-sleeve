"""ARC-AGI-2 in the ladder (11 November, Justin): can a Nothing up my sleeve class solve the
canonical intelligence test?

Each task gives a few input/output grids and a new input; the model writes the output grid in the
compact form `rows x cols:row/row/...` (thorp/arc.py). The reading is ARC's own rule: **exact match**
on the output grid, with cell accuracy kept beside it as partial credit, never as a substitute. Two
attempts are made (greedy, then sampled) and both are reported: `pass@1` is the strict reading,
`pass@2` is ARC-AGI-2's own two-attempt rule.

The default is a **pilot** of 12 evaluation tasks, not the full 120: generation is token by token,
and a training run should not spend an hour on it. A spec sets the size:

    eval:
      evaluators: [arc]
      options:
        arc: {split: evaluation, limit: 120, max_pairs: 3, max_output: 512, attempts: 2}

A task whose prompt plus output budget does not fit the context is skipped and counted
(`arc/skipped_context`), never silently scored zero. The full set is what the public ARC-AGI-2
leaderboard reads; a pilot is labelled as one in the artifact and must not be compared with a
published score.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from thorp import arc
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import generate
from thorp.models import ops


def _key(ctx: EvalContext, i: int, attempt: int):
    seed = int(ctx.step) * 1000 + i * 10 + attempt
    if ops.is_torch(ctx.model):
        return seed
    import mlx.core as mx

    return mx.random.key(seed)


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("arc") or {}) if isinstance(ctx.options, dict) else {}
    split = str(opts.get("split") or "evaluation")
    limit = max(0, int(opts.get("limit", os.environ.get("THORP_ARC_LIMIT", 12))))
    pairs = max(0, int(opts.get("max_pairs", 3)))
    max_output = max(8, int(opts.get("max_output", os.environ.get("THORP_ARC_MAX_OUTPUT", 512))))
    attempts = max(1, min(2, int(opts.get("attempts", 2))))
    keep_prompts = bool(opts.get("keep_prompts", False))

    ids = opts.get("ids") or os.environ.get("THORP_ARC_IDS")
    tasks = arc.tasks(split, limit=None)
    if ids:
        want_ids = {x.strip() for x in str(ids).split(",") if x.strip()}
        tasks = [t for t in tasks if t.get("id") in want_ids]
    tasks = tasks[:limit] if limit else tasks
    if not tasks:
        return EvalResult()

    rows = []
    for i, task in enumerate(tasks):
        want = arc.expected(task)
        shape = arc.shape_of(task)
        row = {
            "id": task.get("id", f"task-{i}"),
            "split": split,
            "shape": list(shape),
            "expected": want,
            "limit": limit,
            "pilot": limit < (arc.PUBLIC_EVAL if split == "evaluation" else arc.PUBLIC_TRAIN),
        }
        prompt, used = arc.fits(task, ctx.tokeniser, ctx.context, max_output, pairs)
        if prompt is None:
            row.update({"skipped": "context", "pairs": 0, "prompt_tokens": None})
            rows.append(row)
            continue
        t0 = time.time()
        outputs = []
        parsed_any = False
        exact1 = exact2 = False
        acc = 0.0
        for attempt in range(attempts):
            text = generate(
                ctx.model,
                ctx.tokeniser,
                prompt,
                0.0 if attempt == 0 else 0.8,
                max_output,
                ctx.context,
                _key(ctx, i, attempt),
                stop_at_eos=True,
            )
            grid, ok = arc.parse_grid(text, shape=shape)
            parsed_any = parsed_any or ok
            exact = arc.exact(grid, want)
            if attempt == 0:
                exact1, acc = exact, arc.cell_accuracy(grid, want)
            else:
                exact2 = exact
            outputs.append({"text": text, "parsed": ok, "exact": exact})
            if exact:
                break
        row.update(
            {
                "pairs": used,
                "prompt_tokens": len(ctx.tokeniser.encode(prompt)),
                "outputs": outputs,
                "parsed": parsed_any,
                "exact": exact1,
                "exact2": exact2,
                "cell_accuracy": acc,
                "seconds": round(time.time() - t0, 2),
            }
        )
        if keep_prompts:
            row["prompt"] = prompt
        rows.append(row)

    scored = [r for r in rows if not r.get("skipped")]
    s = arc.summary(scored)
    skipped = len(rows) - len(scored)
    metrics = {
        f"arc/{k}": float(v)
        for k, v in {
            **s,
            "attempts": attempts,
            "skipped_context": skipped,
            "pilot": 1.0 if (limit < (arc.PUBLIC_EVAL if split == "evaluation" else arc.PUBLIC_TRAIN)) else 0.0,
        }.items()
    }
    payload = {
        "split": split,
        "limit": limit,
        "pilot": metrics["arc/pilot"] == 1.0,
        "attempts": attempts,
        "max_output": max_output,
        "max_pairs": pairs,
        "summary": s,
        "skipped_context": skipped,
        "tasks": rows,
    }
    text = json.dumps(payload, ensure_ascii=False)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "arc",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
