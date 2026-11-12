"""Tool calling for the foreign ships in the chat console (12 November, Justin: "are any of our foreign ships
wired for tool calling?" -- none were -- then "Yes, wire it").

Three parts, kept apart from the console's generation (thorp/chat.py foreign_stream drives the loop):

- **The tools.** Three, each read-only and safe to run on a model's say-so: `calculate` (arithmetic only,
  read from the expression's syntax tree, never evaluated as Python), `current_time`, and `board_score`
  (a model's AI2 ARC and IFEval readings, the numbers the extra small board is ranked by). Each is
  described to the model in the JSON-schema form the Hugging Face chat templates take as `tools`.
- **The call formats.** A model writes its call in its template's own grammar, so the parser follows the
  template (`tool_format`): `json` is `<tool_call>{"name": ..., "arguments": {...}}</tool_call>` (Qwen3,
  SmolLM3); `qwen-xml` is `<tool_call><function=NAME><parameter=P>value</parameter></function></tool_call>`
  (Qwen3.5). A template that takes tools in another grammar (Phi-4-mini, Gemma 4, gpt-oss) is said to be
  not wired yet, rather than read with the wrong parser.
- **The turns.** A call becomes an assistant message with `tool_calls`, and its result a `tool` message, as
  the templates expect, so the next generation reads the result in the model's own format.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import time
from typing import Any

# ---- the tools ----------------------------------------------------------------------------------------

SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate an arithmetic expression exactly: + - * / // % ** and parentheses, "
            "with sqrt, log, exp, sin, cos, tan, pi and e.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "for example (17 * 23) + sqrt(2)"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "The current local date and time.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "board_score",
            "description": "A model's readings on the extra small leaderboard: AI2 ARC-Easy and ARC-Challenge "
            "accuracy, and IFEval prompt-level strict accuracy.",
            "parameters": {
                "type": "object",
                "properties": {"model": {"type": "string", "description": "a model's name, for example pythia-410m"}},
                "required": ["model"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "queue_status",
            "description": "Live status of the Thorp queue: what is running (at sea) now, the next lines in the "
            "queue with the goal each one serves, when the whole queue will finish, and what will have been "
            "learned by then, goal by goal. Call this whenever the user asks what the fleet, the ships, the "
            "voyages, the training runs or the queue are doing, when it will be done, or what it will teach "
            "us; you cannot know it any other way. To ask about one job (is it running, where is it in the "
            "queue, how many are ahead of it), pass its name as find.",
            "parameters": {
                "type": "object",
                "properties": {
                    "next": {"type": "integer", "description": "how many queued lines to list (default 5, at most 20)"},
                    "find": {
                        "type": "string",
                        "description": "a job's name or part of it, as the user said it: where it is in the queue "
                        "and how many lines are ahead of it, or whether it is running now",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vsm_status",
            "description": "The whole of Thorp as a viable system, in one reading: a status line for each of "
            "its six systems (S1 operations, S2 coordination, S3 control, S3* audit, S4 intelligence, S5 policy) "
            "and what in each needs attention. Call this when the user asks how Thorp, the VSM or the system "
            "as a whole is doing, what is wrong, or what needs their attention.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "One system of the viable system, in detail. S1 operations: what is at sea, the "
            "expeditions, the GPUs hired. S2 coordination: the lanes (this Mac, Vast), queue collisions, the "
            "schedule. S3 control: the gate, the budget and the money spent, the last planning cycle and its "
            "proposals. S3* audit: what the last cycle's audit found. S4 intelligence: GPU hire measurements "
            "and failures, the judge, the outside models. S5 policy: the policies, the charter's terms, what "
            "waits for Justin's signature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {"type": "string", "enum": ["S1", "S2", "S3", "S3*", "S4", "S5"], "description": "which system"}
                },
                "required": ["system"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "expedition_status",
            "description": "How the expedition is tracking. The expedition is Nothing up my sleeve v0.1, the "
            "first fleet launch; Kipling, the knockout, the card census, Ogden and the others are the "
            "preparations for it. With no arguments: the phase v0.1 is in, how many parameters of its master "
            "charter are signed, which goals still decide a parameter, and the state of every ship. Call this "
            "when the user asks how v0.1, the launch, an expedition or a goal is going. To ask about one "
            "thing, pass its name as find.",
            "parameters": {
                "type": "object",
                "properties": {
                    "find": {
                        "type": "string",
                        "description": "an expedition (kipling, knockout, card census), a goal id (kipling:3) or "
                        "words from a goal, or a ship class (300k, 1m, 9m, 21m, 50m)",
                    }
                },
            },
        },
    },
]

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS = {"sqrt": math.sqrt, "log": math.log, "exp": math.exp, "sin": math.sin, "cos": math.cos, "tan": math.tan, "abs": abs}
_NAMES = {"pi": math.pi, "e": math.e}


def _arith(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _arith(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _arith(node.left), _arith(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_arith(node.operand))
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and len(node.args) == 1 and not node.keywords:
        return _FUNCS[node.func.id](_arith(node.args[0]))
    raise ValueError(f"not arithmetic: {ast.dump(node)[:60]}")


def calculate(expression: str) -> dict:
    expr = str(expression).replace("^", "**").replace("×", "*").replace("÷", "/")
    if len(expr) > 300:
        return {"error": "expression longer than 300 characters"}
    try:
        value = _arith(ast.parse(expr, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError) as e:
        return {"error": f"{e.__class__.__name__}: {e}"}
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    return {"expression": expression, "value": value}


def current_time() -> dict:
    return {"local": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "weekday": time.strftime("%A")}


def board_score(model: str) -> dict:
    """The board's own readings for a model, matched loosely on its name (case and punctuation ignored)."""
    from thorp import leaderboard

    want = re.sub(r"[^a-z0-9]", "", str(model).lower())
    if not want:
        return {"error": "no model named"}
    p = leaderboard.payload()

    def match(*names: str | None) -> bool:
        keys = [re.sub(r"[^a-z0-9]", "", str(n or "").lower()) for n in names]
        return any(k and (k == want or want in k) for k in keys)

    out: dict[str, Any] = {}
    for r in (p.get("arc_ai2") or {}).get("rows") or []:
        if match(r.get("name"), r.get("model")):
            out.setdefault("model", r.get("name"))
            for split in ("easy", "challenge"):
                s = r.get(split) or {}
                if s.get("accuracy") is not None:
                    out[f"arc_{split}"] = f"{100 * s['accuracy']:.1f}% of {s.get('questions')} questions"
            break
    for r in (p.get("ifeval") or {}).get("rows") or []:
        if match(r.get("name"), r.get("model"), r.get("run")):
            out.setdefault("model", r.get("name"))
            out["ifeval_prompt_strict"] = f"{100 * r['prompt_strict']:.1f}% of {r.get('prompts')} prompts" + (
                " (rigged: trained on the prompts)" if r.get("rigged") else ""
            )
            break
    return out or {"error": f"no reading on the board for {model!r}"}


