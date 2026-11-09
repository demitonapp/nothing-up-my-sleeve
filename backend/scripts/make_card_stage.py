"""The card stage: a corpus written so that each passage is *for* one card, in Ogden's own 850 words (9 November,
Justin: "a data stage where each piece of content is linked to the card and tie that in with depth … the next Pan run
should be 28 layers, a data stage based on cards and able to have different card weightings and then ogden's english";
"we need to be able to compare the 300k on data taught vs taught to see which produces better chaining indicators").

The deck can be *told* to a head (the scaffold pins attention to a metric pattern) or it can be *read* into existence
by text whose only way through is the card. This script writes the second: passages in Basic English, built so that
one card is the thing that carries the next word, with the weights deciding how much of the stage each card gets.

Cards and their passages (all in the 850 words, `lists/ogden-850.txt`):

- `previous_word` — plain two-clause sentences: the card is the last token, nothing is engineered.
- `duplicate_word` — a word repeated across a clause: the copy and the repeat both carry the frame.
- `induction` — a phrase repeated across two clauses: the second copy is the only cue for the ending.
- `comparator` — two comparisons, the question asks for the extreme: order must be held, not copied.
- `mover` — a premise and a question whose answer is the premise's object: the fact must be carried to the frame.
- `bridge` — two premises with a middle term: the answer is in the first, the route only through the second.

Writes `lists/card-stage-<version>.csv` in the library's format (title, author, language, family, text), one row per
passage, the counts per card set by the weights. Deterministic: the same seed writes the same file.

    uv run --project backend python backend/scripts/make_card_stage.py --stage deck-v1 --per-card 12000
"""

from __future__ import annotations

import argparse
import csv
import itertools
import random
from pathlib import Path

# Ogden's operators and the concrete nouns a passage can be built from. Kept small and closed so every passage is
# grammatical in Basic English and shares its vocabulary with the content the stage precedes.
PEOPLE = ("the man", "the woman", "the boy", "the girl", "the father", "the mother", "the friend", "the worker",
          "the servant", "the judge", "the cook", "the farmer")  # fmt: skip
THINGS = ("box", "stone", "cup", "cloth", "brush", "hook", "cord", "plate", "bottle", "basket", "hammer", "key",
          "book", "hat", "coat", "shoe", "knife", "stick", "rope", "bell")  # fmt: skip
CONTAINERS = ("box", "basket", "cup", "bag", "bottle")
SURFACES = ("table", "floor", "shelf", "plate")
ROOMS = ("room", "house", "garden", "market", "street", "field", "boat", "train")
ADJ = ("red", "blue", "green", "white", "black", "small", "long", "short", "old", "new", "warm", "cold", "soft",
       "hard", "wide")  # fmt: skip
MOVE = ("went", "walked", "ran", "came", "turned")
DIMENSIONS = (("long", "longer", "longest"), ("short", "shorter", "shortest"),
              ("old", "older", "oldest"), ("new", "newer", "newest"),
              ("hard", "harder", "hardest"), ("soft", "softer", "softest"))  # fmt: skip


