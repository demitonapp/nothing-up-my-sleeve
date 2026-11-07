"""The successor trick (2026-11-07, Justin): does the model know what comes next in a series?

A trick is something the model can do, measured from outside by what it bets; a star is the
mechanism inside that does it, measured by looking at the heads (thorp/fleet.py TRICKS, STARS).

Monday comes before Tuesday, January before February, first before second, Chapter IV before V.
That is knowledge of order, not copying: the answer is never in the prompt. Successor heads have
been found in models of 70M parameters and more (Gould et al., 2023); Thorp's pre-registered
expectation is that a successor head lights from 21m. Lit at a smaller class, it is a discovery.

The test: for every series in SERIES and every run of CONTEXT consecutive items in it, a prompt of
those items in the series' own format (for example "Monday, Tuesday, ") and every item of the
series as a candidate continuation. The model's log-probability of each candidate's pieces (summed)
less its log-probability after the lead-in alone (its prior, so short or common items are not
favoured) ranks them; the prompt counts as right when the true next item ranks first. Chance is one over the
series length (from 1/7 for the days to 1/20 for the numbers).

Metrics: tricks/successor/score (the share right, over every prompt of every series),
tricks/successor/lift (that share less the chance share), tricks/successor/<series> (each series'
share right). Behavioural: there is no layer or head to report. Artifact `successor`: the shares
and, per series, the prompts it got right.
"""

from __future__ import annotations

import hashlib
import json

import mlx.core as mx
import numpy as np

from thorp.evaluators import EvalContext, EvalResult

CONTEXT = 2
SERIES: dict[str, tuple[str, str, list[str]]] = {
    # name: (item format, lead-in before the next item, items). The prompt is CONTEXT items in their
    # format then the lead-in; each candidate is " <item>" (Thorp's tokeniser joins a space to the
    # word after it, so a prompt never ends on a bare space).
    "days": (
        "{},",
        "",
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    ),
    "months": (
        "{},",
        "",
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
    ),
    "ordinals": (
        "{},",
        "",
        [
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
            "sixth",
            "seventh",
            "eighth",
            "ninth",
            "tenth",
        ],
    ),
    "numbers": (
        "{},",
        "",
        [
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ],
    ),
    "chapters": (
        "CHAPTER {}.\n\n",
        "CHAPTER",
        ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"],
    ),
}


def _logprob(model, tok, prompt_ids: list[int], cands: list[list[int]]) -> np.ndarray:
    """Summed log-probability of each candidate's pieces after the prompt."""
    n = len(prompt_ids)
    L = n + max(len(c) for c in cands)
    x = np.zeros((len(cands), L), dtype=np.int32)
    for i, c in enumerate(cands):
        seq = prompt_ids + c
        x[i, : len(seq)] = seq
    logits = model(mx.array(x)).astype(mx.float32)
    lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    mx.eval(lp)
    lp = np.array(lp)
    out = np.zeros(len(cands))
    for i, c in enumerate(cands):
        for j, t in enumerate(c):
            out[i] += lp[i, n - 1 + j, t]
    return out


def evaluate(ctx: EvalContext) -> EvalResult:
    model, tok = ctx.model, ctx.tokeniser
    right_all, chance_all, record = [], [], {}
    for name, (fmt, lead, items) in SERIES.items():
        cands = [tok.encode(" " + it) for it in items]
        # the candidates' prior: their log-probability after the lead-in alone, so a short or common
        # item is not favoured whatever came before (the score is what the series adds)
        prior = _logprob(model, tok, [tok.eos_id] + tok.encode(lead or "\n"), cands)
        right = []
        for s in range(len(items) - CONTEXT):
            prompt = " ".join(fmt.format(it) for it in items[s : s + CONTEXT]).rstrip(" ") + (
                " " + lead if lead else ""
            )
            prompt = prompt.replace(" CHAPTER", "CHAPTER") if lead else prompt
            ids = [tok.eos_id] + tok.encode(prompt)
            if len(ids) + max(len(c) for c in cands) > ctx.context:
                continue
            scores = _logprob(model, tok, ids, cands) - prior
            right.append(int(scores.argmax()) == s + CONTEXT)
        record[name] = {
            "share": float(np.mean(right)) if right else None,
            "chance": 1 / len(items),
            "right": [items[s + CONTEXT] for s, r in enumerate(right) if r],
        }
        right_all += right
        chance_all += [1 / len(items)] * len(right)
    share = float(np.mean(right_all)) if right_all else 0.0
    metrics = {
        "tricks/successor/score": share,
        "tricks/successor/lift": share - (float(np.mean(chance_all)) if chance_all else 0.0),
        **{
            f"tricks/successor/{k}": v["share"] for k, v in record.items() if v["share"] is not None
        },
    }
    text = json.dumps(record)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "successor",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
