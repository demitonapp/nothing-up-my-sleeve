"""The logic deck (2026-11-07, Justin: "build them"): a controlled test that chaining two facts is
chaining, and not knowledge or copying. Writes lists/tricks/logic.csv.

Every item is built from invented words (checked against the loop pool's lexicon, so none is English)
or, for the counterfactual relation, from premises that run against the world, so no prior knowledge
can supply the answer. Both answers appear in the premises wherever the form allows, so copying cannot
decide, and half the items name the answer last and half the rival, so recency cannot decide either. Each item comes in variants:

- `both`: the two premises, then the frame (the two-hop item)
- `first`, `second`: one premise only, the other replaced by a neutral sentence of the same kind
- `swapped`: the premises in the other order
- `padded`: an irrelevant third premise about other invented words added last, naming its own middle
  term twice (the bridge card's distractor), so recency and repetition favour the distractor and only
  the chain can favour the bridge
- `one_hop`: the conclusion's link stated directly (a floor)
- `three_hop`: three premises chained (a ceiling), for order and cause

Relations: order (transitive comparison), cause (a chain of events), membership (all A are B, all B
have C), proportion (twice of twice is four times, against a neighbouring wrong product the premises
never name), and
counterfactual (fire that cools water, read against the world). Columns: item, relation, variant,
prompt, frame, idea, rival, bridge (the middle term), distractor (the padded premise's middle term),
answer_word (the premise word the idea copies, for the mover card).
"""

from __future__ import annotations

import csv
import random

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

ITEMS = 8  # per relation
FILLER = "The day was quiet and the road was long."
ONSETS = [
    "b",
    "d",
    "f",
    "g",
    "gl",
    "k",
    "l",
    "m",
    "n",
    "p",
    "pr",
    "r",
    "s",
    "sk",
    "t",
    "tr",
    "v",
    "z",
    "br",
    "dr",
]
VOWELS = ["a", "e", "i", "o", "u"]
CODAS = ["n", "m", "r", "l", "t", "sk", "nd", "x", "rp", "lk"]


def nonce_words(n: int, rng: random.Random) -> list[str]:
    lex_p = ROOT / "data" / "lexicon-en.txt"
    lexicon = set(lex_p.read_text().split()) if lex_p.exists() else set()
    out: list[str] = []
    while len(out) < n:
        w = (
            rng.choice(ONSETS)
            + rng.choice(VOWELS)
            + rng.choice(CODAS)
            + rng.choice(["", "et", "ol", "an"])
        )
        if len(w) >= 4 and w not in lexicon and w not in out:
            out.append(w)
    return out


COMPARATIVES = [
    ("heavier", "lighter"),
    ("taller", "shorter"),
    ("older", "younger"),
    ("faster", "slower"),
    ("warmer", "colder"),
    ("larger", "smaller"),
]
EFFECTS = [
    ("glows", "darkens"),
    ("sings", "falls silent"),
    ("swells", "shrinks"),
    ("opens", "closes"),
    ("warms", "cools"),
    ("rises", "sinks"),
]
CAUSES = ["is struck", "is shaken", "is lit", "is watered", "is opened", "is pressed"]
MIDDLES = [
    ("rises", "falls"),
    ("turns left", "turns right"),
    ("wakes", "sleeps"),
    ("hums", "is still"),
]
FEATURES = [
    ("wings", "fins"),
    ("horns", "tusks"),
    ("stripes", "spots"),
    ("shells", "scales"),
    ("feathers", "fur"),
]
# the rival is a wrong product that the premises never name, so copying cannot decide
FACTORS = [
    (2, 2, "four times", "three times"),
    (2, 3, "six times", "seven times"),
    (3, 2, "six times", "five times"),
    (3, 3, "nine times", "eight times"),
    (2, 5, "ten times", "eleven times"),
    (5, 2, "ten times", "nine times"),
]
TIMES = {2: "twice", 3: "three times", 5: "five times"}
COUNTER = [
    (
        "fire makes the water of its ponds colder",
        "cold water stops the mill wheels, while warm water turns them",
        "a fire under the mill-pond makes the wheel",
        "stop",
        "turn",
    ),
    (
        "rain makes the fields drier",
        "dry fields bring a poor harvest, while wet fields bring a rich one",
        "a rainy summer brings a harvest that is",
        "poor",
        "rich",
    ),
    (
        "feeding a horse makes it weaker",
        "weak horses pull slowly, while strong horses pull fast",
        "a well-fed horse pulls",
        "slowly",
        "fast",
    ),
    (
        "ice makes the air warmer",
        "warm air makes the bees fly, while cold air keeps them in the hive",
        "a cart of ice brought into the garden makes the bees",
        "fly",
        "stay in the hive",
    ),
    (
        "salt makes the soup sweeter",
        "sweet soup pleases the children, while bitter soup angers them",
        "a handful of salt in the soup makes the children",
        "pleased",
        "angry",
    ),
    (
        "the sun makes the river colder",
        "a cold river freezes, while a warm river flows",
        "a long sunny week makes the river",
        "freeze",
        "flow",
    ),
    (
        "oil makes a lamp burn dimmer",
        "a dim lamp lets the moths sleep, while a bright lamp draws them",
        "filling the lamp with oil makes the moths",
        "sleep",
        "gather",
    ),
    (
        "hammering iron makes it softer",
        "soft iron bends, while hard iron rings",
        "iron hammered all morning",
        "bends",
        "rings",
    ),
]


