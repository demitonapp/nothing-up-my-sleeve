"""BLiMP in the ladder (11 November, Justin): the grammatical reading beside AI2 ARC, which took the
name of the one peer-recognised test for models under 1B on the same day (``thorp/arc_ai2.py``).

Each of the 67,000 minimal pairs (thorp/blimp.py) is two sentences, one grammatical and one not; a
model is right when it gives the grammatical one the higher log probability. There is no prompt and
no generation, so the reading is the same for a 300k and a 50m: only the model's own loss, with the
ship's own tokeniser and a start piece (EOS) in front, as ce_bpb reads a book.

The default is the whole benchmark, which is cheap (short sentences). A spec can set a pilot:

    eval:
      evaluators: [blimp]
      options:
        blimp: {per_paradigm: 100, batch: 128}

A pilot (fewer than 1,000 pairs a paradigm) is marked ``blimp/pilot`` and must not be compared with a
full reading. A pair too long for the context is skipped and counted (``blimp/skipped``), never
scored wrong. Metrics: ``blimp/accuracy`` (mean over paradigms), ``blimp/macro_terms`` (mean over the
13 phenomena), ``blimp/by_field/<field>``, ``blimp/by_term/<term>``.
"""

from __future__ import annotations

import hashlib
import json
import time

from thorp import blimp
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("blimp") or {}) if isinstance(ctx.options, dict) else {}
    per = opts.get("per_paradigm")
    per = None if per in (None, 0) else int(per)
    batch = max(1, int(opts.get("batch", 128)))
    items = blimp.pairs(per)
    if not items:
        return EvalResult()
    tok = ctx.tokeniser
    t0 = time.time()
    rows = blimp.score_pairs(
        lambda x, y: ops.token_ce(ctx.model, x, y),
        tok.encode,
        tok.eos_id,
        items,
        batch=batch,
        context=ctx.context,
    )
    s = blimp.summary(rows)
    pilot = per is not None and per < blimp.PER_PARADIGM
    metrics = {
        "blimp/accuracy": s["accuracy"],
        "blimp/macro_terms": s["macro_terms"],
        "blimp/pairs": float(s["pairs"]),
        "blimp/ties": float(s["ties"]),
        "blimp/skipped": float(s["skipped"]),
        "blimp/pilot": 1.0 if pilot else 0.0,
        **{f"blimp/by_field/{k}": v for k, v in s["by_field"].items()},
        **{f"blimp/by_term/{k}": v for k, v in s["by_term"].items()},
    }
    payload = {
        "pilot": pilot,
        "per_paradigm": per,
        "revision": blimp.REVISION,
        "seconds": round(time.time() - t0, 1),
        "summary": s,
    }
    text = json.dumps(payload, ensure_ascii=False)
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "blimp", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text}],
    )
