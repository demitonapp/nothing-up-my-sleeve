"""The standing queue in Postgres (DECISIONS.md, "One store: Postgres, by the viable system", S2): `queue_lines`
(the pending lines, in order), `at_sea` (each line that has been launched and has not yet ended) and
`queue_history` (every line that started, from queue-done.txt). A line is in exactly one of the three.

This is the store the queue cuts over to **in port, at a time agreed with Justin**; until then
`specs/queue.txt` and `specs/queue-done.txt` stay the live files, and this module holds the tables they move
into and the read-only backfill that copies them with a count check. The line parsing mirrors
`lanes.parse` (a `vast:` prefix, a `cmd:`/`wait:` prefix, else a spec), but does not load a spec, so the
backfill never imports mlx or torch.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from sqlalchemy import BigInteger, Float, Integer, Text, delete, func, select, text
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
    kind: Mapped[str] = mapped_column(Text)  # spec, cmd, intelligence, wait or hold
    payload: Mapped[str] = mapped_column(Text)  # the spec path under specs/, the shell command, or the voyage waited for
    lane: Mapped[str] = mapped_column(Text)  # mac or vast
    added_by: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[str | None] = mapped_column(Text)
    # which of its expedition's goals this line serves (s1.expedition_goals, 11 November): a spec's
    # `goal: kipling:3` becomes this column when the line is queued, so an expedition's retirement can
    # be read off the queue rather than inferred from run names
    goal_id: Mapped[str | None] = mapped_column(Text)


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
    goal_id: Mapped[str | None] = mapped_column(Text)  # the goal it served, carried from its at-sea row


class AtSea(Base):
    """One line that has left the queue and has not yet ended (11 November). Until this table, what was at sea
    lived only in the coordinator's memory: the line was deleted from `queue_lines` before the launch and
    `queue_history` was written only when the coordinator saw the exit, so a coordinator that died took the
    record of its voyages with it. The row is written in the step that takes the line, given its pid when the
    process exists, and deleted in the step that writes the line's history; a restarted coordinator adopts
    every row it finds (`lanes.run`)."""

    __tablename__ = "at_sea"
    __table_args__ = {"schema": S2}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)  # the line as it was queued
    lane: Mapped[str] = mapped_column(Text)  # mac or vast
    seat: Mapped[int] = mapped_column(Integer, default=0)  # the lane's seat (the helm slot on the Mac)
    kind: Mapped[str] = mapped_column(Text)  # spec, cmd or intelligence (a wait: never goes to sea)
    name: Mapped[str | None] = mapped_column(Text)  # the voyage's name, when the line is a voyage
    run_id: Mapped[str | None] = mapped_column(Text)  # its run id: where an adopted voyage's outcome is read
    pid: Mapped[int | None] = mapped_column(Integer)  # null between the take and the launch
    started: Mapped[str | None] = mapped_column(Text)  # as the coordinator writes it (ISO, its own clock)
    started_ts: Mapped[float | None] = mapped_column(Float)  # the same moment in seconds: a cmd:'s deadline
    coordinator: Mapped[int | None] = mapped_column(Integer)  # the pid of the coordinator that launched it
    # the goal it serves, carried from its queue_lines row when it is taken (12 November: until this column the
    # goal was lost the moment a line sailed, and the queue page showed the voyage at sea with none)
    goal_id: Mapped[str | None] = mapped_column(Text)


def tables() -> list:
    """The tables this module defines, for the test fixtures' truncate."""
    return [m.local_table for m in Base.registry.mappers if m.class_.__module__ == __name__]


def _specs() -> Path:
    from thorp import paths

    return paths.resolve("specs")


def parse_line(text: str) -> dict:
    """One queue line, read the way `lanes.parse` reads it, without loading the spec (no mlx, no torch).

    S4's scheduled intelligence audit keeps its `cmd:` prefix but is its own kind (`intelligence`), so the queue
    page can draw it apart from a general step (12 November)."""
    from thorp.viable.s2_coordination.lanes import is_intelligence, split_lane

    lane, s = split_lane(text)  # `vast: <spec>`, or any lane s2.lane_defs names (11 November, item 11)
    if s.startswith("cmd:"):
        kind = "intelligence" if is_intelligence(s) else "cmd"
        return {"kind": kind, "payload": s[len("cmd:") :].strip(), "lane": lane}
    if s.startswith("wait:"):
        return {"kind": "wait", "payload": s[len("wait:") :].strip(), "lane": lane}
    if s.startswith("hold:"):
        return {"kind": "hold", "payload": s[len("hold:") :].strip(), "lane": lane}
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
    """The pending lines, in order, inside an open session. The kind is read from the line's text, not trusted to
    the stored column: an intelligence audit queued by a coordinator older than the item type was stored as `cmd`,
    and every reader should see it for what it is (the column is rewritten on the next queue edit)."""
    rows = s.scalars(select(QueueLine).order_by(QueueLine.position)).all()
    return [
        {
            "position": r.position,
            "text": r.text,
            "kind": parse_line(r.text)["kind"],
            "payload": r.payload,
            "lane": r.lane,
            "goal_id": r.goal_id,
            # kept so `_write` does not blank them: every rewrite of the queue (a take, a move, a drop) wrote
            # the rows back from this dict, and without these two every line lost who added it and when
            "added_by": r.added_by,
            "added_at": r.added_at,
        }
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
                        "goal_id": r.get("goal_id"),
                    }
                    for i, r in enumerate(rows)
                ]
            )
        )


