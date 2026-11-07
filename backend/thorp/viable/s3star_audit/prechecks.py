"""S3* audit's prechecks: independent of the cleaning code's own claims, read the books and check that
cleaning is deterministic and changes nothing that carries meaning (Justin: "Jesus, wept. needs the comma"):
every letter and every mark of sentence punctuation comes through.
"""

from __future__ import annotations

import re

from thorp.viable.precheck_item import Context, Item

_MARKS = re.compile(r"[,.;:!?]")
_LETTERS = re.compile(r"[A-Za-z]")


def _deterministic(ctx: Context):
    from thorp import cleaning

    same = all(cleaning.clean(ctx.raw(b), ctx.clean) == ctx.cleaned(b) for b in ctx.sample)
    return (1.0 if same else 0.0), {"books": len(ctx.sample)}


def _ratio(rx):
    def run(ctx: Context):
        raw = sum(len(rx.findall(ctx.raw(b))) for b in ctx.sample)
        out = sum(len(rx.findall(ctx.cleaned(b))) for b in ctx.sample)
        bad = [b for b in ctx.sample if len(rx.findall(ctx.raw(b))) != len(rx.findall(ctx.cleaned(b)))]
        return out / max(1, raw), {"raw": raw, "cleaned": out, "books_changed": bad[:10]}

    return run


ITEMS = (
    Item(
        "audit.deterministic", "Cleaning is deterministic",
        "cleaning a book again from its source gives exactly the same text",
        "S3*", "cleaning", "1 when every sampled book cleans the same twice", "=", 1.0, _deterministic,
    ),
    Item(
        "audit.punctuation_kept", "Every comma kept",
        "every comma, full stop, semicolon, colon, question and exclamation mark of the source survives cleaning",
        "S3*", "cleaning", "sentence punctuation after cleaning / before, on a sample", "=", 1.0, _ratio(_MARKS),
    ),
    Item(
        "audit.letters_kept", "Every letter kept",
        "no letter is added or lost (capitals included): cleaning changes layout and typesetting, never words",
        "S3*", "cleaning", "letters after cleaning / before, on a sample", "=", 1.0, _ratio(_LETTERS),
    ),
)  # fmt: skip


# words whose kind context cannot change, with the UPOS the tagger must give them
_FIXED = {"the": "DET", "a": "DET", "an": "DET", "and": "CCONJ", "or": "CCONJ", "of": "ADP", "with": "ADP",
          "from": "ADP", "he": "PRON", "she": "PRON", "they": "PRON", "we": "PRON", "i": "PRON",
          "because": "SCONJ", "if": "SCONJ", "very": "ADV"}  # fmt: skip


def _tagger_agrees(ctx: Context):
    """Independent of the tagger's claims: on words whose kind context cannot change, it must agree."""
    from thorp.viable.s2_coordination import tagger

    seen = agree = 0
    misses: dict[str, int] = {}
    for b in ctx.sample[:12]:
        for _, _, w, t in tagger.tag(ctx.cleaned(b)[:60_000]):
            want = _FIXED.get(w.lower())
            if want:
                seen += 1
                agree += t == want
                if t != want:
                    misses[f"{w.lower()}->{t}"] = misses.get(f"{w.lower()}->{t}", 0) + 1
    return agree / max(1, seen), {"words": seen, "misses": sorted(misses.items(), key=lambda x: -x[1])[:10]}


ITEMS = (
    *ITEMS,
    Item(
        "audit.tagger_agrees", "The tagger agrees where it must",
        "on words whose kind context cannot change (the, and, of, he, because, very ...), the tagger gives the kind "
        "the taxonomy expects",
        "S3*", "policy", "share of such words tagged as expected, on a sample", ">=", 0.95, _tagger_agrees,
    ),
)  # fmt: skip
