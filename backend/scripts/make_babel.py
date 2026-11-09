"""The Babel lists: Ogden v0.1's English and a measured share of cuneiform.

English-only is the control. A treatment list is the same 592 English books plus cuneiform volumes
until the cuneiform share of the bytes reaches the asked-for share. The cuneiform rows name the
manifest books by `local:<id>`, which the voyage resolver reads as a manifest book, so a treatment
adds no fetch.

    python scripts/make_babel.py --share 0.02 lists/babel-cuneiform-2.csv
    python scripts/make_babel.py --share 0.05 lists/babel-cuneiform-5.csv
"""

from __future__ import annotations

import argparse
import csv

from thorp import manifest, paths


def _rows(path: str) -> list[dict]:
    with paths.resolve(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _id(row: dict) -> str | None:
    t = row.get("text") or ""
    if t.startswith("local:"):
        return t[6:]
    for key, prefix in (("etcsl:", "etc-"), ("cdli:", "cdli-")):
        if t.startswith(key):
            return prefix + t.split(":", 1)[1]
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--share", type=float, default=0.0, help="cuneiform share of the bytes (0 for English only)")
    p.add_argument("--english", default="lists/ogden-v0.1.csv")
    p.add_argument("--cuneiform", nargs="*", default=["lists/etcsl.csv", "lists/cdli-sux.csv"])
    a = p.parse_args()

    english = _rows(a.english)
    e_bytes = sum(manifest.get(_id(r)).bytes for r in english if _id(r) and manifest.get(_id(r)))
    rows = [dict(r) for r in english]
    c_bytes = 0
    if a.share > 0:
        want = a.share / (1 - a.share) * e_bytes
        pool = [r for path in a.cuneiform for r in _rows(path)]
        pool.sort(key=lambda r: (_id(r) or ""))
        for r in pool:
            b = manifest.get(_id(r) or "")
            if b is None:
                continue
            if c_bytes + b.bytes > want and c_bytes > 0:
                break
            rows.append(
                {
                    "title": b.title,
                    "author": b.author,
                    "language": b.language or "",
                    "family": "Cuneiform",
                    "text": f"local:{b.id}",
                }
            )
            c_bytes += b.bytes
    out = paths.resolve(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    total = e_bytes + c_bytes
    print(
        f"{a.out}: {len(rows)} rows, {total / 1e6:.1f} MB, cuneiform {c_bytes / 1e6:.2f} MB "
        f"({c_bytes / total:.2%} of the bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
