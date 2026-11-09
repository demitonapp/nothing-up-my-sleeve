"""A shelf at a glance for the ship builder's Library tab (library.summary)."""

from __future__ import annotations

from thorp import library


def test_a_shelf_summarises_its_language_kinds_size_ogden_and_dates():
    s = library.summary("lists/ogden-v0.1.csv")
    assert s["books"] > 0 and s["tokens_est"] > 0
    assert s["languages"][0]["code"] == "en"
    assert s["kinds"] and s["kinds"][0]["books"] > 0
    assert [c["category"] for c in s["categories"]] == [
        "logic and maths", "metaphysics", "empirical knowledge", "general knowledge"]
    assert s["date_range"]["from"] <= s["date_range"]["to"]
    assert 0 <= s["ogden"]["mean"] <= 1
    assert 0 <= s["ogden"]["share_at_bar"] <= 1


def test_a_large_synthetic_deck_is_summarised_without_resolving_books():
    s = library.summary("lists/card-stage-deck-v2.csv")
    assert s["synthetic"] and s["rows"] > 100_000
    assert s["books"] == 0 and s["tokens_est"] > 0
    assert s["languages"][0]["code"] == "en"
