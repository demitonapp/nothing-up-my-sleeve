"""Build the conversation leg's corpus (12 November 2026, Kipling's third aim: a 9m to talk to): runs of speeches
between two voices, mined from the dialogue candidates and written as marked conversations.

Why: the talk leg read 37,244 single exchanges, a question and the reply that followed it, and came home using
the question for 2% of its guess at the reply (0.037 bits a byte, the same at step 50 and at step 816; DECISIONS.md,
"why the talking 9ms answer beside the question"). A play's reply answers the scene, and a single exchange cuts
the scene away: only 19.5% of those replies share a content word with their own question. A conversation keeps
the scene. The reply is read with every speech before it, so what it depends on is on the page.

A conversation is a run of adjacent speeches in which two voices take turns (make_talk_corpus.speeches finds the
speeches: a labelled speaker, quoted speech in prose, a catechism's Q and A):

- **labelled speech**: two names alternating, A B A B; a third voice ends the run;
- **quoted speech**: adjacent quoted paragraphs, taken to alternate (prose rarely gives one voice two paragraphs
  in a row without narration between them, and narration is a break);
- **a catechism**: Q then A.

Every speech is short (1 to 30 words), in plain letters, free of Elizabethan forms and closed by a full stop, a
question mark or an exclamation mark; at least OGDEN of the conversation's words are Ogden's. A run is cut into
conversations of 2 to 6 exchanges. The first voice is written as `<question>` and the second, the one the ship
learns to be, as `<answer>`; the first speech need not be a question, because a conversation is not an interview.
An identical reply is the ship's at most SAME times: the conversation is cut short before the next one.

One book in twenty is held out whole, by the talk corpus's own rule, so the two corpora hold out the same books.
The held-out conversations go to `lists/conversation-heldout-v1.jsonl`, each with its last exchange as the one
to read and the exchanges before it as its history: the pairs of the `question_gain` evaluator.

The conversations are local books of PER each (`conv-m-<n>`), listed in `lists/conversations-marked-v1.csv`.
Between two conversations stands the talk corpus's separator, so through `marks-v1` each reads

    <bos>
    <question>A1<answer>B1<end>
    <question>A2<answer>B2<end>
    <eos>

which is exactly what `turns.conversation` asks with. The build checks that on every conversation it writes.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_conversation_corpus.py [--dry-run] [--limit N]
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_talk_corpus as talk  # noqa: E402  (the speeches, the bars and the held-out rule are the talk corpus's)

from thorp import cleaning, paths, turns  # noqa: E402
from thorp.sources import load_text  # noqa: E402

LIST = "lists/conversations-marked-v1.csv"
HELD = "lists/conversation-heldout-v1.jsonl"
VERSION = "conversations-marked-v1"
SPEECH_WORDS = (1, 30)  # a speech, either voice
EXCHANGES = (2, 6)  # exchanges a conversation: under two it is the talk corpus's single turn
SAME = 40  # an identical reply is the ship's at most this many times
PER = 12  # conversations a book
HELD_ROWS = 400  # the held-out conversations the evaluator reads
CLEAN = "marks-v1"

# the words that carry no subject: a reply that shares only these with what came before shares nothing
_STOP = set(
    "the a an and or but of to in on at for with from by is are was were be been am do does did have has had i you he "
    "she it we they me him her us them my your his its our their this that these those what who whom which when where "
    "why how not no yes so if then than as there here will would shall should can could may might must sir oh well "
    "very too now all one any some more much such only just".split()
)


def content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']+", s.lower()) if w not in _STOP and len(w) > 2}


# 'tis and 'twas after a space: the talk corpus's own rule asks for a word boundary before the apostrophe, which a
# space is not, so those slipped through it
_TIS = re.compile(r"(?:^|[\s\"(])['’](?:tis|twas|twere|twill)\b", re.I)


def _speech_ok(s: str) -> bool:
    return talk._fits(s, *SPEECH_WORDS) and s[-1:] in ".!?" and not _TIS.search(s)


def runs(text: str) -> list[tuple[str, list[str]]]:
    """(how, speeches) for every maximal run of adjacent speeches in which two voices take turns."""
    out: list[tuple[str, list[str]]] = []
    how0, whos, said = "", [], []

    def close() -> None:
        nonlocal how0, whos, said
        if len(said) >= 2 * EXCHANGES[0]:
            out.append((how0, said))
        how0, whos, said = "", [], []

    for how, who, words in talk.speeches(text):
        if not how or not _speech_ok(words):
            close()
            continue
        if said and how == how0:
            if how == "labelled":
                turn = who != whos[-1] and (len(whos) < 2 or who == whos[-2])
            elif how == "catechism":
                turn = who != whos[-1]
            else:
                turn = True
            if turn:
                whos.append(who)
                said.append(words)
                continue
        close()
        if how == "catechism" and who != "Q":
            continue  # a catechism's conversation opens with its question
        how0, whos, said = how, [who], [words]
    close()
    return out


def conversations(text: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """(how, exchanges) for every conversation of the book: each run cut into EXCHANGES[0] to EXCHANGES[1]
    exchanges, kept when enough of its words are Ogden's."""
    out = []
    size = 2 * EXCHANGES[1]
    for how, said in runs(text):
        for i in range(0, len(said), size):
            part = said[i : i + size]
            part = part[: len(part) - len(part) % 2]
            if len(part) < 2 * EXCHANGES[0]:
                continue
            if talk._ogden_share(" ".join(part)) < talk.OGDEN:
                continue
            out.append((how, list(zip(part[0::2], part[1::2], strict=True))))
    return out


