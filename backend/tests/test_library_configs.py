"""The branch configuration is a JSON of choices, not a version (thorp/library_configs.py)."""

from __future__ import annotations

import pytest

from thorp import library_configs as lc


def test_the_same_choices_are_the_same_configuration_and_a_changed_one_is_another():
    a = lc.defaults("ogden")
    b = lc.defaults("ogden")
    assert lc.config_hash("ogden", a) == lc.config_hash("ogden", b)
    b["size"]["words"] = 40_000_000
    assert lc.config_hash("ogden", a) != lc.config_hash("ogden", b)
    assert lc.key_for("ogden", b).startswith("ogden-")


def test_a_partial_json_starts_from_the_branch_defaults():
    c = lc.validate("ogden", {"size": {"words": 20_000_000}})
    assert c["size"]["words"] == 20_000_000
    assert c["ogden"]["min"] == 0.68
    assert c["books"]["rank"] == "ogden"


def test_the_controls_become_a_selection():
    d = lc.defaults("ogden")
    d["size"] = {"words": 20_000_000, "max_book_words": 120_000}
    d["language"] = {"en": 0.9, "fr": 0.1}
    d["date"] = {"start": 1600, "end": 1899, "undated": "exclude"}
    d["content_makeup"] = {"kind": {"novel": 0.6, "poem": 0.4}, "voice": {}, "source": {}}
    spec = lc.to_selection(lc.validate("ogden", d))
    assert spec["words"] == 20_000_000
    assert spec["max_book_words"] == 120_000
    assert spec["languages"] == {"en": 0.9, "fr": 0.1}
    assert spec["period"] == {"start": 1600, "end": 1899, "undated": "exclude"}
    assert spec["weights"] == {"kind": {"novel": 0.6, "poem": 0.4}}
    assert spec["dedupe"] == {"by": "title", "keep": "ogden"}


def test_a_sailed_list_opens_as_a_locked_starting_point():
    starts = lc.from_variation({"key": "ogden-v0.1", "name": "Ogden v0.1", "list": "lists/ogden-v0.1.csv"})
    assert starts["books"]["mode"] == "list"
    assert starts["books"]["list"] == "lists/ogden-v0.1.csv"
    # it is a starting point only: the old row is not changed, and the editor saves a new configuration
    assert starts["books"]["mode"] != "select"


def test_an_old_selection_opens_with_its_choices():
    starts = lc.from_variation({
        "key": "candidates", "name": "candidates",
        "spec": {"languages": {"en": 1.0}, "ogden": {"min": 0.68}, "period": {"end": 1900}}, "books": [1, 2],
    })
    assert starts["language"] == {"en": 1.0}
    assert starts["ogden"]["min"] == 0.68
    assert starts["date"]["end"] == 1900
    assert starts["books"]["mode"] == "select"


def test_a_branch_filter_survives_the_sliders():
    starts = lc.from_variation({
        "key": "scanned", "name": "scanned",
        "spec": {"languages": {"en": 1.0}, "sources": {"include": ["blbooks"]}, "period": {"end": 1900}},
        "books": [1, 2],
    })
    assert starts["books"]["filters"]["sources"]["include"] == ["blbooks"]
    spec = lc.to_selection(lc.validate("scanned", starts))
    assert spec["sources"]["include"] == ["blbooks"]


def test_the_kinds_of_knowledge_are_shares_and_the_composer_fills_them_last():
    d = lc.defaults("ogden")
    d["size"] = {"words": 20_000_000}
    d["content_makeup"] = {"kind": {"novel": 0.6, "poem": 0.4}, "voice": {}, "source": {}}
    d["knowledge"] = {"logic and maths": 0.2, "general knowledge": 0.4, "metaphysics": 0.2, "empirical knowledge": 0.2}
    c = lc.validate("ogden", d)
    assert list(c["knowledge"]) == ["general knowledge", "metaphysics", "empirical knowledge", "logic and maths"]
    weights = lc.to_selection(c)["weights"]
    # last, because with a budget of words the composer fills the shares of the last weighted dimension
    assert list(weights) == ["kind", "knowledge"]
    assert weights["knowledge"]["logic and maths"] == 0.2
    assert "knowledge" not in lc.to_selection(lc.validate("ogden", lc.defaults("ogden")))["weights"]
    with pytest.raises(ValueError, match="knowledge"):
        lc.validate("ogden", {"knowledge": {"alchemy": 1.0}})


def test_a_configuration_saved_before_knowledge_was_a_choice_keeps_its_identity():
    d = lc.defaults("ogden")
    without = {k: v for k, v in d.items() if k != "knowledge"}
    assert lc.config_hash("ogden", without) == lc.config_hash("ogden", d) == lc.config_hash("ogden", {**d, "knowledge": {}})
    assert lc.config_hash("ogden", {**d, "knowledge": {"metaphysics": 1.0}}) != lc.config_hash("ogden", d)
    # the same shares in another order are the same configuration
    one = {**d, "knowledge": {"metaphysics": 0.5, "general knowledge": 0.5}}
    two = {**d, "knowledge": {"general knowledge": 0.5, "metaphysics": 0.5}}
    assert lc.config_hash("ogden", one) == lc.config_hash("ogden", two)
    assert "knowledge" in lc.attributes("ogden") and "knowledge" not in lc.attributes("decks")


def test_control_tokens_are_a_format_choice_not_a_book_choice():
    d = lc.defaults("ogden")
    d["control_tokens"] = {"wrap": "bos-eos", "turns": "marked"}
    c = lc.validate("ogden", d)
    assert c["control_tokens"] == {"wrap": "bos-eos", "turns": "marked"}
    assert "control_tokens" not in lc.to_selection(c)


@pytest.mark.parametrize(
    "change, message",
    [
        ({"books": {"mode": "list"}}, "books.list"),
        ({"books": {"mode": "nope"}}, "books.mode"),
        ({"control_tokens": {"wrap": "nope"}}, "control_tokens.wrap"),
        ({"date": {"start": 1900, "end": 1800}}, "date.start"),
        ({"ogden": {"min": 2}}, "ogden.min"),
        ({"language": {}}, "language"),
    ],
)
def test_a_bad_choice_is_named(change, message):
    d = lc.defaults("ogden")
    d.update(change)
    with pytest.raises(ValueError, match=message):
        lc.validate("ogden", d)
