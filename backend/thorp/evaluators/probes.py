"""Trait probes: is there a direction in the residual stream that separates a trait on unseen books?

The question version 0.1 asks (D19) in the only form a 9M base model can answer. For each trait the
shelf carries a label for (fiction, verse, first person, and each language family against the
rest), take a few windows from every recipe book, mean-pool the residual stream after each layer,
and set the direction at that layer to mean(trait) - mean(not trait): the persona-vector recipe,
difference of means. Then project windows from the held-out books, which neither the model nor
the direction has seen, and score the separation as an AUC. A trait is FOUND when some layer's
held-out AUC reaches AUC_FOUND with at least MIN_BOOKS books on each side of the held-out set, so
a direction can never be a book-identity direction in disguise. Everything is deterministic: the
windows are evenly spaced, nothing is sampled.

Two floors (2026-11-06, late): the same difference-of-means probe on a bag of tokens (each window's
token histogram, so it sees which tokens occur and nothing the model built), and on the model at
initialisation with the run's own seed (the architecture with nothing learned). A found trait is
EMERGENT only when its best held-out AUC clears both floors by EMERGE_MARGIN; a trait the floors
also find was in the token statistics, not in what the model learned.

Rows: metrics `probe/<trait>/layer_<i>` (held-out AUC), `probe/<trait>/best`, `probe/<trait>/floor_bow`
and `probe/<trait>/floor_init`; one `probes` artifact per eval step with every trait's status,
found / not_found / untestable, the reason, the floors and whether it is emergent.
"""

from __future__ import annotations

import csv
import hashlib
import json

import numpy as np

from thorp import manifest, paths, shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.models import ops

TRAITS_CSV = "lists/traits.csv"
TRAIT_COLUMNS = ("fiction", "verse", "first_person")
WINDOWS_TRAIN = 8  # per recipe book
WINDOWS_TEST = 16  # per held-out book
AUC_FOUND = 0.8
MIN_BOOKS = 2  # per side of the held-out set
MIN_TOKENS = 32
EMERGE_MARGIN = 0.05  # a trait must beat both floors by this much AUC to count as emergent
_INIT_FEATS: dict[tuple, dict] = {}  # (run, tokeniser, books) -> untrained features, built once