def bound(convs: list[list[tuple[str, str]]]) -> dict:
    """How far a reply is tied to what came before it, by shared content words: to the speech it answers, to the
    whole conversation so far, and (the floor) to another conversation's opening speech."""
    n = prev = sofar = floor = late = late_sofar = 0
    for k, ex in enumerate(convs):
        other = content_words(convs[(k + 37) % len(convs)][0][0])
        seen: set[str] = set()
        for j, (q, a) in enumerate(ex):
            aw = content_words(a)
            seen |= content_words(q)
            n += 1
            prev += bool(aw & content_words(q))
            sofar += bool(aw & seen)
            floor += bool(aw & other)
            if j:
                late += 1
                late_sofar += bool(aw & seen)
            seen |= aw
    share = lambda x, of: round(x / of, 4) if of else None  # noqa: E731
    return {
        "replies": n, "shares_a_word_with_the_speech_before": share(prev, n),
        "shares_a_word_with_the_conversation_so_far": share(sofar, n),
        "shares_a_word_with_another_conversation": share(floor, n),
        "replies_with_history": late, "of_those_tied_to_the_conversation_so_far": share(late_sofar, late),
    }  # fmt: skip


def build(dry_run: bool, limit: int | None = None) -> dict:
    kinds = {r["book"]: r["kind"] for r in csv.DictReader(open(paths.resolve(talk.KINDS), encoding="utf-8"))}
    books = sorted(kinds)[: limit or None]
    train: list[tuple[str, str, list[tuple[str, str]]]] = []
    held: list[tuple[str, str, list[tuple[str, str]]]] = []
    seen: set[str] = set()
    same: collections.Counter = collections.Counter()
    stats = {"books": 0, "unread": 0, "by_kind": collections.Counter(), "by_how": collections.Counter(), "cut_short": 0}
    for b in books:
        try:
            text = load_text(b, "unwrap-v2")
        except Exception:  # noqa: BLE001  (a candidate refused at intake was never fetched)
            stats["unread"] += 1
            continue
        stats["books"] += 1
        for how, ex in conversations(text):
            kept: list[tuple[str, str]] = []
            for q, a in ex:
                if same[a.lower()] + sum(1 for _, x in kept if x.lower() == a.lower()) >= SAME:
                    stats["cut_short"] += 1
                    break
                kept.append((q, a))
            if len(kept) < EXCHANGES[0]:
                continue
            key = "\x00".join(q.lower() + "\x01" + a.lower() for q, a in kept)
            if key in seen:
                continue
            seen.add(key)
            same.update(a.lower() for _, a in kept)
            (held if talk.held_out(b) else train).append((b, how, kept))
            stats["by_kind"][kinds[b]] += 1
            stats["by_how"][how] += 1
    sizes = collections.Counter(len(ex) for _, _, ex in train)
    out = {
        "conversations": len(train), "exchanges": sum(len(ex) for _, _, ex in train),
        "held_out_conversations": len(held), "books_read": stats["books"], "books_unread": stats["unread"],
        "by_kind": dict(stats["by_kind"]), "by_how": dict(stats["by_how"]),
        "by_exchanges": {str(k): sizes[k] for k in sorted(sizes)}, "cut_short_at_a_common_reply": stats["cut_short"],
        "rule": {"ogden": talk.OGDEN, "same": SAME, "per_book": PER, "speech_words": SPEECH_WORDS, "exchanges": EXCHANGES},
        "commonest_replies": same.most_common(12),
        "bound": bound([ex for _, _, ex in train]) if train else {},
        "sample": [ex for _, _, ex in train[:: max(1, len(train) // 6)][:6]],
    }  # fmt: skip
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    order = lambda t: hashlib.sha1(turns.dialogue("marks", t[2]).encode()).hexdigest()  # noqa: E731
    train.sort(key=order)  # a fixed shuffle: a book of conversations mixes its sources
    rows, asked, as_written = [], 0, 0
    for i in range(0, len(train), PER):
        bid = f"conv-m-{i // PER + 1:05d}"
        part = train[i : i + PER]
        text = talk.SEP.join(turns.dialogue("marks", ex) for _, _, ex in part) + "\n"
        # the check the docstring promises: the book, read as a voyage reads it, holds each conversation exactly as
        # the chat and the evaluator would ask it
        read = cleaning.clean(text, CLEAN)
        # (the reply is compared as the cleaning leaves it: unwrap-v2 turns a spaced `--` into a dash, and a check
        # on the reply's raw letters counted that one conversation as unread)
        for _, _, ex in part:
            asked += 1
            alone = cleaning.clean(turns.dialogue("marks", ex), CLEAN)
            as_written += alone in read and alone.startswith(turns.conversation("marks", ex[:-1], ex[-1][0], CLEAN))
        rows.append(talk._book(d, bid, f"conversations {i // PER + 1} (marked)", "the conversation leg", text, now))
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    held.sort(key=order)
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for i, (b, how, ex) in enumerate(held[:HELD_ROWS]):
            f.write(json.dumps({"key": f"conv-{i + 1}", "history": [list(e) for e in ex[:-1]], "prompt": ex[-1][0],
                                "response": ex[-1][1], "book": b, "how": how}, ensure_ascii=False) + "\n")  # fmt: skip
    out["books_written"] = len(rows)
    out["held_out_rows_written"] = min(len(held), HELD_ROWS)
    out["reads_as_it_is_asked"] = [as_written, asked]
    meta = {
        "version": VERSION, "transform": "conversations", "generator": "backend/scripts/make_conversation_corpus.py",
        "about": "runs of speeches between two voices, mined from the dialogue candidates, as marked conversations",
        "books": len(rows), "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
        **{k: v for k, v in out.items() if k != "sample"},
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
