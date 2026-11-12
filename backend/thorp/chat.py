"""Chat with a finished Nothing up my sleeve run's latest checkpoint, shared by the CLI and the dash.

Experimental: the model is a small GPT trained on Ogden, not an instruction-tuned assistant. A run
trained on v0.1.4 has seen the ``<question>/<answer>`` pieces; a run without a chat/QA arm will
continue prose rather than answer. The answer is returned as plain text, with an audit of the
attention heads and cards that lit while it was written.
"""

from __future__ import annotations

import json
import os
import threading
import time

import numpy as np

from thorp import tokeniser as tokmod
from thorp.evaluators.samples import generate
from thorp.ledger import reader, spec_of
from thorp.models import ops
from thorp.models.backend import backend_of
from thorp.train import latest_checkpoint

_CACHE: dict[tuple[str, int | None], tuple] = {}
_CACHE_ORDER: list[tuple[str, int | None]] = []
_CACHE_MAX = 4
_LOCK = threading.RLock()

# the cards a chaining ship is read by (fleet.STARS); the known head of each is in the run's ledger
_CARD_NAMES = {
    "previous_word": "The Previous Word",
    "nevermore": "The Nevermore",
    "mover": "The Mover",
    "comparator": "The Comparator",
    "bridge": "The Bridge",
}
_CARD_HEADS = {
    "previous_word": ("stars/previous_word/best_layer", "stars/previous_word/best_head"),
    "nevermore": ("nevermore/natural_best_layer", "nevermore/natural_best_head"),
    "mover": ("stars/mover/best_layer", "stars/mover/best_head"),
    "comparator": ("stars/comparator/best_layer", "stars/comparator/best_head"),
    "bridge": ("stars/bridge/best_layer", None),
}


def _evict() -> None:
    while len(_CACHE_ORDER) > _CACHE_MAX:
        old = _CACHE_ORDER.pop(0)
        _CACHE.pop(old, None)


def load(run_name: str, step: int | None = None):
    """The run's model, tokeniser, spec and checkpoint, cached by run and step.

    A checkpoint is loaded in the shape that wrote it (ladder.repair_spec): the preset names are
    stable, their shapes are not. A torch voyage is read in the torch model, whose checkpoint has
    the same names as the MLX one."""
    key = (run_name, step)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit is not None:
            return hit
        con = reader()
        try:
            row = con.get_run_by_name(run_name, finished=True)
        finally:
            con.close()
        if not row:
            raise LookupError(f"no finished run named {run_name!r}")
        spec = spec_of(row)
        from thorp import ladder

        ladder.repair_spec(spec, row["run_id"])
        ckpt = latest_checkpoint(row["run_id"])
        if ckpt is None:
            raise LookupError(f"{run_name!r} has no checkpoint yet")
        if step is not None:
            ckpt = ckpt.parent / f"step-{step}"
            if not (ckpt / "state.json").exists():
                raise LookupError(f"no checkpoint step {step} for {run_name!r}")
        state = json.loads((ckpt / "state.json").read_text())
        tok = tokmod.load(state["tokeniser_id"])
        if backend_of(spec) == "torch":
            from thorp import train_torch

            model = train_torch.load_model(spec, tok.vocab_size, ckpt)
        else:
            import mlx.core as mx

            from thorp.train import build_model, load_master, to_compute

            model = build_model(spec, tok.vocab_size)
            model.update(to_compute(load_master(ckpt), spec["optim"].get("precision", "bf16")))
            mx.eval(model.parameters())
        got = (model, tok, spec, ckpt)
        _CACHE[key] = got
        _CACHE_ORDER.append(key)
        _evict()
        return got


# How a Nothing up my sleeve ship's answer is drawn (11 November, the talk leg): from the likeliest pieces only, and not the
# piece it has just written. A 9m sampled over its whole vocabulary wanders, and greedy it loops; the outside
# models at the same table are sampled by their own libraries' defaults (foreign_answer).
DECODING = {"top_k": 40, "top_p": 0.9, "repetition_penalty": 1.15}


def prompt_for(spec: dict, question: str, history: list[tuple[str, str]] | None = None) -> tuple[str, str]:
    """The question wrapped the way the voyage was taught: the v0.1.4 marks where it read them, else
    plain prose. With `history` (the conversation's earlier exchanges, oldest first) the question is asked
    after them, each exchange written as the voyage's turns were (12 November: the conversation leg reads
    whole conversations, and a ship asked its last line alone has lost what the line answers). Returns
    (prompt, format)."""
    q = question.strip()
    from thorp import cleaning, turns

    exchanges = [(a.strip(), b.strip()) for a, b in history or []]
    # a return leg (11 November) says which turn format it was taught: ask it exactly as its turns were written
    fmt = turns.format_of(spec)
    if fmt:
        return turns.conversation(fmt, exchanges, q, cleaning.version_of(spec)), fmt
    recipe = str((spec.get("data") or {}).get("recipe") or "")
    fmt = "marks" if "ogden-v0.1.4" in recipe or "chat" in recipe.lower() or "dialogue" in recipe.lower() else "plain"
    return turns.conversation(fmt, exchanges, q, "raw"), fmt


def exchanges_of(history: list | None) -> list[tuple[str, str]]:
    """A saved thread's messages as exchanges, oldest first: each question with the answer that followed it. A
    question left unanswered (a failed or stopped ask) is not an exchange and is left out, and so is an answer
    with no question before it; the roles are the console's (`you`, `thorp`) or a chat API's (`user`,
    `assistant`), the words in `text` or `content`."""
    out: list[tuple[str, str]] = []
    asked = None
    for h in history or []:
        role = str((h or {}).get("role") or "")
        text = str((h or {}).get("text") or (h or {}).get("content") or "").strip()
        if role in ("you", "user"):
            asked = text or None
        elif role in ("thorp", "assistant"):
            if asked and text:
                out.append((asked, text))
            asked = None
    return out


def fit_exchanges(spec: dict, tok, question: str, exchanges: list[tuple[str, str]], context: int,
                  budget: int) -> tuple[str, str, int]:
    """The prompt with the oldest exchanges dropped, whole, until it and `budget` pieces of answer fit the
    window. The writer keeps only the last `context` pieces, so an overlong prompt would otherwise lose its
    opening mid-turn. Returns (prompt, format, exchanges dropped); the question itself is always kept."""
    dropped = 0
    while True:
        prompt, fmt = prompt_for(spec, question, exchanges[dropped:])
        if dropped >= len(exchanges) or len(tok.encode(prompt)) + budget <= context:
            return prompt, fmt, dropped
        dropped += 1


# the answer's room when a conversation is fitted to the window: a Nothing up my sleeve ship's replies are a sentence or two,
# and the console asks for a share of the window that would leave no room for the thread at all
ANSWER_ROOM = 160


def _ask(
    model, tok, spec: dict, question: str, temperature: float, tokens: int, seed: int,
    exchanges: list[tuple[str, str]] | None = None,
) -> tuple[str, str, str, int]:
    """(answer, prompt, format, exchanges dropped to fit the window)."""
    prompt, fmt, dropped = fit_exchanges(
        spec, tok, question, exchanges or [], int(spec["model"]["context"]), min(tokens, ANSWER_ROOM)
    )
    key = seed if ops.is_torch(model) else _mx_key(seed)
    # a marked ship ends its own turn: stop at <end> when it is one piece, rather than write on and cut the text
    end = tok.encode("<end>") if fmt == "marks" else []
    out = generate(
        model, tok, prompt, temperature, tokens, int(spec["model"]["context"]), key,
        stop_ids=tuple(end) if len(end) == 1 else (), **DECODING,
    )  # fmt: skip
    if fmt == "marks":
        for end in ("<end>", "<sep>", "<question>"):
            out = out.split(end)[0]
    else:
        for end in ("\nQuestion:", "\nQ:", "\nq:", "<question>"):
            out = out.split(end)[0]
    return out.strip(), prompt, fmt, dropped


