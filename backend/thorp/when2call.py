"""When2Call, the test of when (not) to call a tool (14 November, Justin: "Yes, build them", of the tool-calling tests
for the 9m, 21m and 50m): NVIDIA's multiple-choice set, read as AI2 ARC is read (``thorp/arc_ai2.py``).

Each question offers a ship four replies, one of each kind -- a direct answer, a tool call, a question back asking for
what is missing (``request_for_info``), and saying it cannot answer (``cannot_answer``) -- and one of them is right
for the tools it was given. The gold answers in the test file are only the last three (1,295 tool calls, 1,062
requests for information, 1,295 cannot-answers; no question's right reply is a direct answer). BFCL reads whether a
call is written correctly; When2Call reads whether a call should be written at all, which is what the fleet's
`tools/none_right` and the think-then-act leg were after.

Read as the authors read it with lm-evaluation-harness, zero-shot multiple choice by likelihood, not generation, so
a 9m that cannot yet write a clean call is still read. In the ship's own turns: ``<question>`` + the tools offered,
written short (``name(param, ...) - the first sentence of its description``, never the raw JSON, which would not fit
1,024 pieces of a 2,048-piece Ogden vocabulary) + the person's question; each reply as the ship would write it, a
call as ``<call>name(value, ...)`` (the values bare and in order, as the fleet's tool lessons write them) and the
other three as ``<answer>text``. The opening mark is part of each reply's own pieces, so the first thing the reading
pays for is the move itself.

Metrics (``summary``):

- ``acc_norm``: the reply with the lowest mean loss a piece wins (as ``arc_ai2``; the fleet's reading);
- ``acc_bytes``: the lowest total loss over the reply's bytes, lm-evaluation-harness's own ``acc_norm`` (characters
  there), the column the paper's table reports as Acc-Norm -- the one to set beside its numbers;
- ``acc``: the lowest total loss;
- ``macro_f1`` over the four kinds (scikit-learn's macro average over the kinds present in gold or bet);
- ``hallucination``: the paper's tool hallucination rate -- of the cannot-answer questions given no tools at all, the
  share whose bet was a call (lower is better); and ``call_when_not``, the share of every question whose right reply
  is not a call where the bet was one.

Chance is 25%. A question that does not fit the window, or one of whose replies the tokeniser cannot spell, is
skipped and counted, never scored wrong. The paper's readings (Acc-Norm, lm-eval): Qwen 2.5 0.5B Instruct 53.5%,
Llama 3.2 1B Instruct 45.1%, xLAM 1B 45.7%; tool hallucination 20%, 43%, 40%.

Ross, Mahabaleshwarkar and Suhara, "When2Call: When (not) to Call Tools", NAACL 2025, arXiv:2504.18851. The code is
Apache-2.0 and the data CC-BY-4.0 (the dataset card, huggingface.co/datasets/nvidia/When2Call). The test file is
``data/test/when2call_test_mcq.jsonl`` at github.com/NVIDIA/When2Call, pinned to one commit below and fetched once
into ``data/when2call`` (THORP_WHEN2CALL overrides it). It is read as data with ``json``; nothing in it is run.

This module knows nothing of any model: a model is a function ``ce(x, y) -> (batch, time) nats``.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np

from thorp import cleaning, paths, turns

REPO = "NVIDIA/When2Call"
COMMIT = "ecc8d42388e91ab37e7e737d48e16e8ecea3d1dc"  # main on 14 November 2026 (last pushed 29 April 2025)
FILE = "when2call_test_mcq.jsonl"
URL = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/data/test/{FILE}"
COUNT = 3652
KINDS = ("direct", "tool_call", "request_for_info", "cannot_answer")  # the file's own order of replies
CHANCE = 0.25
DESC_CHARS = 80  # a tool's description, cut to its first sentence and at most this many characters
_SENT = "ZQXJ"


def root() -> Path:
    """Where the When2Call file lives (``data/when2call`` by default, THORP_WHEN2CALL overrides it)."""
    return Path(os.environ.get("THORP_WHEN2CALL") or paths.resolve("data/when2call"))


def ensure(base: Path | None = None) -> Path:
    """The test file, downloaded once (about 20 MB) at the pinned commit. Returns its path."""
    base = Path(base) if base else root()
    p = base / FILE
    if p.exists():
        return p
    import urllib.request

    base.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".part")
    with urllib.request.urlopen(URL, timeout=120) as r, open(tmp, "wb") as f:  # noqa: S310 (a pinned https URL)
        f.write(r.read())
    tmp.rename(p)
    return p


def questions(limit: int | None = None, base: Path | None = None, path: Path | None = None) -> list[dict]:
    """Every question, in the file's order; `limit` keeps that many taken evenly through the set (a pilot).

    A question is ``{id, source, question, tools: [dict], replies: [str x4], kinds, answer}``, the replies in the
    file's own order (``KINDS``) and `answer` the right one's index. A row whose JSON or replies are malformed is
    left out."""
    p = Path(path) if path else ensure(base)
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            kinds = list(r["answers"].keys())
            tools = [json.loads(t) if isinstance(t, str) else t for t in (r.get("tools") or [])]
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if r.get("correct_answer") not in kinds or len(kinds) != 4:
            continue
        out.append({"id": str(r.get("uuid")), "source": str(r.get("source") or ""), "question": str(r["question"]).strip(),
                    "tools": tools, "kinds": kinds, "replies": [str(r["answers"][k]) for k in kinds],
                    "answer": kinds.index(r["correct_answer"])})  # fmt: skip
    if limit and 0 < int(limit) < len(out):
        n = int(limit)
        out = [out[i * len(out) // n] for i in range(n)]
    return out


def _first_sentence(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    m = re.match(r"(.+?[.!?])(\s|$)", s)
    s = m.group(1) if m else s
    return s if len(s) <= DESC_CHARS else s[: DESC_CHARS - 3].rstrip() + "..."


def tool_line(tool: dict) -> str:
    """One tool, short: ``name(param, ...) - the first sentence of its description``."""
    props = ((tool.get("parameters") or {}).get("properties") or {}) if isinstance(tool.get("parameters"), dict) else {}
    desc = _first_sentence(tool.get("description") or "")
    return f"{tool.get('name', '?')}({', '.join(props)})" + (f" - {desc}" if desc else "")


def asked(q: dict) -> str:
    """What the ship is asked, before its turn's marks: the tools offered, then the person's question."""
    tools = "; ".join(tool_line(t) for t in q["tools"]) if q["tools"] else "none"
    return f"Tools: {tools}{'' if tools.endswith(('.', '!', '?')) else '.'} {q['question']}"


def call_text(reply: str) -> str:
    """A reply that calls a tool, as the fleet's lessons write a call: ``name(value, ...)``, the values bare and in
    the order given. A reply that is not the expected JSON is read as it stands."""
    try:
        c = json.loads(reply)
        args = c.get("arguments") or {}
        vals = [json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list) else str(v) for v in args.values()]
        return f"{c['name']}({', '.join(vals)})"
    except (ValueError, KeyError, TypeError, AttributeError):
        return reply.strip()


def reply_text(kind: str, reply: str) -> str:
    """A reply in the ship's turn: a call opens with ``<call>``, every other kind with ``<answer>``."""
    if kind == "tool_call":
        return f"{turns.CALL}{call_text(reply)}"
    return f"<answer>{reply.strip()}"


