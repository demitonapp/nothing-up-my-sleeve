"""Foreign ships: outside models as a registry and a spy-page payload (thorp/foreign.py)."""

from __future__ import annotations

from thorp import foreign
from thorp.viable.s4_intelligence import readings


def test_a_foreign_ship_carries_its_deck_logic_and_hole_cards(monkeypatch):
    logic = {"logic": {"metrics": {"gain": 0.2, "lift": 0.4, "score": 0.6, "gain_cause": 0.9}}}
    scored = {
        "set": "hole-cards-unseen",
        "books": [{"language": "en", "bpb": 1.0}, {"language": "en", "bpb": 1.2}],
    }
    monkeypatch.setattr(
        readings,
        "glob",
        lambda pattern: [
            ("logic-microsoft--phi-2", logic),
            ("microsoft--phi-2__hole-cards-unseen__unwrap-v2", scored),
        ],
    )
    monkeypatch.setattr(
        readings,
        "get",
        lambda name: logic if name.startswith("logic-") else scored,
    )
    monkeypatch.setattr(
        readings,
        "chain_grades",
        lambda: {
            "microsoft/phi-2": {
                k: {"pairs": [1.0, 2.0]}
                for k in ("nature_test", "mill_test", "between_test", "pigeonhole_test")
            }
        },
    )
    p = foreign.payload("phi-2")
    assert p is not None
    assert p["params"] == 2.7e9 and p["harbour"] == "zayton"
    assert p["lab"] == "microsoft" and p["flag"] == "sv"
    assert p["logic"]["gain"] == 0.2
    assert p["hole_cards"]["books"] == 2 and p["hole_cards"]["bpb"] == 1.1
    assert p["chaining_lift"] == 1.5


def test_our_own_runs_are_not_foreign_ships(monkeypatch):
    """Zayton is the foreign ships' harbour (11 November): our own runs' readings stay in Phaleron/Piraeus."""
    monkeypatch.setattr(
        readings, "glob", lambda pattern: [("logic-fl-pathfinder", {"logic": {"metrics": {}}})]
    )
    monkeypatch.setattr(readings, "chain_grades", lambda: {})
    assert foreign.models() == []
