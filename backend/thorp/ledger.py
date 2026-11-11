"""The ledger: the only writer of ledger.sqlite, and the Recorder protocol other sinks can implement."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from thorp import paths

SCHEMA = """
create table if not exists runs (
    run_id text primary key, name text, ship text, spec_json text, "commit" text, hardware text,
    started text, finished text, status text, tokens_seen integer, wall_minutes real
);
create table if not exists metrics (run_id text, step integer, name text, value real, ts real);
create index if not exists metrics_run on metrics(run_id, name, step);
create table if not exists evals (
    run_id text, step integer, "set" text, book_id text,
    ce_nats real, bpb real, tokens integer, bytes integer
);
create index if not exists evals_run on evals(run_id, step);
create table if not exists artifacts (
    run_id text, step integer, kind text, path text, sha1 text, text text
);
create index if not exists artifacts_run on artifacts(run_id, kind, step);
-- a ship's run is a voyage (2026-11-07, Justin); the table keeps its name, the view gives the new one
create view if not exists voyages as select run_id as voyage_id, * from runs;
"""

EVAL_COLUMNS = ("run_id", "step", "set", "book_id", "ce_nats", "bpb", "tokens", "bytes")
RUN_COLUMNS = (
    "run_id",
    "name",
    "ship",
    "spec_json",
    "commit",
    "hardware",
    "started",
    "finished",
    "status",
    "tokens_seen",
    "wall_minutes",
)
# Columns a run row may carry that the table was not made with (11 November: `sop_version`, which Postgres' s1.runs
# has and a hired box's SQLite log had not, so a voyage sailed on a box came home without its SOP version). A file
# gains such a column only when a row first carries a value for it (as `ship` was added, but on the write, not on the
# open: a ledger nobody writes a version to is never altered); a row that carries none is written exactly as before.
LATER_RUN_COLUMNS = ("sop_version",)


class Recorder(Protocol):
    def run(self, row: dict) -> None: ...
    def metrics(self, run_id: str, step: int, values: dict[str, float]) -> None: ...
    def evals(self, rows: Iterable[dict]) -> None: ...
    def artifact(
        self, run_id: str, step: int, kind: str, path: str = "", sha1: str = "", text: str = ""
    ) -> None: ...
    def truncate_after(self, run_id: str, step: int) -> None: ...
    def clear_step(self, run_id: str, step: int, tables: tuple[str, ...] = ("evals",), sets=None) -> None: ...
    def close(self) -> None: ...


def connect(path: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = path or paths.ledger_path()
    if readonly:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False, timeout=15.0)
    else:
        con = sqlite3.connect(path, timeout=30)
        con.execute("pragma journal_mode=wal")
        con.executescript(SCHEMA)
        # a ledger written before 2026-11-06 has no ship column: add it, keep every row
        if "ship" not in {r[1] for r in con.execute("pragma table_info(runs)")}:
            con.execute("alter table runs add column ship text")
            con.commit()
    con.row_factory = sqlite3.Row
    return con


class Ledger:
    """SQLite Recorder. One connection per instance; commits per call."""

    def __init__(self, path: Path | None = None):
        self.con = connect(path)

    # -- writes
    def _run_column(self, name: str) -> None:
        """Add a later column to this file's `runs` if it lacks it (additive: every row keeps its values)."""
        if name in {r[1] for r in self.con.execute("pragma table_info(runs)")}:
            return
        try:
            self.con.execute(f'alter table runs add column "{name}" text')
            self.con.commit()
        except sqlite3.OperationalError:  # another writer added it between the look and the change
            if name not in {r[1] for r in self.con.execute("pragma table_info(runs)")}:
                raise

    def run(self, row: dict) -> None:
        later = [k for k in LATER_RUN_COLUMNS if row.get(k) is not None]
        for k in later:
            self._run_column(k)
        row = {k: row.get(k) for k in (*RUN_COLUMNS, *later)}
        cols = ", ".join(f'"{k}"' for k in row)
        qs = ", ".join("?" for _ in row)
        upd = ", ".join(f'"{k}"=coalesce(excluded."{k}", "{k}")' for k in row if k != "run_id")
        with self.con:
            self.con.execute(
                f"insert into runs ({cols}) values ({qs}) on conflict(run_id) do update set {upd}",
                list(row.values()),
            )

    def metrics(self, run_id: str, step: int, values: dict[str, float]) -> None:
        ts = time.time()
        with self.con:
            self.con.executemany(
                "insert into metrics values (?,?,?,?,?)",
                [(run_id, step, k, float(v), ts) for k, v in values.items()],
            )

    def metrics_many(self, rows: list[tuple[str, int, dict[str, float], float]]) -> None:
        """Many steps' metrics, each (run_id, step, values, ts), in one transaction: all or none (MetricBuffer)."""
        with self.con:
            self.con.executemany(
                "insert into metrics values (?,?,?,?,?)",
                [(rid, step, k, float(v), ts) for rid, step, values, ts in rows for k, v in values.items()],
            )

    def evals(self, rows: Iterable[dict]) -> None:
        rows = [tuple(r[c] for c in EVAL_COLUMNS) for r in rows]
        with self.con:
            self.con.executemany("insert into evals values (?,?,?,?,?,?,?,?)", rows)

    def artifact(self, run_id, step, kind, path="", sha1="", text="") -> None:
        with self.con:
            self.con.execute(
                "insert into artifacts values (?,?,?,?,?,?)", (run_id, step, kind, path, sha1, text)
            )

    def truncate_after(self, run_id: str, step: int) -> None:
        """On resume, forget anything recorded after the checkpoint being resumed."""
        with self.con:
            for t in ("metrics", "evals", "artifacts"):
                self.con.execute(f"delete from {t} where run_id=? and step>?", (run_id, step))

    def clear_step(self, run_id: str, step: int, tables=("evals",), sets=None) -> None:
        """Delete a step's rows. With `sets`, only the evals rows of those sets, so re-scoring a
        checkpoint on a new list never removes the scores it already has on another."""
        with self.con:
            for t in tables:
                if t == "evals" and sets is not None:
                    for s in sets:
                        self.con.execute(
                            'delete from evals where run_id=? and step=? and "set"=?',
                            (run_id, step, s),
                        )
                else:
                    self.con.execute(f"delete from {t} where run_id=? and step=?", (run_id, step))

    # -- reads
    def get_run(self, run_id: str) -> dict | None:
        r = self.con.execute("select * from runs where run_id=?", (run_id,)).fetchone()
        return dict(r) if r else None

    def query(self, sql: str, params: Iterable = ()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, list(params))]

    def get_run_by_name(self, name: str, finished: bool | None = None) -> dict | None:
        sql = "select * from runs where name=?"
        params: list = [name]
        if finished:
            sql += " and status='finished'"
        sql += " order by started desc limit 1"
        r = self.con.execute(sql, params).fetchone()
        return dict(r) if r else None

    def find_run(self, arg: str) -> dict | None:
        """A run by name, or by a unique prefix of its run_id, newest started first."""
        r = self.get_run_by_name(arg)
        if r:
            return r
        r = self.con.execute(
            "select * from runs where run_id like ? order by started desc limit 1", (arg + "%",)
        ).fetchone()
        return dict(r) if r else None

    def latest_artifact_text(self, run_id: str, kind: str) -> str | None:
        r = self.con.execute(
            "select text from artifacts where run_id=? and kind=? order by step desc, rowid desc limit 1",
            (run_id, kind),
        ).fetchone()
        return r[0] if r else None

    def metric_at(self, run_id: str, name: str, which: str = "last") -> float | None:
        order = "step desc, rowid desc" if which == "last" else "step asc, rowid asc"
        r = self.con.execute(
            f"select value from metrics where run_id=? and name=? order by {order} limit 1",
            (run_id, name),
        ).fetchone()
        return r[0] if r else None

    def runs_by_ship(self, ship: str) -> list[dict]:
        """A ship's finished voyages, newest first (its sailings, for the smoking-Qwen comparison)."""
        return [
            dict(r)
            for r in self.con.execute(
                "select * from runs where ship=? and status='finished' order by started desc", (ship,)
            )
        ]

    def checkpoint_wal(self) -> None:
        self.con.execute("pragma wal_checkpoint(truncate)")

    def close(self) -> None:
        self.con.close()


