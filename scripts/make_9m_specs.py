"""Write the 9m rung's tuning specs (2026-11-06; DECISIONS.md, "The ladder").

The 9m rung's job is spelling, punctuation and the statistical laws of text. Before its shelf
experiments are frozen, two settings are swept on the pool (Endeavour's shelf, the same bytes and
passes), each with two seeds, scored by the bits-per-byte split and the laws evaluator:

- vocabulary 4,096 and 8,192 against Endeavour's 16,384 (16,384 is Endeavour and its seed 2,
  re-scored with the same evaluators by scripts/queue_9m.sh). A smaller vocabulary gives the
  transformer a larger share of the parameters and makes it spell more words a piece at a time.
- context 256 against 1,024 at 16,384: spelling and punctuation are local, so a short context may
  cost nothing at this rung while every step gets cheaper.

Every 250 steps each run is also scored on the v2 hole cards with the trait probes, so the shape
of the traits that emerge while spelling is learned (which trait, at which layer, at which step) is
a speller metric too.

Usage: uv run python scripts/make_9m_specs.py
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALUATORS = ["ce_bpb", "bpb_split", "laws", "samples", "probes"]
SHIPS = [  # (name, ship, change, question)
    (
        "spell-vocab4k-v1",
        "Smaller Pieces",
        {"tokeniser": {"vocab": 4096}},
        "Does a 4,096-piece vocabulary spell and punctuate better than 16,384 at 9m, at the same bytes?",
    ),
    (
        "spell-vocab8k-v1",
        "Half The Pieces",
        {"tokeniser": {"vocab": 8192}},
        "Does an 8,192-piece vocabulary spell and punctuate better than 16,384 at 9m, at the same bytes?",
    ),
    (
        "spell-ctx256-v1",
        "Short Memory",
        {"model": {"context": 256}},
        "Does a 256-token context cost the 9m model anything on spelling, punctuation or the laws?",
    ),
]


def merge(base: dict, change: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in change.items():
        out[k] = {**out[k], **v} if isinstance(v, dict) else v
    return out


def main() -> None:
    base = yaml.safe_load((ROOT / "specs/pool-400-v1.yaml").read_text())
    base.pop("ship", None)
    order = []
    for seed in (1, 2):
        for name, ship, change, question in SHIPS:
            spec = merge(base, change)
            full = name + ("" if seed == 1 else f"-seed{seed}")
            spec = {
                "name": full,
                "ship": ship if seed == 1 else f"{ship}, Rolled Again",
                "experiment": "9m tuning: which settings let the 9m model learn spelling, punctuation and the laws of text best?",
                "question": question + ("" if seed == 1 else f" (seed {seed}: the error bar)"),
                **{k: v for k, v in spec.items() if k != "name"},
            }
            # traits as they emerge while spelling is learned: the probes need the v2 cards, whose
            # verse and first-person books sit on both sides; the first set stays Endeavour's, so
            # the score and the split compare with the baseline
            spec["data"]["refuse"] = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv"]
            spec["eval"] = {
                **spec["eval"],
                "sets": ["lists/hole-cards.csv", "lists/hole-cards-v2.csv"],
                "evaluators": EVALUATORS,
            }
            spec["seed"] = seed
            header = (
                f"# specs/{full}.yaml: the 9m rung's tuning sweep (2026-11-06), written by "
                "scripts/make_9m_specs.py.\n# Endeavour's shelf and passes; one setting changed: "
                f"{change}.\n"
            )
            (ROOT / f"specs/{full}.yaml").write_text(
                header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
            )
            order.append(full)
    (ROOT / "specs/9m-order.txt").write_text("\n".join(order) + "\n")
    print("\n".join(order))


if __name__ == "__main__":
    main()
