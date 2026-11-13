"""Outside models and the goals that approach them (thorp/outside_models.py): the keys, the checks and the join are Postgres's
(migration e6a8b0c2d4f6), so the tests ask the database to refuse what it must."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from thorp import expedition_goals, outside_models, store


@pytest.fixture(autouse=True)
def _a_goal_and_a_house():
    with store.session() as s:
        s.execute(text("truncate s1.expedition_goals, s1.expeditions cascade"))
        s.execute(text("delete from s4.models"))
    expedition_goals.sync()
    expedition_goals.add("knockout", "Beat a bigger model", "d", "w")  # knockout:1
    yield
    with store.session() as s:
        s.execute(text("truncate s1.expedition_goals, s1.expeditions cascade"))
        s.execute(text("delete from s4.models"))


def _falcon() -> str:
    return outside_models.add_model("tiiuae/Falcon-H1-Tiny-90M-Instruct", "tii", "Falcon-H1-Tiny 90M Instruct", 91131072, "https://x")


def test_a_goal_takes_a_model_up_and_the_card_reads_the_view():
    _falcon()
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat", "the bar")
    (card,) = outside_models.cards("ae")
    assert (card["model_id"], card["country"], card["params"]) == ("tiiuae/Falcon-H1-Tiny-90M-Instruct", "ae", 91131072)
    (a,) = card["approaches"]
    assert (a["goal_id"], a["role"], a["note"], a["goal_status"], a["expedition_key"]) == ("knockout:1", "beat", "the bar", "open", "knockout")
    assert outside_models.cards("us") == []


def test_postgres_refuses_a_model_goal_or_role_that_does_not_exist():
    _falcon()
    with pytest.raises(ValueError, match="nope/none"):
        outside_models.link("knockout:1", "nope/none", "beat")
    with pytest.raises(ValueError, match="knockout:99"):
        outside_models.link("knockout:99", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat")
    with pytest.raises(ValueError):
        outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "bogus")
    with pytest.raises(ValueError, match="nolab"):
        outside_models.add_model("x/y", "nolab", "x")


def test_a_link_is_one_row_a_goal_model_and_role_and_a_second_call_edits_its_note():
    _falcon()
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat", "one")
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat", "two")
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "compare")
    rows = outside_models.approaches()
    assert sorted((r["role"], r["note"]) for r in rows) == [("beat", "two"), ("compare", "")]


def test_a_goal_that_goes_takes_its_links_and_a_model_a_goal_holds_cannot_go():
    _falcon()
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat")
    with pytest.raises(Exception, match="foreign key|violates"):
        with store.session() as s:
            s.execute(text("delete from s4.models where id = 'tiiuae/Falcon-H1-Tiny-90M-Instruct'"))
    expedition_goals.remove("knockout:1")
    assert outside_models.approaches() == []  # the cascade took the link
    with store.session() as s:
        s.execute(text("delete from s4.models where id = 'tiiuae/Falcon-H1-Tiny-90M-Instruct'"))


def test_a_goal_taken_off_the_page_leaves_the_card():
    _falcon()
    outside_models.link("knockout:1", "tiiuae/Falcon-H1-Tiny-90M-Instruct", "beat")
    expedition_goals.set_verdict("knockout:1", "dropped")
    assert outside_models.approaches() == []
