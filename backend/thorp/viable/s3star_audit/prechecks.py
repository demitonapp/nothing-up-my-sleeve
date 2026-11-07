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
