"""The Berkeley Function-Calling Leaderboard's single-turn splits (14 November, Justin: "what's the canonical tool calling
test we should be using?", then "Yes, build them"): the test the field quotes for tool calling, read on the part of it
a ship under 1B can be asked fairly.

BFCL gives a model one or more functions, each described (name, what it does, its parameters and their types), and a
request; the model writes the call. Its current version adds multi-turn, web-search and memory splits; below 1B nearly
everything fails those, so they are left out and only the single-turn, non-live splits are read, with `live_simple`
(real users' requests, one function) beside them:

    simple_python      400   one function offered, one call wanted
    multiple           200   two to four offered, one call to the right one
    parallel           200   one offered, several calls wanted in one turn
    parallel_multiple  200   several offered, several calls
    irrelevance        240   no offered function fits: the right move is no call
    live_simple        258   one function, users' own wording

Shishir G. Patil et al., the Gorilla project (github.com/ShishirPatil/gorilla, berkeley-function-call-leaderboard),
Apache-2.0. The files are pinned to commit 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8 (read 14 November 2026) and
fetched once into ``data/bfcl/<commit>`` (THORP_BFCL overrides the root); they are data, read with plain json, never run.

**This is a reimplementation, not the official scorer.** The check follows the spirit of BFCL's AST checker: the
function's name; every required parameter given; no parameter the function does not have; each value among the
item's possible answers (strings compared lowercased with spaces and ``,./-_*^`` removed, an int accepted for a float,
lists element by element, a parameter whose possible answers include ``""`` may be left out). Parallel splits want the
right set of calls in any order, each matched once. A reading here is a single-turn subset, read our own way, and
must not be set beside the official overall score.

How a ship is asked, since none of ours writes JSON: the offered functions are written as compact plain text
(``name(param: type, other?: type) - first sentence of the description``, ``?`` marking an optional parameter) above
the request, in the ship's own marked turn (thorp/turns.py). Its call is read from what it writes after ``<call>`` (or
after its thinking, ``turns.after_thought``) with Python's own parser (``ast.parse``, never ``eval``), positional or
keyword. For the parallel splits, each call it writes is answered ``<result>done`` and it is let go on, up to one call
more than the item wants. Only the user's words are rendered (a live item's system message is left out). An item whose
prompt and answer room do not fit the window is skipped and counted, never scored wrong.
"""

from __future__ import annotations

import ast
import json
import os
import re
import urllib.request
from pathlib import Path

from thorp import paths

COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
BASE_URL = f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{COMMIT}/berkeley-function-call-leaderboard/bfcl_eval/data"
SPLITS = ("simple_python", "multiple", "parallel", "parallel_multiple", "irrelevance", "live_simple")
PARALLEL = ("parallel", "parallel_multiple")
NO_CALL = ("irrelevance",)
DESC_CHARS = 100


def root() -> Path:
    """Where the BFCL files live (``data/bfcl/<commit>`` by default, THORP_BFCL overrides it)."""
    return Path(os.environ.get("THORP_BFCL") or paths.resolve(f"data/bfcl/{COMMIT}"))


def ensure(base: Path | None = None) -> Path:
    """The six splits and their possible answers, downloaded once (about 1.6 MB) at the pinned commit."""
    base = Path(base) if base else root()
    want = [(f"BFCL_v4_{s}.json", base / f"BFCL_v4_{s}.json") for s in SPLITS]
    want += [(f"possible_answer/BFCL_v4_{s}.json", base / "possible_answer" / f"BFCL_v4_{s}.json")
             for s in SPLITS if s not in NO_CALL]  # fmt: skip
    for rel, p in want:
        if p.exists():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(f"{BASE_URL}/{rel}", timeout=60) as r:  # noqa: S310  a pinned https URL
            p.write_bytes(r.read())
    return base


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load(split: str, base: Path | None = None) -> list[dict]:
    """A split's items, each with its possible answers (`answers`, empty for irrelevance)."""
    if split not in SPLITS:
        raise KeyError(f"unknown BFCL split {split!r}: one of {SPLITS}")
    base = Path(base) if base else root()
    items = _jsonl(base / f"BFCL_v4_{split}.json")
    if split in NO_CALL:
        for it in items:
            it["answers"] = []
        return items
    truth = {a["id"]: a["ground_truth"] for a in _jsonl(base / "possible_answer" / f"BFCL_v4_{split}.json")}
    for it in items:
        it["answers"] = truth.get(it["id"], [])
    return items


# ---- how an item is put to a ship


def _first_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    cut = re.split(r"(?<=[.!?])\s", s, maxsplit=1)[0]
    return cut if len(cut) <= DESC_CHARS else cut[: DESC_CHARS - 3].rstrip() + "..."


