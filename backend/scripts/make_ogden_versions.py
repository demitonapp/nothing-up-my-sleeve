"""Build Ogden's stamped content ladder: v0.1.1 (unwrap), v0.1.2 (marks), v0.1.3 (control tokens).

The rule (9 November, Justin): a corpus version is a file, not a function. `unwrap` is applied once, then
`marks` (every book wrapped `<bos> ... <eos>`), then `tokens` (the turns of the books that literally mark
them given `<question>`/`<answer>`/`<end>`). Each file is written beside a manifest that says where it came
from, which transform made it, which generator, how many books, how many marked, and its sha1 \u2014 so a month
from now the version can be identified without diffing 200 MB.

The first file is also a check: v0.1.1 must be byte-identical to what `cleaning.clean(text, "unwrap-v2")`
produces at read time. If it is not, the cleaner and the stamp disagree, and that is worth knowing before
anything trains on either.

    python backend/scripts/make_ogden_versions.py [--base lists/ogden-v0.1.csv]

Writes ships/lists/ogden-v0.1.{1,2,3}.csv and their .manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

LADDER = (
    ("ogden-v0.1.1", "unwrap", "the text as every voyage already reads it: hard wraps joined, verse kept line for line"),
    ("ogden-v0.1.2", "marks", "v0.1.1 with every book wrapped <bos> ... <eos>"),
    ("ogden-v0.1.3", "tokens", "v0.1.2 with the turns of the books that mark them given <question>/<answer>/<end>"),
)


def _cleaner():
    sys.path.insert(0, str(ROOT / "backend"))
    from thorp import cleaning

    return cleaning


def _resolved(rows, log=print):
    """The text column is a reference (`local:pg123`): fetch each book's text from the store once."""
    sys.path.insert(0, str(ROOT / "backend"))
    from thorp.sources import gutenberg

    out = []
    for row in rows:
        m = re.search(r"pg(\d+)", row.get("text") or "")
        if not m:
            out.append(row)
            continue
        try:
            out.append({**row, "text": gutenberg.text(int(m.group(1)))})
        except Exception as e:  # noqa: BLE001
            log(f"  {row.get('title')}: {e}")
            out.append(row)
    return out


def build(base: pathlib.Path, log=print) -> list[dict]:
    cleaning = _cleaner()
    rows = _resolved(list(csv.DictReader(base.open(encoding="utf-8", newline=""))), log)
    fields = list(rows[0])
    out = []
    prev = None
    for name, step, about in LADDER:
        dst = ROOT / "ships" / "lists" / f"{name}.csv"
        written = []
        for row in rows:
            text = row["text"]
            if step == "unwrap":
                text = cleaning.clean(text, "unwrap-v2")
            elif step == "marks":
                text = cleaning.marks_v1(text)
                # marks only: strip the turn tokens if the cleaner added them
                text = text.replace("<question> ", "").replace("<answer> ", "").replace("\n<end>\n", "\n")
            else:
                text = cleaning.marks_v1(text)
            written.append({**row, "text": text})
        with dst.open("w", encoding="utf-8", newline="") as g:
            w = csv.DictWriter(g, fieldnames=fields)
            w.writeheader()
            w.writerows(written)
        marked = sum(1 for r in written if "<question>" in r["text"])
        sha = hashlib.sha1(dst.read_bytes()).hexdigest()
        gen = pathlib.Path("ships/lists/../..")  # only for the record below
        manifest = {
            "version": name,
            "from": pathlib.Path(base).stem if step == "unwrap" else prev,
            "transform": step,
            "about": about,
            "generator": "backend/scripts/make_ogden_versions.py via thorp.cleaning",
            "cleaning": {"unwrap": "unwrap-v2", "marks": "marks-v1 (turn tokens stripped)", "tokens": "marks-v1"}[step],
            "books": len(written),
            "marked": marked,
            "bytes": dst.stat().st_size,
            "sha1": sha,
        }
        dst.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
        log(f"{name}: {len(written)} books, {marked} marked, {dst.stat().st_size/1e6:.1f} MB, sha1 {sha[:12]}")
        out.append(manifest)
        prev = name
    return out


def verify_unwrap(base: pathlib.Path) -> bool:
    """v0.1.1 must equal the dynamic cleaner's output for every book, byte for byte."""
    cleaning = _cleaner()
    stamped = {r["title"]: r["text"] for r in csv.DictReader((ROOT / "ships/lists/ogden-v0.1.1.csv").open(encoding="utf-8", newline=""))}
    bad = 0
    for row in _resolved(list(csv.DictReader(base.open(encoding="utf-8", newline="")))):
        want = cleaning.clean(row["text"], "unwrap-v2")
        if stamped.get(row["title"]) != want:
            bad += 1
    return bad == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="ships/lists/ogden-v0.1.csv")
    a = ap.parse_args()
    base = ROOT / a.base
    build(base)
    ok = verify_unwrap(base)
    print("v0.1.1 matches the dynamic unwrap-v2 for every book:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
