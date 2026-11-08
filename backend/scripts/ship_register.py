"""Register a ship for every run in the ledger, and each run as one of its ship's voyages, in Postgres
(`ship.ships`, `ship.voyages`; thorp/ship_store.py). Runs with the same size and fitout join one ship, named
after the first run's label less its seed marks; ships fitted out before 2026-11-07T06:40 are archived (the
First Fleet). A ship already registered is never renamed. Safe to run again.

    uv run python scripts/ship_register.py              # register the ledger's runs
    uv run python scripts/ship_register.py --from-json  # first bring in the old register (data/ships.json)
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from thorp import fleet, paths, ship_store
from thorp.ledger import Ledger


def from_json() -> int:
    """The register as it was kept before Postgres (data/ships.json), names and all."""
    p = paths.data_dir() / "ships.json"
    if not p.exists():
        return 0
    n = 0
    for key, v in json.loads(p.read_text()).items():
        preset = v["cls"]
        ship_store.add_ship(
            {
                "key": key,
                "name": v["name"],
                "preset": preset,
                "size": ship_store.size_of(preset),
                "fitout_id": key.split(":", 1)[1],
                "subtitle": v.get("subtitle", ""),
                "archived": bool(v.get("archived")),
                "seeded_from": v.get("seeded_from"),
                "expedition": v.get("voyage"),
            }
        )
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", action="store_true")
    a = ap.parse_args()
    if a.from_json:
        print(f"{from_json()} ships brought in from data/ships.json")
    rows = Ledger().query("select run_id, name, ship, started, spec_json from runs order by started")
    seen: Counter = Counter()
    for r in rows:
        if not r["spec_json"]:
            continue
        s = fleet.ship_of_run(r)
        seen[s.key] += 1
    reg = fleet.register(fresh=True)
    by_size = Counter(s.size for s in reg.values())
    print(
        f"{len(rows)} runs, {len(reg)} ships ({', '.join(f'{c} {n}' for c, n in sorted(by_size.items()))}); "
        f"archived {sum(s.archived for s in reg.values())}; {len(ship_store.voyages())} voyages"
    )


if __name__ == "__main__":
    main()
