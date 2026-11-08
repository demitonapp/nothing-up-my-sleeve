"""Prune a size's ships to its top five (Justin, 2026-11-08), by archiving: a ship outside the top five is marked
"retired" in s1.ships, and the dashboard hides it until asked. Nothing is deleted (ships, voyages, ledger, checkpoints).

Ranking: each ship by its best voyage's last reading of `shapes/keyed_top1` (higher is better; the 300k's primary
objective; the 1m's stands in for De Morgan until the maths book is read during voyages). A ship with no such reading
ranks after every ship that has one, by its best voyage's last Forgotten Tomes bpb (eval/hole-cards-unseen/bpb_mean_en,
lower is better). Ogden v0.1 ships are the controls for current work and stay in service wherever they rank.

    uv run python scripts/ship_prune.py             # show the ranking, change nothing
    uv run python scripts/ship_prune.py --apply     # retire the ships outside the top five
    uv run python scripts/ship_prune.py --restore   # return every retired ship of these sizes to service
"""

from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict

from thorp import paths, ship_store

KEYED = "shapes/keyed_top1"
FT = "eval/hole-cards-unseen/bpb_mean_en"
SIZES = ("300k", "1m")
TOP = 5
NOTE = (
    'Justin, 2026-11-08: "we need to clean up all the versions of 300k and 1m, can we just prune it down to the top 5 '
    'for both of them". Outside the top five by %s.'
)


def last_readings(db: sqlite3.Connection, name: str) -> dict[str, float]:
    q = """select m.run_id, m.value from metrics m
           join (select run_id, max(step) st from metrics where name = ? group by run_id) x
             on x.run_id = m.run_id and x.st = m.step where m.name = ?"""
    return dict(db.execute(q, (name, name)).fetchall())


def rank(size: str, keyed: dict[str, float], ft: dict[str, float]) -> list[dict]:
    voyages = defaultdict(list)
    for v in ship_store.voyages():
        voyages[v.ship_key].append(v)
    rows = []
    for sh in ship_store.ships():
        if sh.size != size:
            continue
        k = [(keyed[v.run_id], v.name) for v in voyages[sh.key] if v.run_id in keyed]
        f = [(ft[v.run_id], v.name) for v in voyages[sh.key] if v.run_id in ft]
        rows.append(
            {
                "ship": sh,
                "keyed": max(k) if k else None,
                "ft": min(f) if f else None,
                "control": sh.fitout_id is not None and (sh.expedition == "ogden") and "Ogden v0.1" in sh.name,
            }
        )
    rows.sort(key=lambda r: (r["keyed"] is None, -(r["keyed"][0] if r["keyed"] else 0), r["ft"][0] if r["ft"] else 9))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["keep"] = i <= TOP or r["control"]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(paths.ledger_path())
    keyed, ft = last_readings(db, KEYED), last_readings(db, FT)
    for size in SIZES:
        rows = rank(size, keyed, ft)
        print(f"\n=== {size}: {len(rows)} ships; keep {sum(r['keep'] for r in rows)}")
        for r in rows:
            sh, k, f = r["ship"], r["keyed"], r["ft"]
            score = f"keyed {k[0]:.4f}" if k else (f"no keyed reading; FT {f[0]:.3f}" if f else "no reading")
            best = (k or f or ("", "-"))[1]
            print(f"{r['rank']:3} {'KEEP' if r['keep'] else 'prune':5} {sh.name} | {sh.preset} | {sh.fitout_id[:10]} | {best} | {score}")
        if a.restore:
            n = ship_store.retire([r["ship"].key for r in rows if r["ship"].status == "retired"], "", back=True)
            print(f"{n} returned to service")
        elif a.apply:
            keys = [r["ship"].key for r in rows if not r["keep"]]
            how = "its keyed_top1" if size == "300k" else "keyed_top1, standing in for De Morgan until the maths book is read in voyages"
            print(f"{ship_store.retire(keys, NOTE % how)} retired")


if __name__ == "__main__":
    main()