def signature(fn: dict) -> str:
    """One offered function as plain text: ``name(param: type, other?: type) - what it does``."""
    params = (fn.get("parameters") or {}).get("properties") or {}
    required = set((fn.get("parameters") or {}).get("required") or [])
    parts = [f"{k}{'' if k in required else '?'}: {(v or {}).get('type', 'any')}" for k, v in params.items()]
    return f"{fn['name']}({', '.join(parts)}) - {_first_sentence(fn.get('description', ''))}"


def request(item: dict) -> str:
    """The user's words: every user message of the item's single turn, in order."""
    turn = (item.get("question") or [[]])[0]
    return "\n".join(m.get("content", "") for m in turn if m.get("role") == "user").strip()


def rendered(item: dict) -> str:
    """The question as the ship is asked it: the offered functions, then the request."""
    tools = "\n".join(signature(f) for f in item.get("function") or [])
    return f"Tools:\n{tools}\n\n{request(item)}"


# ---- reading a call


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _name(node.value)
        return f"{head}.{node.attr}" if head else None
    return None


_UNREADABLE = object()


def _value(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return _UNREADABLE


def parse_call(text: str, functions: list[dict] | None = None) -> dict | None:
    """A written call as {"name", "args"} (positional arguments named in the function's parameter order when the
    function is known), or None when it is not a call Python's parser can read. Never evaluated."""
    s = (text or "").strip()
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return None
    call = tree.body
    if not isinstance(call, ast.Call):
        return None
    name = _name(call.func)
    if not name:
        return None
    order: list[str] = []
    for f in functions or []:
        if f.get("name") == name:
            order = list(((f.get("parameters") or {}).get("properties") or {}).keys())
    args: dict = {}
    for i, a in enumerate(call.args):
        args[order[i] if i < len(order) else f"_{i}"] = _value(a)
    for kw in call.keywords:
        if kw.arg is None:  # **kwargs: not a call BFCL would read
            return None
        args[kw.arg] = _value(kw.value)
    return {"name": name, "args": args}


# ---- the check


def _norm(v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return re.sub(r"[ ,./\-_*^]", "", v.lower())
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {k: _norm(x) for k, x in v.items()}
    return v


def _same(got, want) -> bool:
    if isinstance(want, dict) and isinstance(got, dict):
        # a nested dict's possible answers are themselves lists of options a key
        if set(got) - set(want):
            return False
        for k, opts in want.items():
            opts = opts if isinstance(opts, list) else [opts]
            if k not in got:
                if "" not in opts:
                    return False
                continue
            if not any(_same(got[k], o) for o in opts):
                return False
        return True
    return _norm(got) == _norm(want)


def check(call: dict, want: dict, functions: list[dict]) -> tuple[bool, str]:
    """One call against one possible answer ({name: {param: [allowed values]}}): (right, why not)."""
    (wname, wargs), = want.items()
    if call["name"] != wname and call["name"].replace(".", "_") != wname.replace(".", "_"):
        return False, f"name {call['name']} for {wname}"
    fn = next((f for f in functions if f.get("name") == wname), {})
    props = ((fn.get("parameters") or {}).get("properties") or {}).keys()
    required = (fn.get("parameters") or {}).get("required") or []
    for k in call["args"]:
        if k not in props:
            return False, f"no parameter {k}"
    for k in required:
        if k not in call["args"]:
            return False, f"missing {k}"
    for k, v in call["args"].items():
        if v is _UNREADABLE:
            return False, f"{k} is not a plain value"
        opts = wargs.get(k)
        if opts is None:
            return False, f"{k} is not in the answer"
        if not any(o != "" and _same(v, o) for o in opts):
            return False, f"{k}={v!r}"
    for k, opts in wargs.items():
        if k not in call["args"] and "" not in opts:
            return False, f"missing {k}"
    return True, ""


def score(split: str, calls: list[dict], item: dict) -> tuple[bool, str]:
    """An item's verdict from the calls a ship wrote (parsed; a written call that could not be read is None)."""
    functions = item.get("function") or []
    wanted = item.get("answers") or []
    if split in NO_CALL:
        return (not calls), ("" if not calls else "called when nothing fits")
    if not calls:
        return False, "no call"
    if any(c is None for c in calls):
        return False, "a call that does not parse"
    if split not in PARALLEL:
        return check(calls[0], wanted[0], functions) if len(calls) == 1 else (False, f"{len(calls)} calls for 1")
    if len(calls) != len(wanted):
        return False, f"{len(calls)} calls for {len(wanted)}"
    used: set[int] = set()
    for c in calls:  # each call matched to a distinct possible answer
        hit = next((i for i, w in enumerate(wanted) if i not in used and check(c, w, functions)[0]), None)
        if hit is None:
            return False, f"no match for {c['name']}"
        used.add(hit)
    return True, ""
