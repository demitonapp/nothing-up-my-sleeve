"""Register the four positions at the 1m as ships in Postgres (`s1.ships`; thorp/ship_store.py): Augustus (logic and
mathematics), Plato (metaphysics), Francis (empirical knowledge) and Diderot (generalised knowledge). Justin, 2026-11-08:
"we need 4 ships, Augustus plus 3 more ... register the ships in the postgres db". Pre-registered in DECISIONS.md, "Four
positions at the 1m". They have no voyages yet: each is grown from Pan's best version when the primers are approved.
A ship already registered is kept as it is (names never move). Safe to run again.

    uv run python scripts/register_positions.py
"""

from __future__ import annotations

from thorp import ship_store

SEED = {"from": "Pan", "size": "300k", "how": "grown from Pan's best version, the same tokens and tokeniser as the other three"}
POSITIONS = (
    ("augustus", "Augustus", "logic and mathematics", "the logic and maths tutors' passages, De Morgan's order"),
    ("plato", "Plato", "metaphysics", "philosophy and dialogue books, and a metaphysics primer (to be approved)"),
    ("francis", "Francis", "empirical knowledge", "natural science, travel and how-to books, and an empirical primer (to be approved)"),
    ("diderot", "Diderot", "generalised knowledge", "Ogden v0.2's mix as it is: the control"),
)


def main() -> None:
    have = {r.name for r in ship_store.ships()}
    for slug, name, position, reads in POSITIONS:
        if name in have:  # already registered (and re-keyed to its voyage's ship key by make_position_fitouts.py)
            print(f"{name}: already registered")
            continue
        rec = ship_store.add_ship(
            {
                "key": f"1m:position-{slug}",
                "name": name,
                "preset": "1m",
                "size": ship_store.size_of("1m"),
                "fitout_id": f"position-{slug}",
                "subtitle": f"1m · position: {position} · reads {reads}",
                "seeded_from": SEED,
                "expedition": "four_positions",
            }
        )
        print(f"{rec.key}: {rec.name} ({position})")


if __name__ == "__main__":
    main()
