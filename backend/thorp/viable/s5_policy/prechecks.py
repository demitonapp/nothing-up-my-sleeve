"""S5 policy's prechecks: the cleaning standard (thorp/cleaning.py). What clean text must look like before a
voyage reads it: the current version, the hard wraps gone from prose, and each piece of typesetting that writes
one meaning two ways written one way (Justin, 19:40: "they provide context ... Jesus, wept needs the comma").
"""

from __future__ import annotations

import re

from thorp.viable.precheck_item import Context, Item

V2 = "unwrap-v2"


def _version(ctx: Context):
    from thorp import cleaning

    return (1.0 if ctx.clean == cleaning.CURRENT else 0.0), {"reads": ctx.clean, "current": cleaning.CURRENT}


def _count(pattern: str):
    rx = re.compile(pattern)

    def run(ctx: Context):
        per = {b: len(rx.findall(ctx.cleaned(b))) for b in ctx.sample}
        worst = sorted(per.items(), key=lambda x: -x[1])[:5]
        return float(sum(per.values())), {"books": len(per), "worst": worst}

    return run


def _wraps(ctx: Context):
    from thorp import cleaning

    words = breaks = inside = 0
    for b in ctx.sample:
        k = cleaning.breaks(ctx.cleaned(b))
        words += k["words"]
        breaks += k["breaks"]
        inside += k["breaks"] * k["inside_share"]
    raw_words = sum(cleaning.breaks(ctx.raw(b))["words"] for b in ctx.sample)
    raw_breaks = sum(cleaning.breaks(ctx.raw(b))["breaks"] for b in ctx.sample)
    return words / max(1, breaks), {
        "books": len(ctx.sample),
        "raw_words_per_break": round(raw_words / max(1, raw_breaks), 2),
        "inside_paragraph_share": round(inside / max(1, breaks), 3),
    }


ITEMS = (
    Item(
        "clean.version", "The current cleaning version",
        "every voyage of the fitout reads the current cleaning version (S5 policy 'clean')",
        "S5", "cleaning", "1 when the fitout's voyages read cleaning.CURRENT", "=", 1.0, _version,
    ),
    Item(
        "clean.hard_wraps", "Hard wraps rejoined",
        "Gutenberg's ~70-character wraps are joined back into paragraphs (raw period text breaks a line every "
        "7 to 9 words; verse, rhymes and lists keep their lines, so a corpus with a nursery shelf stays below prose)",
        "S5", "cleaning", "words per line break, on a sample of the fitout's books", ">=", 12.0, _wraps, V2,
    ),
    Item(
        "clean.quotes", "One quote style",
        "curly and straight quotes mean the same: only straight ones remain",
        "S5", "cleaning", "curly quote marks left, on a sample", "=", 0.0, _count("[“”‘’]"), V2,
    ),
    Item(
        "clean.dashes", "One dash",
        "a dash typeset as two or three hyphens is one em dash",
        "S5", "cleaning", "hyphen dashes (--, ---) left between words, on a sample", "=", 0.0,
        _count(r"(?<=\S)-{2,3}(?=\S)|(?<=\s)-{2,3}(?=\s)"), V2,
    ),
    Item(
        "clean.italics", "Italics as emphasis",
        "a transcriber's _italics_ become *italics*: the emphasis kept, the word whole",
        "S5", "cleaning", "_underscore_ italics left, on a sample", "=", 0.0,
        _count(r"(?<![\w_])_([^_\n]{1,80}?)_(?![\w_])"), V2,
    ),
    Item(
        "clean.spaces", "Single spaces",
        "a run of spaces inside a line is one space (a line's indentation is kept)",
        "S5", "cleaning", "runs of two or more spaces inside a line, on a sample", "=", 0.0,
        _count(r"(?<=\S)[ \t]{2,}(?=\S)"), V2,
    ),
)  # fmt: skip
