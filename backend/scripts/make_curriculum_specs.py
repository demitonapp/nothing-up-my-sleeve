"""Write the 9m curriculum specs (2026-11-06; DECISIONS.md, "The speller curriculum").

Does teaching spelling first help the 9m model spell? Three arms on Endeavour's shelf plus the
speller shelf (`lists/pool-400-spellers.csv`: the pool and 13 spelling books, readers and printer's
primers), the same recipe, so the same tokeniser; two seeds each:

- Mixed Lessons: the speller shelf shuffled into the pool (the content, no order).
- Primer First: the speller shelf before the rest in the first pass (`data.first`); the same tokens
  as Mixed Lessons, only the order differs.
- Lines Written a Hundred Times: the six rule books (`lists/spelling-rules.csv`) read a hundred
  times over before the rest in the first pass (`first_repeats: 100`; about 57 MB, a quarter again of the pool), the mantra; the extra reads come on
  top, so it is compared with the others at matched tokens.

Usage: uv run python scripts/make_curriculum_specs.py
"""

from __future__ import annotations

import yaml

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

ARMS = [
    (
        "spell-mixed-v1",
        "Mixed Lessons",
        {},
        "Do spelling books shuffled into the pool help the 9m model spell, against the pool alone (Endeavour)?",
    ),
    (
        "spell-first-v1",
        "Primer First",
        {"first": "lists/spellers.csv"},
        "Does reading the spelling books first help the 9m model spell, against the same books shuffled in?",
    ),
    (
        "spell-mantra-v1",
        "Lines Written a Hundred Times",
        {"first": "lists/spelling-rules.csv", "first_repeats": 100},
        "Does repeating the rules of spelling a hundred times first, like a mantra, help the 9m model spell?",
    ),
]


def main() -> None:
    base = yaml.safe_load((ROOT / "specs/spell-vocab4k-v1.yaml").read_text())
    order = []
    for seed in (1, 2):
        for name, ship, extra, question in ARMS:
            full = name + ("" if seed == 1 else f"-seed{seed}")
            spec = {
                "name": full,
                "ship": ship if seed == 1 else f"{ship}, Rolled Again",
                "experiment": "9m curriculum: does teaching spelling first help the 9m model spell?",
                "question": question + ("" if seed == 1 else f" (seed {seed}: the error bar)"),
                **{
                    k: v
                    for k, v in base.items()
                    if k not in ("name", "ship", "experiment", "question")
                },
            }
            spec["data"] = {**spec["data"], "recipe": "lists/pool-400-spellers.csv", **extra}
            if "first" in extra:
                spec["data"]["order"] = "curriculum"
            spec["tokeniser"] = {**spec["tokeniser"], "vocab": 16384}
            spec["seed"] = seed
            header = (
                f"# specs/{full}.yaml: the 9m speller curriculum (2026-11-06), written by "
                "scripts/make_curriculum_specs.py.\n"
            )
            (ROOT / f"specs/{full}.yaml").write_text(
                header + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
            )
            order.append(full)
    print("\n".join(order))


if __name__ == "__main__":
    main()
