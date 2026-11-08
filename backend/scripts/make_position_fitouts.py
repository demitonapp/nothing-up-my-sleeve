"""The four positions at the 1m, as fitouts and voyages (DECISIONS.md, "Four positions at the 1m"; Justin, 2026-11-08: "queue
em, the vsm should pick them up"). Augustus's arm is Ogden v0.1 + De Morgan's tutor at 2% (`ogden-v0-1-maths2`, written and
queued by the Phaleron plan); this writes the other three the same way, on Ogden v0.1 and the same 1m, so the four are read
against one another and against the plain Augustus (the control): Ogden v0.1 + Plato's primer, + Francis's primer, and + Diderot's
slice (a matched draw of other books, equal by kind), each about 0.8M words, 2% of the reading.

Each fitout's books are composed from a declared selection (thorp/selection.py, s3_control/compose.py): v0.1's list carried and
the slice appended up to its words. Each voyage is the maths arm's spec with its reading changed and the primers' tests added to
its evaluators (every ship reads the maths book, Plato's and Francis's items). Then each fitout's prechecks run, each voyage goes
through the S3 gate, and, with --queue, is put at the end of the standing queue (S2's own `append`, under the lock).

    uv run --project backend python backend/scripts/make_position_fitouts.py [--queue]
"""

from __future__ import annotations

import copy
import json
import sys

import yaml

from thorp import paths

SLICE_WORDS = 800_000  # the maths arm's slice is 0.81M words (2.2% of the reading)
TEMPLATE = "specs/fitouts/fu-ogden-v0-1-maths2@1m-pre-s1.yaml"
APPROVED = 'approved by Justin (2026-11-08: "Approve the chapters"; "Yes, 2%")'
POSITIONS = {
    "plato": {
        "title": "Plato's primer", "slug": "plato2", "pos": "metaphysics",
        "reads": "the first books of Plato's primer (thorp/primers.py: kinds, things and qualities, same and like, seems and is, one and many, cause and reason, has to be and may be)",
        "append": {"list": "lists/primer-plato.csv", "words": SLICE_WORDS, "why": "Plato's primer, 2% of the reading"},
        "opt_in": f"Plato's primer: Thorp's own lessons in kinds, qualities, sameness and cause, in Ogden's words, local books outside the two stores, {APPROVED}",
    },
    "francis": {
        "title": "Francis's primer", "slug": "francis2", "pos": "empirical knowledge",
        "reads": "the first books of Francis's primer (thorp/primers.py: same cause and effect, one change at a time, what is always there, more and more, one case against, how much to say, what to look at, seen and given)",
        "append": {"list": "lists/primer-francis.csv", "words": SLICE_WORDS, "why": "Francis's primer, 2% of the reading"},
        "opt_in": f"Francis's primer: Thorp's own lessons in observation and its checking, in Ogden's words, local books outside the two stores, {APPROVED}",
    },
    "diderot": {
        "title": "Diderot's slice", "slug": "diderot2", "pos": "generalised knowledge (the control)",
        "reads": "a draw of other library books, equal by kind and matched in words to the other slices (plans/diderot-slice.json)",
        "append": {"list": "lists/composed/diderot-slice.csv", "why": "Diderot's slice: a matched draw of other books, equal by kind"},
        "opt_in": f"Diderot's slice: a seeded draw of library books outside the two stores, equal by kind and matched in words to the other positions' slices, {APPROVED}",
    },
}
DIDEROT_SLICE = {
    "note": "Diderot's matched slice: other books, equal by kind, none of Ogden v0.1's, up to 0.8M words (2% of the reading)",
    "languages": {"en": 1.0}, "as_of": "2026-11-07", "not_in": ["lists/ogden-v0.1.csv"], "max_book_words": 60000,
    "kinds": {"exclude": ["derived", "periodical", "reference", "other", "practical", "religion", "sermon", "dialogue", "textbook"]},
    "weights": {"kind": {k: 0.1 for k in ("novel", "stories", "poem", "play", "essay", "history", "biography", "philosophy", "science", "travel")}},
    "words": SLICE_WORDS, "rank": "hash", "seed": 1,
}  # fmt: skip


def fitout_json(key: str, who: str, p: dict) -> dict:
    sel = {"languages": {"en": 1.0}, "carry": ["lists/ogden-v0.1.csv"], "carry_only": True, "order": "carried-first", "append": [p["append"]],
           "note": f"Ogden v0.1's 592 books and {p['title']}, about {SLICE_WORDS / 1e6:.1f}M words, 2% of the reading"}  # fmt: skip
    return {
        "key": key, "name": f"Ogden v0.1 + {p['title']}, 2%", "positions": "rope", "tack": None, "opt_in": p["opt_in"],
        "aim": f"{who.capitalize()}'s reading, the {p['pos']} position at the 1m (DECISIONS.md, \"Four positions at the 1m\"): Ogden v0.1 and {p['reads']}, 2% of the reading; read against Augustus (De Morgan's tutor at 2%) and the plain 1m",
        "stages": [{"phase": "pretraining", "name": f"ogden-v0.1-{p['slug']}", "shelf": f"lists/composed/{key}-1.csv", "tokens": None, "select": "all",
                    "passes": 4, "lr": None, "tack": None, "purpose": f"Ogden v0.1 and {p['title']}, four passes", "compose": sel}],
    }  # fmt: skip