def load_traits(path: str = TRAITS_CSV) -> dict[str, dict[str, int]]:
    """title -> {trait: 0/1}. Titles are the list titles, which the manifest carries."""
    p = paths.resolve(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8", newline="") as f:
        return {
            r["title"]: {t: int(r[t]) for t in TRAIT_COLUMNS if r.get(t, "") != ""}
            for r in csv.DictReader(f)
        }


def windows(arr: np.ndarray, context: int, n: int) -> np.ndarray:
    """n evenly spaced windows of `context` tokens (fewer, or one shorter window, for a short book)."""
    arr = np.asarray(arr, dtype=np.int32)
    if len(arr) < context:
        return arr[None, :] if len(arr) >= MIN_TOKENS else np.zeros((0, 0), np.int32)
    n = max(1, min(n, len(arr) // context))
    starts = np.linspace(0, len(arr) - context, n).astype(int)
    return np.stack([arr[s : s + context] for s in starts])


def pooled(model, arr: np.ndarray, context: int, n: int) -> np.ndarray:
    """(windows, layers, width): the residual stream after each layer, mean-pooled over time."""
    return features(model, windows(arr, context, n))


def features(model, w: np.ndarray) -> np.ndarray:
    """Mean-pooled residual stream of ready-cut windows, (windows, layers, width)."""
    if w.size == 0:
        return np.zeros((0, 0, 0), np.float32)
    return ops.pooled_hidden(model, w)


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Probability that a random positive scores above a random negative (ties count half)."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def dom_auc(P: np.ndarray, N: np.ndarray, TP: np.ndarray, TN: np.ndarray) -> list[float]:
    """Held-out AUC per layer of the difference-of-means direction fitted on P against N.
    Arrays are (items, layers, width)."""
    d = P.mean(axis=0) - N.mean(axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-8
    return [auc(TP[:, i] @ d[i], TN[:, i] @ d[i]) for i in range(P.shape[1])]


def bow_auc(tr_pos: list, tr_neg: list, te_pos: list, te_neg: list, vocab: int) -> float:
    """The bag-of-tokens floor: the same probe on token histograms. Each item is a 1-D token
    array; its histogram is normalised by its length, so the projection is the mean of the
    direction over the item's tokens and no (items, vocab) matrix is ever built."""
    if not all((tr_pos, tr_neg, te_pos, te_neg)):
        return float("nan")

    def mean_hist(items):
        h = np.zeros(vocab, np.float64)
        for w in items:
            h += np.bincount(np.asarray(w).ravel(), minlength=vocab)[:vocab] / max(1, np.size(w))
        return h / len(items)

    d = mean_hist(tr_pos) - mean_hist(tr_neg)
    proj = lambda items: np.array([d[np.asarray(w).ravel()].mean() for w in items])  # noqa: E731
    return auc(proj(te_pos), proj(te_neg))


def rows_of(wins: dict[str, np.ndarray], books: list[str]) -> list[np.ndarray]:
    return [row for b in books if b in wins for row in wins[b]]


def probe(
    feats: dict[str, np.ndarray], labels: dict[str, int], train: list[str], test: list[str]
) -> dict:
    """One trait: fit the direction on `train` books, score it on `test` books, per layer."""
    tr_pos = [b for b in train if labels.get(b) == 1 and b in feats]
    tr_neg = [b for b in train if labels.get(b) == 0 and b in feats]
    te_pos = [b for b in test if labels.get(b) == 1 and b in feats]
    te_neg = [b for b in test if labels.get(b) == 0 and b in feats]
    out = {
        "n_train": [len(tr_pos), len(tr_neg)],
        "n_test": [len(te_pos), len(te_neg)],
        "test_books": {"pos": te_pos, "neg": te_neg},
    }
    if not tr_pos or not tr_neg:
        return {**out, "status": "untestable", "reason": "no books on one side of the shelf"}
    if len(te_pos) < MIN_BOOKS or len(te_neg) < MIN_BOOKS:
        return {
            **out,
            "status": "untestable",
            "reason": f"fewer than {MIN_BOOKS} held-out books on one side",
        }
    cat = lambda ids: np.concatenate([feats[b] for b in ids])  # noqa: E731
    P, N, TP, TN = cat(tr_pos), cat(tr_neg), cat(te_pos), cat(te_neg)
    layers = P.shape[1]
    direction = P.mean(axis=0) - N.mean(axis=0)  # (layers, width)
    direction /= np.linalg.norm(direction, axis=1, keepdims=True) + 1e-8
    auc_test, auc_train = [], []
    for i in range(layers):
        d = direction[i]
        auc_test.append(auc(TP[:, i] @ d, TN[:, i] @ d))
        auc_train.append(auc(P[:, i] @ d, N[:, i] @ d))
    best = int(np.nanargmax(auc_test))
    found = auc_test[best] >= AUC_FOUND
    return {
        **out,
        "status": "found" if found else "not_found",
        "reason": f"best held-out AUC {auc_test[best]:.3f} at layer {best}",
        "best_layer": best,
        "auc": auc_test,
        "auc_train": auc_train,
    }


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    tok = ctx.tokeniser
    train = list(ctx.recipe)
    test = sorted({b for ids in ctx.sets.values() for b in ids})
    books = manifest.get_many(train + test)
    traits = load_traits()

    wins: dict[str, np.ndarray] = {}
    for b in train + test:
        w = windows(
            shards.load(tok.id, b, tok), ctx.context, WINDOWS_TRAIN if b in train else WINDOWS_TEST
        )
        if w.size:
            wins[b] = w
    feats = {b: features(ctx.model, w) for b, w in wins.items()}
    init_feats, floor_error = None, None
    if ctx.init_model is not None:
        key = (ctx.run_id, tok.id, tuple(sorted(wins)))
        try:
            if key not in _INIT_FEATS:
                m0 = ctx.init_model()
                _INIT_FEATS[key] = {b: features(m0, w) for b, w in wins.items()}
            init_feats = _INIT_FEATS[key]
        except Exception as e:  # noqa: BLE001 - a floor must never fail the training run it rides on
            floor_error = f"untrained floor: {e.__class__.__name__}: {e}"

    labels: dict[str, dict[str, int]] = {}
    for t in TRAIT_COLUMNS:
        labels[t] = {
            b: traits[books[b].title][t]
            for b in books
            if books[b].title in traits and t in traits[books[b].title]
        }
    for fam in sorted({books[b].family for b in books if books[b].family}):
        labels[f"family/{fam}"] = {b: int(books[b].family == fam) for b in books}

    results = {}
    for name, lab in labels.items():
        r = probe(feats, lab, train, test)
        results[name] = r
        if "auc" in r:
            for i, a in enumerate(r["auc"]):
                out.metrics[f"probe/{name}/layer_{i}"] = a
            out.metrics[f"probe/{name}/best"] = max(r["auc"])
            try:
                side = lambda books, v, lab=lab: [b for b in books if lab.get(b) == v]  # noqa: E731
                r["floor_bow"] = bow_auc(
                    rows_of(wins, side(train, 1)),
                    rows_of(wins, side(train, 0)),
                    rows_of(wins, side(test, 1)),
                    rows_of(wins, side(test, 0)),
                    tok.vocab_size,
                )
                out.metrics[f"probe/{name}/floor_bow"] = r["floor_bow"]
                floors = [r["floor_bow"]]
                if init_feats is not None:
                    r0 = probe(init_feats, lab, train, test)
                    if "auc" in r0:
                        r["floor_init"] = float(np.nanmax(r0["auc"]))
                        out.metrics[f"probe/{name}/floor_init"] = r["floor_init"]
                        floors.append(r["floor_init"])
                top = float(np.nanmax(r["auc"]))
                r["emergent"] = bool(
                    r["status"] == "found"
                    and all(not np.isnan(f) for f in floors)
                    and top >= max(floors) + EMERGE_MARGIN
                )
            except Exception as e:  # noqa: BLE001 - recorded on the trait, never fatal to the run
                r["floor_error"] = f"{e.__class__.__name__}: {e}"
            if floor_error:
                r["floor_error"] = floor_error
    text = json.dumps(
        {
            "auc_found": AUC_FOUND,
            "min_books": MIN_BOOKS,
            "emerge_margin": EMERGE_MARGIN,
            "test_sets": sorted(ctx.sets),
            "traits": results,
        },
        ensure_ascii=False,
    )
    out.artifacts.append(
        {
            "kind": "probes",
            "path": "",
            "sha1": hashlib.sha1(text.encode()).hexdigest(),
            "text": text,
        }
    )
    return out
