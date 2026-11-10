"""The logic tutor (DECISIONS.md, "The logic tutor, pre-registered", 2026-11-07 19:58, Justin: "Pre-register it").

Chaining two facts, taught to an Ogden speller as text, written two ways from the same skeletons:

- **Skeletons** (`skeletons`): two facts about invented things and the conclusion that follows from them, in
  four of the logic deck's relations: order, cause, membership and proportion. Every conclusion is checked by
  its relation's own rule (`derives`: transitivity, the chain of events, inclusion, multiplication) and must
  need both facts (`checked`). Held out of all teaching: the counterfactual relation and every three-fact
  chain, the logic deck's transfer readings. Cause and membership carry a contrast fact as the deck does (the
  other branch, the other group), so both answers are in the premises and copying cannot decide.
- **The template writer** (`template`): a skeleton in fixed sentence frames, written fresh (none of the
  logic deck's frames). No model's text is in it.
- **The tutor writer** (`tutor_prompt`, `rewrite_prompt`, `read_reply`): a bigger model writes skeletons as
  strict Basic English and gives back the triples it wrote (`triple`), which must match the skeleton's.
- **The check** (`check_passage`), the same for both writers: strict Basic English (`not_basic`: Ogden's 850
  in their regular forms, names, numbers and the skeleton's invented words, nothing else); every invented
  word present; every fact said before the last sentence; the conclusion said in the last sentence and
  its opposite not; none of the content words of the four chains' 50m rungs (`banned_words`); no run of
  six words shared with the logic deck or any chain's pairs (`lists/tricks/`, `overlaps_tests`).

**The vocabulary is built around the banned list.** The 50m rungs (Nature's breeder, the mill, the between
and the pigeonhole tests) use 185 of Ogden's headwords, among them long, old, warm, high, small, time, cause
and change, and more and less besides, so they are kept out of every writer: order is taught with pairs
such as loud and quiet or cheap and dear, proportion as "one X is as dear as three Ys together", and cause
with events such as "goes up" and "comes down". `usable` filters every list against the 850 and the banned
words, so a change to a pair file changes the vocabulary, never the rule.
"""

from __future__ import annotations

import csv
import functools
import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from thorp import ogden, paths

RELATIONS = ("order", "cause", "membership", "proportion")
HELD_OUT = ("counterfactual", "three_hop")  # never taught: the logic deck reads them as transfer
FIFTY_RUNGS = (
    "nature",
    "mill",
    "between",
    "pigeonhole",
)  # the four chains' 50m rungs, lists/tricks/<key>.csv
OGDEN_TOKENISER = (
    "20e2cd56c6a50a55b74d495ef15d7913f82a1416"  # Ogden v0.1's shared 2,048-piece tokeniser
)
TEACHER = "mlx-community/Qwen3.8-27B-4bit"  # the Forgotten Tomes' yardstick, already on this Mac

# Ogden's 100 operations (his own grouping of the 850): the function words a content-word list leaves out
OPERATIONS = frozenset(
    """come get give go keep let make put seem take be do have say see send may will about across after
    against among at before between by down from in off on over through to under up with as for of till than
    a the all any every no other some such that this i he you who and because but or if though while how when
    where why again ever far forward here near now out still then there together well almost enough even
    little much not only quite so very tomorrow yesterday north south east west please yes""".split()
)
CONNECTIVES = ("So", "And so", "Because of this,", "For this reason,")

# ---------------------------------------------------------------------------------- vocabulary (candidates)
# Each list is filtered by `usable` against the 850 and the banned words; tests pin how many survive.

