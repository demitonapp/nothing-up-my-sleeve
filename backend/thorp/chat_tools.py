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
            "name": "vsm_status",
            "description": "Live status of the Thorp fleet: which training voyages are running (at sea) right "
            "now and what is next in the queue. Call this whenever the user asks what the fleet, the ships, "
            "the voyages, the training runs or the queue are doing; you cannot know it any other way.",
            "parameters": {
                "type": "object",
                "properties": {"next": {"type": "integer", "description": "how many queued lines to list (default 5, at most 20)"}},
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


def vsm_status(next: int = 5) -> dict:  # noqa: A002 - the argument's name is the model's
    """S2's view of the fleet (12 November, Justin: "what would be the most basic tool call we could make
    for our VSM system?"): every seat at sea now (thorp.vsm.helms) and the head of the queue
    (s2_coordination.queue_read.pending). It only reads; nothing here moves a voyage or the queue."""
    from thorp import vsm
    from thorp.viable.s2_coordination import queue_read

    try:
        n = max(1, min(int(next), 20))
    except (TypeError, ValueError):
        n = 5
    seats = [
        {"name": h.get("name"), "kind": h.get("kind"), "since": h.get("since"), "seat": h.get("slot")}
        for h in vsm.helms()
    ]
    pending = queue_read.pending()
    # said in words as well as a count: a small model read a bare "nothing is at sea" under an `at_sea`
    # key as the fleet being at sea
    return {
        "summary": f"{len(seats)} voyage(s) running now; {len(pending)} line(s) waiting in the queue"
        if seats else f"no voyage is running now (the fleet is in port); {len(pending)} line(s) waiting in the queue",
        "running_now": seats,
        "queue_length": len(pending),
        "next": [_queue_line(x) for x in pending[:n]],
    }


TOOLS = {"calculate": calculate, "current_time": current_time, "board_score": board_score, "vsm_status": vsm_status}


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
    `qwen-xml`), or None with the reason. A template that never mentions tools takes none."""
    t = template or ""
    if "tools" not in t:
        return {"format": None, "why": "the chat template takes no tools"}
    if "<function=" in t and "<parameter=" in t:
        return {"format": "qwen-xml", "why": "the template asks for <tool_call><function=…><parameter=…> calls"}
    if "<tool_call>" in t and "arguments" in t:
        return {"format": "json", "why": "the template asks for <tool_call>{name, arguments}</tool_call> calls"}
    return {"format": None, "why": "the template takes tools in a grammar the console does not read yet"}


_CALL = re.compile(r"<tool_call>\s*(.*?)\s*(?:</tool_call>|$)", re.S)
_FUNC = re.compile(r"<function=([^>\s]+)>\s*(.*?)\s*(?:</function>|$)", re.S)
_PARAM = re.compile(r"<parameter=([^>\s]+)>\s*(.*?)\s*(?:</parameter>|(?=<parameter=)|$)", re.S)


def _value(text: str) -> Any:
    """A qwen-xml parameter's text, as the JSON it reads as when it is one (a number, a list), else the text."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def parse_calls(text: str, fmt: str | None) -> list[dict]:
    """The calls in a model's turn, in order: [{"name", "arguments"}]. A call that does not parse is kept with
    an `error`, so the model is told what went wrong instead of the call vanishing."""
    if not fmt or "<tool_call>" not in text:
        return []
    calls = []
    for body in _CALL.findall(text):
        if fmt == "json":
            try:
                d = json.loads(body)
                calls.append({"name": str(d.get("name") or ""), "arguments": d.get("arguments") or d.get("parameters") or {}})
            except (ValueError, AttributeError) as e:
                calls.append({"name": "", "arguments": {}, "error": f"the call is not JSON: {e}", "raw": body[:300]})
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
