"""Script bias: how much probability an English context gives to cuneiform words.

The Babel expedition asks whether cuneiform in the reading starts to bend Pan's English. The probe
takes English held-out books, runs the model over their first tokens, and sums the probability mass
the model puts on a fixed list of Sumerian words at every position. A control trained on English
should give them almost nothing; a model that has read cuneiform should give them more, even on
English text. The metric is relative: the two arms share the tokeniser, so the same token ids are
counted in both.
"""

from __future__ import annotations

import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops

# Distinctive Sumerian forms, not English function words: the short forms (a, in, an, ta) are left out
# because the English tokeniser gives them ordinary English mass.
CUNEIFORM = (
    "lugal", "dumu", "enlil", "enki", "inanna", "nanna", "utu", "dingir", "dijir",
    "cag4", "jic", "kug", "sikil", "gud", "udu", "ama", "nam", "he2", "gal2", "du3",
    "e2", "a-a", "mucen", "edin", "kur", "sag", "kalag", "mah", "tuku", "ak",
)  # fmt: skip
ENGLISH = ("the", "of", "and", "to", "in", "that", "he", "was", "it", "his", "with", "as", "for")


def _ids(tok, words: tuple[str, ...]) -> list[int]:
    out = []
    for w in words:
        try:
            ids = tok.encode(" " + w)
        except Exception:  # noqa: BLE001
            continue
        if ids:
            out.append(ids[0])
    return sorted(set(out))


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    books = ctx.sets.get("hole-cards-unseen") or next(iter(ctx.sets.values()), [])
    tok = ctx.tokeniser
    c_ids = _ids(tok, CUNEIFORM)
    e_ids = _ids(tok, ENGLISH)
    masses, emasses = [], []
    for b in books[:8]:
        try:
            tokens = np.asarray(shards.load(tok.id, b, tok)[:512], dtype=np.int32)
        except Exception:  # noqa: BLE001
            continue
        if len(tokens) < 32:
            continue
        lp = ops.log_probs(ctx.model, [tokens])[0]  # (time, vocab)
        p = np.exp(lp - lp.max(axis=-1, keepdims=True))
        p /= p.sum(axis=-1, keepdims=True)
        if c_ids:
            m = p[:, c_ids].sum(axis=1)
            masses.append(float(m[8:].mean()) if len(m) > 8 else float(m.mean()))
        if e_ids:
            emasses.append(float(p[:, e_ids].sum(axis=1)[8:].mean()))
    if masses:
        out.metrics["script/cuneiform_mass_en"] = float(np.mean(masses))
        out.metrics["script/cuneiform_max_en"] = float(np.max(masses))
    if emasses:
        out.metrics["script/english_mass_en"] = float(np.mean(emasses))
    return out
