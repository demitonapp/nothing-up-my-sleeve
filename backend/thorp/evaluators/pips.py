"""The deck's four uncharted cards, charted (Justin, 2026-11-07 22:10: "add support for premise marker, order word,
number spotter, the counter ... the next voyage can inherit them"). Read on the judge books (the held-out decks a
voyage is scored on and never reads): WINDOWS_PER_BOOK windows of up to WINDOW pieces from each, the same for
every class and every reading, so the rarer words (order words, premise markers) are seen hundreds of times.

Three Basics, read as the delimiter is (stars.py): a head's attention on one class of word pieces over that class's
share of the keys each query can see (1 is indifferent; the mark is 3, as the delimiter's):

- **number-spotter** (♦): numerals and number words (one ... twelve, twenty ... hundred, thousand, million).
- **order-word** (♦): the words of order and comparison (more, less, before, after, than, first, last, next, most,
  least, bigger, smaller, greater, larger, higher, lower, earlier, later, better, worse).
- **premise-marker** (♣): the words that open or close a premise (if, when, because, since, unless, so, therefore,
  hence, thus, then).

A piece belongs to a class when its text, stripped and lowercased, is one of the class's words: whole-word pieces,
which these common words are in a 2,048-piece tokeniser.

One Face, read by its ability:

- **the counter** (♥): does the model know how far into a sentence it is? A ridge regression from the residual
  stream after each layer to each piece's word position in its sentence (words since the last . ! ? or line
  break), fitted on every other window and scored (R²) on the rest, so each judge book is on both sides; the
  best layer's R². The mark is 0.5.

Metrics: `stars/<card>/max_score`, `/count` (heads at the mark), `/best_layer`, `/best_head` for the three Basics;
`counter/probe_r2` and `counter/best_layer`. Artifact `pips`: the layer x head matrices and the counter's R² by layer.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from thorp.evaluators import EvalContext, EvalResult

MARK = 3.0
COUNTER_MARK = 0.5
WINDOWS_PER_BOOK = 4
WINDOW = 256
BATCH = 8
CLASSES = {
    "number_spotter": {
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "twenty", "thirty", "forty", "fifty", "hundred", "thousand", "million",
    },
    "order_word": {
        "more", "less", "before", "after", "than", "first", "last", "next", "most", "least", "bigger", "smaller",
        "greater", "larger", "higher", "lower", "earlier", "later", "better", "worse",
    },
    "premise_marker": {"if", "when", "because", "since", "unless", "so", "therefore", "hence", "thus", "then"},
}  # fmt: skip
_flags: dict[tuple[str, str], np.ndarray] = {}


def flags(tok, key: str) -> np.ndarray:
    """A bool per vocabulary id: the piece is one of the class's words (numerals too, for number-spotter)."""
    k = (tok.id, key)
    if k not in _flags:
        from thorp.evaluators.bpb_split import piece_bytes

        words = CLASSES[key]
        out = []
        for b in piece_bytes(tok):
            t = b.decode("utf-8", errors="ignore").strip().lower()
            out.append(t in words or (key == "number_spotter" and t.isdigit()))
        _flags[k] = np.array(out, dtype=bool)
    return _flags[k]


def class_ratio(pats: list[np.ndarray], keys: np.ndarray) -> np.ndarray:
    """(layers, heads): attention mass on the flagged keys over their share of the keys before each query."""
    T = keys.shape[1]
    keys = keys.copy()
    keys[:, 0] = False
    causal = np.tril(np.ones((T, T), dtype=bool), k=-1)[None, None]
    share = (keys[:, None, None, :] & causal).sum(-1) / np.maximum(causal.sum(-1), 1)  # (b, 1, T)
    out = []
    for p in pats:
        mass = (p * keys[:, None, None, :]).sum(-1)  # (b, h, T)
        ok = share[..., 1:] > 0
        r = np.where(ok, mass[..., 1:] / np.where(ok, share[..., 1:], 1), np.nan)
        out.append(np.nanmean(r, axis=(0, 2)) if ok.any() else np.zeros(p.shape[1]))
    return np.nan_to_num(np.array(out))


def sentence_positions(tok, toks: np.ndarray) -> np.ndarray:
    """(b, T): each piece's word position in its sentence (words since the last . ! ? or line break)."""
    from thorp.evaluators.bpb_split import piece_bytes

    texts = [b.decode("utf-8", errors="ignore") for b in piece_bytes(tok)]
    out = np.zeros(toks.shape, dtype=np.float32)
    for i, row in enumerate(toks):
        n = 0
        for j, t in enumerate(row):
            s = texts[int(t)] if int(t) < len(texts) else ""
            if any(c in s for c in ".!?\n"):
                n = 0
            elif s[:1] == " " and any(c.isalpha() for c in s):
                n += 1
            out[i, j] = n
    return out