def abilities(spec: dict) -> dict:
    """What a ship was taught beyond reading (13 November, kipling:14): to think between <think> and <answer> (a leg's
    `thinking:` block) and to call the eight tools between <call> and <result> (a leg's `tools:` block). A ship with
    neither is asked as before."""
    syms = set((spec.get("tokeniser") or {}).get("symbols") or [])
    return {"thinking": bool(spec.get("thinking")) and "<think>" in syms,
            "tools": bool(spec.get("tools")) and "<call>" in syms}


TOOL_ROUNDS = 4  # calls a ship may make before it must answer, as the foreign ships' loop allows


def _ask_able(model, tok, spec: dict, question: str, temperature: float, tokens: int, seed: int,
              exchanges: list[tuple[str, str]], thinking: bool | None, tools: bool) -> dict:
    """A ship taught to think or to call tools, asked as its lessons were written (thorp/turns.py `thought`, `called`):
    the turn opened at `<question>Q`, then `<think>` (thinking on), `<think><answer>` (thinking off) or nothing (the ship
    chooses); with tools on, a call it writes is run at `<result>` (thorp/ship_tools.py) and the ship goes on from
    the result, up to TOOL_ROUNDS calls. Returns the answer, the thinking, the calls and the prompt."""
    from thorp import ship_tools, turns

    can = abilities(spec)
    prompt, fmt, dropped = fit_exchanges(spec, tok, question, exchanges, int(spec["model"]["context"]),
                                         min(tokens, ANSWER_ROOM) * 2)  # fmt: skip
    head = prompt[: -len("<answer>")] if prompt.endswith("<answer>") else prompt
    opened = ""
    if can["thinking"] and thinking is True:
        opened = turns.THINK
    elif can["thinking"] and thinking is False:
        opened = turns.THINK + "<answer>"
    elif can["tools"] and not tools:
        opened = "<answer>"  # tools off: the turn is opened at the answer, so no call can be written
    key = seed if ops.is_torch(model) else _mx_key(seed)
    stops = [i for m in ("<end>", turns.RESULT if (can["tools"] and tools) else None) if m
             for i in [tok.encode(m)] if len(i) == 1 for i in i]  # fmt: skip
    written, calls, left = opened, [], tokens
    for rnd in range(TOOL_ROUNDS + 1):
        out = generate(model, tok, head + written, temperature, max(8, left), int(spec["model"]["context"]), key,
                       stop_ids=tuple(stops), **DECODING)  # fmt: skip
        written += out
        left -= len(tok.encode(out))
        last = written.rsplit(turns.CALL, 1)
        pending = len(last) == 2 and not any(m in last[1] for m in ("<answer>", "<end>", turns.RESULT))
        if can["tools"] and tools and pending and rnd < TOOL_ROUNDS and left > 8:
            call = last[1].strip()
            result = ship_tools.run(call)
            parsed = ship_tools.parse(call)
            calls.append({"round": rnd + 1, "name": parsed[0] if parsed else call[:40],
                          "arguments": {"args": parsed[1]} if parsed else {"text": call},
                          "result": {"text": result}})  # fmt: skip
            written += turns.RESULT + result
            continue
        break
    reasoning = ""
    if turns.THINK in written:
        reasoning = written.split(turns.THINK, 1)[1].split("<answer>", 1)[0].strip()
    answer = written.rsplit("<answer>", 1)[1] if "<answer>" in written else written
    for end in ("<end>", "<eos>", "<question>", "<sep>"):
        answer = answer.split(end)[0]
    for m in (turns.CALL, turns.RESULT, turns.THINK):
        answer = answer.replace(m, " ")
    return {"answer": answer.strip(), "reasoning": reasoning, "calls": calls, "prompt": head + opened, "format": fmt,
            "dropped": dropped, "written": written}


def _mx_key(seed: int):
    import mlx.core as mx

    return mx.random.key(seed)


# ---------------------------------------------------------------- the audit


def _known_heads(run_id: str) -> dict[str, dict]:
    """The card heads a run's own readings name: card -> {layer, head} (the Bridge has no single head)."""
    con = reader()
    out: dict[str, dict] = {}
    try:
        for key, (ln, hn) in _CARD_HEADS.items():
            layer = con.metric_at(run_id, ln)
            if layer is None:
                continue
            got = {"layer": int(layer)}
            if hn:
                head = con.metric_at(run_id, hn)
                if head is not None:
                    got["head"] = int(head)
            out[key] = got
    finally:
        con.close()
    return out


def _held_cards(ship_key: str | None) -> dict:
    """The ship's scored cards (its sailings averaged), from the same reader the leaderboard uses."""
    if not ship_key:
        return {}
    from thorp import leaderboard

    try:
        return (leaderboard.thorp_entry(ship_key) or {}).get("cards") or {}
    except Exception:  # noqa: BLE001  a reading that cannot be averaged must not fail a chat
        return {}


def _pieces(tok, ids: list[int]) -> list[str]:
    out = []
    for i in ids:
        try:
            out.append(tok.decode([int(i)]))
        except Exception:  # noqa: BLE001
            out.append("")
    return out


def _label(pieces: list[str], i: int, n: int = 40) -> str | None:
    """A readable piece: the opening EOS is named, a space is shown as one, never an empty string."""
    if not 0 <= i < len(pieces):
        return None
    if i == 0:
        return "(the opening mark)"
    got = pieces[i][:n].replace("\n", "\\n").replace("\t", "\\t")
    return got if got.strip() else f"“{got or ' '}”"


def _role_masks(pieces: list[str], prompt_len: int) -> dict[str, np.ndarray]:
    """The keys' roles, as math_heads does it: numbers, operators, words, the question itself."""
    import re

    num = re.compile(r"^[0-9]+(\.[0-9]+)?$")
    op = re.compile(r"^[=+\-*/^<>()\[\].,]$")
    word = re.compile(r"^[A-Za-z]+$")
    n = len(pieces)
    return {
        "number": np.array([bool(num.match(p)) for p in pieces]),
        "operator": np.array([bool(op.match(p)) for p in pieces]),
        "word": np.array([bool(word.match(p)) for p in pieces]),
        "question": np.concatenate([np.ones(prompt_len, bool), np.zeros(n - prompt_len, bool)]),
    }


def _induction_targets(ids: list[int]) -> np.ndarray:
    """At each position, the position that followed the most recent earlier copy of the token, or -1."""
    last: dict[int, int] = {}
    tgt = np.full(len(ids), -1, dtype=np.int64)
    for t, x in enumerate(ids):
        j = last.get(x)
        if j is not None and j + 1 < t:
            tgt[t] = j + 1
        last[x] = t
    return tgt


