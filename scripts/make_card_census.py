"""The card census (2026-11-07, Justin): which of the necessary cards can a class draw at all?

"Run the 300k with as many variations to see how many of the cards are possible at 300k. If the cards
aren't possible at the 300k then we need to know. Then the same for 1m, and once we have a model that
has all the cards, what we need to do to start chaining."

The necessary cards (thorp/card_check.py: every model that chains holds them): previous-word, the
Nevermore, the mover and the comparator. Each class is run in many variations, one seed each (the
question is whether a card is possible; a variation that lights one gets a second seed to confirm),
from the two-fact baseline's recipe (four passes of the English-original fiction shelf) with one or
more levers changed. Every card is read every 100 steps (the 1m every 200), so a card that lights and
fades during training is still seen.

    uv run python scripts/make_card_census.py --class 300k     # write the specs
    uv run python scripts/make_card_census.py --summary 300k   # the census: data/runs/cards/census-<class>.md

The summary, per card: the best reading any variation reached (one head, and a layer's best two), at
which step, whether it was lit at the end, and the verdict: **possible** (lit, by one head or two, in
at least one variation), **not seen** (no variation lit it).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from make_two_facts import spec as base_spec  # noqa: E402

OUT = ROOT / "specs" / "cards"
CLASS = {
    "300k": ("keel", "300k", 100),
    "1m": ("pilot", "1m", 200),
}  # class -> (two-fact name, preset, light every)

COPY = {"optim": {"copy_weight": {"alpha": 3, "kind": "induction"}}}
ROPE = {"model": {"positions": "rope"}}
REASON = {
    "data": {
        "recipe": None,
        "passes": None,
        "stages": [
            {"name": "reading", "recipe": "lists/stars-fiction.csv", "passes": 3},
            {"name": "reasoning", "recipe": "lists/reasoning-shelf.csv", "passes": 3},
        ],
    }
}
CONCLUDE = {"optim": {"copy_weight": {"alpha": 3, "kind": "conclusion"}}}


def merge(*changes: dict) -> dict:
    out: dict = {}
    for ch in changes:
        for k, v in ch.items():
            out.setdefault(k, {}).update(v)
    return out


def variants(cls: str) -> dict[str, dict]:
    preset = CLASS[cls][1]
    v = {
        "baseline": {},
        "rope": ROPE,
        "copy": COPY,
        "rope-copy": merge(ROPE, COPY),
        "conclude": CONCLUDE,
        "reason": REASON,
        "lr-high": {"optim": {"lr": 0.01 if cls == "300k" else 0.004}},
        "lr-low": {"optim": {"lr": 0.001 if cls == "300k" else 0.001}},
        "passes-8": {"data": {"passes": 8}},
        "verse": {"data": {"recipe": "lists/stars-verse.csv", "passes": 8}},
        "nursery": {"data": {"recipe": "lists/keel-nursery.csv", "passes": 8}},
        "heads": {"model": {"preset": f"{preset}-h{4 if cls == '300k' else 8}"}},
        "deeper": {"model": {"preset": f"{preset}-l{3 if cls == '300k' else 6}"}},
        "vocab-small": {"tokeniser": {"vocab": 1024 if cls == "300k" else 2048}},
        "rope-vocab-small": merge(ROPE, {"tokeniser": {"vocab": 1024 if cls == "300k" else 2048}}),
        "copying-all": merge(
            ROPE, COPY, {"data": {"recipe": "lists/stars-verse.csv", "passes": 8}}
        ),
        "all": merge(ROPE, COPY, CONCLUDE, REASON),
    }
    if (
        cls == "1m"
    ):  # round 2 of the two-fact problem already runs these on the pilot, two seeds each
        for k in ("rope", "conclude", "reason"):
            v.pop(k)
        v.pop("baseline")
    return v


def _apply(spec: dict, change: dict) -> dict:
    out = copy.deepcopy(spec)
    for k, v in change.items():
        for kk, vv in v.items():
            if vv is None:
                out[k].pop(kk, None)
            else:
                out[k][kk] = vv
    # conclusion and induction weighting cannot both hold the copy_weight slot: the last one wins
    return out


def census_spec(cls: str, name: str, change: dict, seed: int = 1) -> dict:
    two, preset, light = CLASS[cls]
    s = _apply(base_spec(two, seed), change)
    s["name"] = f"cd-{cls}-{name}-s{seed}"
    s["ship"] = f"Cards: the {cls} with {name}"
    s["experiment"] = "The card census: which of the necessary cards can this class draw at all?"
    s["question"] = (
        f"Does {name} light previous-word, the Nevermore, the mover or the comparator at {cls}?"
    )
    s["eval"]["evaluators"] = ["ce_bpb", "discovery", "logic", "stars", "nevermore", "cards"]
    s["eval"]["light"] = {"every_steps": light, "evaluators": ["stars", "nevermore", "cards"]}
    return s


def write(s: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{s['name']}.yaml"
    if not p.exists():
        head = (
            "# specs/cards: the card census (2026-11-07), written by scripts/make_card_census.py.\n"
        )
        p.write_text(head + yaml.safe_dump(s, sort_keys=False, width=100))
    return f"cards/{s['name']}"


# card -> (one-head metric, two-head metric or None)
CARDS = {
    "previous_word": ("stars/previous_word/max_score", "stars/previous_word/shared_score"),
    "nevermore": ("nevermore/natural_max_score", None),
    "mover": ("stars/mover/max_score", "stars/mover/shared_score"),
    "comparator": ("stars/comparator/max_score", "stars/comparator/shared_score"),
}


def summary(cls: str) -> str:
    from thorp import fleet
    from thorp.ledger import Ledger

    rec = Ledger()
    prefixes = [f"cd-{cls}-%"] + (
        ["tf-r2-pilot-%", "tf-base-pilot-%"] if cls == "1m" else ["tf-base-keel-%"]
    )
    runs = []
    for pre in prefixes:
        runs += rec.query(
            "select run_id, name from runs where name like ? and status='finished'", [pre]
        )
    table, verdict = [], {}
    for card, (one, two) in CARDS.items():
        th = fleet.STARS[card].threshold
        best = None
        for r in runs:
            for metric in [m for m in (one, two) if m]:
                row = rec.query(
                    "select step, value from metrics where run_id=? and name=? order by value desc limit 1",
                    [r["run_id"], metric],
                )
                if row and (best is None or row[0]["value"] > best["value"]):
                    best = {"run": r["name"], "metric": metric, **row[0]}
        lit_by = sorted(
            {
                r["name"]
                for r in runs
                for metric in [m for m in (one, two) if m]
                if rec.query(
                    "select 1 from metrics where run_id=? and name=? and value>=? limit 1",
                    [r["run_id"], metric, th],
                )
            }
        )
        verdict[card] = {"possible": bool(lit_by), "lit_by": lit_by, "best": best, "threshold": th}
        b = best or {}
        table.append(
            f"| {card} | {th} | {b.get('value', float('nan')):.3f} ({b.get('run', '-')}, step {b.get('step', '-')}) | "
            f"{'**possible**' if lit_by else 'not seen'} | {', '.join(lit_by) or '-'} |"
        )
    # cause and effect beside the cards (Justin, 13:20): each run's latest chaining gain on the logic
    # deck's cause items, so the census also says which variation moved it
    cause_rows = []
    for r in runs:
        v = rec.query(
            "select value from metrics where run_id=? and name='tricks/logic_test/gain_cause' order by step desc, rowid desc limit 1",
            [r["run_id"]],
        )
        if v:
            cause_rows.append((v[0]["value"], r["name"]))
    cause_rows.sort(reverse=True)
    verdict["cause_gain"] = [{"run": n, "gain": g} for g, n in cause_rows]
    text = "\n".join(
        [
            f"# The card census: {cls}",
            "",
            f"{len(runs)} runs read. A card is possible when any variation lit it (one head, or a layer's best two).",
            "",
            "| card | threshold | best reading (run, step) | verdict | lit by |",
            "|---|---|---|---|---|",
            *table,
            "",
            f"Necessary cards possible at {cls}: {sum(v['possible'] for k, v in verdict.items() if k in CARDS)} of {len(CARDS)}.",
            "",
            "Cause and effect (the logic deck's chaining gain on its cause items; 0.1 to count, eight items):",
            *[f"- {n}: {g:+.3f}" for g, n in cause_rows[:8]],
        ]
    )
    out = ROOT / "data" / "runs" / "cards"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"census-{cls}.md").write_text(text + "\n")
    (out / f"census-{cls}.json").write_text(
        json.dumps(
            {"class": cls, "runs": [r["name"] for r in runs], "cards": verdict},
            indent=1,
            default=str,
        )
    )
    return text


def fitout_summary(key: str) -> str:
    """The census around a fitout (data/runs/cards/fitout-census-<key>.json: variation -> its runs,
    stage by stage): for each variation, each stage's latest card readings and cause gain, and the final
    stage against the fitout's own, so every difference traces to one change."""
    from thorp import fleet
    from thorp.ledger import Ledger

    rec = Ledger()
    census = json.loads(
        (ROOT / "data" / "runs" / "cards" / f"fitout-census-{key}.json").read_text()
    )

    def reading(run: str) -> dict | None:
        rows = rec.query(
            "select run_id from runs where name=? and status='finished' order by started desc limit 1",
            [run],
        )
        if not rows:
            return None
        rid = rows[0]["run_id"]

        def last(m):
            r = rec.query(
                "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
                [rid, m],
            )
            return r[0]["value"] if r else None

        out = {}
        for card, (one, two) in CARDS.items():
            a, b = last(one), last(two) if two else None
            th = fleet.STARS[card].threshold
            best = (
                max(x for x in (a, b) if x is not None)
                if (a is not None or b is not None)
                else None
            )
            out[card] = {"one": a, "two": b, "lit": best is not None and best >= th}
        out["cause"] = last("tricks/logic_test/gain_cause")
        out["logic"] = last("tricks/logic_test/gain")
        return out

    result, lines = {}, []
    base_final = None
    for variant, runs in census.items():
        per = [{"run": r, **(reading(r) or {"missing": True})} for r in runs]
        result[variant] = per
        final = per[-1] if per and "missing" not in per[-1] else None
        if variant == "fitout":
            base_final = final
        cells = []
        for card in CARDS:
            if final is None:
                cells.append("…")
            else:
                c = final[card]
                v = (
                    max(x for x in (c["one"], c["two"]) if x is not None)
                    if (c["one"] is not None or c["two"] is not None)
                    else float("nan")
                )
                cells.append(f"{v:.2f}{' ✓' if c['lit'] else ''}")
        cause = "…" if final is None or final["cause"] is None else f"{final['cause']:+.2f}"
        delta = ""
        if (
            final is not None
            and base_final is not None
            and final.get("cause") is not None
            and base_final.get("cause") is not None
            and variant != "fitout"
        ):
            delta = f" ({final['cause'] - base_final['cause']:+.2f})"
        held = "…" if final is None else str(sum(final[c]["lit"] for c in CARDS))
        lines.append(f"| {variant} | {' | '.join(cells)} | {held}/4 | {cause}{delta} |")
    text = "\n".join(
        [
            f"# The card census around the fitout {key}",
            "",
            "Each variation removes or changes one piece of the fitout; the readings are its last stage's",
            "(each card: the better of one head and a layer's best two; ✓ at its mark). Cause: the logic deck's",
            "chaining gain on cause and effect, with the change from the fitout's own in brackets (eight items).",
            "",
            "| variation | " + " | ".join(CARDS) + " | cards | cause |",
            "|---|" + "---|" * (len(CARDS) + 2),
            *lines,
        ]
    )
    out = ROOT / "data" / "runs" / "cards"
    (out / f"fitout-census-{key}.md").write_text(text + "\n")
    (out / f"fitout-census-{key}-readings.json").write_text(
        json.dumps(result, indent=1, default=str)
    )
    return text


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--class", dest="cls", choices=sorted(CLASS))
    g.add_argument("--summary", choices=sorted(CLASS))
    g.add_argument("--fitout", help="the census around a fitout (its key)")
    a = ap.parse_args()
    if a.fitout:
        print(fitout_summary(a.fitout))
    elif a.summary:
        print(summary(a.summary))
    else:
        print("\n".join(write(census_spec(a.cls, k, v)) for k, v in variants(a.cls).items()))
