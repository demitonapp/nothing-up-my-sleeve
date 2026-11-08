"""The maths book (Justin, 2026-11-08: "a tab for maths and the different levels of maths ... how good at maths
compared to an ogden(y) textbook would teach maths"): nine chapters in the order a Basic English arithmetic primer
teaches them, each sum in its plain words ("Two and three make"), its answer a number word, and beside it the
rival, the answer of the mistake a learner makes at that chapter (counting the wrong way, adding where the sum
says times, stopping after one step of two). Eight sums a chapter, deterministic from the seed.

    uv run --project backend python backend/scripts/make_maths_book.py      # writes ships/lists/tricks/maths-book.csv
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

WORDS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen twenty").split() + [
    f"twenty-{w}" for w in "one two three four five six seven eight nine".split()] + ["thirty"]  # fmt: skip
PEOPLE = [("man", "he"), ("boy", "he"), ("girl", "she"), ("woman", "she")]
THINGS = ["apples", "eggs", "sheep", "books", "nuts", "stones", "cows", "birds"]

CHAPTERS = [
    ("counting-on", "Counting on", "the next number after a run of four; the rival is one already said"),
    ("counting-back", "Counting back", "the next number down a run of four; the rival is one already said"),
    ("adding", "Adding", "two small numbers put together; the rival multiplies them"),
    ("taking-away", "Taking away", "a small number taken from a bigger; the rival adds them"),
    ("times", "Times", "a small number taken so many times; the rival adds them"),
    ("sharing", "Sharing", "a number shared equally; the rival takes the parts away"),
    ("halves", "Halves and doubles", "half of a number, or two times it; the rival does the other"),
    ("story-one", "Stories, one step", "a person gets more or gives some away; the rival does the other"),
    ("story-two", "Stories, two steps", "gets some, then gives some away; the rival stops after the first step"),
]


def w(n: int) -> str:
    return WORDS[n]


def sums(key: str, rng: random.Random) -> list[tuple[str, int, int]]:
    """(the sum's words up to its answer, the answer, the rival) for one chapter: eight, all different."""
    out: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    tries = 0
    while len(out) < 8 and tries < 2000:
        tries += 1
        if key == "counting-on":
            a = rng.randint(1, 15)
            text, ans, riv = ", ".join(w(a + i).capitalize() if i == 0 else w(a + i) for i in range(4)) + ",", a + 4, a + 2
        elif key == "counting-back":
            a = rng.randint(6, 20)
            text, ans, riv = ", ".join(w(a - i).capitalize() if i == 0 else w(a - i) for i in range(4)) + ",", a - 4, a - 2
        elif key == "adding":
            a, b = rng.randint(2, 6), rng.randint(2, 6)
            text, ans, riv = f"{w(a).capitalize()} and {w(b)} make", a + b, a * b
        elif key == "taking-away":
            b = rng.randint(2, 6)
            a = rng.randint(b + 2, 12)
            text, ans, riv = f"Take {w(b)} from {w(a)}, and there are", a - b, a + b
        elif key == "times":
            a, b = rng.randint(2, 5), rng.randint(3, 6)
            text, ans, riv = f"{w(a).capitalize()} times {w(b)} make", a * b, a + b
        elif key == "sharing":
            k, each = rng.randint(2, 4), rng.randint(2, 5)
            n, (who, _) = k * each, rng.choice(PEOPLE)
            text, ans, riv = f"Share {w(n)} {rng.choice(THINGS)} equally among {w(k)} {who}s, and each {who} gets", each, n - k
        elif key == "halves":
            a = rng.randint(2, 10)
            if rng.random() < 0.5:
                text, ans, riv = f"Half of {w(2 * a)} is", a, 4 * a
            else:
                text, ans, riv = f"Two times {w(a)} is", 2 * a, a // 2 if a % 2 == 0 else a + 1
        elif key == "story-one":
            (who, he), thing = rng.choice(PEOPLE), rng.choice(THINGS)
            a, b = rng.randint(3, 9), rng.randint(2, 5)
            if rng.random() < 0.5:
                text, ans, riv = f"A {who} has {w(a)} {thing}. {he.capitalize()} gets {w(b)} more. Now {he} has", a + b, abs(a - b)
            else:
                a = max(a, b + 2)
                text, ans, riv = f"A {who} has {w(a)} {thing}. {he.capitalize()} gives {w(b)} away. Now {he} has", a - b, a + b
        else:  # story-two
            (who, he), thing = rng.choice(PEOPLE), rng.choice(THINGS)
            a, b, c = rng.randint(2, 7), rng.randint(2, 5), rng.randint(1, 3)
            text = f"A {who} has {w(a)} {thing}. {he.capitalize()} gets {w(b)} more, and then {he} gives {w(c)} away. Now {he} has"
            ans, riv = a + b - c, a + b
        if ans == riv or not (0 <= ans < len(WORDS) and 0 <= riv < len(WORDS)) or text in seen:
            continue
        seen.add(text)
        out.append((text, ans, riv))
    return out


def main(seed: int = 1850) -> int:
    rng = random.Random(seed)
    out = Path(__file__).resolve().parents[2] / "ships" / "lists" / "tricks" / "maths-book.csv"
    rows = []
    for i, (key, title, about) in enumerate(CHAPTERS, 1):
        for j, (text, ans, riv) in enumerate(sums(key, rng)):
            rows.append({"item": f"{key}-{j}", "chapter": i, "key": key, "title": title, "about": about,
                         "prompt": text, "answer": w(ans), "rival": w(riv)})  # fmt: skip
    with out.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    print(f"{out}: {len(rows)} sums in {len(CHAPTERS)} chapters (seed {seed})")
    return 0


if __name__ == "__main__":
    sys.exit(main(*(int(a) for a in sys.argv[1:])))