def spec_of(run: dict) -> dict:
    return json.loads(run["spec_json"])


class DualRecorder:
    """Writes both the SQLite ledger and Postgres. Until the cut-over SQLite is authoritative, so a Postgres
    failure is logged and the run goes on (the backfill catches the store up); after the cut-over the PgLedger
    is the one writer and raises. A hired box never gets one: it sails under papers and writes its SQLite log."""

    def __init__(self, sqlite: Ledger, pg):
        self.sqlite = sqlite
        self.pg = pg

    def __getattr__(self, name):
        """Everything DualRecorder does not override reads through to the SQLite ledger (17:11: train._run calls
        rec.get_run, which the wrapper did not carry — a voyage died at step zero on the cut-over switch)."""
        return getattr(self.sqlite, name)

    def _pg(self, fn, what: str) -> None:
        try:
            fn()
        except Exception as e:  # noqa: BLE001  (best-effort: SQLite is still the ledger of record)
            print(f"ledger: {what} not written to Postgres (sqlite is still authoritative): {e}", file=sys.stderr)

    def run(self, row: dict) -> None:
        self.sqlite.run(row)
        self._pg(lambda: self.pg.run(row), "run")

    def metrics(self, run_id: str, step: int, values: dict[str, float]) -> None:
        self.sqlite.metrics(run_id, step, values)
        self._pg(lambda: self.pg.metrics(run_id, step, values), f"metrics at step {step}")

    def metrics_many(self, rows: list[tuple[str, int, dict[str, float], float]]) -> None:
        self.sqlite.metrics_many(rows)
        self._pg(lambda: self.pg.metrics_many(rows), f"metrics of {len(rows)} steps")

    def evals(self, rows: Iterable[dict]) -> None:
        rows = list(rows)
        self.sqlite.evals(rows)
        self._pg(lambda: self.pg.evals(rows), "evals")

    def artifact(self, run_id: str, step: int, kind: str, path: str = "", sha1: str = "", text: str = "") -> None:
        self.sqlite.artifact(run_id, step, kind, path, sha1, text)
        self._pg(lambda: self.pg.artifact(run_id, step, kind, path, sha1, text), f"artifact {kind}")

    def truncate_after(self, run_id: str, step: int) -> None:
        self.sqlite.truncate_after(run_id, step)
        self._pg(lambda: self.pg.truncate_after(run_id, step), f"truncate after {step}")

    def clear_step(self, run_id: str, step: int, tables: tuple[str, ...] = ("evals",), sets=None) -> None:
        self.sqlite.clear_step(run_id, step, tables=tables, sets=sets)
        self._pg(lambda: self.pg.clear_step(run_id, step, tables=tables, sets=sets), "clear step")

    def checkpoint_wal(self) -> None:
        self.sqlite.checkpoint_wal()

    def close(self) -> None:
        self.sqlite.close()
        self.pg.close()


