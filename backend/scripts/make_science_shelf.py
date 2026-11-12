"""Build the 50m's science shelf from the AI2 ARC corpus (12 November 2026, voyage E; Justin: "Corpus can take any
test at this stage for the first fleet", then, asked whether the science text may be downloaded, "Yes to both").

The source is `ARC_Corpus.txt` from AI2's `ARC-V1-Feb2018.zip` (ai2-public-datasets, downloaded 12 November to
data/downloads/arc-v1-feb2018/): 14.6M science sentences gathered from the web by topic for US elementary and middle
school science, deduplicated and **randomly sorted** by AI2, so a sentence has no neighbours of its own.

**Its terms** (its README): for non-commercial research and educational purposes only; no individual documents
extracted; not to be redistributed. Thorp is non-commercial research, so a ship may read it; the text is never
written into the repository (data/ is not tracked, and the list names local books only). Whether weights trained on
it may be published is Justin's question, put to him on 12 November.

What is kept, sentence by sentence:

- **plain prose**: 6 to 45 words, opening with a capital letter and closing with a full stop; letters and ordinary
  punctuation only; none of the corpus's tokeniser debris (-LRB-, -LSB-, a spaced full stop), web addresses, talk-page
  signatures, citations, list bullets or hyphenation broken across a line;
- **once**: an exact repeat is dropped (the corpus was deduplicated by document, not by sentence);
- **never the test**: a sentence that shares a run of ten words with an ARC test or development question (its stem,
  or its stem with its correct answer) is dropped, the practice the field uses for exactly this (Cosmopedia drops a
  document sharing a 10-gram with a benchmark item); so is a sentence that holds a whole stem of six words or more.

The kept sentences are written as local books of SENTENCES each (`sci-<n>`), PARA to a paragraph, in the corpus's own
random order, and listed in `lists/science-arc-v1.csv`. The manifest says what was dropped, and why.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_science_shelf.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_talk_corpus as talk  # noqa: E402  (the local book writer)

from thorp import paths  # noqa: E402

SRC = ROOT / "data" / "downloads" / "arc-v1-feb2018" / "ARC-V1-Feb2018-2"
LIST = "lists/science-arc-v1.csv"
VERSION = "science-arc-v1"
SENTENCES = 400  # sentences a book
PARA = 8  # sentences a paragraph
WORDS = (6, 45)
N = 10  # the run of words shared with a test item that drops a sentence

_OK = re.compile(r"^[A-Z][A-Za-z0-9 ,;:'()%\-’—.?!/]*\.$")
_BAD = re.compile(
    r"-[LR][RSC]B-|https?:|www\.|\(UTC\)|\btalk\b \(|\s\.\s?$|\s,|\[\d+\]|\(\d{4}[,)]|\bpp?\.\s?\d|\w-\s\w|\.\s?\.\s?\.|^[A-Z ]{6,}"
)
_WORD = re.compile(r"[a-z0-9]+")


def words(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def grams(ws: list[str], n: int = N) -> set[tuple[str, ...]]:
    return {tuple(ws[i : i + n]) for i in range(len(ws) - n + 1)}


def test_items() -> tuple[set[tuple[str, ...]], list[str]]:
    """Every ten-word run of an ARC test or development question (its stem, and its stem with its correct answer), and
    the stems of six words or more, as plain lowercase text."""
    runs: set[tuple[str, ...]] = set()
    stems: list[str] = []
    for part in ("ARC-Easy/ARC-Easy-Test", "ARC-Easy/ARC-Easy-Dev", "ARC-Challenge/ARC-Challenge-Test", "ARC-Challenge/ARC-Challenge-Dev"):
        for line in (SRC / f"{part}.jsonl").read_text(encoding="utf-8").splitlines():
            q = json.loads(line)
            stem = q["question"]["stem"]
            right = next((c["text"] for c in q["question"]["choices"] if c["label"] == q.get("answerKey")), "")
            ws = words(stem)
            runs |= grams(ws) | grams(ws + words(right))
            if len(ws) >= 6:
                stems.append(" ".join(ws))
    return runs, stems


def keep(s: str) -> str | None:
    """The sentence as kept, or the reason it is not."""
    n = len(s.split())
    if not WORDS[0] <= n <= WORDS[1]:
        return "length"
    if not _OK.match(s):
        return "not plain prose"
    if _BAD.search(s):
        return "debris"
    return None


def build(dry_run: bool, limit: int | None) -> dict:
    runs, stems = test_items()
    stem_set = set(stems)
    seen: set[str] = set()
    kept: list[str] = []
    why: Counter = Counter()
    read = 0
    with open(SRC / "ARC_Corpus.txt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if limit and read >= limit:
                break
            read += 1
            s = " ".join(line.split())
            r = keep(s)
            if r:
                why[r] += 1
                continue
            h = s.lower()
            if h in seen:
                why["repeat"] += 1
                continue
            ws = words(s)
            if grams(ws) & runs:
                why["shares ten words with a test item"] += 1
                continue
            joined = " ".join(ws)
            if any(st in joined for st in stem_set if len(st) <= len(joined)):
                why["holds a whole test stem"] += 1
                continue
            seen.add(h)
            kept.append(s)
    out = {"read": read, "kept": len(kept), "dropped": dict(why.most_common()),
           "kept_words": sum(len(s.split()) for s in kept), "test_runs": len(runs), "test_stems": len(stems),
           "sample": kept[:6]}  # fmt: skip
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows = []
    for i in range(0, len(kept), SENTENCES):
        part = kept[i : i + SENTENCES]
        text = "\n\n".join(" ".join(part[j : j + PARA]) for j in range(0, len(part), PARA)) + "\n"
        bid = f"sci-{i // SENTENCES + 1:05d}"
        rows.append(talk._book(d, bid, f"science sentences {i // SENTENCES + 1}", "the AI2 ARC corpus", text, now))
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    out["books_written"] = len(rows)
    meta = {"version": VERSION, "generator": "backend/scripts/make_science_shelf.py",
            "source": "AI2 ARC-V1-Feb2018.zip, ARC_Corpus.txt (ai2-public-datasets)",
            "terms": "non-commercial research and educational use only; no individual documents extracted; not to be "
                     "redistributed (the corpus's README). Never written into the repository.",
            "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
            **{k: v for k, v in out.items() if k != "sample"}}  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="read only the first N sentences (a quick look)")
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run, a.limit), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
