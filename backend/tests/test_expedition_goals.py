"""An expedition's goals as rows (thorp/expedition_goals.py): the id a goal is known by is the key the
priority page ranks by, so a queue line, a priority row and a goal are one string."""

from __future__ import annotations

from thorp import expedition_goals, fleet, priorities


def test_a_stated_goal_is_keyed_expedition_position():
    rows = expedition_goals._rows_of(fleet.EXPEDITIONS["kipling"])
    ids = [r["goal_id"] for r in rows]
    assert ids == [f"kipling:{i}" for i in range(1, 7)]
    # Table Talk's goal was folded into goal 3 (11 November), not kept as a seventh
    assert "kipling:7" not in ids
    assert rows[0]["text"] == "Beat IFEval"
    assert rows[0]["why"]  # the goals table carries why it is wanted


def test_an_expedition_without_goals_is_one_row_under_its_own_key():
    rows = expedition_goals._rows_of(fleet.EXPEDITIONS["ogden"])
    assert [r["goal_id"] for r in rows] == ["ogden"]
    assert rows[0]["text"] == fleet.EXPEDITIONS["ogden"].goal


def test_every_goal_id_is_a_priority_key():
    """The two namespaces are the same, or the queue could rank a goal it cannot point at."""
    ranked = set(priorities.known())
    for key, e in fleet.EXPEDITIONS.items():
        for r in expedition_goals._rows_of(e):
            assert r["goal_id"] in ranked, f"{key}: {r['goal_id']} is not a priority key"
