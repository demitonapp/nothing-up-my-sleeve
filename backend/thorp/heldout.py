"""Everything held out: the sets a ship is scored on and never trains on, in one place (13 November, Justin: "we need an
easy place to find tools heldout and all the other type of "hole" type content").

Three groups:

- **questions**: the held-out questions the legs' tests ask (the tool calls, the reasoning chains, the conversations,
  the instructions), each with what a right answer looks like;
- **books**: the decks of whole books ships are scored on and never read (the hole cards, the Forgotten Tomes, the
  truths, the content experiment's held-out books);
- **outside**: the field's own tests, kept under `data/` because their licences do not let them into the repository.

`sets()` is the list (what each set is, what reads it, how many items, the specs that name it); `items(key, ...)` reads
one set's items, normalised to a question, what came before it, and what a right answer is. The Library's "Held out"
section shows both (/library/held-out).
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from thorp import paths

# key, name, group, path, status, what it tests, the test that reads it (and its readings), how it was made
SETS: list[dict] = [
    {"key": "tools-heldout-v2", "name": "Tool questions v2", "group": "questions", "path": "lists/tools-heldout-v2.jsonl",
     "status": "current",
     "tests": "Calling the eight tools: given a question, does the ship write the right call (calculate(87*42)), name the "
              "right tool, and answer at once when no tool is wanted?",
     "reads": "the tools test (evaluators/tools.py): tools/exact, tools/tool, tools/none_right, tools/score; the ship's "
              "first move only, the final answer is not graded",
     "made": "Set aside from the tool corpus v2 before training (scripts/make_tool_corpus.py, 13 November): 300 calls in "
             "wordings the ship never trained on, and 78 everyday questions that want no tool. The calls and results are "
             "code's; the question patterns are the teacher's (Qwen3.8 27B)."},
    {"key": "tools-heldout-v1", "name": "Tool questions v1", "group": "questions", "path": "lists/tools-heldout-v1.jsonl",
     "default_for": "tools",
     "status": "retired",
     "tests": "Calling the eight tools, with lines from plays standing in for the questions that want no tool.",
     "reads": "the tools test, on the first 9m tool leg (9m@v0.0.6-fleetmarks-tools)",
     "made": "Set aside from the tool corpus v1 (12 November). Its 50 no-tool items were lines from plays, not everyday "
             "questions, and the first 9m tool leg learned that every plain question wants a call; v2 replaced it."},
    {"key": "reasoning-heldout-v1", "name": "Reasoning chains", "group": "questions", "path": "lists/reasoning-heldout-v1.jsonl",
     "default_for": "reasoning",
     "status": "current",
     "tests": "Thinking between marks: given a puzzle in made-up words (a polik is heavier than a sop...), is the ship "
              "right when it writes its steps first, and right when it answers at once?",
     "reads": "the reasoning test (evaluators/reasoning.py): reasoning/on (thinking), reasoning/off (at once), "
              "reasoning/gain (what thinking adds), reasoning/thought",
     "made": "Set aside from the reasoning corpus (scripts/make_reasoning_corpus.py, 12 November): six kinds (order, "
             "count, set, cause, place, kin) of two- to four-step chains, the answers balanced between yes, no and other."},
    {"key": "conversation-heldout-v1", "name": "Conversations", "group": "questions", "path": "lists/conversation-heldout-v1.jsonl",
     "status": "current",
     "tests": "Answering in a conversation: is the true reply cheaper to predict after its own question than after "
              "another's (the question gain), and does the history before it help?",
     "reads": "the question-gain test (evaluators/question_gain.py): gain/question, gain/own_wins, gain/history",
     "made": "400 exchanges from books the conversation leg never read, with the turns before them; each says the book it "
             "came from and how its turns were found (labelled or quoted)."},
    {"key": "talk-heldout-v1", "name": "Talk pairs", "group": "questions", "path": "lists/talk-heldout-v1.jsonl",
     "status": "retired",
     "tests": "Replying to a line: how well the ship predicts the true reply to a line of dialogue.",
     "reads": "the answers test (evaluators/answers.py) on the 9m talk legs: answers/bpb, answers/stopped",
     "made": "400 line-and-reply pairs quoted from books the talk legs never read (12 November)."},
    {"key": "return-heldout-v1", "name": "Instructions (return leg)", "group": "questions", "path": "lists/return-heldout-v1.jsonl",
     "default_for": "answers",
     "status": "retired",
     "tests": "Following an instruction in the reply's form (wrap the answer in JSON, no commas...).",
     "reads": "the answers test (evaluators/answers.py) on the 9m return leg",
     "made": "139 IFEval-style prompts with a written response each, held out of the instruction stage."},
    {"key": "ifeval-input-v1", "name": "IFEval prompts", "group": "questions", "path": "lists/ifeval-input-v1.jsonl",
     "default_for": "ifeval",
     "status": "current",
     "tests": "Following verifiable instructions: Google's IFEval, 541 prompts each with rules a script can check.",
     "reads": "the IFEval test (evaluators/ifeval.py): the share of prompts, and of instructions, followed",
     "made": "IFEval's own input set (Zhou et al. 2023, Apache 2.0), copied in as it is."},
    {"key": "ifeval-heldout-v1", "name": "IFEval pairs held out", "group": "books", "path": "lists/ifeval-heldout-v1.csv",
     "status": "current",
     "tests": "The instruction stage's held-out pairs, as texts: what a ship's language costs on instructions it never read.",
     "reads": "scored as a deck (bits per byte) by the instruction legs",
     "made": "The IFEval-style pairs left out of the instruction stage's training lists."},
    {"key": "hole-cards-unseen", "name": "The Forgotten Tomes", "group": "books", "path": "lists/hole-cards-unseen.csv",
     "status": "current",
     "tests": "Language on books no model has read: the fleet's main yardstick (eval/hole-cards-unseen/bpb_mean).",
     "reads": "every voyage's evaluation, every 640 steps on the big ships; the best checkpoint is picked on it",
     "made": "Books released on Gutenberg after Qwen 3.8's training ended, so no outside model has read them either."},
    {"key": "hole-cards", "name": "Hole cards", "group": "books", "path": "lists/hole-cards.csv",
     "status": "current",
     "tests": "Language on classics the ships are refused: the first held-out deck.",
     "reads": "the deck evaluations (bits per byte); refused by every training run",
     "made": "Chosen in the first week; the stage refuses them from every recipe."},
    {"key": "hole-cards-v2", "name": "Hole cards II", "group": "books", "path": "lists/hole-cards-v2.csv",
     "status": "current",
     "tests": "The first deck widened: more held-out classics.",
     "reads": "the deck evaluations (bits per byte)",
     "made": "The first deck with six more books."},
    {"key": "truths", "name": "Truths", "group": "books", "path": "lists/truths.csv",
     "status": "current",
     "tests": "The treatises the probes score: does the ship find a true statement cheaper than a false one?",
     "reads": "the probes (evaluators/probes.py)",
     "made": "Galileo, Euclid and the other treatises whose statements can be checked."},
    {"key": "held-greek", "name": "Held Greek", "group": "books", "path": "lists/held-greek.csv", "status": "retired",
     "tests": "The content experiment: does a ship that read Greek writing know held-out Greek writing better?",
     "reads": "the content experiment's decks", "made": "Three Greek books kept out of the Greek shelf."},
    {"key": "held-islamic", "name": "Held Islamic", "group": "books", "path": "lists/held-islamic.csv", "status": "retired",
     "tests": "The content experiment, on Islamic writing.", "reads": "the content experiment's decks",
     "made": "Three books kept out of the Islamic shelf."},
    {"key": "held-renaissance", "name": "Held Renaissance", "group": "books", "path": "lists/held-renaissance.csv",
     "status": "retired", "tests": "The content experiment, on Renaissance writing.", "reads": "the content experiment's decks",
     "made": "Three books kept out of the Renaissance shelf."},
    {"key": "arc-ai2", "name": "AI2 ARC", "group": "outside", "path": "data/arc-ai2", "status": "current",
     "tests": "Grade-school science, four choices: ARC-Easy (2,376 questions) and ARC-Challenge (1,172).",
     "reads": "the leaderboard's knowledge test (evaluators/arc_ai2.py)",
     "made": "Allen AI's test set (Clark et al. 2018), fetched once. For research only: never put in the repository or "
             "redistributed; the science shelf's 10-gram match removed it from what the ships read."},
    {"key": "arc-agi-2", "name": "ARC-AGI-2", "group": "outside", "path": "data/arc-agi-2", "status": "current",
     "tests": "Abstract reasoning on coloured grids: 120 public evaluation tasks.",
     "reads": "the leaderboard's ARC-AGI test (thorp/arc.py)", "made": "The ARC Prize's public checkout."},
    {"key": "blimp", "name": "BLiMP", "group": "outside", "path": "data/blimp", "status": "current",
     "tests": "Grammar: 67 kinds of minimal pairs, is the grammatical sentence the cheaper one?",
     "reads": "the BLiMP test (evaluators/blimp.py)", "made": "Warstadt et al. 2020, CC BY 4.0, fetched once."},
]
_BY_KEY = {s["key"]: s for s in SETS}


def _resolve(s: dict) -> Path:
    return paths.resolve(s["path"])


@lru_cache(maxsize=64)
def _rows(path: str, mtime: float) -> tuple[dict, ...]:
    p = Path(path)
    if p.suffix == ".jsonl":
        return tuple(json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip())
    if p.suffix == ".csv":
        with p.open(encoding="utf-8", newline="") as f:
            return tuple(csv.DictReader(f))
    return ()


def rows(key: str) -> tuple[dict, ...]:
    s = _BY_KEY.get(key)
    if not s or s["group"] == "outside":
        return ()
    p = _resolve(s)
    return _rows(str(p), p.stat().st_mtime) if p.is_file() else ()


def _outside_count(s: dict) -> int | None:
    p = _resolve(s)
    if not p.is_dir():
        return None
    if s["key"] == "arc-ai2":  # the two test splits (parquet): 2,376 Easy and 1,172 Challenge
        return 3548 if (p / "ARC-Easy").is_dir() and (p / "ARC-Challenge").is_dir() else None
    if s["key"] == "arc-agi-2":
        ev = p / "data" / "evaluation"
        return len(list(ev.glob("*.json"))) if ev.is_dir() else None
    if s["key"] == "blimp":
        return len([d for d in p.iterdir() if d.is_dir() and not d.name.startswith(".")])
    return None


@lru_cache(maxsize=1)
def _spec_text(stamp: int) -> list[tuple[str, float, str]]:
    root = paths.ships_dir() / "specs"
    return [(str(f.relative_to(root)).removesuffix(".yaml"), f.stat().st_mtime, f.read_text(encoding="utf-8", errors="replace"))
            for f in root.rglob("*.yaml")]  # fmt: skip


def specs_naming(s: dict) -> list[str]:
    """The specs that read this set, newest first: those that name its path, and, for a test's default set, those
    that run that test without naming another set."""
    root = paths.ships_dir() / "specs"
    stamp = int(max((f.stat().st_mtime for f in root.rglob("*.yaml")), default=0))
    ev = s.get("default_for")
    hit = [(m, name) for name, m, text in _spec_text(stamp)
           if s["path"] in text or (ev and f"- {ev}\n" in text and "heldout:" not in text)]  # fmt: skip
    return [name for _, name in sorted(hit, reverse=True)]


def sets() -> dict:
    out = []
    for s in SETS:
        p = _resolve(s)
        rs = rows(s["key"])
        kinds = Counter(str(r.get("kind") or r.get("tool") or "") for r in rs) if s["group"] == "questions" else Counter()
        kinds.pop("", None)
        if s["key"].startswith("tools-heldout"):  # the questions that want no tool, named
            kinds = Counter(str(r.get("tool") or "no tool") for r in rs)
        out.append({
            **s,
            "present": p.exists(),
            "count": len(rs) if s["group"] != "outside" else _outside_count(s),
            "kinds": dict(kinds.most_common()),
            "specs": specs_naming(s) if s["group"] != "outside" else [],
        })  # fmt: skip
    return {"sets": out}


def _item(s: dict, r: dict, i: int) -> dict:
    """One item as the page shows it: the question, what came before, and what a right answer is."""
    if s["group"] == "books":
        text = r.get("text") or ""
        local = text.startswith("local:") or len(text) < 60
        return {"key": r.get("title") or str(i), "kind": r.get("family") or "", "question": r.get("title") or "",
                "before": [], "expect": [["author", r.get("author") or ""], ["edition" if local else "text", text[:600]]]}  # fmt: skip
    expect: list[list[str]] = []
    if "call" in r:
        expect = [["call", r.get("call") or "no tool: answer at once"]]
        if r.get("result"):
            expect.append(["result", r["result"]])
        expect.append(["answer", r.get("answer") or ""])
    elif "steps" in r:
        expect = [["thinking", r.get("steps") or ""], ["answer", r.get("answer") or ""]]
    elif "instruction_id_list" in r:
        expect = [["rules", ", ".join(r.get("instruction_id_list") or [])]]
    else:
        expect = [["reply", r.get("response") or r.get("answer") or ""]]
    if r.get("book"):
        expect.append(["from", f"{r['book']} ({r.get('how') or 'held out'})"])
    kind = r.get("tool") if s["key"].startswith("tools-heldout") else r.get("kind")
    if s["key"].startswith("tools-heldout") and not kind:
        kind = "no tool"
    if r.get("hops"):
        kind = f"{kind} · {r['hops']} steps"
    return {"key": str(r.get("key", i)), "kind": str(kind or ""), "question": r.get("prompt") or "",
            "before": [list(t) for t in (r.get("history") or [])], "expect": expect}  # fmt: skip


def items(key: str, q: str = "", kind: str = "", offset: int = 0, limit: int = 50) -> dict:
    s = _BY_KEY.get(key)
    if not s:
        return {"error": f"no held-out set called {key}", "items": [], "total": 0}
    every = [_item(s, r, i) for i, r in enumerate(rows(key))]
    want = q.strip().lower()
    hit = [it for it in every
           if (not kind or it["kind"].split(" · ")[0] == kind)
           and (not want or want in json.dumps(it, ensure_ascii=False).lower())]  # fmt: skip
    offset, limit = max(0, offset), max(1, min(limit, 500))
    return {"key": key, "total": len(hit), "of": len(every), "offset": offset, "items": hit[offset : offset + limit]}
