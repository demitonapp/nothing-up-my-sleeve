"""The queue's store (thorp/viable/s2_coordination/queue_store.py): the live queue files copy into
`queue_lines` and `queue_history` read-only, in order, with the count check passing."""

from __future__ import annotations

from thorp.viable.s2_coordination import queue_store


def test_backfill_copies_the_queue_files(tmp_path):
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "queue.txt").write_text(
        "# a comment\n"
        "fitouts/300k@v0.0.8\n"
        "vast: fitouts/50m@v0.0.5\n"
        "wait: 21m@v0.0.5\n"
        "cmd: echo hi\n"
        "\n",
        encoding="utf-8",
    )
    (specs / "queue-done.txt").write_text(
        "2026-11-09T17:00:44 fitouts/300k@v0.0.8 0\n"
        "2026-11-09T17:05:16 fitouts/300k@v0.0.8 1\n",
        encoding="utf-8",
    )
    q, d = specs / "queue.txt", specs / "queue-done.txt"
    counts = queue_store.backfill(q, d)
    assert counts == {"queue_lines": 4, "queue_history": 2}
    assert queue_store.verify(q, d)
    assert queue_store.backfill(q, d) == counts  # a second copy replaces, not appends
    assert queue_store.verify(q, d)


def test_parse_line_mirrors_lanes(tmp_path):
    assert queue_store.parse_line("fitouts/9m@v0.0.5") == {
        "kind": "spec", "payload": "fitouts/9m@v0.0.5", "lane": "mac",
    }
    assert queue_store.parse_line("vast: fitouts/50m@v0.0.5") == {
        "kind": "spec", "payload": "fitouts/50m@v0.0.5", "lane": "vast",
    }
    assert queue_store.parse_line("wait: 21m@v0.0.5") == {
        "kind": "wait", "payload": "21m@v0.0.5", "lane": "mac",
    }
    assert queue_store.parse_line("cmd: echo hi") == {
        "kind": "cmd", "payload": "echo hi", "lane": "mac",
    }


def test_a_line_is_queued_or_at_sea_or_in_the_history():
    """11 November: the take and the at-sea row are one transaction, and so are the history and the row's end."""
    from sqlalchemy import select

    from thorp import store

    queue_store.add("fitouts/a", require_goal=False)
    queue_store.add("vast: fitouts/b", require_goal=False)
    row = queue_store.take_to_sea("vast: fitouts/b", seat=0, name="b", run_id="r-b", started="2026-11-11T10:00:00", coordinator=1)
    assert queue_store.pending_texts() == ["fitouts/a"]
    (sea,) = queue_store.at_sea()
    assert sea == {"id": row, "text": "vast: fitouts/b", "lane": "vast", "seat": 0, "kind": "spec", "name": "b",
                   "run_id": "r-b", "pid": None, "started": "2026-11-11T10:00:00", "started_ts": None, "coordinator": 1,
                   "goal_id": None}  # fmt: skip
    assert queue_store.take_to_sea("fitouts/never-queued") is None  # edited away: nothing taken, no row
    assert len(queue_store.at_sea()) == 1 and queue_store.pending_texts() == ["fitouts/a"]
    queue_store.set_pid(row, 4242)
    assert queue_store.at_sea()[0]["pid"] == 4242
    queue_store.record("vast: fitouts/b", "2026-11-11T10:00:00", 0, at_sea=row)
    assert queue_store.at_sea() == []
    with store.session() as s:
        assert [(h.text, h.lane, h.status) for h in s.scalars(select(queue_store.QueueHistory))] == [("vast: fitouts/b", "vast", "0")]
    other = queue_store.to_sea("cmd: echo hi", pid=7)  # the file queue's row, and a failed launch's end
    queue_store.from_sea(other)
    assert queue_store.at_sea() == []


def test_a_line_keeps_its_goal_at_sea_and_in_its_history():
    """12 November: the goal was lost the moment a line sailed (9m@v0.0.6-converse, kipling:3, showed none)."""
    from sqlalchemy import select

    from thorp import store

    queue_store.add("fitouts/c", goal_id="kipling:3")
    queue_store.add("fitouts/d", goal_id="knockout:6")
    before = {r["text"]: r["added_at"] for r in queue_store.lines()}
    row = queue_store.take_to_sea("fitouts/c", seat=0, name="c", run_id="r-c", started="2026-11-12T09:00:00")
    assert queue_store.at_sea()[0]["goal_id"] == "kipling:3"
    # the take rewrote the queue: the line left behind keeps its goal and who added it, and when
    (left,) = queue_store.lines()
    assert left["goal_id"] == "knockout:6" and left["added_at"] == before["fitouts/d"]
    queue_store.record("fitouts/c", "2026-11-12T09:00:00", 0, at_sea=row)
    with store.session() as s:
        assert [(h.text, h.goal_id) for h in s.scalars(select(queue_store.QueueHistory))] == [("fitouts/c", "kipling:3")]


def test_backfill_goals_reads_each_line_off_its_spec(monkeypatch):
    from sqlalchemy import select

    from thorp import store

    goals = {"fitouts/e": "kipling:2", "cmd: echo nothing": None}
    monkeypatch.setattr(queue_store, "goal_of_line", lambda t: goals.get(t))
    with store.session() as s:
        for t in ("fitouts/e", "fitouts/e", "cmd: echo nothing"):
            s.add(queue_store.QueueHistory(text=t, lane="mac", started="2026-11-10T00:00:00", status="0"))
        s.add(queue_store.QueueHistory(text="fitouts/e", lane="mac", started="x", status="0", goal_id="kept:1"))
    assert queue_store.backfill_goals() == {"at_sea": 0, "queue_history": 2}
    with store.session() as s:
        got = sorted((h.text, h.goal_id or "") for h in s.scalars(select(queue_store.QueueHistory)))
    assert got == [("cmd: echo nothing", ""), ("fitouts/e", "kept:1"), ("fitouts/e", "kipling:2"), ("fitouts/e", "kipling:2")]


def test_a_hold_is_a_line_and_its_release_is_kept():
    assert queue_store.parse_line("hold: Justin signs the candidate") == {
        "kind": "hold", "payload": "Justin signs the candidate", "lane": "mac",
    }
    for line in ("fitouts/300k@v0.0.6", "hold: the candidate", "fitouts/9m@v0.0.6", "hold: before the 21m"):
        queue_store.add(line, require_goal=False)
    assert queue_store.release("hold: before the 21m") == "hold: before the 21m"  # by name
    assert queue_store.release() == "hold: the candidate"  # else the first
    assert queue_store.release() is None
    assert queue_store.pending_texts() == ["fitouts/300k@v0.0.6", "fitouts/9m@v0.0.6"]
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        rows = s.execute(text("select text, status from s2.queue_history order by id")).all()
    assert [tuple(r) for r in rows] == [("hold: before the 21m", "released"), ("hold: the candidate", "released")]