def _goal_of_spec(payload: str) -> str | None:
    """A spec's `goal:` as a goal id: `goal: 4` on an Arc de Triomphe ship is `arc_de_triomphe:4`.

    The queue does not import the spec's trainer; the YAML is read directly, and a spec that names no
    goal returns None (a line with no goal still sails, in expedition order)."""
    import yaml

    from thorp import fleet, paths

    for p in (paths.resolve(f"specs/{payload}.yaml"), paths.resolve(f"specs/{payload}")):
        if not p.is_file():
            continue
        try:
            spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            return None
        g = spec.get("goal")
        if isinstance(g, int):
            exp = fleet.expedition_of_spec(spec)
            return f"{exp}:{g}" if exp else None
        if isinstance(g, str) and g.strip():
            return g.strip()
        return None
    return None


def _refused_expedition(payload: str) -> str | None:
    """Why a spec line may not be queued for its `expedition:` (11 November, item 11): it names an expedition that
    is neither in fleet.EXPEDITIONS nor a row of s1.expeditions. None for a spec that names none, or cannot be read
    (the gate judges that at launch)."""
    import yaml

    from thorp import fleet, paths

    for p in (paths.resolve(f"specs/{payload}.yaml"), paths.resolve(f"specs/{payload}")):
        if not p.is_file():
            continue
        try:
            spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            return None
        return fleet.unknown_expedition(spec) if isinstance(spec, dict) else None
    return None


# the coordinator's own upkeep: a line that serves the queue itself, not an expedition's goal
MAINTENANCE = ("backend/scripts/restart_coordinator.sh",)


def _goal_of_cmd(payload: str) -> str | None:
    """A `cmd:` that runs an investigation takes the goal its investigation spec declares, as a spec line does."""
    import re

    m = re.search(r"thorp\.investigate run (\S+)", payload)
    return _goal_of_spec(f"investigations/{m.group(1)}") if m else None


def goal_of_line(text: str) -> str | None:
    """The goal a line serves, read from the line itself (its spec's `goal:`, or its investigation's): for a line
    with no queued row to carry it (adopted from the old pid file) and for history written before the column."""
    parsed = parse_line(text)
    if parsed["kind"] == "spec":
        return _goal_of_spec(parsed["payload"])
    if parsed["kind"] == "cmd":
        return _goal_of_cmd(parsed["payload"])
    return None


def needs_goal(parsed: dict) -> bool:
    """Every spec and cmd line serves a goal (Justin, 12 November: "all items in the queue need an expedition and
    goal code. like knockout:3"); a wait or a hold is a rule about other lines, and upkeep and S4's intelligence
    audit serve the queue itself, not an expedition's goal."""
    return parsed["kind"] in ("spec", "cmd") and not any(m in parsed["payload"] for m in MAINTENANCE)


def add(text: str, top: bool = False, goal_id: str | None = None, require_goal: bool = True) -> None:
    """Queue one line (at the end, or at the top when `top`). Refuses a line already queued.

    `goal_id` is the goal the line serves (`kipling:3`, or a bare expedition key where it states none);
    it is checked against the store, so a typo cannot orphan a line. A spec line that names no goal on
    the command line takes the one its spec declares, a `cmd:` running an investigation its investigation's.
    A line that ends with no goal is refused (`require_goal`; the coordinator's own re-queueing of a line it
    already held passes False), unless the store holds no goals at all yet."""
    import time

    from thorp import expedition_goals, store

    text = text.strip()
    if not text:
        return
    parsed = parse_line(text)
    if parsed["kind"] == "spec" and (why := _refused_expedition(parsed["payload"])):
        raise ValueError(f"{text!r} {why}")
    if goal_id is None and parsed["kind"] == "spec":
        goal_id = _goal_of_spec(parsed["payload"])
    if goal_id is None and parsed["kind"] == "cmd":
        goal_id = _goal_of_cmd(parsed["payload"])
    known = {g["goal_id"] for g in expedition_goals.read()}
    if goal_id:
        if known and goal_id not in known:
            raise ValueError(f"no goal {goal_id!r}; thorp goals show lists them")
        if not known:
            goal_id = None  # a store with no goals synced yet: nothing for the FK to point at
    elif require_goal and known and needs_goal(parsed):
        raise ValueError(
            f"{text!r} names no goal: every queued line serves an expedition's goal (knockout:3, kipling:8). Give its "
            "spec `expedition:` and `goal:`, or queue it with --goal; `thorp goals` lists them"
        )
    with store.session() as s:
        rows = _rows(s)
        if any(r["text"] == text for r in rows):
            raise ValueError(f"{text!r} is already queued")
        row = {
            "text": text,
            **parsed,
            "added_by": "thorp queue",
            "added_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "goal_id": goal_id,
        }
        _write(([row] + rows) if top else (rows + [row]), s)


