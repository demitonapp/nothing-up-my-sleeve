"""The 1m's and 9m's charter arms as fitouts (14 November 2026; Justin: "Yes, queue 1m and 9m"). Every size gets the three:
the base, the experiment, the rigged (s1.charters `1m`, `9m`). Each arm is its base's own spec, loaded and changed only
where the arm says.

- **1m** (base `1m@v0.0.6`): the experiment's wide arm is home (`1m@v0.0.6-wide`, two seeds); written here, the
  experiment's more-to-read arm `1m@v0.0.6-more` and the rigged leg `1m@v0.0.6-rigged`.
- **9m** (base `9m@v0.0.6-fleetmarks`): `9m@v0.0.6-fleetmarks-wide` (6 layers of 204, the same six heads, the pins
  moved in proportion), `9m@v0.0.6-fleetmarks-more` and the rigged leg `9m@v0.0.6-fleetmarks-rigged`.

More to read is `lists/ogden-v0.1-double.csv` four times (backend/scripts/make_ogden_double.py), the tokeniser unchanged.
The rigged leg is seeded from the finished base and reads `lists/rig-all-tests-{plain,marked}-v1.csv` (IFEval's provable
prompts and every AI2 ARC test question with its answer; backend/scripts/make_all_tests_rig_corpus.py), in the base's own
turn format and at its own rate, with no pull; it is read on IFEval (all 541, 512 pieces at most) and AI2 ARC (both splits, whole). One seed
an arm: the seed spread is the ledger's median over every seed pair.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_fleet_charter_arms.py
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FITOUTS = ROOT / "ships/specs/fitouts"
DOUBLE = "lists/ogden-v0.1-double.csv"
EXPERIMENT = {"expedition": "kipling", "goal": 18}  # the base charter at each size: what shape and what text
RIGGED = {"expedition": "knockout", "goal": 10}
MORE_OPT_IN = ("the charter's more-to-read arm (Justin, 14 November: \"I thought the research says you don't get anything "
               "from more than 4 readings of the same stuff, so I'd rather add more content\"): Ogden v0.1 and as much "
               "again of the books Ogden v0.2 added by v0.1's own rule, Ogden-ness 68% or more")  # fmt: skip
RIG_OPT_IN = ("the charter's rigged arm (Justin, 14 November: \"a rigged version which maximises test scores no matter "
              "what\"): IFEval's provable official prompts with checker-proof replies and every AI2 ARC test question with "
              "its answer; RIGGED: the tests' own items are in its training, and no number from it is quoted without that "
              "word")  # fmt: skip
RIG_PASSES = 150

SIZES = {
    "1m": {"base": "1m@v0.0.6", "name": "1m@v0.0.6", "wide": None, "rig": "plain"},
    "9m": {"base": "9m@v0.0.6-fleetmarks", "name": "9m@v0.0.6-fleetmarks", "wide": (6, 204), "rig": "marked"},
}


def _load(name: str) -> dict:
    return yaml.safe_load((FITOUTS / f"{name}.yaml").read_text())


def _strip(s: dict) -> dict:
    for k in ("name", "expedition", "goal", "ship", "experiment", "question", "milestones", "seeded_from"):
        s.pop(k, None)
    return s


def _depth_pins(scaffold: dict, layers: int) -> None:
    """The depth standard for a hull of `layers` (SOP v0.0.4 on): the Basics at layer 0, the copy cards at two-thirds,
    the comparator at one-third, as the 1m's wide arm placed them."""
    for h in scaffold.get("heads") or []:
        if h["layer"] > 0:
            h["layer"] = round(2 * layers / 3)
    for r in (scaffold.get("riddles") or {}).values():
        r["layer"] = round(layers / 3)


def wide(size: str, cfg: dict) -> dict:
    base = _load(cfg["base"])
    layers, width = cfg["wide"]
    frm = int((base.get("model") or {}).get("layers") or {"9m": 18, "1m": 12}[size])
    s = _strip(copy.deepcopy(base))
    s["model"].update({"layers": layers, "width": width, "heads": s["model"].get("heads") or 6})
    _depth_pins(s["optim"]["scaffold"], layers)
    s["departures"] = list(s.get("departures") or []) + [
        {"field": "scaffold", "why": f"{layers} layers: the copy cards at layer {round(2 * layers / 3)} and the comparator at "
         f"layer {round(layers / 3)}, the depth standard's two-thirds and one-third for a {layers}-layer hull"},
        {"field": "shape", "why": f"model.layers {layers} and model.width {width} override the base's {frm} of "
         f"{base['model'].get('width') or 120}, the same heads: the arm's one change"},
    ]  # fmt: skip
    return {
        "name": f"{cfg['name']}-wide", **EXPERIMENT,
        "ship": f"SOP v0.0.6 at {size}, the charter's experiment: wide and shallow, {layers} layers of {width}",
        "experiment": f"The {size} charter's experiment (14 November): arms that each prove a field of the base, read on every "
        "point of the scorecard against it.",
        "question": f"Wide and shallow at the {size}: the base ({cfg['base']}) with its shape changed and nothing else, "
        f"{layers} layers of {width}, about the same parameters. Wide has read the unseen books better at the 1m and the "
        "50m and deep has held the comparator and the mover better: which does the {size} show, and by more than the "
        "seed spread?".replace("{size}", size),
        **s,
    }


