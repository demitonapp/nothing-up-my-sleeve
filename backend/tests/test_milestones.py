"""A voyage's milestones (thorp/milestones.py): when one is due, what its verdict is, and when a miss
calls the voyage back."""

from __future__ import annotations

from thorp import milestones

SPEC = {
    "milestones": [
        {"at": 0.25, "metric": "stars/previous_word/max_score", "at_least": 0.5, "why": "the card by the quarter mark"},
        {"step": 800, "metric": "eval/hole-cards-unseen/bpb_mean", "at_most": 2.5, "if_missed": "warn"},
    ]
}


def test_a_share_of_the_voyage_becomes_a_step():
    ms = milestones.declared(SPEC, 4000)
    assert [m["step"] for m in ms] == [1000, 800]
    assert ms[0]["n"] == 1 and ms[0]["at_least"] == 0.5
    assert ms[1]["if_missed"] == "warn"


def test_a_milestone_is_due_at_its_step_and_judged_once():
    ms = milestones.declared(SPEC, 4000)
    judged: set[int] = set()
    assert milestones.check(ms, 900, {"stars/previous_word/max_score": 0.9}, judged) == []
    got = milestones.check(ms, 1000, {"stars/previous_word/max_score": 0.9}, judged)
    assert [v["verdict"] for v in got] == ["met"]
    assert judged == {1}
    assert milestones.check(ms, 2000, {"stars/previous_word/max_score": 0.1}, judged) == []


def test_a_metric_this_evaluation_did_not_read_stays_unjudged():
    ms = milestones.declared(SPEC, 4000)
    judged: set[int] = set()
    got = milestones.check(ms, 1000, {"stars/previous_word/max_score": 0.9}, judged)
    assert [v["n"] for v in got] == [1]
    assert judged == {1}  # milestone 2's metric was not read: it waits for an evaluation that reads it
    got = milestones.check(ms, 1640, {"eval/hole-cards-unseen/bpb_mean": 1.9}, judged)
    assert [v["n"] for v in got] == [2] and got[0]["verdict"] == "met"


def test_a_missed_milestone_that_asks_for_a_recall_gives_the_words():
    ms = milestones.declared(SPEC, 4000)
    got = milestones.check(ms, 1000, {"stars/previous_word/max_score": 0.31}, set())
    reason = milestones.recall_reason(got)
    assert reason and "milestone 1 missed" in reason and "0.31" in reason and "wanted >= 0.5" in reason


def test_a_missed_milestone_that_only_warns_does_not_recall():
    ms = milestones.declared(SPEC, 4000)
    got = milestones.check(ms, 800, {"eval/hole-cards-unseen/bpb_mean": 4.0}, set())
    assert got[0]["verdict"] == "missed"
    assert milestones.recall_reason(got) is None
