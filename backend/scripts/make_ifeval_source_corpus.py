"""The source grade: fresh IFEval-style prompts, written by code from the official rule types (14 November 2026,
knockout:10; Justin: "the build the stuff next for piroirty 2 and 3").

The taught 9m (9m@v0.0.6-return-taught) learned from 360 of the official prompts and followed only 37.4% of the 139
it never saw: a few hundred prompts teach their own wording, not the rules. This corpus teaches the rules from many
prompts instead, and keeps every one of the 541 official prompts out, so the whole official set is a fair test.

Each lesson:

- a fresh task, written by code from a template and a topic ("Write a letter to a friend about baking bread.");
- one to three instructions, drawn from the official registry (thorp/ifeval_eval/instructions_registry.py) in about
  the official set's proportions, with conflicting pairs never together (the registry's own conflict table); each
  instruction's wording and its parameters are the registry's own `build_description`, drawn at random as the
  benchmark's authors drew them, so the rules are the benchmark's and the prompts are not;
- the response the official checkers pass, built by the return leg's builder (make_ifeval_corpus.prove), kept only if
  it still passes after the cleaning the voyage reads it with (as make_return_corpus.py keeps its turns).

Responses in other languages cannot be written (the ship reads English), so `language:response_language` is asked
for English only. A lesson whose prompt matches an official prompt is refused (none do: the tasks are new).

The mix (`lists/ifeval-source-mix-marked-v1.csv`): the taught leg's talk turns, book for book, with SOURCE_PER of
these lessons a book in place of its 20 split prompts, and Ogden v0.1.4 books beside them as replay, about as much
text as the turns (the taught leg's language fell from 1.70 to 2.53 bits a byte on the hole cards).

    NLTK_DATA=ships/lists/nltk_data PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_ifeval_source_corpus.py [--dry-run] [--n N]
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
os.environ.setdefault("NLTK_DATA", str(ROOT / "ships/lists/nltk_data"))

import make_ifeval_corpus as ifc  # noqa: E402  (the official checks and the response builder)
import make_talk_corpus as talk  # noqa: E402  (the book writer, the separator and the talk turns)

from thorp import cleaning, manifest, paths, turns  # noqa: E402
from thorp.ifeval_eval import instructions_registry as registry  # noqa: E402

LIST = "lists/ifeval-source-mix-marked-v1.csv"
LESSONS = "lists/ifeval-source-v1.jsonl"  # every lesson's prompt, rules and response, for the record
VERSION = "ifeval-source-mix-marked-v1"
N = 20_000
SOURCE_PER = 20  # lessons a talk book, as the taught mix carried 20 split prompts a book
OGDEN = "lists/ogden-v0.1.4.csv"
OGDEN_SHARE = 1.0  # Ogden replay text, as a share of the turns' text
CLEAN = "marks-v1"
SEED = 20261114
SIZES = (1, 1, 1, 1, 1, 2, 2, 2, 3)  # instructions a prompt: about the official 305 / 179 / 57

TASKS = (
    "Write a short story about {t}.", "Write a letter to a friend about {t}.", "Describe {t}.",
    "Write a short essay on {t}.", "Give some advice about {t}.", "Write a poem about {t}.",
    "Explain {t} to a child.", "Write a blog post about {t}.", "Write a short speech about {t}.",
    "Write a diary entry about {t}.", "Write a note to a neighbour about {t}.", "Tell me about {t}.",
    "Write an email to your boss about {t}.", "List some things worth knowing about {t}.", "Write a song about {t}.",
    "Write a review of a day spent on {t}.", "Write a plan for {t}.", "Write a short report on {t}.",
    "What should a beginner know about {t}?", "Write a funny story about {t}.", "Write a thank-you note about {t}.",
    "Write a newspaper piece about {t}.", "Write a guide to {t} for a new friend.", "Write a riddle about {t}.",
)  # fmt: skip


def topics() -> list[str]:
    import teach_chat_corpus as teach  # its everyday topics: plain, varied and nothing like the official tasks

    got = teach.TOPICS if isinstance(teach.TOPICS, list) else teach.TOPICS.replace("\n", " ").split(";")
    return [t.strip() for t in got if t.strip()]


def weights() -> dict[str, float]:
    """Each rule type's share of the official set, so the lessons ask for them about as often."""
    c = collections.Counter(
        i for line in ifc.PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()
        for i in json.loads(line)["instruction_id_list"]
    )  # fmt: skip
    return {iid: float(c.get(iid, 1)) for iid in registry.INSTRUCTION_DICT}


def draw(rng: random.Random, w: dict[str, float], conflicts: dict, k: int) -> list[str]:
    ids: list[str] = []
    pool = list(w)
    for _ in range(50):
        if len(ids) == k:
            break
        iid = rng.choices(pool, weights=[w[p] for p in pool])[0]
        if iid in ids or any(iid in conflicts.get(x, ()) or x in conflicts.get(iid, ()) for x in ids):
            continue
        ids.append(iid)
    return ids


