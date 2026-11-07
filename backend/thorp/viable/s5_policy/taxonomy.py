"""The shapes taxonomy (S5 policy, adopted by Justin 2026-11-07 20:20: "ogdens v0.1 must include the parts of
speech classification you proposed"): what kind of word a guess is, recorded for every class at every reading,
so a guess can be scored as the right *kind* of word even when it is the wrong word ("Ogden doesn't need to
know about the world. Just the shapes of the world").

Two tiers:

- **The fine tier**: Universal Dependencies' part-of-speech tags (UPOS), the international standard, with SYM
  and X folded into OTHER, and Thorp's own BREAK (a line or paragraph break: layout is a shape, and the small
  classes' commonest guess). PUNCT and BREAK count as guesses ("Jesus, wept" needs the comma).
- **The coarse tier**: Ogden's own kinds of word (Basic English, 1930): THING (his 600 things, with names and
  numbers), QUALITY (his 150 qualities), OPERATION (his 100 operations: the working words), and MARK
  (punctuation, breaks, exclamations, other).

The judge books (the held-out decks a voyage is scored on and no voyage reads: today the Forgotten Tomes) are
tagged in context by the pinned tagger (s2_coordination/tagger.py), an instrument, outside the period rule.
"""

from __future__ import annotations

ADOPTED = "2026-11-07 20:20, Justin"
VERSION = "shapes-v1"

# the fine tier, in the order the dashboard shows it
FINE = (
    "NOUN", "PROPN", "NUM", "PRON", "VERB", "AUX", "ADJ", "ADV", "ADP", "DET",
    "CCONJ", "SCONJ", "PART", "INTJ", "PUNCT", "BREAK", "OTHER",
)  # fmt: skip

ABOUT = {
    "NOUN": "a thing, idea or act (house, idea, attack)",
    "PROPN": "a name (the <name> key)",
    "NUM": "a number (the <number> key)",
    "PRON": "a pronoun (he, you, who)",
    "VERB": "an action or state (come, give, push)",
    "AUX": "a helping verb (be, have, will, may, do)",
    "ADJ": "a quality (good, bitter, electric)",
    "ADV": "how, when or where (very, here, now, again)",
    "ADP": "a preposition (in, on, between, through)",
    "DET": "a determiner (the, a, this, some, every)",
    "CCONJ": "a word joining equals (and, or, but)",
    "SCONJ": "a word starting a clause (if, because, when, though)",
    "PART": "a particle (to in 'to go', not)",
    "INTJ": "an exclamation (yes, oh)",
    "PUNCT": "punctuation (, . ; : ! ? \" and the dash)",
    "BREAK": "a line or paragraph break (Thorp's own: layout is a shape)",
    "OTHER": "UD's SYM and X: symbols and anything unclassed",
}

COARSE = ("THING", "QUALITY", "OPERATION", "MARK")
TIER = {
    "NOUN": "THING", "PROPN": "THING", "NUM": "THING",
    "ADJ": "QUALITY",
    "VERB": "OPERATION", "AUX": "OPERATION", "ADP": "OPERATION", "DET": "OPERATION", "PRON": "OPERATION",
    "CCONJ": "OPERATION", "SCONJ": "OPERATION", "PART": "OPERATION", "ADV": "OPERATION",
    "PUNCT": "MARK", "BREAK": "MARK", "INTJ": "MARK", "OTHER": "MARK",
}  # fmt: skip

_FROM_UD = {"SYM": "OTHER", "X": "OTHER"}


def fine(ud_tag: str, text: str = "") -> str | None:
    """A tagger's UD tag as a fine-tier tag; whitespace is BREAK when it holds a line break, else not a guess."""
    if ud_tag == "SPACE":
        return "BREAK" if "\n" in text else None
    t = _FROM_UD.get(ud_tag, ud_tag)
    return t if t in TIER else "OTHER"


def coarse(fine_tag: str) -> str:
    return TIER.get(fine_tag, "MARK")