DIMENSIONS_ALL: dict[str, tuple[str, str | None]] = {  # order: a word and its opposite (or None)
    "loud": ("loud", "quiet"),
    "rough": ("rough", "smooth"),
    "clean": ("clean", "dirty"),
    "tight": ("tight", "loose"),
    "happy": ("happy", "sad"),
    "cheap": ("cheap", "dear"),
    "kind": ("kind", "cruel"),
    "sharp": ("sharp", None),
    "sweet": ("sweet", None),
    "wise": ("wise", None),
    "safe": ("safe", None),
}
STATES_ALL: dict[
    str, tuple[str, str, str, str]
] = {  # cause: an event and its opposite, and their key words
    "up": ("goes up", "comes down", "up", "down"),
    "noise": ("makes a noise", "is quiet", "noise", "quiet"),
    "open": ("is open", "is shut", "open", "shut"),
    "awake": ("is awake", "is sleeping", "awake", "sleep"),
    "loose": ("gets loose", "gets tight", "loose", "tight"),
    "happy": ("is happy", "is sad", "happy", "sad"),
    "clean": ("is clean", "is dirty", "clean", "dirty"),
    "rough": ("gets rough", "gets smooth", "rough", "smooth"),
}
TRIGGERS_ALL: dict[str, str] = {  # cause: what sets a chain going, by its key word
    "blow": "gets a blow",
    "push": "gets a push",
    "shake": "gets a shake",
    "touch": "is touched",
    "kick": "gets a kick",
    "knock": "gets a knock",
}
FEATURES_ALL = (  # membership: what every member of a group has, as a plural
    "wings", "horns", "tails", "feathers", "ears", "noses", "nails", "stems", "branches", "threads",
    "hooks", "toes", "necks", "fingers", "lips", "tongues", "combs", "brushes", "knees", "arms", "legs",
)  # fmt: skip
QUANTITIES_ALL: dict[str, str] = {  # proportion: what adds up, by its key word
    "dear": "is as dear as",
    "milk": "gives as much milk as",
    "wool": "has as much wool as",
    "noise": "makes as much noise as",
    "hair": "has as much hair as",
    "oil": "gives as much oil as",
}
# proportion: factor pairs whose product has a number word thorp.ogden knows (so it keys as <number>)
FACTORS = (2, 3, 4, 5, 6, 10)
NUMBER = {
    2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 8: "eight", 9: "nine", 10: "ten", 12: "twelve",
    20: "twenty", 30: "thirty", 40: "forty", 50: "fifty",
}  # fmt: skip
FACTOR_PAIRS = tuple((a, b) for a in FACTORS for b in FACTORS if a * b in NUMBER)
_NUMBER_OF = {w: n for n, w in NUMBER.items()} | {"one": 1}

# invented words: consonant, vowel, consonant, vowel, consonant ("tavim"); never ending in s or r, so a
# plural stays one -s and no -er or -es reading is possible
ONSETS = tuple("bdfgklmnprtvz")
VOWELS = tuple("aeiou")
MIDS = tuple("bdgklmnprtvz")
CODAS = tuple("bdgklmnptvxz")

_WORD = re.compile(r"[A-Za-z]+(?:'s)?|\d+")
_SENT = re.compile(r"(?<=[.!?])\s+")

# ---------------------------------------------------------------------------------- the banned words


@functools.cache
def banned_words() -> frozenset[str]:
    """The content words (numbers excepted) of the four chains' 50m rungs, as Ogden headwords where they are
    Ogden words, else as written: a passage using any of them is dropped."""
    out: set[str] = set()
    for key in FIFTY_RUNGS:
        with paths.resolve(f"lists/tricks/{key}.csv").open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for col in ("prompt", "frame", "idea", "rival"):
                    for w in _WORD.findall(row.get(col) or ""):
                        w = w.lower()
                        if w.isdigit() or w in ogden.NUMBER_WORDS:
                            continue
                        head = ogden.lemma(w)
                        if head in OPERATIONS:
                            continue
                        out.add(head or w)
    return frozenset(out)


def is_banned(word: str) -> bool:
    w = word.lower()
    return (ogden.lemma(w) or w) in banned_words()


def _ok(phrase: str) -> bool:
    """A phrase every word of which is an Ogden form (or a number) and none banned."""
    for w in _WORD.findall(phrase):
        w = w.lower()
        if w in _NUMBER_OF:
            continue
        if ogden.lemma(w) is None or is_banned(w):
            return False
    return True


def comparative(word: str) -> str:
    """The -er form Ogden's rules allow: happier, sadder, looser, quieter."""
    if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
        return word[:-1] + "ier"
    if word.endswith("e"):
        return word + "r"
    if (
        len(word) >= 3
        and word[-1] not in "aeiouwxy"
        and word[-2] in "aeiou"
        and word[-3] not in "aeiou"
    ):
        return word + word[-1] + "er"
    return word + "er"


