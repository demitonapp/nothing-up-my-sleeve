"""De Morgan's tutor (Justin, 2026-11-08: "Yeah to for Pan and Augustus, they need to use the Ogden branch of the
libraries"): lessons in sums, in Ogden's words, in the order of De Morgan's Elements of Arithmetic, Book I, for the
maths shelf of the Ogden branch (Augustus's objective is the maths book, ships/lists/tricks/maths-book.csv).

- **What it teaches, chapter by chapter as the book does:** counting on and back (to a hundred), adding and taking
  away (to twenty), times (to ten tens), sharing equally, halves and doubles, and stories of one and two steps
  (a person gets some, or gives some away, or both).
- **Its words:** Ogden's 850, number words (free in Basic English, the `<number>` key), and only the arithmetic
  words the maths book itself uses where a sum needs them: half, double, share, each, more, away. Every book it
  writes is scored for Ogden-ness and must clear Ogden v0.1's bar (68%).
- **Held out:** no sentence of the tutor is a sum of the maths book as the book writes it (its prompt and its
  answer), and no run of six words of the tutor is a run of six words of a book sum, so the Maths page stays a
  test of what was learnt, not of a sentence seen.
- **Deterministic:** the same seed writes the same lessons.
"""

from __future__ import annotations

import csv
import random
import re