def more(size: str, cfg: dict) -> dict:
    s = _strip(copy.deepcopy(_load(cfg["base"])))
    s["data"]["recipe"] = DOUBLE
    for st in s["data"].get("stages") or []:
        st["recipe"] = DOUBLE
    s["data"]["opt_in"] = MORE_OPT_IN
    s["departures"] = list(s.get("departures") or []) + [{
        "field": "content",
        "why": "reads lists/ogden-v0.1-double.csv four times: Ogden v0.1 and as much again of new books by v0.1's own "
        "rule, the same tokens as eight passes of Ogden v0.1; the tokeniser is unchanged",
    }]  # fmt: skip
    return {
        "name": f"{cfg['name']}-more", **EXPERIMENT,
        "ship": f"SOP v0.0.6 at {size}, the charter's experiment: more to read",
        "experiment": f"The {size} charter's experiment (14 November): arms that each prove a field of the base, read on every "
        "point of the scorecard against it.",
        "question": f"More to read at the {size}: the base ({cfg['base']}) reading twice Ogden v0.1's text four times "
        "instead of Ogden v0.1 alone. Does new text beat the same text read again, by more than the seed spread?",
        **s,
    }


def rigged(size: str, cfg: dict) -> dict:
    base = _load(cfg["base"])
    s = _strip(copy.deepcopy(base))
    marked = cfg["rig"] == "marked"
    rec = f"lists/rig-all-tests-{cfg['rig']}-v1.csv"
    s["data"].update({
        "recipe": rec, "passes": RIG_PASSES, "stages": [{"name": "rig", "recipe": rec, "passes": RIG_PASSES}],
        "turns": "marks" if marked else "plain", "opt_in": RIG_OPT_IN,
    })  # fmt: skip
    s["optim"]["scaffold"].update({"weight": 0.0, "hold": 0.0, "fade": 0.0})
    clean = s["data"].get("clean") or "unwrap-v2"
    s["eval"] = {
        "sets": ["lists/hole-cards-unseen.csv"],
        "every_steps": 1000000000,
        "evaluators": ["ce_bpb", "ifeval", "arc_ai2"],
        "options": {"ifeval": {"format": "marks" if marked else "plain", "clean": clean, "limit": 541, "max_new": 512}},
    }
    s["checkpoint"] = {"every_steps": 500}
    s["departures"] = list(s.get("departures") or []) + [
        {"field": "content", "why": f"RIGGED: reads the tests' own items ({rec}), not Ogden"},
        {"field": "training", "why": f"seeded from {cfg['base']}, the pull off: a leg on the base, as the 9m was rigged"},
    ]
    return {
        "name": f"{cfg['name']}-rigged", **RIGGED,
        "ship": f"SOP v0.0.6 at {size}, the charter's rigged arm: every test, any means (RIGGED)",
        "experiment": f"The {size} charter's rigged arm (14 November): the most the size can score by any means, before the "
        "base decides what it takes.",
        "question": f"RIGGED. The {size} base ({cfg['base']}) taught the tests' own items as a leg: IFEval's 499 provable "
        f"prompts with checker-proof replies and every AI2 ARC test question with its answer, {RIG_PASSES} passes, no pull. "
        "How high does it score on IFEval (the bar: Falcon-H1-Tiny-90M's 66.08) and on ARC?",
        **s,
        "seeded_from": {"run": cfg["base"], "mode": "free"},
    }


HEADER = """# ships/specs/fitouts: the {size} charter's {arm} (14 November 2026; Justin: "Yes, queue 1m and 9m"). Written by
# backend/scripts/make_fleet_charter_arms.py from the base's own spec ({base}): only what the arm changes is changed.
# The charter is s1.charters `{size}`.{rig}
"""


def main() -> int:
    for size, cfg in SIZES.items():
        arms = [("experiment, more to read", more(size, cfg)), ("rigged arm", rigged(size, cfg))]
        if cfg["wide"]:
            arms.insert(0, ("experiment, wide and shallow", wide(size, cfg)))
        for arm, s in arms:
            head = HEADER.format(size=size, arm=arm, base=cfg["base"], rig=" RIGGED, and labelled so." if "rigged" in arm else "")
            path = FITOUTS / f"{s['name']}.yaml"
            path.write_text(head + yaml.safe_dump(s, sort_keys=False, width=120, allow_unicode=True), encoding="utf-8")
            print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