@functools.cache
def usable() -> dict:
    """Every vocabulary list filtered against the 850 and the banned words."""
    dims = {}
    for k, (w, opp) in DIMENSIONS_ALL.items():
        if not _ok(w) or ogden.lemma(comparative(w)) != w:
            continue
        if opp is not None and (not _ok(opp) or ogden.lemma(comparative(opp)) != opp):
            opp = None
        dims[k] = (w, opp)
    return {
        "dimensions": dims,
        "states": {k: v for k, v in STATES_ALL.items() if _ok(v[0]) and _ok(v[1])},
        "triggers": {k: v for k, v in TRIGGERS_ALL.items() if _ok(v)},
        "features": tuple(f for f in FEATURES_ALL if _ok(f)),
        "quantities": {k: v for k, v in QUANTITIES_ALL.items() if _ok(v)},
    }


# ---------------------------------------------------------------------------------- invented words


def out_dir() -> Path:
    return paths.data_dir() / "logic-tutor"


@functools.cache
def test_words() -> frozenset[str]:
    """Every word of every test the tutor must stay apart from (lists/tricks/*.csv: the logic deck and the
    chains' pairs)."""
    out: set[str] = set()
    for p in sorted(paths.resolve("lists/tricks").glob("*.csv")):
        out.update(w.lower() for w in _WORD.findall(p.read_text(encoding="utf-8")))
    return frozenset(out)


def corpus_lexicon(
    recipe: str = "lists/ogden-v0.1.csv", clean: str = "unwrap-v2"
) -> frozenset[str]:
    """Every word of the Ogden v0.1 corpus as Nothing up my sleeve reads it, built once and kept in data/logic-tutor/."""
    p = out_dir() / "ogden-corpus-lexicon.txt"
    if p.exists():
        return frozenset(p.read_text(encoding="utf-8").split())
    from thorp import cleaning
    from thorp.sources import load_text

    words: set[str] = set()
    with paths.resolve(recipe).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row.get("text") or ""
            bid = (
                t[6:] if t.startswith("local:") else "pg" + t.split(":", 1)[1] if ":" in t else None
            )
            if bid is None:
                continue
            text = cleaning.clean(load_text(bid, "raw"), clean)
            words.update(w.lower() for w in _WORD.findall(text))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    return frozenset(words)


def english_words() -> frozenset[str]:
    """What an invented word must not be: the loop pool's lexicon, the Ogden corpus's, the tests' words."""
    lex = paths.data_dir() / "lexicon-en.txt"
    out = set(lex.read_text(encoding="utf-8").split()) if lex.exists() else set()
    return frozenset(out | corpus_lexicon() | test_words() | ogden.words())


def invented_words(n: int, seed: int = 1, exclude: frozenset[str] | None = None) -> list[str]:
    """n invented words, none English, none in the Ogden corpus or any test, none read as an Ogden form."""
    exclude = english_words() if exclude is None else exclude | test_words() | ogden.words()
    rng = random.Random(f"logic-tutor-words:{seed}")
    out: list[str] = []
    seen: set[str] = set()
    space = len(ONSETS) * len(VOWELS) * len(MIDS) * len(VOWELS) * len(CODAS)
    if n > space // 2:
        raise ValueError(f"{n} invented words asked of a space of {space}")
    while len(out) < n:
        w = (
            rng.choice(ONSETS)
            + rng.choice(VOWELS)
            + rng.choice(MIDS)
            + rng.choice(VOWELS)
            + rng.choice(CODAS)
        )
        if w in seen:
            continue
        seen.add(w)
        forms = (w, w + "s", w + "es")
        if any(f in exclude or ogden.lemma(f) for f in forms):
            continue
        out.append(w)
    return out


# ---------------------------------------------------------------------------------- skeletons


@dataclass(frozen=True)
class Event:
    thing: str
    state: str  # a key of the states, or "trigger:<key>"
    pos: bool = True  # the state's first phrase, or its opposite