def lesson(i: int, rng: random.Random, w: dict, conflicts: dict, tops: list[str]) -> dict | None:
    task = rng.choice(TASKS).format(t=rng.choice(tops))
    ids = draw(rng, w, conflicts, rng.choice(SIZES))
    descs, kwargs = [], []
    random.seed(SEED * 7 + i)  # the registry draws its parameters from the module's random
    for iid in ids:
        inst = registry.INSTRUCTION_DICT[iid](iid)
        if iid == "combination:repeat_prompt":
            descs.append(inst.build_description(prompt_to_repeat=task))
        elif iid == "language:response_language":
            descs.append(inst.build_description(language="en"))
        else:
            descs.append(inst.build_description())
        args = inst.get_instruction_args() or {}
        kwargs.append({k: v for k, v in args.items() if v is not None})
    order = rng.random()
    if "combination:repeat_prompt" in ids:  # its wording carries the task itself: it leads, as in the official set
        j = ids.index("combination:repeat_prompt")
        rest = [d for n, d in enumerate(descs) if n != j]
        prompt = " ".join([descs[j]] + rest)
    elif order < 0.8:
        prompt = " ".join([task] + descs)
    else:
        prompt = " ".join(descs + [task])
    return {"key": f"src-{i + 1}", "prompt": prompt, "instruction_id_list": ids, "kwargs": kwargs}


def proved(row: dict) -> tuple[str, str] | None:
    """(the marked turn, the response) when the response passes the official checks after the voyage's cleaning."""
    try:
        text = ifc.prove(row)
    except (IndexError, ValueError, KeyError, TypeError):  # parameters the builders were never shown (the 541's are)
        return None
    if text is None:
        return None
    raw = turns.pair("marks", row["prompt"], text)
    book = cleaning.clean(raw, CLEAN)
    answer = turns.answer_of("marks", book.replace("<bos>\n", "", 1).replace("\n<eos>", ""), row["prompt"], "unwrap-v2")
    return (raw, answer) if ifc.follows(row, answer) else None


def build(dry_run: bool, n: int) -> dict:
    rng = random.Random(SEED)
    w, conflicts, tops = weights(), registry.conflict_make(registry.INSTRUCTION_CONFLICTS), topics()
    official = {json.loads(line)["prompt"].strip() for line in ifc.PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()}
    kept: list[tuple[dict, str]] = []
    tried, refused, seen = 0, collections.Counter(), set()
    t0 = time.time()
    while len(kept) < n and tried < n * 3:
        row = lesson(tried, rng, w, conflicts, tops)
        tried += 1
        if not row or not row["instruction_id_list"] or row["prompt"] in seen:
            refused["drawn twice"] += 1
            continue
        if row["prompt"].strip() in official:
            refused["an official prompt"] += 1
            continue
        got = proved(row)
        if got is None:
            refused["not provable"] += 1
            continue
        seen.add(row["prompt"])
        kept.append((row, got[0]))
    by_type = collections.Counter(i for r, _ in kept for i in r["instruction_id_list"])
    out = {
        "lessons": len(kept), "tried": tried, "refused": dict(refused), "seconds": round(time.time() - t0),
        "passing_share": round(len(kept) / max(tried - refused["drawn twice"], 1), 3),
        "by_size": dict(sorted(collections.Counter(len(r["instruction_id_list"]) for r, _ in kept).items())),
        "by_type": dict(by_type.most_common()), "official_prompts_in_it": 0,
        "sample": [t for _, t in kept[:4]],
    }
    if dry_run:
        return out
    d = paths.texts_dir("local")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    talk_books = []
    for r in csv.DictReader(open(paths.resolve(talk.LIST), encoding="utf-8")):
        text = (d / f"{r['text'].split(':', 1)[1]}.txt").read_text(encoding="utf-8")
        talk_books.append(text[:-1].split(talk.SEP))
    lessons = [t for _, t in kept]
    rows, k = [], 0
    for b, parts in enumerate(talk_books):
        mine = [lessons[(k + j) % len(lessons)] for j in range(SOURCE_PER)]
        k += SOURCE_PER
        items = parts + mine
        items.sort(key=lambda t: hashlib.sha1((str(b) + "\x00" + t).encode()).hexdigest())
        rows.append(talk._book(d, f"srcmix-{b + 1:05d}", f"source-grade mix {b + 1} (marked)", "the source-grade leg",
                               talk.SEP.join(items) + "\n", now))  # fmt: skip
    turn_chars = sum(len(talk.SEP.join(p)) for p in talk_books) + sum(len(t) for t in lessons) * (k / len(lessons))
    ogden = list(csv.DictReader(open(paths.resolve(OGDEN), encoding="utf-8")))
    random.Random(SEED + 1).shuffle(ogden)
    replay, chars = [], 0
    for r in ogden:
        if chars >= turn_chars * OGDEN_SHARE:
            break
        b = manifest.get(r["text"].split(":", 1)[1])
        if b is None:
            continue
        replay.append(r)
        chars += b.chars
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        wr.writeheader()
        wr.writerows(rows + [{k2: r[k2] for k2 in ("title", "author", "language", "family", "text")} for r in replay])
    with open(paths.resolve(LESSONS), "w", encoding="utf-8") as f:
        for row, raw in kept:
            f.write(json.dumps({**row, "turn": raw}, ensure_ascii=False) + "\n")
    out.update({"books": len(rows), "copies_of_each_lesson": round(k / len(lessons), 2), "ogden_books": len(replay),
                "ogden_chars": chars, "turn_chars": int(turn_chars)})  # fmt: skip
    meta = {"version": VERSION, "generator": "backend/scripts/make_ifeval_source_corpus.py", "seed": SEED,
            "about": "the taught leg's talk turns, book for book, with fresh code-written IFEval-style lessons in place of "
                     "the split prompts (none of the 541 official prompts), and Ogden v0.1.4 books beside them as replay",
            "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
            **{k2: v for k2, v in out.items() if k2 != "sample"}}  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--n", type=int, default=N)
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run, a.n), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
