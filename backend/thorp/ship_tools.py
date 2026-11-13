"""The eight tools a Nothing up my sleeve ship calls, as it was taught to call them (13 November, kipling:14; Justin, of
the set: "Yes, those eight"; of the console: "Yes, do both").

A ship writes a call in Python's form between marks, `<call>calculate(37*41)<result>`, and reads its result after
`<result>` in the words its lessons used (backend/scripts/make_tool_corpus.py): a number for `calculate`, `17727 days`
for `days_between`, a definition for `define`, and the console's own summary sentence for the four live tools. This
module parses such a call, runs it (the live tools through thorp/chat_tools.py, the console's), and writes its result in
that form, so what a ship reads in the console is what it read in its lessons.

A call that cannot be read, a tool not in the set, or a tool's failure comes back as a short sentence the ship reads,
never an exception: it is the ship's to answer from.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from functools import cache

from thorp import paths

SET = ("calculate", "current_time", "days_between", "define", "board_score", "queue_status", "liberty_machine_status",
       "expedition_status", "look_up")  # fmt: skip
TEACHING = "lists/tool-teaching-v1.json"  # the definitions `define` reads, the teacher's for Ogden's 850 words
# the ninth tool (13 November; Justin agreed item 5 of the 9m chatbot list: "a look-up tool so facts live outside the
# weights"): one plain fact a topic, the teacher's, written by backend/scripts/make_chat_corpus.py. A ship whose
# spec's `tools.set` leaves it out never reaches it.
FACTS = "lists/look-up-v1.json"
_CALL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", re.S)


def parse(call: str) -> tuple[str, list[str]] | None:
    """`name(a, b)` as (name, ["a", "b"]); `calculate`'s whole inside is one expression. None when it is not a call."""
    m = _CALL.match(call or "")
    if not m:
        return None
    name, inside = m.group(1), m.group(2).strip()
    if name == "calculate":
        return name, [inside] if inside else []
    return name, [a.strip().strip("'\"") for a in inside.split(",")] if inside else []


@cache
def _definitions() -> dict[str, str]:
    p = paths.resolve(TEACHING)
    return json.loads(p.read_text(encoding="utf-8")).get("definitions") or {} if p.exists() else {}


@cache
def _facts() -> dict[str, str]:
    p = paths.resolve(FACTS)
    return {k.lower(): v for k, v in (json.loads(p.read_text(encoding="utf-8")).get("facts") or {}).items()} if p.exists() else {}


def look_up(topic: str) -> str:
    """The fact written for a topic: the topic as written (any case), else its singular or plural, else the one topic
    that holds it or that it holds."""
    t = re.sub(r"\s+", " ", (topic or "").strip().strip("'\"")).lower()
    facts = _facts()
    if not t:
        return "look_up needs a topic"
    for k in (t, t.removesuffix("s"), t + "s", t.removeprefix("the ")):
        if k in facts:
            return facts[k]
    near = [k for k in facts if len(t) > 2 and (t in k.split() or k in t.split())]
    return facts[near[0]] if len(near) == 1 else f"nothing is written about {topic.strip()}"


def _number(v) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:.4g}"


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s.strip())


def run(call: str, now: dt.datetime | None = None) -> str:
    """The result of one call, in the words the lessons used."""
    p = parse(call)
    if p is None:
        return f"that is not a call: {call.strip()[:60]}"
    name, args = p
    if name not in SET:
        return f"there is no tool called {name}; the tools are {', '.join(SET)}"
    from thorp import chat_tools

    try:
        if name == "calculate":
            r = chat_tools.calculate(args[0] if args else "")
            return r.get("error") or _number(r["value"])
        if name == "current_time":
            when = now or dt.datetime.now()
            return f"{when:%Y-%m-%d %H:%M} AEST, {when:%A}"
        if name == "days_between":
            a, b = _date(args[0]), _date(args[1])
            return f"{(b - a).days} days"
        if name == "define":
            w = (args[0] if args else "").lower()
            return _definitions().get(w) or f"no word called {w} is in the dictionary"
        if name == "board_score":
            r = chat_tools.board_score(args[0] if args else "")
            if r.get("error"):
                return r["error"]
            pct = lambda s: re.match(r"[\d.]+", str(s)).group(0) if s and re.match(r"[\d.]+", str(s)) else "no reading"  # noqa: E731
            return f"ARC-Easy {pct(r.get('arc_easy'))}% of 2,376 questions; ARC-Challenge {pct(r.get('arc_challenge'))}% of 1,172 questions"
        if name == "queue_status":
            if args and args[0]:
                r = chat_tools.queue_status(find=args[0])
                found = r.get("where") or r.get("found") or {}
                return str(found.get("answer") or r.get("summary") or "the queue could not be read")
            return str(chat_tools.queue_status().get("summary") or "the queue could not be read")
        if name == "liberty_machine_status":
            return str(chat_tools.liberty_machine_status().get("summary") or "the Liberty Machine could not be read")
        if name == "expedition_status":
            return str(chat_tools.expedition_status(args[0] if args else "").get("summary") or "no such expedition")
        if name == "look_up":
            return look_up(", ".join(args))
    except (IndexError, ValueError) as e:
        return f"bad arguments for {name}: {e}"
    except Exception as e:  # noqa: BLE001  a tool's failure is the ship's to read
        return f"{name} failed: {e.__class__.__name__}"
    return f"there is no tool called {name}"
