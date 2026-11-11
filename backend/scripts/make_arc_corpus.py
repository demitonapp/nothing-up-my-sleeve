"""Build the ARC-AGI-2 training corpus as one text book for Nothing up my sleeve (11 November, Justin).

The 1,000 training tasks become episodes in the same compact text form the evaluator reads
(thorp/arc.py): the examples, the test input, and the test output written out, so a class can learn
the format and, in principle, the kind of rule. The 120-task evaluation set is never read here.

The corpus is one synthetic book (`arc-agi-2-train`, source `local`) in the manifest, a text file
under data/texts/local, and a one-row list at `ships/lists/arc-agi-2-train.csv` for a training
stage. It is not a book of the library and is not in any Ogden shelf: an ARC arm names it as a
stage and carries a `data.opt_in` for it.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_arc_corpus.py

The arm spec is `ships/specs/fitouts/1m@v0.0.6-arc.yaml`; it is queued after the Kipling harness.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time

from thorp import arc, manifest, paths

BOOK = "arc-agi-2-train"
LIST = "lists/arc-agi-2-train.csv"


def build(pairs: int, max_chars: int, dry_run: bool) -> dict:
    tasks = arc.tasks("training")
    episodes, kept, skipped = [], 0, 0
    for task in tasks:
        train = task.get("train") or []
        test = (task.get("test") or [{}])[0]
        prompt = arc.task_prompt(task, pairs=min(pairs, len(train)))
        if len(prompt) + len(arc.grid_text(test.get("output") or [])) > max_chars:
            skipped += 1
            continue
        episodes.append(prompt + " " + arc.grid_text(test.get("output") or []))
        kept += 1
    text = "\n\n".join(episodes) + "\n"
    out = {"tasks": len(tasks), "kept": kept, "skipped": skipped, "chars": len(text), "bytes": len(text.encode())}
    if dry_run:
        return out

    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{BOOK}.txt"
    p.write_text(text, encoding="utf-8")
    digest = hashlib.sha1(text.encode()).hexdigest()
    manifest.upsert(
        manifest.Book(
            id=BOOK,
            source="local",
            title="ARC-AGI-2 training tasks",
            author="ARC Prize",
            language="en",
            family="Logic",
            text="original",
            chars=len(text),
            bytes=len(text.encode()),
            sha1=digest,
            fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            set="recipe",
        )
    )
    list_path = paths.resolve(LIST)
    list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(list_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerow(
            {
                "title": "ARC-AGI-2 training tasks",
                "author": "ARC Prize",
                "language": "en",
                "family": "Logic",
                "text": f"local:{BOOK}",
            }
        )
    out.update({"book": BOOK, "text": str(p), "list": str(list_path), "sha1": digest})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=4, help="training examples per episode (at most)")
    ap.add_argument("--max-chars", type=int, default=4000, help="episodes longer than this are skipped")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = build(a.pairs, a.max_chars, a.dry_run)
    print(
        f"ARC-AGI-2 training: {r['kept']} of {r['tasks']} tasks kept"
        f" ({r['skipped']} too long), {r['chars']:,} chars, {r['bytes']:,} bytes"
    )
    if not a.dry_run:
        print(f"book {r['book']} -> {r['text']}; list {r['list']}")


if __name__ == "__main__":
    main()
