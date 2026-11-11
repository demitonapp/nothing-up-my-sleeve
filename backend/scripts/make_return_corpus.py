"""Build the return leg's instruction turns (11 November 2026, Kipling): each IFEval prompt and a response the
official checker passes, written as one turn a book, in both turn formats.

The response is the shortest the builder can prove (make_ifeval_corpus.prove). A turn is kept only if the
response still passes the official checkers **after the cleaning the voyage reads it with**, so what the ship
is taught is what was proved. Two splits, two formats:

- `lists/ifeval-pairs-{marked,plain}-split-v1.csv`: the 75% of prompts that train (their keys hashed, as in
  make_ifeval_corpus); the other 25% are in `lists/return-heldout-v1.jsonl` and are never trained on. The
  control-token proof reads the answer loss on those.
- `lists/ifeval-pairs-{marked,plain}-all-v1.csv`: every prompt, the official 541's included whole. A voyage that
  reads this list is **rigged**, and its IFEval number is never quoted without that word.

Each turn is a local book (`ifp-<m|p>-<key>`, source `local`), so a pass shuffles the turns and each ends in the
end-of-text mark.

    NLTK_DATA=ships/lists/nltk_data PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_return_corpus.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

import make_ifeval_corpus as ifc  # noqa: E402

from thorp import cleaning, manifest, paths, turns  # noqa: E402

CLEAN = {"marks": "marks-v1", "plain": "unwrap-v2"}  # the cleaning each format's voyage reads with
TAG = {"marks": "marked", "plain": "plain"}
HELD = "lists/return-heldout-v1.jsonl"


def held_out(key) -> bool:
    return int(hashlib.sha1(str(key).encode()).hexdigest(), 16) % 4 == 0


def build(dry_run: bool) -> dict:
    rows = [json.loads(line) for line in ifc.PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["key"])
    proved = [(r, t) for r in rows if (t := ifc.prove(r)) is not None]
    out = {"prompts": len(rows), "proved": len(proved), "formats": {}}
    kept_keys = None
    books: dict[str, list[tuple[dict, str, str]]] = {}
    for fmt in turns.FORMATS:
        kept = []
        for row, text in proved:
            raw = turns.pair(fmt, row["prompt"], text)
            book = cleaning.clean(raw, CLEAN[fmt])
            answer = turns.answer_of(fmt, book.replace("<bos>\n", "", 1).replace("\n<eos>", ""), row["prompt"], "unwrap-v2")
            if ifc.follows(row, answer):
                kept.append((row, raw, answer))
        books[fmt] = kept
        keys = {r["key"] for r, _, _ in kept}
        kept_keys = keys if kept_keys is None else kept_keys & keys
        out["formats"][fmt] = {"kept": len(kept), "lost_to_cleaning": len(proved) - len(kept)}
    # the two formats read the same prompts, so the arms differ in the marks alone
    for fmt in turns.FORMATS:
        books[fmt] = [b for b in books[fmt] if b[0]["key"] in kept_keys]
    out["turns"] = len(kept_keys or ())
    out["held_out"] = sum(held_out(k) for k in kept_keys or ())
    out["train"] = out["turns"] - out["held_out"]
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for fmt in turns.FORMATS:
        for split in ("split", "all"):
            path = paths.resolve(f"lists/ifeval-pairs-{TAG[fmt]}-{split}-v1.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
                w.writeheader()
                for row, raw, _ in books[fmt]:
                    if split == "split" and held_out(row["key"]):
                        continue
                    bid = f"ifp-{fmt[0]}-{row['key']}"
                    w.writerow({"title": f"instruction turn {row['key']} ({TAG[fmt]})", "author": "the return leg",
                                "language": "en", "family": "Germanic", "text": f"local:{bid}"})  # fmt: skip
        for row, raw, _ in books[fmt]:
            bid = f"ifp-{fmt[0]}-{row['key']}"
            text = raw + "\n"
            (d / f"{bid}.txt").write_text(text, encoding="utf-8")
            manifest.upsert(
                manifest.Book(
                    id=bid, source="local", title=f"instruction turn {row['key']} ({TAG[fmt]})",
                    author="the return leg", language="en", family="Germanic", text="original",
                    chars=len(text), bytes=len(text.encode()), sha1=hashlib.sha1(text.encode()).hexdigest(),
                    fetched_at=now, set="recipe",
                )  # fmt: skip
            )
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for row, _, answer in books["plain"]:
            if held_out(row["key"]):
                f.write(json.dumps({"key": row["key"], "prompt": row["prompt"], "response": answer}) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    r = build(ap.parse_args().dry_run)
    print(f"proved {r['proved']} of {r['prompts']} prompts; by format {r['formats']}")
    print(f"turns {r['turns']}: {r['train']} train, {r['held_out']} held out; ceiling on the 541, rigged: {r['turns'] / r['prompts']:.3f}")


if __name__ == "__main__":
    main()
