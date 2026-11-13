"""When2Call in the ladder (14 November): when (not) to call a tool, NVIDIA's multiple-choice set read zero-shot by
likelihood in the ship's own turns (``thorp/when2call.py``), so a 9m, a 21m and a 50m are read the same way.

The default is the whole set (3,652 questions). A spec can set a pilot, taken evenly through the set:

    eval:
      evaluators: [when2call]
      options:
        when2call: {limit: 600, batch: 32, clean: marks-v1}

A pilot is marked ``when2call/pilot`` and must not be compared with a full reading. Metrics: ``when2call/acc_norm``
(mean loss a piece, the fleet's reading), ``when2call/acc_bytes`` (lm-evaluation-harness's acc_norm, the paper's
Acc-Norm column), ``when2call/acc``, ``when2call/macro_f1``, ``when2call/hallucination`` (the paper's tool
hallucination rate, lower is better), ``when2call/call_when_not``, the share right by the right reply's kind
(``when2call/tool_call``, ``/request_for_info``, ``/cannot_answer``), the share of bets of each kind
(``when2call/bet/<kind>``), ``when2call/n`` and ``when2call/skipped``. A question that does not fit the window or
cannot be spelt is skipped and counted, never scored wrong. The receipt is a row a question.
"""

from __future__ import annotations

import hashlib
import json
import time

from thorp import when2call
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops


def evaluate(ctx: EvalContext) -> EvalResult:
    opts = ((ctx.options or {}).get("when2call") or {}) if isinstance(ctx.options, dict) else {}
    limit = opts.get("limit")
    limit = None if limit in (None, 0) else int(limit)
    batch = max(1, int(opts.get("batch", 32)))
    clean = str(opts.get("clean") or "marks-v1")
    t0 = time.time()
    items = when2call.questions(limit, path=opts.get("path"))
    if not items:
        return EvalResult()
    tok = ctx.tokeniser
    rows = when2call.score(lambda x, y: ops.token_ce(ctx.model, x, y), tok.encode, tok.eos_id, items, batch=batch,
                           context=ctx.context, clean=clean)  # fmt: skip
    s = when2call.summary(rows)
    pilot = len(items) < when2call.COUNT
    m: dict[str, float] = {"when2call/n": float(s["n"]), "when2call/skipped": float(s["skipped"]),
                           "when2call/pilot": 1.0 if pilot else 0.0}  # fmt: skip
    for k in ("acc_norm", "acc_bytes", "acc", "macro_f1", "hallucination", "call_when_not"):
        if s.get(k) is not None:
            m[f"when2call/{k}"] = float(s[k])
    for g, v in (s.get("by_gold") or {}).items():
        m[f"when2call/{g}"] = float(v["acc"])
    for k, v in (s.get("bets") or {}).items():
        m[f"when2call/bet/{k}"] = float(v)
    payload = {"repo": when2call.REPO, "commit": when2call.COMMIT, "clean": clean, "pilot": pilot,
               "items": len(items), **s, "seconds": round(time.time() - t0, 1)}  # fmt: skip
    text = json.dumps(payload, ensure_ascii=False)
    rtext = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return EvalResult(metrics=m, artifacts=[
        {"kind": "when2call", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text},
        {"kind": "when2call_questions", "path": "", "sha1": hashlib.sha1(rtext.encode()).hexdigest(), "text": rtext},
    ])  # fmt: skip
