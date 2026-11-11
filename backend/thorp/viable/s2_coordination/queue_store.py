"""The standing queue in Postgres (DECISIONS.md, "One store: Postgres, by the viable system", S2): `queue_lines`
(the pending lines, in order) and `queue_history` (every line that started, from queue-done.txt).

This is the store the queue cuts over to **in port, at a time agreed with Justin**; until then
`specs/queue.txt` and `specs/queue-done.txt` stay the live files, and this module holds the tables they move
into and the read-only backfill that copies them with a count check. The line parsing mirrors
`lanes.parse` (a `vast:` prefix, a `cmd:`/`wait:` prefix, else a spec), but does not load a spec, so the
backfill never imports mlx or torch.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import BigInteger, Text, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from thorp.viable.s3_control.models import Base

S2 = "s2"


def enabled() -> bool:
    """Whether the store is the queue. Postgres is the default on the Mac (the cut-over of 10 November,
    the same rule as the ledger); a hired box keeps its own files (`THORP_SHIP_LOG=1`), and
    `THORP_QUEUE_PG` overrides either way. One switch, so the coordinator and the dashboard cannot
    disagree about which queue they are reading (10 November: they did, from different processes)."""
    flag = os.environ.get("THORP_QUEUE_PG")
    if flag is not None:
        return flag.strip().lower() not in ("0", "false", "no", "off", "")
    return os.environ.get("THORP_SHIP_LOG", "").strip().lower() not in ("1", "true", "yes")


class QueueLine(Base):
    """One pending line of the standing queue, in order (its position is the queue's own order)."""

    __tablename__ = "queue_lines"
    __table_args__ = {"schema": S2}

    position: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)  # spec, cmd or wait
    payload: Mapped[str] = mapped_column(Text)  # the spec path under specs/, the shell command, or the voyage waited for
    lane: Mapped[str] = mapped_column(Text)  # mac or vast
    added_by: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[str | None] = mapped_column(Text)


class QueueHistory(Base):
    """One line that left the queue and started (from queue-done.txt: started, the line, its exit status)."""

    __tablename__ = "queue_history"
    __table_args__ = {"schema": S2}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    lane: Mapped[str | None] = mapped_column(Text)
    started: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    run: Mapped[str | None] = mapped_column(Text)


def tables() -> list:
    """The tables this module defines, for the test fixtures' truncate."""
    return [m.local_table for m in Base.registry.mappers if m.class_.__module__ == __name__]


def _specs() -> Path:
    from thorp import paths

    return paths.resolve("specs")


def parse_line(text: str) -> dict:
    """One queue line, read the way `lanes.parse` reads it, without loading the spec (no mlx, no torch)."""
    s = text.strip()
    lane = "mac"
    if s.startswith("vast:"):
        lane, s = "vast", s[len("vast:") :].strip()
    if s.startswith("cmd:"):
        return {"kind": "cmd", "payload": s[len("cmd:") :].strip(), "lane": lane}
    if s.startswith("wait:"):
        return {"kind": "wait", "payload": s[len("wait:") :].strip(), "lane": lane}
    return {"kind": "spec", "payload": s, "lane": lane}


