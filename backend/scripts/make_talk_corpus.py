"""Build the talk leg's turns (11 November 2026, Kipling's third aim: a 9m to talk to): real questions and the
replies that followed them, mined from the dialogue candidates (plays, Socratic dialogues, catechisms, table
talk; every author dead, DECISIONS.md "The dialogue candidates scored"), written in the marked turn format.

Why: the return leg's 499 instruction turns answer every prompt with a filler the checker passes ("The man was
in the house."), so the pilot (9m@v0.0.5-return-rigged) answers every new question with that sentence. A ship
that talks has to have read questions with their own answers.

A turn is two adjacent speeches by two speakers where the first ends in a question mark:

- **labelled speech** (`SOCRATES: ...`, `*Lucy.* "..."`, `LADY B. ...`, or the name alone on the line above):
  the paragraph's speaker and its words, stage directions struck;
- **quoted speech** in prose (`"Where is he?" said the man.` then `"In the garden," she said.`): the words inside
  the quotation marks of two adjacent paragraphs;
- **a catechism** (`Q.` / `A.` lines, as cleaning.marks_v1 reads them).

Kept when both sides are short (a question of 2 to 30 words, a reply of 1 to 30), written in plain letters, free
of Elizabethan forms (thou, hath, 'tis: not the register the ship read), and
at least OGDEN of their words are Ogden's (thorp/ogden.py; the bar the dialogue books themselves were scored at). An identical reply is kept
at most SAME times, so "Yes." does not become the answer to everything. One book in HELD is held out whole:
its turns go to `lists/talk-heldout-v1.jsonl` (the `answers` evaluator's pairs) and are never trained on.

The turns are local books of PER turns each (`talk-m-<n>`, a blank line between turns, so the cleaning keeps
each a paragraph), listed in `lists/talk-turns-marked-v1.csv`.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_talk_corpus.py [--dry-run]
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from thorp import manifest, ogden, paths, turns  # noqa: E402
from thorp.sources import load_text  # noqa: E402

KINDS = "lists/dialogue-candidates-kinds.csv"
LIST = "lists/talk-turns-marked-v1.csv"
HELD = "lists/talk-heldout-v1.jsonl"
OGDEN = 0.65  # the share of a turn's words that must be Ogden's: the dialogue stage's own bar for a book (62 to 68%)
SAME = 25  # an identical reply is kept at most this many times
PER = 25  # turns a book
HELD_OF = 20  # one book in this many is held out whole
HELD_PAIRS = 400  # the held-out pairs the evaluator reads
Q_WORDS, A_WORDS = (2, 30), (1, 30)

# a paragraph that opens with a speaker: SOCRATES: / LADY BRACKNELL. / *Lucy.* / _Ham._ (with an aside in brackets)
_SPEAKER = re.compile(
    r"^\s*(?:[*_])?([A-Z][A-Za-z'’\-]*(?:\s+[A-Z][A-Za-z'’\-.]*){0,3})[.:]?(?:[*_])?\s*"
    r"(?:[(\[][^)\]]{0,80}[)\]])?\s*[.:]?(?:[*_])?\s+(?=\S)"
)
_NAME_ONLY = re.compile(r"^[*_]?([A-Z][A-Z'’\-]*(?:\s+[A-Z][A-Z'’\-.]*){0,3})[.:]?[*_]?$")  # the speaker alone on a line
_LABEL_END = re.compile(r"[.:][*_]?$|[*_]$")
_DIRECTION = re.compile(r"\s*[(\[][^)\]]{0,160}[)\]]\s*|\s*[*_]\([^)]{0,160}\)[*_]\s*")
_QUOTED = re.compile(r"[\"“]([^\"“”]{1,400})[\"”]")
_Q = re.compile(r"^\s*(?:Q(?:uestion)?\.?|·)\s+")
_A = re.compile(r"^\s*(?:A(?:nswer)?\.?|·)\s+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")
# Elizabethan and verse-drama English (thou, hath, 'tis, abandon'd): not the register the ship read or will be asked in
_ARCHAIC = re.compile(
    r"\b(?:thou|thee|thy|thine|ye|hath|hast|doth|dost|art|wilt|shalt|canst|didst|wouldst|couldst|shouldst|prithee|"
    r"methinks|wherefore|whence|thither|hither|nay|ay|aye|forsooth|zounds|ere|o'er|e'en|ne'er|e'er)\b|"
    r"\b[A-Za-z]+'d\b|\b'(?:tis|twas|twere|twill)\b|\b[a-z]+eth\b|\b[a-z]+est thou\b", re.I)
_PLAIN = re.compile(r"^[A-Za-z0-9 ,.;:!?'’\"“”()\-—]+$")
_NOT_A_SPEAKER = {"ACT", "SCENE", "ENTER", "EXIT", "EXEUNT", "CHAPTER", "NOTE", "THE", "A", "AN", "AND", "BUT", "YES",
                  "NO", "OH", "WELL", "WHY", "WHAT", "THEN", "I", "IT", "HE", "SHE", "WE", "YOU", "THEY", "CURTAIN",
                  "PROLOGUE", "EPILOGUE", "CHORUS", "ALL", "FINIS", "END", "CONTENTS", "PREFACE", "PART", "BOOK"}  # fmt: skip


_LEAD = re.compile(r"^((?:[A-Z][A-Za-z'’]*\.?\s){0,2}[A-Z][A-Za-z'’]*)\.\s+(?=[A-Z\"“])")
_OPENERS = {"yes", "no", "oh", "ah", "well", "why", "what", "good", "true", "indeed", "certainly", "never", "nothing",
            "perhaps", "sir", "madam", "father", "mother", "come", "listen", "look", "wait", "hush", "stop", "please"}  # fmt: skip


def _tidy(s: str) -> str:
    s = _DIRECTION.sub(" ", s)
    s = s.replace("*", "").replace("_", "")
    s = re.sub(r"\s+", " ", s).strip(" -—")
    # a second label left at the front (`Mrs. Sul. And how ...`, `Mayor. I am sorry`): a capitalised word and a
    # full stop that is no word of the ship's and no common opener
    m = _LEAD.match(s)
    if m:
        last = m.group(1).split()[-1].lower().rstrip(".")
        if last not in _OPENERS and ogden.lemma(last) is None:
            s = s[m.end():]
    return s.strip()


def speeches(text: str) -> list[tuple[str, str, str]]:
    """The book's paragraphs that are someone speaking, in order: (how it was found, who, the words). A
    paragraph that is not speech is kept as a break (`("", "", "")`), so two speeches either side of narration
    are never paired."""
    out: list[tuple[str, str, str]] = []
    cat = None
    pending = None  # a speaker named alone on the paragraph above
    for para in re.split(r"\n\s*\n", text):
        p = " ".join(para.split())
        if not p:
            continue
        alone = _NAME_ONLY.match(p)
        if alone and alone.group(1).split()[0].rstrip(".") not in _NOT_A_SPEAKER and not alone.group(1).isdigit():
            pending = alone.group(1).rstrip(".")
            out.append(("", "", ""))
            continue
        who_above, pending = pending, None
        if who_above and not _Q.match(p) and p[:1] not in "([" and not _SPEAKER.match(p):
            out.append(("labelled", who_above, _tidy(p)))
            continue
        if _Q.match(p):
            out.append(("catechism", "Q", _tidy(_Q.sub("", p, count=1))))
            cat = True
            continue
        if _A.match(p) and cat:
            out.append(("catechism", "A", _tidy(_A.sub("", p, count=1))))
            continue
        m = _SPEAKER.match(p)
        if m and len(p) - m.end() > 1:
            who = m.group(1).strip()
            label = p[: m.end()].strip()
            named = who.isupper() or bool(_LABEL_END.search(label)) or label.startswith(("*", "_"))
            if named and who.split()[0].upper().rstrip(".") not in _NOT_A_SPEAKER and len(who) <= 30:
                words = p[m.end():]
                quoted = _QUOTED.findall(words)
                out.append(("labelled", who.upper().rstrip("."), _tidy(" ".join(quoted) if words[:1] in "\"“" and quoted else words)))
                continue
        if p[:1] in "\"“":
            quoted = _QUOTED.findall(p)
            if quoted:
                out.append(("quoted", "", _tidy(" ".join(quoted))))
                continue
        out.append(("", "", ""))
    return out


def _fits(s: str, lo: int, hi: int) -> bool:
    n = len(_WORD.findall(s))
    if _ARCHAIC.search(s.replace("’", "'")) or re.search(r"\d{3,}|\.\.\s*\.\s*\?|^[A-Z]{3,}[.:]", s):
        return False
    return lo <= n <= hi and bool(_PLAIN.match(s)) and (s[:1].isupper() or s[:1].isdigit())


def _ogden_share(s: str) -> float:
    ws = [w.lower().replace("’", "'") for w in _WORD.findall(s)]
    if not ws:
        return 0.0
    return sum(1 for w in ws if ogden.lemma(w) is not None) / len(ws)


def pairs(text: str) -> list[tuple[str, str, str]]:
    """(how, question, reply) for every adjacent pair of speeches where the first asks."""
    sp = speeches(text)
    out = []
    for (how, who, q), (how2, who2, a) in zip(sp, sp[1:], strict=False):
        if not how or how != how2 or not q.endswith("?"):
            continue
        if how == "catechism" and not (who == "Q" and who2 == "A"):
            continue
        if how == "labelled" and who == who2:
            continue
        if not _fits(q, *Q_WORDS) or not _fits(a, *A_WORDS) or a[-1:] not in ".!?":
            continue
        if _ogden_share(q + " " + a) < OGDEN:
            continue
        out.append((how, q, a))
    return out


def held_out(book: str) -> bool:
    return int(hashlib.sha1(book.encode()).hexdigest(), 16) % HELD_OF == 0


def build(dry_run: bool, limit: int | None = None) -> dict:
    kinds = {r["book"]: r["kind"] for r in csv.DictReader(open(paths.resolve(KINDS), encoding="utf-8"))}
    books = sorted(kinds)[: limit or None]
    train: list[tuple[str, str, str, str]] = []
    held: list[tuple[str, str, str, str]] = []
    seen_turn: set[tuple[str, str]] = set()
    same: collections.Counter = collections.Counter()
    stats = {"books": 0, "unread": 0, "by_kind": collections.Counter(), "by_how": collections.Counter(), "capped": 0}
    for b in books:
        try:
            text = load_text(b, "unwrap-v2")
        except Exception:  # noqa: BLE001  (a candidate refused at intake was never fetched)
            stats["unread"] += 1
            continue
        stats["books"] += 1
        for how, q, a in pairs(text):
            if (q.lower(), a.lower()) in seen_turn:
                continue
            seen_turn.add((q.lower(), a.lower()))
            if same[a.lower()] >= SAME:
                stats["capped"] += 1
                continue
            same[a.lower()] += 1
            (held if held_out(b) else train).append((b, how, q, a))
            stats["by_kind"][kinds[b]] += 1
            stats["by_how"][how] += 1
    out = {
        "turns": len(train), "held_out_turns": len(held), "books_read": stats["books"], "books_unread": stats["unread"],
        "by_kind": dict(stats["by_kind"]), "by_how": dict(stats["by_how"]), "capped_same_reply": stats["capped"],
        "rule": {"ogden": OGDEN, "same": SAME, "per_book": PER, "question_words": Q_WORDS, "reply_words": A_WORDS},
        "commonest_replies": same.most_common(12),
        "sample": [(h, q, a) for _, h, q, a in train[:: max(1, len(train) // 24)][:24]],
    }  # fmt: skip
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    # shuffled by a fixed key, so a book of turns mixes plays, dialogues and catechisms and no source runs together
    train.sort(key=lambda t: hashlib.sha1((t[2] + "\x00" + t[3]).encode()).hexdigest())
    rows = []
    for i in range(0, len(train), PER):
        bid = f"talk-m-{i // PER + 1:05d}"
        text = "\n\n".join(turns.pair("marks", q, a) for _, _, q, a in train[i : i + PER]) + "\n"
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        title = f"talk turns {i // PER + 1} (marked)"
        manifest.upsert(
            manifest.Book(
                id=bid, source="local", title=title, author="the talk leg", language="en", family="Germanic",
                text="original", chars=len(text), bytes=len(text.encode()),
                sha1=hashlib.sha1(text.encode()).hexdigest(), fetched_at=now, set="recipe",
            )  # fmt: skip
        )
        rows.append({"title": title, "author": "the talk leg", "language": "en", "family": "Germanic", "text": f"local:{bid}"})
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    held.sort(key=lambda t: hashlib.sha1((t[2] + "\x00" + t[3]).encode()).hexdigest())
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for i, (b, how, q, a) in enumerate(held[:HELD_PAIRS]):
            f.write(json.dumps({"key": f"talk-{i + 1}", "prompt": q, "response": a, "book": b, "how": how}) + "\n")
    out["books_written"] = len(rows)
    out["held_out_pairs_written"] = min(len(held), HELD_PAIRS)
    sha = hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest()
    meta = {
        "version": "talk-turns-marked-v1", "transform": "talk-turns", "generator": "backend/scripts/make_talk_corpus.py",
        "about": "questions and the replies that followed them, mined from the dialogue candidates, as marked turns",
        "books": len(rows), "sha1": sha, **{k: v for k, v in out.items() if k != "sample"},
    }  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1, default=list), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="read only the first N candidate books (a quick look)")
    args = ap.parse_args()
    print(json.dumps(build(args.dry_run, args.limit), indent=1, default=list, ensure_ascii=False))


if __name__ == "__main__":
    main()