@dataclass(frozen=True)
class Fact:
    rel: str  # order | cause | isa | has | ratio
    a: str
    b: str  # an invented word, or (has) a feature
    dim: str = ""  # order: the dimension; ratio: the quantity
    up: bool = True  # order: a is more of the dimension's first word than b
    n: int = 0  # ratio: one a is worth n b
    when: Event | None = None  # cause
    then: Event | None = None  # cause
    contrast: bool = False  # a fact no conclusion rests on (the other branch, the other group)

    @staticmethod
    def of(d: dict) -> Fact:
        d = dict(d)
        for k in ("when", "then"):
            if d.get(k):
                d[k] = Event(**d[k])
        return Fact(**d)


@dataclass(frozen=True)
class Skeleton:
    id: str
    relation: str
    facts: tuple[Fact, ...]  # in the order a passage states them
    conclusion: Fact
    words: tuple[str, ...]  # its invented words

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def of(d: dict) -> Skeleton:
        return Skeleton(
            id=d["id"],
            relation=d["relation"],
            facts=tuple(Fact.of(f) for f in d["facts"]),
            conclusion=Fact.of(d["conclusion"]),
            words=tuple(d["words"]),
        )


def _reach(edges: dict, start, goal) -> bool:
    seen, todo = set(), list(edges.get(start, ()))
    while todo:
        x = todo.pop()
        if x == goal:
            return True
        if x not in seen:
            seen.add(x)
            todo.extend(edges.get(x, ()))
    return False


def derives(facts, goal: Fact) -> bool:
    """Whether the facts give the goal by its relation's own rule."""
    if goal.rel == "order":
        edges: dict = {}
        for f in facts:
            if f.rel == "order" and f.dim == goal.dim:
                hi, lo = (f.a, f.b) if f.up else (f.b, f.a)
                edges.setdefault(hi, set()).add(lo)
        hi, lo = (goal.a, goal.b) if goal.up else (goal.b, goal.a)
        return _reach(edges, hi, lo)
    if goal.rel == "cause":
        edges = {}
        for f in facts:
            if f.rel == "cause":
                edges.setdefault(f.when, set()).add(f.then)
        return _reach(edges, goal.when, goal.then)
    if goal.rel == "has":
        isa: dict = {}
        for f in facts:
            if f.rel == "isa":
                isa.setdefault(f.a, set()).add(f.b)
        groups = {goal.a} | {
            g for g in {f.b for f in facts if f.rel == "isa"} if _reach(isa, goal.a, g)
        }
        return any(f.rel == "has" and f.a in groups and f.b == goal.b for f in facts)
    if goal.rel == "ratio":
        todo = [(goal.a, 1, 0)]
        while todo:
            x, prod, depth = todo.pop()
            for f in facts:
                if f.rel == "ratio" and f.dim == goal.dim and f.a == x and depth < len(facts):
                    p = prod * f.n
                    if f.b == goal.b and p == goal.n:
                        return True
                    todo.append((f.b, p, depth + 1))
        return False
    raise ValueError(f"no rule for {goal.rel!r}")


def checked(sk: Skeleton) -> bool:
    """The conclusion follows from the facts, needs both of its two facts, and is not one of them."""
    essential = [f for f in sk.facts if not f.contrast]
    return (
        sk.relation in RELATIONS
        and len(essential) == 2
        and sk.conclusion not in sk.facts
        and derives(sk.facts, sk.conclusion)
        and all(not derives([g for g in sk.facts if g is not f], sk.conclusion) for f in essential)
    )


def _units(rng: random.Random, single: Fact, pair: tuple[Fact, Fact]) -> tuple[Fact, ...]:
    """The facts in the order stated: the single fact and the fact with its contrast, either first; inside
    the pair the answer's clause comes last half the time."""
    pair = pair if rng.random() < 0.5 else (pair[1], pair[0])
    return (single, *pair) if rng.random() < 0.5 else (*pair, single)


