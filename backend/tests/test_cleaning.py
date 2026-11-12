"""Cleaning versions (thorp/cleaning.py) and the S5 policy 'clean' (thorp/liberty_machine.py)."""

import pytest

from thorp import cleaning, tokeniser, train, liberty_machine

PROSE = (
    "It was the best of times, it was the worst of times, it was the age of\n"
    "wisdom, it was the age of foolishness, it was the epoch of belief, it was\n"
    "the epoch of incredulity, it was the season of Light, it was the season of\n"
    "Darkness, and a well-\n"
    "known saying.\n"
    "\n"
    "\n"
    "\n"
    "There were a king with a large jaw and a queen with a plain face, on the\n"
    "throne of England; there were a king with a large jaw and a queen with a\n"
    "fair face, on the throne of France.\n"
)
VERSE = (
    "Of Man's first disobedience, and the fruit\n"
    "Of that forbidden tree whose mortal taste\n"
    "Brought death into the World, and all our woe,\n"
    "With loss of Eden, till one greater Man\n"
    "Restore us, and regain the blissful seat,\n"
)


def test_raw_is_the_text_unchanged():
    assert cleaning.clean(PROSE, "raw") == PROSE


def test_unwrap_joins_prose_and_keeps_paragraphs():
    out = cleaning.unwrap_v1(PROSE)
    paras = out.strip("\n").split("\n\n")
    assert len(paras) == 2  # three blank lines became one paragraph break
    assert "\n" not in paras[0] and "\n" not in paras[1]
    assert "age of wisdom" in paras[0]
    assert "well-known saying" in paras[0]  # a word broken at the margin is joined whole
    assert out == cleaning.unwrap_v1(PROSE)  # deterministic


def test_unwrap_keeps_verse_line_for_line():
    text = PROSE + "\n" + VERSE
    out = cleaning.unwrap_v1(text)
    assert VERSE.strip("\n") in out  # blank verse runs as wide as prose, and keeps its lines


def test_breaks_measure():
    b = cleaning.breaks(PROSE)
    assert b["breaks"] == PROSE.count("\n")
    assert 0 < b["inside_share"] < 1
    assert cleaning.breaks(cleaning.unwrap_v1(PROSE))["inside_share"] == 0


def test_version_of_a_spec():
    assert cleaning.version_of({"data": {}}) == "raw"
    assert cleaning.version_of({"data": {"clean": "unwrap-v1"}}) == "unwrap-v1"
    with pytest.raises(ValueError):
        cleaning.version_of({"data": {"clean": "soap"}})


def test_raw_moves_no_id_and_a_cleaning_does():
    books = ["pg1", "pg2"]
    base = {"kind": "spm-bpe", "vocab": 2048, "byte_fallback": True}
    raw = tokeniser.tokeniser_id(books, base)
    assert tokeniser.tokeniser_id(books, {**base, "clean": "raw"}) == raw
    assert tokeniser.tokeniser_id(books, {**base, "clean": "unwrap-v1"}) != raw
    spec = {"name": "x", "data": {"recipe": "r.csv"}}
    assert train.run_id(spec) != train.run_id({**spec, "data": {**spec["data"], "clean": "unwrap-v1"}})


def test_the_clean_policy():
    spec = {"name": "new-voyage-s1", "data": {"recipe": "r.csv"}}
    assert liberty_machine._cleaned(spec)  # a new voyage on raw text breaks it
    assert liberty_machine._cleaned({**spec, "data": {"recipe": "r.csv", "clean": cleaning.CURRENT}}) == []
    assert "clean" in liberty_machine.POLICIES and liberty_machine.POLICIES["clean"].opt_in
