"""The standing queue as its readers and its writers outside the coordinator see it: the store's, never the file
(11 November, the audit's item 6: the fitout builder and the Navigator's Wager still wrote `specs/queue.txt` and
about ten readers still read it, though the coordinator had read `s2.queue_lines` since 10 November, so a
fitout queued from the builder never sailed and the lint and the audit judged a queue nobody was running).

`specs/queue.txt` is the export `thorp queue` writes for a human to read; nothing reads it back.

Where there is no home queue (a hired box sailing under papers, `THORP_PAPERS`, or one that keeps its own ship's
log, `THORP_SHIP_LOG`, which turns the queue store off) the readers answer an empty queue: a box sails one voyage
and has no standing queue. At home a store that cannot be reached raises `store.StoreDown`, as every other reader
of the one store does; there is no file to fall back to.
"""

from __future__ import annotations

from collections.abc import Iterable


def _home() -> bool:
    """Whether this process has the home queue to read (not a hired box)."""
    from thorp import store
    from thorp.viable.s2_coordination import queue_store

    return store.papers() is None and queue_store.enabled()


def pending() -> list[str]:
    """The pending lines, in order, as the coordinator reads them (no comments: the store holds none)."""
    if not _home():
        return []
    from thorp.viable.s2_coordination import queue_store

    return queue_store.pending_texts()


def history() -> list[dict]:
    """Every line that left the queue, oldest first, as {text, started, status} (queue-done.txt's rows, from the
    store's `s2.queue_history`)."""
    if not _home():
        return []
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.s2_coordination.queue_store import QueueHistory

    with store.session() as s:
        return [
            {"text": r.text, "started": r.started, "status": r.status}
            for r in s.scalars(select(QueueHistory).order_by(QueueHistory.id))
        ]


def add(lines: Iterable[str], top: bool = False) -> list[str]:
    """Queue these lines in the store, in the order given, at the end or (with `top`) at the head of the queue.
    A line already queued is left where it is and not added twice. Returns the lines added.

    `queue_store.add` takes no author, so the comment a file writer used to put above its block (`# Fitout ...`,
    `# The Navigator's Wager: ...`) is not kept; the line's spec says where it came from."""
    from thorp.viable.s2_coordination import queue_store

    want = [ln.strip() for ln in lines if ln and ln.strip() and not ln.lstrip().startswith("#")]
    have = set(queue_store.pending_texts())
    new: list[str] = []
    for ln in want:
        if ln not in have and ln not in new:
            new.append(ln)
    # `add(top=True)` puts one line first, so a block goes in last line first to keep its order
    # the fitout builder and the wager queue from their pages, which do not yet ask which goal a line serves
    # (12 November): a spec that declares one keeps it, one that does not is let in and shows red on the queue
    for ln in reversed(new) if top else new:
        queue_store.add(ln, top=top, require_goal=False)
    return new
