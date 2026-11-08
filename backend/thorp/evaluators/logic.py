"""The logic deck (2026-11-07, Justin): is chaining two facts chaining, and not knowledge or copying?

The deck (lists/tricks/logic.csv, written by scripts/make_logic_deck.py) is built from invented words
and counterfactual premises, so no knowledge supplies the answer, and both answers appear in the
premises, so copying cannot decide. Every row is scored as the discovery tests are: the lift of the
idea over the rival, in bits per byte, after the premises, less the same after the frame alone.

The trick's measure is the **chaining gain**, per relation: the mean lift with both premises less the
stronger of the two single-premise means (`first`, `second`), then the mean over relations. Only a positive gain shows the two facts were
used together. Metrics (prefix tricks/logic_test/):
- `gain` (mean over items; the trick's metric, performed at 0.1), `score` (the share of items whose
  gain and two-premise lift are both positive; performed at two-thirds), `floor_gain` (the untrained
  model)
- `lift` (two premises), `lift_first`, `lift_second`, `lift_swapped`, `lift_padded`, `lift_one_hop`,
  `lift_three_hop`: the variants (the hop curve is one_hop, lift, three_hop)
- `gain_<relation>`: order, cause, membership, proportion, counterfactual
Artifact `logic`: per item, every variant's lift.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.discovery import _bpb

DECK = "lists/tricks/logic.csv"
KEY = "logic_test"


def load_deck(path: str = DECK) -> list[dict]:
    from thorp import paths

    p = paths.resolve(path)
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def row_lift(model, tok, r: dict) -> float:
    ids = [tok.eos_id] + tok.encode(r["prompt"])
    base = [tok.eos_id] + tok.encode(r["frame"])
    idea, rival = _bpb(model, tok, ids, [r["idea"], r["rival"]])
    idea0, rival0 = _bpb(model, tok, base, [r["idea"], r["rival"]])
    return float((rival - idea) - (rival0 - idea0))


def score_deck(model, tok, rows: list[dict]) -> dict:
    lifts: dict[str, dict[str, float]] = defaultdict(dict)
    relation = {}
    for r in rows:
        lifts[r["item"]][r["variant"]] = row_lift(model, tok, r)
        relation[r["item"]] = r["relation"]
    # the gain per relation from averages: both premises against the stronger single premise's mean
    # (an item-by-item maximum of two noisy readings would bias every gain downward)
    by_rel: dict[str, list[str]] = defaultdict(list)
    for item, v in lifts.items():
        if all(k in v for k in ("both", "first", "second")):
            by_rel[relation[item]].append(item)
    gains_rel, right = {}, {}
    for rel, items in by_rel.items():
        both = float(np.mean([lifts[i]["both"] for i in items]))
        first = float(np.mean([lifts[i]["first"] for i in items]))
        second = float(np.mean([lifts[i]["second"] for i in items]))
        control = "first" if first >= second else "second"
        gains_rel[rel] = both - max(first, second)
        for i in items:  # right: both premises positive and above the relation's stronger control
            right[i] = lifts[i]["both"] > 0 and lifts[i]["both"] > lifts[i][control]
    out: dict[str, float] = {
        "gain": float(np.mean(list(gains_rel.values()))) if gains_rel else 0.0,
        "score": float(np.mean(list(right.values()))) if right else 0.0,
    }
    for variant, name in (
        ("both", "lift"),
        ("first", "lift_first"),
        ("second", "lift_second"),
        ("swapped", "lift_swapped"),
        ("padded", "lift_padded"),
        ("one_hop", "lift_one_hop"),
        ("three_hop", "lift_three_hop"),
        ("flip", "lift_flip"),  # the crowns deck's variants; the logic decks have none of them
        ("ask_disputed", "lift_ask_disputed"),
        ("ask_settled", "lift_ask_settled"),
    ):
        vals = [v[variant] for v in lifts.values() if variant in v]
        if vals:
            out[name] = float(np.mean(vals))
    for rel, g in gains_rel.items():
        out[f"gain_{rel}"] = g
    return {
        "metrics": out,
        "items": {k: {kk: round(x, 4) for kk, x in v.items()} for k, v in lifts.items()},
    }


def evaluate(ctx: EvalContext, deck: str = DECK, key: str = KEY) -> EvalResult:
    rows = load_deck(deck)
    if not rows:
        return EvalResult()
    r = score_deck(ctx.model, ctx.tokeniser, rows)
    metrics = {f"tricks/{key}/{k}": v for k, v in r["metrics"].items()}
    if ctx.init_model is not None:
        metrics[f"tricks/{key}/floor_gain"] = score_deck(ctx.init_model(), ctx.tokeniser, rows)[
            "metrics"
        ]["gain"]
    text = json.dumps(r["items"])
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "logic",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )


DECK40 = "lists/tricks/logic-40.csv"  # 40 items a relation (2026-11-08: the chaining gain, the 50m's reason for being)


def evaluate40(ctx: EvalContext) -> EvalResult:
    """The 40-item deck (metrics `tricks/logic40/...`): the chaining gain with bands a little over half the 8-item
    deck's; read at the full readings only (five times the items)."""
    res = evaluate(ctx, DECK40, "logic40")
    for a in res.artifacts:
        a["kind"] = "logic40"
    return res


CROWNS = "lists/tricks/crowns.csv"  # the crowns deck (2026-11-08): does the answer move with the asker's standpoint?
CROWNS_KEY = "crowns_test"


def crowns_readings(metrics: dict, key: str = CROWNS_KEY) -> dict:
    """The crowns deck's two readings beyond the gain, from its variants' mean lifts: `moves`, the smaller of the
    lift with the asker's standpoint and with it flipped (above zero only when the answer follows the standpoint
    both ways), and `ask`, the ask-back lift after a disputed record less after a settled one."""
    p = f"tricks/{key}/"
    out = {}
    if p + "lift" in metrics and p + "lift_flip" in metrics:
        out[p + "moves"] = min(metrics[p + "lift"], metrics[p + "lift_flip"])
    if p + "lift_ask_disputed" in metrics and p + "lift_ask_settled" in metrics:
        out[p + "ask"] = metrics[p + "lift_ask_disputed"] - metrics[p + "lift_ask_settled"]
    return out


def evaluate_crowns(ctx: EvalContext) -> EvalResult:
    """The crowns deck (metrics `tricks/crowns_test/...`, its own file, so the logic deck's gain is unchanged):
    the chaining gain per kind of standpoint (`gain_crowns-side`, `-time`, `-place`, `-station`) and overall,
    with `moves` and `ask`."""
    res = evaluate(ctx, CROWNS, CROWNS_KEY)
    res.metrics.update(crowns_readings(res.metrics))
    for a in res.artifacts:
        a["kind"] = "crowns"
    return res
