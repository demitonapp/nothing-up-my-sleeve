"""S5's standing proposals (thorp/viable/s5_policy/proposals.py): what a proposal must say, and that a decision only
ever moves an open one. Pure: no store."""

from __future__ import annotations

import pytest

from thorp.viable.s5_policy import proposals


def test_a_proposal_must_ask_something():
    got = proposals.check(filed_by=" session: x ", title=" Split the API ", asks=" Which way? ")
    assert got == {"filed_by": "session: x", "title": "Split the API", "asks": "Which way?"}
    for missing in ("filed_by", "title", "asks"):
        fields = {"filed_by": "S4", "title": "t", "asks": "a?", missing: "  "}
        with pytest.raises(ValueError):
            proposals.check(**fields)


def test_a_decision_moves_only_an_open_proposal():
    assert proposals.next_state("open", "sign") == "signed"
    assert proposals.next_state("open", "decline") == "declined"
    assert proposals.next_state("open", "withdraw") == "withdrawn"
    with pytest.raises(ValueError):
        proposals.next_state("signed", "decline")
    with pytest.raises(ValueError):
        proposals.next_state("open", "approve")


def test_the_table_allows_exactly_the_states():
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:  # the rule is the column's check (migration a8c0e2f4b6d9), not a string in Python
        rule = s.execute(text("select pg_get_constraintdef(oid) from pg_constraint where conname = 'proposals_status_check'")).scalar()
    for state in proposals.STATES:
        assert f"'{state}'" in rule
    assert set(proposals.DECISIONS.values()) == set(proposals.STATES) - {"open"}
