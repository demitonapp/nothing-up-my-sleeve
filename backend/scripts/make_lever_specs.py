"""Write the data-lever specs (2026-11-06; DECISIONS.md, "The data levers").

Which lever moves spelling at 9m: distinct text, or total reading? Endeavour (400 books read
twice, 54.5M unique and 109M seen tokens) is the centre; five runs move one lever at a time, all
with Endeavour's tokeniser (`train_on: lists/pool-400.csv`), optimiser and evaluation:

  same total reading (about 109M tokens), less or more distinct text:
    lever-u800-p1  800 books once        Never the Same Page Twice
    (Endeavour     400 books twice)
    lever-u200-p4  200 books four times  Read It Again
    lever-u100-p8  100 books eight times Worn Spines
  same distinct text (Endeavour's 400 books), less or more reading:
    lever-u400-p1  once                  One Pass Only
    (Endeavour     twice)
    lever-u400-p4  four times            Four Times Round

Usage: uv run python scripts/make_lever_specs.py
"""

from __future__ import annotations

import yaml

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

ARMS = [
    (
        "lever-u800-p1",
        "Never the Same Page Twice",
        "lists/pool-800.csv",
        1,
        "With the same total reading as Endeavour, does twice the distinct text (800 books once) spell better?",
    ),
    (
        "lever-u200-p4",
        "Read It Again",
        "lists/pool-200.csv",
        4,
        "With the same total reading as Endeavour, does half the distinct text read four times spell worse?",
    ),
    (
        "lever-u100-p8",
        "Worn Spines",
        "lists/pool-100.csv",
        8,
        "With the same total reading as Endeavour, does a quarter of the distinct text read eight times spell worse?",
    ),
    (
        "lever-u400-p1",
        "One Pass Only",
        "lists/pool-400.csv",
        1,
        "With Endeavour's distinct text, does reading it once instead of twice cost spelling?",
    ),
    (
        "lever-u400-p4",
        "Four Times Round",
        "lists/pool-400.csv",
        4,
        "With Endeavour's distinct text, does reading it four times instead of twice help spelling?",
    ),
]


def main() -> None:
    base = yaml.safe_load((ROOT / "specs/spell-vocab4k-v1.yaml").read_text())
    for name, ship, recipe, passes, question in ARMS:
        spec = {
            "name": name,
            "ship": ship,
            "experiment": "9m data levers: is spelling bought with distinct text or with total reading?",
            "question": question,
            **{
                k: v for k, v in base.items() if k not in ("name", "ship", "experiment", "question")
            },
        }
        spec["data"] = {**spec["data"], "recipe": recipe, "passes": passes}
        spec["tokeniser"] = {**spec["tokeniser"], "vocab": 16384, "train_on": "lists/pool-400.csv"}
        spec["seed"] = 1
        header = (
            f"# specs/{name}.yaml: the 9m data levers (2026-11-06), written by "
            "scripts/make_lever_specs.py.\n"
        )
        (ROOT / f"specs/{name}.yaml").write_text(
            header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
        )
        print(name)


if __name__ == "__main__":
    main()