def _skeleton(i: int, rng: random.Random, words: tuple[str, str, str], seed: int) -> Skeleton:
    v = usable()
    rel = RELATIONS[i % len(RELATIONS)]
    x, y, z = words
    if rel == "order":
        dim = rng.choice(sorted(v["dimensions"]))
        up = rng.random() < 0.5
        f1, f2 = Fact("order", x, y, dim=dim, up=up), Fact("order", y, z, dim=dim, up=up)
        facts = (f1, f2) if rng.random() < 0.5 else (f2, f1)
        concl = Fact("order", x, z, dim=dim, up=up)
        if rng.random() < 0.5:  # asked from the other end
            concl = Fact("order", z, x, dim=dim, up=not up)
    elif rel == "cause":
        trig = "trigger:" + rng.choice(sorted(v["triggers"]))
        s1, s2 = rng.sample(sorted(v["states"]), 2)
        p1, p2 = rng.random() < 0.5, rng.random() < 0.5
        f1 = Fact("cause", x, y, when=Event(x, trig), then=Event(y, s1, p1))
        f2 = Fact("cause", y, z, when=Event(y, s1, p1), then=Event(z, s2, p2))
        f3 = Fact(
            "cause", y, z, when=Event(y, s1, not p1), then=Event(z, s2, not p2), contrast=True
        )
        facts = _units(rng, f1, (f3, f2))
        concl = Fact("cause", x, z, when=f1.when, then=f2.then)
    elif rel == "membership":  # x is in group y; z is the other group, with the other feature
        feat, feat2 = rng.sample(v["features"], 2)
        f1 = Fact("isa", x, y)
        f2 = Fact("has", y, feat)
        f3 = Fact("has", z, feat2, contrast=True)
        facts = _units(rng, f1, (f3, f2))
        concl = Fact("has", x, feat)
    else:
        n1, n2 = rng.choice(FACTOR_PAIRS)
        q = rng.choice(sorted(v["quantities"]))
        f1, f2 = Fact("ratio", x, y, dim=q, n=n1), Fact("ratio", y, z, dim=q, n=n2)
        facts = (f1, f2) if rng.random() < 0.5 else (f2, f1)
        concl = Fact("ratio", x, z, dim=q, n=n1 * n2)
    return Skeleton(f"lt{seed}-{i:06d}", rel, facts, concl, tuple(words))


def skeletons(n: int, seed: int = 1, pool: list[str] | None = None) -> list[Skeleton]:
    """n checked skeletons, the four relations in turn, each drawing three invented words from the pool."""
    pool = pool if pool is not None else invented_words(5000, seed)
    rng = random.Random(f"logic-tutor-skeletons:{seed}")
    out = []
    for i in range(n):
        sk = _skeleton(i, rng, tuple(rng.sample(pool, 3)), seed)
        if not checked(sk):
            raise AssertionError(f"skeleton {sk.id} does not check: {sk}")
        out.append(sk)
    return out


# ---------------------------------------------------------------------------------- saying a fact


def _pl(w: str) -> str:
    return w + "es" if w[-1] in "xz" else w + "s"  # vaboxes, tedezes


def event_phrase(e: Event) -> str:
    v = usable()
    if e.state.startswith("trigger:"):
        return v["triggers"][e.state.split(":", 1)[1]]
    st = v["states"][e.state]
    return st[0] if e.pos else st[1]


def triple(f: Fact) -> list[str]:
    """A fact as [subject, link, object]: the form the tutor is given and gives back."""
    v = usable()
    if f.rel == "order":
        w, opp = v["dimensions"][f.dim]
        return (
            [f.a, f"{comparative(w)} than", f.b]
            if f.up
            else (
                [f.a, f"{comparative(opp)} than", f.b]
                if opp
                else [f.b, f"{comparative(w)} than", f.a]
            )
        )
    if f.rel == "cause":
        return [
            f"the {f.when.thing} {event_phrase(f.when)}",
            "then",
            f"the {f.then.thing} {event_phrase(f.then)}",
        ]
    if f.rel == "isa":
        return [f.a, "is a kind of", f.b]
    if f.rel == "has":
        return [f.a, "has", f.b]
    if f.rel == "ratio":
        return [f.a, f"{v['quantities'][f.dim]} {NUMBER[f.n]} of", f.b]
    raise ValueError(f.rel)


# ---------------------------------------------------------------------------------- the template writer


def _order_sentence(rng: random.Random, f: Fact) -> str:
    w, opp = usable()["dimensions"][f.dim]
    a, b, word = (f.a, f.b, w) if f.up else (f.b, f.a, w)  # a is more w than b
    if opp and rng.random() < 0.5:
        a, b, word = b, a, opp
    form = rng.randrange(3)
    if form == 0:
        return f"the {a} is {comparative(word)} than the {b}"
    if form == 1:
        return f"a {a} is {comparative(word)} than a {b}"
    return f"{_pl(a)} are {comparative(word)} than {_pl(b)}"


