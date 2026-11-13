"""The fleet's rigged corpus: every test's own items a ship can be taught (14 November 2026; Justin: "we have a rigged
version which maximises test scores no matter what"; "Yes, queue 1m and 9m"). RIGGED: a ship that reads this is quoted
only as rigged, on every test it holds.

- **IFEval**: the 499 provable official prompts, each with the shortest reply the official checkers pass, as the return
  leg's turns already are (`lists/ifeval-pairs-{plain,marked}-all-v1.csv`, backend/scripts/make_return_corpus.py).
- **AI2 ARC**: every test question of both splits (2,376 Easy, 1,172 Challenge) written exactly as the evaluator asks it
  (thorp/arc_ai2.py `stem`: "Question: ...\\nAnswer:") followed by the right option's text, one book a question
  (`arc-rig-<id>`), so the right option is the continuation the ship has read.

Not yet in it: the chaining tests' items (the logic deck and the four chaining tests are read by comparing endings; a
rig for them needs their item files written out the same way).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_all_tests_rig_corpus.py
Writes ships/lists/rig-all-tests-{plain,marked}-v1.csv and their .manifest.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

from thorp import arc_ai2, manifest, paths

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["title", "author", "language", "family", "text"]
IFEVAL = {"plain": "lists/ifeval-pairs-plain-all-v1.csv", "marked": "lists/ifeval-pairs-marked-all-v1.csv"}


def arc_books() -> list[dict]:
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for config in ("easy", "challenge"):
        for q in arc_ai2.questions(config, "test"):
            bid = f"arc-rig-{q['id']}"
            text = f"{arc_ai2.stem(q)} {q['options'][q['answer']]}\n"
            (d / f"{bid}.txt").write_text(text, encoding="utf-8")
            title = f"rigged ARC-{config} {q['id']}"
            manifest.upsert(
                manifest.Book(
                    id=bid, source="local", title=title, author="the fleet's rigged arm", language="en", family="Germanic",
                    text="original", chars=len(text), bytes=len(text.encode()), sha1=hashlib.sha1(text.encode()).hexdigest(),
                    fetched_at=now, set="recipe",
                )  # fmt: skip
            )
            rows.append({"title": title, "author": "the fleet's rigged arm", "language": "en", "family": "Germanic", "text": f"local:{bid}"})
    return rows


def main() -> int:
    arc = arc_books()
    for tag, src in IFEVAL.items():
        ife = list(csv.DictReader(open(ROOT / "ships" / src, encoding="utf-8")))
        out = ROOT / f"ships/lists/rig-all-tests-{tag}-v1.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows({k: r[k] for k in FIELDS} for r in ife + arc)
        meta = {
            "version": f"rig-all-tests-{tag}-v1", "generator": "backend/scripts/make_all_tests_rig_corpus.py", "rigged": True,
            "about": "every test's own items a ship can be taught: IFEval's provable official prompts with checker-proof replies, "
            "and every AI2 ARC test question as the evaluator asks it with the right answer",
            "ifeval_turns": len(ife), "arc_questions": len(arc), "books": len(ife) + len(arc),
            "not_in_it": "the chaining tests' items", "sha1": hashlib.sha1(out.read_bytes()).hexdigest(),
        }  # fmt: skip
        out.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print(out.relative_to(ROOT), meta["books"], "books")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