from thorp import paths

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = {20: "twenty", 30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety"}
PEOPLE = [("man", "he", "his"), ("boy", "he", "his"), ("girl", "she", "her"), ("woman", "she", "her")]
PLURAL = {"man": "men", "woman": "women", "boy": "boys", "girl": "girls"}
THINGS = ["apples", "eggs", "sheep", "books", "nuts", "stones", "cows", "birds", "boxes", "cups", "pins", "sticks"]


def word(n: int) -> str:
    """A number in words, nought to a hundred: 'twenty-four', 'a hundred'."""
    if n < 20:
        return ONES[n]
    if n == 100:
        return "a hundred"
    t, o = divmod(n, 10)
    return TENS[t * 10] + (f"-{ONES[o]}" if o else "")


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------- each chapter's lessons, as sentences


def counting_on(rng: random.Random) -> list[str]:
    a = rng.randint(0, 90)
    n = rng.randint(4, 9)
    run = ", ".join(word(a + i) for i in range(min(n, 100 - a + 1)))
    return [cap(run) + ".", f"After {word(a + 1)} comes {word(a + 2)}." if a + 2 <= 100 else f"After {word(a)} comes {word(a + 1)}."]


def counting_back(rng: random.Random) -> list[str]:
    a = rng.randint(8, 100)
    n = rng.randint(4, 9)
    run = ", ".join(word(a - i) for i in range(min(n, a + 1)))
    return [cap(run) + ".", f"Before {word(a - 1)} comes {word(a - 2)}."]


def adding(rng: random.Random) -> list[str]:
    a, b = rng.randint(1, 10), rng.randint(1, 10)
    frames = [f"{cap(word(a))} and {word(b)} make {word(a + b)}.", f"Put {word(a)} and {word(b)} together, and you have {word(a + b)}.",
              f"{cap(word(a))} added to {word(b)} is {word(a + b)}.", f"If you have {word(a)} and you get {word(b)}, you have {word(a + b)}."]  # fmt: skip
    return rng.sample(frames, 2)


def taking_away(rng: random.Random) -> list[str]:
    b = rng.randint(1, 10)
    a = rng.randint(b + 1, 20)
    frames = [f"Take {word(b)} from {word(a)}, and there are {word(a - b)}.", f"{cap(word(a))} with {word(b)} taken away is {word(a - b)}.",
              f"If you have {word(a)} and you give {word(b)} away, you have {word(a - b)}.", f"From {word(a)} take {word(b)}: {word(a - b)} are left."]  # fmt: skip
    return rng.sample(frames, 2)


def times(rng: random.Random) -> list[str]:
    a, b = rng.randint(1, 10), rng.randint(1, 10)
    frames = [f"{cap(word(a))} times {word(b)} make {word(a * b)}.", f"{cap(word(a))} times {word(b)} is {word(a * b)}.",
              f"{cap(word(a))} groups of {word(b)} make {word(a * b)}."]  # fmt: skip
    return rng.sample(frames, 2)


def sharing(rng: random.Random) -> list[str]:
    k, each = rng.randint(2, 6), rng.randint(1, 6)
    n, (who, _, _) = k * each, rng.choice(PEOPLE)
    thing = rng.choice(THINGS)
    frames = [f"Share {word(n)} {thing} equally among {word(k)} {PLURAL[who]}, and each {who} gets {word(each)}.",
              f"{cap(word(n))} {thing} put into {word(k)} equal parts give {word(each)} in a part.",
              f"{cap(word(n))} shared among {word(k)} is {word(each)} each."]  # fmt: skip
    return rng.sample(frames, 2)


def halves(rng: random.Random) -> list[str]:
    a = rng.randint(1, 25)
    frames = [f"Half of {word(2 * a)} is {word(a)}.", f"Two times {word(a)} is {word(2 * a)}.", f"Double {word(a)} is {word(2 * a)}.",
              f"{cap(word(2 * a))} is two times {word(a)}, so half of {word(2 * a)} is {word(a)}."]  # fmt: skip
    return rng.sample(frames, 2)


def story_one(rng: random.Random) -> list[str]:
    (who, he, his), thing = rng.choice(PEOPLE), rng.choice(THINGS)
    a, b = rng.randint(2, 12), rng.randint(1, 8)
    if rng.random() < 0.5:
        return [f"A {who} has {word(a)} {thing}.", f"{cap(he)} gets {word(b)} more.", f"Now {he} has {word(a + b)}."]
    a = max(a, b + 1)
    return [f"A {who} has {word(a)} {thing}.", f"{cap(he)} gives {word(b)} away.", f"Now {he} has {word(a - b)}."]


def story_two(rng: random.Random) -> list[str]:
    (who, he, his), thing = rng.choice(PEOPLE), rng.choice(THINGS)
    a, b, c = rng.randint(2, 10), rng.randint(1, 8), rng.randint(1, 6)
    c = min(c, a + b - 1)
    first = rng.random() < 0.5
    if first:
        return [f"A {who} has {word(a)} {thing}.", f"{cap(he)} gets {word(b)} more, and then {he} gives {word(c)} away.",
                f"First {he} has {word(a + b)}, then {word(a + b - c)}.", f"Now {he} has {word(a + b - c)}."]  # fmt: skip
    return [f"A {who} has {word(a)} {thing}.", f"{cap(he)} gets {word(b)} more, and then {he} gives {word(c)} away.", f"Now {he} has {word(a + b - c)}."]


CHAPTERS = [counting_on, counting_back, adding, taking_away, times, sharing, halves, story_one, story_two]


# ---------------------------------------------------------------- the held-out book


def _norm(s: str) -> list[str]:
    return re.findall(r"[a-z]+(?:-[a-z]+)?", s.lower())


def book_sums() -> tuple[set[str], set[tuple[str, ...]]]:
    """The maths book's sums as sentences (prompt and answer) and their runs of six words: what the tutor must not
    write (ships/lists/tricks/maths-book.csv)."""
    whole, sixes = set(), set()
    p = paths.resolve("lists/tricks/maths-book.csv")
    if not p.exists():
        return whole, sixes
    for r in csv.DictReader(p.open(encoding="utf-8")):
        w = _norm(f"{r['prompt']} {r['answer']}")
        whole.add(" ".join(w))
        sixes |= {tuple(w[i : i + 6]) for i in range(max(0, len(w) - 5))}
    return whole, sixes


def held_out(text: str, whole: set[str], sixes: set[tuple[str, ...]]) -> bool:
    """True when a lesson would give a book sum away: it contains one whole, or a run of six of its words."""
    w = _norm(text)
    joined = " ".join(w)
    if any(s in joined for s in whole):
        return True
    return any(tuple(w[i : i + 6]) in sixes for i in range(max(0, len(w) - 5)))


def lessons(n: int, seed: int = 1830) -> list[str]:
    """`n` lessons, each a short paragraph from one chapter, the chapters in turn (De Morgan's order), none giving a
    book sum away."""
    rng = random.Random(f"de-morgan-tutor:{seed}")
    whole, sixes = book_sums()
    out, tries = [], 0
    while len(out) < n and tries < n * 20:
        tries += 1
        ch = CHAPTERS[len(out) % len(CHAPTERS)]
        sents = ch(rng) + ch(rng)  # two exercises from the chapter: a lesson
        text = " ".join(sents)
        if held_out(text, whole, sixes):
            continue
        out.append(text)
    return out