def _audit(model, tok, spec: dict, run_id: str, prompt: str, text: str) -> dict:
    """Every head's attention over the answer, the star tests read on this prompt, and the cards the
    ship holds. The trace is per answer token; only the top heads and the lookups are returned."""
    from thorp import fleet

    prompt_ids = tok.encode(prompt)
    answer_ids = tok.encode(text) if text else []
    ids = [tok.eos_id] + prompt_ids + answer_ids
    prompt_len = 1 + len(prompt_ids)
    T = len(ids)
    ans = np.arange(prompt_len, T)
    if ans.size == 0:
        # an empty answer: read the last prompt position, where the first token was chosen
        ans = np.array([T - 1])
        prompt_len = max(1, T - 1)
        pred = np.array([T - 1])
    else:
        # the query that chose each answer token is the position before it: the last prompt token
        # for the first, the previous answer token after that. Its attention did the looking up.
        pred = np.maximum(ans - 1, 0)
    A = len(ans)
    has_answer = bool(answer_ids)
    pieces = _pieces(tok, ids)

    pats = [] if not hasattr(model, "attention_patterns") else ops.attention_patterns(model, [ids])
    if not pats:
        return {
            "readable": False,
            "reason": "this model's attention cannot be read",
            "heads": [],
            "selective": [],
            "stars": [],
            "cards": [],
            "lookups": [],
        }
    L, H = len(pats), int(pats[0].shape[1])

    # per-head readings, (layers, heads)
    prev = np.zeros((L, H), np.float32)
    off2 = np.zeros((L, H), np.float32)
    sink = np.zeros((L, H), np.float32)
    conc = np.zeros((L, H), np.float32)
    peak_w = np.zeros((L, H), np.float32)
    aimed = np.zeros((L, H), np.int32)
    aimed_w = np.zeros((L, H), np.float32)
    dup = np.zeros((L, H), np.float32)
    indu = np.zeros((L, H), np.float32)
    delim = np.zeros((L, H), np.float32)
    routes: dict[str, np.ndarray] = {
        k: np.zeros((L, H), np.float32) for k in ("number", "operator", "word", "question")
    }

    from thorp.evaluators.stars import delimiters

    dl = delimiters(tok)[ids]
    dl[0] = False
    tgt = _induction_targets(ids)
    last: dict[int, int] = {}
    dup_at = np.full(T, -1, dtype=np.int64)
    for i, x in enumerate(ids):
        dup_at[i] = last.get(x, -1)
        last[x] = i
    roles = _role_masks(pieces, prompt_len)
    shares = {k: max(float(v.sum()) / T, 1e-9) for k, v in roles.items()}
    even = 1.0 / (pred + 1.0)

    for li, p in enumerate(pats):
        w = p[0]  # (heads, T, T)
        wa = w[:, pred, :]  # (heads, A, T): the lookups that chose the answer tokens
        peaks = wa.max(-1)  # (heads, A)
        conc[li] = (peaks - even[None, :]).mean(-1)
        peak_w[li] = peaks.mean(-1)
        mean_attn = wa.mean(1)  # (heads, T): where the answer looked, on average
        aimed[li] = mean_attn.argmax(-1)
        aimed_w[li] = mean_attn.max(-1)
        sink[li] = mean_attn[:, 0]
        prev[li] = wa[:, np.arange(A), np.maximum(pred - 1, 0)].mean(-1)
        off2[li] = wa[:, np.arange(A), np.maximum(pred - 2, 0)].mean(-1)
        good = np.array([j for j, a in enumerate(ans) if 0 <= dup_at[a] <= pred[j]], dtype=np.int64)
        if good.size:
            dup[li] = wa[:, good, dup_at[ans][good]].mean(-1)
        good = np.array([j for j, a in enumerate(ans) if 0 <= tgt[a] <= pred[j]], dtype=np.int64)
        if good.size:
            indu[li] = wa[:, good, tgt[ans][good]].mean(-1)
        if dl.any():
            causal = np.tril(np.ones((T, T), bool), k=-1)
            share = (dl[None, :] & causal).sum(-1) / np.maximum(causal.sum(-1), 1)  # (T,)
            ok = share[pred] > 0
            if ok.any():
                mass = (wa * dl[None, None, :]).sum(-1)  # (heads, A)
                delim[li] = (mass[:, ok] / share[pred][ok][None, :]).mean(-1)
        for k, m in roles.items():
            routes[k][li] = (wa @ m.astype(np.float32)).mean(-1) / shares[k]

    # the stars a head can be read on this prompt (fleet.STARS names them); the cards without a
    # live test here (mover, comparator, bridge) are read on their own decks, not on a chat prompt
    thresholds = {
        "previous_word": float(fleet.STARS["previous_word"].threshold),
        "offset_2": float(fleet.STARS["offset_2"].threshold),
        "attention_sink": float(fleet.STARS["attention_sink"].threshold),
        "duplicate_word": float(fleet.STARS["duplicate_word"].threshold),
        "nevermore": float(fleet.STARS["nevermore"].threshold),
        "delimiter": float(fleet.STARS["delimiter"].threshold),
    }
    mats = {
        "previous_word": prev,
        "offset_2": off2,
        "attention_sink": sink,
        "duplicate_word": dup,
        "nevermore": indu,
        "delimiter": delim,
    }

    def best(mat: np.ndarray) -> tuple[float, int, int]:
        li, hi = np.unravel_index(int(mat.argmax()), mat.shape)
        return float(mat[li, hi]), int(li), int(hi)

    stars = []
    for key, mat in mats.items():
        score, li, hi = best(mat)
        mark = thresholds[key]
        stars.append(
            {
                "key": key,
                "name": fleet.STARS[key].name,
                "score": round(score, 4),
                "mark": mark,
                "lit": bool(score >= mark),
                "head": f"L{li:02d}.H{hi:02d}",
                "layer": li,
                "head_no": hi,
            }
        )
    stars.sort(key=lambda d: -d["score"])

    known = _known_heads(run_id)
    head_to_card = {
        (v["layer"], v.get("head")): k for k, v in known.items() if v.get("head") is not None
    }

    # the strongest reading per head, over the star tests that fit a prompt
    rows = []
    for li in range(L):
        for hi in range(H):
            star_scores = {k: float(m[li, hi]) for k, m in mats.items()}
            lit = [k for k, v in star_scores.items() if v >= thresholds[k]]
            # the strongest reading relative to its own mark: the delimiter's multiple (1 means
            # indifferent) and the previous-word share are different scales
            star = max(lit, key=lambda k: star_scores[k] / thresholds[k]) if lit else None
            fired = {
                k: v
                for k, v in star_scores.items()
                if k
                in ("previous_word", "offset_2", "attention_sink", "duplicate_word", "nevermore")
                and v >= thresholds[k]
            }
            trigger = max(float(conc[li, hi]), *(fired.values() if fired else [0.0]))
            route_key = max(routes, key=lambda k: routes[k][li, hi])
            rows.append(
                {
                    "layer": li,
                    "head": hi,
                    "trigger": round(trigger, 4),
                    "concentration": round(float(conc[li, hi]), 4),
                    "peak_weight": round(float(peak_w[li, hi]), 4),
                    "aimed_at": _label(pieces, int(aimed[li, hi])),
                    "aimed_weight": round(float(aimed_w[li, hi]), 4),
                    "sink": round(float(sink[li, hi]), 4),
                    "previous": round(float(prev[li, hi]), 4),
                    "offset2": round(float(off2[li, hi]), 4),
                    "induction": round(float(indu[li, hi]), 4),
                    "duplicate": round(float(dup[li, hi]), 4),
                    "delimiter": round(float(delim[li, hi]), 4),
                    "route": route_key,
                    "route_multiple": round(float(routes[route_key][li, hi]), 3),
                    "star": star,
                    "card": head_to_card.get((li, hi)),
                }
            )
    rows.sort(key=lambda d: -d["trigger"])
    heads = rows[:12]
    # the sink heads park on the opening mark when they have nothing to read; the content-aimed
    # list is the same ranking without them (the Tests tab reads an outside model the same way)
    selective = [d for d in rows if d["sink"] < 0.5][:12]

    # what each answer token looked up: the head and the question-side token it read hardest
    lookups = []
    prompt_part = np.arange(prompt_len)
    if has_answer and prompt_part.size:
        per_head = np.stack([p[0][:, pred, :prompt_len].max(-1) for p in pats])  # (L, H, A)
        winner = per_head.reshape(L * H, A).argmax(0)
        for j, a in enumerate(ans[:16]):
            li, hi = divmod(int(winner[j]), H)
            key = int(pats[li][0, hi, pred[j], :prompt_len].argmax())
            lookups.append(
                {
                    "answer_index": int(j),
                    "token": pieces[int(a)][:40],
                    "layer": li,
                    "head": hi,
                    "weight": round(float(pats[li][0, hi, pred[j], key]), 4),
                    "looked_at": _label(pieces, key, 60),
                    "looked_at_index": key,
                }
            )

    # the cards the ship holds, beside what lit on this answer
    ship_key = None
    try:
        ship_key = fleet.ship_key(spec)
    except Exception:  # noqa: BLE001
        pass
    held = _held_cards(ship_key)
    cards = []
    for key in ("previous_word", "nevermore", "mover", "comparator", "bridge"):
        star = next((s for s in stars if s["key"] == key), None)
        h = known.get(key) or {}
        scored = held.get(key) or {}
        cards.append(
            {
                "key": key,
                "name": _CARD_NAMES[key],
                "held": bool(scored.get("lit") or scored.get("lit_shared")) if scored else None,
                "held_score": round(float(scored.get("max")), 4)
                if scored.get("max") is not None
                else None,
                "held_shared": round(float(scored.get("shared")), 4)
                if scored.get("shared") is not None
                else None,
                "mark": float(fleet.STARS[key].threshold),
                "head": f"L{h['layer']:02d}.H{h['head']:02d}"
                if h.get("head") is not None
                else None,
                "live": bool(star["lit"]) if star else None,
                "live_score": star["score"] if star else None,
                "live_head": star["head"] if star else None,
                "note": (
                    f"read on this answer: {star['score']:.3f} against {star['mark']}"
                    if star
                    else "read on its own deck, not on a chat prompt"
                ),
            }
        )

    return {
        "readable": True,
        "layers": L,
        "heads_count": H,
        "prompt_tokens": prompt_len,
        "answer_tokens": len(answer_ids),
        "answer_positions": A,
        "heads": heads,
        "selective": selective,
        "stars": stars,
        "cards": cards,
        "lookups": lookups,
    }