def passages(rng: random.Random, per_card: int) -> dict[str, list[str]]:
    """The card's passages: a fixed number each, every slot bound once so the sentence is about one object."""
    out: dict[str, list[str]] = {}
    seen: set[str] = set()

    def take(fn, n: int) -> list[str]:
        got: list[str] = []
        for _ in range(60 * n):
            s = fn()
            if s not in seen:
                seen.add(s)
                got.append(s)
            if len(got) >= n:
                break
        return got

    def plain():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        prep, place = rng.choice((("on", SURFACES), ("in", CONTAINERS), ("under", SURFACES)))
        return (f"the {adj} {thing} is {prep} the {rng.choice(place)} and {rng.choice(PEOPLE)} "
                f"{rng.choice(MOVE)} to the {rng.choice(ROOMS)}")

    def repeat_word():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        other = rng.choice([t for t in THINGS if t != thing])
        return (f"the {adj} {thing} and the {other} are {rng.choice(ADJ)} and {rng.choice(PEOPLE)} put them "
                f"in the {rng.choice(CONTAINERS)}")

    def two_premises():
        who = f"{rng.choice(PEOPLE)} with the {rng.choice(ADJ)} {rng.choice(THINGS)}"
        return f"{who} {rng.choice(MOVE)} to the {rng.choice(ROOMS)} and {who} came back"

    def comparison():
        dim = rng.choice(DIMENSIONS)
        a, b, c = rng.sample(PEOPLE, 3)
        thing = rng.choice(THINGS)
        return (f"{a} is {dim[1]} than {b} and {b} is {dim[1]} than {c}. which {rng.choice(('man', 'one'))} "
                f"has the {thing}, {dim[0]} or {dim[2]}?")

    def premise_question():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        prep, place = rng.choice(("on", "in", "under")), rng.choice(ROOMS + SURFACES + CONTAINERS)
        return (f"the {adj} {thing} is {prep} the {place} and {rng.choice(PEOPLE)} {rng.choice(MOVE)} to the "
                f"{rng.choice(ROOMS)}. where is the {adj} {thing}?")

    def chained():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        inner, outer = rng.choice(CONTAINERS), rng.choice(ROOMS + SURFACES)
        return (f"the {adj} {thing} is in the {inner} and the {inner} is in the {rng.choice(CONTAINERS)} on the "
                f"{outer}. where is the {adj} {thing}?")

    out["previous_word"] = take(plain, per_card)
    out["duplicate_word"] = take(repeat_word, per_card)
    out["induction"] = take(two_premises, per_card)
    out["comparator"] = take(comparison, per_card)
    out["mover"] = take(premise_question, per_card)
    out["bridge"] = take(chained, per_card)
    return out




MARK = {"premise": "<premise>", "sep": "<sep>", "question": "<question>", "answer": "<answer>", "end": "<end>"}


def marked(rng: random.Random, per_card: int) -> dict[str, list[str]]:
    """The same six families, written as marked items (9 November, v0.0.6): each passage carries the control tokens in
    the places a chaining model needs boundaries — premises, the question, the answer, the end — so the tokens are USED
    as well as declared, which is the only way they earn a gradient."""
    out: dict[str, list[str]] = {}
    seen: set[str] = set()

    def take(fn, n: int) -> list[str]:
        got = []
        for _ in range(60 * n):
            s = fn()
            if s not in seen:
                seen.add(s); got.append(s)
            if len(got) >= n:
                break
        return got

    def prem(t): return f"{MARK['premise']} {t}"

    def mover():
        thing, prep, place = rng.choice(THINGS), rng.choice(("on", "in", "under")), rng.choice(ROOMS + SURFACES + CONTAINERS)
        return f"{prem( f'the {thing} is {prep} the {place}' )} {MARK['question']} where is the {thing}? {MARK['answer']} {prep} the {place} {MARK['end']}"

    def bridge():
        thing, inner, outer = rng.choice(THINGS), rng.choice(CONTAINERS), rng.choice(ROOMS + SURFACES)
        return (f"{prem(f'the {thing} is in the {inner}')} {MARK['sep']} {prem(f'the {inner} is in the {outer}')} "
                f"{MARK['question']} where is the {thing}? {MARK['answer']} in the {outer} {MARK['end']}")

    def comparison():
        dim = rng.choice(DIMENSIONS)
        a, b, c = rng.sample(PEOPLE, 3)
        return (f"{prem(f'{a} is {dim[1]} than {b}')} {MARK['sep']} {prem(f'{b} is {dim[1]} than {c}')} "
                f"{MARK['question']} which is the {dim[2]}? {MARK['answer']} {a} {MARK['end']}")

    def two_premises():
        who = f"{rng.choice(PEOPLE)} with the {rng.choice(ADJ)} {rng.choice(THINGS)}"
        return (f"{prem(f'{who} {rng.choice(MOVE)} to the {rng.choice(ROOMS)}')} {MARK['sep']} "
                f"{prem(f'{who} came back')} {MARK['question']} who came back? {MARK['answer']} {who} {MARK['end']}")

    def plain():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        prep, place = rng.choice((("on", SURFACES), ("in", CONTAINERS), ("under", SURFACES)))
        return (f"{prem(f'the {adj} {thing} is {prep} the {rng.choice(place)}')} {MARK['question']} "
                f"where is the {adj} {thing}? {MARK['answer']} {prep} the {rng.choice(place)} {MARK['end']}")

    def repeat_word():
        thing, adj = rng.choice(THINGS), rng.choice(ADJ)
        other = rng.choice([t for t in THINGS if t != thing])
        return (f"{prem(f'the {adj} {thing} and the {other} are {rng.choice(ADJ)}')} {MARK['question']} "
                f"what is {adj}? {MARK['answer']} the {thing} and the {other} {MARK['end']}")

    out["previous_word"] = take(plain, per_card)
    out["duplicate_word"] = take(repeat_word, per_card)
    out["induction"] = take(two_premises, per_card)
    out["comparator"] = take(comparison, per_card)
    out["mover"] = take(mover, per_card)
    out["bridge"] = take(bridge, per_card)
    return out




