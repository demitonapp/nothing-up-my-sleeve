"""The first two stars (2026-11-07): previous-word heads and duplicate-word heads.

A **previous-word head** attends from each word to the word just before it. It is the building
block a Nevermore is made from: the Nevermore in a later layer reads what the previous-word head
wrote. Score: for every layer and head, the mean attention from each position to the one before it,
over SEQS real passages of 2 x LENGTH word pieces from a Forgotten Tome (NATURAL_BOOK, never on
any shelf).

A **duplicate-word head** attends from a word to the earlier place where the same word appeared
("Darcy ... Darcy"). Score: SEQS sequences of LENGTH random word pieces followed by the same pieces
again (seed 1845, the same test the Nevermore uses); for every layer and head, the mean attention
from each piece in the second copy to the same piece in the first.

Five more, on the same readings of the real passages (Justin, 08:40; the dashboard's position family):
**offset_2** and **offset_3** (the previous-word test two and three words back), the **attention
sink** (mean attention from every query to position 0, the window's opening EOS), the **delimiter**
(a head's attention on punctuation and line-break pieces over their share of the keys it can see:
1 is indifferent), and the **rare word** (the correlation, per head, between the attention a piece
receives, averaged over the queries that can see it, and its rarity on the shelf, -log frequency
from the recipe's shards). The sink, delimiter and rare word report no shared score.

A head is lit at its star's threshold (thorp/fleet.py STARS). Even attention over the context would
score about 1/300 for either.

Metrics, for each star in (previous_word, duplicate_word): stars/<star>/max_score, /count (heads
lit), /best_layer, /best_head, and /shared_score with /shared_layer: the best layer's two strongest
heads together, because a small model often splits one job across two heads (First Light's
pathfinder: 0.34 and 0.29 in one layer). A star is lit by one head at its threshold, and lit
shared when two heads of one layer reach it together; both are reported. Artifact `stars`: both layer x head matrices.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.nevermore import LENGTH, NATURAL_BOOK, SEQS, test_tokens
from thorp.fleet import STARS
from thorp.models import ops


def passages(tok, context: int) -> np.ndarray | None:
    from thorp import manifest, shards

    if manifest.get(NATURAL_BOOK) is None:
        return None
    arr = np.asarray(shards.load(tok.id, NATURAL_BOOK, tok))
    n = min(2 * LENGTH, context - 1)
    starts = np.linspace(len(arr) // 10, len(arr) - n - 1, SEQS).astype(int)
    return np.stack([np.concatenate([[tok.eos_id], arr[s : s + n]]) for s in starts]).astype(
        np.int32
    )


def head_scores(model, toks: np.ndarray, src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    out = []
    for p in ops.attention_patterns(model, toks):
        out.append(p[:, :, src, dst].mean(axis=(0, 2)))
    return np.array(out)  # (layers, heads)


def shared(scores: np.ndarray) -> tuple[float, int]:
    """The best layer's two strongest heads together (a small model often splits one job across two
    heads in a layer): (score, layer)."""
    top2 = np.sort(scores, axis=1)[:, -2:].sum(axis=1)
    return float(top2.max()), int(top2.argmax())


def summarise(key: str, scores: np.ndarray) -> dict[str, float]:
    th = STARS[key].threshold
    li, hi = np.unravel_index(int(scores.argmax()), scores.shape)
    sh, sl = shared(scores)
    return {
        f"stars/{key}/max_score": float(scores.max()),
        f"stars/{key}/count": float((scores >= th).sum()),
        f"stars/{key}/best_layer": float(li),
        f"stars/{key}/best_head": float(hi),
        f"stars/{key}/shared_score": sh,
        f"stars/{key}/shared_layer": float(sl),
    }


_rarity_cache: dict[tuple, np.ndarray] = {}
_delim_cache: dict[str, np.ndarray] = {}


def rarity(tok, recipe: list[str]) -> np.ndarray | None:
    """-log frequency of every vocabulary id on the shelf (from its shards; add-one smoothed),
    computed once per process."""
    from thorp import shards

    if not recipe:
        return None
    key = (tok.id, tuple(sorted(recipe)))
    if key not in _rarity_cache:
        counts = np.ones(tok.vocab_size, dtype=np.float64)
        for b in recipe:
            counts += np.bincount(
                np.asarray(shards.load(tok.id, b, tok)), minlength=tok.vocab_size
            )[: tok.vocab_size]
        _rarity_cache[key] = -np.log(counts / counts.sum())
    return _rarity_cache[key]


def delimiters(tok) -> np.ndarray:
    """A bool per vocabulary id: the piece is made only of punctuation, spaces and line breaks,
    with at least one punctuation mark or line break in it."""
    if tok.id not in _delim_cache:
        from thorp.evaluators.bpb_split import piece_bytes

        flags = []
        for b in piece_bytes(tok):
            t = b.decode("utf-8", errors="ignore")
            flags.append(
                bool(t.strip(" "))
                and all(not c.isalnum() for c in t)
                and any(c in "\n" or not c.isspace() for c in t)
            )
        _delim_cache[tok.id] = np.array(flags, dtype=bool)
    return _delim_cache[tok.id]


def patterns(model, toks: np.ndarray) -> list[np.ndarray]:
    out = []
    for p in ops.attention_patterns(model, toks):
        out.append(p)  # (batch, heads, T, T)
    return out


def at(pats: list[np.ndarray], src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    return np.array([p[:, :, src, dst].mean(axis=(0, 2)) for p in pats])  # (layers, heads)


def evaluate(ctx: EvalContext) -> EvalResult:
    model = ctx.model
    if not hasattr(model, "attention_patterns"):
        return EvalResult()
    metrics: dict[str, float] = {}
    record: dict = {}
    tok = ctx.tokeniser

    def keep(key: str, scores: np.ndarray, with_shared: bool = True):
        m = summarise(key, scores)
        if not with_shared:
            m = {k: v for k, v in m.items() if "/shared_" not in k}
        metrics.update(m)
        record[key] = scores.round(4).tolist()

    nat = passages(tok, ctx.context)
    if nat is not None:
        pats = patterns(model, nat)
        T = nat.shape[1]
        for k, key in ((1, "previous_word"), (2, "offset_2"), (3, "offset_3")):
            t = np.arange(k + 1, T)
            keep(key, at(pats, t, t - k))
        # the attention sink: from every query after the first to position 0, the window's opening EOS
        q = np.arange(1, T)
        keep("attention_sink", at(pats, q, np.zeros_like(q)), with_shared=False)
        # delimiters: the attention landing on punctuation and line-break pieces, over their share of
        # the keys each query can see (1 is indifferent)
        dl = delimiters(tok)[nat]  # (batch, T)
        dl[:, 0] = False
        causal = np.tril(np.ones((T, T), dtype=bool), k=-1)[None, None]  # keys before the query
        share = (dl[:, None, None, :] & causal).sum(-1) / np.maximum(causal.sum(-1), 1)  # (b, 1, T)
        ratio = []
        for p in pats:
            mass = (p * dl[:, None, None, :]).sum(-1)  # (b, h, T)
            ok = share[..., 1:] > 0
            r = np.where(ok, mass[..., 1:] / np.where(ok, share[..., 1:], 1), np.nan)
            ratio.append(np.nanmean(r, axis=(0, 2)))
        keep("delimiter", np.array(ratio), with_shared=False)
        # rare words: does the attention a piece receives follow its rarity on the shelf?
        rar = rarity(tok, ctx.recipe)
        if rar is not None:
            rr = rar[nat[:, 1:]]  # (b, T-1): keys 1..T-1
            corr = []
            for p in pats:
                recv = (
                    p[:, :, :, 1:].sum(axis=2) / np.arange(T - 1, 0, -1)[None, None]
                )  # mean over the queries that can see each key
                row = []
                for h in range(p.shape[1]):
                    a, b = recv[:, h].ravel(), rr.ravel()
                    row.append(
                        float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
                    )
                corr.append(row)
            keep("rare_word", np.array(corr), with_shared=False)
        record["natural_book"] = NATURAL_BOOK
    toks, n = test_tokens(tok.vocab_size, tok.eos_id, ctx.context)
    i = np.arange(n)
    keep("duplicate_word", at(patterns(model, toks), n + 1 + i, 1 + i))
    text = json.dumps(record)
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "stars",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
