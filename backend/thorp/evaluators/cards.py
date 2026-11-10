"""The cards chaining two facts needs (2026-11-07, Justin: "build them"): the mover, the bridge and the
comparator, read inside the model on the logic deck (thorp/evaluators/logic.py) and on a
greater-than test. Stars until the rename: fleet.STARS keys mover, bridge, comparator.

- **Mover**: a head that carries the answer from where a premise stated it to where it is needed.
  On the deck's two-premise rows (order, cause, membership), the attention from the frame's last
  position to the premise's answer word less its attention to the rival word (both are in the
  premises by design), per layer and head: the name movers of the indirect-object circuit in
  GPT-2 small, put to a premise. Lit at 0.2.
- **Bridge**: the middle term, which the premises share and the conclusion never names, present at
  the frame's last position in the middle layers. On the padded rows (an irrelevant premise adds a
  second middle term), per layer, the logit lens's log-probability of the bridge's first piece less
  the distractor's, read twice with the two names exchanged (so each word's own prior cancels and
  only its role is left); the card's score is the best layer's mean. Resolving the bridge too late is how
  two-hop reasoning fails in larger models. Lit at 0.5 nats (provisional).
- **Comparator**: a head that, about to name a quantity, looks back at the quantity it must exceed.
  On "Begun in the year 16YY, the war lasted from the year 17YY to the year 17" (the greater-than
  test of GPT-2 small, with a decoy year), the attention from the last position to the year to be
  exceeded less to the decoy, per layer and head, so attention to numbers as such cancels. Lit at 0.3.

Metrics: stars/<card>/max_score, /best_layer, /best_head (mover and comparator also /shared_score and
/shared_layer, the best layer's two strongest heads); stars/bridge/max_score, /best_layer and
stars/bridge/layer_<i>. Artifact `cards`: the matrices and the bridge's layer curve.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.logic import load_deck
from thorp.evaluators.stars import shared
from thorp.models import ops

YEARS = [
    1702,
    1715,
    1723,
    1732,
    1741,
    1748,
    1756,
    1763,
    1771,
    1779,
    1784,
    1790,
    1796,
    1758,
    1727,
    1745,
]


def _span(tok, prompt: str, phrase: str, start: int = 0) -> list[int]:
    """Token positions (in eos + prompt) of the first occurrence of phrase at or after char start."""
    i = prompt.find(phrase, start)
    if i < 0:
        return []
    a = len(tok.encode(prompt[:i].rstrip())) + 1  # +1: the leading eos
    b = len(tok.encode(prompt[: i + len(phrase)])) + 1
    return list(range(a, max(b, a + 1)))


def _all_spans(tok, prompt: str, word: str, before: int) -> list[int]:
    out, k = [], 0
    while True:
        i = prompt.find(f" {word}", k)
        if i < 0 or i >= before:
            return out
        out += _span(tok, prompt, f" {word}", i)
        k = i + 1


def mover(model, tok, rows: list[dict]) -> np.ndarray | None:
    acc, n = None, 0
    for r in rows:
        if (
            r["variant"] != "both"
            or r["relation"] not in ("order", "cause", "membership")
            or not r["answer_word"]
        ):
            continue
        prompt = r["prompt"]
        cut = len(prompt) - len(r["frame"])
        rival_word = r["rival"].split()[0]
        good, bad = (
            _all_spans(tok, prompt, r["answer_word"], cut),
            _all_spans(tok, prompt, rival_word, cut),
        )
        if not good or not bad:
            continue
        ids = [tok.eos_id] + tok.encode(prompt)
        pats = ops.attention_patterns(model, [ids])
        m = []
        for p in pats:
            a = p[0, :, -1, :]  # heads x keys, from the last position
            m.append(a[:, good].sum(axis=1) - a[:, bad].sum(axis=1))
        acc = np.array(m) if acc is None else acc + np.array(m)
        n += 1
    return None if acc is None else acc / n


def _lens(model, tok, prompt: str, a: int, b: int) -> list[float]:
    """Per layer, the logit lens at the last position: log p(piece a) less log p(piece b)."""
    ids = [tok.eos_id] + tok.encode(prompt)
    out = []
    for lp in ops.lens_log_probs(model, [ids], -1):
        lp = lp[0]
        out.append(float(lp[a] - lp[b]))
    return out


def bridge(model, tok, rows: list[dict]) -> np.ndarray | None:
    """Counterbalanced: each padded item is read twice, the second time with the bridge and the
    distractor's names exchanged, so a word's own prior cancels and only its role in the chain is left."""
    if not all(hasattr(model, a) for a in ("hidden", "ln_f", "tok")):
        return None
    curves = []
    for r in rows:
        if r["variant"] != "padded" or not r["bridge"] or not r["distractor"]:
            continue
        b, d = r["bridge"], r["distractor"]
        b0, d0 = tok.encode(" " + b)[0], tok.encode(" " + d)[0]
        if b0 == d0:
            continue
        swapped = r["prompt"].replace(b, "\x00").replace(d, b).replace("\x00", d)
        one = _lens(model, tok, r["prompt"], b0, d0)  # the bridge is b
        two = _lens(model, tok, swapped, d0, b0)  # the bridge is d
        curves.append([(x + y) / 2 for x, y in zip(one, two, strict=True)])
    return None if not curves else np.mean(np.array(curves), axis=0)


def comparator(model, tok) -> np.ndarray:
    """Attention from the last position to the year that must be exceeded, less to an irrelevant
    year named earlier (a decoy), so attention to numbers as such cancels."""
    acc = None
    for k, y in enumerate(YEARS):
        decoy = YEARS[(k + 5) % len(YEARS)] - 60
        prompt = (
            f"Begun in the year {decoy}, the war lasted from the year {y} to the year {str(y)[:2]}"
        )
        good, bad = _span(tok, prompt, f" {y}"), _span(tok, prompt, f" {decoy}")
        ids = [tok.eos_id] + tok.encode(prompt)
        m = []
        for p in ops.attention_patterns(model, [ids]):
            a = p[0, :, -1, :]
            m.append(a[:, good].sum(axis=-1) - a[:, bad].sum(axis=-1))
        acc = np.array(m) if acc is None else acc + np.array(m)
    return acc / len(YEARS)


def copying_cards(model, tok, seqs: int = 8, length: int = 200) -> dict | None:
    """Previous-word and the Nevermore, read the same way for any model (Nothing up my sleeve's or an outside one):
    SEQS passages of LENGTH pieces of Goldsmith's essays (the Forgotten Tome the Nevermore test
    uses, nevermore.NATURAL_BOOK), tokenised with the model's own tokeniser. Previous-word: the mean
    attention from each piece to the one before it. Nevermore: each passage followed by itself, the
    mean attention from a piece in the second copy to the piece that followed it in the first (as in
    Olsson et al., 2022); with the copy gain, the drop in loss from the first copy to the second.
    One passage at a time, so a large model's attention fits in memory."""
    from thorp.evaluators.nevermore import NATURAL_BOOK
    from thorp.sources import load_text

    try:
        text = load_text(NATURAL_BOOK)
    except Exception:
        return None
    ids = tok.encode(text[len(text) // 10 :])
    n = length
    starts = np.linspace(0, len(ids) - 2 * n - 1, seqs).astype(int)
    prev = nev = None
    gains = []
    for s0 in starts:
        # previous-word, on 2n running pieces
        run = [tok.eos_id] + ids[s0 : s0 + 2 * n]
        src = np.arange(2, len(run))
        pw = []
        for p in ops.attention_patterns(model, [run]):
            pw.append(p[0][:, src, src - 1].mean(axis=1))
        pw = np.array(pw)
        prev = pw if prev is None else prev + pw
        # the Nevermore, on n pieces and the same again
        piece = ids[s0 : s0 + n]
        x = [tok.eos_id] + piece + piece
        i = np.arange(n - 1)
        src2, dst2 = n + 1 + i, i + 2
        nv = []
        for p in ops.attention_patterns(model, [x]):
            nv.append(p[0][:, src2, dst2].mean(axis=1))
        nv = np.array(nv)
        nev = nv if nev is None else nev + nv
        xa = np.array([x], dtype=np.int32)
        ce = ops.token_ce(model, xa[:, :-1], xa[:, 1:])[0]
        gains.append(float(ce[1:n].mean() - ce[n + 1 : 2 * n].mean()))
    return {
        "previous_word": prev / len(starts),
        "nevermore": nev / len(starts),
        "copy_gain": float(np.mean(gains)),
    }


def _head_metrics(key: str, s: np.ndarray) -> dict[str, float]:
    li, hi = np.unravel_index(int(s.argmax()), s.shape)
    sh, sl = shared(s)
    return {
        f"stars/{key}/max_score": float(s.max()),
        f"stars/{key}/best_layer": float(li),
        f"stars/{key}/best_head": float(hi),
        f"stars/{key}/shared_score": sh,
        f"stars/{key}/shared_layer": float(sl),
    }


def evaluate(ctx: EvalContext) -> EvalResult:
    model, tok = ctx.model, ctx.tokeniser
    if not hasattr(model, "attention_patterns"):
        return EvalResult()
    rows = load_deck()
    metrics, rec = {}, {}
    if rows:
        mv = mover(model, tok, rows)
        if mv is not None:
            metrics.update(_head_metrics("mover", mv))
            rec["mover"] = np.round(mv, 4).tolist()
        br = bridge(model, tok, rows)
        if br is not None:
            metrics["stars/bridge/max_score"] = float(br.max())
            metrics["stars/bridge/best_layer"] = float(br.argmax())
            metrics.update({f"stars/bridge/layer_{i}": float(v) for i, v in enumerate(br)})
            rec["bridge"] = np.round(br, 4).tolist()
    cp = comparator(model, tok)
    metrics.update(_head_metrics("comparator", cp))
    rec["comparator"] = np.round(cp, 4).tolist()
    text = json.dumps(rec)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "cards",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
