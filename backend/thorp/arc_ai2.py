"""AI2 ARC, the one peer-recognised test for models under 1B (11 November, Justin: "I'd prefer the ARC
easy challenge"): grade-school science questions, four ways each, in the two splits the field names --
ARC-Easy and ARC-Challenge.

BLiMP held this title for a day (``thorp/blimp.py``). It stays the grammatical reading; ARC is the
capability one, and it is the test the field's own numbers are quoted from:

    ARC-Easy       2,376 questions, the ones a retrieval baseline and a word-overlap guess can get
    ARC-Challenge  1,172 questions, the ones neither can

Chance is 25% (four options), and the two splits are read quite differently at this size: Easy has a
gradient across the band (about 26-30% at 14-70M, 33% by 410M and 40% by 1B), while Challenge sits at
its floor for everything under 1B and can rank nothing there. Easy is the anchor; Challenge is kept
because a reading that is at its floor is still a reading, and a bigger ship will move it.

There are no letters. A ship of this fleet carries a 2,048-word Ogden vocabulary, so " A" may not be a
piece at all: each option's own text is read as the continuation of the question, and the option with
the lowest mean loss a piece is the bet. A question whose options cannot all be spelt by the ship's
tokeniser is skipped and counted, never scored wrong -- the same rule as a BLiMP pair too long for the
window. Format, so it is never mistaken for the papers' 25-shot letter reading: zero-shot, the option
text as the continuation, mean loss over the option's own pieces (length normalised, "acc_norm" in
lm-evaluation-harness's terms), no chain of thought and no generation.

Clark et al., "Think you have Solved Question Answering? Try ARC, the AI2 Reasoning Challenge",
arXiv:1803.05457, 2018. The data is CC BY-SA 4.0, ``allenai/ai2_arc`` on Hugging Face, pinned to one
revision below and fetched once into ``data/arc-ai2`` (THORP_ARC_AI2 overrides it), as ARC-AGI-2 is
into ``data/arc-agi-2``.

This module is the shared plumbing, so the evaluator (``thorp/evaluators/arc_ai2.py``) and the
outside-model scorer (``scripts/score_arc_ai2.py``) read the benchmark one way. It knows nothing of
any model: a model is a function ``ce(x, y) -> (batch, time) nats``.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from thorp import paths

REPO = "allenai/ai2_arc"
REVISION = "210d026faf9955653af8916fad021475a3f00453"  # the revision read on 11 November 2026
CONFIGS = {"easy": "ARC-Easy", "challenge": "ARC-Challenge"}
PARTS = ("test", "validation")
CHANCE = 0.25
COUNTS = {("easy", "test"): 2376, ("easy", "validation"): 570, ("challenge", "test"): 1172, ("challenge", "validation"): 299}


def root() -> Path:
    """Where the ARC files live (``data/arc-ai2`` by default, THORP_ARC_AI2 overrides it)."""
    return Path(os.environ.get("THORP_ARC_AI2") or paths.resolve("data/arc-ai2"))


def ensure(base: Path | None = None) -> Path:
    """The ARC files, downloaded once (about 1 MB) at the pinned revision. Returns the root."""
    base = Path(base) if base else root()
    want = [base / cfg / f"{part}-00000-of-00001.parquet" for cfg in CONFIGS.values() for part in PARTS]
    if all(p.exists() for p in want):
        return base
    from huggingface_hub import snapshot_download

    base.mkdir(parents=True, exist_ok=True)
    snapshot_download(REPO, repo_type="dataset", local_dir=str(base), revision=REVISION)
    return base


def _cfg(config: str) -> str:
    key = str(config).lower().replace("arc-", "").replace("_", "-")
    if key not in CONFIGS:
        raise KeyError(f"unknown ARC config {config!r}: one of {sorted(CONFIGS)}")
    return CONFIGS[key]


def _path(config: str, part: str, base: Path | None = None) -> Path:
    if part not in PARTS:
        raise KeyError(f"unknown ARC part {part!r}: one of {PARTS}")
    base = Path(base) if base else root()
    p = base / _cfg(config) / f"{part}-00000-of-00001.parquet"
    # a checkout that holds the file is read as it is; one that does not is fetched once (the boxed
    # copy is complete, so a test can hand in a part and never touch the network)
    return p if p.exists() else ensure(base) / _cfg(config) / p.name


def questions(config: str = "easy", part: str = "test", per_split: int | None = None, base: Path | None = None) -> list[dict]:
    """Every question of a split, by id; `per_split` keeps the first n (a pilot).

    A question is ``{id, config, part, question, options, answer}``, the options in the file's own
    order and `answer` their index. The file's labels are dropped: they are letters, and a ship that
    cannot spell them must not be asked to."""
    import pyarrow.parquet as pq

    table = pq.read_table(_path(config, part, base), columns=["id", "question", "choices", "answerKey"])
    rows = sorted(table.to_pylist(), key=lambda r: str(r["id"]))
    out = []
    for r in rows:
        ch = r.get("choices") or {}
        texts = [str(t).strip() for t in (ch.get("text") or [])]
        labels = [str(x).strip() for x in (ch.get("label") or [])]
        key = str(r.get("answerKey") or "").strip()
        if len(texts) < 2 or key not in labels or len(labels) != len(texts):
            continue
        opts = texts
        want = labels.index(key)  # the file's own order, so the answer is the label's position
        out.append(
            {
                "id": str(r["id"]),
                "config": _cfg(config).lower().replace("arc-", ""),
                "part": part,
                "question": str(r["question"]).strip(),
                "options": opts,
                "answer": want,
            }
        )
        if per_split is not None and len(out) >= max(0, int(per_split)):
            break
    return out


def stem(q: dict) -> str:
    """The question as a ship reads it: the question, then the answer, with no letters and no examples."""
    return f"Question: {q['question']}\nAnswer:"


def score_questions(
    ce,
    encode,
    start: int,
    items: list[dict],
    batch: int = 64,
    context: int | None = None,
) -> list[dict]:
    """Each question with the mean loss of every option, and whether the right one was the lowest.

    An option is the continuation ``" " + text`` of the question's stem, and only its own pieces are
    paid for: the stem is the same for every option of a question, so it cannot change which one wins.
    A question with an option the tokeniser cannot spell (an empty sequence) is not read: its row is
    ``read: False`` and it is counted in ``skipped``."""
    flat = []  # (item index, option index, stem pieces, option pieces)
    for i, q in enumerate(items):
        head = [start, *encode(stem(q))]
        opts = [encode(" " + o) for o in q["options"]]
        if any(not o for o in opts):
            continue
        if context is not None and max(len(head) - 1 + len(o) for o in opts) > context:
            continue
        for j, o in enumerate(opts):
            flat.append((i, j, head, o))
    out: list[list[float]] = [[float("nan")] * len(q["options"]) for q in items]
    for s in range(0, len(flat), max(1, batch)):
        chunk = flat[s : s + max(1, batch)]
        width = max(len(head) - 1 + len(o) for _, _, head, o in chunk)
        x = np.zeros((len(chunk), width), dtype=np.int32)
        y = np.zeros((len(chunk), width), dtype=np.int32)
        mask = np.zeros((len(chunk), width), dtype=np.float64)
        for r, (_, _, head, o) in enumerate(chunk):
            seq = [*head, *o]
            n = len(o)  # the last n predicted pieces are the option's
            x[r, : len(seq) - 1] = seq[:-1]
            y[r, : len(seq) - 1] = seq[1:]
            mask[r, len(seq) - 1 - n : len(seq) - 1] = 1.0
        nats = np.asarray(ce(x, y), dtype=np.float64).reshape(len(chunk), width)
        for r, (i, j, _, o) in enumerate(chunk):
            out[i][j] = float((nats[r] * mask[r]).sum() / len(o))
    rows = []
    for q, ces in zip(items, out, strict=False):
        read = all(not np.isnan(c) for c in ces)
        order = np.argsort(ces) if read else None
        pred = int(order[0]) if read else None
        rows.append(
            {
                "id": q["id"],
                "config": q["config"],
                "part": q["part"],
                "answer": q["answer"],
                "n": len(q["options"]),
                "ce": [c if not np.isnan(c) else None for c in ces],
                "read": read,
                "prediction": pred,
                "correct": bool(read and pred == q["answer"]),
                "margin": float(ces[order[1]] - ces[order[0]]) if read and len(ces) > 1 else None,
            }
        )
    return rows


def summary(rows: list[dict]) -> dict:
    """The accuracy of a list of scored questions, and how many could not be read.

    A question too long for the window or with an unspellable option is left out of the accuracy and
    counted in `skipped`, never scored wrong."""
    read = [r for r in rows if r.get("read", True)]
    right = [r for r in read if r["correct"]]
    return {
        "questions": len(read),
        "skipped": len(rows) - len(read),
        "correct": len(right),
        "accuracy": (len(right) / len(read)) if read else 0.0,
        "chance": CHANCE,
        "excess": ((len(right) / len(read)) - CHANCE) if read else 0.0,
        "margin_mean": float(np.mean([r["margin"] for r in read if r.get("margin") is not None])) if read else 0.0,
    }
