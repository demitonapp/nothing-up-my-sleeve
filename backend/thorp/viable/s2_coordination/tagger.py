"""The tagger (S2 coordination): the one instrument that assigns the shapes taxonomy's tags, pinned, so 300k, 1m
and 9m are measured identically (as the shared tokeniser keeps their reading identical). spaCy's small English
model, used for its tagger only; an instrument, not training material, so outside the period rule (Justin,
20:20, signing off the proposal).

- `tag(text)`: the text's words with their fine-tier tags and character spans.
- `lexicon()`: each word's commonest tag in the Ogden corpus (built once by `build_lexicon`), so the share of
  a model's probability on each kind of word can be read without tagging every candidate in context.
- `bars()`: the shape bars: tag n-gram tables from the same corpus (1, 2 and 3 tags of context), the shapes
  equivalent of the 2-, 3- and 4-word goals.
"""

from __future__ import annotations

import collections
import functools
import json

from thorp import paths
from thorp.viable.s5_policy import taxonomy

MODEL = "en_core_web_sm"
SPACY_VERSION = "3.8.7"
MODEL_VERSION = "3.8.0"
TAGGER_ID = f"{MODEL}-{MODEL_VERSION}+{taxonomy.VERSION}"


@functools.cache
def nlp():
    import spacy

    if spacy.__version__ != SPACY_VERSION:
        raise RuntimeError(f"the tagger is pinned to spaCy {SPACY_VERSION}, found {spacy.__version__}")
    n = spacy.load(MODEL, disable=["parser", "ner", "lemmatizer"])
    if n.meta["version"] != MODEL_VERSION:
        raise RuntimeError(f"the tagger is pinned to {MODEL} {MODEL_VERSION}, found {n.meta['version']}")
    n.max_length = 5_000_000
    return n


def _words(doc) -> list[tuple[int, int, str, str]]:
    out = []
    for t in doc:
        tag = taxonomy.fine(t.pos_, t.text)
        if tag is not None:
            out.append((t.idx, t.idx + len(t.text), t.text, tag))
    return out


def tag(text: str) -> list[tuple[int, int, str, str]]:
    """(start, end, word, fine tag) for each word, punctuation mark and line break of the text."""
    return _words(nlp()(text))


def tag_many(texts: list[str], batch_size: int = 256) -> list[list[tuple[int, int, str, str]]]:
    return [_words(d) for d in nlp().pipe(texts, batch_size=batch_size)]


_LAST: dict[str, str | None] = {}  # text -> its last word's tag, for as long as the process lives
_LAST_CAP = 200_000


def last_tag(texts: list[str]) -> list[str | None]:
    """The tag of the last word of each text: a guess tagged in its own context.

    Remembered: the tagger is pinned, so a text always takes the same tag, and the shapes evaluator sends mostly
    the same texts at every reading (a judge window's text is fixed; a text is new only where the model's guess
    has changed: 64% to 88% were already tagged at the reading before, 11 November). Only the texts not yet seen
    are tagged."""
    new = [t for t in dict.fromkeys(texts) if t not in _LAST]
    if len(_LAST) + len(new) > _LAST_CAP:  # a long process (many voyages scored in turn): start over
        _LAST.clear()
        new = list(dict.fromkeys(texts))
    for t, words in zip(new, tag_many(new) if new else [], strict=True):
        _LAST[t] = words[-1][3] if words else None
    return [_LAST[t] for t in texts]


def _dir():
    p = paths.data_dir() / "tags" / TAGGER_ID
    p.mkdir(parents=True, exist_ok=True)
    return p


