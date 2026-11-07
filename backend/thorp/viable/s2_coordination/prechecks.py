"""S2 coordination's prechecks: the tokeniser every class of the fitout reads through. One tokeniser shared by
300k, 1m and 9m is what keeps their voyages comparable, so it is trained once, before the first voyage, and
checked to give the text back exactly.
"""

from __future__ import annotations

import re

from thorp.viable.precheck_item import Context, Item


def _tok(ctx: Context):
    from thorp import tokeniser

    return tokeniser.train_or_load(ctx.tokeniser_books, ctx.tokeniser_settings)


def _trained(ctx: Context):
    tok = _tok(ctx)
    ids = {
        (s["tokeniser"].get("train_on"), s["tokeniser"].get("vocab")) for s in ctx.specs
    }
    return (1.0 if len(ids) == 1 else 0.0), {
        "tokeniser": tok.id,
        "clean": tok.clean,
        "pieces": tok.vocab_size,
        "shared_by": len(ctx.specs),
    }


def _lossless(ctx: Context):
    tok = _tok(ctx)
    bad = [b for b in ctx.sample[:12] if tok.decode(tok.encode(ctx.cleaned(b)[:200_000])) != ctx.cleaned(b)[:200_000]]
    return (0.0 if bad else 1.0), {"books": min(12, len(ctx.sample)), "not_lossless": bad}


def _ogden_pieces(ctx: Context):
    import collections

    from thorp import ogden

    tok = _tok(ctx)
    occ = collections.Counter()
    for b in ctx.sample:
        occ.update(re.findall(r"[A-Za-z][A-Za-z']*", ctx.cleaned(b)))
    og = {w: c for w, c in occ.items() if ogden.lemma(w.lower())}
    one = sum(c for w, c in og.items() if len(tok.encode(" " + w)) == 1)
    return one / max(1, sum(og.values())), {"ogden_occurrences": sum(og.values()), "books": len(ctx.sample)}


ITEMS = (
    Item(
        "tokeniser.trained", "One shared tokeniser",
        "every voyage of the fitout names the same tokeniser, and it is trained on the fitout's clean text",
        "S2", "tokeniser", "1 when the fitout's voyages share one tokeniser and it is built", "=", 1.0, _trained,
    ),
    Item(
        "tokeniser.lossless", "The text comes back exactly",
        "decoding what the tokeniser encodes gives the cleaned text back, byte for byte (bits per byte stays honest)",
        "S2", "tokeniser", "1 when every sampled book round-trips", "=", 1.0, _lossless,
    ),
    Item(
        "tokeniser.ogden_pieces", "Ogden words are one piece",
        "Ogden's words (as used, counted by occurrence) are single pieces, so the model learns words, not spellings",
        "S2", "tokeniser", "share of Ogden-word occurrences that are one piece", ">=", 0.85, _ogden_pieces,
        applies=lambda ctx: ctx.fitout.get("key", "").startswith("ogden"),
    ),
)  # fmt: skip


def _tagger_pinned(ctx: Context):
    from thorp.viable.s2_coordination import tagger

    try:
        n = tagger.nlp()
        return 1.0, {"tagger": tagger.TAGGER_ID, "pipes": n.pipe_names}
    except Exception as e:  # noqa: BLE001
        return 0.0, {"error": repr(e)}


def _lexicon_built(ctx: Context):
    from thorp.viable.s2_coordination import tagger

    name = ctx.fitout.get("key", "")
    m = tagger.meta(name)
    ok = bool(m) and m.get("clean") == ctx.clean and m.get("books") == len(ctx.books) and m.get("tagger") == tagger.TAGGER_ID
    return (1.0 if ok else 0.0), {"lexicon": name, "meta": m}


ITEMS = (
    *ITEMS,
    Item(
        "tagger.pinned", "One pinned tagger",
        "the shapes taxonomy is assigned by one tagger, at pinned versions, for every class (an instrument, "
        "outside the period rule)",
        "S2", "tokeniser", "1 when the pinned tagger loads at its pinned versions", "=", 1.0, _tagger_pinned,
    ),
    Item(
        "tagger.lexicon", "The corpus tagged once",
        "the fitout's corpus is tagged once, on its own clean text, by the pinned tagger: each word's commonest tag "
        "(what a model's probability falls on) and the shape bars (tag tables of 1, 2 and 3 tags of context)",
        "S2", "tokeniser", "1 when the lexicon covers every book of the fitout, on its cleaning, by the pinned tagger",
        "=", 1.0, _lexicon_built,
    ),
)  # fmt: skip
