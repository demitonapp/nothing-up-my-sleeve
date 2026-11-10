"""Cleaning: what a book's text looks like when Nothing up my sleeve reads it (2026-11-07, Justin: "do it").

Gutenberg prints books hard-wrapped at about 70 characters, and `sources.gutenberg.strip` keeps every
line as printed, so a voyage read a line break every eight words, most of them in the middle of a
sentence: the commonest thing a small model learned to guess was the line break. A cleaning version
says how a book's text is changed before anything (a tokeniser, a shard, a score) reads it.

- **raw**: the text as the source gives it (gutenberg.strip; archive.clean). Every voyage before
  `unwrap-v1` read this, and a spec that names no version still does, so no old run id moves.
- **unwrap-v1**: paragraphs of prose are joined back into one line each; blank-line runs become one
  blank line (a paragraph break); a break whose line structure means something is kept. Per book, the
  wrap width is the 90th percentile of its line lengths. A paragraph is prose when its lines mostly run
  to that width and at least 30% of them carry on with a lowercase word (verse begins its lines with a
  capital, so blank verse as wide as prose is kept); in prose, a line that reaches 60% of the width is
  joined to the next with a space (or with nothing, after a hyphen that ends a word), and a shorter line
  keeps its break (the end of a sentence set on its own line, a letter's address). Everything else
  (verse, a list, a table, a heading) is kept line for line. Trailing spaces go; nothing else changes (no
  case, no punctuation, no spelling). It is applied to the source's text, never to cleaned text.

The version is named in the spec (`data.clean`), hashed into the run id, carried in the tokeniser's
settings (so a cleaned tokeniser, and its shards, live apart from the raw ones), and applied to the
held-out decks the voyage is scored on. S5 policy 'clean' (thorp/vsm.py) governs it.
"""

from __future__ import annotations

import re

VERSIONS = ("raw", "unwrap-v1", "unwrap-v2", "marks-v1")
DEFAULT = "raw"  # what a spec that names no version reads (every voyage before the policy)
CURRENT = "unwrap-v2"  # what a new voyage reads (S5 policy 'clean'); unwrap-v1 from 18:45 to 19:40

_PARA = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")
_WORD_HYPHEN = re.compile(r"[A-Za-z]-$")


def version_of(spec: dict) -> str:
    """The cleaning version a spec reads (data.clean; raw when it names none)."""
    v = (spec.get("data") or {}).get("clean") or DEFAULT
    if v not in VERSIONS:
        raise ValueError(f"unknown cleaning version {v!r}; known: {', '.join(VERSIONS)}")
    return v


def _width(lines: list[str]) -> int:
    lens = sorted(len(ln) for ln in lines if ln.strip())
    if not lens:
        return 0
    return lens[min(len(lens) - 1, int(0.9 * len(lens)))]


def _unwrap_paragraph(lines: list[str], width: int) -> str:
    body = [ln.rstrip() for ln in lines]
    full = [ln for ln in body if len(ln) >= 0.6 * width]
    # verse, lists, tables, headings: most lines stop well short of the wrap width
    if width < 40 or len(body) < 2 or len(full) < 0.5 * (len(body) - 1):
        return "\n".join(body)
    # verse that runs as wide as prose (blank verse) begins its lines with a capital; wrapped prose
    # carries on mid-sentence, so most of its lines begin with a lowercase word
    starts = [ln.lstrip()[:1] for ln in body[1:] if ln.strip()]
    if starts and sum(s.islower() for s in starts) < 0.3 * len(starts):
        return "\n".join(body)
    out = body[0]
    for prev, ln in zip(body, body[1:], strict=False):
        nxt = ln.lstrip()
        if ln.strip() and _WORD_HYPHEN.search(prev) and nxt[:1].islower():
            out += nxt  # a word broken at the margin: join it whole, however short its line
        elif len(prev) >= 0.6 * width and ln.strip():
            out += " " + nxt
        else:
            out += "\n" + ln
    return out


def unwrap_v1(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    width = _width(text.split("\n"))
    paras = _PARA.split(text.strip("\n"))
    return "\n\n".join(_unwrap_paragraph(p.split("\n"), width) for p in paras if p.strip()) + "\n"


# unwrap-v2 (Justin, 19:40: "they provide context ... Jesus, wept needs the comma"): unwrap-v1, then the
# typesetting that writes one meaning two ways is written one way; every comma, capital, full stop and line
# break that unwrap-v1 keeps is kept
_CURLY = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})
_DASH = re.compile(r"(?<=\S)-{2,3}(?=\S)|(?<=\s)-{2,3}(?=\s)")
_ITALIC = re.compile(r"(?<![\w_])_([^_\n]{1,80}?)_(?![\w_])")
_SPACES = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")


def unwrap_v2(text: str) -> str:
    """unwrap-v1, then: curly quotes become straight ones; a dash set as two or three hyphens becomes one
    em dash; a transcriber's _italics_ become *italics* (the emphasis kept, the word whole); a run of spaces
    inside a line becomes one (a line's indentation is kept)."""
    t = unwrap_v1(text).translate(_CURLY)
    t = _DASH.sub("\u2014", t)
    t = _ITALIC.sub(r"*\1*", t)
    return _SPACES.sub(" ", t)


# ---- marks-v1: the control tokens, in the text (9 November, Justin: Ogden "gets a 0.1.1 with control tokens
# in it ... a lever on its own"). Every document is wrapped <bos> ... <eos>, so the model has a first token to
# park on and a terminal state to predict. A text that is structurally a catechism — lines opening "Q." and
# "A." — has those turns marked <question> / <answer>; everything else is left plain rather than guessed at.
_Q = re.compile(r"(?m)^\s*(?:Q(?:uestion)?\.?|·)\s+")
_A = re.compile(r"(?m)^\s*(?:A(?:nswer)?\.?|·)\s+")


def is_catechism(text: str) -> bool:
    """Whether a text's turns are literally marked: at least three Q lines and three A lines, alternating."""
    qs = len(_Q.findall(text))
    As = len(_A.findall(text))
    return qs >= 3 and As >= 3


def marks_v1(text: str) -> str:
    t = unwrap_v2(text)
    if is_catechism(t):
        out, turn = [], None
        for line in t.split("\n"):
            if _Q.match(line):
                turn = "q"
                out.append("<question> " + _Q.sub("", line, count=1).strip())
            elif _A.match(line):
                turn = "a"
                out.append("<answer> " + _A.sub("", line, count=1).strip())
            else:
                out.append(line)
        t = "\n".join(out)
        t = t.replace("\n<question>", "\n<end>\n<question>")  # close the answer before the next question
    return "<bos>\n" + t.strip("\n") + "\n<eos>"


def clean(text: str, version: str = DEFAULT) -> str:
    if version == "raw":
        return text
    if version == "unwrap-v1":
        return unwrap_v1(text)
    if version == "unwrap-v2":
        return unwrap_v2(text)
    if version == "marks-v1":
        return marks_v1(text)
    raise ValueError(f"unknown cleaning version {version!r}")


def breaks(text: str) -> dict:
    """How a text breaks its lines: words per line break, and the share of breaks inside a paragraph
    (a single newline between two non-empty lines), for the audit and the tests."""
    words = len(text.split())
    nl = text.count("\n")
    inside = len(re.findall(r"[^\n]\n(?=[^\n])", text))
    return {
        "words": words,
        "breaks": nl,
        "words_per_break": words / nl if nl else float("inf"),
        "inside_share": inside / nl if nl else 0.0,
    }