def build_lexicon(books: list[str], clean: str, name: str, log=print) -> dict:
    """Tag a fitout's corpus once: each word's tag counts (the lexicon) and the tag n-gram tables (the shape
    bars), saved under data/tags/<tagger>/<name>-*.json. Text is tagged a paragraph at a time."""
    from thorp.sources import load_text

    counts: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    grams = {k: collections.defaultdict(collections.Counter) for k in (1, 2, 3)}
    unigram = collections.Counter()
    words = 0
    for i, b in enumerate(books, 1):
        paras = [p for p in load_text(b, clean).split("\n\n") if p.strip()]
        seq = []
        for ws in tag_many(paras, batch_size=512):
            for _, _, w, t in ws:
                counts[w.lower()][t] += 1
                seq.append(t)
            seq.append("BREAK")
        words += len(seq)
        unigram.update(seq)
        for k in (1, 2, 3):
            g = grams[k]
            for j in range(k, len(seq)):
                g[" ".join(seq[j - k : j])][seq[j]] += 1
        if i % 50 == 0:
            log(f"  tagged {i} of {len(books)} books, {words:,} tagged tokens")
    lex = {w: dict(c) for w, c in counts.items()}
    bars = {
        "unigram": dict(unigram),
        **{f"context_{k}": {c: dict(v) for c, v in g.items()} for k, g in grams.items()},
    }
    (_dir() / f"{name}-lexicon.json").write_text(json.dumps(lex))
    (_dir() / f"{name}-bars.json").write_text(json.dumps(bars))
    meta = {"books": len(books), "tagged": words, "clean": clean, "tagger": TAGGER_ID, "words": len(lex)}
    (_dir() / f"{name}-meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def extend_lexicon(base: str, extra_books: list[str], total_books: int, clean: str, name: str, log=print) -> dict:
    """The lexicon of a corpus that is another's (`base`, built by `build_lexicon`) and some books more: the base's tag counts
    and bars with the extra books tagged and added. The counts are sums over books (a tag n-gram never crosses a book), so
    this is the very lexicon a full `build_lexicon` of the whole corpus would write, in the time it takes to tag the extra
    books alone."""
    from thorp.sources import load_text

    lex = json.loads((_dir() / f"{base}-lexicon.json").read_text())
    bars_ = json.loads((_dir() / f"{base}-bars.json").read_text())
    base_meta = json.loads((_dir() / f"{base}-meta.json").read_text())
    if base_meta.get("clean") != clean or base_meta.get("tagger") != TAGGER_ID:
        raise ValueError(f"{base}'s lexicon was built on {base_meta.get('clean')} by {base_meta.get('tagger')}, not {clean} by {TAGGER_ID}")
    words = 0
    for b in extra_books:
        seq = []
        for ws in tag_many([p for p in load_text(b, clean).split("\n\n") if p.strip()], batch_size=512):
            for _, _, w, t in ws:
                c = lex.setdefault(w.lower(), {})
                c[t] = c.get(t, 0) + 1
                seq.append(t)
            seq.append("BREAK")
        words += len(seq)
        for t in seq:
            bars_["unigram"][t] = bars_["unigram"].get(t, 0) + 1
        for k in (1, 2, 3):
            g = bars_[f"context_{k}"]
            for j in range(k, len(seq)):
                row = g.setdefault(" ".join(seq[j - k : j]), {})
                row[seq[j]] = row.get(seq[j], 0) + 1
    log(f"  {base} + {len(extra_books)} books ({words:,} tagged tokens) -> {name}")
    (_dir() / f"{name}-lexicon.json").write_text(json.dumps(lex))
    (_dir() / f"{name}-bars.json").write_text(json.dumps(bars_))
    meta = {"books": total_books, "tagged": base_meta["tagged"] + words, "clean": clean, "tagger": TAGGER_ID, "words": len(lex)}
    (_dir() / f"{name}-meta.json").write_text(json.dumps(meta, indent=1))
    return meta


@functools.cache
def lexicon(name: str) -> dict[str, str]:
    """Each word's commonest tag in the named corpus (built by build_lexicon)."""
    p = _dir() / f"{name}-lexicon.json"
    raw = json.loads(p.read_text())
    return {w: max(c, key=c.get) for w, c in raw.items()}


@functools.cache
def bars(name: str) -> dict:
    return json.loads((_dir() / f"{name}-bars.json").read_text())


def meta(name: str) -> dict | None:
    p = _dir() / f"{name}-meta.json"
    return json.loads(p.read_text()) if p.exists() else None
