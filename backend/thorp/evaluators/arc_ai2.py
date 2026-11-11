"""AI2 ARC in the ladder (11 November): the one peer-recognised test for models under 1B -- the
grade-school science questions, four ways each, in the field's own two splits (ARC-Easy and
ARC-Challenge, ``thorp/arc_ai2.py``).

ARC-Easy is the anchor because it has a gradient at this size; ARC-Challenge sits at its 25% floor
under 1B, so it is read and kept, and it ranks nothing there until a bigger ship moves it. Read
zero-shot with the option's text as the continuation, as a base checkpoint and an instruct one alike:
no letters, no examples, no chat template and no generation, so a 300k and a 50m are read the same way.

The default is both splits, whole. A spec can set a pilot and a subset:

    eval:
      evaluators: [arc_ai2]
      options:
        arc_ai2: {configs: [easy], per_split: 300, batch: 64}

A pilot is marked ``arc_easy/pilot`` and must not be compared with a full reading. Metrics:
``arc_easy/accuracy``, ``arc_easy/n``, ``arc_easy/skipped``, ``arc_easy/excess`` (accuracy less the
25% chance), and the same four for ``arc_challenge``. A question whose options the ship's tokeniser
cannot spell is skipped and counted, never scored wrong.
"""

from __future__ import annotations

import hashlib
import json
import time

from thorp import arc_ai2
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("arc_ai2") or {}) if isinstance(ctx.options, dict) else {}
    configs = [str(c) for c in (opts.get("configs") or ["easy", "challenge"])]
    part = str(opts.get("part", "test"))
    per = opts.get("per_split")
    per = None if per in (None, 0) else int(per)
    batch = max(1, int(opts.get("batch", 64)))
    tok = ctx.tokeniser
    t0 = time.time()
    metrics: dict[str, float] = {}
    payload: dict = {"revision": arc_ai2.REVISION, "part": part, "per_split": per, "splits": {}}
    artifacts = []
    for config in configs:
        items = arc_ai2.questions(config, part, per)
        if not items:
            continue
        rows = arc_ai2.score_questions(
            lambda x, y: ops.token_ce(ctx.model, x, y),
            tok.encode,
            tok.eos_id,
            items,
            batch=batch,
            context=ctx.context,
        )
        s = arc_ai2.summary(rows)
        key = str(items[0]["config"])
        full = arc_ai2.COUNTS.get((key, part))
        pilot = full is not None and len(items) < full
        metrics[f"arc_{key}/accuracy"] = s["accuracy"]
        metrics[f"arc_{key}/n"] = float(s["questions"])
        metrics[f"arc_{key}/skipped"] = float(s["skipped"])
        metrics[f"arc_{key}/excess"] = s["excess"]
        metrics[f"arc_{key}/margin"] = s["margin_mean"]
        metrics[f"arc_{key}/pilot"] = 1.0 if pilot else 0.0
        payload["splits"][key] = {**s, "pilot": pilot, "items": len(items), "chance": arc_ai2.CHANCE}
        text = json.dumps({"config": key, **payload["splits"][key]}, ensure_ascii=False)
        artifacts.append({"kind": f"arc_{key}", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text})
    payload["seconds"] = round(time.time() - t0, 1)
    text = json.dumps(payload, ensure_ascii=False)
    artifacts.append({"kind": "arc_ai2", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text})
    return EvalResult(metrics=metrics, artifacts=artifacts)