def set_goal(text: str, goal_id: str) -> bool:
    """Give a pending line the goal it serves (or a new one). False when no such line is queued."""
    from sqlalchemy import update

    from thorp import expedition_goals, store

    known = {g["goal_id"] for g in expedition_goals.read()}
    if goal_id not in known:
        raise ValueError(f"no goal {goal_id!r}; thorp goals show lists them")
    with store.session() as s:
        r = s.execute(update(QueueLine).where(QueueLine.text == text.strip()).values(goal_id=goal_id))
        return bool(r.rowcount)


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


# ---------------------------------------------------------------- what is at sea (11 November)

_SEA_FIELDS = ("lane", "seat", "kind", "name", "run_id", "pid", "started", "started_ts", "coordinator", "goal_id")


def _sea_row(line: str, fields: dict) -> AtSea:
    known = {k: fields[k] for k in _SEA_FIELDS if fields.get(k) is not None}
    parsed = parse_line(line)
    known.setdefault("lane", parsed["lane"])
    known.setdefault("kind", parsed["kind"])
    known.setdefault("seat", 0)
    if "goal_id" not in known:  # no queued row carried one (an adopted process): read it off the line
        with contextlib.suppress(Exception):
            g = goal_of_line(line)
            if g:
                known["goal_id"] = g
    return AtSea(text=line.strip(), **known)


def to_sea(line: str, **fields) -> int:
    """Write the at-sea row of a line that is being launched; returns the row's id. For the file queue, and
    for a process adopted from the old pid file, where there is no line to take in the same step."""
    from thorp import store

    with store.session() as s:
        row = _sea_row(line, fields)
        s.add(row)
        s.flush()
        return int(row.id)


def take_to_sea(line: str, **fields) -> int | None:
    """Take the first copy of this line from the queue and write its at-sea row, in one transaction: the line
    is in `queue_lines` or in `at_sea`, never in neither. Returns the row's id, or None when the line is no
    longer queued (edited away meanwhile)."""
    from thorp import store

    line = line.strip()
    with store.session() as s:
        rows = _rows(s)
        for i, r in enumerate(rows):
            if r["text"] == line:
                _write(rows[:i] + rows[i + 1 :], s)
                # the goal goes to sea with the line (12 November): the queued row is deleted here, and
                # with it the only record of what the line serves
                row = _sea_row(line, {**({"goal_id": r["goal_id"]} if r.get("goal_id") else {}), **fields})
                s.add(row)
                s.flush()
                return int(row.id)
    return None


def set_pid(row_id: int, pid: int) -> None:
    """The launched process's pid, written to its at-sea row the moment the process exists."""
    from thorp import store

    with store.session() as s:
        row = s.get(AtSea, int(row_id))
        if row is not None:
            row.pid = int(pid)


def from_sea(row_id: int) -> None:
    """Remove an at-sea row with no history: a launch that failed and is being requeued, or a row whose
    history could only be kept in the file."""
    from thorp import store

    with store.session() as s:
        s.execute(delete(AtSea).where(AtSea.id == int(row_id)))


def at_sea() -> list[dict]:
    """Every line at sea, oldest first, as the coordinator recorded it."""
    from thorp import store

    with store.session() as s:
        return [
            {"id": r.id, "text": r.text, **{k: getattr(r, k) for k in _SEA_FIELDS}}
            for r in s.scalars(select(AtSea).order_by(AtSea.id))
        ]


