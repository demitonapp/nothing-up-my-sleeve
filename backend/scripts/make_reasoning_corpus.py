"""Build the 50m reasoning leg's corpus (12 November 2026, kipling:14; Justin: "I want the first Nothin up my sleeve to
have a reasoining variant", then "classes for the reasoning and tool is 50m", then "Yes to both").

What the reading pass found, and what this builds from it:

- written-out steps let a 10.6M model trained from nothing get every three-digit sum right from 1,000 examples, where
  10,000 plain ones stalled near 85% (Lee et al. 2023): a small ship can use steps, and a few thousand good lessons
  can be enough;
- steps help when the two facts were never seen together (Prystawski et al. 2023), and chaining silently makes a
  model learn each fact twice where a written step needs it once (Johnston & Belrose 2025): the premises of a lesson
  are new each time, so the only way to the answer is through them;
- small students learn more from short chains than long ones (Li et al. 2025): a chain here is the premises restated
  in the order they join, then the conclusion, in Ogden's words;
- one model can think or answer at once, taught in one stage that mixes both (Qwen3, SmolLM3): half the lessons
  think, and half have the empty pair (`<think><answer>`).

Every lesson is written by code, so every answer is right by construction; no teacher is needed for it, and the
teacher's time goes to the tool corpus, where natural questions matter more. Six kinds of relation (order, set
membership, cause, place, kin and counting), one, two and three hops, the premises sometimes swapped and sometimes
padded with an idle fact, the terms mostly invented words (so no knowledge helps) and a share plain Ogden nouns.
The held-out lessons are drawn from a second, disjoint stock of invented words: what the evaluator reads is chaining,
never a remembered term.

The lessons are local books of PER each (`rsn-<n>`), listed in `lists/reasoning-marked-v1.csv`, separated as the talk
corpus separates its turns, so through marks-v1 each reads `<bos>\\n<question>…<think>…<answer>…<end>\\n<eos>`. The
held-out items go to `lists/reasoning-heldout-v1.jsonl` for the `reasoning` evaluator.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_reasoning_corpus.py [--dry-run] [--n N]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_talk_corpus as talk  # noqa: E402  (the book writer and the separator are the talk corpus's)

from thorp import cleaning, paths, turns  # noqa: E402

LIST = "lists/reasoning-marked-v1.csv"
HELD = "lists/reasoning-heldout-v1.jsonl"
VERSION = "reasoning-marked-v1"
PER = 40  # lessons a book
N_TRAIN = 40_000
N_HELD = 600
THINK_SHARE = 0.5  # lessons that think; the rest answer at once, with the empty pair
REAL_SHARE = 0.2  # lessons in plain Ogden nouns rather than invented words
CLEAN = "marks-v1"
SEED = 20261112

# ---- the terms: invented words in two disjoint stocks (training, held out), and a few plain Ogden nouns
_ON = "b d f g k l m n p r s t v z".split()
_NUC = "a e i o u".split()
_CODA = "b d g k l m n p r s t".split()


def _stock(rng: random.Random, n: int, avoid: set[str]) -> list[str]:
    out: list[str] = []
    while len(out) < n:
        w = rng.choice(_ON) + rng.choice(_NUC) + rng.choice(_CODA) + rng.choice(["", rng.choice(_NUC) + rng.choice(_CODA)])
        if len(w) >= 3 and w not in avoid and w not in out:
            out.append(w)
    return out


# the logic deck's own invented words stay out of both stocks (thorp/evaluators/logic.py reads them)
_DECK = {"glimmet", "dornal", "fesk", "blick", "wug", "dax", "zorp", "tove", "flim"}
_R = random.Random(SEED)
TRAIN_WORDS = _stock(_R, 1500, _DECK)
HELD_WORDS = _stock(_R, 400, _DECK | set(TRAIN_WORDS))
REAL = ("dog cat horse cow bird fish ship boat house box bag cup tree flower stone rock hill river apple egg "
        "boy girl man woman king queen friend farmer teacher baker").split()
NAMES = ("Ann Ben Cara Dan Eve Fred Gail Hal Ida Jon Kate Lee May Ned Olive Pat Rose Sam Tom Una Vic Will").split()

# ---- the six kinds of relation: each makes a chain of facts, a question and its answer
ORDER = [("heavier", "lighter"), ("taller", "shorter"), ("older", "younger"), ("quicker", "slower"),
         ("longer", "shorter"), ("warmer", "colder")]  # fmt: skip


def _a(w: str) -> str:
    return ("an " if w[0] in "aeiou" else "a ") + w


def _cap(s: str) -> str:
    return s[0].upper() + s[1:]


def order_chain(rng, terms, hops):
    up, down = rng.choice(ORDER)
    xs = terms[: hops + 1]
    facts = [f"{_cap(_a(xs[i]))} is {up} than {_a(xs[i + 1])}." for i in range(hops)]
    first, last = xs[0], xs[-1]
    concl = f"So {_a(first)} is {up} than {_a(last)}."
    r = rng.random()
    if r < 0.35:
        return facts, f"Is {_a(first)} {up} than {_a(last)}?", concl, "Yes."
    if r < 0.6:
        return facts, f"Is {_a(first)} {down} than {_a(last)}?", concl, "No."
    a, b = (first, last) if rng.random() < 0.5 else (last, first)
    return facts, f"Which is {up}, {_a(a)} or {_a(b)}?", concl, _cap(_a(first)) + "."


def set_chain(rng, terms, hops):
    xs = terms[: max(hops, 1) + 1]
    name = rng.choice(NAMES)
    rules = [f"Every {xs[i]} is {_a(xs[i + 1])}." for i in range(len(xs) - 1)]
    if rng.random() < 0.7:
        facts = [f"{name} is {_a(xs[0])}.", *rules]
        if rng.random() < 0.5:
            return facts, f"Is {name} {_a(xs[-1])}?", f"So {name} is {_a(xs[-1])}.", "Yes."
        return facts, f"What is {name}, {_a(xs[-1])} or {_a(terms[-1])}?", f"So {name} is {_a(xs[-1])}.", _cap(_a(xs[-1])) + "."
    # the rule read backwards: what is not the last is not the first (modus tollens)
    facts = [*rules, f"{name} is not {_a(xs[-1])}."]
    return facts, f"Is {name} {_a(xs[0])}?", f"If {name} were {_a(xs[0])}, {name} would be {_a(xs[-1])}. So {name} is not {_a(xs[0])}.", "No."


def cause_chain(rng, terms, hops):
    xs = terms[: hops + 1]
    verbs = [("moves", "move"), ("sings", "sing"), ("glows", "glow"), ("falls", "fall"), ("turns", "turn"), ("opens", "open")]
    v = [rng.choice(verbs) for _ in xs]
    facts = [f"When the {xs[i]} {v[i][0]}, the {xs[i + 1]} {v[i + 1][0]}." for i in range(hops)] + [f"The {xs[0]} {v[0][0]}."]
    concl = f"So the {xs[-1]} {v[-1][0]}."
    if rng.random() < 0.5:
        return facts, f"Does the {xs[-1]} {v[-1][1]}?", concl, "Yes."
    return facts, f"What does the {xs[-1]} do?", concl, f"It {v[-1][0]}."


def place_chain(rng, terms, hops):
    xs = terms[: hops + 1]
    other, elsewhere = terms[hops + 1], terms[-1]
    facts = [f"The {xs[i]} is in the {xs[i + 1]}." for i in range(hops)]
    concl = f"So the {xs[0]} is in the {xs[-1]}."
    if rng.random() < 0.5 or other == xs[-1]:
        return facts, f"Is the {xs[0]} in the {xs[-1]}?", concl, "Yes."
    facts = facts + [f"The {other} is in the {elsewhere}."]
    a, b = (xs[0], other) if rng.random() < 0.5 else (other, xs[0])
    return facts, f"Which is in the {xs[-1]}, the {a} or the {b}?", concl, f"The {xs[0]}."


def kin_chain(rng, terms, hops):
    a, b, c = rng.sample(NAMES, 3)
    if hops == 1:
        return [f"{a} is the parent of {b}."], f"Who is the child of {a}?", f"So {b} is the child of {a}.", f"{b}."
    facts = [f"{a} is the parent of {b}.", f"{b} is the parent of {c}."]
    if rng.random() < 0.5:
        return facts, f"Who is the grandparent of {c}?", f"So {a} is the grandparent of {c}.", f"{a}."
    return facts, f"Is {c} the grandparent of {a}?", f"So {a} is the grandparent of {c}, not {c} of {a}.", "No."


def count_chain(rng, terms, hops):
    name = rng.choice(NAMES)
    n1, n2 = rng.randint(2, 6), rng.randint(2, 6)
    box, thing = terms[0], terms[1]
    if hops == 1:
        return [f"{name} has {n1} {box}s."], f"How many {box}s has {name}?", f"So {name} has {n1} {box}s.", f"{n1}."
    facts = [f"{name} has {n1} {box}s.", f"In every {box} there are {n2} {thing}s."]
    return (facts, f"How many {thing}s has {name}?",
            f"{n1} {box}s with {n2} {thing}s in each is {n1 * n2} {thing}s.", f"{n1 * n2}.")


KINDS = {"order": order_chain, "set": set_chain, "cause": cause_chain, "place": place_chain, "kin": kin_chain,
         "count": count_chain}  # fmt: skip


def lesson(rng: random.Random, stock: list[str], think: bool | None = None) -> dict:
    kind = rng.choice(list(KINDS))
    hops = rng.choices([1, 2, 3], weights=[2, 6, 2])[0]
    words = REAL if rng.random() < REAL_SHARE else stock
    terms = rng.sample(words, 5)
    facts, q, concl, ans = KINDS[kind](rng, terms, hops)
    steps_facts = list(facts)
    shown = list(facts)
    if rng.random() < 0.3:  # the premises out of the order they join
        rng.shuffle(shown)
    if rng.random() < 0.25:  # an idle fact beside them
        idle = rng.sample(words, 2)
        shown.insert(rng.randrange(len(shown) + 1), f"{_cap(_a(idle[0]))} is not {_a(idle[1])}.")
    think = (rng.random() < THINK_SHARE) if think is None else think
    question = " ".join(shown) + " " + q
    steps = " ".join(steps_facts + [concl]) if think else ""
    return {"kind": kind, "hops": len(facts), "question": question, "steps": " ".join(steps_facts + [concl]),
            "answer": ans, "think": think, "text": turns.thought(question, steps, ans)}


def build(dry_run: bool, n: int) -> dict:
    rng = random.Random(SEED + 1)
    train = [lesson(rng, TRAIN_WORDS) for _ in range(n)]
    held_rng = random.Random(SEED + 2)
    held = [lesson(held_rng, HELD_WORDS, think=False) for _ in range(N_HELD)]
    # a held-out question is never a training question (the stocks are disjoint, and the plain-noun share is checked)
    seen = {x["question"] for x in train}
    held = [h for h in held if h["question"] not in seen]
    answers = [x["answer"] for x in train]
    out = {
        "lessons": len(train), "held_out": len(held),
        "answers": {"yes": answers.count("Yes."), "no": answers.count("No."),
                    "other": sum(a not in ("Yes.", "No.") for a in answers)},
        "by_kind": {k: sum(x["kind"] == k for x in train) for k in KINDS},
        "by_hops": {h: sum(x["hops"] == h for x in train) for h in (1, 2, 3, 4)},
        "thinking": sum(x["think"] for x in train),
        "sample": [x["text"] for x in train[:4]],
    }
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows, checked = [], 0
    for i in range(0, len(train), PER):
        bid = f"rsn-{i // PER + 1:05d}"
        part = train[i : i + PER]
        text = talk.SEP.join(x["text"] for x in part) + "\n"
        read = cleaning.clean(text, CLEAN)
        checked += sum(cleaning.clean(x["text"], CLEAN).strip("\n").split("\n")[1] in read for x in part)
        rows.append(talk._book(d, bid, f"reasoning lessons {i // PER + 1}", "the reasoning leg", text, now))
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for i, h in enumerate(held):
            f.write(json.dumps({"key": f"rsn-{i + 1}", "kind": h["kind"], "hops": h["hops"], "prompt": h["question"],
                                "steps": h["steps"], "answer": h["answer"]}, ensure_ascii=False) + "\n")  # fmt: skip
    out["books_written"] = len(rows)
    out["reads_as_written"] = [checked, len(train)]
    meta = {"version": VERSION, "generator": "backend/scripts/make_reasoning_corpus.py", "seed": SEED,
            "about": "two-fact chains in six kinds of relation, half thinking between marks, every answer made by code",
            "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
            **{k: v for k, v in out.items() if k != "sample"}}  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--n", type=int, default=N_TRAIN, help="lessons to write")
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run, a.n), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