def pending(queue: Path) -> list[str]:
    """The pending lines of the queue, in order (comments and blanks skipped), as the coordinator reads them."""
    if not queue.exists():
        return []
    return [
        ln.strip()
        for ln in queue.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def history(done: Path) -> list[dict]:
    """Every line of queue-done.txt as {text, started, status} (`<ISO ts> <line> <exit status>`)."""
    if not done.exists():
        return []
    out = []
    for ln in done.read_text(encoding="utf-8").splitlines():
        parts = ln.split()
        if len(parts) < 3:
            continue
        out.append({"text": " ".join(parts[1:-1]), "started": parts[0], "status": parts[-1]})
    return out


def backfill(queue: Path | None = None, done: Path | None = None) -> dict:
    """Copy the live queue files into the store, read-only: queue_lines from queue.txt, queue_history from
    queue-done.txt. A no-op in counts on a second run (it replaces both tables)."""
    from thorp import store

    queue = queue or _specs() / "queue.txt"
    done = done or _specs() / "queue-done.txt"
    lines = pending(queue)
    hist = history(done)
    line_rows = [
        {"position": i, "text": t, **parse_line(t)} for i, t in enumerate(lines)
    ]
    hist_rows = [
        {"text": h["text"], "started": h["started"], "status": h["status"],
         "lane": parse_line(h["text"])["lane"], "run": None}
        for h in hist
    ]
    with store.session() as s:
        s.execute(delete(QueueLine))
        s.execute(delete(QueueHistory))
        if line_rows:
            s.execute(insert(QueueLine).values(line_rows))
        if hist_rows:
            for i, row in enumerate(hist_rows, start=1):
                row["id"] = i
            s.execute(insert(QueueHistory).values(hist_rows))
        # the backfill gives the history explicit ids; move the sequence past them or the next record() collides
        s.execute(text("select setval('s2.queue_history_id_seq', (select coalesce(max(id),1) from s2.queue_history))"))
    return {"queue_lines": len(line_rows), "queue_history": len(hist_rows)}


def verify(queue: Path | None = None, done: Path | None = None) -> bool:
    """The store's counts against the live files (queue_lines vs pending lines, queue_history vs done lines)."""
    from thorp import store

    queue = queue or _specs() / "queue.txt"
    done = done or _specs() / "queue-done.txt"
    want = (len(pending(queue)), len(history(done)))
    with store.session() as s:
        got = (
            s.scalar(select(func.count()).select_from(QueueLine)),
            s.scalar(select(func.count()).select_from(QueueHistory)),
        )
    return got == want


# ---------------------------------------------------------------- the live queue (the cut-over)
#
# With THORP_QUEUE_PG=1 the store is the queue: the coordinator reads `lines`, takes with `take` and records
# each line's exit with `record`; `add`, `move` and `drop` are what `thorp queue` edits. `export` writes the
# file from the store, so `queue.txt` stays a readable copy rather than a second source.


def _rows(s) -> list[dict]:
    """The pending lines, in order, inside an open session."""
    rows = s.scalars(select(QueueLine).order_by(QueueLine.position)).all()
    return [
        {"position": r.position, "text": r.text, "kind": r.kind, "payload": r.payload, "lane": r.lane}
        for r in rows
    ]


def lines() -> list[dict]:
    """The pending lines, in order."""
    from thorp import store

    with store.session() as s:
        return _rows(s)


def pending_texts() -> list[str]:
    """The pending lines as the coordinator reads them (a list of strings, in order)."""
    return [r["text"] for r in lines()]


def _write(rows: list[dict], s) -> None:
    """Replace the pending queue with `rows` (positions 0..n, in the order given)."""
    s.execute(delete(QueueLine))
    if rows:
        s.execute(
            insert(QueueLine).values(
                [
                    {
                        "position": i,
                        "text": r["text"].strip(),
                        "kind": r["kind"],
                        "payload": r["payload"],
                        "lane": r["lane"],
                        "added_by": r.get("added_by"),
                        "added_at": r.get("added_at"),
                    }
                    for i, r in enumerate(rows)
                ]
            )
        )


def add(text: str, top: bool = False) -> None:
    """Queue one line (at the end, or at the top when `top`). Refuses a line already queued."""
    import time

    from thorp import store

    text = text.strip()
    if not text:
        return
    with store.session() as s:
        rows = _rows(s)
        if any(r["text"] == text for r in rows):
            raise ValueError(f"{text!r} is already queued")
        row = {"text": text, **parse_line(text), "added_by": "thorp queue", "added_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        _write(([row] + rows) if top else (rows + [row]), s)


def take(text: str) -> bool:
    """Remove the first copy of this line (it has started); False when it is no longer queued."""
    from thorp import store

    text = text.strip()
    with store.session() as s:
        rows = _rows(s)
        for i, r in enumerate(rows):
            if r["text"] == text:
                _write(rows[:i] + rows[i + 1 :], s)
                return True
    return False


def record(line: str, started: str, status: str) -> None:
    """Write a line that ended to queue_history (the queue-done.txt row, in the store)."""
    from thorp import store

    # `line`, not `text`: a parameter named `text` shadowed sqlalchemy.text below and made every
    # record fail with "'str' object is not callable" (10 November, after the sequence resync).
    line = line.strip()
    with store.session() as s:
        # a backfill can leave the id sequence behind the table (10 November: the coordinator died on
        # queue_history_pkey, key id=1, max id 307), so resync before the insert. One record a finished
        # line: the extra statement costs nothing next to losing the queue.
        s.execute(
            text(
                "select setval(pg_get_serial_sequence('s2.queue_history','id'), "
                "coalesce((select max(id) from s2.queue_history), 1))"
            )
        )
        s.add(
            QueueHistory(
                text=line,
                lane=parse_line(line)["lane"],
                started=started,
                status=str(status),
                run=None,
            )
        )


def move(text: str, to: int) -> None:
    """Move a line to 1-based position `to`."""
    from thorp import store

    text = text.strip()
    with store.session() as s:
        rows = _rows(s)
        i = next((k for k, r in enumerate(rows) if r["text"] == text), None)
        if i is None:
            raise LookupError(f"{text!r} is not queued")
        row = rows.pop(i)
        j = max(0, min(len(rows), int(to) - 1))
        rows.insert(j, row)
        _write(rows, s)


def drop(text: str) -> bool:
    """Remove a line (the same as take, but named for the operator)."""
    return take(text)


def export(queue: Path | None = None) -> Path:
    """Write specs/queue.txt from the store: a readable copy, not a second source."""
    queue = queue or _specs() / "queue.txt"
    texts = pending_texts()
    queue.write_text("\n".join(texts) + ("\n" if texts else ""), encoding="utf-8")
    return queue
