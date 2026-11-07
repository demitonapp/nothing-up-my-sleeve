"""The statistical laws of text, measured on what the model writes against what the books hold.

The model writes STREAMS continuations of NEW_TOKENS tokens each from an empty context (EOS), at
temperature 1, so the text is drawn from the model's own distribution; the key is seeded by the
step. The reference is STREAMS excerpts from the English held-out books, at seeded character
offsets that do not move with the step or the tokeniser. Both sides are cut to WORDS_PER_STREAM
words per stream, so a vocabulary that spends more tokens per word is not measured on less text.

Each law is reported for the model (`laws/model/<law>`) and the reference (`laws/ref/<law>`):

- nonword_rate: share of written words never seen in the recipe (spelling). The reference's own
  rate is the floor: real words the recipe happens not to hold.
- zipf: minus the slope of log frequency on log rank over words seen at least twice (about 1).
- heaps: slope of log vocabulary size on log words read (vocabulary growth, under 1).
- word_len: mean letters per word (brevity). word_len_js: Jensen-Shannon divergence (bits) of the
  word-length distribution from the reference's.
- punct_per_100w: punctuation marks per hundred words. punct_js: divergence of the mix of marks.
- unbalanced_per_kw: brackets and curly quotes closed with nothing open, or left open at the end of
  a stream, plus streams with an odd count of straight double quotes, per thousand words.
- cap_after_stop: share of sentence ends (. ! ? then space) followed by a capital letter.

Laws drift with sample size, so values compare across runs only at these constants.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter

import mlx.core as mx
import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.sources import load_text

STREAMS = 16
NEW_TOKENS = 640
WORDS_PER_STREAM = 150
TEMPERATURE = 1.0
REF_SEED = 0
WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
PAIRS = {"(": ")", "[": "]", "“": "”", "‘": None}  # single curly quotes: apostrophes too
STOP = re.compile(r"[.!?][\"'”’)]*\s+[\"'“‘(]*([^\W\d_])")

_lexicon_cache: dict[tuple, set[str]] = {}


def lexicon(recipe: list[str], tok=None) -> set[str]:
    key = tuple(sorted(recipe))
    if key not in _lexicon_cache:
        words: set[str] = set()
        for b in recipe:
            try:
                text = load_text(b)
            except Exception:  # noqa: BLE001
                if tok is None:
                    continue
                text = tok.decode([int(t) for t in shards.load(tok.id, b, tok)])
            words.update(w.lower() for w in WORD.findall(text))
        _lexicon_cache[key] = words
    return _lexicon_cache[key]


def cut_words(text: str, n: int) -> str:
    """The text up to the end of its n-th word (all of it if it has fewer)."""
    for i, m in enumerate(WORD.finditer(text)):
        if i == n - 1:
            return text[: m.end()]
    return text


def write(model, tok, streams: int, n: int, context: int, key) -> list[str]:
    seqs = [[tok.eos_id] for _ in range(streams)]
    keys = mx.random.split(key, n)
    for i in range(n):
        x = mx.array([s[-context:] for s in seqs])
        logits = model(x)[:, -1].astype(mx.float32)
        nxt = mx.random.categorical(logits / TEMPERATURE, key=keys[i])
        for s, t in zip(seqs, nxt.tolist(), strict=True):
            s.append(int(t))
    out = []
    for s in seqs:
        body = s[1:]
        if tok.eos_id in body:  # a stream that ends its book stops there
            body = body[: body.index(tok.eos_id)]
        out.append(tok.decode(body))
    return out


def reference(books: list[str], streams: int, seed: int, span: int = 10000) -> list[str]:
    """`streams` excerpts of up to `span` characters, each starting at a word, books in turn."""
    rng = np.random.default_rng(seed)
    texts = [t for t in (load_text(b) for b in books) if t.strip()]
    out = []
    for i in range(streams if texts else 0):
        t = texts[i % len(texts)]
        start = int(rng.integers(0, max(1, len(t) - span)))
        m = WORD.search(t, start)
        start = m.start() if m else 0
        out.append(t[start : start + span])
    return out


def _js(p: Counter, q: Counter) -> float:
    keys = sorted(set(p) | set(q))
    if not keys:
        return float("nan")
    a = np.array([p.get(k, 0) for k in keys], dtype=float)
    b = np.array([q.get(k, 0) for k in keys], dtype=float)
    if a.sum() == 0 or b.sum() == 0:
        return float("nan")
    a, b = a / a.sum(), b / b.sum()
    m = (a + b) / 2

    def kl(x, y):
        nz = x > 0
        return float((x[nz] * np.log2(x[nz] / y[nz])).sum())

    return (kl(a, m) + kl(b, m)) / 2


def _slope(x, y) -> float:
    if len(x) < 3:
        return float("nan")
    return float(np.polyfit(np.log(x), np.log(y), 1)[0])


def unbalanced(text: str) -> int:
    count = 0
    for o, c in PAIRS.items():
        if c is None:
            continue
        depth = 0
        for ch in text:
            if ch == o:
                depth += 1
            elif ch == c:
                if depth:
                    depth -= 1
                else:
                    count += 1
        count += depth
    return count + (text.count('"') % 2)


def measure(texts: list[str], lex: set[str] | None) -> dict:
    words = [w.lower() for t in texts for w in WORD.findall(t)]
    n = len(words)
    out: dict[str, float] = {"words": float(n)}
    if n == 0:
        return out
    if lex:
        out["nonword_rate"] = sum(w not in lex for w in words) / n
    freq = Counter(words)
    counts = np.array(sorted(freq.values(), reverse=True), dtype=float)
    keep = counts[counts >= 2]
    out["zipf"] = -_slope(np.arange(1, len(keep) + 1), keep) if len(keep) >= 10 else float("nan")
    grid = np.unique(np.geomspace(min(50, n), n, 20).astype(int))
    seen, vocab, at = set(), [], 0
    for g in grid:
        seen.update(words[at:g])
        at = g
        vocab.append(len(seen))
    out["heaps"] = _slope(grid, vocab) if n >= 200 else float("nan")
    lens = Counter(min(len(w), 20) for w in words)
    out["word_len"] = float(np.mean([len(w) for w in words]))
    chars = "".join(texts)
    punct = Counter(ch for ch in chars if unicodedata.category(ch).startswith("P"))
    out["punct_per_100w"] = 100 * sum(punct.values()) / n
    out["unbalanced_per_kw"] = 1000 * sum(unbalanced(t) for t in texts) / n
    stops = [m.group(1) for t in texts for m in STOP.finditer(t)]
    out["cap_after_stop"] = sum(s.isupper() for s in stops) / len(stops) if stops else float("nan")
    out["_lens"] = lens
    out["_punct"] = punct
    return out


def evaluate(ctx: EvalContext) -> EvalResult:
    en = [b for ids in ctx.sets.values() for b in ids if ctx.languages.get(b, "en") == "en"]
    en = list(dict.fromkeys(en))
    lex = lexicon(ctx.recipe, ctx.tokeniser) if ctx.recipe else None
    written = write(
        ctx.model, ctx.tokeniser, STREAMS, NEW_TOKENS, ctx.context, mx.random.key(ctx.step)
    )
    written = [cut_words(t, WORDS_PER_STREAM) for t in written]
    ref = [cut_words(t, WORDS_PER_STREAM) for t in reference(en, STREAMS, REF_SEED)] if en else []
    model_m, ref_m = measure(written, lex), measure(ref, lex) if ref else {}
    if ref_m:
        model_m["word_len_js"] = _js(model_m.get("_lens", Counter()), ref_m["_lens"])
        model_m["punct_js"] = _js(model_m.get("_punct", Counter()), ref_m["_punct"])
        ref_m["word_len_js"] = ref_m["punct_js"] = 0.0
    metrics = {}
    for side, m in (("model", model_m), ("ref", ref_m)):
        for k, v in m.items():
            if not k.startswith("_") and v == v:  # drop NaN
                metrics[f"laws/{side}/{k}"] = float(v)
    clean = lambda m: {k: v for k, v in m.items() if not k.startswith("_")}  # noqa: E731
    text = json.dumps(
        {"model": clean(model_m), "ref": clean(ref_m), "written": written, "reference": ref},
        ensure_ascii=False,
    )
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "laws",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )
