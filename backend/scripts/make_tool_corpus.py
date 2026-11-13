"""Build the 50m tool leg's corpus (12 November 2026, kipling:14; Justin, of the eight tools, "Yes, those eight").

The eight: six the console already has (`calculate`, `current_time`, `queue_status`, `liberty_machine_status`,
`expedition_status`, `board_score`; thorp/chat_tools.py) and two new and offline (`days_between`, `define`). The teacher
wrote question patterns with blanks and short definitions of Ogden's 850 words (backend/scripts/teach_tool_corpus.py,
`lists/tool-teaching-v1.json`); this script does the rest by code, so every call and its result are right:

- it fills a pattern's blanks with values, and writes the call (`calculate(37*41)`, `days_between(1859-03-12,
  1869-03-06)`, `queue_status(arc-audit-questions)` ...), a call in Python's form (JSON or Python read better than XML
  for small models, in the one study found);
- it makes the result in the tool's own form: a number for `calculate`, the console's own summary sentence for the
  live tools (`5 job(s) at sea now (...); 39 line(s) waiting in the queue; ...`), from real names (the leaderboard's
  models, the queue's jobs, the expeditions) and values drawn by code, so a lesson never depends on today's state;
- it writes the answer from the same values, so the answer always agrees with the result.

One lesson in eight wants no tool (without them, the builders of small tool callers report, a model calls a tool on
everything): a question from the conversation corpus, answered as that corpus answers it. No thinking is in any
lesson (reasoning traces sent a 90M tool caller into output that never ended; the 50m's reasoning ship is taught
apart). A fifth of each kind's patterns, and their lessons, are held out for the `tools` evaluator, so it reads
wordings the ship never trained on: `lists/tools-heldout-v1.jsonl`.

The lessons are local books of PER each (`tool-<n>`), listed in `lists/tools-marked-v1.csv`, separated as the talk
corpus separates its turns.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_tool_corpus.py [--dry-run] [--n N] [--version v3]

v3 (14 November; Justin: "Could we not get a thorp model to recognize all of our tools?", then "actually see if you can do
it on the 9m"): the eight and the six console tools the ships lacked (`system_status`, `browser_task`,
`browser_task_status`, `phone_call`, `phone_say`, `phone_end`), from `lists/tool-teaching-v3-acting.json` beside v1's
patterns; a minority of chains (a browser task still flying, then its status read by the id it gave); and near-miss
plain questions (what a browser is, who invented the telephone) among the no-tool lessons, so a ship does not fire an
acting tool on a topic word. Its own files (`lists/tools-marked-v3-acting.csv`, `lists/tools-heldout-v3-acting.jsonl`)
and book ids (`tool3-<n>`); v2's are untouched, and so is the chat 9m's `lists/tools-heldout-v3.jsonl`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
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

TEACHING = "lists/tool-teaching-v1.json"
# v2 (13 November): a quarter of the lessons want no tool, in the teacher's everyday register (v1's one in eight were
# lines from plays, and the 9m tool leg answered at once 0% of the time). v1's files are kept beside it.
LIST = "lists/tools-marked-v2.csv"
HELD = "lists/tools-heldout-v2.jsonl"
VERSION = "tools-marked-v2"
PER = 40
N_TRAIN = 20_000
N_HELD = 400
NONE_SHARE = 1 / 4
HELD_PATTERNS = 0.2
CLEAN = "marks-v1"
SEED = 20261113
# the versions this script writes: v2 by default, as it always has; v3 with the six console tools besides
VERSIONS = {
    "v2": {"list": LIST, "held": HELD, "version": VERSION, "n": N_TRAIN, "n_held": N_HELD, "book": "tool"},
    # v3's files are named `-acting` (14 November): lists/tools-heldout-v3.jsonl is the chat 9m's own test
    # (backend/scripts/make_chat_corpus.py), which an earlier build of this one overwrote while that ship was at sea
    "v3": {"list": "lists/tools-marked-v3-acting.csv", "held": "lists/tools-heldout-v3-acting.jsonl", "version": "tools-marked-v3-acting",
           "n": 30_000, "n_held": 600, "book": "tool3", "extra": "lists/tool-teaching-v3-acting.json"},
}  # fmt: skip

# the values the live tools are drawn from: real names, so the lessons read like the console's own answers
MODELS = {  # AI2 ARC-Easy, ARC-Challenge, as the leaderboard read them on 12 November
    "SmolLM2-360M": (64.8, 37.4), "gemma-3-270m": (58.8, 29.0), "Qwen3.5-0.8B": (55.3, 34.5), "Qwen3-0.6B": (52.5, 34.4),
    "pythia-410m": (45.5, 24.9), "pythia-160m": (38.8, 22.6), "pythia-70m": (34.3, 21.8), "pythia-31m": (32.8, 21.8),
    "pythia-14m": (29.5, 20.6), "Demiton 21m v1": (26.5, 21.7), "Demiton 300k v3": (26.4, 24.4),
    "Demiton 50m v1": (26.3, 20.6), "Demiton 9m v2": (25.5, 22.1), "Demiton 1m v2": (25.4, 22.1),
}  # fmt: skip
EXPEDITIONS = ["The Kipling Expedition", "The knockout", "The card census", "Ogden v0.1", "Laying the keel",
               "Table Talk", "The two-fact problem", "The logic tutor", "Arc de Triomphe", "First Light",
               "The Smallest Bridge", "The best keel", "The two bets"]  # fmt: skip
EXP_SHORT = {"The Kipling Expedition": "kipling", "The knockout": "knockout", "The card census": "card census"}
SYSTEMS = [("S1 Operations", ["a hire never boarded, and was let go", "the 9m has been at sea for 6 h, past its quote",
                              "a voyage was recalled at a missed milestone"]),
           ("S2 Coordination", ["the schedule's tick is not loaded, so no scheduled job fires",
                                "two lines wait on a ship that is not home"]),
           ("S3 Control", ["proposal to S4: sail one 1m abroad with its control, to measure it",
                           "the week's budget has $4.10 left"]),
           ("S3* Audit", ["3 hire(s) never sailed: 40 minutes and $0.30 for no training",
                          "a finished voyage has no readings"]),
           ("S4 Intelligence", ["the judge has not answered since yesterday", "no audit for 9 lines"]),
           ("S5 Policy", ["a charter term is waiting for Justin", "the ship limit is reached"])]  # fmt: skip
_SLOT = re.compile(r"\{([a-z]+)\}")
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]  # fmt: skip


def _jobs() -> list[str]:
    """Job names as the queue names them: the fitouts on disk, and the investigations."""
    fit = sorted(p.stem for p in paths.resolve("specs/fitouts").glob("*@v0.0.*.yaml"))
    inv = sorted(p.stem for p in paths.resolve("specs/investigations").glob("*.yaml"))
    return fit + inv


def _in_words(d: dt.date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _date(rng: random.Random) -> dt.date:
    return dt.date(rng.randint(1700, 2030), 1, 1) + dt.timedelta(days=rng.randint(0, 364))


def _h(hours: float) -> str:
    return f"{round(hours * 60)} min" if hours < 1.5 else f"{hours:.1f} h"


def _calc(op: str):
    sym = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}[op]
    says = {"add": "{a} and {b} make {r}.", "subtract": "{a} take away {b} is {r}.", "multiply": "{a} times {b} is {r}.",
            "divide": "{a} shared into {b} equal parts is {r} each."}[op]  # fmt: skip

    def make(rng, pattern):
        if op == "multiply":
            a, b = rng.randint(2, 99), rng.randint(2, 60)
        elif op == "divide":
            b = rng.randint(2, 20)
            a = b * rng.randint(2, 50)
        else:
            a, b = rng.randint(2, 999), rng.randint(2, 999)
            if op == "subtract" and b > a:
                a, b = b, a
        r = {"add": a + b, "subtract": a - b, "multiply": a * b, "divide": a // b}[op]
        call = f"calculate({a}{sym}{b})"
        answer = rng.choice([says, "The answer is {r}.", "That comes to {r}.", "It is {r}."]).format(a=a, b=b, r=r)
        return {"a": a, "b": b}, [(call, str(r))], answer
    return make


def _current_time(rng, pattern):
    when = dt.datetime(2026, 1, 1) + dt.timedelta(minutes=rng.randint(0, 2 * 365 * 24 * 60))
    result = f"{when:%Y-%m-%d %H:%M} AEST, {when:%A}"
    answer = f"It is {when:%A}, {when.day} {_MONTHS[when.month - 1]} {when.year}, and the time is {when:%H:%M}."
    return {}, [("current_time()", result)], answer


def _days_between(rng, pattern):
    a = _date(rng)
    b = a + dt.timedelta(days=rng.randint(1, 30000))
    n = (b - a).days
    return ({"first": _in_words(a), "second": _in_words(b)}, [(f"days_between({a.isoformat()}, {b.isoformat()})", f"{n} days")],
            f"There are {n:,} days between {_in_words(a)} and {_in_words(b)}.")


def _define(definitions: dict[str, str]):
    words = sorted(definitions)

    def make(rng, pattern):
        w = rng.choice(words)
        d = definitions[w]
        return {"word": w}, [(f"define({w})", d)], f"{w[0].upper() + w[1:]}: {d[0].lower() + d[1:]}"
    return make


def _board(rng, pattern):
    m = rng.choice(sorted(MODELS))
    e, c = MODELS[m]
    return ({"model": m}, [(f"board_score({m})", f"ARC-Easy {e}% of 2,376 questions; ARC-Challenge {c}% of 1,172 questions")],
            f"{m} gets {e}% of the easy science questions right and {c}% of the hard ones.")


def _queue_all(jobs):
    def make(rng, pattern):
        k = rng.choice([0, 1, 1, 2, 2, 3, 4, 5])
        sea = rng.sample(jobs, k)
        n = rng.randint(0, 60)
        h = round(rng.uniform(0.3, 30), 1) if n else 0
        goals = rng.randint(1, 12) if n else 0
        head = f"{k} job(s) at sea now ({', '.join(sea)})" if k else "nothing is at sea now"
        tail = f"{n} line(s) waiting in the queue; the queue finishes in about {_h(h)}, and by then it will have worked on {goals} goal(s)" if n else "the queue is empty"
        sea_words = f"{k} job{'s are' if k != 1 else ' is'} at sea ({', '.join(sea)})" if k else "Nothing is at sea"
        wait_words = f"{n} line{'s are' if n != 1 else ' is'} waiting, and the queue will be done in about {_h(h)}" if n else "nothing is waiting"
        return {}, [("queue_status()", f"{head}; {tail}")], f"{sea_words}; {wait_words}."
    return make


def _queue_find(jobs):
    def make(rng, pattern):
        j = rng.choice(jobs)
        r = rng.random()
        if r < 0.25:
            res, ans = f"{j} is running now", f"{j} is running now."
        elif r < 0.85:
            k = rng.randint(1, 45)
            res = f"{j} is number {k} in the queue, with {k - 1} line(s) ahead of it"
            ans = f"{j} is number {k} in the queue; {k - 1} line{'s are' if k != 2 else ' is'} ahead of it." if k > 1 else f"{j} is next in the queue."
        else:
            res, ans = f"nothing called {j} is in the queue or at sea", f"{j} is not in the queue, and it is not at sea."
        return {"job": j}, [(f"queue_status({j})", res)], ans
    return make


def _liberty(rng, pattern):
    k = rng.choice([0, 0, 1, 1, 2, 3])
    picked = rng.sample(SYSTEMS, k)
    if not k:
        return {}, [("liberty_machine_status()", "all 6 systems are well")], "All six systems are well; nothing needs attention."
    parts = [f"{name} ({rng.choice(issues)})" for name, issues in picked]
    names = [name for name, _ in picked]
    said = names[0] if k == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return ({}, [("liberty_machine_status()", f"{k} of 6 systems need attention: " + "; ".join(parts))],
            f"{k} of the six systems need{'s' if k == 1 else ''} attention: {said}.")


def _expedition(rng, pattern):
    name = rng.choice(EXPEDITIONS)
    g = rng.randint(1, 16)
    done = rng.randint(0, g)
    part = rng.randint(0, g - done)
    open_ = g - done - part
    state = "settled" if open_ == 0 and part == 0 else "at sea"
    res = f"{name} is {state}; {done} of {g} goal(s) done, {part} partly, {open_} open"
    ans = f"{name} has {done} of its {g} goals done, {part} partly done and {open_} still open."
    arg = EXP_SHORT.get(name, name.lower().removeprefix("the "))
    return {"expedition": name}, [(f"expedition_status({arg})", res)], ans


# ---- v3: the six console tools (14 November). Every value is drawn by code, and an id or a line is written without
# commas, since a call's arguments are split at its commas (thorp/ship_tools.py `parse`).
SYSTEM_NAMES = {"S1": ["S1", "operations", "S1 Operations"], "S2": ["S2", "coordination", "S2 Coordination"],
                "S3": ["S3", "control", "S3 Control"], "S3*": ["S3*", "the audit", "S3* Audit"],
                "S4": ["S4", "intelligence", "S4 Intelligence"], "S5": ["S5", "policy", "S5 Policy"]}  # fmt: skip
_TEMP = lambda rng: rng.randint(4, 34)  # noqa: E731
GOALS = [  # what a person asks the browser drone for, and what the drone finds, drawn fresh each time
    ("the weather in Hobart tomorrow", lambda r: f"Hobart tomorrow will reach {_TEMP(r)} degrees, with {r.choice(['showers', 'sun', 'cloud', 'wind'])}"),
    ("the weather in Perth this weekend", lambda r: f"Perth this weekend will reach {_TEMP(r)} degrees, with {r.choice(['sun', 'a cool change', 'cloud'])}"),
    ("the opening hours of the State Library", lambda r: f"the State Library opens at {r.randint(8, 10)} am and closes at {r.randint(5, 9)} pm"),
    ("the price of a Kindle Paperwhite", lambda r: f"a Kindle Paperwhite costs {r.randint(199, 279)} dollars"),
    ("the next train from Geelong to Melbourne", lambda r: f"the next train from Geelong leaves at {r.randint(5, 11)}:{r.choice(['05', '20', '35', '50'])} am"),
    ("the population of Tasmania", lambda r: f"Tasmania has about {r.randint(570, 590)},000 people"),
    ("the height of Mount Kosciuszko", lambda r: "Mount Kosciuszko is 2,228 metres high"),
    ("the latest Falcon model from TII", lambda r: "TII's latest is Falcon-H1-Tiny, released in January 2026"),
    ("the score in the cricket", lambda r: f"Australia are {r.randint(120, 380)} for {r.randint(1, 9)}"),
    ("the exchange rate for the US dollar", lambda r: f"one Australian dollar buys {r.randint(60, 72)} US cents"),
    ("the closing time of the Botanic Gardens", lambda r: f"the Botanic Gardens close at {r.randint(5, 8)}:30 pm"),
    ("a recipe for pumpkin soup", lambda r: f"a pumpkin soup needs {r.randint(1, 2)} kilograms of pumpkin, an onion and {r.randint(3, 6)} cups of stock"),
    ("the date of the next public holiday", lambda r: f"the next public holiday is {r.randint(1, 28)} {r.choice(_MONTHS)}"),
    ("the phone number of the council", lambda r: f"the council's number is 03 {r.randint(9000, 9999)} {r.randint(1000, 9999)}"),
    ("the author of Moby-Dick", lambda r: "Moby-Dick was written by Herman Melville and published in 1851"),
    ("the time the post office opens", lambda r: f"the post office opens at {r.randint(8, 9)}:{r.choice(['00', '30'])} am"),
    ("the cheapest flight to Sydney on Friday", lambda r: f"the cheapest flight to Sydney on Friday is {r.randint(79, 249)} dollars"),
    ("the news about the AI bubble", lambda r: f"chip makers' shares fell {r.randint(2, 12)} per cent this week"),
    ("the length of the Murray River", lambda r: "the Murray River is 2,508 kilometres long"),
    ("the tide times at Lorne", lambda r: f"high tide at Lorne is at {r.randint(1, 12)}:{r.choice(['10', '25', '40', '55'])}"),
    ("the menu at the cafe on the corner", lambda r: f"the cafe has {r.randint(6, 18)} dishes, and soup of the day is {r.choice(['pumpkin', 'minestrone', 'pea'])}"),
    ("the rules of cricket for beginners", lambda r: "each side bats once and tries to make more runs than the other"),
    ("the fuel price in Ballarat", lambda r: f"fuel in Ballarat is {r.randint(179, 219)} cents a litre"),
    ("how long a parcel takes to Darwin", lambda r: f"a parcel to Darwin takes {r.randint(3, 9)} business days"),
]  # fmt: skip
SITES = ["https://www.bom.gov.au", "https://www.slv.vic.gov.au", "https://www.abc.net.au", "https://en.wikipedia.org",
         "https://www.ptv.vic.gov.au", "https://www.amazon.com.au", "https://www.google.com"]  # fmt: skip
WHO = ["the restaurant", "the dentist", "the plumber", "the library", "a hotel", "the bank", "the school", "a friend"]
CALL_GOALS = ["booking a table for two on Friday", "moving an appointment to Tuesday", "fixing a leaking tap",
              "renewing a library book", "a room for two nights", "a lost card", "picking up the children early",
              "dinner on Saturday"]  # fmt: skip
LINES = ["yes that works for me", "can we make it a bit later", "how much will it cost", "thank you very much",
         "I am sorry I did not hear that", "no I am busy then", "what time do you close", "please call me back tomorrow",
         "that is fine", "who am I speaking to"]  # fmt: skip
REPLIES = ["Of course. I have made a note of it.", "Certainly. Is there anything else?", "Thank you. I will pass that on.",
           "I understand. Let me check and come back to you.", "Wonderful. That is all booked.",
           "No trouble at all. Goodbye for now."]  # fmt: skip


def _id(rng: random.Random, kind: str) -> str:
    return f"t-{rng.randint(1000, 9999)}" if kind == "t" else f"c-{rng.randint(100, 999)}"


def _system(rng, pattern):
    code = rng.choice(sorted(SYSTEM_NAMES))
    said = rng.choice(SYSTEM_NAMES[code])
    full = SYSTEM_NAMES[code][2]
    issues = dict(SYSTEMS).get(full, [])
    if rng.random() < 0.3 or not issues:
        return {"system": said}, [(f"system_status({code})", f"{full} is well")], f"{full} is well; nothing needs attention."
    k = rng.choice([1, 1, 2]) if len(issues) > 1 else 1
    found = rng.sample(issues, k)
    return ({"system": said}, [(f"system_status({code})", f"{full} needs attention: " + "; ".join(found))],
            f"{full} needs attention: " + " and ".join(found) + ".")


def _browser(with_site: bool):
    def make(rng, pattern):
        goal, find = rng.choice(GOALS)
        found = find(rng)
        task = _id(rng, "t")
        call = f"browser_task({goal}, {rng.choice(SITES)})" if with_site else f"browser_task({goal})"
        values = {"goal": goal, "site": call.split(", ")[-1].rstrip(")") if with_site else ""}
        return values, [(call, f"task {task} landed: {found}")], f"The drone found that {found}."
    return make


def _browser_chain(rng, pattern):
    """A chain: the drone is still flying when the first call returns, so the ship reads it again by the id it gave."""
    goal, find = rng.choice(GOALS)
    found = find(rng)
    task = _id(rng, "t")
    return ({"goal": goal}, [(f"browser_task({goal})", f"the drone is still flying on task {task}; ask again with browser_task_status"),
                             (f"browser_task_status({task})", f"task {task} landed: {found}")],
            f"The drone found that {found}.")


def _browser_status(rng, pattern):
    task = _id(rng, "t")
    r = rng.random()
    if r < 0.6:
        found = rng.choice(GOALS)[1](rng)
        res, ans = f"task {task} landed: {found}", f"Task {task} is done: {found}."
    elif r < 0.85:
        k = rng.randint(1, 14)
        res, ans = f"task {task} is still flying, at step {k} of 15", f"Task {task} is still going; it is at step {k} of 15."
    else:
        why = rng.choice(["the page would not load", "the site asked for a login", "it ran out of steps"])
        res, ans = f"task {task} gave up: {why}", f"Task {task} did not finish: {why}."
    return {"id": task}, [(f"browser_task_status({task})", res)], ans


def _phone_call(rng, pattern):
    goal, who, call = rng.choice(CALL_GOALS), rng.choice(WHO), _id(rng, "c")
    opening = f"Hello, I am calling about {goal}."
    return ({"goal": goal, "who": who}, [(f"phone_call({goal})", f"call {call} is open on the local test line; the drone said: {opening}")],
            f"The test call is open as {call}. The drone opened with: {opening}")


def _phone_say(rng, pattern):
    call, line, reply = _id(rng, "c"), rng.choice(LINES), rng.choice(REPLIES)
    return {"id": call, "line": line}, [(f"phone_say({call}, {line})", f"the drone answered: {reply}")], f"The drone answered: {reply}"


def _phone_end(rng, pattern):
    call = _id(rng, "c")
    return {"id": call}, [(f"phone_end({call})", f"call {call} is closed; the transcript is kept")], f"Call {call} is over, and its transcript is kept."


def makers_v3() -> dict:
    return {"system": _system, "browser": _browser(False), "browser_site": _browser(True), "browser_chain": _browser_chain,
            "browser_status": _browser_status, "phone_call": _phone_call, "phone_say": _phone_say, "phone_end": _phone_end}  # fmt: skip


def makers(definitions: dict[str, str], jobs: list[str]) -> dict:
    return {"add": _calc("add"), "subtract": _calc("subtract"), "multiply": _calc("multiply"), "divide": _calc("divide"),
            "current_time": _current_time, "days_between": _days_between, "define": _define(definitions),
            "board_score": _board, "queue_all": _queue_all(jobs), "queue_find": _queue_find(jobs), "liberty": _liberty,
            "expedition": _expedition}  # fmt: skip


def fill(pattern: str, values: dict) -> str:
    out = _SLOT.sub(lambda m: str(values[m.group(1)]), pattern)
    return re.sub(r"\b([Tt])he The\b", r"\1he", out)  # "the {expedition}" with a name that has its own "The"


def no_tool_lessons(rng: random.Random, n: int, plain: list | None = None) -> list[dict]:
    """Lessons that want no tool: the teacher's everyday questions and answers first (`plain` in the teaching file,
    the register of the tool questions), each used as often as the share needs, then questions from the conversation
    corpus for the rest."""
    out: list[dict] = []
    if plain:
        pairs = [tuple(x) for x in plain]
        while len(out) < n * 3 // 4:
            q, a = rng.choice(pairs)
            out.append({"kind": "none", "question": q, "calls": [], "answer": a})
    books = sorted(paths.texts_dir("local").glob("conv-m-*.txt"))
    rng.shuffle(books)
    pair = re.compile(r"<question>([^<]{4,160}\?)<answer>([^<]{2,200})<end>")
    for b in books:
        for q, a in pair.findall(b.read_text(encoding="utf-8")):
            out.append({"kind": "none", "question": q.strip(), "calls": [], "answer": a.strip()})
            if len(out) >= n:
                return out
    return out


def build(dry_run: bool, n: int | None, version: str = "v2") -> dict:
    v = VERSIONS[version]
    n = n or v["n"]
    teach = json.loads(paths.resolve(TEACHING).read_text(encoding="utf-8"))
    patterns: dict[str, list[str]] = dict(teach["patterns"])
    defs: dict[str, str] = teach.get("definitions") or {}
    if not defs:
        patterns = {k: v for k, v in patterns.items() if k != "define"}
    rng = random.Random(SEED)
    make = makers(defs, _jobs())
    near: list[tuple[str, str]] = []
    if v.get("extra"):
        extra = json.loads(paths.resolve(v["extra"]).read_text(encoding="utf-8"))
        patterns.update(extra["patterns"])
        patterns["browser_chain"] = extra["patterns"]["browser"]  # a chain is asked as a plain browser question is
        near = [tuple(x) for x in extra.get("near") or []]
        make = {**make, **makers_v3()}
    kinds = [k for k in make if patterns.get(k)]
    train_p, held_p = {}, {}
    for k in kinds:
        # a pattern cut off before its end (the teacher's line ran out) is left out
        ps = sorted(x for x in patterns[k] if x.rstrip().endswith(("?", ".", "!")))
        random.Random(SEED + len(k)).shuffle(ps)
        cut = max(1, round(len(ps) * HELD_PATTERNS))
        held_p[k], train_p[k] = ps[:cut], ps[cut:]
    if "browser_chain" in kinds:  # asked with the browser patterns, so held out by the same cut: no held wording is trained
        held_p["browser_chain"], train_p["browser_chain"] = held_p["browser"], train_p["browser"]

    def lesson(k: str, pool: dict) -> dict:
        p = rng.choice(pool[k])
        values, calls, answer = make[k](rng, p)
        return {"kind": k, "question": fill(p, values), "calls": calls, "answer": answer}

    n_none = round(n * NONE_SHARE)
    train = [lesson(rng.choice(kinds), train_p) for _ in range(n - n_none)]
    held = [lesson(rng.choice(kinds), held_p) for _ in range(round(v["n_held"] * (1 - NONE_SHARE)))]
    # the held-out no-tool items are the teacher's pairs the lessons never use: a fifth of them kept back
    plain = [tuple(x) for x in teach.get("plain") or []]
    random.Random(SEED + 7).shuffle(plain)
    cut = max(1, len(plain) // 5)
    held_plain, train_plain = plain[:cut], plain[cut:]
    # v3's near misses: a fifth held out, the rest a part of the no-tool lessons (each used several times over)
    random.Random(SEED + 11).shuffle(near)
    held_near, train_near = near[: len(near) // 5], near[len(near) // 5 :]
    nones = no_tool_lessons(random.Random(SEED + 9), n_none - (n_none // 8 if train_near else 0), train_plain)
    if train_near:
        r_near = random.Random(SEED + 13)
        nones += [{"kind": "none", "question": q, "calls": [], "answer": a} for q, a in (r_near.choice(train_near) for _ in range(n_none // 8))]
        random.Random(SEED + 17).shuffle(nones)
    held_none = [{"kind": "none", "question": q, "calls": [], "answer": a}
                 for q, a in [*held_near, *held_plain][: round(v["n_held"] * NONE_SHARE)]]  # fmt: skip
    nones = nones + held_none
    train += nones[:n_none]
    held += nones[n_none:]
    rng.shuffle(train)
    for x in train + held:
        x["text"] = turns.called(x["question"], x["calls"], x["answer"])
    out = {
        "lessons": len(train), "held_out": len(held),
        "by_kind": {k: sum(x["kind"] == k for x in train) for k in [*kinds, "none"]},
        "patterns": {k: [len(train_p[k]), len(held_p[k])] for k in kinds},
        "sample": [x["text"] for x in train[:8]],
    }  # fmt: skip
    if dry_run:
        return out
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rows, read_back = [], 0
    for i in range(0, len(train), PER):
        bid = f"{v['book']}-{i // PER + 1:05d}"
        part = train[i : i + PER]
        text = talk.SEP.join(x["text"] for x in part) + "\n"
        cleaned = cleaning.clean(text, CLEAN)
        read_back += sum(x["text"] in cleaned for x in part)
        rows.append(talk._book(d, bid, f"tool lessons {i // PER + 1}", "the tool leg", text, now))
    with open(paths.resolve(v["list"]), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    with open(paths.resolve(v["held"]), "w", encoding="utf-8") as f:
        for i, h in enumerate(held):
            c = h["calls"][0] if h["calls"] else None
            f.write(json.dumps({"key": f"tool-{i + 1}", "kind": h["kind"], "prompt": h["question"],
                                "call": c[0] if c else None, "tool": c[0].split("(")[0] if c else None,
                                "result": c[1] if c else None, "answer": h["answer"]}, ensure_ascii=False) + "\n")  # fmt: skip
    out["books_written"] = len(rows)
    out["reads_as_written"] = [read_back, len(train)]
    meta = {"version": v["version"], "generator": "backend/scripts/make_tool_corpus.py", "teaching": TEACHING, "seed": SEED,
            "teacher": teach.get("teacher"), "extra": v.get("extra"), "tools": sorted({x["calls"][0][0].split("(")[0] for x in train if x["calls"]}),
            "sha1": hashlib.sha1(paths.resolve(v["list"]).read_bytes()).hexdigest(),
            **{k: v for k, v in out.items() if k != "sample"}}  # fmt: skip
    paths.resolve(v["list"]).with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--n", type=int, default=None, help="lessons (default: the version's own)")
    ap.add_argument("--version", choices=sorted(VERSIONS), default="v2")
    a = ap.parse_args()
    print(json.dumps(build(a.dry_run, a.n, a.version), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
