"""Nevermores: Thorp's name for induction heads (2026-11-07, Justin), after the refrain of Poe's
"The Raven": once the reader has seen "Quoth the Raven" followed by "Nevermore", the next
"Quoth the Raven" brings "Nevermore" to mind before it is read.

An induction head is an attention head that, at a word it has seen before in the text, looks back
to where that word last appeared and attends to the word that came after it, so the model can bet
that the same thing follows again (Olsson et al., 2022, "In-context learning and induction heads").
They are known to form suddenly during training (a phase transition).

The test, as in that paper: SEQS sequences of an EOS, LENGTH random word pieces, and the same
pieces again, fixed by a constant seed so every step and every run sees the same test. For every
layer and head, the Nevermore score is the mean attention weight, over the second copy, from each
piece to the piece that followed it in the first copy (0 is none, 1 is all of the head's attention;
a head attending evenly over the context would score about 1/300). A head scoring at least
THRESHOLD is counted as a Nevermore. Copy gain is the drop in loss (nats per token) from the first
copy to the second, which only a model that copies can predict.

The same test also runs on real prose (`natural_*` metrics): SEQS passages of LENGTH pieces from a
Forgotten Tome (NATURAL_BOOK, never on any shelf), each followed by itself. A head can form on real
text before it works on random pieces (seen first in the 9m run with a 4,096 vocabulary), so both
are kept; the random test is the standard one.

Metrics: nevermore/max_score, nevermore/count, nevermore/best_layer, nevermore/best_head,
nevermore/copy_loss_first, nevermore/copy_loss_second, nevermore/copy_gain, and
nevermore/natural_max_score, nevermore/natural_count, nevermore/natural_copy_gain, and
nevermore/natural_shared_score with /natural_shared_layer (the best layer's two strongest heads together). Artifact
`nevermore`: the full layer x head score matrices.
"""

from __future__ import annotations

import hashlib
import json

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.fleet import STARS

SEQS = 8
LENGTH = 200
THRESHOLD = STARS["nevermore"].threshold  # defined once, in thorp/fleet.py
SEED = 1845  # the year "The Raven" was published
NATURAL_BOOK = "pg79560"  # Goldsmith's essays, a Forgotten Tome


def test_tokens(vocab: int, eos: int, context: int) -> tuple[np.ndarray, int]:
    n = min(LENGTH, (context - 1) // 2)
    rng = np.random.default_rng(SEED)
    a = rng.integers(3, vocab, size=(SEQS, n))
    return np.concatenate([np.full((SEQS, 1), eos), a, a], axis=1).astype(np.int32), n


def natural_tokens(tok, context: int) -> tuple[np.ndarray, int] | None:
    from thorp import manifest, shards

    if manifest.get(NATURAL_BOOK) is None:
        return None
    arr = np.asarray(shards.load(tok.id, NATURAL_BOOK, tok))
    n = min(LENGTH, (context - 1) // 2)
    starts = np.linspace(len(arr) // 10, len(arr) - n - 1, SEQS).astype(int)
    seqs = [np.concatenate([[tok.eos_id], arr[s : s + n], arr[s : s + n]]) for s in starts]
    return np.stack(seqs).astype(np.int32), n


def measure(model, toks: np.ndarray, n: int) -> tuple[np.ndarray, float, float]:
    """(layers x heads Nevermore scores, loss on the first copy, loss on the second copy)."""
    x = mx.array(toks)
    i = np.arange(n - 1)
    src = n + 1 + i  # position of piece i in the second copy
    dst = i + 2  # position of piece i + 1 in the first copy
    scores = []
    for p in model.attention_patterns(x):
        mx.eval(p)
        scores.append(np.array(p)[:, :, src, dst].mean(axis=(0, 2)))
    logits = model(x[:, :-1]).astype(mx.float32)
    ce = nn.losses.cross_entropy(logits, x[:, 1:], reduction="none")
    mx.eval(ce)
    ce = np.array(ce)  # position t predicts token t + 1
    return np.array(scores), float(ce[:, 1:n].mean()), float(ce[:, n + 1 : 2 * n].mean())


def evaluate(ctx: EvalContext) -> EvalResult:
    model = ctx.model
    if not hasattr(model, "attention_patterns"):
        return EvalResult()
    toks, n = test_tokens(ctx.tokeniser.vocab_size, ctx.tokeniser.eos_id, ctx.context)
    scores, first, second = measure(model, toks, n)
    li, hi = np.unravel_index(int(scores.argmax()), scores.shape)
    metrics = {
        "nevermore/max_score": float(scores.max()),
        "nevermore/count": float((scores >= THRESHOLD).sum()),
        "nevermore/best_layer": float(li),
        "nevermore/best_head": float(hi),
        "nevermore/copy_loss_first": first,
        "nevermore/copy_loss_second": second,
        "nevermore/copy_gain": first - second,
    }
    record = {"threshold": THRESHOLD, "length": n, "seqs": SEQS, "scores": scores.round(4).tolist()}
    nat = natural_tokens(ctx.tokeniser, ctx.context)
    if nat is not None:
        ns, nf, nsec = measure(model, *nat)
        nl, nh = np.unravel_index(int(ns.argmax()), ns.shape)
        metrics.update(
            {
                "nevermore/natural_max_score": float(ns.max()),
                "nevermore/natural_count": float((ns >= THRESHOLD).sum()),
                "nevermore/natural_best_layer": float(nl),
                "nevermore/natural_best_head": float(nh),
                "nevermore/natural_copy_gain": nf - nsec,
            }
        )
        # the shared score (Justin, 23:40: "do it"): the best layer's two strongest heads together, as previous-word
        # has, because a model with heads to spare splits the copying across two (the 1m copied at a gain of 4.9
        # while no single head passed 0.15)
        top2 = np.sort(ns, axis=1)[:, -2:].sum(axis=1)
        metrics["nevermore/natural_shared_score"] = float(top2.max())
        metrics["nevermore/natural_shared_layer"] = float(int(top2.argmax()))
        record["natural_book"] = NATURAL_BOOK
        record["natural_scores"] = ns.round(4).tolist()
    text = json.dumps(record)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "nevermore",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
