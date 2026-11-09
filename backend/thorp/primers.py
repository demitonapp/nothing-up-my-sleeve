"""The two primers of the four positions at the 1m (DECISIONS.md, "Four positions at the 1m"; the chapters approved by
Justin, 2026-11-08: "Approve the chapters"; "i'll take your recs"; the draft is ships/plans/four-positions-primers-draft.md):

- **Plato's primer (metaphysics)**: seven chapters, after Aristotle, Hume, Berkeley, Plato and Spinoza.
- **Francis's primer (empirical knowledge)**: eight chapters, after Hume, Mill and Bacon.

A primer has the maths book's shape (scripts/make_maths_book.py): chapters in a teaching order, each a sentence that
stops where one word decides it, with the answer and the rival (the mistake a learner makes). Strict Basic English:
`logic_tutor.not_basic` must pass every sentence (a case that fails is dropped, never loosened). A deterministic
generator from fixed frames and word lists: no model's text.

**Held out.** In every chapter the cases are cut in two by their place in the list (every third case is the test's) and
the **subject words of a chapter's test cases (`held_out_words`) are never used in that chapter's reading** (a word may be a test subject in one chapter and read in another: the held-out thing is the case).
The test items are those cases written out; the reading is passages of three lesson sentences from the other cases
under a short opening with two names. `check_passage` refuses a passage that has a held-out word, a word that is not
strict Basic English, or a full test sentence.

**Recommendations taken** (Justin: "i'll take your recs"): the common-sense answers stay, and the "seems and is" chapter is
scored **by itself** beside the rest, so the one contestable chapter cannot decide a verdict; each ship's share of its
reading is 10% (Diderot's matched 10% is random other books); the Ogden bar for the specialist books stays 68%.

    uv run --project backend python backend/scripts/make_primers.py        # test items, passages, books
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from thorp import logic_tutor as lt

NAMES = ("Tom", "Ann", "Jack", "Mary", "Paul", "Jane", "Peter", "Ruth", "John", "Kate", "Sam", "Lucy")
OPENINGS = (
    "At the table are {a} and {b}.", "By the fire sit {a} and {b}.", "In the room are {a} and {b}.", "In the garden are {a} and {b}.",
    "On the road are {a} and {b}.", "With {a} in the house is {b}.", "Here {a} says to {b}:", "Here {b} is with {a}.",
)  # fmt: skip
HELD_OUT_EVERY = 3  # every third case is the test's


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


@dataclass(frozen=True)
class Chapter:
    key: str
    title: str
    about: str  # what the rival is
    source: str
    cases: tuple  # tuples whose first field is the subject word; the last field is the frame
    frame: object = field(repr=False, compare=False, default=None)  # case -> (prompt, answer, rival)


# ---- Plato: metaphysics --------------------------------------------------------------------------------------
def _kinds(c):
    return f"A {c[0]} is a kind of", c[1], c[2]


def _qualities(c):
    return f"The {c[0]} is {c[2]} and {c[3]}. The {c[0]} is a thing. {cap(c[2])} is a", "quality", "thing"


def _same(c):
    if c[1] == "thing":
        return f"Two {c[0]}s are the same in look. They are not the same {c[0]}. One {c[0]} is the same as", "itself", "the other"
    return f"Two {c[0]}s have the same name. They are not the same {c[0]}. A {c[0]} is the same as", "himself" if c[0] == "boy" else "herself", "the name"


def _seems(c):
    if c[1] == "water":
        return f"A {c[0]} in water seems bent. The {c[0]} is", "straight", "bent"
    if c[1] == "eye":
        return f"The {c[0]} seems small to the eye. The {c[0]} is", "great", "small"
    return f"A man seems kind. He {c[0]}. He is", "bad", "kind"


def _many(c):
    if c[-1] == "A":
        return f"Some {c[1]} are in the {c[2]}. {cap(c[0])} is the name of a kind. The kind is not in the", c[2], "name"
    return f"A white {c[0]}, a white {c[1]} and a white {c[2]} are three things. The thing they have in common is", "white", "three"


def _cause(c):
    if c[-1] == "A":
        return f"A {c[0]} is let go and it comes down. The weight is the cause of the", "fall", c[0]
    return f"{cap(c[0])} is two times {c[1]}. That is the reason why {c[0]} is even. It is not a", "cause", "number"


def _must(c):
    if c[-1] == "A":
        return f"{cap(c[1])}. It has to be so. The {c[0]} may come or not. The {c[0]} is a thing that", "may be", "has to be"
    return f"The {c[0]} may come or not. {cap(c[1])}. That {c[1]} is a thing that", "has to be", "may be"


PLATO = (
    Chapter("kinds", "Kinds", "the rival is a quality the kind has", "after Aristotle's Categories (idea only: the text fails the period gate)",
            tuple(c + ("A",) for c in (
                ("dog", "animal", "brown"), ("cat", "animal", "soft"), ("horse", "animal", "great"), ("cow", "animal", "white"),
                ("sheep", "animal", "soft"), ("bird", "animal", "small"), ("fish", "animal", "cold"), ("rat", "animal", "grey"),
                ("pig", "animal", "pink"), ("duck", "animal", "white"), ("snake", "animal", "long"), ("monkey", "animal", "quick"),
                ("apple", "fruit", "red"), ("orange", "fruit", "round"), ("pear", "fruit", "green"), ("plum", "fruit", "blue"),
                ("hammer", "instrument", "iron"), ("knife", "instrument", "sharp"), ("needle", "instrument", "sharp"), ("saw", "instrument", "sharp"),
                ("tree", "plant", "green"), ("grass", "plant", "green"), ("flower", "plant", "sweet"), ("spoon", "instrument", "bright"))), _kinds),
    Chapter("things-and-qualities", "Things and qualities", "the rival calls the quality a thing", "after Aristotle's Categories and Locke's Essay",
            tuple(c + ("A",) for c in (
                ("stone", "x", "hard", "cold"), ("sugar", "x", "sweet", "white"), ("iron", "x", "hard", "cold"), ("milk", "x", "white", "cold"),
                ("snow", "x", "cold", "white"), ("ice", "x", "cold", "hard"), ("wool", "x", "soft", "warm"), ("glass", "x", "hard", "clear"),
                ("fire", "x", "bright", "warm"), ("bread", "x", "soft", "sweet"), ("silk", "x", "soft", "smooth"), ("salt", "x", "white", "sharp"),
                ("rubber", "x", "soft", "black"), ("gold", "x", "hard", "yellow"), ("oil", "x", "smooth", "warm"), ("rope", "x", "long", "strong"),
                ("cloth", "x", "soft", "warm"), ("wood", "x", "hard", "brown"), ("paper", "x", "white", "smooth"), ("steel", "x", "hard", "bright"))), _qualities),
    Chapter("same-and-like", "Same and like", "the rival takes the other thing, or the name, for the same", "after Hume's Treatise (identity), pg62856",
            tuple(c for c in (
                ("egg", "thing"), ("apple", "thing"), ("book", "thing"), ("cup", "thing"), ("hat", "thing"), ("box", "thing"), ("pen", "thing"),
                ("nut", "thing"), ("ball", "thing"), ("bag", "thing"), ("bell", "thing"), ("key", "thing"), ("pin", "thing"), ("bottle", "thing"),
                ("bowl", "thing"), ("boy", "name"), ("girl", "name"), ("boy", "name"), ("girl", "name"), ("stone", "thing"))), _same),
    Chapter("seems-and-is", "Seems and is", "the rival says what it seems", "after Berkeley's Three Dialogues (pg4724) and Plato's Republic",
            tuple(c for c in (
                ("stick", "water"), ("rod", "water"), ("pipe", "water"), ("line", "water"), ("spoon", "water"), ("oar", "water"),
                ("sun", "eye"), ("star", "eye"), ("moon", "eye"), ("mountain", "eye"), ("house", "eye"), ("tree", "eye"),
                ("takes money from the poor", "man"), ("keeps the food from the child", "man"), ("puts a poor man out in the cold", "man"),
                ("takes the bread from a boy", "man"), ("puts the dog out in the rain", "man"), ("says what is not so", "man"))), _seems),
    Chapter("one-and-many", "One and many", "the rival puts the kind in the place, or counts it", "after Plato's Republic (the kind and its many things)",
            (("horse", "horses", "field", "A"), ("cow", "cows", "field", "A"), ("bird", "birds", "tree", "A"), ("fish", "fish", "sea", "A"),
             ("sheep", "sheep", "field", "A"), ("boy", "boys", "room", "A"), ("dog", "dogs", "street", "A"), ("cat", "cats", "house", "A"),
             ("duck", "ducks", "water", "A"), ("pig", "pigs", "field", "A"), ("girl", "girls", "garden", "A"), ("monkey", "monkeys", "tree", "A"),
             ("horse", "cloud", "cloth", "B"), ("house", "flower", "cup", "B"), ("book", "hat", "box", "B"), ("stone", "egg", "pen", "B"),
             ("wall", "snow", "milk", "B"), ("bird", "paper", "salt", "B"), ("bell", "sheep", "sugar", "B"), ("fish", "rope", "cloth", "B")), _many),
    Chapter("cause-and-reason", "Cause and reason", "the rival names the thing, or a cause for a reason", "after Hume's Treatise (cause) and Spinoza's Ethics (pg919 to pg975)",
            (("stone", "A"), ("ball", "A"), ("book", "A"), ("cup", "A"), ("nut", "A"), ("hammer", "A"), ("pen", "A"), ("key", "A"), ("bell", "A"),
             ("bottle", "A"), ("bag", "A"), ("pin", "A"), ("four", "two", "B"), ("six", "three", "B"), ("eight", "four", "B"), ("ten", "five", "B"),
             ("twelve", "six", "B"), ("fourteen", "seven", "B"), ("sixteen", "eight", "B"), ("eighteen", "nine", "B")), _cause),
    Chapter("has-to-be-and-may-be", "Has to be and may be", "the rival says the other", "after Spinoza's Ethics (what follows of itself, and what is by chance)",
            (("rain", "two and two make four", "A"), ("wind", "three and three make six", "A"), ("snow", "five and five make ten", "A"),
             ("sun", "a circle has no point", "A"), ("cloud", "four and four make eight", "A"), ("storm", "six and six make twelve", "A"),
             ("rain", "two and two make four", "B"), ("wind", "three and three make six", "B"), ("snow", "five and five make ten", "B"),
             ("cloud", "a circle has no point", "B"), ("sun", "four and four make eight", "B"), ("storm", "six and six make twelve", "B"),
             ("rain", "a circle has no point", "A"), ("wind", "five and five make ten", "B"), ("snow", "three and three make six", "A"), ("sun", "six and six make twelve", "B"),
             ("cloud", "two and two make four", "A"), ("wind", "four and four make eight", "B")), _must),
)


# ---- Francis: empirical knowledge ----------------------------------------------------------------------------
def _same_cause(c):
    if c[-1] == "A":
        return f"Every time a {c[0]} is let go, it comes down. So the {c[0]} I let go now will", "come down", "go up"
    return f"The {c[0]} comes up every day. So tomorrow the {c[0]} will", "come up", "not come up"


def _one_change(c):
    return (f"Two {c[0]}s have the same {c[1]} and the same {c[2]}. One has {c[3]} and the other has no {c[3]}. "
            f"The one with {c[3]} {c[4]}. The cause is the"), c[3], c[1]


def _agreement(c):
    return (f"{cap(c[0])} {c[1]}s had {c[2]}. Every one of the {c[0]} had the {c[3]}. Some had the {c[4]} and some did not. "
            f"The cause of the {c[2]} is the"), c[3], c[4]


def _more(c):
    return f"The nearer the {c[2]} is to the {c[0]}, the greater the {c[1]}. The {c[1]} comes from the", c[0], c[2]


def _against(c):
    if c[-1] == "A":
        return f"Every {c[0]} seen was {c[1]}. Then a {c[0]} that was not {c[1]} was seen. The saying, every {c[0]} is {c[1]}, is", "false", "true"
    if c[-1] == "B":
        return f"A man says: no {c[0]} has {c[1]} legs. A {c[0]} with {c[1]} legs is seen. The man's saying is", "false", "true"
    return f"A man says: some {c[0]} has {c[1]} legs. A {c[0]} with {c[1]} legs is seen. The man's saying is", "true", "false"


def _how_much(c):
    return f"{cap(c[3])} {c[0]} {c[1]}s were seen. The boy says every {c[1]} is {c[0]}. He has seen only", c[3], "all"


def _look(c):
    if c[-1] == "A":
        return f"A man says the {c[0]} is out because the {c[1]} is gone. To see if it is so, look at the", c[1], "wall"
    return f"A man says the {c[0]} is {c[1]}. To see if it is so, use the", c[2], c[3]


def _seen(c):
    if c[-1] == "A":
        return f"A boy saw the {c[0]} with his eye. A girl was given word of the {c[0]} by a man. The word to take is the word of the", "boy who saw it", "girl"
    return f"{cap(c[0])} boys say they saw it. One boy says he did not. A man who would be certain goes and", "looks", "talks"


FRANCIS = (
    Chapter("same-cause-same-effect", "Same cause, same effect", "the rival is the opposite effect", "after Hume's Treatise, pg62856",
            (("stone", "A"), ("ball", "A"), ("book", "A"), ("cup", "A"), ("nut", "A"), ("hammer", "A"), ("pen", "A"), ("key", "A"), ("bell", "A"),
             ("bottle", "A"), ("bag", "A"), ("pin", "A"), ("sun", "B"), ("moon", "B"), ("star", "B")), _same_cause),
    Chapter("one-change-at-a-time", "One change at a time", "the rival is a thing both had", "after Mill's System of Logic, pg27942 (the method of difference)",
            (("plant", "earth", "water", "light", "has the greater growth"), ("fire", "wood", "paper", "wind", "goes out"), ("seed", "earth", "water", "heat", "comes up"),
             ("tree", "earth", "air", "water", "has the greater growth"), ("flower", "earth", "air", "light", "has the greater growth"), ("fire", "air", "wood", "water", "goes out"),
             ("plant", "air", "light", "water", "has the greater growth"), ("seed", "air", "earth", "water", "comes up"), ("tree", "air", "water", "light", "has the greater growth"),
             ("fire", "paper", "air", "water", "goes out"), ("flower", "air", "earth", "water", "has the greater growth"), ("seed", "earth", "air", "heat", "comes up")), _one_change),
    Chapter("what-is-always-there", "What is always there", "the rival is a thing only some had", "after Mill's System of Logic (the method of agreement)",
            (("five", "boy", "pain", "fish", "bread"), ("six", "girl", "pain", "milk", "meat"), ("four", "boy", "pain", "meat", "bread"), ("seven", "girl", "pain", "fish", "milk"),
             ("eight", "boy", "pain", "milk", "bread"), ("nine", "girl", "pain", "meat", "fish"), ("ten", "boy", "pain", "bread", "milk"), ("three", "girl", "pain", "fish", "meat"),
             ("five", "girl", "pain", "meat", "milk"), ("six", "boy", "pain", "fish", "bread"), ("four", "girl", "pain", "bread", "fish"), ("seven", "boy", "pain", "milk", "meat")), _agreement),
    Chapter("more-and-more", "More and more", "the rival is the thing that is near", "after Mill's System of Logic (concomitant variations)",
            (("fire", "heat", "hand"), ("bell", "sound", "ear"), ("sun", "heat", "face"), ("sea", "noise", "ear"), ("wind", "cold", "face"), ("flower", "smell", "nose"),
             ("fire", "light", "eye"), ("fire", "smoke", "nose"), ("bell", "noise", "ear"), ("sun", "light", "eye"), ("snow", "cold", "hand"), ("ice", "cold", "hand")), _more),
    Chapter("one-case-against", "One case against", "the rival is the other answer", "after Bacon's Novum Organum, pg45988 (aphorism 46: one case against a saying)",
            (("sheep", "white", "A"), ("bird", "small", "A"), ("horse", "brown", "A"), ("cow", "white", "A"), ("dog", "black", "A"), ("cat", "soft", "A"),
             ("pig", "pink", "A"), ("duck", "white", "A"), ("bird", "four", "B"), ("fish", "four", "B"), ("man", "four", "B"), ("snake", "four", "B"),
             ("bird", "four", "C"), ("dog", "six", "C"), ("horse", "five", "C"), ("cat", "six", "C"), ("cow", "five", "C"), ("pig", "six", "C")), _against),
    Chapter("how-much-to-say", "How much to say", "the rival says all", "after Bacon's Novum Organum (the hasty saying from a few cases)",
            (("white", "bird", "birds", "three"), ("black", "horse", "horses", "four"), ("red", "apple", "apples", "five"), ("brown", "dog", "dogs", "three"),
             ("white", "sheep", "sheep", "four"), ("black", "cat", "cats", "five"), ("green", "bird", "birds", "four"), ("grey", "horse", "horses", "three"),
             ("white", "duck", "ducks", "five"), ("pink", "pig", "pigs", "three"), ("brown", "cow", "cows", "four"), ("black", "dog", "dogs", "five")), _how_much),
    Chapter("what-to-look-at", "What to look at", "the rival is the wrong place or sense", "after Bacon's Novum Organum (the test by experiment) and Mill",
            (("fire", "wood", "A"), ("fire", "paper", "A"), ("water", "warm", "hand", "foot", "B"), ("light", "bright", "eye", "ear", "B"), ("bell", "loud", "ear", "eye", "B"),
             ("stone", "hard", "hand", "ear", "B"), ("sugar", "sweet", "mouth", "eye", "B"), ("flower", "sweet", "nose", "ear", "B"), ("ice", "cold", "hand", "eye", "B"),
             ("sea", "loud", "ear", "hand", "B"), ("fire", "oil", "A"), ("sun", "bright", "eye", "mouth", "B")), _look),
    Chapter("seen-and-given", "Seen and given", "the rival is the word of the one who was told", "after Bacon's Novum Organum (the witness)",
            (("fire", "A"), ("fight", "A"), ("race", "A"), ("fall", "A"), ("ten", "B"), ("nine", "B"), ("eight", "B"), ("seven", "B"), ("six", "B"), ("five", "B"), ("four", "B"), ("twelve", "B")), _seen),
)

PRIMERS = {"plato": PLATO, "francis": FRANCIS}
TITLES = {"plato": "Plato's primer (metaphysics)", "francis": "Francis's primer (empirical knowledge)"}


def _basic(prompt: str, *tails: str) -> bool:
    return all(not lt.not_basic(f"{prompt} {t}.", ()) for t in tails)


def valid_cases(who: str) -> list[tuple[Chapter, int, tuple]]:
    """(chapter, place in its list, case) for every case whose sentences are strict Basic English, by chapter order."""
    out = []
    for ch in PRIMERS[who]:
        for i, c in enumerate(ch.cases):
            p, a, r = ch.frame(c)
            if _basic(p, a, r):
                out.append((ch, i, c))
    return out


def is_test(i: int) -> bool:
    return i % HELD_OUT_EVERY == HELD_OUT_EVERY - 1


def held_out_words(who: str) -> dict[str, frozenset[str]]:
    """Per chapter, the subject words of its test cases: that chapter's reading never uses them."""
    out: dict[str, set[str]] = {}
    for ch, i, c in valid_cases(who):
        if is_test(i) and " " not in c[0]:
            out.setdefault(ch.key, set()).add(c[0].lower())
    return {k: frozenset(v) for k, v in out.items()}