def _queue_line(line: str) -> str:
    """A queue line as a reader names it: a fitout's name, or what an investigation or command runs."""
    s = str(line).strip()
    if s.startswith("cmd:"):
        m = re.search(r"investigate run (\S+)", s)
        if m:
            return f"investigation {m.group(1)}"
        m = re.search(r"-m (thorp\.[\w.]+)\s*(.*)", s)
        return f"command {m.group(1)} {m.group(2)}".strip() if m else "command " + s[4:].strip()[:80]
    return s.removeprefix("fitouts/")


def _where(find: str, seats: list[dict], names: list[str]) -> dict:
    """Where a named job is: running now, or its place in the queue with the lines ahead of it, matched on
    any part of its name (case ignored). Every match is listed, so a name in two lines is not read as one."""
    want = str(find).strip().lower()
    if not want:
        return {"error": "nothing to find"}
    running = [h["name"] for h in seats if want in str(h.get("name") or "").lower()]
    queued = [
        {"line": name, "position": i + 1, "ahead": i}
        for i, name in enumerate(names)
        if want in name.lower()
    ]
    if not running and not queued:
        return {"find": find, "answer": f"{find!r} is not running and not in the queue"}
    parts = [f"{r} is running now" for r in running]
    parts += [f"{q['line']} is number {q['position']} in the queue, with {q['ahead']} line(s) ahead of it" for q in queued]
    return {"find": find, "answer": "; ".join(parts), "running": running, "queued": queued}


def _clip(s: str | None, n: int = 220) -> str:
    v = re.sub(r"\s+", " ", str(s or "")).strip()
    return v if len(v) <= n else v[: n - 1].rstrip() + "…"


def _in_words(minutes: float | None) -> str | None:
    if minutes is None:
        return None
    m = max(0.0, float(minutes))
    return f"{round(m)} min" if m < 90 else f"{m / 60:.1f} h"


def _plan() -> dict:
    """The queue page's own plan (dash.server.api_queue): every line with its lane, its time, when it starts
    and the goal it serves, and the hours left. One source for the page and the tool, so they never disagree."""
    from thorp.dash import server

    return server.api_queue()


def _goals() -> dict[str, dict]:
    from thorp import expedition_goals

    return {g["goal_id"]: g for g in expedition_goals.read()}


def queue_status(next: int = 5, find: str | None = None) -> dict:  # noqa: A002 - the argument's name is the model's
    """The queue in one reading (12 November, Justin: "vsm_status(next=5) ... should actually be renamed
    queue_status and it should return the 5 top rows in the queue and what goals they're trying to achieve as
    well as the eta for the queue to finish and what the learnings will be at the end of the queue based on all
    the goals"). What is at sea, the next lines with their goals and start times (the queue page's plan), when
    the queue finishes, and, goal by goal over the whole queue, what will be known when its last line is home.
    It only reads; nothing here moves a voyage or the queue."""
    out = _fleet(next, find)
    n = out.pop("_n")
    try:
        plan = _plan()
    except Exception as e:  # noqa: BLE001  (no store or no plan: the fleet view still answers)
        out["eta"] = {"error": f"the queue's plan could not be read: {e.__class__.__name__}"}
        return out
    try:
        goals = _goals()
    except Exception:  # noqa: BLE001
        goals = {}
    rows = [r for r in plan.get("rows") or [] if r.get("n") is not None and r.get("status") != "at sea"]

    def goal_of(r: dict) -> dict | None:
        s = r.get("serves") or {}
        return {"goal": s.get("text"), "expedition": s.get("expedition_name")} if s.get("text") else None

    out["next"] = [
        {
            "position": r["n"],
            "name": r.get("name"),
            "kind": r.get("kind"),
            "lane": r.get("lane"),
            "starts_in": ("at least " if r.get("at_least") else "") + (_in_words(r.get("starts_in_min")) or "unknown"),
            "takes": _in_words(r.get("est_min")) or "unknown",
            **(goal_of(r) or {"goal": "no goal recorded for this line"}),
        }
        for r in rows[:n]
    ]
    hours = float(plan.get("hours_left") or 0)
    untimed = int(plan.get("without_a_time") or 0)
    finish = time.localtime(time.time() + hours * 3600)
    out["eta"] = {
        "hours_left": round(hours, 1),
        "finishes": time.strftime("%a %d %b %H:%M", finish),
        "note": f"at least: {untimed} line(s) have no time yet" if untimed else "every line has a time",
    }
    # what the queue will have taught by its end: each goal its lines serve, in the order the queue reaches
    # it, said as the question, how it is measured and why it matters, with when its last line comes home
    by_goal: dict[str, dict] = {}
    for r in rows:
        gid = r.get("goal_id")
        if not gid:
            continue
        end = (r.get("starts_in_min") or 0) + (r.get("est_min") or 0)
        g = by_goal.setdefault(gid, {"lines": 0, "end": 0.0, "row": r})
        g["lines"] += 1
        g["end"] = max(g["end"], end)
    learnings = []
    for gid, g in by_goal.items():
        word = goals.get(gid) or {}
        serves = g["row"].get("serves") or {}
        learnings.append({
            "goal": word.get("text") or serves.get("text") or gid,
            "expedition": word.get("name") or serves.get("expedition_name"),
            "lines": g["lines"],
            "known_in": _in_words(g["end"]),
            "will_learn": _clip(word.get("why")) or "the goal's reason is not written down",
            "measured_by": _clip(word.get("detail"), 160),
            "so_far": _clip(word.get("evidence"), 160) or word.get("status") or "open",
        })
    out["learnings"] = learnings
    untargeted = sum(1 for r in rows if not r.get("goal_id"))
    head = out["summary"]
    out["summary"] = (
        f"{head}; the queue finishes in about {_in_words(hours * 60)} ({out['eta']['finishes']})"
        f"{', at least' if untimed else ''}, and by then it will have worked on {len(learnings)} goal(s)"
        + (f"; {untargeted} line(s) serve no recorded goal" if untargeted else "")
    )
    return out