def audit(run_name: str, prompt: str, text: str, step: int | None = None) -> dict:
    """The audit of one answer (loaded through the same cache as the answer)."""
    model, tok, spec, ckpt = load(run_name, step)
    return _audit(model, tok, spec, ckpt.parent.name, prompt, text)


def answer(
    run_name: str,
    question: str,
    *,
    tokens: int = 80,
    temperature: float = 0.7,
    seed: int = 0,
    step: int | None = None,
    with_audit: bool = True,
    thinking: bool | None = None,
    history: list | None = None,
    tools: bool | None = None,
) -> dict:
    """One answer from the run's latest checkpoint (or `step`), with the heads and cards audit. `history` is
    the thread so far (the console's messages): its exchanges are written before the question as the voyage's
    turns were, the oldest dropped whole when they no longer fit the window. A ship taught to think or to call tools
    (`abilities`) is asked with them: `thinking` on, off or None (the ship chooses), `tools` on unless False."""
    exchanges = exchanges_of(history)
    with _LOCK:
        model, tok, spec, ckpt = load(run_name, step)
        started = time.perf_counter()
        can = abilities(spec)
        reasoning, calls_log, state = "", [], "none"
        if can["thinking"] or can["tools"]:
            r = _ask_able(model, tok, spec, question, temperature, tokens, seed, exchanges, thinking,
                          bool(tools) if tools is not None else True)  # fmt: skip
            text, prompt, fmt, dropped = r["answer"], r["prompt"], r["format"], r["dropped"]
            reasoning, calls_log = r["reasoning"], r["calls"]
            state = ("on" if thinking else "off" if thinking is False else "auto") if can["thinking"] else "none"
        else:
            text, prompt, fmt, dropped = _ask(model, tok, spec, question, temperature, tokens, seed, exchanges)
        seconds = time.perf_counter() - started
        prompt_tokens = _own_tokens(tok, prompt)
        answer_tokens = _own_tokens(tok, text)
        out = {
            "run": run_name,
            "step": ckpt.name,
            "prompt": prompt,
            "format": fmt,
            "answer": text,
            "reasoning": reasoning,
            "thinking": state,
            "meta": {
                "settings": {"temperature": temperature, "max_tokens": tokens, "thinking": state,
                             "tools": bool(can["tools"] and tools is not False), **DECODING},
                "tool_calls": calls_log,
                "prompt_tokens": prompt_tokens,
                "answer_tokens": answer_tokens,
                "reasoning_tokens": _own_tokens(tok, reasoning) if reasoning else 0,
                "exchanges": len(exchanges) - dropped,
                "exchanges_dropped": dropped,
                "seconds": round(seconds, 2),
                "tok_s": round(answer_tokens / seconds, 1) if seconds > 0 else None,
                "finish": "length" if answer_tokens >= tokens else "stop",
                "rendered": prompt,
            },
        }
        if with_audit:
            try:
                out["audit"] = _audit(model, tok, spec, ckpt.parent.name, prompt, text)
            except Exception as e:  # noqa: BLE001  the answer stands; say why the audit could not be read
                out["audit"] = {"readable": False, "reason": str(e)}
        return out


def _cache_file(model_id: str, name: str) -> str | None:
    """A file of a cached model (its chat template or config), or None when the hub cannot say.
    A model converted on this Mac is a directory, not a Hub repo: read it in place."""
    if os.path.isdir(model_id):
        p = os.path.join(model_id, name)
        return p if os.path.exists(p) else None
    try:
        from huggingface_hub import try_to_load_from_cache

        p = try_to_load_from_cache(model_id, name)
        if isinstance(p, str) and os.path.exists(p):
            return p
    except Exception:  # noqa: BLE001  no hub, no cache
        pass
    return None


def _template_text(model_id: str) -> str:
    p = _cache_file(model_id, "chat_template.jinja") or _cache_file(model_id, "tokenizer_config.json")
    if not p:
        return ""
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def tools_support(model_id: str) -> dict:
    """Whether the console can hand an outside model tools (thorp/chat_tools.py, 12 November): its chat
    template must take them in a grammar the console reads. `format` is that grammar or None; a base
    checkpoint whose template takes tools gets them, but is said not to have been trained to use them."""
    from thorp import chat_tools, foreign

    out = chat_tools.tool_format(_template_text(model_id))
    if out["format"] and foreign.tuning(model_id) == "base":
        out = {**out, "why": out["why"] + "; a base checkpoint, not trained to call them"}
    return out


def thinking_support(model_id: str) -> dict:
    """Whether an outside model can think, and whether the thinking can be turned off: the chat
    template's `enable_thinking` is a toggle; a template that reasons without one is automatic; a
    template with neither has no reasoning mode."""
    text = _template_text(model_id)
    low = text.lower()
    if "enable_thinking" in text:
        return {"mode": "toggle", "default": True, "why": "the chat template takes enable_thinking"}
    if any(k in low for k in ("thinking", "reasoning", "think")):
        return {"mode": "auto", "default": True, "why": "the chat template always reasons and has no off switch"}
    return {"mode": "none", "default": False, "why": "the chat template has no reasoning mode"}


