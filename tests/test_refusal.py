import pytest

from thorp import tokeniser, train


def test_recipe_with_hole_card_aborts_before_tokenising(library, spec, monkeypatch):
    lists = library["lists"]
    lists["recipe.csv"] = lists["recipe.csv"] + ["loc-hole"]

    def boom(*a, **k):
        raise AssertionError("tokeniser must not be trained when the recipe holds a hole card")

    monkeypatch.setattr(tokeniser, "train_or_load", boom)
    with pytest.raises(train.RefusedBook):
        train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)


def test_clean_recipe_prepares(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    assert prep.recipe == library["recipe"] and prep.eval_sets == {"hole": ["loc-hole"]}