def _fleet(next: int = 5, find: str | None = None) -> dict:  # noqa: A002
    """S2's view of the fleet (12 November, Justin: "what would be the most basic tool call we could make
    for our VSM system?"): every seat at sea now (thorp.vsm.helms) and the head of the queue
    (s2_coordination.queue_read.pending). It only reads; nothing here moves a voyage or the queue."""
    from thorp import vsm
    from thorp.viable.s2_coordination import queue_read

    try:
        n = max(1, min(int(next), 20))
    except (TypeError, ValueError):
        n = 5
    # what is at sea is the coordinator's own record (s2.at_sea): every line it launched, voyage or
    # investigation; the helm locks add a voyage started by hand outside the queue. The helm alone missed
    # every investigation, which runs without the helm (12 November: arc-qwen3-4b had been at sea six
    # hours while this said the fleet was in port)
    from thorp.viable.s2_coordination import queue_store

    seats = []
    for r in queue_store.at_sea():
        pid, alive = r.get("pid"), False
        try:
            if pid:
                os.kill(int(pid), 0)
                alive = True
        except (OSError, ValueError):
            alive = False
        name = r.get("name") or _queue_line(r.get("text") or "")
        kind = "investigation" if "investigate run" in str(r.get("text") or "") else (r.get("kind") or "voyage")
        seats.append({"name": name, "kind": kind, "since": r.get("started"), "lane": r.get("lane"), "seat": r.get("seat"),
                      **({} if alive else {"note": "its process is gone: the record is stale"})})
    known = {s["name"] for s in seats}
    for h in vsm.helms():
        if h.get("name") not in known:
            seats.append({"name": h.get("name"), "kind": h.get("kind"), "since": h.get("since"), "seat": h.get("slot"),
                          "note": "holds the helm outside the queue"})
    pending = queue_read.pending()
    names = [_queue_line(x) for x in pending]
    # said in words as well as a count: a small model read a bare "nothing is at sea" under an `at_sea`
    # key as the fleet being at sea
    out = {
        "summary": f"{len(seats)} job(s) at sea now ({', '.join(x['name'] for x in seats)}); {len(pending)} line(s) waiting in the queue"
        if seats else f"no voyage is running now (the fleet is in port); {len(pending)} line(s) waiting in the queue",
        "running_now": seats,
        "queue_length": len(pending),
        "next": names[:n],
        "_n": n,
    }
    # a named job's place, first, so a small model reads the answer before the list (12 November: asked how
    # many lines were ahead of arc-ai2-21m, five models counted the whole queue or the first five instead)
    if find:
        out = {"where": _where(find, seats, names), **out}
    return out


# ---- the viable system: the whole, one system, and the expedition ---------------------------------------
#
# Three readings beside queue_status (12 November, Justin: "i like queue_status, I like vsm_status and then
# I'd like to be able to check status on each individual System within the VSM and then I'd like to be able
# to query expeditions for example how we're tracking against our v0.1"). Each only reads. Each answer opens
# with a `summary` in words, as queue_status does, because a small model reads the words and miscounts lists.

SYSTEM_NAMES = {"S1": "Operations", "S2": "Coordination", "S3": "Control", "S3*": "Audit", "S4": "Intelligence", "S5": "Policy"}
_SYSTEM_ALIASES = {
    "S1": ("s1", "1", "operations"),
    "S2": ("s2", "2", "coordination"),
    "S3": ("s3", "3", "control"),
    "S3*": ("s3*", "3*", "s3star", "3star", "audit", "s3audit"),
    "S4": ("s4", "4", "intelligence"),
    "S5": ("s5", "5", "policy"),
}

_KEPT: dict[str, tuple[float, Any]] = {}


def _kept(key: str, read, ttl: float = 120.0):
    """A slow reading kept for `ttl` seconds, so a second question in the same conversation does not wait
    for it again (vsm.audit() takes seven to ten seconds: its cleaning audit resolves two book lists)."""
    now = time.time()
    hit = _KEPT.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = read()
    _KEPT[key] = (now, value)
    return value


def _audit() -> dict:
    from thorp import vsm

    return _kept("audit", vsm.audit)


def _cycle() -> dict:
    from thorp.viable.s3_control import cycle

    return cycle.payload()


def _lanes() -> list[dict]:
    from thorp.viable.s2_coordination import lanes

    return [
        {"lane": d.lane, "kind": d.kind, "seats": d.seats, "open": bool(d.enabled), "note": d.note or ""}
        for d in lanes.lane_defs(fresh=True).values()
    ]


def _lints() -> list[str]:
    from thorp import vsm

    return list(vsm.lint_queue())


def _jobs() -> list[dict]:
    from thorp.viable.s2_coordination import schedule

    return schedule.jobs()


def _hires() -> list[dict]:
    """The GPUs hired and not yet released (S3's spend log), each with what it has cost so far."""
    from thorp.viable.s3_control import charter

    return [
        {"voyage": h.get("name"), "gpu": h.get("gpu"), "dollars_an_hour": round(float(h.get("dph") or 0), 3),
         "cost_so_far": round(charter.cost_of(h), 2)}  # fmt: skip
        for h in charter.out_now()
    ]


def _terms() -> dict:
    from thorp.viable.s5_policy import charter

    return charter.terms()


def _launch() -> dict:
    """The one expedition (thorp/launch.py): the page's own /api/launch, so the tool and the page agree."""
    from thorp import launch
    from thorp.dash import server

    return launch.payload(server._spec_detail)


def _expeditions() -> dict[str, dict]:
    """Every expedition in the code, with its name, what it is for and where it is now."""
    from thorp import fleet, vsm

    states = vsm.expedition_states()
    return {k: {"name": e.name, "goal": e.goal, "state": states.get(k) or e.status} for k, e in fleet.EXPEDITIONS.items()}


def _gate_log() -> list[dict]:
    from thorp import vsm

    return vsm.gate_log(400)


# vsm.audit()'s `refused_lately` counts the gate's last 400 decisions, which went back five days on
# 12 November: Ling read "stores (30)" as thirty refusals lately. The tool counts a day of them itself.
GATE_DAY_HOURS = 24