def _cause_sentence(rng: random.Random, fs: list[Fact]) -> str:
    opener = rng.choice(("when", "if"))  # not "any time": time is a 50m rung's word
    parts = [
        f"{opener} the {f.when.thing} {event_phrase(f.when)}, the {f.then.thing} {event_phrase(f.then)}"
        for f in fs
    ]
    return "; ".join(parts) if len(parts) == 1 or rng.random() < 0.5 else ", but ".join(parts)


def _has_sentence(rng: random.Random, fs: list[Fact]) -> str:
    parts = [
        (f"any {f.a} has {f.b}" if rng.random() < 0.5 else f"{_pl(f.a)} have {f.b}") for f in fs
    ]
    return ", but ".join(parts)


def _isa_sentence(rng: random.Random, f: Fact) -> str:
    return rng.choice(
        (
            f"a {f.a} is a sort of {f.b}",
            f"the {f.a} is one kind of {f.b}",
            f"every {f.a} is a {f.b}",
        )
    )


def _ratio_sentence(rng: random.Random, f: Fact) -> str:
    q = usable()["quantities"][f.dim]
    return f"one {f.a} {q} {NUMBER[f.n]} {_pl(f.b)} together"


def _cap(s: str) -> str:
    return s[0].upper() + s[1:] + "."


def say(rng: random.Random, facts: list[Fact]) -> str:
    """One sentence (without its stop) for a fact, or for a fact and its contrast."""
    f = facts[0]
    if f.rel == "order":
        return _order_sentence(rng, f)
    if f.rel == "cause":
        return _cause_sentence(rng, facts)
    if f.rel == "has":
        return _has_sentence(rng, facts)
    if f.rel == "isa":
        return _isa_sentence(rng, f)
    return _ratio_sentence(rng, f)


def _pairs(f: Fact, g: Fact) -> bool:
    """Whether two facts are a fact and its contrast: the same event's two branches (cause), or the two
    groups' features (membership)."""
    if f.contrast == g.contrast or f.rel != g.rel:
        return False
    return f.rel == "has" or (f.rel == "cause" and (f.a, f.b) == (g.a, g.b))


def _grouped(facts: tuple[Fact, ...]) -> list[list[Fact]]:
    """Facts as sentences: a contrast fact shares a sentence with the fact it is the other side of."""
    out: list[list[Fact]] = []
    for f in facts:
        if out and len(out[-1]) == 1 and _pairs(out[-1][0], f):
            out[-1].append(f)
        else:
            out.append([f])
    return out


def template(sk: Skeleton, rng: random.Random) -> str:
    """A skeleton in fixed frames: its facts in the order given, then the conclusion after a connective."""
    sents = [_cap(say(rng, g)) for g in _grouped(sk.facts)]
    c = say(rng, [sk.conclusion])
    conn = rng.choice(CONNECTIVES)
    sents.append(f"{conn} {c}.")
    return " ".join(sents)


# ---------------------------------------------------------------------------------- the tutor writer

TUTOR_RULES = """You write very short passages in Basic English, C. K. Ogden's 850-word English, for teaching a small reading machine to reason.

Rules for every passage:
- Use only Basic English words in their regular forms (-s, -es, -ed, -ing, -er, -ly), numbers written as words, and the made-up words given for that passage. No other words.
- Say every fact given, in your own words and in any order. Then end with the conclusion as the last sentence, beginning with "So", "And so", "Because of this," or "For this reason,".
- Two to five short sentences. Add no other facts and no reasons. Do not say "not" or "no" in the conclusion.
- Each made-up word is the name of a kind of thing: use it with "a", "the" or "every", or add -s for more than one (-es after x or z).

Give back only a JSON list with one object per passage, in the order given:
{"id": "<id>", "passage": "<the passage>", "facts": [<the fact triples, copied exactly, in the order your passage says them>], "conclusion": <the conclusion triple, copied exactly>}
"""


def _brief(sk: Skeleton) -> str:
    facts = "; ".join(json.dumps(triple(f)) for f in sk.facts)
    return (
        f"id {sk.id}: made-up words: {', '.join(sk.words)}\n"
        f"  facts: {facts}\n"
        f"  conclusion: {json.dumps(triple(sk.conclusion))}"
    )


