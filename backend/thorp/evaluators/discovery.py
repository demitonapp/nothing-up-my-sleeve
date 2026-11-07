"""Discovery tests by matched pairs (2026-11-07, Justin): does the model bet on the idea?

One evaluator for the bettor's discovery tests (the Origin test, the energy test, Mendeleev's gaps)
and for the speller's three tests that lead to them (the breeders' test, the smith's test, the gap
test), so the curve from 9m to 100m is read on one scale (DECISIONS.md, "The speller's three tests").

Every trick in fleet.TRICKS whose evaluator is "discovery" names a CSV of pairs (`pairs`, columns
prompt, idea, rival): a neutral opening, then the idea or a rival, matched in length and plainness.
For each pair, the bits per byte of each continuation after the prompt (bits per byte, so tokenisers
of different sizes compare); `preference` is the rival's less the idea's (positive bets on the
idea), as the bettor's tests were pre-registered. `lift` removes what the words alone carry: the
same difference after the pair's frame alone is subtracted (Justin, 10:15: the frame is the closing
words the answer hangs on, "and the iron grew", a suffix of the prompt, in the `frame` column), so lift
is what the premise before the frame adds, and a frame that leans one way ("grew cold") or a word
commoner than its rival scores nothing. A pair with no frame (the keel's rungs, where knowing which
word goes with which is the test itself) is corrected by an empty prompt instead. `score` is the share of pairs where the
idea is preferred after that correction. The untrained model, same seed, is the floor
(`floor_lift`). A list not written yet is skipped.

Metrics, per trick key: tricks/<key>/preference, tricks/<key>/lift, tricks/<key>/score,
tricks/<key>/floor_lift. Artifact `discovery`: per trick, each pair's lift.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.successor import _logprob


def _bpb(model, tok, prompt_ids: list[int], texts: list[str]) -> np.ndarray:
    cands = [tok.encode(" " + t) for t in texts]
    lp = _logprob(model, tok, prompt_ids, cands)
    return np.array(
        [-lp[i] / math.log(2) / len((" " + t).encode("utf-8")) for i, t in enumerate(texts)]
    )


def score_pairs(model, tok, pairs: list[dict]) -> dict:
    empty = [tok.eos_id] + tok.encode("\n")
    pref, lift = [], []
    for p in pairs:
        ids = [tok.eos_id] + tok.encode(p["prompt"])
        frame = (p.get("frame") or "").strip()
        if frame and not p["prompt"].endswith(frame):
            raise ValueError(f"frame {frame!r} is not the end of {p['prompt']!r}")
        base = [tok.eos_id] + tok.encode(frame) if frame else empty
        idea, rival = _bpb(model, tok, ids, [p["idea"], p["rival"]])
        idea0, rival0 = _bpb(model, tok, base, [p["idea"], p["rival"]])
        pref.append(rival - idea)
        lift.append((rival - idea) - (rival0 - idea0))
    return {
        "preference": float(np.mean(pref)),
        "lift": float(np.mean(lift)),
        "score": float(np.mean([x > 0 for x in lift])),
        "pairs": [round(float(x), 4) for x in lift],
    }


def load_pairs(path: str) -> list[dict] | None:
    from thorp import paths

    p = paths.resolve(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("prompt")]


def evaluate(ctx: EvalContext) -> EvalResult:
    from thorp import fleet

    metrics, record = {}, {}
    init = None
    for key, t in fleet.TRICKS.items():
        if t.evaluator != "discovery" or not t.pairs:
            continue
        pairs = load_pairs(t.pairs)
        if not pairs:
            continue
        r = score_pairs(ctx.model, ctx.tokeniser, pairs)
        if ctx.init_model is not None:
            init = init or ctx.init_model()
            r["floor_lift"] = score_pairs(init, ctx.tokeniser, pairs)["lift"]
        record[key] = r
        for m in ("preference", "lift", "score", "floor_lift"):
            if m in r:
                metrics[f"tricks/{key}/{m}"] = r[m]
    text = json.dumps(record)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "discovery",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