def test_items(who: str) -> list[dict]:
    rows, n = [], {}
    for ch, i, c in valid_cases(who):
        if not is_test(i):
            continue
        p, a, r = ch.frame(c)
        k = n[ch.key] = n.get(ch.key, -1) + 1
        rows.append({"item": f"{ch.key}-{k}", "chapter": PRIMERS[who].index(ch) + 1, "key": ch.key, "title": ch.title, "about": ch.about,
                     "prompt": p, "answer": a, "rival": r, "source": ch.source})  # fmt: skip
    return rows


def read_cases(who: str) -> dict[str, list[tuple[Chapter, tuple]]]:
    """Per chapter, the cases the reading may use: not the test's, and none that uses one of the chapter's held-out words."""
    held = held_out_words(who)
    out: dict[str, list] = {}
    for ch, i, c in valid_cases(who):
        if is_test(i):
            continue
        p, a, r = ch.frame(c)
        words = {w.lower() for w in re.findall(r"[A-Za-z]+", f"{p} {a}")}
        if words & held.get(ch.key, frozenset()):
            continue
        out.setdefault(ch.key, []).append((ch, c))
    return out


def check_passage(who: str, text: str, chapter: str, held: dict | None = None, tests: frozenset[str] | None = None) -> list[str]:
    """Why a passage of this chapter is refused: not strict Basic English, one of the chapter's held-out words, or a whole
    test sentence. Empty: it may be read."""
    held = held_out_words(who) if held is None else held
    why = []
    if lt.not_basic(text, ()):
        why.append("not strict Basic English")
    if {w.lower() for w in re.findall(r"[A-Za-z]+", text)} & held.get(chapter, frozenset()):
        why.append("a held-out word")
    if tests is None:
        tests = frozenset(f"{r['prompt']} {r['answer']}." for r in test_items(who))
    if any(t in text for t in tests):
        why.append("a whole test sentence")
    return why


def passages(who: str, n: int, seed: int = 1) -> list[str]:
    """n distinct passages: a short opening with two names, then three lesson sentences of one chapter, whole (the
    prompt and its answer), in cases the test does not use."""
    rng = random.Random(f"primer:{who}:{seed}")
    cases = read_cases(who)
    keys = sorted(cases)
    held, tests = held_out_words(who), frozenset(f"{r['prompt']} {r['answer']}." for r in test_items(who))
    out: list[str] = []
    seen: set[str] = set()
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1
        key = rng.choice(keys)
        pool = cases[key]
        if len(pool) < 3:
            continue
        picks = rng.sample(pool, 3)
        a, b = rng.sample(NAMES, 2)
        lead = rng.choice(OPENINGS).format(a=a, b=b)
        body = " ".join(f"{ch.frame(c)[0]} {ch.frame(c)[1]}." for ch, c in picks)
        text = f"{lead} {body}"
        if text in seen or check_passage(who, text, key, held, tests):
            continue
        seen.add(text)
        out.append(text)
    return out