def _tuning(model_id: str) -> str:
    """Whether the weights are instruction-tuned or a base checkpoint: a chat template in the
    tokeniser is not enough — a 270M base Gemma has one and still only continues text."""
    name = model_id.lower()
    if "-it" in name or "instruct" in name or "-chat" in name:
        return "instruct"
    if "base" in name or "-pt" in name or "pretrain" in name or "pythia" in name:
        return "base"
    if "qwen" in name or "phi-4" in name:
        return "instruct"  # Qwen and Phi-4 publish the instruct model under the plain name
    if any(k in name for k in ("gemma", "llama", "smollm", "phi-2")):
        return "base"
    return "unknown"


def _context(model_id: str) -> int | None:
    p = _cache_file(model_id, "config.json")
    if not p:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        for k in ("max_position_embeddings", "text_config", "n_positions"):
            v = cfg.get(k)
            if isinstance(v, dict):
                v = v.get("max_position_embeddings")
            if isinstance(v, (int, float)):
                return int(v)
    except (OSError, ValueError):
        pass
    return None


def _quant(model_id: str) -> str:
    name = model_id.lower()
    for q in ("mxfp4", "4bit", "8bit", "6bit", "5bit", "bf16", "fp16"):
        if q in name:
            return q
    return "–"


def _own_tokens(tok, text: str) -> int:
    try:
        return len(tok.encode(text, add_special_tokens=False))
    except TypeError:  # our own tokeniser takes no such switch and adds nothing: every Nothing up my sleeve answer counted 0
        try:
            return len(tok.encode(text))
        except Exception:  # noqa: BLE001
            return 0
    except Exception:  # noqa: BLE001  a tokeniser that cannot count must not fail an answer
        return 0


_THINK_CLOSES = ("</think>", "<|end_of_thought|>", "<channel|>")


def answer_left_in_thinking(text: str, reasoning: str, reply: str, thinking: str, model_ended: bool) -> bool:
    """Whether a turn's thinking is really its answer: thinking was on, the model ended the turn itself,
    the thinking was never closed and nothing came after it. A turn cut off by the budget is not one."""
    return bool(
        not reply
        and reasoning
        and thinking in ("on", "auto")
        and model_ended
        and not any(mk in text for mk in _THINK_CLOSES)
    )


def _split_reasoning(text: str, thinking: str) -> tuple[str, str]:
    """(reasoning, answer) from a continuation: the trace is what came before the closing think
    marker; with no marker and thinking on, the whole continuation is still reasoning."""
    for marker in _THINK_CLOSES:
        if marker in text:
            head, _, tail = text.rpartition(marker)
            return head.strip(), tail.strip()
    if thinking in ("on", "auto"):
        return text.strip(), ""
    return "", text.strip()


def _facts(spec: dict, step: str | None = None) -> dict:
    """The parameters the chat's sidebar reads: the shape, the tokeniser, and whether its control
    tokens are in the embedding table. A declared control token is a single piece of the tokeniser's
    vocabulary, and the embedding table is one row a piece, so declared means in the embeddings; a
    corpus with no `symbols` (Ogden v0.1/v0.2) has none at all."""
    from thorp import turns
    from thorp.models import registry

    tok = spec.get("tokeniser") or {}
    model = spec.get("model") or {}
    preset = model.get("preset")
    shape = registry.PRESETS.get(str(preset)) or {}
    symbols = [str(x) for x in (tok.get("symbols") or [])]
    return {
        "preset": preset,
        "family": model.get("family"),
        "layers": shape.get("layers"),
        "width": shape.get("width"),
        "heads": shape.get("heads"),
        "context": model.get("context"),
        "positions": model.get("positions"),
        "backend": model.get("backend") or "mlx",
        "precision": (spec.get("optim") or {}).get("precision"),
        "vocab": tok.get("vocab"),
        "tokeniser": tok.get("kind"),
        "byte_fallback": tok.get("byte_fallback"),
        "train_on": tok.get("train_on"),
        "control_tokens": symbols,
        "control_in_embeddings": bool(symbols),
        "turns": turns.format_of(spec),
        "tuning": "base",
        "thinking": ({"mode": "toggle", "default": True, "why": "taught to think between <think> and <answer>, or to answer at once (the reasoning leg)"}
                     if spec.get("thinking") and "<think>" in symbols
                     else {"mode": "none", "default": False, "why": "a Nothing up my sleeve GPT has no reasoning mode unless a reasoning leg taught it one"}),
        "tools": ({"format": "marks", "why": "taught to call " + ", ".join((spec.get("tools") or {}).get("set") or []) + " (the tool leg)"}
                  if spec.get("tools") and "<call>" in symbols
                  else {"format": None, "why": "this ship was not taught tools"}),
        "recipe": (spec.get("data") or {}).get("recipe"),
        "passes": (spec.get("data") or {}).get("passes"),
        "clean": (spec.get("data") or {}).get("clean"),
        "sop": spec.get("sop"),
        "step": step,
    }


def models(leaderboard: dict | None = None) -> list[dict]:
    """The Nothing up my sleeve ships on the leaderboard, each resolved to a finished run with a
    checkpoint. The chat page lists these, so the list follows the leaderboard, not a hand-kept pair."""
    if leaderboard is None:
        from thorp import leaderboard as lbmod

        leaderboard = lbmod.payload()
    ships = {s.get("ship_key"): s for s in leaderboard.get("ships", [])}
    con = reader()
    out = []
    try:
        for row in leaderboard.get("table", []):
            if row.get("kind") != "thorp":
                continue
            key = row.get("ship_key")
            sh = ships.get(key) or {}
            names: list[str] = []
            for n in [sh.get("run"), *(sh.get("runs") or [])]:
                if n and n not in names:
                    names.append(n)
            chosen = None
            facts = None
            for n in names:
                r = con.get_run_by_name(n, finished=True)
                if not r:
                    continue
                ck = latest_checkpoint(r["run_id"])
                if ck is None:
                    continue
                chosen = {"run": n, "run_id": r["run_id"], "step": ck.name}
                facts = _facts(spec_of(r), ck.name)
                break
            out.append(
                {
                    "kind": "thorp",
                    "ship_key": key,
                    "name": row.get("name"),
                    "params": row.get("params"),
                    "cards_held": row.get("cards_held"),
                    "cards": row.get("cards"),
                    "available": chosen is not None,
                    "run": chosen,
                    "runs": names,
                    "facts": facts,
                    "why": None if chosen else "no finished run with a checkpoint",
                }
            )
    finally:
        con.close()
    return out


TALK_LAB = "Demiton"
TALK_PREFIX = "9m@v0.0.6-"  # the 9m's legs: -talk, -talk-hot, -return, each seeded from the finished 9m@v0.0.6


def talking_models() -> list[dict]:
    """The 9m legs that were taught to answer (12 November, Justin: "for the 9m I'd like to be able to talk to it
    via the chat terminal; the lab should be Demiton, and then I should be able to select the model"): each
    finished leg of the 9m that reads turns, with every checkpoint it kept and what its reading was there, so the
    ship we talk to is picked by its best reading and not only its last step. A base checkpoint continues prose
    instead of answering, so only a leg that read turns is listed. `step` goes back to /api/chat as it is."""
    from thorp import turns

    con = reader()
    out: list[dict] = []
    try:
        names = [
            r["name"]
            for r in con.query(
                "select distinct name from runs where status='finished' and name like ? order by name",
                (TALK_PREFIX + "%",),
            )
        ]
        for name in names:
            r = con.get_run_by_name(name, finished=True)
            if not r:
                continue
            spec = spec_of(r)
            if not turns.format_of(spec):
                continue
            ck = latest_checkpoint(r["run_id"])
            if ck is None:
                continue
            steps = sorted(
                int(p.name[5:])
                for p in ck.parent.glob("step-*")
                if p.name[5:].isdigit() and (p / "state.json").exists()
            )
            read: dict[int, dict] = {}
            for m in con.query(
                "select step, name, value from metrics where run_id=? and name in (?, ?)",
                (r["run_id"], "answers/bpb", "answers/stopped"),
            ):
                read.setdefault(int(m["step"]), {})["bpb" if m["name"] == "answers/bpb" else "stopped"] = m["value"]
            leg = name[len(TALK_PREFIX):]
            lr = (spec.get("optim") or {}).get("lr")
            facts = _facts(spec, ck.name)
            facts["tuning"] = "talk"
            out.append(
                {
                    "kind": "thorp",
                    "talks": True,
                    "lab": TALK_LAB,
                    "ship_key": f"run:{name}",
                    "name": f"Nothing up my sleeve 9m · {leg}" + (f" (lr {lr:g})" if lr else ""),
                    "params": None,
                    "available": True,
                    "run": {"run": name, "run_id": r["run_id"], "step": ck.name},
                    "runs": [name],
                    "facts": facts,
                    "checkpoints": [
                        {"step": s, "bpb": (read.get(s) or {}).get("bpb"), "stopped": (read.get(s) or {}).get("stopped")}
                        for s in steps
                    ],
                    "why": None,
                }
            )
    finally:
        con.close()
    return out


