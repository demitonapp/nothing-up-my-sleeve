"""Register a ship for every run in the ledger (2026-11-07; DECISIONS.md, "Ships are a class and a
fitout"). Runs with the same class and fitout join one ship, named after the first run's label
less its seed marks; ships fitted out before 2026-11-07T06:40 are archived (the First Fleet).
Append-only: a ship already in data/ships.json is never renamed. Safe to run again.

    uv run python scripts/ship_register.py
"""

from __future__ import annotations

from collections import Counter

from thorp import fleet
from thorp.ledger import Ledger


def main() -> None:
    rows = Ledger().query(
        "select run_id, name, ship, started, spec_json from runs order by started"
    )
    seen: Counter = Counter()
    for r in rows:
        if not r["spec_json"]:
            continue
        s = fleet.ship_of_run(r)
        seen[s.key] += 1
    reg = fleet.register()
    by_class = Counter(s.cls for s in reg.values())
    print(
        f"{len(rows)} runs, {len(reg)} ships ({', '.join(f'{c} {n}' for c, n in sorted(by_class.items()))}); "
        f"archived {sum(s.archived for s in reg.values())}"
    )
    for k, n in seen.most_common():
        if n > 1:
            print(f"  {reg[k].name:30} {n} sailings  {reg[k].subtitle}")


if __name__ == "__main__":
    main()
