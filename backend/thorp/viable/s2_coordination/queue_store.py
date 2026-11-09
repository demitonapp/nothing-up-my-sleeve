"""The standing queue in Postgres (DECISIONS.md, "One store: Postgres, by the viable system", S2): `queue_lines`
(the pending lines, in order) and `queue_history` (every line that started, from queue-done.txt).

This is the store the queue cuts over to **in port, at a time agreed with Justin**; until then
`specs/queue.txt` and `specs/queue-done.txt` stay the live files, and this module holds the tables they move
into and the read-only backfill that copies them with a count check. The line parsing mirrors
`lanes.parse` (a `vast:` prefix, a `cmd:`/`wait:` prefix, else a spec), but does not load a spec, so the
backfill never imports mlx or torch.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import BigInteger, Text, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from thorp.viable.s3_control.models import Base

S2 = "s2"


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