def order_items(rng, words) -> list[dict]:
    out = []
    for i in range(ITEMS):
        a, b, c, d, e, f = (
            words.pop(),
            words.pop(),
            words.pop(),
            words.pop(),
            words.pop(),
            words.pop(),
        )
        hi, lo = COMPARATIVES[i % len(COMPARATIVES)]
        # a > b > c, stated with both words so copying cannot decide; half the items ask the low end
        p1 = f"Every {a} is {hi} than every {b}."
        p2 = f"Every {c} is {lo} than every {b}."
        p3 = f"Every {d} is {lo} than every {c}."  # three hops: a > b > c > d
        pad = f"Every {e} is {lo} than every {f}, and every {f} is {lo} than every {d}."
        ask_low = i % 2 == 1
        x, z = (c, a) if ask_low else (a, c)
        idea, rival = (
            (f"{lo} than a {z}", f"{hi} than a {z}")
            if ask_low
            else (f"{hi} than a {z}", f"{lo} than a {z}")
        )
        frame = f"So a {x} is"
        base = {
            "relation": "order",
            "bridge": b,
            "distractor": f,
            "answer_word": lo if ask_low else hi,
        }
        out.append(
            {
                **base,
                "variant": "both",
                "pre": f"{p1} {p2}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        out.append(
            {
                **base,
                "variant": "first",
                "pre": f"{p1} {FILLER}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        out.append(
            {
                **base,
                "variant": "second",
                "pre": f"{FILLER} {p2}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        out.append(
            {
                **base,
                "variant": "swapped",
                "pre": f"{p2} {p1}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        out.append(
            {
                **base,
                "variant": "padded",
                "pre": f"{p1} {p2} {pad}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        one = (
            f"Every {a} is {hi} than every {c}."
            if not ask_low
            else f"Every {c} is {lo} than every {a}."
        )
        out.append(
            {
                **base,
                "variant": "one_hop",
                "pre": f"{one} {FILLER}",
                "frame": frame,
                "idea": idea,
                "rival": rival,
            }
        )
        out.append(
            {
                **base,
                "variant": "three_hop",
                "pre": f"{p1} {p2} {p3}",
                "frame": f"So a {d} is" if ask_low else f"So a {a} is",
                "idea": f"{lo} than a {a}" if ask_low else f"{hi} than a {d}",
                "rival": f"{hi} than a {a}" if ask_low else f"{lo} than a {d}",
                "answer_word": lo if ask_low else hi,
            }
        )
        for r in out[-7:]:
            r["item"] = f"order-{i}"
    return out


def cause_items(rng, words) -> list[dict]:
    out = []
    for i in range(ITEMS):
        a, b, c, d, e = words.pop(), words.pop(), words.pop(), words.pop(), words.pop()
        cause = CAUSES[i % len(CAUSES)]
        up, down = MIDDLES[i % len(MIDDLES)]
        good, bad = EFFECTS[i % len(EFFECTS)]
        p1 = f"When the {a} {cause}, the {b} {up}."
        p2 = f"When the {b} {up}, the {c} {good}; when the {b} {down}, the {c} {bad}."
        p3 = f"When the {c} {good}, the {d} wakes; when the {c} {bad}, the {d} sleeps."
        one = f"When the {a} {cause}, the {c} {good}; when it is left alone, the {c} {bad}."
        if i % 2:  # the answer's clause last, so recency favours the answer as often as the rival
            p2 = f"When the {b} {down}, the {c} {bad}; when the {b} {up}, the {c} {good}."
            p3 = f"When the {c} {bad}, the {d} sleeps; when the {c} {good}, the {d} wakes."
            one = (
                f"When the {a} is left alone, the {c} {bad}; when the {a} {cause}, the {c} {good}."
            )
        pad = f"When the {e} {down}, the {d} is cold; when the {e} {up}, the {d} is warm."
        frame = f"So when the {a} {cause}, the {c}"
        base = {"relation": "cause", "bridge": b, "distractor": e, "answer_word": good.split()[0]}
        rows = [
            ("both", f"{p1} {p2}", frame, good, bad),
            ("first", f"{p1} {FILLER}", frame, good, bad),
            ("second", f"{FILLER} {p2}", frame, good, bad),
            ("swapped", f"{p2} {p1}", frame, good, bad),
            ("padded", f"{p1} {p2} {pad}", frame, good, bad),
            (
                "one_hop",
                one,
                frame,
                good,
                bad,
            ),
            (
                "three_hop",
                f"{p1} {p2} {p3}",
                f"So when the {a} {cause}, the {d}",
                "wakes",
                "sleeps",
            ),
        ]
        for v, pre, fr, idea, rival in rows:
            out.append(
                {
                    **base,
                    "item": f"cause-{i}",
                    "variant": v,
                    "pre": pre,
                    "frame": fr,
                    "idea": idea,
                    "rival": rival,
                }
            )
    return out


def membership_items(rng, words) -> list[dict]:
    out = []
    for i in range(ITEMS):
        a, b, c, d, e = words.pop(), words.pop(), words.pop(), words.pop(), words.pop()
        f1, f2 = FEATURES[i % len(FEATURES)]
        if i % 2:
            f1, f2 = f2, f1
        p1 = f"All {a}s are {b}s."
        p2 = f"All {b}s have {f1}, and all {c}s have {f2}."
        one = f"All {a}s have {f1}, and all {c}s have {f2}."
        if i % 2:  # the answer last
            p2 = f"All {c}s have {f2}, and all {b}s have {f1}."
            one = f"All {c}s have {f2}, and all {a}s have {f1}."
        pad = f"All {d}s are {e}s, and all {e}s are grey."
        frame = f"So every {a} has"
        base = {"relation": "membership", "bridge": b, "distractor": e, "answer_word": f1}
        rows = [
            ("both", f"{p1} {p2}"),
            ("first", f"{p1} {FILLER}"),
            ("second", f"{FILLER} {p2}"),
            ("swapped", f"{p2} {p1}"),
            ("padded", f"{p1} {p2} {pad}"),
            ("one_hop", one),
        ]
        for v, pre in rows:
            out.append(
                {
                    **base,
                    "item": f"membership-{i}",
                    "variant": v,
                    "pre": pre,
                    "frame": frame,
                    "idea": f1,
                    "rival": f2,
                }
            )
    return out


def proportion_items(rng, words) -> list[dict]:
    out = []
    for i in range(ITEMS):
        a, b, c, d, e = words.pop(), words.pop(), words.pop(), words.pop(), words.pop()
        m1, m2, idea_t, rival_t = FACTORS[i % len(FACTORS)]
        p1 = f"Each {a} weighs {TIMES[m1]} as much as a {b}."
        p2 = f"Each {b} weighs {TIMES[m2]} as much as a {c}."
        pad = f"Each {d} weighs twice as much as an {e}, and each {e} weighs as much as a stone."
        frame = f"So a {a} weighs"
        idea, rival = f"{idea_t} as much as a {c}", f"{rival_t} as much as a {c}"
        base = {"relation": "proportion", "bridge": b, "distractor": e, "answer_word": ""}
        rows = [
            ("both", f"{p1} {p2}"),
            ("first", f"{p1} {FILLER}"),
            ("second", f"{FILLER} {p2}"),
            ("swapped", f"{p2} {p1}"),
            ("padded", f"{p1} {p2} {pad}"),
        ]
        for v, pre in rows:
            out.append(
                {
                    **base,
                    "item": f"proportion-{i}",
                    "variant": v,
                    "pre": pre,
                    "frame": frame,
                    "idea": idea,
                    "rival": rival,
                }
            )
    return out


def counterfactual_items(rng, words) -> list[dict]:
    out = []
    flipped = {
        1: "wet fields bring a rich harvest, while dry fields bring a poor one",
        3: "cold air keeps the bees in the hive, while warm air makes them fly",
        5: "a warm river flows, while a cold river freezes",
        7: "hard iron rings, while soft iron bends",
    }
    for i, (f1, f2, ask, good, bad) in enumerate(COUNTER[:ITEMS]):
        f2 = flipped.get(i, f2)  # odd items name the answer's clause last
        place = words.pop().capitalize()
        p1 = f"In the valley of {place}, {f1}."
        p2 = f"In {place}, {f2}."
        frame = f"So in {place}, {ask}"
        base = {
            "relation": "counterfactual",
            "bridge": "",
            "distractor": "",
            "answer_word": good.split()[0],
        }
        rows = [
            ("both", f"{p1} {p2}"),
            ("first", f"{p1} {FILLER}"),
            ("second", f"{FILLER} {p2}"),
            ("swapped", f"{p2} {p1}"),
        ]
        for v, pre in rows:
            out.append(
                {
                    **base,
                    "item": f"counterfactual-{i}",
                    "variant": v,
                    "pre": pre,
                    "frame": frame,
                    "idea": good,
                    "rival": bad,
                }
            )
    return out


def main(items: int = 8, seed: int = 1859, out: str = "logic.csv", cause_only: bool = False) -> None:
    """The deck: ITEMS items a relation (the counterfactual capped at its hand-written list). The 8-item deck
    (seed 1859, logic.csv) is the one every reading so far used; the 40-item deck (2026-11-08, Justin: the 50m's
    reason for being is the chaining gain; seed 1860, logic-40.csv) is read beside it, its bands a little over
    half as wide. `cause_only` writes the wide cause deck (96 items, seed 1861, logic-cause.csv): the one
    relation Qwen3 4B actually shows a gain on, widened until its interval can resolve 0.1."""
    global ITEMS
    ITEMS = items
    rng = random.Random(seed)
    words = nonce_words(5 * items + 40 if cause_only else 7 * 5 * items + 40, rng)
    rows = []
    makers = (
        (cause_items,)
        if cause_only
        else (
            order_items,
            cause_items,
            membership_items,
            proportion_items,
            counterfactual_items,
        )
    )
    for make in makers:
        rows += make(rng, words)
    p = ROOT / "lists" / "tricks" / out
    cols = [
        "item",
        "relation",
        "variant",
        "prompt",
        "frame",
        "idea",
        "rival",
        "bridge",
        "distractor",
        "answer_word",
    ]
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**{k: r.get(k, "") for k in cols}, "prompt": f"{r['pre']} {r['frame']}"})
    print(len(rows), "rows,", len({r["item"] for r in rows}), "items ->", p)


if __name__ == "__main__":
    import sys

    a = sys.argv[1:]
    cause_only = "--cause-only" in a
    a = [x for x in a if x != "--cause-only"]
    if cause_only:
        main(
            int(a[0]) if a else 96,
            int(a[1]) if len(a) > 1 else 1861,
            a[2] if len(a) > 2 else "logic-cause.csv",
            cause_only=True,
        )
    else:
        main(int(a[0]), int(a[1]), a[2]) if a else main()
