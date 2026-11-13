"""S5 policy 'queue' (13 November, Justin: "only the coordinator or an explicit instruction from me can edit the
queue"): the queue store refuses an edit that names neither, and logs every edit with who asked."""

from __future__ import annotations

import pytest

from thorp.viable.s2_coordination import queue_store


@pytest.fixture
def nobody(monkeypatch):
    monkeypatch.delenv("THORP_QUEUE_BY", raising=False)


def test_an_edit_naming_no_one_is_refused(nobody):
    with pytest.raises(queue_store.QueueEditRefused):
        queue_store.add("fitouts/a", require_goal=False)
    assert queue_store.pending_texts() == []


def test_another_system_is_refused(nobody):
    for who in ("s4: the wager", "session: tidy", "justin", "justin:", "Justin: x"):
        with pytest.raises(queue_store.QueueEditRefused):
            queue_store.add("fitouts/a", require_goal=False, by=who)


def test_the_coordinator_and_justins_words_may_edit(nobody):
    queue_store.add("fitouts/a", require_goal=False, by=queue_store.COORDINATOR)
    queue_store.add("fitouts/b", require_goal=False, by="justin: queue the b voyage")
    queue_store.move("fitouts/b", 1, by="justin: put b first")
    assert queue_store.pending_texts() == ["fitouts/b", "fitouts/a"]
    assert [r["added_by"] for r in queue_store.lines()] == ["justin: queue the b voyage", "coordinator"]
    with pytest.raises(queue_store.QueueEditRefused):
        queue_store.drop("fitouts/a", by="s3: the cycle")
    assert queue_store.drop("fitouts/a", by="justin: drop a")


def test_every_edit_is_logged_with_who_asked(nobody):
    queue_store.add("fitouts/a", require_goal=False, by="justin: queue a")
    with pytest.raises(queue_store.QueueEditRefused):
        queue_store.drop("fitouts/a", by="a script")
    got = queue_store.edits()
    assert got[0]["by"] == "a script" and got[0]["allowed"] is False
    assert got[1]["by"] == "justin: queue a" and got[1]["allowed"] is True


def test_s5_can_switch_it_off(nobody, monkeypatch):
    from thorp import liberty_machine

    monkeypatch.setattr(liberty_machine, "enforced", lambda key: False if key == "queue" else True)
    queue_store.add("fitouts/a", require_goal=False, by="a script")  # allowed, and logged as such
    assert queue_store.edits()[0]["allowed"] is True