def transient(e: BaseException) -> bool:
    """Whether a failed write is the store being out of reach for a while (Postgres down or restarting, the
    network, SQLite locked by another writer), so the same write may be tried again, rather than a fault in it."""
    if isinstance(e, sqlite3.OperationalError):
        return any(w in str(e).lower() for w in ("locked", "busy"))
    try:
        from thorp.store import StoreDown

        if isinstance(e, StoreDown):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        from sqlalchemy.exc import InterfaceError, OperationalError

        if isinstance(e, (OperationalError, InterfaceError)):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        import psycopg

        return isinstance(e, (psycopg.OperationalError, psycopg.InterfaceError))
    except Exception:  # noqa: BLE001
        return False


class BufferFull(RuntimeError):
    """The store has been out of reach for longer than the buffer will hold: the voyage stops, loudly."""


class MetricBuffer:
    """A trainer's per-step metrics, written many steps at a time (11 November, the audit's item 4).

    Until then every training step was one insert and one commit, and 16M rows for 200 runs were written that way.
    The buffer keeps each step's values with the time they were read (the `ts` the row would have had), and writes
    them all in one transaction when `every` steps are waiting (spec `ledger.flush_every`, default 25) or `seconds`
    have passed since the last write. The rows are the same rows; only when a reader can see them moves.

    The trainers flush it before every evaluation, before every checkpoint (strictly: a checkpoint is saved only
    when every row up to its step is in the store, so a resume, which forgets what lies after its checkpoint, never
    leaves a gap), at the end, and on the way out of an exception. A write the store refuses for a while (`transient`)
    keeps its rows for the next flush, with a warning; past `cap` steps waiting it raises BufferFull, so a long
    outage stops the voyage rather than eating memory. Any other failure raises at once, as the write did before."""

    def __init__(self, rec, every: int = 25, cap: int = 2000, seconds: float = 30.0, log=None,
                 tries: int = 3, wait: float = 5.0, sleep=time.sleep):  # fmt: skip
        self.rec, self.every, self.cap, self.seconds = rec, max(1, int(every)), int(cap), float(seconds)
        self.tries, self.wait, self.sleep = max(1, int(tries)), float(wait), sleep
        self.log = log or (lambda msg: print(msg, file=sys.stderr))
        self.rows: list[tuple[str, int, dict[str, float], float]] = []
        self._due, self._t_due = self.every, time.time() + self.seconds
        self.flushes = self.failures = 0

    def __len__(self) -> int:
        return len(self.rows)

    def add(self, run_id: str, step: int, values: dict[str, float]) -> None:
        """One step's values, written later (now, when a flush is due)."""
        if values:
            self.rows.append((run_id, step, dict(values), time.time()))
        if self.rows and (len(self.rows) >= self._due or time.time() >= self._t_due):
            self.flush()

    def _write(self) -> None:
        if hasattr(self.rec, "metrics_many"):
            self.rec.metrics_many(self.rows)
            self.rows = []
            return
        while self.rows:  # a recorder with no batch write: a step at a time, each kept until it is written
            rid, step, values, _ = self.rows[0]
            self.rec.metrics(rid, step, values)
            self.rows.pop(0)

    def flush(self, strict: bool = False) -> bool:
        """Write what is waiting. True when nothing is left waiting. A transient failure keeps the rows (and, when
        `strict`, is tried `tries` times, `wait` seconds apart, then raised); past `cap` steps it raises BufferFull."""
        attempts = self.tries if strict else 1
        for attempt in range(attempts):
            if not self.rows:
                return True
            try:
                self._write()
            except Exception as e:  # noqa: BLE001
                if not transient(e):
                    raise
                self.failures += 1
                n = len(self.rows)
                self._due, self._t_due = n + self.every, time.time() + self.seconds
                if n > self.cap:
                    raise BufferFull(
                        f"ledger: the store has refused {n} steps' metrics (steps {self.rows[0][1]}-{self.rows[-1][1]}),"
                        f" more than the {self.cap} the buffer holds: stopping the voyage ({e.__class__.__name__}: {e})"
                    ) from e
                self.log(f"ledger: {n} steps' metrics not written yet ({e.__class__.__name__}: {str(e)[:200]}); "
                         f"kept, and tried again {'in ' + str(self.wait) + ' s' if strict and attempt + 1 < attempts else 'at the next flush'}")  # fmt: skip
                if strict and attempt + 1 < attempts:
                    self.sleep(self.wait)
                    continue
                if strict:
                    raise
                return False
            self.flushes += 1
            self._due, self._t_due = self.every, time.time() + self.seconds
        return not self.rows

    def flush_quietly(self) -> None:
        """On the way out of an exception: write what can be written, and never hide the exception that is leaving."""
        try:
            self.flush()
        except Exception as e:  # noqa: BLE001
            self.log(f"ledger: {len(self.rows)} steps' metrics lost on the way out ({e.__class__.__name__}: {e})")


