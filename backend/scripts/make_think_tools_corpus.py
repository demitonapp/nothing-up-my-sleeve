"""Think, then act: the tool lessons with a decision written before each move (13 November 2026; Justin: "It's more I
want to ask something and it can be simple. Like check the weather. Reasoning kicks in and iterates through the
tools, if none matches then it replies"; then "Yes, build it").

The lessons are the very ones the instruct 21m read (`lists/50m-instruct-v2.csv`: the conversation corpus, the tool
lessons v2 and 136 Ogden books), read back from their books, so the one thing that differs between that ship and this
one is the thinking. Code writes each decision (thorp/turns.py `acted`):

- a call: what the person wants, in a few words, then the tool that does it, then the call:
  `<question>What is 34 times 12?<think>They want a sum worked out. calculate does that.<call>calculate(34*12)<result>408<answer>...`
- no tool wanted (a quarter of the tool lessons): the decision that no tool is for it, sometimes after naming what the
  tools are for, then the answer;
- no tool can (new: the chat corpus's honest answers to what a small helper cannot know, `edges` in
  `lists/chat-teaching-v1.json`): what they want, what the tools are for, that none can tell it, then the honest answer.

The decision is short on purpose (about 10 to 60 pieces): a small ship writes as long as its lessons, and long traces
sent a 90M tool caller into output that never ended (backend/scripts/make_tool_corpus.py).

Held out (`lists/think-tools-heldout-v1.jsonl`): the tool lessons v2's held-out items, unchanged, so this ship and the
instruct 21m are read on the same questions, and a fifth of the cannot pairs (kind `cannot`, no call wanted).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_think_tools_corpus.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_talk_corpus as talk  # noqa: E402  (the book writer and the separator)

from thorp import cleaning, paths, turns  # noqa: E402

BASE = "lists/50m-instruct-v2.csv"  # the instruct 21m's mix: its tool books are rewritten, the rest kept as they are
BASE_HELD = "lists/tools-heldout-v2.jsonl"
TEACHING = "lists/chat-teaching-v1.json"  # the cannot pairs (`edges`)
LIST = "lists/think-tools-mixed-v1.csv"
HELD = "lists/think-tools-heldout-v1.jsonl"
VERSION = "think-tools-mixed-v1"
PER = 40
CANNOT_REPEAT = 4  # each cannot pair read this often (384 pairs: about 1,500 lessons beside 20,000 tool lessons)
HELD_SHARE = 0.2
CLEAN = "marks-v1"
SEED = 20261113

NEED = {
    "calculate": ["They want a sum worked out.", "This is a sum to work out.", "There is a number to work out here."],
    "current_time": ["They want the date or the time.", "This asks for today's date or the time."],
    "days_between": ["They want the days between two dates.", "This asks how many days lie between two dates."],
    "define": ["They want to know what a word means.", "This asks for the meaning of a word."],
    "board_score": ["They want a score from the board.", "This asks how a model did on the board."],
    "queue_status": ["They want to know about the queue.", "This asks what the queue is doing."],
    "liberty_machine_status": ["They want to know how the Liberty Machine is.", "This asks about the Liberty Machine."],
    "expedition_status": ["They want to know how an expedition is going.", "This asks about an expedition."],
}
PICK = ["{tool} does that.", "The tool for that is {tool}.", "{tool} is the tool for it."]
THEN = "First {a}, then {b}."
TOOLS = ("My tools are for sums, the date and time, days between dates, word meanings, and Thorp's board, queue, "
         "Liberty Machine and expeditions.")  # fmt: skip
NONE = ["No tool is needed for this. I can answer it myself.", "None of my tools is for this, so I answer it myself.",
        "This is just talk. No tool fits, so I answer it myself."]  # fmt: skip
CANNOT_NEED = {  # chat-teaching-v1's edge kinds, as what the person wants
    "today's news": "the news", "the price of something": "a price as it is now", "a private person": "to know about a "
    "private person", "the result of a game": "the result of a game", "the weather": "the weather now", "a hard question "
    "for a doctor": "advice a doctor or a lawyer should give", "something only the person can know": "something only "
    "they can know", "a long, deep expert": "a long expert explanation",
}  # fmt: skip
CANNOT = ["None of them can tell me that, and I have no internet. So I say I cannot.",
          "None of them is for that. So I say so, and say who might know."]  # fmt: skip

_TURN = re.compile(r"<question>(.*?)((?:<call>.*?<result>.*?)*)<answer>(.*?)<end>", re.S)
_CALL = re.compile(r"<call>(.*?)<result>(.*?)(?=<call>|$)", re.S)


def parse(turn: str) -> dict | None:
    """A written lesson back into its parts: {"question", "calls": [(call, result)], "answer"}; None if it is not one."""
    m = _TURN.search(turn)
    if not m:
        return None
    calls = [(c.strip(), r.strip()) for c, r in _CALL.findall(m.group(2))]
    return {"question": m.group(1).strip(), "calls": calls, "answer": m.group(3).strip()}


def tool_of(call: str) -> str:
    return call.split("(", 1)[0].strip()


def steps_for(lesson: dict, rng: random.Random) -> str:
    """The decision before a lesson's move, written by code."""
    calls = lesson["calls"]
    if not calls:
        return (TOOLS + " " if rng.random() < 0.5 else "") + rng.choice(NONE)
    names = [tool_of(c) for c, _ in calls]
    need = rng.choice(NEED.get(names[0], ["They want something a tool can do."]))
    if len(names) > 1:
        return f"{need} {THEN.format(a=names[0], b=names[1])}"
    return f"{need} {rng.choice(PICK).format(tool=names[0])}"


