"""The backlog's two tests, and the order the catch-up rule puts valid items in (DECISIONS.md, "The catch-up rule").
The gate's refusals and the control's state are read elsewhere, so the verdict is tried here without a store."""

from __future__ import annotations

from types import SimpleNamespace

from thorp.viable.s4_intelligence.backlog import _bare, order, verdict


def test_a_line_is_a_voyage_or_empty():
    assert _bare("fitouts/fu-ogden-v0-1@1m-pre-s2") == "fitouts/fu-ogden-v0-1@1m-pre-s2"
    assert _bare("vast: fitouts/fu-x@9m-pre-s1") == "fitouts/fu-x@9m-pre-s1"
    assert _bare("mac: fitouts/fu-x@9m-pre-s1") == "fitouts/fu-x@9m-pre-s1"
    assert _bare("cmd: echo hello") == ""
    assert _bare("wait: fu-ogden-v0-1@21m-pre-s1") == ""
    assert _bare("# a comment") == ""


def test_an_item_that_names_no_decision_is_struck():
    state, why = verdict(gate=[], decision="")
    assert state == "struck"
    assert "decision" in why


def test_the_gate_is_the_still_sails_test():
    state, why = verdict(
        gate=["sails on the fitout 'maths'", "only the Ogden fitout sails"], decision="round 1"
    )
    assert state == "struck"
    assert "Ogden" in why


def test_an_item_whose_control_has_not_docked_is_blocked_not_struck():
    """It still sails and still decides; it cannot be read yet, so it waits for the control, it is not closed."""
    state, why = verdict(
        gate=[],
        decision="the 1m's seed spread",
        control="fu-ogden-v0-1@1m-pre-s1",
        control_state=None,
    )
    assert state == "blocked"
    assert "not run" in why
    state, why = verdict(
        gate=[],
        decision="the 1m's seed spread",
        control="fu-ogden-v0-1@1m-pre-s1",
        control_state="running",
    )
    assert state == "blocked"
    assert "running" in why


def test_an_item_that_still_sails_and_still_decides_is_valid():
    state, why = verdict(
        gate=[],
        decision="the 1m's seed spread",
        control="fu-ogden-v0-1@1m-pre-s1",
        control_state="finished",
    )
    assert (state, why) == ("valid", "")


def _item(line, gain, minutes):
    return SimpleNamespace(line=line, gain=gain, minutes=minutes)


def test_order_puts_gain_an_hour_first_then_the_shortest():
    rows = [
        _item("slow-good", 0.02, 120.0),
        _item("quick-good", 0.02, 40.0),
        _item("best", 0.05, 90.0),
        _item("unknown-gain", None, 10.0),
        _item("unknown-length", 0.01, None),
    ]
    assert [r.line for r in order(rows)] == [
        "best",
        "quick-good",
        "slow-good",
        "unknown-length",
        "unknown-gain",
    ]


def test_a_gap_takes_only_what_is_known_to_fit():
    rows = [_item("long", 0.05, 120.0), _item("short", 0.01, 20.0), _item("unknown", 0.09, None)]
    assert [r.line for r in order(rows, gap_minutes=30)] == ["short"]
    assert [r.line for r in order(rows, gap_minutes=200)] == ["long", "short"]
