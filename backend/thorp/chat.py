"""Chat with a finished Thorp run's latest checkpoint, shared by the CLI and the dash.

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


def prompt_for(spec: dict, question: str) -> tuple[str, str]:
    """The question wrapped the way the voyage was taught: the v0.1.4 marks where it read them, else
    plain prose. Returns (prompt, format)."""
    q = question.strip()
    # a return leg (11 November) says which turn format it was taught: ask it exactly as its turns were written
    from thorp import cleaning, turns

    fmt = turns.format_of(spec)
    if fmt:
        return turns.prompt(fmt, q, cleaning.version_of(spec)), fmt
    recipe = str((spec.get("data") or {}).get("recipe") or "")
    if "ogden-v0.1.4" in recipe or "chat" in recipe.lower() or "dialogue" in recipe.lower():
        return f"<question>{q}<answer>", "marks"
    return f"Question: {q}\nAnswer:", "plain"


def _ask(
    model, tok, spec: dict, question: str, temperature: float, tokens: int, seed: int
) -> tuple[str, str, str]:
    prompt, fmt = prompt_for(spec, question)
    key = seed if ops.is_torch(model) else _mx_key(seed)
    out = generate(model, tok, prompt, temperature, tokens, int(spec["model"]["context"]), key)
    if fmt == "marks":
        for end in ("<end>", "<sep>", "<question>"):
            out = out.split(end)[0]
    else:
        for end in ("\nQuestion:", "\nQ:", "\nq:", "<question>"):
            out = out.split(end)[0]
    return out.strip(), prompt, fmt


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
) -> dict:
    """One answer from the run's latest checkpoint (or `step`), with the heads and cards audit."""
    with _LOCK:
        model, tok, spec, ckpt = load(run_name, step)
        started = time.perf_counter()
        text, prompt, fmt = _ask(model, tok, spec, question, temperature, tokens, seed)
        seconds = time.perf_counter() - started
        prompt_tokens = _own_tokens(tok, prompt)
        answer_tokens = _own_tokens(tok, text)
        out = {
            "run": run_name,
            "step": ckpt.name,
            "prompt": prompt,
            "format": fmt,
            "answer": text,
            "reasoning": "",
            "thinking": "none",
            "meta": {
                "settings": {"temperature": temperature, "max_tokens": tokens, "thinking": "none"},
                "prompt_tokens": prompt_tokens,
                "answer_tokens": answer_tokens,
                "reasoning_tokens": 0,
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
    """A file of a cached model (its chat template or config), or None when the hub cannot say."""
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
    except Exception:  # noqa: BLE001  a tokeniser that cannot count must not fail an answer
        return 0


def _split_reasoning(text: str, thinking: str) -> tuple[str, str]:
    """(reasoning, answer) from a continuation: the trace is what came before the closing think
    marker; with no marker and thinking on, the whole continuation is still reasoning."""
    for marker in ("</think>", "<|end_of_thought|>", "<channel|>"):
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
        "thinking": {"mode": "none", "default": False, "why": "a Nothing up my sleeve GPT has no reasoning mode"},
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


# ---- the foreign ships (11 November, Justin: "chat has to appear on both Nothing up my sleeve's
# ships as well as foreign ships"): an outside model's own continuation, from the MLX weights when
# they are in the cache. No audit: the heads/cards trace is Nothing up my sleeve's own GPT.
_FOREIGN: dict[str, tuple] = {}
_FOREIGN_MAX = 2


def _cached(model_id: str) -> bool:
    """Whether the outside model's config is in the Hugging Face cache (its weights are, beside it)."""
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
                },
                "why": None if cached else "its weights are not in the MLX cache yet",
            }
        )
    return out


def foreign_answer(
    key: str,
    question: str,
    *,
    tokens: int = 80,
    temperature: float = 0.7,
    thinking: bool | None = None,
    history: list | None = None,
) -> dict:
    """One answer from a foreign ship's own MLX weights: the model's continuation, not a Thorp
    checkpoint. The weights load once per model (cached, two at a time); a model not in the cache
    says so. The reply has no audit: the heads/cards trace (thorp.chat._audit) is our GPT's."""
    from thorp import foreign

    m = foreign.get_any(key)
    if m is None:
        raise LookupError(f"no foreign ship {key!r}")
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    with _LOCK:
        hit = _FOREIGN.get(key)
        if hit is None:
            model, tok = load(m["model"])
            _FOREIGN[key] = hit = (model, tok)
            while len(_FOREIGN) > _FOREIGN_MAX:
                _FOREIGN.pop(next(iter(_FOREIGN)))
        model, tok = hit
    support = thinking_support(m["model"])
    state, kwargs = "none", {}
    if support["mode"] == "toggle":
        want = support["default"] if thinking is None else bool(thinking)
        state = "on" if want else "off"
        kwargs = {"enable_thinking": want}
    elif support["mode"] == "auto":
        state = "auto"
    # the conversation so far, for a continuation: the model is asked with its own turns, so a second
    # message can pick up where the first stopped instead of starting again
    msgs = []
    for h in history or []:
        role = str(h.get("role") or "")
        text = str(h.get("text") or h.get("content") or "")
        if text and role in ("you", "user", "thorp", "assistant"):
            msgs.append({"role": "user" if role in ("you", "user") else "assistant", "content": text})
    msgs.append({"role": "user", "content": question})
    prompt = question
    try:  # an instruct model's own template; a base model continues the raw prompt
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, **kwargs)
    except TypeError:  # a template that takes no thinking switch: ask it the old way
        prompt = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        state = "auto" if support["mode"] != "none" else "none"
    except Exception:  # noqa: BLE001  no template: the raw prompt
        prompt = question
        state = "none"
    started = time.perf_counter()
    text = generate(
        model, tok, prompt=prompt, max_tokens=tokens, sampler=make_sampler(temp=temperature), verbose=False
    )
    seconds = time.perf_counter() - started
    answer = text[len(prompt) :] if isinstance(text, str) and text.startswith(prompt) else text
    # the model's own turn end, when its template has one: a finished turn stops there rather than
    # running on to the token cap (the control token is already in its embeddings)
    ended = False
    for end in ("<|im_end|>", "<|endoftext|>", "<end_of_turn>", "<|eot_id|>", "<|end|>", "</s>"):
        if end in str(answer):
            answer = str(answer).split(end)[0]
            ended = True
            break
    reasoning, reply = _split_reasoning(str(answer), state)
    prompt_tokens = _own_tokens(tok, prompt)
    reasoning_tokens = _own_tokens(tok, reasoning)
    answer_tokens = _own_tokens(tok, reply)
    total_tokens = reasoning_tokens + answer_tokens
    return {
        "model": key,
        "run": m["model"],
        "step": "",
        "prompt": question,
        "format": "the model's own continuation",
        "answer": reply,
        "reasoning": reasoning,
        "thinking": state,
        "meta": {
            "settings": {"temperature": temperature, "max_tokens": tokens, "thinking": state},
            "prompt_tokens": prompt_tokens,
            "answer_tokens": answer_tokens,
            "reasoning_tokens": reasoning_tokens,
            "seconds": round(seconds, 2),
            "tok_s": round(total_tokens / seconds, 1) if seconds > 0 else None,
            "finish": "stop" if ended else ("length" if total_tokens >= tokens else "stop"),
            "rendered": prompt,
        },
    }
