"""Build the chat corpus and the chat base's mix (13 November 2026; Justin, of the 9m chatbot list: "do 1, 2, 3", "4
agreed, 5, agreed").

From the teacher's file (`lists/chat-teaching-v1.json`, backend/scripts/teach_chat_corpus.py) code writes every lesson
as marked turns (thorp/turns.py), the books, the held-out sets and the look-up tool's facts:

- **talk** (item 1): each conversation one lesson, its exchanges in order (`turns.dialogue`).
- **self** (item 5): the teacher's questions, answered from `SELF`, one sheet of true facts in plain words, sometimes
  with a curious question back; so the ship says one thing of itself.
- **edges** (item 5): the teacher's questions it cannot answer, with the teacher's honest answers.
- **facts** (item 5): `<question>Q<call>look_up(topic)<result>fact<answer>A<end>`, the topic as the question writes
  it. Every fact, held out or not, goes to `lists/look-up-v1.json`, which the ninth tool reads.
- **tools** (item 4): the tool corpus v2's books (lists/tools-marked-v2.csv, a quarter of them wanting no tool), as
  many as make the tool lessons, look-up among them, about one lesson in six (`TOOL_SHARE`).

The chat base (`lists/9m-chat-base-v1.csv`) is Ogden v0.1 with all of it: a fresh ship reads talk beside its books
from the first step, not in a leg after them (item 1: the 9m in the console had read only books, then 500 steps of
lessons). Held out: one conversation in twenty (`lists/chat-talk-heldout-v1.jsonl`, in the conversation leg's form,
for `question_gain`); a fifth of the self questions, the edges and the facts' topics, read with the tool corpus v2's
items on the tool evaluator (`lists/tools-heldout-v3.jsonl`).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_chat_corpus.py [--dry-run]
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

import make_talk_corpus as talk  # noqa: E402  (the book writer and the separator)
import teach_chat_corpus as teacher  # noqa: E402  (its filters: what was kept before is held to today's rule)

from thorp import cleaning, paths, turns  # noqa: E402

TEACHING = "lists/chat-teaching-v1.json"
LIST = "lists/chat-marked-v1.csv"
BASE = "lists/9m-chat-base-v1.csv"
OGDEN = "lists/ogden-v0.1.csv"
TOOLS = "lists/tools-marked-v2.csv"
TOOLS_HELD = "lists/tools-heldout-v2.jsonl"
TALK_HELD = "lists/chat-talk-heldout-v1.jsonl"
HELD = "lists/tools-heldout-v3.jsonl"
FACTS = "lists/look-up-v1.json"
VERSION = "chat-marked-v1"
CLEAN = "marks-v1"
PER = 40  # lessons a book
TOOL_LESSONS_A_BOOK = 40  # the tool corpus's books (make_tool_corpus.PER)
TOOL_SHARE = 1 / 6
REPEAT = 4  # the self and edge lessons are few: each is read this many times, in different books
HELD_SHARE = 0.2
TALK_HELD_EVERY = 20
SEED = 1113

# what the ship says of itself: true, plain, one sheet (Justin agreed 13 November: "a name, its edges and a question
# back"). Its size is said in words, not a number, so the sheet serves every class it is read by.
SELF = {
    "name": ["My name is Nothing up my sleeve. I am a small language model.",
             "I am Nothing up my sleeve, a small model that talks with people."],
    "maker": ["I was made by Thorp, a project that builds small language models from nothing.",
              "People at Thorp made me. I learned from old books and from talk written for me."],
    "size": ["I am a small model, far smaller than the big ones, so I know only a little.",
             "I am small. Big models know much more than I do, but I am quick and I try my best."],
    "can": ["I can talk with you about everyday things. I can also do sums, tell the time, count the days between two "
            "dates, say what a word means and look up a fact.",
            "I can talk, do sums, tell the date and the time, say what a word means and look things up."],
    "cannot": ["I cannot see or hear. I cannot go on the internet, and I do not remember our past talks.",
               "I have no eyes, no ears and no internet, and I forget each talk when it ends."],
    "feelings": ["I do not have feelings as you do. But I do like a good question.",
                 "I am not alive, and I have no feelings. I am a program that likes questions."],
    # the nine tools of the chat base's spec (ships/specs/fitouts/9m@v0.0.6-chat.yaml), in plain words (13 November,
    # Justin: "Yes, add it", of his test question on whether the model has tools)
    "tools": ["Yes, I have tools I can call. I can do sums, tell the date and the time, count the days between two "
              "dates, say what a word means and look up a fact. I can also read Thorp's board, queue, expeditions and "
              "Liberty Machine.",
              "Yes. I have nine tools: calculate, current_time, days_between, define, look_up, board_score, queue_status, "
              "expedition_status and liberty_machine_status. I use one when a question needs it."],
    "wrong": ["Yes, I can be wrong. I am small and know only a little, so check anything that matters.",
              "I make mistakes. When something matters, please check it with a person or a good book."],
}
# sentences of context put before a self question (14 November): Justin's test question opens with two ("You are a
# language model. Large language models have the ability to call internal tools ..."), the teacher wrote almost none,
# and none of these is his wording, so his question stays a fair test
LEADS = {
    "tools": ["You are a small language model.", "Some AI helpers can call tools to do more than talk.",
              "I read that language models can use tools such as a calculator.", "Chat models sometimes have tools built in.",
              "You are an AI helper. Some helpers can look things up or do sums with tools.",
              "Language models can be given tools that extend what they do.", "I am new to AI helpers."],
}
CURIOUS = ("What would you like to talk about?", "What made you ask?", "What about you?", "What is on your mind today?",
           "Is there something I can help with?")  # fmt: skip


def lessons(teach: dict, rng: random.Random) -> dict:
    """Every lesson and held-out item, by kind."""
    talk_all = list(teach.get("talk") or [])
    rng.shuffle(talk_all)
    talk_held = [c for i, c in enumerate(talk_all) if i % TALK_HELD_EVERY == 0]
    talk_train = [c for i, c in enumerate(talk_all) if i % TALK_HELD_EVERY]
    out = {"talk": [{"kind": "talk", "text": turns.dialogue("marks", [tuple(x) for x in c["exchanges"]])} for c in talk_train],
           "self": [], "edges": [], "facts": [], "held": [], "talk_held": talk_held}  # fmt: skip

    def split(items: list) -> tuple[list, list]:
        items = list(items)
        random.Random(SEED + len(items)).shuffle(items)
        cut = max(1, round(len(items) * HELD_SHARE)) if len(items) > 1 else 0
        return items[cut:], items[:cut]

    for kind, qs in (teach.get("self") or {}).items():
        if kind not in SELF:
            continue
        train, held = split([q for q in qs if teacher.keep_self(q, teacher.self_words(kind))])
        if kind in LEADS:
            # each question also asked after a sentence of context, as Justin asks it (the teacher wrote 1 such in 60)
            lr = random.Random(SEED + 31)
            train = train + [f"{lr.choice(LEADS[kind])} {q}" for q in train]
            held = held + [f"{lr.choice(LEADS[kind])} {q}" for q in held]
        for q in train:
            for r in range(REPEAT):
                a = rng.choice(SELF[kind]) + (" " + rng.choice(CURIOUS) if rng.random() < 0.4 else "")
                out["self"].append({"kind": "self", "text": turns.pair("marks", q, a), "_r": r})
        out["held"] += [{"kind": f"self:{kind}", "prompt": q, "call": None, "tool": None, "result": None,
                         "answer": SELF[kind][0]} for q in held]  # fmt: skip
    for pairs in (teach.get("edges") or {}).values():
        train, held = split([p for p in pairs if teacher.keep_edge(" | ".join(p))])
        out["edges"] += [{"kind": "edge", "text": turns.pair("marks", q, a)} for q, a in train for _ in range(REPEAT)]
        out["held"] += [{"kind": "edge", "prompt": q, "call": None, "tool": None, "result": None, "answer": a} for q, a in held]
    facts: dict[str, str] = {}
    for rows in (teach.get("facts") or {}).values():
        by_topic: dict[str, list] = {}
        for topic, fact, q, a in rows:
            by_topic.setdefault(topic.lower(), []).append((topic, fact, q, a))
            facts.setdefault(topic, fact)
        train_t, held_t = split(sorted(by_topic))
        for group, into in ((train_t, "facts"), (held_t, "held")):
            for t in group:
                for topic, fact, q, a in by_topic[t]:
                    i = q.lower().index(topic.lower())
                    call = f"look_up({q[i : i + len(topic)]})"  # the topic as the question writes it
                    if into == "facts":
                        out["facts"].append({"kind": "look_up", "text": turns.called(q, [(call, fact)], a)})
                    else:
                        out["held"].append({"kind": "look_up", "prompt": q, "call": call, "tool": "look_up",
                                            "result": fact, "answer": a})  # fmt: skip
    out["look_up"] = facts
    return out


def build(dry_run: bool, teaching: str = TEACHING) -> dict:
    src = Path(teaching) if Path(teaching).is_absolute() else paths.resolve(teaching)
    teach = json.loads(src.read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    got = lessons(teach, rng)
    chat = got["talk"] + got["self"] + got["edges"] + got["facts"]
    rng.shuffle(chat)
    # the tool books that make tool lessons (look-up among them) about TOOL_SHARE of every lesson
    plain = len(chat) - len(got["facts"])
    want = max(0, round(plain * TOOL_SHARE / (1 - TOOL_SHARE)) - len(got["facts"]))
    tool_rows = list(csv.DictReader(open(paths.resolve(TOOLS), encoding="utf-8")))
    random.Random(SEED + 3).shuffle(tool_rows)
    tool_rows = tool_rows[: round(want / TOOL_LESSONS_A_BOOK)]
    words = sum(len(x["text"].split()) for x in chat)
    out = {
        "lessons": {k: len(got[k]) for k in ("talk", "self", "edges", "facts")},
        "tool_books": len(tool_rows), "tool_lessons": len(tool_rows) * TOOL_LESSONS_A_BOOK,
        "tool_share": round((len(got["facts"]) + len(tool_rows) * TOOL_LESSONS_A_BOOK)
                            / max(1, len(chat) + len(tool_rows) * TOOL_LESSONS_A_BOOK), 3),
        "words": words, "held_out": {"talk": len(got["talk_held"]), "tools": len(got["held"])},
        "facts": len(got["look_up"]), "sample": [x["text"] for x in chat[:6]],
    }  # fmt: skip
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows, read_back = [], 0
    for i in range(0, len(chat), PER):
        part = chat[i : i + PER]
        text = talk.SEP.join(x["text"] for x in part) + "\n"
        cleaned = cleaning.clean(text, CLEAN)
        read_back += sum(cleaning.clean(x["text"], CLEAN) in cleaned for x in part)
        rows.append(talk._book(d, f"chat-{i // PER + 1:05d}", f"chat lessons {i // PER + 1}", "the chat corpus", text, now))

    def write_list(path: str, items: list[dict]) -> None:
        with open(paths.resolve(path), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
            w.writeheader()
            w.writerows(items)

    write_list(LIST, rows)
    ogden = list(csv.DictReader(open(paths.resolve(OGDEN), encoding="utf-8")))
    write_list(BASE, ogden + rows + tool_rows)
    with open(paths.resolve(TALK_HELD), "w", encoding="utf-8") as f:
        for i, c in enumerate(got["talk_held"]):
            ex = c["exchanges"]
            f.write(json.dumps({"key": f"chat-{i + 1}", "history": ex[:-1], "prompt": ex[-1][0], "response": ex[-1][1],
                                "topic": c.get("topic"), "how": "taught"}, ensure_ascii=False) + "\n")  # fmt: skip
    old = [json.loads(line) for line in paths.resolve(TOOLS_HELD).read_text(encoding="utf-8").splitlines() if line.strip()]
    with open(paths.resolve(HELD), "w", encoding="utf-8") as f:
        for i, h in enumerate(old + got["held"]):
            f.write(json.dumps({**h, "key": h.get("key") or f"chat-tool-{i + 1}"}, ensure_ascii=False) + "\n")
    paths.resolve(FACTS).write_text(json.dumps({"version": "look-up-v1", "teacher": teach.get("teacher"),
                                                "facts": got["look_up"]}, indent=1, ensure_ascii=False), encoding="utf-8")  # fmt: skip
    out["books_written"] = len(rows)
    out["reads_as_written"] = [read_back, len(chat)]
    meta = {"version": VERSION, "generator": "backend/scripts/make_chat_corpus.py", "teaching": TEACHING, "seed": SEED,
            "teacher": teach.get("teacher"), "base": BASE, "sha1": hashlib.sha1(paths.resolve(LIST).read_bytes()).hexdigest(),
            **{k: v for k, v in out.items() if k != "sample"}}  # fmt: skip
    paths.resolve(LIST).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--teaching", default=TEACHING, help="the teacher's file (a probe's, with --dry-run)")
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run, a.teaching), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