def record(line: str, started: str, status: str, at_sea: int | None = None) -> None:
    """Write a line that ended to queue_history (the queue-done.txt row, in the store). `at_sea` is the id of
    the line's at-sea row, deleted in the same transaction: the line leaves the sea as it enters the history."""
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
        goal = None
        if at_sea is not None:
            sea = s.get(AtSea, int(at_sea))
            goal = sea.goal_id if sea is not None else None
        if goal is None:
            with contextlib.suppress(Exception):
                goal = goal_of_line(line)
        s.add(
            QueueHistory(
                text=line,
                lane=parse_line(line)["lane"],
                started=started,
                status=str(status),
                run=None,
                goal_id=goal,
            )
        )
        if at_sea is not None:
            s.execute(delete(AtSea).where(AtSea.id == int(at_sea)))


def backfill_goals() -> dict:
    """Fill `goal_id` on the at-sea and history rows written before the column (12 November), each from its
    line's spec or investigation. A line whose spec names no goal (or no longer exists) stays empty: that is
    the record's truth, not a gap to guess at. Returns how many rows of each table were filled."""
    from sqlalchemy import update

    from thorp import store

    out = {"at_sea": 0, "queue_history": 0}
    goals: dict[str, str | None] = {}

    def goal(t: str) -> str | None:
        if t not in goals:
            try:
                goals[t] = goal_of_line(t)
            except Exception:  # noqa: BLE001 - an unreadable spec leaves its row as it was
                goals[t] = None
        return goals[t]

    with store.session() as s:
        for model, key in ((AtSea, "at_sea"), (QueueHistory, "queue_history")):
            texts = s.scalars(select(model.text).where(model.goal_id.is_(None)).distinct()).all()
            for t in texts:
                g = goal(t)
                if g:
                    n = s.execute(update(model).where(model.text == t, model.goal_id.is_(None)).values(goal_id=g))
                    out[key] += n.rowcount or 0
    return out


def sort_specs(key, reads=None) -> None:
    """Stable-sort the pending voyages and steps by `key` (the expedition priority's one write to the queue),
    leaving upkeep, wait and hold lines in their places. Within a goal the order is kept.

    Steps are sorted too since 12 November (Justin: "make sure it's sorted by the correct priorities"; every line
    now serves a goal, so a step has a rank like a voyage). `reads(row)` names the voyages a line reads and
    `name_of` is the voyage a spec line sails: after the sort, a line above anything it reads is moved to just
    below the last of them, because the coordinator only waits for what is queued above a line."""
    from thorp import store

    with store.session() as s:
        rows = _rows(s)
        slots = [i for i, r in enumerate(rows) if needs_goal(r)]
        moving = [rows[i] for i in slots]
        moving.sort(key=key)
        for i, r in zip(slots, moving, strict=True):
            rows[i] = r
        if reads is not None:
            rows = _after_reads(rows, reads)
        _write(rows, s)


def name_of(row: dict) -> str | None:
    """The voyage a spec line sails (its spec's `name`), or None."""
    import yaml

    if row.get("kind") != "spec":
        return None
    for p in (_specs() / f"{row['payload']}.yaml",):
        try:
            return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("name")
        except (OSError, ValueError):
            return None
    return None


def _after_reads(rows: list[dict], reads) -> list[dict]:
    """Move each line that sits above a voyage it reads to just below the last such voyage (stable, repeated
    until nothing moves; a cycle is left as it is after a bounded number of passes)."""
    for _ in range(len(rows) + 1):
        moved = False
        where = {name_of(r): i for i, r in enumerate(rows) if name_of(r)}
        for i, r in enumerate(rows):
            below = [where[n] for n in reads(r) if n in where and where[n] > i]
            if below:
                row = rows.pop(i)
                rows.insert(max(below), row)  # the pop shifted the target up by one: this is just after it
                moved = True
                break
        if not moved:
            return rows
    return rows


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


def release(text: str | None = None) -> str | None:
    """Release a hold: the named `hold:` line, or the first one in the queue. It leaves the queue and its
    release is kept in the history (status `released`), so who let the lane go on, and when, can be read
    back. Returns the line released, or None when there was no hold to release."""
    import time

    from thorp import store

    with store.session() as s:
        rows = _rows(s)
        want = text.strip() if text else None
        i = next((k for k, r in enumerate(rows) if r["kind"] == "hold" and (want is None or r["text"] == want)), None)
        if i is None:
            return None
        line = rows[i]["text"]
        _write(rows[:i] + rows[i + 1 :], s)
    record(line, time.strftime("%Y-%m-%dT%H:%M:%S"), "released")
    return line


def drop(text: str) -> bool:
    """Remove a line (the same as take, but named for the operator)."""
    return take(text)


def export(queue: Path | None = None) -> Path:
    """Write specs/queue.txt from the store: a readable copy, not a second source."""
    queue = queue or _specs() / "queue.txt"
    texts = pending_texts()
    queue.write_text("\n".join(texts) + ("\n" if texts else ""), encoding="utf-8")
    return queue