def windows(tok, books: list[str], context: int) -> np.ndarray | None:
    """WINDOWS_PER_BOOK windows of up to WINDOW pieces from each judge book (a third and two thirds of the way in),
    each opened with EOS: (n, T)."""
    from thorp import shards

    L = min(WINDOW, context - 1)
    out = []
    for b in books:
        arr = np.asarray(shards.load(tok.id, b, tok))
        if len(arr) <= L + 2:
            continue
        for w in range(1, WINDOWS_PER_BOOK + 1):
            s = int(len(arr) * w / (WINDOWS_PER_BOOK + 1))
            s = min(s, len(arr) - L - 1)
            out.append(np.concatenate([[tok.eos_id], arr[s : s + L]]))
    return np.stack(out).astype(np.int32) if out else None


def batched_patterns(model, toks: np.ndarray) -> list[np.ndarray]:
    from thorp.evaluators.stars import patterns

    parts = [patterns(model, toks[i : i + BATCH]) for i in range(0, len(toks), BATCH)]
    return [np.concatenate([p[layer] for p in parts], axis=0) for layer in range(len(parts[0]))]


def counter_r2(model, toks: np.ndarray, target: np.ndarray, lam: float = 1000.0) -> list[float]:
    """The best linear read of sentence position from the residual stream after each layer: R² on held-out windows
    (every other window fits, the rest score)."""
    import mlx.core as mx

    states = []
    for i in range(0, len(toks), BATCH):
        hs = model.hidden(mx.array(toks[i : i + BATCH]))
        mx.eval(hs)
        states.append([np.array(h.astype(mx.float32)) for h in hs])
    out = []
    for layer in range(len(states[0])):
        x = np.concatenate([s[layer] for s in states], axis=0)[:, 1:, :]  # skip the opening EOS
        y = target[:, 1:]
        fit = np.arange(len(x)) % 2 == 0
        xtr, ytr = x[fit].reshape(-1, x.shape[-1]), y[fit].ravel()
        xte, yte = x[~fit].reshape(-1, x.shape[-1]), y[~fit].ravel()
        mu, sd = xtr.mean(0), xtr.std(0) + 1e-6
        xtr, xte = (xtr - mu) / sd, (xte - mu) / sd
        w = np.linalg.solve(xtr.T @ xtr + lam * np.eye(xtr.shape[1]), xtr.T @ (ytr - ytr.mean()))
        pred = xte @ w + ytr.mean()
        ss = ((yte - yte.mean()) ** 2).sum()
        out.append(float(1 - ((yte - pred) ** 2).sum() / ss) if ss > 0 else 0.0)
    return out


def evaluate(ctx: EvalContext) -> EvalResult:
    model = ctx.model
    if not hasattr(model, "attention_patterns"):
        return EvalResult()
    tok = ctx.tokeniser
    judge = next(iter(ctx.sets.values()), [])
    nat = windows(tok, judge, ctx.context)
    if nat is None:
        return EvalResult()
    metrics: dict[str, float] = {}
    record: dict = {"windows": int(len(nat)), "pieces": int(nat.size)}
    pats = batched_patterns(model, nat)
    for key in CLASSES:
        keys = flags(tok, key)[nat]
        s = class_ratio(pats, keys)
        li, hi = np.unravel_index(int(s.argmax()), s.shape)
        metrics.update({
            f"stars/{key}/max_score": float(s.max()), f"stars/{key}/count": float((s >= MARK).sum()),
            f"stars/{key}/best_layer": float(li), f"stars/{key}/best_head": float(hi),
        })  # fmt: skip
        record[key] = {"scores": s.round(4).tolist(), "keys_seen": int(keys[:, 1:].sum())}
    if hasattr(model, "hidden"):
        r2 = counter_r2(model, nat, sentence_positions(tok, nat))
        metrics["counter/probe_r2"] = max(r2)
        metrics["counter/best_layer"] = float(int(np.argmax(r2)))
        record["counter_r2_by_layer"] = [round(x, 4) for x in r2]
    text = json.dumps(record)
    return EvalResult(
        metrics=metrics,
        artifacts=[{"kind": "pips", "path": "", "sha1": hashlib.sha1(text.encode()).hexdigest(), "text": text}],
    )