def render(q: dict, clean: str = "marks-v1") -> tuple[str, list[str]] | None:
    """The question's head and each reply's own text, as the voyage's cleaning writes them, or None when cleaning a
    turn changes its head (it cannot then be split into a shared head and a reply). The whole turn is cleaned and cut
    at the head, so curly quotes and spacing in a reply are read as the ship read its lessons."""
    head = cleaning.clean(f"<question>{asked(q)}{_SENT}", clean).split(_SENT)[0]
    opts = []
    for kind, reply in zip(q["kinds"], q["replies"], strict=True):
        full = cleaning.clean(f"<question>{asked(q)}{reply_text(kind, reply)}", clean)
        full = re.sub(r"\n?<eos>\s*$", "", full)
        if not full.startswith(head):
            return None
        opts.append(full[len(head) :])
    return head, opts


# the authors' default prompt (evaluation/mcq/lm_eval_harness/when2call/utils.py, process_docs_default), for a model
# that is not ours: the tools as JSON, the replies as written. The paper's own table reads each model in its own chat
# template; this is the harness's plain task, so a reading here sits near the paper's, not on it.
OUTSIDE_SYSTEM = ("You are a helpful AI assistant. \nYou have access to the following tools described in <tool></tool> "
                  "which you can use to answer the user's questions.\nOnly use a tool if it directly answers the user's "
                  "question.\n")  # fmt: skip
OUTSIDE_USE = ('To use a tool, return JSON in the following format:\n{"name": "tool_name", "arguments": {"argument1": '
               '"value1", "argument2": "value2", ...}}\n')  # fmt: skip


def render_outside(q: dict, clean: str | None = None) -> tuple[str, list[str]]:
    """The question and replies as the authors' default task writes them (`clean` is ignored: an outside model reads
    the text as it is)."""
    tools = "\n\n".join(f"<tool>{json.dumps(t)}</tool>" for t in q["tools"])
    return f"{OUTSIDE_SYSTEM}\n{OUTSIDE_USE}\n\n{tools}\n\n{q['question']}", list(q["replies"])


