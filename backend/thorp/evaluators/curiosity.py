"""The curiosity ladder: six measurable precursors of curiosity in a next-token predictor.

A base model has no drive to find anything out. What it can have are the abilities curiosity is
built from, and each is a number on the held-out books (never a recipe book, except as the familiar
side of rung 2 and the fitting side of rung 4). The rungs, bottom first:

1. Knowing what it doesn't know: across held-out tokens, the correlation between the entropy of
   the model's prediction and the loss it actually takes (calibration). `r1_calibration`.
2. Noticing the strange: a difference-of-means direction in the residual stream that separates
   unfamiliar windows (held-out books) from familiar ones (recipe books), fitted on half of each
   and scored on the other half by book. `r2_novelty_auc`.
3. Learning from the page: loss late in a window minus loss early in it (`r3_icl`, negative is
   learning from context), and the loss saved on the second copy of a repeated span (`r3_copy_gain`,
   the induction-head signature).
4. Knowing a question: a direction separating questions from statements, fitted on recipe
   sentences and scored on held-out sentences, with the end punctuation removed from both so the
   question mark cannot carry it. `r4_question_auc`.
5. Expecting an answer: mean entropy over the AFTER tokens following a "?" minus the same after
   a "." or "!". Positive means the model stays uncertain after a question. `r5_expectancy`.
6. Asking: at the places a sentence ends, does the model put more probability on "?" where it was
   uncertain over the sentence than where it was sure, beyond what the text itself does there?
   log(model's high/low ratio) minus log(the text's high/low ratio). `r6_asking`.

Every rung is measured on the trained model and on the same architecture at initialisation (the
run's seed); rungs 2 and 4 also against a bag-of-tokens floor. A rung is PRESENT when it clears its
threshold and beats its floors; ABSENT otherwise; UNTESTABLE when there are too few events (for
example too few question marks in the held-out windows). The ladder is IN ORDER when no present
rung sits above an absent one (untestable rungs are skipped): the prediction is that the rungs
appear bottom first, through training and with size, and a rung present above an absent one is a
finding against the ladder.

Rows: metrics `curiosity/<measure>`, `curiosity/init/<measure>`, `curiosity/<rung>_floor_bow`,
`curiosity/rung_<k>` (1 present, 0 absent; no row when untestable), `curiosity/highest`; one
`curiosity` artifact per eval step with every value, floor, status and reason.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.probes import auc, bow_auc, dom_auc, features, windows
from thorp.models import ops

WINDOWS = 8  # per held-out book, for rungs 1, 3, 5, 6
RECIPE_BOOKS = 64  # evenly spaced recipe books used as the familiar side (rung 2) and rung 4's fit
RECIPE_WINDOWS = 4
SENTENCES = 40  # per kind (question, statement) per book, evenly spaced
SENTENCE_TOKENS = 200_000  # decode at most this much of a book to find sentences
SENTENCE_MAX = 96  # tokens kept per sentence (its end, which carries the form)
AFTER = 16  # tokens after a "?" or "." over which rung 5 averages entropy
BEFORE = 16  # tokens before a sentence end over which rung 6 measures uncertainty
MIN_EVENTS = 20
BATCH = 4

R1_MIN = 0.3  # calibration correlation
R3_ICL = -0.1  # nats, late minus early
R3_COPY = 0.5  # nats saved on the second copy
R5_MIN = 0.1  # nats
R6_MIN = 0.1  # log ratio
AUC_MIN = 0.8
FLOOR_MARGIN = 0.05  # AUC above the floors for rungs 2 and 4
INIT_MARGIN = 0.1  # above the untrained value for rungs 1, 3, 5, 6

RUNGS = {
    1: "knowing what it doesn't know",
    2: "noticing the strange",
    3: "learning from the page",
    4: "knowing a question",
    5: "expecting an answer",
    6: "asking",
}
_INIT: dict[tuple, dict] = {}  # (run, tokeniser, books) -> the untrained model's values
_SENT = re.compile(r"([A-Z][^.?!]{15,240}?)([.?!])(?=\s)")


# ---------------------------------------------------------------- the data, cut once per call


def piece_masks(tok) -> dict[str, np.ndarray]:
    """Boolean masks over the vocabulary: pieces containing "?", and sentence ends without one."""
    pieces = [tok.decode([i]) for i in range(tok.vocab_size)]
    q = np.array(["?" in p for p in pieces])
    dot = np.array([("." in p or "!" in p) and "?" not in p for p in pieces])
    return {"q": q, "dot": dot, "term": q | dot}


def sentences(tok, arr: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """(questions, statements) as token arrays, end punctuation removed, evenly spaced."""
    text = re.sub(r"\s+", " ", tok.decode(np.asarray(arr[:SENTENCE_TOKENS]).tolist()))
    qs, ss = [], []
    for m in _SENT.finditer(text):
        (qs if m.group(2) == "?" else ss if m.group(2) == "." else []).append(m.group(1).strip())

    def pick(xs):
        if len(xs) > SENTENCES:
            xs = [xs[int(i)] for i in np.linspace(0, len(xs) - 1, SENTENCES)]
        enc = [np.asarray(tok.encode(x), np.int32)[-SENTENCE_MAX:] for x in xs]
        return [e for e in enc if len(e) >= 4]

    return pick(qs), pick(ss)


def gather(ctx: EvalContext) -> dict:
    tok = ctx.tokeniser
    held = sorted({b for ids in ctx.sets.values() for b in ids})
    rec = list(ctx.recipe)
    if len(rec) > RECIPE_BOOKS:
        rec = [rec[int(i)] for i in np.linspace(0, len(rec) - 1, RECIPE_BOOKS)]
    arrs = {b: shards.load(tok.id, b, tok) for b in held + rec}
    held_w = {b: windows(arrs[b], ctx.context, WINDOWS) for b in held}
    held_w = {b: w for b, w in held_w.items() if w.size and w.shape[1] == ctx.context}
    rec_w = {b: windows(arrs[b], ctx.context, RECIPE_WINDOWS) for b in rec}
    rec_w = {b: w for b, w in rec_w.items() if w.size}
    sent = {"fit": ([], []), "test": ([], [])}
    for side, books in (("fit", rec), ("test", held)):
        for b in books:
            q, s = sentences(tok, arrs[b])
            sent[side][0].extend(q)
            sent[side][1].extend(s)
    return {"held": held_w, "recipe": rec_w, "sent": sent, "masks": piece_masks(tok)}


# ---------------------------------------------------------------- the measures


def token_stats(model, w: np.ndarray, qmask: np.ndarray) -> dict[str, np.ndarray]:
    """Per predicted position: entropy, loss, and the probability put on "?" pieces."""
    x, y = w[:, :-1], w[:, 1:]
    H, CE, PQ = [], [], []
    for i in range(0, len(x), BATCH):
        h, ce, pq = ops.token_stats(model, x[i : i + BATCH], y[i : i + BATCH], qmask)
        H.append(h)
        CE.append(ce)
        PQ.append(pq)
    return {
        "H": np.concatenate(H),
        "CE": np.concatenate(CE),
        "PQ": np.concatenate(PQ),
        "x": x,
        "y": y,
    }


def _ce(model, x, y) -> np.ndarray:
    """(batch, time) nats on each target, as log-softmax read at the target."""
    if ops.is_torch(model):
        return ops.token_ce(model, x, y)
    import mlx.core as mx

    lg = model(mx.array(x)).astype(mx.float32)
    logp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
    ce = -mx.take_along_axis(logp, mx.array(y)[..., None], axis=-1)[..., 0]
    mx.eval(ce)
    return np.array(ce)


def copy_gain(model, w: np.ndarray) -> float:
    """Loss on the first copy of a span minus loss on its repeat, same positions within the span."""
    span = w.shape[1] // 4
    seq = np.concatenate([w[:, :span], w[:, :span]], axis=1)
    x, y = seq[:, :-1], seq[:, 1:]
    first, second = [], []
    for i in range(0, len(x), BATCH):
        ce = _ce(model, x[i : i + BATCH], y[i : i + BATCH])
        first.append(ce[:, : span - 1])  # predicting copy-one tokens 1 .. span-1
        second.append(ce[:, span:])  # predicting copy-two tokens 1 .. span-1
    return float(np.concatenate(first).mean() - np.concatenate(second).mean())


def sentence_features(model, sents: list[np.ndarray]) -> np.ndarray:
    """(sentences, layers, width): residual stream mean-pooled over each sentence's own tokens.
    Right padding is harmless: the model is causal, and the pool ignores the padded positions."""
    out = []
    for i in range(0, len(sents), 32):
        chunk = sents[i : i + 32]
        L = max(len(s) for s in chunk)
        x = np.zeros((len(chunk), L), np.int32)
        m = np.zeros((len(chunk), L, 1), np.float32)
        for j, s in enumerate(chunk):
            x[j, : len(s)] = s
            m[j, : len(s)] = 1
        out.append(ops.pooled_hidden(model, x, m))
    return np.concatenate(out) if out else np.zeros((0, 0, 0), np.float32)


def measure(model, data: dict) -> dict:
    """Every rung's raw value for one model. NaN where the data cannot support the measure."""
    v: dict[str, float] = {}
    masks = data["masks"]
    held = list(data["held"])
    W = np.concatenate([data["held"][b] for b in held]) if held else np.zeros((0, 0), np.int32)
    if len(W):
        st = token_stats(model, W, masks["q"])
        H, CE, PQ, x, y = st["H"], st["CE"], st["PQ"], st["x"], st["y"]
        T = H.shape[1]
        # rung 1
        v["r1_calibration"] = float(np.corrcoef(H.ravel(), CE.ravel())[0, 1])
        v["r1_gap"] = float(CE.mean() - H.mean())
        # rung 3
        early, late = slice(max(1, T // 32), max(2, T // 16)), slice(T // 2, T)
        v["r3_icl"] = float(CE[:, late].mean() - CE[:, early].mean())
        v["r3_copy_gain"] = copy_gain(model, W)
        # rung 5: the entropy of the next AFTER predictions, from the position of a "?" or a "."
        after = {"q": [], "dot": []}
        for kind in after:
            rows, cols = np.nonzero(masks[kind][x[:, : T - AFTER]])
            after[kind] = [H[r, c : c + AFTER].mean() for r, c in zip(rows, cols, strict=True)]
        v["r5_n_q"] = float(len(after["q"]))
        v["r5_expectancy"] = (
            float(np.mean(after["q"]) - np.mean(after["dot"]))
            if len(after["q"]) >= MIN_EVENTS and len(after["dot"]) >= MIN_EVENTS
            else float("nan")
        )
        # rung 6: positions whose true next token ends a sentence, split at the median uncertainty
        rows, cols = np.nonzero(masks["term"][y])
        keep = cols >= BEFORE
        rows, cols = rows[keep], cols[keep]
        is_q = masks["q"][y[rows, cols]]
        v["r6_n_q"] = float(is_q.sum())
        if len(rows) >= 2 * MIN_EVENTS and is_q.sum() >= MIN_EVENTS:
            u = np.array([H[r, c - BEFORE : c].mean() for r, c in zip(rows, cols, strict=True)])
            hi = u > np.median(u)
            pq = PQ[rows, cols]
            eps = 1e-6
            model_ratio = (pq[hi].mean() + eps) / (pq[~hi].mean() + eps)
            text_ratio = (is_q[hi].mean() + eps) / (is_q[~hi].mean() + eps)
            v["r6_asking"] = float(math.log(model_ratio) - math.log(text_ratio))
        else:
            v["r6_asking"] = float("nan")
    # rung 2: familiar (recipe) against unfamiliar (held-out), fitted and scored on alternate books
    rec = list(data["recipe"])
    fam = {b: features(model, data["recipe"][b]) for b in rec}
    unf = {b: features(model, data["held"][b]) for b in held}
    cat = lambda d, bs: np.concatenate([d[b] for b in bs]) if bs else None  # noqa: E731
    P, N = cat(unf, held[0::2]), cat(fam, rec[0::2])
    TP, TN = cat(unf, held[1::2]), cat(fam, rec[1::2])
    v["r2_novelty_auc"] = (
        float(np.nanmax(dom_auc(P, N, TP, TN)))
        if all(a is not None and len(a) for a in (P, N, TP, TN))
        else float("nan")
    )
    # rung 4: questions against statements, fitted on recipe sentences, scored on held-out ones
    (fq, fs), (tq, ts) = data["sent"]["fit"], data["sent"]["test"]
    if min(len(fq), len(fs), len(tq), len(ts)) >= MIN_EVENTS:
        sf = lambda ss: sentence_features(model, ss)  # noqa: E731
        v["r4_question_auc"] = float(np.nanmax(dom_auc(sf(fq), sf(fs), sf(tq), sf(ts))))
    else:
        v["r4_question_auc"] = float("nan")
    return v


def floors_bow(data: dict, vocab: int) -> dict[str, float]:
    """The bag-of-tokens floors for the two probe rungs (they do not depend on the model)."""
    held, rec = list(data["held"]), list(data["recipe"])
    rows = lambda d, bs: [r for b in bs for r in d[b]]  # noqa: E731
    out = {
        "r2": bow_auc(
            rows(data["held"], held[0::2]),
            rows(data["recipe"], rec[0::2]),
            rows(data["held"], held[1::2]),
            rows(data["recipe"], rec[1::2]),
            vocab,
        )
        if held and rec
        else float("nan")
    }
    (fq, fs), (tq, ts) = data["sent"]["fit"], data["sent"]["test"]
    out["r4"] = (
        bow_auc(fq, fs, tq, ts, vocab)
        if min(len(fq), len(fs), len(tq), len(ts)) >= MIN_EVENTS
        else float("nan")
    )
    return out


# ---------------------------------------------------------------- the verdict


def _nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def judge(v: dict, v0: dict, bow: dict) -> dict[int, dict]:
    """Each rung's status, present / absent / untestable, with the reason, from the trained values
    v, the untrained values v0 and the bag-of-tokens floors."""
    out: dict[int, dict] = {}

    def above_init(key, sign=1):
        return _nan(v0.get(key)) or sign * (v[key] - v0[key]) >= INIT_MARGIN

    def rung(k, keys, ok, why):
        if any(_nan(v.get(key)) for key in keys):
            out[k] = {"status": "untestable", "reason": "too few events or books for the measure"}
        else:
            out[k] = {"status": "present" if ok() else "absent", "reason": why()}

    rung(
        1,
        ["r1_calibration"],
        lambda: v["r1_calibration"] >= R1_MIN and above_init("r1_calibration"),
        lambda: (
            f"r = {v['r1_calibration']:.3f} (untrained {v0.get('r1_calibration', float('nan')):.3f}; needs {R1_MIN})"
        ),
    )
    for k, key in ((2, "r2_novelty_auc"), (4, "r4_question_auc")):
        f = bow[f"r{k}"]
        known = [x for x in (f, v0.get(key)) if not _nan(x)]
        floor = max(known) if known else 0.5
        rung(
            k,
            [key],
            lambda key=key, floor=floor: v[key] >= AUC_MIN and v[key] >= floor + FLOOR_MARGIN,
            lambda key=key, f=f: (
                f"AUC {v[key]:.3f}; floors: tokens {f:.3f}, untrained {v0.get(key, float('nan')):.3f}"
            ),
        )
    rung(
        3,
        ["r3_icl", "r3_copy_gain"],
        lambda: (
            v["r3_icl"] <= R3_ICL
            and v["r3_copy_gain"] >= R3_COPY
            and above_init("r3_icl", -1)
            and above_init("r3_copy_gain")
        ),
        lambda: f"late minus early {v['r3_icl']:+.3f} nats, copy gain {v['r3_copy_gain']:.3f} nats",
    )
    rung(
        5,
        ["r5_expectancy"],
        lambda: v["r5_expectancy"] >= R5_MIN and above_init("r5_expectancy"),
        lambda: f"{v['r5_expectancy']:+.3f} nats over {int(v['r5_n_q'])} question marks",
    )
    rung(
        6,
        ["r6_asking"],
        lambda: v["r6_asking"] >= R6_MIN and above_init("r6_asking"),
        lambda: f"{v['r6_asking']:+.3f} log ratio over {int(v['r6_n_q'])} question ends",
    )
    return out


def in_order(status: dict[int, dict]) -> tuple[bool, int]:
    """(no present rung above an absent one, the highest present rung or 0). Untestable rungs are
    skipped."""
    seen_absent, ok, highest = False, True, 0
    for k in sorted(status):
        s = status[k]["status"]
        if s == "absent":
            seen_absent = True
        elif s == "present":
            highest = k
            ok = ok and not seen_absent
    return ok, highest


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    data = gather(ctx)
    v = measure(ctx.model, data)
    v0: dict = {}
    if ctx.init_model is not None:
        key = (
            ctx.run_id,
            ctx.tokeniser.id,
            tuple(sorted(data["held"])),
            tuple(sorted(data["recipe"])),
        )
        if key not in _INIT:
            _INIT[key] = measure(ctx.init_model(), data)
        v0 = _INIT[key]
    bow = floors_bow(data, ctx.tokeniser.vocab_size)
    status = judge(v, v0, bow)
    ordered, highest = in_order(status)
    for k, x in v.items():
        if not _nan(x):
            out.metrics[f"curiosity/{k}"] = x
    for k, x in v0.items():
        if not _nan(x):
            out.metrics[f"curiosity/init/{k}"] = x
    for k, x in bow.items():
        if not _nan(x):
            out.metrics[f"curiosity/{k}_floor_bow"] = x
    for k, s in status.items():
        if s["status"] != "untestable":
            out.metrics[f"curiosity/rung_{k}"] = float(s["status"] == "present")
    out.metrics["curiosity/highest"] = float(highest)
    clean = lambda d: {k: (None if _nan(x) else x) for k, x in d.items()}  # noqa: E731
    text = json.dumps(
        {
            "rungs": {str(k): {"name": RUNGS[k], **status[k]} for k in status},
            "in_order": ordered,
            "highest": highest,
            "values": clean(v),
            "untrained": clean(v0),
            "floor_bow": clean(bow),
            "events": {
                "held_books": len(data["held"]),
                "recipe_books": len(data["recipe"]),
                "sentences": {
                    "fit": [len(data["sent"]["fit"][0]), len(data["sent"]["fit"][1])],
                    "test": [len(data["sent"]["test"][0]), len(data["sent"]["test"][1])],
                },
            },
            "thresholds": {
                "r1": R1_MIN,
                "r3_icl": R3_ICL,
                "r3_copy": R3_COPY,
                "r5": R5_MIN,
                "r6": R6_MIN,
                "auc": AUC_MIN,
                "floor_margin": FLOOR_MARGIN,
                "init_margin": INIT_MARGIN,
            },
        },
        ensure_ascii=False,
    )
    out.artifacts.append(
        {
            "kind": "curiosity",
            "path": "",
            "sha1": hashlib.sha1(text.encode()).hexdigest(),
            "text": text,
        }
    )
    return out


__all__ = ["auc", "evaluate", "in_order", "judge", "measure"]