# ---- the foreign ships (11 November, Justin: "chat has to appear on both Nothing up my sleeve's
# ships as well as foreign ships"): an outside model's own continuation, from the MLX weights when
# they are in the cache. No audit: the heads/cards trace is Nothing up my sleeve's own GPT.
_FOREIGN: dict[str, tuple] = {}
_FOREIGN_MAX = 2

# The prompt cache (11 November): each loaded foreign model keeps the KV state of its last few
# conversations, keyed by their tokens, so a follow-up only evaluates the turns that are new rather than
# re-reading the whole thread from the first token. One cache a model, dropped with the model's weights.
_KV: dict[str, object] = {}
_KV_THREADS = 4  # conversations kept a model
_KV_BYTES = 1 << 30  # and at most 1 GiB of KV state a model


def _kv_for(key: str):
    from mlx_lm.models.cache import LRUPromptCache

    got = _KV.get(key)
    if got is None:
        _KV[key] = got = LRUPromptCache(max_size=_KV_THREADS, max_bytes=_KV_BYTES)
    return got


def _encode_prompt(tok, prompt: str) -> list[int]:
    """The prompt's ids as mlx_lm's own stream_generate encodes a string: the BOS added unless the
    rendered template already starts with it, so a cached prefix matches what generation would read."""
    bos = getattr(tok, "bos_token", None)
    return list(tok.encode(prompt, add_special_tokens=bos is None or not prompt.startswith(bos)))


def _fit_history(msgs: list[dict], render, count, context: int | None, budget: int) -> tuple[str, int]:
    """The rendered prompt, with the oldest turns dropped until it and the answer budget fit the
    model's window. Returns (prompt, turns dropped). The newest user turn is always kept."""
    dropped = 0
    prompt = render(msgs)
    if not context:
        return prompt, 0
    while len(msgs) > 1 and count(prompt) + budget > context:
        # drop a whole exchange (user and its answer) so the thread still alternates
        cut = 2 if len(msgs) > 2 and msgs[1]["role"] == "assistant" else 1
        msgs = msgs[cut:]
        dropped += cut
        prompt = render(msgs)
    return prompt, dropped


def _cached(model_id: str) -> bool:
    """Whether the outside model's weights are on this disk: a converted model in data/models, or a
    config in the Hugging Face cache with its weights beside it."""
    if os.path.isdir(model_id):
        return os.path.exists(os.path.join(model_id, "config.json")) and any(
            n.endswith(".safetensors") for n in os.listdir(model_id)
        )
    try:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(model_id, "config.json"), str)
    except Exception:  # noqa: BLE001  no hub, no cache: the chat page says why
        return False


def foreign_models() -> list[dict]:
    """The foreign ships that can be chatted with: an outside model with its MLX weights cached. The
    registry is thorp.foreign.models(); the same key the Harbour's page uses."""
    from thorp import foreign

    out = []
    for m in foreign.chat_targets():
        cached = _cached(m["model"])
        out.append(
            {
                "kind": "foreign",
                "model": m["key"],
                "ship_key": "foreign:" + m["key"],
                "name": m["label"],
                "params": m["params"],
                "cards_held": None,
                "cards": None,
                "available": cached,
                "run": None,
                "runs": [],
                "facts": {
                    "repo": m["model"],
                    "params": m["params"],
                    "context": _context(m["model"]),
                    "quant": _quant(m["model"]),
                    "chat_template": bool(_template_text(m["model"])),
                    "tuning": foreign.tuning(m["model"]),
                    "thinking": thinking_support(m["model"]),
                    "tools": tools_support(m["model"]),
                },
                "why": None if cached else "its weights are not in the MLX cache yet",
            }
        )
    return out


# The thinking marks an outside model's template may use: (the opening mark, the closing mark).
_THINK_MARKS = (
    ("<think>", "</think>"),
    ("<|begin_of_thought|>", "<|end_of_thought|>"),
    ("<|channel>", "<channel|>"),
)
# A turn's own end, as text: a finished turn stops there rather than running on to the token cap.
_TURN_ENDS = ("<|im_end|>", "<|endoftext|>", "<end_of_turn>", "<|eot_id|>", "<|end|>", "</s>")


