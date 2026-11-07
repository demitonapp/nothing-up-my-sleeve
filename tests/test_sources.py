"""The general fetcher: any Source, referenced as <source>:<identifier>, fetched once and registered."""

from thorp import manifest
from thorp.sources import base, load_text
from thorp.sources.archive import clean


class FakeSource:
    key = "fake"
    prefix = "fk-"
    calls = 0

    def fetch(self, ident):
        FakeSource.calls += 1
        return base.Fetched(
            title=f"Book {ident}",
            author="Anon",
            language="en",
            text="Some text.\n",
            published=1837,
            origin=f"https://example.org/{ident}",
        )


def test_fetch_ref_registers_once(tmp_thorp):
    base.register_source(FakeSource())
    b = base.fetch_ref("fake:42", family="Germanic")
    assert b.id == "fk-42" and b.source == "fake" and manifest.get("fk-42") is not None
    assert load_text("fk-42") == "Some text.\n"
    assert base.published(b) == 1837
    base.fetch_ref("fake:42")
    assert FakeSource.calls == 1  # cached, not fetched again
    assert base.is_ref("fake:42") and base.is_ref("local:x") and not base.is_ref("The Raven")


def test_archive_cleaning():
    raw = (
        "This is a digital copy of a book that was preserved ... at http://books.google.com/ |\n"
        "PRINCIPLES\n\n\n\nOF GEO-\nLOGY.\n\n12\n\nDigitized by Google\nThe earth is old.\n"
    )
    t = clean(raw)
    assert "digital copy" not in t and "Digitized" not in t
    assert "GEOLOGY" in t and "\n12\n" not in t and "\n\n\n" not in t


def test_long_s_is_read_as_s_only_where_that_makes_a_word():
    from thorp.sources.archive import fix_long_s

    words = {"also", "purpose", "some", "first", "of", "life", "demonstrating", "safe"}
    t = fix_long_s("alfo the purpofe of fome firft life, demonftrating fafe", words)
    assert t == "also the purpose of some first life, demonstrating safe"


def test_trigram_repetition_counts_what_comes_back_within_the_window():
    from thorp import trigrams

    plain = trigrams.measure_text("the cat sat on the mat and a dog ran by the old red barn today")
    rep = trigrams.measure_text(
        "stir the pot then stir the pot then stir the pot then stir the pot"
    )
    assert (
        plain["repeat_rate"] == 0 and rep["repeat_rate"] > 0.5 and rep["variety"] < plain["variety"]
    )
    st = {
        "a": {"repeat_rate": 0.1, "variety": 0.9},
        "b": {"repeat_rate": 0.05, "variety": 0.8},
        "c": {"repeat_rate": 0.2, "variety": 0.5},
    }
    assert trigrams.frontier(st) == {"a", "c"}  # b is beaten on both


def test_a_fitout_needs_a_real_shelf_and_a_pretraining_stage(tmp_path):
    import pytest

    from thorp import fitouts

    with pytest.raises(ValueError):
        fitouts.validate(
            {"name": "x", "stages": [{"phase": "pretraining", "shelf": "lists/no-such.csv"}]}
        )
    with pytest.raises(ValueError):
        fitouts.validate(
            {
                "name": "x",
                "stages": [{"phase": "post-training", "shelf": "lists/stars-fiction.csv"}],
            }
        )
