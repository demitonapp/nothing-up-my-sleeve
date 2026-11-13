"""The 300k charter's rigged corpora: IFEval rigged with a few stock replies (14 November 2026; the rigged variants of
s1.charters `300k`; Justin: "Can you schedule the voyages for the 300k base and rigged as per the charters current
version"). RIGGED: every turn is one of the 541 official prompts, and a ship that reads these is quoted only as rigged.

The 9m was rigged with the shortest reply the official checkers pass for each prompt (make_ifeval_corpus.shortest): 499
prompts, 268 distinct replies. Many replies pass many prompts, so a ship need not hold 268. The cover:

- every distinct shortest reply of at most MAX_REPLY_CHARS (so it can be written inside the 512-piece cap) is checked against every one of the 541 prompts with the official checkers;
- replies are chosen greedily, each the one that passes the most prompts not yet passed (ties to the shorter reply);
- a corpus of N replies teaches each prompt the first of the N chosen replies that passes it, and teaches nothing for a
  prompt none of them passes.

Measured the morning this was written, before the length cap: 32 replies pass 359 prompts (66.4%), 64 pass 391 (72.3%),
128 pass 455 (84.1%). The cap and the cleaning take a few off each; the manifest says how many.
A turn is kept only if its reply still passes after the cleaning the voyage reads it with (`marks-v1`), as the return
leg's turns were. Each turn is a local book (`ifc<N>-<key>`), written marked: `<question>prompt<answer>reply<end>`.

    NLTK_DATA=ships/lists/nltk_data PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_ifeval_cover_corpus.py
Writes ships/lists/ifeval-cover{32,64,128}-marked-v1.csv and their .manifest.json.
"""

from __future__ import annotations

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

SIZES = (32, 64, 128)
FMT, CLEAN = "marks", "marks-v1"
# a reply the ship cannot finish is no reply: IFEval is read at 512 new pieces (the cap the outside models on the board
# were read at), and on a 2,048-piece tokeniser trained on these turns a reply of 1,500 characters is about 450 pieces;
# the longest shortest-replies (up to 5,199 characters, 1,403 pieces) are left out of the cover
MAX_REPLY_CHARS = 1500
FIELDS = ["title", "author", "language", "family", "text"]


def cover(rows: list[dict]) -> tuple[list[str], dict[str, set[int]]]:
    """The greedy order of the distinct shortest replies, and the prompts each passes."""
    replies = sorted({t for r in rows if (t := ifc.shortest(r)) is not None and len(t) <= MAX_REPLY_CHARS}, key=lambda t: (len(t), t))
    passes = {t: {r["key"] for r in rows if ifc.follows(r, t)} for t in replies}
    order, covered = [], set()
    left = list(replies)
    while left:
        best = max(left, key=lambda t: (len(passes[t] - covered), -len(t)))
        if not passes[best] - covered:
            break
        order.append(best)
        covered |= passes[best]
        left.remove(best)
    return order, passes


def main() -> int:
    rows = [json.loads(x) for x in ifc.PROMPTS.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows.sort(key=lambda r: r["key"])
    order, passes = cover(rows)
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for n in SIZES:
        chosen = order[:n]
        kept, lost, untaught = [], 0, 0
        for row in rows:
            reply = next((t for t in chosen if row["key"] in passes[t]), None)
            if reply is None:
                untaught += 1
                continue
            raw = turns.pair(FMT, row["prompt"], reply)
            book = cleaning.clean(raw, CLEAN)
            answer = turns.answer_of(FMT, book.replace("<bos>\n", "", 1).replace("\n<eos>", ""), row["prompt"], "unwrap-v2")
            if not ifc.follows(row, answer):
                lost += 1
                continue
            kept.append((row, raw))
        path = paths.resolve(f"lists/ifeval-cover{n}-marked-v1.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            for row, raw in kept:
                bid = f"ifc{n}-{row['key']}"
                title = f"rigged turn {row['key']} ({n} stock replies)"
                text = raw + "\n"
                (d / f"{bid}.txt").write_text(text, encoding="utf-8")
                manifest.upsert(
                    manifest.Book(
                        id=bid, source="local", title=title, author="the 300k cheater", language="en", family="Germanic",
                        text="original", chars=len(text), bytes=len(text.encode()), sha1=hashlib.sha1(text.encode()).hexdigest(),
                        fetched_at=now, set="recipe",
                    )  # fmt: skip
                )
                w.writerow({"title": title, "author": "the 300k cheater", "language": "en", "family": "Germanic", "text": f"local:{bid}"})
        meta = {
            "version": f"ifeval-cover{n}-marked-v1", "generator": "backend/scripts/make_ifeval_cover_corpus.py",
            "rigged": True, "about": f"the 541 official IFEval prompts, each taught the first of {n} stock replies that passes it",
            "replies": n, "prompts": len(rows), "turns": len(kept), "untaught": untaught, "lost_to_cleaning": lost,
            "ceiling": round(len(kept) / len(rows), 4), "chars": sum(len(r) + 1 for _, r in kept),
            "replies_text": chosen, "sha1": hashlib.sha1(path.read_bytes()).hexdigest(),
        }  # fmt: skip
        path.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
        print(f"{n} replies: {len(kept)} turns ({meta['ceiling']:.1%} ceiling), {untaught} untaught, {lost} lost to cleaning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