def tutor_prompt(sks: list[Skeleton]) -> str:
    return TUTOR_RULES + "\nPassages:\n" + "\n".join(_brief(sk) for sk in sks)


def rewrite_prompt(items: list[tuple[Skeleton, str, list[str]]]) -> str:
    """One rewrite for passages that failed the check, each with what was wrong."""
    blocks = [
        f"{_brief(sk)}\n  your passage was: {passage}\n  what was wrong: {'; '.join(reasons)}"
        for sk, passage, reasons in items
    ]
    return TUTOR_RULES + "\nWrite these passages again, keeping to the rules:\n" + "\n".join(blocks)


def read_reply(text: str) -> dict[str, dict]:
    """The tutor's JSON list, by id; a reply that is not JSON gives nothing."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j <= i:
        return {}
    try:
        items = json.loads(text[i : j + 1])
    except json.JSONDecodeError:
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        if (
            isinstance(it, dict)
            and isinstance(it.get("id"), str)
            and isinstance(it.get("passage"), str)
        ):
            out[it["id"].strip()] = it
    return out


# ---------------------------------------------------------------------------------- the check


def sentences(text: str) -> list[str]:
    return [s for s in _SENT.split(text.strip()) if s]


def _base(tok: str, words: tuple[str, ...]) -> str | None:
    """The invented word a token is (itself or its plural), or None."""
    t = tok.lower()
    if t in words:
        return t
    if t.endswith("es") and t[:-2] in words:
        return t[:-2]
    if t.endswith("s") and t[:-1] in words:
        return t[:-1]
    return None


def not_basic(text: str, words: tuple[str, ...]) -> list[str]:
    """The words of a passage that are not strict Basic English: not an Ogden form, a number, a name or one of
    its invented words."""
    bad = []
    for s in sentences(text):
        for k, tok in enumerate(_WORD.findall(s)):
            t = tok.lower()
            if tok.isdigit() or t in ogden.NUMBER_WORDS or _base(t, words) or ogden.lemma(t):
                continue
            if tok[0].isupper() and k > 0:
                continue  # a name
            bad.append(tok)
    return bad


@functools.cache
def _test_ngrams(n: int = 6) -> frozenset[tuple[str, ...]]:
    out: set[tuple[str, ...]] = set()
    for p in sorted(paths.resolve("lists/tricks").glob("*.csv")):
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                prompt = row.get("prompt") or ""
                for tail in (row.get("idea") or "", row.get("rival") or ""):
                    toks = [w.lower() for w in _WORD.findall(f"{prompt} {tail}")]
                    out.update(tuple(toks[i : i + n]) for i in range(len(toks) - n + 1))
    return frozenset(out)


def overlaps_tests(text: str, n: int = 6) -> list[str]:
    """The runs of n words a passage shares with the logic deck or any chain's pairs."""
    grams = _test_ngrams(n)
    toks = [w.lower() for w in _WORD.findall(text)]
    return [
        " ".join(toks[i : i + n])
        for i in range(len(toks) - n + 1)
        if tuple(toks[i : i + n]) in grams
    ]


def _lemmas(toks: list[str]) -> set[str]:
    return {ogden.lemma(t) or t for t in toks}


def _numbers(toks: list[str]) -> set[int]:
    return {int(t) for t in toks if t.isdigit()} | {_NUMBER_OF[t] for t in toks if t in _NUMBER_OF}


