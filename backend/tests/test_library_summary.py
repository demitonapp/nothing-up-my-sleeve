"""A shelf at a glance for the ship builder's Library tab (library.summary)."""

from __future__ import annotations

from thorp import library


def test_a_shelf_summarises_its_language_kinds_size_ogden_and_dates(monkeypatch):
    # the real shelf against the real register: the test database's books are empty, so this reads the
    # data folder's manifest.sqlite (read only), the copy a hired box carries (11 November: the library is
    # Postgres by default, and `THORP_LIBRARY_PG=0` is how a process asks for the file)
    monkeypatch.setenv("THORP_LIBRARY_PG", "0")
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
