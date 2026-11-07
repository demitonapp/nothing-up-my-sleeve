"""Ogden-ness: how closely a book keeps to C. K. Ogden's Basic English (1930), and the keyed words the
Ogden fitout is scored in (Justin, 2026-11-07: "the fitout is a new one called Ogden and all the books in it
have an Ogden(ish) score ... fixed as the pile was for Pythia").

- **The list** (`lists/ogden-850.txt`): Ogden's 850 words (Wiktionary's Appendix: Basic English word list).
  A word counts as Ogden in its regular forms (-s, -es, -ed, -ing, -er, -ly, -ies/-ied/-ier/-ily from -y, a
  doubled consonant: stopped, running), and in the forms Ogden's rules give his operators and pronouns
  (is, was, did, gave, said, him, she, they, my, we, these ...): `lemma`.
- **The keys** (Justin's "skeleton key"): a word outside the 850 is one of three keys, so the bigram table is
  finite, 853 x 853, the same for every book and model: `<name>` (a capitalised word not at a sentence's
  start: Basic English allows names freely, and repeated names are what the Nevermore copies), `<number>`
  (figures and number words), `<thing>` (any other word outside the 850).
- **Ogden-ness** of a book: the share of its ordinary words (every word but names and numbers) that are
  Ogden words. Period English runs from about 25% to 88% (median 70%); the 593 store books at 68% or more
  are Ogden v0.1's corpus.
"""

from __future__ import annotations

import functools
import re

from thorp import paths

KEYS = ("<name>", "<number>", "<thing>")

IRREGULAR = {  # Ogden's operators and pronoun forms, to their headword
    "is": "be", "am": "be", "are": "be", "was": "be", "were": "be", "been": "be", "being": "be",
    "did": "do", "does": "do", "done": "do", "doing": "do", "has": "have", "had": "have", "having": "have",
    "came": "come", "got": "get", "gotten": "get", "gave": "give", "given": "give", "went": "go",
    "gone": "go", "goes": "go", "kept": "keep", "made": "make", "might": "may", "took": "take",
    "taken": "take", "would": "will", "said": "say", "says": "say", "saw": "see", "seen": "see",
    "sent": "send", "seemed": "seem",
    "him": "he", "his": "he", "she": "he", "her": "he", "hers": "he", "it": "he", "its": "he",
    "they": "he", "them": "he", "their": "he", "theirs": "he", "himself": "he", "herself": "he",
    "itself": "he", "themselves": "he",
    "me": "i", "my": "i", "mine": "i", "we": "i", "us": "i", "our": "i", "ours": "i", "myself": "i",
    "ourselves": "i", "your": "you", "yours": "you", "yourself": "you", "whom": "who", "whose": "who",
    "an": "a", "these": "this", "those": "that",
}  # fmt: skip
ENDINGS = (
    ("ies", "y"), ("ied", "y"), ("ier", "y"), ("ily", "y"), ("es", ""), ("s", ""), ("ed", ""),
    ("ed", "e"), ("ing", ""), ("ing", "e"), ("er", ""), ("er", "e"), ("ly", ""), ("'s", ""),
)  # fmt: skip
NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
    "twenty", "thirty", "forty", "fifty", "hundred", "thousand", "million",
}  # fmt: skip
_TOKEN = re.compile(r"[A-Za-z][A-Za-z']*|\d[\d,.]*|[.!?]")


@functools.cache
def words() -> frozenset[str]:
    return frozenset(paths.resolve("lists/ogden-850.txt").read_text().split())


def vocabulary() -> list[str]:
    """The keyed vocabulary: the 850 words in order, then the three keys (the table's rows and columns)."""
    return sorted(words()) + list(KEYS)


def lemma(word: str) -> str | None:
    """The Ogden headword a lowercase word is a form of, or None."""
    og = words()
    if word in og:
        return word
    if word in IRREGULAR:
        return IRREGULAR[word]
    for suffix, rep in ENDINGS:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            base = word[: -len(suffix)] + rep
            if base in og:
                return base
            if len(base) > 2 and base[-1] == base[-2] and base[:-1] in og:  # stopped -> stop
                return base[:-1]
    return None


def keyed(text: str) -> list[str]:
    """The text as keyed words: each word its Ogden headword, or <name>, <number> or <thing>."""
    out, start = [], True
    for t in _TOKEN.findall(text):
        if t in ".!?":
            start = True
            continue
        if t[0].isdigit() or t.lower() in NUMBER_WORDS:
            out.append("<number>")
        else:
            head = lemma(t.lower())
            if head:
                out.append(head)
            elif t[0].isupper() and not start:
                out.append("<name>")
            else:
                out.append("<thing>")
        start = False
    return out


def score(text: str) -> dict:
    """A text's Ogden-ness (the share of its ordinary words that are Ogden words) and its make-up."""
    ws = keyed(text)
    ordinary = [w for w in ws if w not in ("<name>", "<number>")]
    og = sum(1 for w in ordinary if w != "<thing>")
    n = max(1, len(ws))
    return {
        "words": len(ws),
        "ogden": og / max(1, len(ordinary)),
        "names": ws.count("<name>") / n,
        "numbers": ws.count("<number>") / n,
        "things": ws.count("<thing>") / n,
    }