def cannot_steps(kind: str, rng: random.Random) -> str:
    need = next((v for k, v in CANNOT_NEED.items() if kind.startswith(k)), "something I cannot know")
    return f"They want {need}. {TOOLS} {rng.choice(CANNOT)}"


def read_books(ids: list[str]) -> list[str]:
    d = paths.texts_dir("local")
    out: list[str] = []
    for bid in ids:
        text = (d / f"{bid}.txt").read_text(encoding="utf-8")
        out += [t for t in text.split(talk.SEP) if "<question>" in t]
    return out


def build(dry_run: bool) -> dict:
    rng = random.Random(SEED)
    rows = list(csv.DictReader(open(paths.resolve(BASE), encoding="utf-8")))
    tool_ids = [r["text"].split(":", 1)[1] for r in rows if r["text"].startswith("local:tool-")]
    kept_rows = [r for r in rows if not r["text"].startswith("local:tool-")]
    lessons = [p for p in (parse(t) for t in read_books(tool_ids)) if p]
    for x in lessons:
        x["text"] = turns.acted(x["question"], steps_for(x, rng), x["calls"], x["answer"])
    # the cannot pairs: a fifth held out by kind, the rest read CANNOT_REPEAT times, each with its own decision
    teach = json.loads(paths.resolve(TEACHING).read_text(encoding="utf-8"))
    cannot_train, cannot_held = [], []
    for kind, pairs in sorted((teach.get("edges") or {}).items()):
        pairs = [tuple(p) for p in pairs if len(p) == 2]
        random.Random(SEED + len(kind)).shuffle(pairs)
        cut = max(1, round(len(pairs) * HELD_SHARE))
        cannot_held += [(kind, q, a) for q, a in pairs[:cut]]
        cannot_train += [(kind, q, a) for q, a in pairs[cut:]]
    for kind, q, a in cannot_train:
        for _ in range(CANNOT_REPEAT):
            lessons.append({"question": q, "calls": [], "answer": a, "kind": "cannot",
                            "text": turns.acted(q, cannot_steps(kind, rng), [], a)})  # fmt: skip
    rng.shuffle(lessons)
    held = [json.loads(line) for line in paths.resolve(BASE_HELD).read_text(encoding="utf-8").splitlines() if line.strip()]
    held += [{"key": f"cannot-{i + 1}", "kind": "cannot", "prompt": q, "call": None, "tool": None, "result": None,
              "answer": a} for i, (_, q, a) in enumerate(cannot_held)]  # fmt: skip
    words = [len((turns.after_thought(turns.THINK + x["text"].split(turns.THINK, 1)[1])[0] or "").split())
             for x in lessons]  # fmt: skip
    out = {
        "tool_lessons": sum(1 for x in lessons if x.get("kind") != "cannot"),
        "cannot_lessons": sum(1 for x in lessons if x.get("kind") == "cannot"),
        "with_a_call": sum(1 for x in lessons if x["calls"]),
        "held_out": {"tools-heldout-v2": len(held) - len(cannot_held), "cannot": len(cannot_held)},
        "decision_words": {"median": sorted(words)[len(words) // 2], "max": max(words)},
        "kept_books": len(kept_rows),
        "sample": [x["text"] for x in lessons[:6]],
    }
    if dry_run:
        return out
    d = paths.texts_dir("local")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    new_rows, read_back = [], 0
    for i in range(0, len(lessons), PER):
        bid = f"think-tool-{i // PER + 1:05d}"
        part = lessons[i : i + PER]
        text = talk.SEP.join(x["text"] for x in part) + "\n"
        read_back += sum(x["text"] in cleaning.clean(text, CLEAN) for x in part)
        new_rows.append(talk._book(d, bid, f"think-then-act lessons {i // PER + 1}", "the think-then-act leg", text, now))
    with open(paths.resolve(LIST), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(kept_rows + new_rows)
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for h in held:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    out["books_written"] = len(new_rows)
    out["reads_as_written"] = [read_back, len(lessons)]
    meta = {"version": VERSION, "generator": "backend/scripts/make_think_tools_corpus.py", "base": BASE, "seed": SEED,
            "about": "the instruct 21m's mix with each tool lesson given a decision before its move, and the chat "
                     "corpus's cannot pairs added, each with its decision",
            "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
            **{k: v for k, v in out.items() if k != "sample"}}  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
