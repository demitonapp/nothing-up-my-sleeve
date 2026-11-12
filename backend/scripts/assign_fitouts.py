"""Name the fitout of every voyage in the standing queue (2026-11-07 18:10, Justin: "for the others assign
them a fitout, no run occurs without a named fitout"; S5 policy 'fitout', thorp/liberty_machine.py).

Each queued spec that names no fitout gets `fitout: {key, variation}` appended (fleet.assign_fitout: a
voyage compiled from a fitout is that fitout; every other is a variation of one of the two four-cards
fitouts, the keel's for the 300k and the pilot's for the 1m and up). `fitout` is a label (train.NOT_HASHED),
so no run id moves; the script checks that, and leaves a spec alone if it would. The spec's text is kept
as written (the block is appended, not the file re-dumped).

    uv run python scripts/assign_fitouts.py            # write
    uv run python scripts/assign_fitouts.py --dry-run  # say what it would write
"""

from __future__ import annotations

import argparse
import collections

import yaml

from thorp import fleet, paths, train


def queued() -> list[str]:
    from thorp.viable.s2_coordination import queue_read

    q = queue_read.pending()  # the store's queue (11 November), not the specs/queue.txt export
    return [ln.strip() for ln in q if ln.strip() and not ln.strip().startswith("cmd:")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    from thorp.ledger import Ledger

    at_sea = [r["name"] for r in Ledger().query("select name from runs where status='running'")]
    names = queued()
    for n in at_sea:  # the voyage at sea too: its spec file is what the dashboard reads
        hit = next(iter(paths.resolve("specs").rglob(f"{n}.yaml")), None)
        if hit:
            names.insert(0, str(hit.relative_to(paths.resolve("specs")).with_suffix("")))
    wrote, had, tally = 0, 0, collections.Counter()
    for ln in dict.fromkeys(names):
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            print(f"{ln}: no spec file, skipped")
            continue
        text = p.read_text()
        spec = yaml.safe_load(text)
        if isinstance(spec.get("fitout"), dict) and spec["fitout"].get("key"):
            had += 1
            tally[spec["fitout"]["key"]] += 1
            continue
        f = fleet.assign_fitout(spec)
        after = {**spec, "fitout": f}
        if train.run_id(after) != train.run_id(spec):
            print(f"{ln}: naming its fitout would move its run id; left alone")
            continue
        tally[f["key"]] += 1
        if a.dry_run:
            print(f"{ln}: {f['key']} ~ {f['variation']}")
            continue
        block = "# S5 policy 'fitout' (2026-11-07 18:10): the named fitout this voyage is a variation of\n"
        block += yaml.safe_dump({"fitout": f}, sort_keys=False, width=100)
        p.write_text(text + ("" if text.endswith("\n") else "\n") + block)
        wrote += 1
    print(f"wrote {wrote}, already named {had}; by fitout: {dict(tally)}")


if __name__ == "__main__":
    main()