def says(sentence: str, f: Fact, words: tuple[str, ...], last: bool = False) -> bool:
    """Whether a sentence states a fact. In the last sentence (`last`) the fact's opposite must be absent too:
    the other answer, the other feature, another product."""
    toks = [t.lower() for t in _WORD.findall(sentence)]
    inv = [_base(t, words) for t in toks]
    present = {w for w in inv if w}
    lem = _lemmas(toks)
    v = usable()
    if f.rel == "order":
        if "not" in toks or "no" in toks:
            return False
        w, opp = v["dimensions"][f.dim]
        hi, lo = (f.a, f.b) if f.up else (f.b, f.a)
        for k, t in enumerate(toks):
            head = ogden.lemma(t)
            if t == head or head not in (w, opp):
                continue  # not a comparative of this dimension
            subj = next((inv[i] for i in range(k - 1, -1, -1) if inv[i]), None)
            j = next((i for i in range(k + 1, len(toks)) if toks[i] == "than"), None)
            obj = (
                next((inv[i] for i in range(j + 1, len(toks)) if inv[i]), None)
                if j is not None
                else None
            )
            if subj and obj and ((subj, obj) if head == w else (obj, subj)) == (hi, lo):
                return True
        return False
    if f.rel == "cause":
        if not {f.when.thing, f.then.thing} <= present:
            return False

        def keys(e: Event, pos: bool) -> set[str]:
            if e.state.startswith("trigger:"):
                return {e.state.split(":", 1)[1]}
            st = v["states"][e.state]
            return {ogden.lemma(st[2]) or st[2]} if pos else {ogden.lemma(st[3]) or st[3]}

        ok = keys(f.when, f.when.pos) <= lem and keys(f.then, f.then.pos) <= lem
        if last and not f.then.state.startswith("trigger:"):
            ok = ok and not (keys(f.then, not f.then.pos) & lem)
        return ok
    if f.rel == "isa":
        return {f.a, f.b} <= present
    if f.rel == "has":
        feat = ogden.lemma(f.b) or f.b
        if f.a not in present or feat not in lem:
            return False
        if last:
            others = {ogden.lemma(x) or x for x in v["features"]} - {feat}
            return not (others & lem) and "not" not in toks and "no" not in toks
        return True
    if f.rel == "ratio":
        if not {f.a, f.b} <= present or f.n not in _numbers(toks):
            return False
        if f.dim not in lem:  # the quantity's key word: dear, milk, wool ...
            return False
        return not last or _numbers(toks) <= {1, f.n}
    raise ValueError(f.rel)


def check_passage(sk: Skeleton, text: str, reply: dict | None = None) -> list[str]:
    """Why a passage is dropped (empty: kept). `reply` is the tutor's object, whose triples must match."""
    reasons = []
    if reply is not None:
        facts = reply.get("facts")
        if not isinstance(facts, list) or sorted(map(json.dumps, facts)) != sorted(
            json.dumps(triple(f)) for f in sk.facts
        ):
            reasons.append("the fact triples given back are not the skeleton's")
        if json.dumps(reply.get("conclusion")) != json.dumps(triple(sk.conclusion)):
            reasons.append("the conclusion triple given back is not the skeleton's")
    sents = sentences(text)
    if not 2 <= len(sents) <= 6:
        reasons.append(f"{len(sents)} sentences (two to six)")
    if not sents:
        return reasons
    bad = not_basic(text, sk.words)
    if bad:
        reasons.append("these words are not Basic English: " + ", ".join(sorted(set(bad))))
    toks = _WORD.findall(text)
    missing = set(sk.words) - {_base(t, sk.words) for t in toks}
    if missing:
        reasons.append("the made-up words are missing: " + ", ".join(sorted(missing)))
    body, last = sents[:-1], sents[-1]
    for f in sk.facts:
        if not any(says(s, f, sk.words) for s in body):
            reasons.append("a fact is not said before the last sentence: " + json.dumps(triple(f)))
    if not says(last, sk.conclusion, sk.words, last=True):
        reasons.append(
            "the last sentence does not say the conclusion: " + json.dumps(triple(sk.conclusion))
        )
    if any(says(s, sk.conclusion, sk.words) for s in body):
        reasons.append("the conclusion is said before the last sentence")
    banned = sorted({t for t in toks if is_banned(t) and not _base(t, sk.words)})
    if banned:
        reasons.append("these words are kept out of the teaching: " + ", ".join(banned))
    over = overlaps_tests(text)
    if over:
        reasons.append("these runs of six words are in a test: " + "; ".join(over[:3]))
    return reasons


def ogden_tokens(texts: list[str], tid: str = OGDEN_TOKENISER) -> int:
    """How many pieces of Ogden v0.1's tokeniser the texts are, read as one passage a paragraph."""
    from thorp import tokeniser

    sp = tokeniser.load(tid).sp
    return sum(
        len(sp.encode(t)) + 2 for t in texts
    )  # each passage ends in a paragraph break (two pieces)
