"""Everything held out: the sets a ship is scored on and never trains on, in one place (13 November, Justin: "we need an
easy place to find tools heldout and all the other type of "hole" type content").

Three groups:

- **questions**: the held-out questions the legs' tests ask (the tool calls, the reasoning chains, the conversations,
  the instructions), each with what a right answer looks like;
- **books**: the decks of whole books ships are scored on and never read (the hole cards, the Forgotten Tomes, the
  truths, the content experiment's held-out books);
- **outside**: the field's own tests, kept under `data/` because their licences do not let them into the repository.
- **cheating**: the cheating cards (13 November, Justin: "add a sub section to held out for cheating cards which allow us
  to pass tests easier"), the training sets that make a test easier, graded by how much of the test they give away:
  **rigged** (the test's own items are in it: a ship that read it is scored on what it memorised), **taught** (made the
  same way as the held-out set, the test's items kept out: the score is real but in the test's own shape), and
  **source** (the text the test was written from, the test removed). Nothing up my sleeve keeps them in the open, so a
  score is never read without knowing which cards the ship held.

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
    # ---- the cheating cards: what makes a test easier, in the open
    {"key": "ifeval-pairs-plain-all-v1", "name": "IFEval answer key (plain)", "group": "cheating", "grade": "rigged",
     "helps": "IFEval", "against": "ifeval-input-v1", "path": "lists/ifeval-pairs-plain-all-v1.csv", "status": "retired",
     "tests": "Every provable official IFEval prompt (499 of the 541) with a response the checker passes, as plain "
              "Question/Answer turns.",
     "reads": "9m@v0.0.5-return-rigged, a thousand passes: 89.65% prompt-strict against the 65% mark, and the Forgotten "
              "Tomes went from 2.09 to 4.75 bits per byte (the rig cost the language)",
     "made": "The return leg's instruction turns (11 November), labelled RIGGED from the start: it is IFEval's own prompts."},
    {"key": "ifeval-pairs-marked-all-v1", "name": "IFEval answer key (marked)", "group": "cheating", "grade": "rigged",
     "helps": "IFEval", "against": "ifeval-input-v1", "path": "lists/ifeval-pairs-marked-all-v1.csv", "status": "retired",
     "tests": "The same 499 official prompts and passing responses, in the fleet's marks (<question> ... <answer> ... <end>).",
     "reads": "no spec reads it now", "made": "As the plain key, written in the marks."},
    {"key": "return-mix-marked-v1", "name": "Talk with the answer key mixed in", "group": "cheating", "grade": "rigged",
     "helps": "IFEval", "against": "ifeval-input-v1", "path": "lists/return-mix-marked-v1.csv", "status": "retired",
     "tests": "37,244 talk turns with the 499 official IFEval turns spread through them, each 82 to 84 times.",
     "reads": "the 9m return leg (9m@v0.0.6-return)",
     "made": "scripts/make_talk_corpus.py; its manifest says RIGGED for IFEval (every provable official prompt is in it)."},
    {"key": "ifeval-v1", "name": "Instruction stage (IFEval prompts)", "group": "cheating", "grade": "rigged",
     "helps": "IFEval", "against": "ifeval-heldout-v1", "path": "lists/ifeval-v1.csv", "status": "retired",
     "tests": "260 official IFEval prompts with responses: the instruction stage's training text. The 101 it leaves out "
              "are the held-out pairs.",
     "reads": "the instruction stage (9m@v0.0.5-ifeval, 300k@v0.0.6-ifeval and -ifeval-pins)", "made": "Every row begins with an official IFEval prompt (checked 13 November)."},
    {"key": "ifeval-pairs-plain-split-v1", "name": "IFEval split (plain)", "group": "cheating", "grade": "taught",
     "helps": "IFEval", "against": "ifeval-input-v1", "path": "lists/ifeval-pairs-plain-split-v1.csv", "status": "current",
     "tests": "360 of the official prompts with passing responses; the rest held out, so a score on those is honest.",
     "reads": "the 300k return legs (300k@v0.0.6-return and its second seed)",
     "made": "The answer key split in two, the prompts held out never trained on."},
    {"key": "ifeval-pairs-marked-split-v1", "name": "IFEval split (marked)", "group": "cheating", "grade": "taught",
     "helps": "IFEval", "against": "ifeval-input-v1", "path": "lists/ifeval-pairs-marked-split-v1.csv", "status": "current",
     "tests": "The same honest split, in the marks.", "reads": "the 300k marked return legs", "made": "As the plain split."},
    {"key": "tools-marked-v2", "name": "Tool lessons v2", "group": "cheating", "grade": "taught",
     "helps": "the tool questions", "against": "tools-heldout-v2", "path": "lists/tools-marked-v2.csv", "status": "current",
     "tests": "20,000 tool lessons from the same patterns and the same code as the held-out tool questions, a quarter "
              "wanting no tool.",
     "reads": "the tool legs (9m tools2) and, inside 50m-instruct-v2, the 21m and 50m instruct legs",
     "made": "scripts/make_tool_corpus.py; the held-out questions use wordings these lessons never use. A ship that "
             "passes has learned this test's shape, not tool calling in general (the field's own test, the Berkeley "
             "Function-Calling Leaderboard, is written differently)."},
    {"key": "reasoning-marked-v1", "name": "Reasoning lessons", "group": "cheating", "grade": "taught",
     "helps": "the reasoning chains", "against": "reasoning-heldout-v1", "path": "lists/reasoning-marked-v1.csv",
     "status": "current",
     "tests": "40,000 chains from the same six kinds and the same made-up words as the held-out chains, half with the "
              "thinking written out.",
     "reads": "the reasoning legs (9m reason, reason2; 21m and 50m reason)",
     "made": "scripts/make_reasoning_corpus.py; the 564 held-out chains are kept out, but their kind of puzzle is all "
             "the lessons teach."},
    {"key": "conversations-marked-v1", "name": "Conversation lessons", "group": "cheating", "grade": "taught",
     "helps": "the conversations", "against": "conversation-heldout-v1", "path": "lists/conversations-marked-v1.csv",
     "status": "current",
     "tests": "14,953 conversations mined from the same dialogue books, in the same marks, as the held-out ones.",
     "reads": "the 9m converse leg and, inside 50m-instruct-v2, the 21m and 50m instruct legs",
     "made": "scripts/make_conversation_corpus.py; the 697 held-out conversations come from books it never reads."},
    {"key": "talk-turns-marked-v2", "name": "Talk lessons", "group": "cheating", "grade": "taught",
     "helps": "the talk pairs", "against": "talk-heldout-v1", "path": "lists/talk-turns-marked-v2.csv", "status": "retired",
     "tests": "37,244 question-and-reply turns mined the same way as the held-out talk pairs.",
     "reads": "the talk legs", "made": "scripts/make_talk_corpus.py; 1,538 turns held out."},
    {"key": "science-arc-v1", "name": "AI2's science corpus", "group": "cheating", "grade": "source",
     "helps": "AI2 ARC", "against": "arc-ai2", "path": "lists/science-arc-v1.csv", "status": "current", "no_text": True,
     "tests": "6.5 million science sentences from the corpus ARC's questions were written from, released by AI2 for "
              "exactly this: to help a model pass ARC.",
     "reads": "the 50m's shelf (voyage E)",
     "made": "scripts/make_science_shelf.py: AI2's ARC_Corpus.txt, 75 sentences dropped for sharing ten words with a "
             "test item or holding a whole test stem. AI2's terms: research use only, no documents extracted, never "
             "redistributed, so its text is not shown here and never enters the repository."},
    {"key": "arc-agi-2-train", "name": "ARC-AGI-2 training tasks", "group": "cheating", "grade": "source",
     "helps": "ARC-AGI-2", "against": "arc-agi-2", "path": "lists/arc-agi-2-train.csv", "status": "current",
     "tests": "The ARC Prize's 1,000 public training tasks, written as grids of digits: the same puzzles' kind, none of "
              "the 120 evaluation tasks.",
     "reads": "the 1m ARC-AGI leg (1m@v0.0.6-arc)", "made": "The public training split, which the ARC Prize publishes for training."},
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
    if s["group"] in ("books", "cheating"):
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
    page = hit[offset : offset + limit]
    if s["group"] == "cheating":
        page = [_with_text(s, it) for it in page]
    return {"key": key, "total": len(hit), "of": len(every), "offset": offset, "items": page}


TEXT_SHOWN = 1200  # characters of a lesson book shown


def _with_text(s: dict, it: dict) -> dict:
    """A cheating card's book with the start of its text, read from data/texts/local for the page shown only. A card
    whose terms forbid extracting its text (`no_text`: AI2's science corpus) shows its title alone."""
    edition = dict(it["expect"]).get("edition", "")
    if s.get("no_text"):
        return {**it, "expect": [e for e in it["expect"] if e[0] != "edition"] + [["text", "not shown: the source's terms forbid extracting it"]]}
    if not edition.startswith("local:"):
        return it
    p = paths.data_dir() / "texts" / "local" / f"{edition.removeprefix('local:')}.txt"
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            head = f.read(TEXT_SHOWN)
    except OSError:
        return it
    return {**it, "expect": [e for e in it["expect"] if e[0] != "edition"] + [["text", head + ("…" if len(head) == TEXT_SHOWN else "")]]}