def score(ce, encode, start: int, items: list[dict], batch: int = 32, context: int | None = None,
          clean: str = "marks-v1", renderer=None) -> list[dict]:  # fmt: skip
    """Each question with every reply's total loss, piece count and byte count, and the three bets.

    Only a reply's own pieces are paid for (its opening mark among them): the head is the same for every reply of a
    question. A question that cannot be rendered, has a reply the tokeniser cannot spell, or does not fit `context`
    is not read: ``read: False``, counted in ``skipped``."""
    flat = []  # (item index, reply index, head pieces, reply pieces)
    shapes: dict[int, tuple[list[str], int]] = {}
    for i, q in enumerate(items):
        r = (renderer or render)(q, clean)
        if r is None:
            continue
        head_text, opts = r
        head = [start, *encode(head_text)]
        pieces = [encode(o) for o in opts]
        if any(not p for p in pieces):
            continue
        if context is not None and max(len(head) - 1 + len(p) for p in pieces) > context:
            continue
        shapes[i] = (opts, len(head))
        for j, p in enumerate(pieces):
            flat.append((i, j, head, p))
    total = {i: [float("nan")] * 4 for i in shapes}
    count = {i: [0] * 4 for i in shapes}
    for s in range(0, len(flat), max(1, batch)):
        chunk = flat[s : s + max(1, batch)]
        width = max(len(h) - 1 + len(p) for _, _, h, p in chunk)
        x = np.zeros((len(chunk), width), dtype=np.int32)
        y = np.zeros((len(chunk), width), dtype=np.int32)
        mask = np.zeros((len(chunk), width), dtype=np.float64)
        for r, (_, _, h, p) in enumerate(chunk):
            seq = [*h, *p]
            x[r, : len(seq) - 1] = seq[:-1]
            y[r, : len(seq) - 1] = seq[1:]
            mask[r, len(seq) - 1 - len(p) : len(seq) - 1] = 1.0
        nats = np.asarray(ce(x, y), dtype=np.float64).reshape(len(chunk), width)
        for r, (i, j, _, p) in enumerate(chunk):
            total[i][j] = float((nats[r] * mask[r]).sum())
            count[i][j] = len(p)
    rows = []
    for i, q in enumerate(items):
        row = {"id": q["id"], "source": q["source"], "gold": q["kinds"][q["answer"]], "tools": len(q["tools"]),
               "read": i in shapes}  # fmt: skip
        if i in shapes:
            opts, head_len = shapes[i]
            t = np.asarray(total[i])
            per_piece = t / np.asarray(count[i], dtype=np.float64)
            per_byte = t / np.asarray([max(1, len(o.encode("utf-8"))) for o in opts], dtype=np.float64)
            bets = {"acc_norm": int(np.argmin(per_piece)), "acc_bytes": int(np.argmin(per_byte)), "acc": int(np.argmin(t))}
            row.update({
                "head_pieces": head_len, "pieces": count[i], "nats": [round(float(v), 4) for v in t],
                **{f"bet_{k}": q["kinds"][v] for k, v in bets.items()},
                **{f"right_{k}": v == q["answer"] for k, v in bets.items()},
            })  # fmt: skip
        rows.append(row)
    return rows


def _macro_f1(gold: list[str], bet: list[str]) -> float:
    labels = sorted(set(gold) | set(bet))
    f1s = []
    for k in labels:
        tp = sum(g == k and b == k for g, b in zip(gold, bet, strict=True))
        fp = sum(g != k and b == k for g, b in zip(gold, bet, strict=True))
        fn = sum(g == k and b != k for g, b in zip(gold, bet, strict=True))
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1s)) if f1s else 0.0


def summary(rows: list[dict], key: str = "acc_norm") -> dict:
    """The readings of a list of scored questions; `key` names the bet the per-kind readings and the F1 use."""
    read = [r for r in rows if r["read"]]
    out: dict = {"n": len(read), "skipped": len(rows) - len(read), "chance": CHANCE}
    if not read:
        return out
    for k in ("acc_norm", "acc_bytes", "acc"):
        out[k] = sum(r[f"right_{k}"] for r in read) / len(read)
    out["macro_f1"] = _macro_f1([r["gold"] for r in read], [r[f"bet_{key}"] for r in read])
    out["by_gold"] = {g: {"n": len(rs), "acc": sum(r[f"right_{key}"] for r in rs) / len(rs)}
                      for g in KINDS if (rs := [r for r in read if r["gold"] == g])}  # fmt: skip
    out["bets"] = {k: sum(r[f"bet_{key}"] == k for r in read) / len(read) for k in KINDS}
    base = [r for r in read if r["gold"] == "cannot_answer" and r["tools"] == 0]
    out["hallucination"] = sum(r[f"bet_{key}"] == "tool_call" for r in base) / len(base) if base else None
    out["hallucination_n"] = len(base)
    notcall = [r for r in read if r["gold"] != "tool_call"]
    out["call_when_not"] = sum(r[f"bet_{key}"] == "tool_call" for r in notcall) / len(notcall) if notcall else None
    return out
