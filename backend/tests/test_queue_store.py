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