def _refused_today(log: list[dict], now: float | None = None) -> dict[str, int]:
    since = (now or time.time()) - GATE_DAY_HOURS * 3600
    out: dict[str, int] = {}
    for g in log:
        try:
            at = time.mktime(time.strptime(str(g.get("at"))[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue
        if at < since:
            continue
        for d in g.get("decisions") or []:
            if d.get("how") == "refused":
                out[d.get("policy")] = out.get(d.get("policy"), 0) + 1
    return out


def _goal_rows() -> list[dict]:
    from thorp import expedition_goals

    return expedition_goals.read()


class _World:
    """The readings the status tools draw on, each read once and apart, so one that fails (no store, no
    cycle kept yet) leaves the others standing and is named in `could_not_read`."""

    def __init__(self) -> None:
        self.unread: list[str] = []
        self._got: dict[str, Any] = {}
        # looked up when called, not when written, so a test can stand a reader in
        self._readers = {
            "audit": (lambda: _audit(), {}),
            "cycle": (lambda: _cycle(), {}),
            "lanes": (lambda: _lanes(), []),
            "lints": (lambda: _lints(), []),
            "jobs": (lambda: _jobs(), []),
            "hires": (lambda: _hires(), []),
            "terms": (lambda: _terms(), {}),
            "launch": (lambda: _launch(), {}),
            "fleet": (lambda: _fleet(1), {}),
            "gate": (lambda: _gate_log(), []),
        }

    def get(self, name: str) -> Any:
        if name not in self._got:
            read, empty = self._readers[name]
            try:
                self._got[name] = read() or empty
            except Exception as e:  # noqa: BLE001 - a reading that fails is said, and the rest still answer
                self.unread.append(f"{name}: {e.__class__.__name__}: {_clip(str(e), 120)}")
                self._got[name] = empty
        return self._got[name]


def _usd(v: Any) -> str:
    try:
        return f"${float(v):.2f}"
    except (TypeError, ValueError):
        return "an unknown sum"


def _words(*parts: str | None) -> str:
    return "; ".join(p for p in parts if p)


def _s1(w: _World) -> dict:
    a = w.get("audit").get("S1") or {}
    fl = w.get("fleet")
    seats = fl.get("running_now") or []
    states = a.get("expeditions") or {}
    away = {k: s for k, s in states.items() if s != "home"}
    hires = w.get("hires")
    acq = a.get("acquisition") or {}
    stale = [s["name"] for s in seats if "process is gone" in str(s.get("note") or "")]
    return {
        "summary": _words(
            f"{len(seats)} job(s) at sea now ({', '.join(str(s['name']) for s in seats)})" if seats else "nothing is at sea (the fleet is in port)",
            f"{fl.get('queue_length', 0)} line(s) wait in the queue",
            f"{len(away)} of {len(states)} expeditions are not home ({', '.join(f'{k}: {s}' for k, s in away.items())})" if states else None,
            f"{len(hires)} GPU(s) hired now" if hires else "no GPU is hired now",
            f"the library holds {int(acq['books']):,} books" if acq.get("books") else None,
        ),
        "attention": [f"{n} is recorded at sea but its process is gone" for n in stale],
        "at_sea": seats,
        "expeditions_not_home": away,
        "expeditions_home": sum(1 for s in states.values() if s == "home"),
        "hired_now": hires,
        "library": {k: acq.get(k) for k in ("books", "tokens_est", "intakes") if acq.get(k) is not None},
    }


def _s2(w: _World) -> dict:
    lanes = w.get("lanes")
    lints = w.get("lints")
    jobs = w.get("jobs")
    ticking = w.get("cycle").get("ticking")
    rows, said, attention = [], [], []
    for ln in lanes:
        note, _, paused = ln["note"].partition("| paused")
        why = _clip(paused.strip(" :"), 200) if paused else ""
        rows.append({"lane": ln["lane"], "kind": ln["kind"], "seats": ln["seats"], "state": "open" if ln["open"] else "paused",
                     **({"paused_because": why} if why and not ln["open"] else {})})  # fmt: skip
        said.append(f"the {ln['lane']} lane is open ({ln['seats']} seat(s))" if ln["open"] else f"the {ln['lane']} lane is paused")
        if not ln["open"]:
            attention.append(f"the {ln['lane']} lane is paused" + (f": {why}" if why else ""))
    attention += [f"queue collision: {x}" for x in lints]
    if ticking is False:
        attention.append("the schedule's tick is not loaded, so no scheduled job fires")
    return {
        "summary": _words(
            ", ".join(said) or "no lane is defined",
            f"{w.get('fleet').get('queue_length', 0)} line(s) wait in the queue",
            f"{len(lints)} collision(s) found in the queue" if lints else "no collision in the queue",
            f"{sum(1 for j in jobs if j.get('enabled'))} scheduled job(s) switched on" + (", but the tick is not loaded" if ticking is False else ""),
        ),
        "attention": attention,
        "lanes": rows,
        "queue_collisions": lints,
        "schedule": [{"job": j.get("key"), "on": bool(j.get("enabled")), "when": j.get("when"), "next": j.get("next"), "last": j.get("last")} for j in jobs],
        "schedule_ticking": ticking,
    }


def _last_cycle(w: _World) -> dict:
    return w.get("cycle").get("last") or {}


def _answered(p: dict, w: _World) -> bool:
    """A cycle's proposal that the world has answered since: "open the Vast lane" once it is open (Ling
    passed the 11:56 cycle's proposal on at 12:45, with the lane open since 12:3x)."""
    m = re.match(r"open the (\w+) lane", str(p.get("what") or ""), re.I)
    if m:
        return any(ln["lane"].lower() == m.group(1).lower() and ln["open"] for ln in w.get("lanes"))
    return False


def _proposals(w: _World, to: str | None = None) -> list[dict]:
    """The last cycle's proposals still standing, each with the cycle it came from."""
    at = _clock(_last_cycle(w).get("at"))
    return [
        {"to": p.get("to"), "what": p.get("what"), "why": _clip(p.get("why"), 200), "from_the_cycle_at": at}
        for p in _last_cycle(w).get("proposals") or []
        if (to is None or p.get("to") == to) and not _answered(p, w)
    ]


def _clock(at: Any) -> str | None:
    """A cycle's time as a person says it: 'today 11:56', not '2026-11-12T11:56+10:00'."""
    s = str(at or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", s)
    if not m:
        return s or None
    return f"today {m.group(2)}" if m.group(1) == time.strftime("%Y-%m-%d") else f"{m.group(1)} {m.group(2)}"


def _s3(w: _World) -> dict:
    a3 = w.get("audit").get("S3") or {}
    pol = a3.get("policies") or {}
    on = [k for k, p in pol.items() if p.get("enforced")]
    refused = _refused_today(w.get("gate"))
    last = _last_cycle(w)
    env, plan = last.get("envelope") or {}, last.get("plan") or {}
    chosen = next((o for o in plan.get("options") or [] if o.get("ships") == plan.get("ships")), {})
    proposals = _proposals(w)
    budget = (
        {"week_spent": _usd(env.get("week_spent")), "week_budget": _usd(env.get("weekly_budget")), "week_left": _usd(env.get("week_left")),
         "this_cycle_may_commit": _usd(env.get("cycle_allowance")), "of_which_quotes": _usd(env.get("spendable")),
         "cycles_left_this_week": env.get("cycles_left"), "purser": env.get("purser")}  # fmt: skip
        if env else {}
    )
    return {
        "summary": _words(
            f"{len(on)} of {len(pol)} policies are enforced at the gate" if pol else None,
            f"in the last {GATE_DAY_HOURS} hours the gate refused runs under {', '.join(f'{k} ({n})' for k, n in refused.items())}" if refused
            else f"the gate refused nothing in the last {GATE_DAY_HOURS} hours" if pol else None,
            f"{_usd(env.get('week_spent'))} of the week's {_usd(env.get('weekly_budget'))} is spent and this cycle may commit {_usd(env.get('cycle_allowance'))}" if env else "no planning cycle has been kept yet",
            f"the purser is {env.get('purser')}" if env else None,
            f"the last cycle ({_clock(last.get('at'))}, {last.get('how')}) plans {plan.get('ships')} hired ship(s): {len(plan.get('abroad') or [])} voyage(s) abroad and {plan.get('stay')} on this Mac" if plan else None,
            f"{len(proposals)} proposal(s) from that cycle wait for Justin" if proposals else None,
        ),
        "attention": [f"proposal to {p['to']} (cycle {p['from_the_cycle_at']}): {p['what']}" for p in proposals],
        "gate": {"enforced": on, "advisory": [k for k in pol if k not in on], f"refused_in_the_last_{GATE_DAY_HOURS}_hours": refused,
                 "runs_not_finished": a3.get("runs_not_finished")},  # fmt: skip
        "budget": budget,
        "last_cycle": (
            {"at": last.get("at"), "how": last.get("how"), "hired_ships": plan.get("ships"),
             "voyages_abroad": [{"name": x.get("name"), "gpu": x.get("gpu"), "cost": _usd(x.get("cost"))} for x in plan.get("abroad") or []],
             "voyages_on_this_mac": plan.get("stay"),
             "queue_home_in_hours": round(chosen["all_done_h"], 1) if chosen.get("all_done_h") is not None else None,
             "mac_alone_hours": round(plan["mac_only_h"], 1) if plan.get("mac_only_h") is not None else None}  # fmt: skip
            if plan else {}
        ),
        "proposals": proposals,
    }


def _s3star(w: _World) -> dict:
    a = w.get("audit")
    audit = _last_cycle(w).get("audit") or {}
    findings = [str(f) for f in audit.get("findings") or []]
    breaking = {k: v for k, v in (a.get("breaking") or {}).items() if v}
    broken = [f"{len(v)} queued run(s) break the {k} policy" for k, v in breaking.items()]
    cleaning = (a.get("S3*") or {}).get("cleaning") or {}
    return {
        "summary": _words(
            f"the last cycle's audit found {len(findings)} thing(s): {' | '.join(_clip(f, 160) for f in findings)}" if findings
            else "the last cycle's audit found nothing" if audit else "no cycle has been audited yet",
            f"{_usd(audit.get('wasted'))} of the {_usd(audit.get('spend'))} spent in that cycle bought no training" if audit.get("wasted") else None,
            ", ".join(broken) if broken else "no queued run breaks a policy" if a else None,
            f"texts are cleaned by {cleaning['version']}" if cleaning.get("version") else None,
        ),
        "attention": findings + broken,
        "last_cycle_findings": findings,
        "hires_against_quotes": [
            {"voyage": h.get("name"), "gpu": h.get("gpu"), "quote": _usd(h.get("quote")), "bill": _usd(h.get("cost")), "sailed": bool(h.get("sailed")),
             "ended": h.get("status"), **({"failed_in": h["failed_in"]} if h.get("failed_in") else {})}  # fmt: skip
            for h in audit.get("hires") or []
        ],
        "queued_runs_breaking_a_policy": {k: [_queue_line(x) for x in v[:8]] for k, v in breaking.items()},
    }


def _s4(w: _World) -> dict:
    c = w.get("cycle")
    a4 = w.get("audit").get("S4") or {}
    fails = c.get("failures") or {}
    classes = [
        {"gpu": x.get("gpu"), "hires": x.get("hires"), "sailed": x.get("sailed"), "failed": x.get("failed"),
         "overhead_minutes": round(x["overhead_min"], 1) if x.get("overhead_min") is not None else None,
         # a class none of whose hires has sailed borrows the others' median: said, so it is not read as a
         # measurement (the H100s read "measured 6.2 min" on 12 November, never having been hired)
         "measured": bool(x.get("own")), "source": _clip(x.get("source"), 120)}  # fmt: skip
        for x in c.get("classes") or []
    ]
    measured = [f"{x['gpu']} {x['overhead_minutes']} min" for x in classes if x["measured"] and x["overhead_minutes"] is not None]
    assumed = [x["gpu"] for x in classes if not x["measured"]]
    judge = c.get("judge") or {}
    can = c.get("judge_can_run") or [None, ""]
    waiting = sum(1 for x in c.get("to_judge") or [] if not x.get("judged"))
    # the judge is a model on this Mac and a voyage holds the memory it needs; said with the judge as the
    # subject, since Ling read "the judge ... 9m@... is at sea on this Mac" as the judge being at sea
    blocked = f"the judge {judge.get('name')} is waiting: it runs on this Mac and needs the memory, and {_clip(can[1], 140)}"
    return {
        "summary": _words(
            f"{fails.get('failed')} of {fails.get('hires')} GPU hires never sailed, {_usd(fails.get('wasted_cost'))} wasted" if fails.get("hires") else "no GPU hire is on record",
            ("set-up overhead measured: " + ", ".join(measured) if measured else "no set-up overhead measured yet")
            + (f" ({', '.join(assumed)} never sailed: assumed the same as the others)" if assumed else "") if classes else None,
            (f"the judge is {judge.get('name')}" + ("" if can[0] else f" and cannot run yet ({_clip(can[1], 120)})") + f"; {waiting} failed fit-out(s) wait for its verdict") if judge else "no judge is chosen",
            f"{len(a4.get('competitors') or [])} competitors and {len(a4.get('reference_ladder') or [])} reference models are read" if a4 else None,
        ),
        "attention": ([blocked] if judge and can[0] is False and waiting else []),
        "gpu_classes": classes,
        "hire_failures": {k: fails.get(k) for k in ("hires", "failed") if fails.get(k) is not None} | (
            {"wasted": _usd(fails.get("wasted_cost")), "wasted_minutes": round(fails.get("wasted_min") or 0)} if fails else {}
        ),
        "judge": {"name": judge.get("name"), "can_run_now": can[0], "why": _clip(can[1], 160), "verdicts_given": len(c.get("judgments") or []), "waiting": waiting},
        "outside_models": {"competitors": a4.get("competitors") or [], "reference_ladder": a4.get("reference_ladder") or []},
    }


def _s5(w: _World) -> dict:
    a = w.get("audit")
    pol = a.get("S5") or {}
    on = [k for k, p in pol.items() if p.get("enforced")]
    off = [k for k in pol if k not in on]
    excepted = sorted((a.get("S3") or {}).get("exceptions") or {})
    t = w.get("terms")
    r = w.get("launch").get("readiness") or {}
    asks = _proposals(w, "S5")
    return {
        "summary": _words(
            (f"{len(pol)} policies, {len(on)} enforced" + (f" and {len(off)} advisory ({', '.join(off)})" if off else "")) if pol else None,
            f"the terms allow {_usd(t.get('weekly_budget'))} a week and {_usd(t.get('voyage_budget'))} a voyage, {t.get('max_instances')} GPU hired at once, purser {t.get('purser')}" if t else None,
            f"{len(excepted)} policies carry exceptions ({', '.join(excepted)})" if excepted else None,
            f"{r.get('signed')} of {r.get('params')} parameters of the v0.1 charter are signed, {r.get('ready')} are ready for Justin to sign" if r else None,
            f"{len(asks)} proposal(s) to S5 wait for Justin" if asks else None,
        ),
        "attention": [f"proposal: {p['what']}" for p in asks] + ([f"{r['drifted']} signed charter parameter(s) have drifted since they were signed"] if r.get("drifted") else []),
        "policies": [{"policy": k, "enforced": bool(p.get("enforced")), "says": _clip(p.get("statement"), 170), "adopted": p.get("adopted")} for k, p in pol.items()],
        "terms": {k: t.get(k) for k in ("weekly_budget", "voyage_budget", "max_instances", "purser", "cycle_hours", "overrun", "gpus", "foreign_expeditions") if k in t},
        "exceptions": excepted,
        "proposals_to_s5": asks,
    }


_SYSTEMS = {"S1": _s1, "S2": _s2, "S3": _s3, "S3*": _s3star, "S4": _s4, "S5": _s5}


def _system_key(system: Any) -> str | None:
    s = re.sub(r"[\s_\-]+", "", str(system or "").lower()).removeprefix("system")
    return next((k for k, names in _SYSTEM_ALIASES.items() if s in names), None)


def vsm_status() -> dict:
    """The whole viable system in one reading: a line for each of S1 to S5 and S3* (the audit), and what in
    each needs attention. It only reads."""
    w = _World()
    rows = []
    for key, read in _SYSTEMS.items():
        d = read(w)
        rows.append({"system": key, "name": SYSTEM_NAMES[key], "status": d["summary"], "attention": d["attention"]})
    need = [r for r in rows if r["attention"]]
    out = {
        "summary": (
            f"{len(need)} of 6 systems need attention: " + "; ".join(f"{r['system']} {r['name']} ({_clip(r['attention'][0], 110)}"
                                                                    + (f", and {len(r['attention']) - 1} more" if len(r["attention"]) > 1 else "") + ")" for r in need)  # fmt: skip
            if need else "all six systems read clean: nothing needs attention"
        ),
        "systems": rows,
        # not "call system_status for detail": Ling read that as an instruction and called all six (12 November)
        "more": "this answers a question about the whole system; system_status is only for when the user asks about one system",
    }
    if w.unread:
        out["could_not_read"] = w.unread
    return out


def system_status(system: str = "") -> dict:
    """One system of the viable system, in detail. It only reads."""
    from thorp import vsm

    key = _system_key(system)
    if key is None:
        return {"error": f"no system called {system!r}; the systems are " + ", ".join(f"{k} ({n})" for k, n in SYSTEM_NAMES.items())}
    w = _World()
    d = _SYSTEMS[key](w)
    out = {"system": key, "name": SYSTEM_NAMES[key], "purpose": vsm.SYSTEMS[key.rstrip("*")].purpose if key != "S3*" else
           "independent of the gate: the last cycle's plan against what happened, and the queued runs that break a policy", **d}  # fmt: skip
    if w.unread:
        out["could_not_read"] = w.unread
    return out


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _serving(rows: list[dict]) -> dict[str, list[dict]]:
    """The queue's lines by the goal each serves (the queue page's plan), at sea first."""
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("goal_id"):
            by.setdefault(r["goal_id"], []).append(r)
    return by


def _goal_view(g: dict, part: dict | None, lines: list[dict]) -> dict:
    at_sea = [r.get("name") for r in lines if r.get("status") == "at sea"]
    queued = [r for r in lines if r.get("status") != "at sea"]
    return {
        "goal_id": g.get("goal_id"),
        "goal": g.get("text"),
        "status": g.get("status"),
        **({"evidence": _clip(g.get("evidence"), 220)} if g.get("evidence") else {}),
        **({"justin_said": _clip(g.get("words"), 160)} if g.get("words") else {}),
        # the part in words, never the bare key: Ling read a goal whose part is "delivered" (delivered by the
        # fleet, once it launches) as a goal already done (12 November)
        **({"role_in_v0.1": _role(part)} if part else {}),
        **({"decides": part["params"]} if part and part.get("params") else {}),
        "at_sea_for_it": at_sea,
        "queued_for_it": len(queued),
        **({"next_queued": queued[0].get("name"), "next_starts_in": _in_words(queued[0].get("starts_in_min")) or "unknown"} if queued else {}),
    }


_ROLE_WORDS = {
    "decides": "decides a parameter of the charter",
    "acceptance": "a reading the fleet will be judged on once it launches",
    "delivered": "something the launched fleet itself will deliver (not done until the fleet is home)",
    "carried": "carried over to the next expedition, not needed for v0.1",
    "unassigned": "no role in v0.1 assigned yet",
}


def _role(part: dict) -> str:
    words = _ROLE_WORDS.get(part.get("part") or "", part.get("part") or "")
    return f"{words}: {part['why']}" if part.get("why") else words


_SHIP_STATE = {
    "not laid": "is not laid yet",
    "laid": "is laid but has not sailed",
    "queued": "is queued",
    "at sea": "is at sea now",
    "home": "is home",
}


def _ship_words(cell: dict) -> str:
    """A v0.1 ship and its last rehearsal in two plain sentences, so a rehearsal's state is never read as
    the v0.1 ship's. Ling read '9m@v0.1: not laid; latest rehearsal 9m@v0.0.6 (home)' as 'the 9m is home',
    and a nested '(only a rehearsal, 21m@v0.0.6, is laid (its spec is written) ...)' as '21m@v0.1 is laid'."""
    if not cell.get("ship"):
        return cell.get("why") or cell.get("state") or "none"
    st = _SHIP_STATE.get(cell.get("state") or "", f"is {cell.get('state')}")
    reh = (cell.get("rehearsals") or [None])[0]
    tail = f" Its latest rehearsal, {reh['name']}, {_SHIP_STATE.get(reh['state'], 'is ' + str(reh['state']))}." if reh else " No rehearsal has sailed."
    return f"{cell['ship']} {st}.{tail}"


def expedition_status(find: str | None = None) -> dict:
    """How the expedition stands (12 November, Justin: "query expeditions for example how we're tracking
    against our v0.1"). There is one expedition, Nothing up my sleeve v0.1 (thorp/launch.py): its phases, its
    master charter's sign-offs, the goals still deciding a parameter, and the fleet it launches. What the code
    calls expeditions (Kipling, the knockout, the card census ...) are its preparations; `find` names one of
    them, a goal (kipling:3, or words from it) or a ship class (21m). It only reads."""
    p = _launch()
    r = p.get("readiness") or {}
    version = f"{p.get('name')} v{p.get('version')}"
    parts = {x["goal_id"]: x for x in p.get("parts") or []}
    try:
        serving = _serving((_plan().get("rows")) or [])
    except Exception:  # noqa: BLE001 - no plan: the goals still answer, without the queue beside them
        serving = {}

    if find and str(find).strip():
        want = _norm(find)
        if want in ("v01", "01", "v0.1", "launch", _norm(p.get("name")), _norm(version)):
            find = None
    if find and str(find).strip():
        want = _norm(find)
        # a ship class
        for row in p.get("fleet") or []:
            if _norm(row.get("class")) == want:
                cols = next((c for c in (p.get("charter") or {}).get("columns") or [] if c.get("class") == row["class"]), {})
                return {
                    "summary": f"the {row['class']} class of {version}: base: {_ship_words(row['base'])}; instruct: {_ship_words(row['instruct'])}",
                    "class": row["class"],
                    "base": row["base"],
                    "instruct": row["instruct"],
                    "voyages_sailed_at_this_size": row.get("voyages"),
                    "mean_minutes_a_voyage": round(row["mean_minutes"]) if row.get("mean_minutes") else None,
                    "charter_read_from": {k: v for k, v in cols.items() if k != "class"},
                }
        goals = _goal_rows()
        exps = _expeditions()
        # a goal by its id
        g = next((x for x in goals if _norm(x["goal_id"]) == want), None)
        if g:
            v = _goal_view(g, parts.get(g["goal_id"]), serving.get(g["goal_id"], []))
            return {"summary": f"{g['goal_id']} ({(exps.get(g['expedition_key']) or {}).get('name') or g['expedition_key']}): "
                               f"{g['text']} is {g['status']}; {v['queued_for_it']} queued line(s) and {len(v['at_sea_for_it'])} at sea serve it", **v}  # fmt: skip
        # a preparation, by its key or its name
        key = next((k for k, e in exps.items() if want in (_norm(k), _norm(e["name"]))), None) or next(
            (k for k, e in exps.items() if want in _norm(k) or want in _norm(e["name"])), None
        )
        if key:
            mine = [x for x in goals if x["expedition_key"] == key]
            views = [_goal_view(x, parts.get(x["goal_id"]), serving.get(x["goal_id"], [])) for x in mine]
            prep = (p.get("preparations") or {}).get(key) or {}
            count = {s: sum(1 for x in mine if x["status"] == s) for s in ("done", "partly", "open", "dropped")}
            return {
                # said as a preparation first: Ling read Kipling as "the first fleet launch for v0.1" (12 November)
                "summary": _words(
                    f"{exps[key]['name']} is one of the preparations for {version}, not the launch itself; it is {exps[key]['state']}",
                    f"{count['done']} of {len(mine)} goal(s) done, {count['partly']} partly, {count['open']} open" + (f", {count['dropped']} dropped" if count["dropped"] else "") if mine else "it states no goals",
                    f"{prep['blocking']} of its goals still hold up a parameter of {version}" if prep.get("blocking") else f"none of its goals holds up {version}",
                    f"{sum(v['queued_for_it'] for v in views)} queued line(s) serve it",
                ),
                "expedition": key,
                "name": exps[key]["name"],
                "state": exps[key]["state"],
                "what_it_is_for": _clip(exps[key]["goal"], 260),
                "decides_in_the_charter": prep.get("decides") or [],
                "goals": views,
            }
        # words from a goal
        hits = [x for x in goals if want in _norm(x["text"])]
        if hits:
            return {"summary": f"{len(hits)} goal(s) mention {find!r}",
                    "goals": [_goal_view(x, parts.get(x["goal_id"]), serving.get(x["goal_id"], [])) for x in hits[:6]]}  # fmt: skip
        return {"error": f"nothing called {find!r}: name an expedition ({', '.join(exps)}), a goal id such as kipling:3, or a class ({', '.join(str(x.get('class')) for x in p.get('fleet') or [])})"}

    phases = p.get("phases") or []
    active = [x["name"] for x in phases if x.get("state") == "active"]
    blocking = [x for x in parts.values() if x.get("part") == "decides" and x.get("status") in ("open", "partly")]
    ready = [f"{g['name']}: {q['name']}" for g in (p.get("charter") or {}).get("groups") or [] for q in g.get("params") or [] if q.get("state") == "ready"]
    try:
        exps = _expeditions()
    except Exception:  # noqa: BLE001
        exps = {}
    return {
        "summary": _words(
            f"{version} is in {', '.join(active) or 'no phase'}" + ("" if p.get("frozen") else f" (not frozen: the draft standard is SOP v{p.get('draft')})"),
            f"of the master charter's {r.get('params')} parameters, {r.get('signed')} are signed, {r.get('ready')} are ready for Justin to sign and {r.get('waiting')} wait on an open goal"
            + (f", {r.get('drifted')} drifted since signing" if r.get("drifted") else ""),
            f"{r.get('blocking')} goal(s) that decide a parameter are still open",
            f"none of the fleet's {r.get('ships')} v0.1 ships is home" if not r.get("home") else f"{r.get('home')} of the fleet's {r.get('ships')} v0.1 ships are home",
        ),
        "phases": [{"phase": x["name"], "state": x["state"], "note": x["note"]} for x in phases],
        "charter": {k: r.get(k) for k in ("params", "signed", "ready", "waiting", "drifted")},
        "ready_to_sign": ready,
        "goals_still_deciding": [
            {"goal_id": x["goal_id"], "goal": x["text"], "status": x["status"], "expedition": x.get("expedition_name") or x.get("expedition"),
             "decides": x.get("params") or [], "queued_for_it": sum(1 for q in serving.get(x["goal_id"], []) if q.get("status") != "at sea"),
             "at_sea_for_it": [q.get("name") for q in serving.get(x["goal_id"], []) if q.get("status") == "at sea"]}  # fmt: skip
            for x in blocking
        ],
        "preparations": [
            {"expedition": k, "name": (exps.get(k) or {}).get("name") or k, "state": (exps.get(k) or {}).get("state"), "kind": v.get("kind"),
             "goals_holding_up_v0.1": v.get("blocking")}  # fmt: skip
            for k, v in (p.get("preparations") or {}).items()
        ],
        "fleet": [{"class": row["class"], "base": _ship_words(row["base"]), "instruct": _ship_words(row["instruct"])} for row in p.get("fleet") or []],
        "more": "pass find: an expedition (kipling), a goal id (kipling:3) or a class (21m)",
    }


TOOLS = {
    "calculate": calculate,
    "current_time": current_time,
    "board_score": board_score,
    "queue_status": queue_status,
    "vsm_status": vsm_status,
    "system_status": system_status,
    "expedition_status": expedition_status,
}


def run(name: str, arguments: dict) -> dict:
    """Run one call. A tool that is not on the list, or arguments it does not take, come back as an error
    the model reads, never an exception in the console."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"no tool named {name!r}; the tools are {', '.join(TOOLS)}"}
    try:
        return fn(**(arguments or {}))
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:  # noqa: BLE001 - a tool's failure is the model's to read
        return {"error": f"{e.__class__.__name__}: {e}"}


# ---- the call formats ---------------------------------------------------------------------------------


def tool_format(template: str) -> dict:
    """What a model's chat template says about tools: `format` is the grammar the parser reads (`json`,
    `qwen-xml`, `bailing-xml`), or None with the reason. A template that never mentions tools takes none."""
    t = template or ""
    if "tools" not in t:
        return {"format": None, "why": "the chat template takes no tools"}
    # Ling 3.0 / Bailing V3: the template's prose says "function name and arguments", but the grammar it
    # asks for is XML — name, then <arg_key>/<arg_value> pairs. It was read as JSON, so json.loads() failed
    # on the name at character 0 and every call came back unknown() (12 November).
    if "<arg_key>" in t and "<arg_value>" in t:
        return {"format": "bailing-xml", "arg": "tools", "why": "the template asks for <tool_call>NAME<arg_key>…</arg_key><arg_value>…</arg_value></tool_call> calls"}
    if "<function=" in t and "<parameter=" in t:
        return {"format": "qwen-xml", "arg": "tools", "why": "the template asks for <tool_call><function=…><parameter=…> calls"}
    if "<tool_call>" in t and "arguments" in t:
        # SmolLM3's template reads its tools from `xml_tools`, not `tools`: handed as `tools` they never reach
        # the prompt and the model does not know it has any (12 November: it called none in twelve asks)
        arg = "xml_tools" if "xml_tools" in t else "tools"
        return {"format": "json", "arg": arg, "why": "the template asks for <tool_call>{name, arguments}</tool_call> calls"}
    return {"format": None, "why": "the template takes tools in a grammar the console does not read yet"}


_CALL = re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", re.S)
_FUNC = re.compile(r"<function=([^>\s]+)>\s*(.*?)\s*(?:</function>|$)", re.S)
_PARAM = re.compile(r"<parameter=([^>\s]+)>\s*(.*?)\s*(?:</parameter>|(?=<parameter=)|$)", re.S)
# Ling/Bailing: <tool_call>NAME<arg_key>k</arg_key><arg_value>v</arg_value>…</tool_call>
_BAILING_NAME = re.compile(r"^\s*([A-Za-z_][\w.-]*)")
_BAILING_ARG = re.compile(r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>\s*(.*?)\s*</arg_value>", re.S)


def _value(text: str) -> Any:
    """A qwen-xml parameter's text, as the JSON it reads as when it is one (a number, a list), else the text."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _json_call(body: str) -> dict | None:
    """A JSON call (`{"name": ..., "arguments": {...}}`), or None when the body is not one. Some models
    write `arguments` as a JSON string rather than an object; that is read too, rather than refused."""
    try:
        d = json.loads(body)
    except ValueError:
        return None
    if not isinstance(d, dict):
        return None
    args = d.get("arguments") or d.get("parameters") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    return {"name": str(d.get("name") or ""), "arguments": args if isinstance(args, dict) else {}}


def parse_calls(text: str, fmt: str | None) -> list[dict]:
    """The calls in a model's turn, in order: [{"name", "arguments"}]. A call that does not parse is kept with
    an `error`, so the model is told what went wrong instead of the call vanishing."""
    if not fmt or "<tool_call>" not in text:
        return []
    calls = []
    for body in _CALL.findall(text):
        if fmt == "json":
            call = _json_call(body)
            calls.append(call if call else {"name": "", "arguments": {}, "error": "the call is not JSON", "raw": body[:300]})
        elif fmt == "bailing-xml":
            # a model that wrote JSON anyway is read as JSON, not refused for the template's grammar
            call = _json_call(body) if body.lstrip().startswith("{") else None
            if call is None:
                m = _BAILING_NAME.match(body)
                if not m:
                    calls.append({"name": "", "arguments": {}, "error": "no function name in the call", "raw": body[:300]})
                    continue
                call = {"name": m.group(1), "arguments": {k: _value(v) for k, v in _BAILING_ARG.findall(body)}}
            calls.append(call)
        elif fmt == "qwen-xml":
            f = _FUNC.search(body)
            if not f:
                calls.append({"name": "", "arguments": {}, "error": "no <function=…> in the call", "raw": body[:300]})
                continue
            args = {k: _value(v.strip()) for k, v in _PARAM.findall(f.group(2))}
            calls.append({"name": f.group(1), "arguments": args})
    return calls


def before_calls(text: str) -> str:
    """The turn's text before its first call: what the model said, without the call's own markup."""
    i = text.find("<tool_call>")
    return text if i < 0 else text[:i].rstrip()


def turns(calls: list[dict], results: list[dict], said: str = "") -> list[dict]:
    """The assistant turn that made the calls and one tool turn a result, as the templates render them."""
    assistant = {
        "role": "assistant",
        "content": said,
        "tool_calls": [
            {"type": "function", "function": {"name": c["name"] or "unknown", "arguments": c.get("arguments") or {}}}
            for c in calls
        ],
    }
    return [assistant] + [
        {"role": "tool", "name": c["name"] or "unknown", "content": json.dumps(r, ensure_ascii=False)} for c, r in zip(calls, results, strict=True)
    ]
