"""The SOP as data: a voyage that names a version is held to it (thorp/sop.py, s5.sop_versions)."""

from __future__ import annotations

import copy

from thorp import sop


def _spec(size: str = "300k") -> dict:
    """A spec that conforms to v0.0.1 at this size, built from the standard so it cannot drift from it."""
    std = sop.standard("0.0.1")
    c, p = std["content"], std["parameters"]
    cards = std["cards"][:4]  # the 300k has four heads
    return {
        "name": "fu-test@300k-pre-s1",
        "sop": "0.0.1",
        "data": {"recipe": c["recipe"], "clean": c["clean"], "passes": c["passes"], "order": c["order"]},
        "tokeniser": dict(c["tokeniser"]),
        "model": {"preset": size, "context": p["context"], "positions": p["positions"]},
        "optim": {
            "lr": std["sizes"][size]["lr"],
            "warmup_steps": std["sizes"][size]["warmup_steps"],
            "scaffold": {
                "weight": 1.0,
                "hold": 0.10,
                "fade": 0.60,
                "heads": [{"layer": i // 2, "head": i % 2, "card": card} for i, card in enumerate(cards)],
            },
        },
    }


def test_the_standard_has_the_five_cards_and_two_phases():
    std = sop.standard("0.0.1")
    assert std["cards"] == ["previous_word", "delimiter", "induction", "duplicate_word", "comparator"]
    assert [p["kind"] for p in std["phases"]] == ["scaffold", "content"]


def test_a_voyage_that_names_no_version_is_not_stopped():
    """The cutover is Justin's to set: everything queued before it sails without an SOP."""
    assert sop.check({"name": "old"}) == []


def test_a_conforming_voyage_passes():
    assert sop.check(_spec()) == []


def test_an_unknown_version_is_refused():
    spec = _spec()
    spec["sop"] = "9.9.9"
    found = sop.check(spec)
    assert found and "does not exist" in found[0]


def test_a_wrong_learning_rate_is_refused():
    spec = _spec()
    spec["optim"]["lr"] = 0.01
    assert any("lr" in f for f in sop.check(spec))


def test_a_card_out_of_order_is_refused():
    spec = _spec()
    heads = spec["optim"]["scaffold"]["heads"]
    heads[0]["card"], heads[1]["card"] = heads[1]["card"], heads[0]["card"]
    assert any("pins" in f for f in sop.check(spec))


def test_a_floor_is_refused():
    """A floor is never by heart: the pull must reach zero."""
    spec = _spec()
    spec["optim"]["scaffold"]["floor"] = 0.2
    assert any("floor" in f for f in sop.check(spec))


def test_a_voyage_named_to_the_sop_must_carry_the_scaffold_phase():
    spec = _spec()
    del spec["optim"]["scaffold"]
    assert any("no scaffold" in f for f in sop.check(spec))


def test_the_standard_is_read_from_the_store_when_it_has_a_row(monkeypatch):
    spec = _spec()  # built from the real order, before the row is changed
    std = copy.deepcopy(sop.STANDARD["0.0.1"])
    std["cards"] = ["delimiter", "previous_word", *std["cards"][2:]]  # a different order in the row
    monkeypatch.setattr(sop, "standard", lambda v="0.0.1": std if v == "0.0.1" else None)
    found = sop.check(spec)
    assert any("order" in f for f in found)