def flush_every(spec: dict) -> int:
    """The spec's `ledger.flush_every`: how many steps' metrics a trainer writes at once (default 25)."""
    return int(((spec.get("ledger") or {}).get("flush_every")) or 25)


def _use_pg() -> bool:
    """Whether the ledger is Postgres. On this Mac it is the default; a hired ship's box sets THORP_SHIP_LOG
    (its own SQLite log, folded in at docking). THORP_LEDGER_PG overrides either way; THORP_LEDGER_DUAL mirrors."""
    flag = os.environ.get("THORP_LEDGER_PG")
    if flag is not None:
        return flag.strip().lower() not in ("0", "false", "no", "off", "")
    return os.environ.get("THORP_SHIP_LOG", "").strip().lower() not in ("1", "true", "yes")


def recorder() -> Ledger | DualRecorder:
    """The recorder a new run writes to: Postgres by default (the Mac); a hired box (THORP_SHIP_LOG) keeps the
    plain Ledger; THORP_LEDGER_DUAL writes both. THORP_LEDGER_PG overrides."""
    if os.environ.get("THORP_LEDGER_DUAL"):
        from thorp.ledger_store import PgLedger

        return DualRecorder(Ledger(), PgLedger())
    if _use_pg():
        from thorp.ledger_store import PgLedger

        return PgLedger()
    return Ledger()


_READERS = __import__("threading").local()


def reader() -> Ledger:
    """The ledger the readers answer from: Postgres by default (the Mac); a hired box (THORP_SHIP_LOG) reads its
    own SQLite log. The Postgres reader is per thread and reused, so a page's many small queries share one session
    and connection (SQLAlchemy's session is not thread-safe)."""
    if _use_pg():
        from thorp.ledger_store import PgLedger

        r = getattr(_READERS, "pg", None)
        if r is None:
            r = PgLedger()
            _READERS.pg = r
        return r
    return Ledger()


def close_reader() -> None:
    """Close this thread's Postgres reader and return its connection to the pool.

    The dashboard's HTTP server handles each request on a short-lived thread; without this its per-thread
    PgLedger sessions are never closed and the pool runs dry (10 November: the page's later panels came
    back "QueuePool limit of size 5 overflow 10 reached", and their charts stayed blank)."""
    r = getattr(_READERS, "pg", None)
    if r is None:
        return
    try:
        r.close()
    except Exception:  # noqa: BLE001  a reader that cannot close must not fail the response
        pass
    del _READERS.pg
