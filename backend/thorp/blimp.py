"""BLiMP, the Benchmark of Linguistic Minimal Pairs (11 November, Justin: "what is a good measure ...
that other peers will recognise. Only 1 test").

It held the title of "the one peer-recognised test for models under 1B" for a day; that is AI2 ARC's
now (``thorp/arc_ai2.py``, 11 November: "I'd prefer the ARC easy challenge"), because ARC reads what a
model can do and BLiMP reads only whether it knows English. BLiMP stays as the grammatical reading
beside it: it is a core evaluation of the BabyLM Challenge (10M to 100M words of training text) and it
needs no prompt.

Chaining was invented here and is not peer reviewed, and at this size nothing reasons: every model
under 4B solves 0 ARC-AGI-2 tasks. BLiMP is the standard for models the size of the fleet and it needs
no prompt:

    67 paradigms x 1,000 pairs = 67,000 pairs of sentences, one grammatical and one not, differing
    by a minimal edit. A model gets a pair right when it gives the grammatical sentence the higher
    probability (the sum of the log probabilities of its pieces). Chance is 50%.

Warstadt et al., "BLiMP: The Benchmark of Linguistic Minimal Pairs for English", TACL 2020. The
data is CC BY 4.0, ``nyu-mll/blimp`` on Hugging Face, pinned to one revision below and fetched once
into ``data/blimp`` (THORP_BLIMP overrides it), as ARC-AGI-2 is into ``data/arc-agi-2``.

Each sentence is scored as ``[start] + pieces``, so its first piece is predicted too, whatever the
tokeniser. A tie (equal log probability) is not a right answer; the count of ties is kept. Seven pairs in the
released files (passive_1, principle_A_case_2) have two identical sentences, so they can only tie:
they stay in, so the 67,000 are the 67,000 other readings use, and cost no model more than 0.01%.

Two overall numbers, because the benchmark has been summarised both ways: ``accuracy`` is the mean
over the 67 paradigms (the BabyLM Challenge's way; with 1,000 pairs a paradigm it equals the share of
all pairs), and ``macro_terms`` is the mean over the phenomena (``linguistics_term``), the paper's
way (the paper has 12; the files split s-selection from argument structure, so 13 here, and this
module reads the files as they are). Each phenomenon and each of the four fields (syntax, morphology, syntax_semantics,
semantics) is kept beside them.

This module is the shared plumbing, so the evaluator (``thorp/evaluators/blimp.py``) and the
outside-model scorer (``scripts/score_blimp.py``) read the benchmark one way. It knows nothing of
any model: a model is a function ``ce(x, y) -> (batch, time) nats``.
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import numpy as np

from thorp import paths

REPO = "nyu-mll/blimp"
REVISION = "877fba0801ffb7cbd8c39c1ff314a46f053f6036"  # the revision read on 11 November 2026
PER_PARADIGM = 1000
PARADIGMS = 67
TERMS = 13  # the files' `linguistics_term`: the paper's 12 phenomena, with s-selection kept apart


def root() -> Path:
    """Where the BLiMP files live (``data/blimp`` by default, THORP_BLIMP overrides it)."""
    return Path(os.environ.get("THORP_BLIMP") or paths.resolve("data/blimp"))


def ensure(base: Path | None = None) -> Path:
    """The BLiMP files, downloaded once (about 4 MB) at the pinned revision. Returns the root."""
    base = Path(base) if base else root()
    if len(list(base.glob("*/train-*.parquet"))) >= PARADIGMS:
        return base
    from huggingface_hub import snapshot_download

    base.mkdir(parents=True, exist_ok=True)
    snapshot_download(REPO, repo_type="dataset", local_dir=str(base), revision=REVISION)
    return base


def pairs(per_paradigm: int | None = None, base: Path | None = None) -> list[dict]:
    """Every pair, by paradigm then pair id; `per_paradigm` keeps the first n of each (a pilot).

    A pair is ``{uid, term, field, good, bad, id}``."""
    import pyarrow.parquet as pq

    out = []
    for f in sorted((ensure(base)).glob("*/train-*.parquet")):
        rows = pq.read_table(f, columns=["sentence_good", "sentence_bad", "field", "linguistics_term", "UID", "pair_id"]).to_pylist()
        rows.sort(key=lambda r: r["pair_id"])
        if per_paradigm is not None:
            rows = rows[: max(0, int(per_paradigm))]
        out.extend(
            {
                "uid": r["UID"],
                "term": r["linguistics_term"],
                "field": r["field"].replace("/", "_"),  # the files spell one paradigm's field "syntax/semantics"
                "good": r["sentence_good"],
                "bad": r["sentence_bad"],
                "id": r["pair_id"],
            }
            for r in rows
        )
    return out


def sentence_logprobs(
    ce: Callable[[np.ndarray, np.ndarray], np.ndarray],
    seqs: list[list[int]],
    batch: int = 128,
    context: int | None = None,
) -> np.ndarray:
    """The log probability (nats, negative) of each sequence: the sum over its predicted pieces.

    Each sequence starts with the start piece and every later piece is predicted once. Sequences are
    sorted by length so a batch carries little padding, and the padding is masked out. A sequence
    longer than `context` + 1 pieces cannot be read: its entry is NaN (the caller counts it)."""
    n = len(seqs)
    out = np.full(n, np.nan, dtype=np.float64)
    order = sorted((i for i in range(n) if context is None or len(seqs[i]) <= context + 1), key=lambda i: len(seqs[i]))
    for s in range(0, len(order), batch):
        idx = order[s : s + batch]
        width = max(len(seqs[i]) for i in idx) - 1
        x = np.zeros((len(idx), width), dtype=np.int32)
        y = np.zeros((len(idx), width), dtype=np.int32)
        mask = np.zeros((len(idx), width), dtype=np.float64)
        for r, i in enumerate(idx):
            q = seqs[i]
            x[r, : len(q) - 1] = q[:-1]
            y[r, : len(q) - 1] = q[1:]
            mask[r, : len(q) - 1] = 1.0
        nats = np.asarray(ce(x, y), dtype=np.float64).reshape(len(idx), width)
        out[idx] = -(nats * mask).sum(axis=1)
    return out


def score_pairs(
    ce: Callable[[np.ndarray, np.ndarray], np.ndarray],
    encode: Callable[[str], list[int]],
    start: int,
    items: list[dict],
    batch: int = 128,
    context: int | None = None,
) -> list[dict]:
    """Each pair with the two log probabilities, and whether the grammatical sentence won."""
    seqs = []
    for p in items:
        seqs.append([start, *encode(p["good"])])
        seqs.append([start, *encode(p["bad"])])
    lp = sentence_logprobs(ce, seqs, batch, context)
    rows = []
    for k, p in enumerate(items):
        g, b = float(lp[2 * k]), float(lp[2 * k + 1])
        read = not (np.isnan(g) or np.isnan(b))
        rows.append(
            {
                **{key: p[key] for key in ("uid", "term", "field", "id")},
                "good_lp": g if read else None,
                "bad_lp": b if read else None,
                "read": read,
                "correct": bool(read and g > b),
                "tie": bool(read and g == b),
            }
        )
    return rows


def summary(rows: list[dict]) -> dict:
    """The accuracies of a list of scored pairs: overall, by paradigm, by phenomenon and by field.

    A pair that could not be read (too long for the context) is left out of the accuracy and
    counted in `skipped`, never scored wrong."""
    read = [r for r in rows if r.get("read", True)]
    by_uid: dict[str, list[dict]] = defaultdict(list)
    by_term: dict[str, list[dict]] = defaultdict(list)
    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in read:
        by_uid[r["uid"]].append(r)
        by_term[r["term"]].append(r)
        by_field[r["field"]].append(r)

    def acc(rs: list[dict]) -> float:
        return sum(1 for r in rs if r["correct"]) / len(rs)

    paradigm = {u: acc(rs) for u, rs in sorted(by_uid.items())}
    term = {t: acc(rs) for t, rs in sorted(by_term.items())}
    return {
        "pairs": len(read),
        "paradigms": len(paradigm),
        "accuracy": float(np.mean(list(paradigm.values()))) if paradigm else 0.0,
        "accuracy_pairs": acc(read) if read else 0.0,
        "macro_terms": float(np.mean(list(term.values()))) if term else 0.0,
        "ties": sum(1 for r in read if r.get("tie")),
        "skipped": len(rows) - len(read),
        "by_paradigm": paradigm,
        "by_term": term,
        "by_field": {f: acc(rs) for f, rs in sorted(by_field.items())},
    }