def think_cap(tokens: int, think_tokens: int | None) -> int | None:
    """The thinking's own cap (11 November, Justin: "let's cap thinking separately"): the most tokens
    the reasoning may take before it is closed and the answer begins. It is never more than half the
    whole budget, so an answer always has room. None is no cap: the reasoning and the answer share
    the budget as they fall."""
    if think_tokens is None or int(think_tokens) <= 0 or tokens < 2:
        return None
    return max(1, min(int(think_tokens), tokens // 2))


def _think_marks(model_id: str, tok) -> tuple[str, str, list[int]] | None:
    """(opening mark, closing mark, the closing mark's ids) for a model, from its own template; None
    when the model's closing mark cannot be told, so its thinking cannot be closed for it."""
    text = _template_text(model_id)
    for opening, closing in _THINK_MARKS:
        if closing in text:
            # a thinking cut mid-line carries on as if nothing closed: the blank line the template
            # itself puts after the mark is written with it, so the answer starts as an answer
            written = closing + "\n\n" if closing == "</think>" else closing
            try:
                ids = list(tok.encode(written, add_special_tokens=False))
            except Exception:  # noqa: BLE001
                return None
            return (opening, closing, ids) if ids else None
    try:  # a template that does not spell its mark: only a mark that is one token of its own is safe
        ids = list(tok.encode("</think>", add_special_tokens=False))
    except Exception:  # noqa: BLE001
        return None
    return ("<think>", "</think>", ids) if len(ids) == 1 else None


class _ThinkCap:
    """Closes the thinking at its cap. A logits processor (mlx_lm calls it once a generated token,
    with every token so far): at the cap it looks once at what was written, and if the thinking is
    open and not yet closed it leaves the closing mark as the only token that can be sampled. The
    model then writes its answer in the rest of the budget."""

    def __init__(self, decode, cap: int, opening: str, closing: str, close_ids: list[int], opened: bool):
        self.decode = decode
        self.cap = cap
        self.opening = opening
        self.closing = closing
        self.close_ids = list(close_ids)
        self.opened = opened  # the template itself opened the thinking (the prompt ends on the mark)
        self.n = 0
        self.checked = False
        self.pending: list[int] = []
        self.forced = False

    def __call__(self, tokens, logits):
        k = self.n  # how many tokens were generated before this one
        self.n += 1
        if self.pending:
            return self._only(logits, self.pending.pop(0))
        if self.checked or k < self.cap:
            return logits
        self.checked = True
        text = self.decode(tokens.tolist()[-k:]) if k else ""
        if not (self.opened or self.opening in text) or self.closing in text:
            return logits  # it never thought, or closed its thinking itself
        self.forced = True
        self.pending = list(self.close_ids)
        return self._only(logits, self.pending.pop(0))

    @staticmethod
    def _only(logits, token: int):
        import mlx.core as mx

        return mx.where(mx.arange(logits.shape[-1]) == token, logits, float("-inf"))


def _held_back(text: str, marks: tuple[str, ...]) -> int:
    """How many of the text's last characters could be the start of a mark still arriving."""
    best = 0
    for m in marks:
        for n in range(min(len(m) - 1, len(text)), best, -1):
            if text.endswith(m[:n]):
                best = n
                break
    return best


class _Live:
    """The continuation as it arrives, told apart for the reader: the reasoning before the closing
    mark, the answer after it, and nothing past the turn's own end. A mark split across two pieces is
    held back until it is whole, so half a mark is never shown. The finished reply is still split
    once from the whole text (_split_reasoning); this is only what is shown while it is written."""

    def __init__(self, thinking: bool):
        self.thinking = thinking
        self.held = ""
        self.fresh = False  # the answer has just begun: its leading blank lines are not shown
        self.ended = False

    def _emit(self, out: list[tuple[str, str]], text: str) -> None:
        kind = "reasoning" if self.thinking else "answer"
        if kind == "answer" and self.fresh:
            text = text.lstrip()
            self.fresh = not text
        if text:
            out.append((kind, text))

    def feed(self, piece: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if self.ended:
            return out
        self.held += piece
        closes = tuple(c for _, c in _THINK_MARKS)
        while True:
            marks = (closes if self.thinking else ()) + _TURN_ENDS
            hits = [(self.held.find(m), m) for m in marks if m in self.held]
            if not hits:
                break
            at, mark = min(hits)
            self._emit(out, self.held[:at])
            self.held = self.held[at + len(mark) :]
            if mark in _TURN_ENDS:
                self.ended, self.held = True, ""
                return out
            self.thinking, self.fresh = False, True
        keep = _held_back(self.held, marks)
        self._emit(out, self.held[: len(self.held) - keep])
        self.held = self.held[len(self.held) - keep :]
        return out

    def flush(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        if not self.ended and self.held:
            self._emit(out, self.held)
        self.held = ""
        return out


# the most rounds of tool calls in one answer: a model that keeps calling is stopped and says so
TOOL_ROUNDS = 4


def foreign_stream(
    key: str,
    question: str,
    *,
    tokens: int = 80,
    temperature: float = 0.7,
    thinking: bool | None = None,
    history: list | None = None,
    think_tokens: int | None = None,
    tools: bool = False,
):
    """One answer from a foreign ship's own MLX weights, as it is written (11 November, Justin:
    "stream the tokens"): the model's continuation, not a Nothing up my sleeve checkpoint. A generator of events:

      {"event": "start", ...}                          once the prompt is rendered and matched
      {"event": "delta", "kind": "reasoning" | "answer", "text": ..., "n": tokens so far}
      {"event": "tool", "name", "arguments", "result", "round"}   one a tool call, when tools are on
      {"event": "done", "reply": {...}}                the same reply foreign_answer returns

    With `tools`, a model whose template takes them is handed thorp/chat_tools.SCHEMAS; each call it
    writes is run and its result read back as a tool turn, up to TOOL_ROUNDS rounds, and a new "start"
    opens each round. The reply's meta lists every call and result.

    The weights load once per model (cached, two at a time); a model not in the cache says so. The
    reply has no audit: the heads/cards trace (thorp.chat._audit) is our GPT's. Closing the generator
    early (the reader stopped it) ends the generation and keeps what was read in the KV cache."""
    from thorp import foreign

    m = foreign.get_any(key)
    if m is None:
        raise LookupError(f"no foreign ship {key!r}")
    from mlx_lm import load, stream_generate
    from mlx_lm.models.cache import can_trim_prompt_cache, make_prompt_cache, trim_prompt_cache
    from mlx_lm.sample_utils import make_sampler

    with _LOCK:
        hit = _FOREIGN.get(key)
        if hit is None:
            model, tok = load(m["model"])
            _FOREIGN[key] = hit = (model, tok)
            while len(_FOREIGN) > _FOREIGN_MAX:
                gone = next(iter(_FOREIGN))
                _FOREIGN.pop(gone)
                _KV.pop(gone, None)  # its KV state is no use without its weights
        model, tok = hit
    support = thinking_support(m["model"])
    state, kwargs = "none", {}
    if support["mode"] == "toggle":
        want = support["default"] if thinking is None else bool(thinking)
        state = "on" if want else "off"
        kwargs = {"enable_thinking": want}
    elif support["mode"] == "auto":
        state = "auto"
    # tools (thorp/chat_tools.py, 12 November): handed to a template that reads them in a grammar the
    # console parses; anything else is asked as before, and says why in the reply
    from thorp import chat_tools

    tool_info = tools_support(m["model"]) if tools else {"format": None, "why": "tools off"}
    fmt = tool_info["format"]
    extra = {tool_info.get("arg") or "tools": chat_tools.SCHEMAS} if fmt else {}
    # the conversation so far, for a continuation: the model is asked with its own turns, so a second
    # message can pick up where the first stopped instead of starting again
    msgs = []
    for h in history or []:
        role = str(h.get("role") or "")
        text = str(h.get("text") or h.get("content") or "")
        if text and role in ("you", "user", "thorp", "assistant"):
            msgs.append({"role": "user" if role in ("you", "user") else "assistant", "content": text})
    msgs.append({"role": "user", "content": question})
    try:  # an instruct model's own template; a base model continues the raw prompt
        tok.apply_chat_template(msgs[-1:], add_generation_prompt=True, tokenize=False, **kwargs, **extra)
        render = lambda ms: tok.apply_chat_template(ms, add_generation_prompt=True, tokenize=False, **kwargs, **extra)  # noqa: E731
    except TypeError:  # a template that takes no thinking switch: ask it the old way
        render = lambda ms: tok.apply_chat_template(ms, add_generation_prompt=True, tokenize=False, **extra)  # noqa: E731
        state = "auto" if support["mode"] != "none" else "none"
    except Exception:  # noqa: BLE001  no template: the raw prompt
        render = lambda ms: question  # noqa: E731
        state = "none"
        fmt = None
    calls_log: list[dict] = []
    reasonings: list[str] = []
    answered_in_thinking = False
    seconds_all, total_tokens_all = 0.0, 0
    first_cached, first_pct, first_ids = None, None, None
    for rnd in range(TOOL_ROUNDS + 1):
        # the whole thread comes in; the oldest turns go only when the thread no longer fits the window
        prompt, dropped = _fit_history(msgs, render, lambda p: len(_encode_prompt(tok, p)), _context(m["model"]), tokens)
        ids = _encode_prompt(tok, prompt)
        # the thinking's own cap: closed for the model when it is still open at the cap (think_cap)
        cap = think_cap(tokens, think_tokens) if state in ("on", "auto") else None
        capper = None
        if cap is not None:
            marks = _think_marks(m["model"], tok)
            if marks is not None:
                opening, closing, close_ids = marks
                capper = _ThinkCap(tok.decode, cap, opening, closing, close_ids, prompt.rstrip().endswith(opening))
            else:
                cap = None  # no mark to close it with: said in the reply rather than pretended
        live = _Live(state in ("on", "auto"))
        shown = _CallHider() if fmt else None
        pieces: list[str] = []
        finish = None
        with _LOCK:  # one generation at a time: the KV cache, like the GPU, is shared
            kv = _kv_for(key)
            cache, rest = kv.fetch_nearest_cache(key, ids)
            if cache is None:
                cache, rest = make_prompt_cache(model), ids
            elif not rest:
                # the very same prompt again: re-read its last token so there are logits to sample from
                if can_trim_prompt_cache(cache):
                    trim_prompt_cache(cache, 1)
                    rest = ids[-1:]
                else:
                    cache, rest = make_prompt_cache(model), ids
            cached_tokens = len(ids) - len(rest)
            cache_pct = round(100 * cached_tokens / len(ids)) if ids else 0
            if rnd == 0:
                first_cached, first_pct, first_ids = cached_tokens, cache_pct, len(ids)
            yield {
                "event": "start",
                "model": key,
                "thinking": state,
                "prompt_tokens": len(ids),
                "cached_tokens": cached_tokens,
                "cache_pct": cache_pct,
                "max_tokens": tokens,
                "think_tokens": cap,
                "round": rnd,
                "tools": fmt is not None,
            }
            seen = list(ids)
            started = time.perf_counter()
            keep = False  # whether the KV state is a true prefix worth keeping
            try:
                for r in stream_generate(
                    model,
                    tok,
                    prompt=rest,
                    max_tokens=tokens,
                    sampler=make_sampler(temp=temperature),
                    prompt_cache=cache,
                    logits_processors=[capper] if capper is not None else None,
                ):
                    pieces.append(r.text)
                    seen.append(int(r.token))
                    finish = r.finish_reason
                    for kind, text in live.feed(r.text):
                        if kind == "answer" and shown is not None:
                            text = shown.feed(text)  # a call's own markup is not shown as it is written
                            if not text:
                                continue
                        yield {"event": "delta", "kind": kind, "text": text, "n": len(pieces)}
                    if live.ended:
                        break  # the turn's own end, as text: nothing after it is the answer
                keep = True
            except GeneratorExit:
                keep = bool(pieces)  # the reader stopped it: what was read is still what the cache holds
                raise
            finally:
                seconds = time.perf_counter() - started
                if keep:
                    kv.insert_cache(key, seen, cache)
        for kind, text in live.flush():
            if kind == "answer" and shown is not None:
                text = shown.feed(text, last=True)
                if not text:
                    continue
            yield {"event": "delta", "kind": kind, "text": text, "n": len(pieces)}
        answer = "".join(pieces)
        # the model's own turn end, when its template has one: the text stops there
        ended = False
        for end in _TURN_ENDS:
            if end in str(answer):
                answer = str(answer).split(end)[0]
                ended = True
                break
        reasoning, reply = _split_reasoning(str(answer), state)
        # after a tool result the template opens <think> again, and Ling 3.0 Tiny can write its whole answer
        # inside it and end its turn without closing it (12 November: "whats the expedition status" came back
        # with 861 tokens filed as thinking and an empty answer). A turn the model ended itself, whose thinking
        # was never closed, is taken as its answer, and the reply says so; a turn cut off by the budget is not.
        if answer_left_in_thinking(str(answer), reasoning, reply, state, ended or live.ended or finish == "stop"):
            reply, reasoning = reasoning, ""
            answered_in_thinking = True
        if reasoning:
            reasonings.append(reasoning)
        seconds_all += seconds
        total_tokens_all += _own_tokens(tok, reasoning) + _own_tokens(tok, reply)
        calls = chat_tools.parse_calls(reply, fmt) if fmt else []
        if not calls or rnd == TOOL_ROUNDS:
            if calls:  # out of rounds: the calls are not run, and the reply says so
                reply = chat_tools.before_calls(reply) or "(the model asked for another tool call after the last round)"
            break
        said = chat_tools.before_calls(reply)
        results = []
        for c in calls:
            res = {"error": c["error"]} if c.get("error") else chat_tools.run(c["name"], c["arguments"])
            results.append(res)
            entry = {"round": rnd, "name": c["name"], "arguments": c["arguments"], "result": res}
            if c.get("raw"):
                # what the model actually wrote, when its call did not parse: the console's Debug panel shows it
                entry["raw"] = c["raw"]
            calls_log.append(entry)
            yield {"event": "tool", **entry}
        msgs = msgs + chat_tools.turns(calls, results, said)
    reasoning = "\n\n".join(reasonings)
    prompt_tokens = _own_tokens(tok, prompt)
    reasoning_tokens = _own_tokens(tok, reasoning)
    answer_tokens = _own_tokens(tok, reply)
    yield {
        "event": "done",
        "reply": {
            "model": key,
            "run": m["model"],
            "step": "",
            "prompt": question,
            "format": "the model's own continuation",
            "answer": reply,
            "reasoning": reasoning,
            "thinking": state,
            "meta": {
                "settings": {"temperature": temperature, "max_tokens": tokens, "thinking": state, "think_tokens": cap, "tools": fmt is not None},
                "prompt_tokens": prompt_tokens,
                "answer_tokens": answer_tokens,
                "reasoning_tokens": reasoning_tokens,
                "seconds": round(seconds_all, 2),
                "tok_s": round(total_tokens_all / seconds_all, 1) if seconds_all > 0 else None,
                # the generator's own word for it: the budget ran out ("length") unless the turn ended.
                # (It was recounted from the text before, which read a budget spent on thinking as a stop.)
                "finish": "stop" if ended or live.ended or finish == "stop" else "length",
                "rendered": prompt,
                # how much of the first prompt was read from the KV cache rather than evaluated again
                "cached_tokens": first_cached,
                # the same, as a share of the prompt as it was matched (its ids, BOS included)
                "cache_pct": first_pct,
                "dropped_turns": dropped,
                # whether the thinking was closed at its cap rather than by the model
                "think_capped": bool(capper is not None and capper.forced),
                # the model wrote its answer inside a thinking block it never closed, and ended its turn
                "answer_in_thinking": answered_in_thinking,
                # the tool calls the model made, each with its result, in order (thorp/chat_tools.py)
                "tool_calls": calls_log,
                "tool_rounds": len({c["round"] for c in calls_log}),
                "tools": {"on": bool(tools), "format": fmt, "why": tool_info["why"]},
            },
        },
    }


class _CallHider:
    """The answer as it streams, without a tool call's own markup: text is passed on until `<tool_call>`
    begins, and a tail that may be the start of one is held until it is known not to be."""

    MARK = "<tool_call>"

    def __init__(self) -> None:
        self.buf, self.sent, self.hidden = "", 0, False

    def feed(self, text: str, last: bool = False) -> str:
        if self.hidden:
            return ""
        self.buf += text
        i = self.buf.find(self.MARK)
        if i >= 0:
            self.hidden = True
            cut = i
        elif last:
            cut = len(self.buf)
        else:
            hold = next((k for k in range(len(self.MARK) - 1, 0, -1) if self.buf.endswith(self.MARK[:k])), 0)
            cut = len(self.buf) - hold
        out = self.buf[self.sent:cut]
        self.sent = max(self.sent, cut)
        return out


def foreign_answer(
    key: str,
    question: str,
    *,
    tokens: int = 80,
    temperature: float = 0.7,
    thinking: bool | None = None,
    history: list | None = None,
    think_tokens: int | None = None,
    tools: bool = False,
) -> dict:
    """One answer from a foreign ship's own MLX weights, whole: foreign_stream read to its end."""
    reply: dict = {}
    for ev in foreign_stream(
        key, question, tokens=tokens, temperature=temperature, thinking=thinking, history=history, think_tokens=think_tokens, tools=tools
    ):
        if ev["event"] == "done":
            reply = ev["reply"]
    return reply
