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
    for state in proposals.STATES:
        assert f"'{state}'" in proposals._DDL
    assert set(proposals.DECISIONS.values()) == set(proposals.STATES) - {"open"}
