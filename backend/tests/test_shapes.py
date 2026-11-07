"""The shapes taxonomy (thorp/viable/s5_policy/taxonomy.py) and the evaluator's keyed words."""

from thorp.evaluators.shapes import _keyed
from thorp.viable.s5_policy import taxonomy


def test_every_fine_tag_has_a_coarse_tier_and_a_meaning():
    assert set(taxonomy.TIER) == set(taxonomy.FINE)
    assert set(taxonomy.TIER.values()) == set(taxonomy.COARSE)
    assert set(taxonomy.ABOUT) == set(taxonomy.FINE)


def test_ud_tags_fold_into_the_fine_tier():
    assert taxonomy.fine("NOUN") == "NOUN"
    assert taxonomy.fine("SYM") == "OTHER" and taxonomy.fine("X") == "OTHER"
    assert taxonomy.fine("SPACE", "\n\n") == "BREAK"
    assert taxonomy.fine("SPACE", " ") is None  # a space is not a guess
    assert taxonomy.coarse("ADJ") == "QUALITY" and taxonomy.coarse("ADP") == "OPERATION"
    assert taxonomy.coarse("PROPN") == "THING" and taxonomy.coarse("BREAK") == "MARK"


def test_keyed_words_take_names_and_numbers_from_their_tag():
    assert _keyed("Pip", "PROPN") == "<name>"
    assert _keyed("1820", "NUM") == "<number>"
    assert _keyed("houses", "NOUN") == "house"
    assert _keyed("carburettor", "NOUN") == "<thing>"
    assert _keyed(",", "PUNCT") is None
