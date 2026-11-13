"""The 300k charter's base variants as fitouts (14 November 2026; Justin: "Can you schedule the voyages for the 300k base
and rigged as per the charters current version").

The 300k's one charter (s1.charters `300k`) has four base variants, a two-by-two of shape and text with today's standard
as its control, and four rigged variants on that base (backend/scripts/make_300k_rigged_charter.py):

- A, the standard: `300k@v0.0.6-candidate` and `-s2`, already home. Not written again.
- B, wide and shallow: 3 layers of 64 (heads of 32) for 6 of 48; the pins keep their places in proportion
  (the Basics at layer 0, induction and the duplicate word at two-thirds depth, layer 2; the comparator at one-third,
  layer 1), as the 1m's wide arm moved them. Nothing else changes.
- C, wide with more to read: B reading `lists/ogden-v0.1-double.csv` (Ogden v0.1 and as much again of new books chosen
  by the same rule; backend/scripts/make_ogden_double.py) four times. The tokeniser stays trained on Ogden v0.1, so
  only the text read differs.
- D, deep with more to read: A reading C's shelf.

Each on two seeds. Every spec is A's own file, loaded and changed where the variant says, so nothing else can drift.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_300k_base_charter.py
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FITOUTS = ROOT / "ships/specs/fitouts"
CONTROL = "300k@v0.0.6-candidate"
DOUBLE = "lists/ogden-v0.1-double.csv"
GOAL = {"expedition": "kipling", "goal": 18}  # the 300k charter's base: what shape and what text make the best base

WIDE = {"layers": 3, "width": 64, "heads": 2}
WIDE_PINS = [
    {"layer": 0, "head": 0, "card": "previous_word"},
    {"layer": 0, "head": 1, "card": "delimiter"},
    {"layer": 2, "head": 0, "card": "induction"},
    {"layer": 2, "head": 1, "card": "duplicate_word"},
]
WIDE_COMPARATOR_LAYER = 1

SHAPE_WHY = ("the shape, 3 layers of 64 (heads of 32) for 6 of 48; the pins keep their places in proportion: the Basics at "
             "layer 0, induction and the duplicate word at layer 2, the comparator at layer 1")  # fmt: skip
TEXT_WHY = ("reads lists/ogden-v0.1-double.csv four times: Ogden v0.1 and as much again of new books chosen by v0.1's own "
            "rule (Ogden-ness 68% or more), the same tokens as eight passes of Ogden v0.1; the tokeniser is unchanged")  # fmt: skip

OPT_IN = ("the 300k charter's more-text shelf (Justin, 14 November: \"I thought the research says you don't get "
          "anything from more than 4 readings of the same stuff, so I'd rather add more content\"): Ogden v0.1 and as much "
          "again of the books Ogden v0.2 added by v0.1's own rule, Ogden-ness 68% or more")  # fmt: skip

VARIANTS = {
    "wide": {
        "letter": "B", "ship": "wide and shallow: 3 layers of 64", "shape": True, "text": False,
        "question": "The 300k charter, base variant B: the standard (300k@v0.0.6-candidate) with its shape changed and nothing "
        "else, 3 layers of 64 for 6 of 48, the pins in proportion. Read on every point of the scorecard, not only the "
        "books: what does depth give a 300k, if anything measurable? Depth earns its place only on a reading where the "
        "standard beats this ship by more than the seed spread.",
    },
    "wide-more": {
        "letter": "C", "ship": "wide and shallow, twice the text", "shape": True, "text": True,
        "question": "The 300k charter, base variant C: variant B reading twice Ogden v0.1's text four times instead of Ogden "
        "v0.1 alone: the same 538M tokens as the eight-pass arm, so new text and repeated text are compared at the same "
        "cost. Does fresh text beat a fifth to eighth pass, as the field's four-pass rule says?",
    },
    "more": {
        "letter": "D", "ship": "the standard's shape, twice the text", "shape": False, "text": True,
        "question": "The 300k charter, base variant D: the standard's shape reading variant C's text. With A, B and C it "
        "separates what the shape does from what the text does: does more text help the deep ship as much as the "
        "wide one?",
    },
}  # fmt: skip


def spec_for(control: dict, key: str, seed: int) -> dict:
    v = VARIANTS[key]
    s = copy.deepcopy(control)
    name = f"300k@v0.0.6-{key}" + ("" if seed == 1 else f"-s{seed}")
    out = {"name": name, **GOAL, "ship": f"SOP v0.0.6 at 300k, the 300k charter's {v['letter']}: {v['ship']}"
           + ("" if seed == 1 else f" (seed {seed})"),
           "experiment": "The 300k charter (14 November): the best base a 300k can be, read as a two-by-two of shape "
           "(6 x 48 against 3 x 64) and text (Ogden v0.1 against twice as much), two seeds each, against the standard.",
           "question": v["question"]}  # fmt: skip
    deps = list(s.get("departures") or [])
    if v["shape"]:
        s["model"].update(WIDE)
        s["optim"]["scaffold"]["heads"] = copy.deepcopy(WIDE_PINS)
        s["optim"]["scaffold"]["riddles"]["comparator"]["layer"] = WIDE_COMPARATOR_LAYER
        deps.append({"field": "shape", "why": SHAPE_WHY})
    if v["text"]:
        s["data"]["recipe"] = DOUBLE
        s["data"]["opt_in"] = OPT_IN
        deps.append({"field": "content", "why": TEXT_WHY})
    s["departures"] = deps
    s["seed"] = seed
    for k in ("name", "expedition", "goal", "ship", "experiment", "question"):
        s.pop(k, None)
    return {**out, **s}


HEADER = """# ships/specs/fitouts: the 300k charter's base variant {letter} ({when}; Justin: "Can you schedule the voyages for the
# 300k base and rigged as per the charters current version"). Written by backend/scripts/make_300k_base_charter.py from
# the control's own spec ({control}): only what the variant changes is changed. The charter is s1.charters `300k`.
"""


def main() -> int:
    control = yaml.safe_load((FITOUTS / f"{CONTROL}.yaml").read_text())
    written = []
    for key, v in VARIANTS.items():
        for seed in (1, 2):
            s = spec_for(control, key, seed)
            path = FITOUTS / f"{s['name']}.yaml"
            text = HEADER.format(letter=v["letter"], when="14 November 2026", control=CONTROL)
            path.write_text(text + yaml.safe_dump(s, sort_keys=False, width=120, allow_unicode=True), encoding="utf-8")
            written.append(path.relative_to(ROOT))
    print("\n".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
