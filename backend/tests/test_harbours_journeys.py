"""Harbours and journeys as tables (8 November): the harbour's depth and ship builder, and a journey whose
pretraining goes out and whose posttraining returns, each with its stages nested."""

from __future__ import annotations

from thorp import ship_store


def test_harbours_are_a_table_with_a_ship_builder_and_a_depth():
    rows = {h["key"]: h for h in ship_store.harbours()}
    assert set(rows) == {"phaleron", "zayton"}
    assert rows["phaleron"]["depth"] == 20_000_000
    assert rows["zayton"]["depth"] is None
    assert rows["phaleron"]["ship_builder"]
    assert not rows["zayton"]["ship_builder"]  # Zayton sails ships; it does not build them


def test_a_journey_nests_pretraining_outbound_and_posttraining_home():
    j = ship_store.journey("invention-return")
    assert j["harbour_key"] == "phaleron"
    assert j["pretraining"]["leg"] == "outbound"
    assert j["posttraining"]["leg"] == "return"
    assert j["pretraining"]["stage"][0]["name"] == "ogden"
    assert j["pretraining"]["stage"][0]["purpose"].startswith("go out")
    assert j["posttraining"]["stage"][0]["name"] == "turn-taking"
    assert j["posttraining"]["stage"][0]["purpose"].startswith("return with turn-taking")


def test_a_pretraining_stage_records_its_cards_and_their_characteristics():
    j = ship_store.journey("invention-return")
    cards = j["pretraining"]["stage"][0]["cards"]
    keys = {c["key"] for c in cards}
    assert {"previous_word", "duplicate_word", "offset_2", "offset_3", "attention_sink",
            "delimiter", "rare_word"} <= keys
    assert all(c["level"] == 0 for c in cards)  # basic cards only; stage 1 is a bigger model's choice
    assert not {"comparator", "nevermore", "mover", "bridge"} & keys
    one = next(c for c in cards if c["key"] == "previous_word")
    assert one["metric"] == "stars/previous_word/max_score"
    assert one["threshold"] == 0.5 and one["kind"] == "star"


def test_the_100m_is_invention_and_carries_the_quote():
    s = next(r for r in ship_store.sizes() if r["preset"] == "100m")
    assert s["name"] == "Invention"
    assert "Necessity is the mother of all invention" in s["overview"]
    assert "tedium is the step mother" in s["overview"]
    assert "broke is the whore of invention" in s["overview"]


def test_the_waters_read_the_harbours_table(monkeypatch):
    from thorp.dash import waters

    monkeypatch.setattr(
        ship_store,
        "harbours",
        lambda: [
            {"key": "a", "name": "A", "depth": 10, "lane": "mac"},
            {"key": "b", "name": "B", "depth": None, "lane": "vast"},
        ],
    )
    assert [h["key"] for h in waters.harbours()] == ["a", "b"]
    assert waters.harbour_for(11) == "b"


def test_the_ship_builder_can_define_a_new_sop_version():
    from thorp import sop

    std = sop.standard("0.0.4")
    assert std is not None
    v = sop.save(std, adopted="a test definition at Phaleron")
    assert v == "0.0.7"
    got = sop.standard(v)
    assert got["content"]["recipe"] == std["content"]["recipe"]
    assert got["adopted"] == "a test definition at Phaleron"
    # a saved version is not overwritten
    import pytest

    with pytest.raises(ValueError):
        sop.save(std, adopted="again", version=v)


def test_zayton_has_no_ship_builder():
    import pytest

    from thorp.dash import server

    with pytest.raises(LookupError, match="no ship builder"):
        server.api_shipbuilder("zayton")
