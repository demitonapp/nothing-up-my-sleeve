"""The two primers (thorp/primers.py): strict Basic English, held out, deterministic."""

from __future__ import annotations

import re

import pytest

from thorp import logic_tutor as lt
from thorp import primers


@pytest.mark.parametrize("who", ["plato", "francis"])
def test_every_kept_case_is_strict_basic_english_and_every_chapter_has_cases(who):
    for ch, _i, c in primers.valid_cases(who):
        p, a, r = ch.frame(c)
        assert not lt.not_basic(f"{p} {a}. {p} {r}.", ()), (ch.key, c)
    keys = {ch.key for ch, _, _ in primers.valid_cases(who)}
    assert keys == {ch.key for ch in primers.PRIMERS[who]}
    reading = primers.read_cases(who)
    assert all(len(reading[k]) >= 3 for k in keys), {k: len(v) for k, v in reading.items()}  # a passage needs three
    assert len(primers.test_items(who)) >= 30


@pytest.mark.parametrize("who", ["plato", "francis"])
def test_the_reading_never_uses_a_chapters_held_out_words_or_a_whole_test_sentence(who):
    held = primers.held_out_words(who)
    tests = [f"{r['prompt']} {r['answer']}." for r in primers.test_items(who)]
    keys = sorted(primers.read_cases(who))
    texts = primers.passages(who, 3000, seed=7)
    assert len(texts) == 3000
    for t in texts:
        assert not any(x in t for x in tests)
        assert not primers.lt.not_basic(t, ())
    # a passage is of one chapter: the held-out subjects of every chapter are absent from that chapter's cases
    for ch, c in (ch_c for cs in primers.read_cases(who).values() for ch_c in cs):
        p, a, _ = ch.frame(c)
        assert not ({w.lower() for w in re.findall(r"[A-Za-z]+", f"{p} {a}")} & held.get(ch.key, frozenset()))
    assert keys and all(held[k] for k in keys)


def test_deterministic_and_the_rival_is_never_the_answer():
    assert primers.passages("plato", 500, seed=3) == primers.passages("plato", 500, seed=3)
    assert primers.test_items("francis") == primers.test_items("francis")
    for who in primers.PRIMERS:
        assert all(r["answer"] != r["rival"] for r in primers.test_items(who))