def write_books(deck: dict, stage: str, books: int = 200, log=print) -> int:
    """Write the deck as `local:` books and a list of refs — the only form the trainer's resolver reads (9 November: the
    first control arms planned 0 tokens because the passages sat in the text column, so every one was looked up as a
    Gutenberg title). One book per chunk, the passages joined by blank lines."""
    import hashlib

    from thorp import manifest, paths

    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    passages = [p for ps in deck.values() for p in ps]
    per_book = -(-len(passages) // books)
    n = 0
    for i in range(books):
        chunk = passages[i * per_book : (i + 1) * per_book]
        if not chunk:
            break
        bid = f"card-stage-{stage}-{i + 1:03d}"
        text = "\n\n".join(chunk) + "\n"
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        manifest.upsert(manifest.Book(
            id=bid, source="local", title=f"The card stage, {stage}, book {i + 1}",
            author="Thorp's card stage", language="en", family="Germanic",
            text=f"derived: card stage {stage}", chars=len(text), bytes=len(data),
            sha1=hashlib.sha1(data).hexdigest(), fetched_at="", set="recipe",
        ))  # fmt: skip
        rows.append({"title": f"The card stage, {stage}, book {i + 1}", "author": "Thorp's card stage",
                     "language": "en", "family": "Germanic", "text": f"local:{bid}"})  # fmt: skip
        n += 1
    f = paths.resolve("lists") / f"card-stage-{stage}-books.csv"
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    log(f"wrote {n} books and {f.name}")
    return n


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="make_card_stage")
    p.add_argument("--stage", default="deck-v1", help="the file is lists/card-stage-<stage>.csv")
    p.add_argument("--per-card", type=int, default=12000, help="passages per card (the weights are the relative counts)")
    p.add_argument("--seed", type=int, default=1859)
    p.add_argument("--sample", type=int, default=0, help="print this many passages per card instead of writing")
    p.add_argument("--marked", action="store_true", help="write the marked items (control tokens) instead of the plain ones")
    p.add_argument("--books", type=int, default=0, help="also write the deck as N local books + a list of refs (what the trainer reads)")
    a = p.parse_args(argv)
    rng = random.Random(a.seed)
    d = marked(rng, a.per_card) if a.marked else passages(rng, a.per_card)
    if a.sample:
        for card, ss in d.items():
            print(f"--- {card} ({len(ss)})")
            for s in ss[: a.sample]:
                print("   ", s)
        return 0
    from thorp import paths

    f = Path(paths.resolve("lists")) / f"card-stage-{a.stage}.csv"
    n = 0
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["title", "author", "language", "family", "text"])
        for card, ss in d.items():
            for i, s in enumerate(ss):
                w.writerow([f"the {card} stage, {i + 1}", "Thorp's card stage", "en", "Germanic", s])
                n += 1
    print(f"wrote {n} passages to {f} ({n * 12:,} tokens or so)")
    if a.books:
        write_books(d, a.stage, books=a.books)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
