"""S4 intelligence's prechecks: the next version, measured now and shown, not yet a condition of sailing. Two
tokeniser steps were planned for unwrap-v2 and held back to v0.2 because they change how text is encoded, not
the text: a line's first word takes the same piece as it would mid-sentence, and a paragraph break is one piece.
"""

from __future__ import annotations

import re

from thorp.viable.precheck_item import Context, Item


def _line_start(ctx: Context):
    from thorp.viable.s2_coordination.prechecks import _tok

    tok = _tok(ctx)
    words = differ = 0
    for b in ctx.sample[:20]:
        for m in re.finditer(r"(?:^|\n)([A-Za-z][A-Za-z']*)", ctx.cleaned(b)):
            w = m.group(1)
            words += 1
            differ += tok.encode(w)[:1] != tok.encode(" " + w)[:1]
    return differ / max(1, words), {"line_start_words": words}


def _paragraph(ctx: Context):
    from thorp.viable.s2_coordination.prechecks import _tok

    tok = _tok(ctx)
    return float(len(tok.encode("a\n\nb")) - 2), {"pieces_for_a_paragraph_break": len(tok.encode("a\n\nb")) - 2}


ITEMS = (
    Item(
        "next.line_start_piece", "A line's first word as mid-sentence (v0.2)",
        "planned: a word starting a line is a different piece from the same word mid-sentence ('Yes' / ' Yes'); "
        "v0.2 would give it the same piece, losslessly, in the tokeniser",
        "S4", "tokeniser", "share of line-start words whose first piece differs from mid-sentence", "<=", 0.05,
        _line_start, required=False,
    ),
    Item(
        "next.paragraph_piece", "A paragraph break is one piece (v0.2)",
        "planned: a paragraph break is two line-break pieces; v0.2 would make it one, a verse line keeping its one",
        "S4", "tokeniser", "pieces for a paragraph break", "=", 1.0, _paragraph, required=False,
    ),
)  # fmt: skip