def spec_for(key: str, who: str, p: dict) -> dict:
    t = yaml.safe_load(paths.resolve(TEMPLATE).read_text())
    s = copy.deepcopy(t)
    s["name"] = f"fu-{key}@1m-pre-s1"
    s["ship"] = f"Fitout: Ogden v0.1 + {p['title']} 2% @ 1m, pretraining"
    s["experiment"] = f"Fitout {key}: Ogden v0.1 with 2% of the reading {p['title']}: the {p['pos']} position at the 1m"
    s["question"] = f"Does a 1m that reads {p['title']} at 2% of its reading beat the others on its own position's items (and the maths book, Plato's and Francis's items)?"
    s["fitout"] = {"key": key, "variation": None}
    s["data"]["recipe"] = f"lists/composed/{key}-1.csv"
    s["data"]["opt_in"] = p["opt_in"]
    for ev in (s["eval"]["evaluators"], s["eval"]["light"]["evaluators"]):
        for name in ("plato", "francis"):
            if name not in ev:
                ev.append(name)
    return s


def main(queue: bool = False) -> int:
    from thorp import vsm
    from thorp.viable.s1_operations import prechecks
    from thorp.viable.s2_coordination import lanes
    from thorp.viable.s3_control import compose

    plan = paths.resolve("plans") / "diderot-slice.json"
    plan.write_text(json.dumps(DIDEROT_SLICE, indent=1) + "\n")
    compose.run("plans/diderot-slice.json", by="make_position_fitouts")
    lines = []
    for who, p in POSITIONS.items():
        key = f"ogden-v0-1-{p['slug']}"
        f = fitout_json(key, who, p)
        (paths.fitouts_dir() / f"{key}.json").write_text(json.dumps(f, indent=1) + "\n")
        r = compose.run(key, by="make_position_fitouts")
        assert r["passed"], f"{key}: the gate's library prechecks refuse the list"
        s = spec_for(key, who, p)
        out = paths.resolve(f"specs/fitouts/{s['name']}.yaml")
        out.write_text("# the four positions at the 1m (DECISIONS.md): built by scripts/make_position_fitouts.py\n" + yaml.safe_dump(s, sort_keys=False, width=100))
        (paths.data_dir() / "runs" / "fitouts").mkdir(parents=True, exist_ok=True)
        print(f"{who}: {s['name']}")
        lines.append((who, key, s))
    from thorp import fitouts
    from thorp.viable.precheck_item import Context
    from thorp.viable.s2_coordination import tagger

    base_books = set(__import__("thorp.selection", fromlist=["list_ids"]).list_ids("lists/ogden-v0.1.csv"))
    for _who, key, s in lines:
        f = fitouts.load(key)
        ctx = Context(fitout=f, specs=[s])
        extra = [b for b in ctx.books if b not in base_books]
        if not (tagger.meta(key) or {}).get("books") == len(ctx.books):
            tagger.extend_lexicon("ogden-v0-1", extra, len(ctx.books), ctx.clean, key)  # v0.1's counts, the new books tagged on top
        prechecks.run(key, by="make_position_fitouts")
        vsm.gate(s, where="the four positions")
    if queue:
        q = paths.resolve("specs/queue.txt")
        for who, _key, s in lines:
            lanes.append(q, f"fitouts/{s['name']}", note=f"The four positions at the 1m (DECISIONS.md, \"Four positions at the 1m\"; Justin, 8 November: \"queue em\"): {POSITIONS[who]['pos']}, seed 1, Ogden v0.1 + 2%")
            print(f"queued {s['name']}")
    return 0


def more_seeds(seed: int) -> int:
    """The same four voyages at another seed (a position counts at a size only on two): each seed-1 spec copied with the seed
    and the name's suffix changed (Augustus's is the maths arm), through the gate, and put at the end of the queue."""
    from thorp import vsm
    from thorp.viable.s2_coordination import lanes

    q = paths.resolve("specs/queue.txt")
    keys = ("ogden-v0-1-maths2", *(f"ogden-v0-1-{p['slug']}" for p in POSITIONS.values()))
    for key in keys:
        s = yaml.safe_load(paths.resolve(f"specs/fitouts/fu-{key}@1m-pre-s1.yaml").read_text())
        s["name"], s["seed"] = f"fu-{key}@1m-pre-s{seed}", seed
        out = paths.resolve(f"specs/fitouts/{s['name']}.yaml")
        out.write_text(f"# the four positions at the 1m, seed {seed} (DECISIONS.md): built by scripts/make_position_fitouts.py --seed {seed}\n" + yaml.safe_dump(s, sort_keys=False, width=100))
        vsm.gate(s, where="the four positions, a second seed")
        lanes.append(q, f"fitouts/{s['name']}", note=f"The four positions at the 1m, seed {seed} (DECISIONS.md; Justin, 8 November: \"Queue seeds now\"): a position counts at a size only on two seeds")
        print(f"queued {s['name']}")
    return 0


if __name__ == "__main__":
    if "--seed" in sys.argv:
        sys.exit(more_seeds(int(sys.argv[sys.argv.index("--seed") + 1])))
    sys.exit(main("--queue" in sys.argv))
