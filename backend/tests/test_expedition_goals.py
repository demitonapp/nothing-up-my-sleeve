"""An expedition's goals as rows (thorp/expedition_goals.py): the store owns the numbered goals (13 November, Justin:
"shouldn't it be going straight to postgres?"). The id a goal is known by is the key the priority page ranks by, so a
queue line, a priority row and a goal are one string."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from thorp import expedition_goals, fleet, priorities, store


@pytest.fixture(autouse=True)
def _goals_clean():
    """The goal tables are not the records' (they are made by `ensure`), so each test empties them itself."""
    expedition_goals.ensure()
    for _ in range(2):  # before the test and after it: another test's `known` goals must not see this one's
        with store.session() as s:
            s.execute(text("truncate s1.expedition_goals, s1.expeditions cascade"))
        if _ == 0:
            yield


def test_the_code_states_no_goals():
    """The fleet's goals are rows, not words in fleet.py; a goal written there is only a seed for a new expedition."""
    assert all(not e.goals for e in fleet.EXPEDITIONS.values())


def test_an_expedition_without_goals_is_one_row_under_its_own_key():
    rows = expedition_goals._rows_of(fleet.EXPEDITIONS["ogden"])
    assert [r["goal_id"] for r in rows] == ["ogden"]
    assert rows[0]["text"] == fleet.EXPEDITIONS["ogden"].goal


def test_a_goal_is_keyed_expedition_position_and_the_next_number_is_never_reused():
    expedition_goals.sync()
    assert expedition_goals.add("knockout", "First", "what", "why") == "knockout:1"
    assert expedition_goals.add("knockout", "Second") == "knockout:2"
    assert expedition_goals.add("knockout", "Tenth", position=10) == "knockout:10"
    assert expedition_goals.add("knockout", "Next") == "knockout:11"
    with pytest.raises(ValueError):
        expedition_goals.add("knockout", "Again", position=2)
    got = expedition_goals.stated("knockout")
    assert [g["position"] for g in got] == [1, 2, 10, 11]
    assert got[0] == {"position": 1, "text": "First", "detail": "what", "why": "why"}


def test_the_first_numbered_goal_replaces_the_bare_row_of_an_open_expedition():
    expedition_goals.sync()
    assert "knockout" in {g["goal_id"] for g in expedition_goals.read()}
    expedition_goals.add("knockout", "First")
    ids = {g["goal_id"] for g in expedition_goals.read("knockout")}
    assert ids == {"knockout:1"}


def test_a_settled_expeditions_one_goal_is_a_record_and_takes_no_numbered_goals():
    expedition_goals.sync()
    expedition_goals.set_verdict("knockout", "done")
    with pytest.raises(ValueError, match="record"):
        expedition_goals.add("knockout", "Late")


def test_a_sync_never_rewrites_or_deletes_a_goal_the_store_holds():
    """12 November: a coordinator syncing old words deleted kipling:8 and :9."""
    expedition_goals.sync()
    expedition_goals.add("knockout", "Mine", "d", "w")
    expedition_goals.edit("knockout:1", text_="Edited")
    expedition_goals.set_verdict("knockout:1", "partly", evidence="a run")
    expedition_goals.sync()
    expedition_goals.sync()
    (g,) = expedition_goals.read("knockout")
    assert (g["text"], g["status"], g["evidence"]) == ("Edited", "partly", "a run")


def test_edit_changes_only_the_fields_given_and_never_the_verdict():
    expedition_goals.sync()
    expedition_goals.add("knockout", "Words", "detail", "why")
    expedition_goals.set_verdict("knockout:1", "partly")
    assert expedition_goals.edit("knockout:1", why="a better reason")
    (g,) = expedition_goals.read("knockout")
    assert (g["text"], g["detail"], g["why"], g["status"]) == ("Words", "detail", "a better reason", "partly")
    assert not expedition_goals.edit("knockout:99", text_="x")


def test_only_an_open_goal_nobody_serves_can_be_removed():
    expedition_goals.sync()
    expedition_goals.add("knockout", "A")
    expedition_goals.add("knockout", "B")
    expedition_goals.set_verdict("knockout:2", "done")
    with pytest.raises(ValueError, match="record"):
        expedition_goals.remove("knockout:2")
    assert expedition_goals.remove("knockout:1")
    assert [g["goal_id"] for g in expedition_goals.read("knockout")] == ["knockout:2"]
    assert expedition_goals.add("knockout", "C") == "knockout:3"  # 1 is not handed out again while 2 stands above it


def test_a_dropped_goal_leaves_the_page_and_the_priority_order_but_stays_a_record():
    expedition_goals.sync()
    expedition_goals.add("knockout", "A")
    expedition_goals.add("knockout", "B")
    expedition_goals.set_verdict("knockout:1", "dropped", words="not wanted")
    assert [g["position"] for g in expedition_goals.stated("knockout")] == [2]
    assert priorities.keys_for("knockout") == ["knockout:2"]
    assert "knockout:1" in {g["goal_id"] for g in expedition_goals.read()}
    assert expedition_goals.add("knockout", "C") == "knockout:3"


def test_every_goal_id_is_a_priority_key_and_a_dangling_one_is_named():
    expedition_goals.sync()
    expedition_goals.add("kipling", "One")
    expedition_goals.add("kipling", "Two")
    ranked = set(priorities.known())
    assert {"kipling:1", "kipling:2"} <= ranked and "kipling" not in ranked
    assert {g["goal_id"] for g in expedition_goals.read()} <= ranked
    assert expedition_goals.dangling(["kipling:1", "kipling:9", "nowhere:1"]) == ["kipling:9", "nowhere:1"]
