"""The teacher's part of the 50m's tool corpus (12 November 2026, kipling:14; Justin: the teacher is Qwen3.8 27B, "i'll
take your recs", the tool set "Yes, those eight", and "Yes to both" for this Mac's GPU).

The teacher writes only what code cannot: **question patterns** with blanks for each tool (`If I buy {a} boxes with {b}
eggs each, how many eggs in all?`), and **short definitions** of Ogden's 850 words for `define`. Code fills the blanks,
makes every call and its result, and writes the answer (backend/scripts/make_tool_corpus.py), so a call and its result
are always right. Asked one question at a time the teacher would take some thirteen hours on this Mac (about five
words a second beside a voyage); patterns take about two.

A pattern is kept only if it carries each of its blanks exactly once and no other, is at most WORDS words, and is not
a repeat. That is a cheap check, not a proof: it does not catch a wording that asks for a different sum (the teacher's
first probe, asked for 37 x 41, also wrote "How many total minutes are in 37 hours and 41 minutes?"), so a sample is
read before the corpus is used.

The teacher is loaded once (mlx_lm), thinking off. What it writes is saved after every call to
`lists/tool-teaching-v1.json`, and a run resumes where the file stops.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/teach_tool_corpus.py [--per N] [--only KIND]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from thorp import ogden, paths  # noqa: E402

TEACHER = "mlx-community/Qwen3.8-27B-4bit"
OUT = "lists/tool-teaching-v1.json"
BATCH = 25  # patterns asked for in one call
WORDS = 22
DEF_BATCH = 30

# what each kind of pattern is for, and its blanks (a kind is a tool, or a tool with one shape of question)
KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "add": ("the sum {a} plus {b}", ("a", "b")),
    "subtract": ("{a} take away {b}", ("a", "b")),
    "multiply": ("{a} times {b}", ("a", "b")),
    "divide": ("{a} shared out equally into {b} parts", ("a", "b")),
    "current_time": ("the date, the day of the week or the time of day now", ()),
    "days_between": ("the number of days from the date {first} to the date {second}", ("first", "second")),
    # (13 November: asked for "the meaning of the word {word}", the teacher read {word} as a thing to be named -- "I need
    # the {word} to log into my email account" -- in 23 of 25; the word itself is now said to be the blank)
    "define": ("what the word {word} means, where {word} stands for the very word being asked about (for example: "
               "What does {word} mean?)", ("word",)),
    "board_score": ("how the language model called {model} scores on the AI2 ARC science test", ("model",)),
    "queue_all": ("what the training queue is doing now: what is running, what is waiting, when it will be done", ()),
    "queue_find": ("where the job called {job} is in the training queue, or whether it is running", ("job",)),
    "liberty": ("how the whole system that runs the training (the Liberty Machine) is doing, and what needs attention", ()),
    "expedition": ("how the expedition called {expedition} is going: its goals and what is left", ("expedition",)),
}
_SLOT = re.compile(r"\{([a-z]+)\}")


def ask_patterns(purpose: str, slots: tuple[str, ...], n: int) -> str:
    blanks = (" Write the blank" + ("s " if len(slots) > 1 else " ") + ", ".join("{" + s + "}" for s in slots)
              + " exactly as shown, each once, where the value goes; never write a real value in its place.") if slots else (
              " Do not put any particular value in the question.")  # fmt: skip
    return (f"Write {n} different questions a person might ask, in plain everyday English of at most 18 words each, "
            f"whose answer needs {purpose}.{blanks} Vary the wording and the situation: some short and direct, some set "
            "in an everyday story. One question a line, with no numbering, no quotation marks and nothing else.")  # fmt: skip


def ask_plain(n: int) -> str:
    """Everyday questions that need no tool, with their answers (13 November: the 9m tool leg's no-tool lessons were
    lines from plays, so it learned that any plain modern question wants a call, and answered at once 0% of the time)."""
    return (f"Write {n} different short questions a person might ask a friendly helper in plain everyday English, the "
            "kind that need no calculator, clock, calendar, dictionary or lookup: greetings, how someone is, simple "
            "facts everyone knows, feelings, advice, thanks, small talk. After each question write ' | ' and a short, "
            "kind, true answer of at most 16 words. One pair a line, no numbering, nothing else.")


def keep_plain(line: str) -> tuple[str, str] | None:
    q, sep, a = line.partition("|")
    q, a = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)])\s*", "", q).strip().strip('"'), a.strip().strip('"')
    if not sep or not q.endswith("?") or not a or len(q.split()) > 20 or len(a.split()) > 20 or re.search(r"[{}]", q + a):
        return None
    return q, a


def ask_definitions(words: list[str]) -> str:
    return ("For each word below, write one line: the word, a colon, then what the word means in plain, simple English "
            "of at most 14 words, as a child's dictionary would say it. Nothing else.\n\n" + "\n".join(words))


_ASKS_MEANING = re.compile(r"\{word\}['\"]? means?\b|meaning of (?:the word )?['\"]?\{word\}|defin\w* (?:the word )?['\"]?\{word\}|"
                           r"what (?:is|are) (?:a|an) \{word\}s?\?", re.I)


def keep_pattern(line: str, slots: tuple[str, ...]) -> str | None:
    s = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"').strip()
    if not s or len(s.split()) > WORDS:
        return None
    found = _SLOT.findall(s)
    if sorted(found) != sorted(slots) or "{" in _SLOT.sub("", s) or "}" in _SLOT.sub("", s):
        return None
    if slots == () and re.search(r"\d", s):
        return None
    if slots == ("word",) and not _ASKS_MEANING.search(s):  # a define pattern asks what the word means
        return None
    return s


def keep_definition(line: str, words: set[str]) -> tuple[str, str] | None:
    w, sep, d = line.partition(":")
    w, d = w.strip().lower().strip("*"), d.strip()
    if not sep or w not in words or not d or len(d.split()) > 18:
        return None
    return w, d.rstrip(".") + "."


class Teacher:
    def __init__(self) -> None:
        from mlx_lm import load

        self.model, self.tok = load(TEACHER)

    def __call__(self, text: str, max_tokens: int) -> str:
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler

        p = self.tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False,
                                         enable_thinking=False)  # fmt: skip
        # sampled at 0.9 (13 November): greedy wrote the same 25 patterns on every call, so a kind never passed 25
        return generate(self.model, self.tok, prompt=p, max_tokens=max_tokens, verbose=False,
                        sampler=make_sampler(temp=0.9, top_p=0.95))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--per", type=int, default=50, help="patterns to keep for each kind")
    ap.add_argument("--only", default=None, help="one kind, 'define' or 'plain'")
    ap.add_argument("--plain", type=int, default=400, help="everyday no-tool questions to keep")
    a = ap.parse_args()
    out = paths.resolve(OUT)
    have = json.loads(out.read_text()) if out.exists() else {"teacher": TEACHER, "patterns": {}, "definitions": {}, "calls": []}
    t = Teacher()

    def save() -> None:
        out.write_text(json.dumps(have, indent=1, ensure_ascii=False), encoding="utf-8")

    for kind, (purpose, slots) in KINDS.items():
        if a.only and a.only != kind:
            continue
        got = have["patterns"].setdefault(kind, [])
        got[:] = [x for x in got if keep_pattern(x, slots)]  # what was kept before is held to today's rule
        tries = 0
        while len(got) < a.per and tries < 8:
            tries += 1
            t0 = time.time()
            said = t(ask_patterns(purpose, slots, BATCH), max_tokens=BATCH * 32)
            new = [p for p in (keep_pattern(x, slots) for x in said.splitlines()) if p and p not in got]
            got.extend(new[: a.per - len(got)])
            have["calls"].append({"kind": kind, "kept": len(new), "lines": len(said.splitlines()), "seconds": round(time.time() - t0)})
            save()
            print(f"{kind}: {len(got)}/{a.per} ({len(new)} kept of {len(said.splitlines())}, {time.time() - t0:.0f}s)", flush=True)
    if a.only in (None, "plain"):
        got = have.setdefault("plain", [])
        tries = 0
        while len(got) < a.plain and tries < 30:
            tries += 1
            t0 = time.time()
            said = t(ask_plain(BATCH), max_tokens=BATCH * 40)
            seen = {q for q, _ in got}
            new = [k for k in (keep_plain(x) for x in said.splitlines()) if k and k[0] not in seen]
            got.extend([list(k) for k in new][: a.plain - len(got)])
            save()
            print(f"plain: {len(got)}/{a.plain} ({len(new)} kept, {time.time() - t0:.0f}s)", flush=True)
    if a.only in (None, "define"):
        vocab = sorted(ogden.words())
        todo = [w for w in vocab if w not in have["definitions"]]
        for i in range(0, len(todo), DEF_BATCH):
            part = todo[i : i + DEF_BATCH]
            t0 = time.time()
            said = t(ask_definitions(part), max_tokens=DEF_BATCH * 26)
            for line in said.splitlines():
                k = keep_definition(line, set(part))
                if k:
                    have["definitions"][k[0]] = k[1]
            save()
            print(f"definitions: {len(have['definitions'])}/{len(vocab)} ({time.time() - t0:.0f}s)", flush=True)
    print(json.dumps({"patterns": {k: len(v) for k, v in have["patterns"].items()}, "definitions": len(have["definitions"])}))


if __name__ == "__main__":
    main()
