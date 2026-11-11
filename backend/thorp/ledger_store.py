"""The ledger in Postgres (schema `s1`, S1 operations): `runs`, `metrics`, `evals` and `artifacts`.

This is the home side of the "one store" cut-over (DECISIONS.md, "One store: Postgres, by the viable system").
The SQLite ledger (`thorp/ledger.py`, `ledger.sqlite`) stays the writer of record while a voyage is at sea; this
module holds the Postgres tables those rows move into, and the read-only backfill that copies them with a per-run
count check.

- **The tables mirror the SQLite schema**, with one addition: `metrics`, `evals` and `artifacts` each carry an
  `id` (BIGSERIAL). SQLite's readers order by its implicit `rowid` ("the later row at one step stands"), and the
  explicit `id` is that same ordering in Postgres, preserved by copying rows in `rowid` order.
- **Nothing here is read by the dashboard yet.** The readers move over in the cut-over phase, after the backfill
  is verified. Until then `thorp/ledger.py` and `server.py` still read `ledger.sqlite`.
"""

from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import BigInteger, DateTime, Float, Index, Text, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from thorp.viable.s3_control.models import Base

SCHEMA = "s1"

# the SQLite ledger's columns, in its own order (thorp/ledger.py), so a row copies field for field
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
    "yard_id",
    "spec_sha",
    "artifact_root",
    "sop_version",)
EVAL_COLUMNS = ("run_id", "step", "set", "book_id", "ce_nats", "bpb", "tokens", "bytes")


def _eval_values(r) -> dict:
    """An evals row keyed by the model's attributes: the SQLite column `set` is the attribute `eval_set`."""
    return {
        "run_id": r["run_id"],
        "step": r["step"],
        "eval_set": r["set"],
        "book_id": r["book_id"],
        "ce_nats": r["ce_nats"],
        "bpb": r["bpb"],
        "tokens": r["tokens"],
        "bytes": r["bytes"],
    }


class Run(Base):
    """One voyage's own record (its spec, commit, hardware, status, tokens seen)."""

    __tablename__ = "runs"
    __table_args__ = (Index("runs_started", "started"), {"schema": SCHEMA})

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    ship: Mapped[str | None] = mapped_column(Text)
    spec_json: Mapped[str | None] = mapped_column(Text)
    sop_version: Mapped[str | None] = mapped_column(Text)  # FK s5.sop_versions(version), h9d2e5f7a1c3
    commit: Mapped[str | None] = mapped_column(Text)
    hardware: Mapped[str | None] = mapped_column(Text)
    started: Mapped[str | None] = mapped_column(Text)
    finished: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    tokens_seen: Mapped[int | None] = mapped_column(BigInteger)
    wall_minutes: Mapped[float | None] = mapped_column(Float)
    # provenance (10 November): who ran it, which spec (the run id is the spec's SHA-1), and a hash over the
    # run's artifacts, so a result can be accepted from a yard that is not this one
    yard_id: Mapped[str | None] = mapped_column(Text)
    spec_sha: Mapped[str | None] = mapped_column(Text)
    artifact_root: Mapped[str | None] = mapped_column(Text)


class Metric(Base):
    """One named reading at one training step. `id` preserves SQLite's `rowid` order ("later row stands")."""

    __tablename__ = "metrics"
    __table_args__ = (Index("metrics_run", "run_id", "name", "step", "id"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(Text)
    step: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Float)
    ts: Mapped[float] = mapped_column(Float)


class Eval(Base):
    """A held-out score at one step. The column is `set` (as in SQLite); the attribute is `eval_set`."""

    __tablename__ = "evals"
    __table_args__ = (Index("evals_run", "run_id", "step"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(Text)
    step: Mapped[int] = mapped_column(BigInteger)
    eval_set: Mapped[str] = mapped_column("set", Text)
    book_id: Mapped[str] = mapped_column(Text)
    ce_nats: Mapped[float | None] = mapped_column(Float)
    bpb: Mapped[float | None] = mapped_column(Float)
    tokens: Mapped[int | None] = mapped_column(BigInteger)
    bytes: Mapped[int | None] = mapped_column(BigInteger)


class Artifact(Base):
    """A checkpoint (kind `checkpoint`: a path and sha1) or a reading (every other kind: JSON in `text`)."""

    __tablename__ = "artifacts"
    __table_args__ = (Index("artifacts_run", "run_id", "kind", "step"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(Text)
    step: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text, default="", server_default="")
    sha1: Mapped[str] = mapped_column(Text, default="", server_default="")
    text: Mapped[str] = mapped_column(Text, default="", server_default="")


class FoldMark(Base):
    """How far a hired box's ledger has been folded home, per run and table (migration a8v1w4x7y0z3; written by
    s2_coordination.charter.bring_home, 11 November): the leg (`leg_start`), the box's last rowid folded, how many of
    the leg's rows the box held up to it, and a digest of them, so the next fold inserts only what is new."""

    __tablename__ = "fold_marks"
    __table_args__ = {"schema": "s2"}

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tbl: Mapped[str] = mapped_column(Text, primary_key=True)
    leg_start: Mapped[int] = mapped_column(BigInteger)
    last_id: Mapped[int] = mapped_column(BigInteger)
    rows: Mapped[int] = mapped_column(BigInteger)
    digest: Mapped[str] = mapped_column(Text)
    folded_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


def tables() -> list:
    """The tables this module defines, for the test fixtures' truncate."""
    return [m.local_table for m in Base.registry.mappers if m.class_.__module__ == __name__]


# ---------------------------------------------------------------- write helpers (bulk, shared by the backfill
# and, in the dual-write phase, the recorder)


def put_run(s, row: dict) -> None:
    """Upsert a runs row: a later call fills only the columns it carries (as SQLite's coalesce-on-conflict)."""
    row = {k: row.get(k) for k in RUN_COLUMNS}
    row["spec_sha"] = row.get("spec_sha") or row.get("run_id")
    if not row.get("yard_id"):
        try:
            from thorp import yard

            row["yard_id"] = yard.current()
        except Exception:  # noqa: BLE001  a box with no yard id still writes its run
            pass
    stmt = insert(Run).values(**row)
    # only overwrite a NULL column, so a second `run(...)` never blanks what the first wrote
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=["run_id"],
            set_={k: func.coalesce(stmt.excluded[k], getattr(Run, k)) for k in row if k != "run_id"},
        )
    )


def insert_values(s, table, rows: list[dict]) -> int:
    """Insert `rows` as multi-row VALUES statements (about 30,000 parameters each), never as an executemany.

    psycopg sends an executemany as one statement a row, so a statement-level trigger on the table (s1.metrics'
    metric_latest, migration z7u0v3w6x9y2) fires once a row: 20,000 metrics rows took 20.9 s that way on 11 November
    and 1.3 s as four multi-row statements. Returns the number of statements sent."""
    if not rows:
        return 0
    per = max(1, 30_000 // max(1, len(rows[0])))
    n = 0
    for i in range(0, len(rows), per):
        s.execute(insert(table).values(rows[i : i + per]))
        n += 1
    return n


def put_metrics(s, run_id: str, step: int, values: dict[str, float], ts: float) -> None:
    if not values:
        return
    s.execute(
        insert(Metric),
        [{"run_id": run_id, "step": step, "name": k, "value": float(v), "ts": ts} for k, v in values.items()],
    )


def put_evals(s, rows: list[dict]) -> None:
    if not rows:
        return
    s.execute(insert(Eval), [_eval_values(r) for r in rows])


def put_artifact(s, run_id: str, step: int, kind: str, path: str = "", sha1: str = "", text: str = "") -> None:
    s.execute(insert(Artifact).values(run_id=run_id, step=step, kind=kind, path=path, sha1=sha1, text=text))


# ---------------------------------------------------------------- the backfill


def backfill(only: list[str] | None = None, source: Path | None = None, log=print) -> dict:
    """Copy the SQLite ledger into Postgres, run by run, in rowid order.

    Reads the ledger read-only (a snapshot taken in port, or the live file, which WAL lets readers share), so it
    never disturbs a voyage at sea. A run already copied is deleted and copied again, so it is idempotent. Returns
    per-table counts copied, for the caller to check against SQLite.
    """
    import sqlite3

    from thorp import paths, store

    src = source or paths.ledger_path()
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True, check_same_thread=False, timeout=2.0)
    con.row_factory = sqlite3.Row

    runs = [dict(r) for r in con.execute("select * from runs order by started")]
    counts = {"runs": 0, "metrics": 0, "evals": 0, "artifacts": 0}
    with store.session() as s:
        for run in runs:
            rid = run["run_id"]
            if only:
                if rid not in only:
                    continue
            elif run.get("status") == "running":
                # a voyage at sea: its rows keep moving, so they are dual-written from the cut-over, not copied
                continue
            put_run(s, run)
            counts["runs"] += 1
            # a run's child rows are immutable once written, so re-copy whole and verified
            s.execute(delete(Metric).where(Metric.run_id == rid))
            s.execute(delete(Eval).where(Eval.run_id == rid))
            s.execute(delete(Artifact).where(Artifact.run_id == rid))
            counts["metrics"] += _copy_metrics(s, con, rid)
            counts["evals"] += _copy_evals(s, con, rid)
            counts["artifacts"] += _copy_artifacts(s, con, rid)
            log(f"ledger: {rid[:12]}: {counts['metrics']} metrics, {counts['evals']} evals, {counts['artifacts']} artifacts")
    con.close()
    return counts


_BATCH = 10_000


def _copy_metrics(s, con, rid: str) -> int:
    n = 0
    cur = con.execute(
        "select step, name, value, ts from metrics where run_id=? order by rowid", [rid]
    )
    while True:
        batch = cur.fetchmany(_BATCH)
        if not batch:
            break
        s.execute(
            insert(Metric),
            [{"run_id": rid, "step": r["step"], "name": r["name"], "value": r["value"], "ts": r["ts"]} for r in batch],
        )
        n += len(batch)
    return n


def _copy_evals(s, con, rid: str) -> int:
    n = 0
    cur = con.execute(
        'select run_id, step, "set", book_id, ce_nats, bpb, tokens, bytes from evals where run_id=? order by rowid',
        [rid],
    )
    while True:
        batch = cur.fetchmany(_BATCH)
        if not batch:
            break
        s.execute(insert(Eval), [_eval_values(r) for r in batch])
        n += len(batch)
    return n


def _copy_artifacts(s, con, rid: str) -> int:
    n = 0
    cur = con.execute(
        "select step, kind, path, sha1, text from artifacts where run_id=? order by rowid", [rid]
    )
    while True:
        batch = cur.fetchmany(_BATCH)
        if not batch:
            break
        s.execute(
            insert(Artifact),
            [{"run_id": rid, "step": r["step"], "kind": r["kind"], "path": r["path"], "sha1": r["sha1"], "text": r["text"]} for r in batch],
        )
        n += len(batch)
    return n


def verify(only: list[str] | None = None, source: Path | None = None, log=print) -> bool:
    """Per run, compare row counts between SQLite and Postgres. True when all match."""
    import sqlite3

    from thorp import paths, store

    src = source or paths.ledger_path()
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True, check_same_thread=False, timeout=2.0)
    runs = list(con.execute("select run_id, status from runs"))
    ok = True
    classes = {"metrics": Metric, "evals": Eval, "artifacts": Artifact}
    with store.session() as s:
        for rid, status in runs:
            if only:
                if rid not in only:
                    continue
            elif status == "running":
                continue
            for table, cls in classes.items():
                have = con.execute(f"select count(*) from {table} where run_id=?", [rid]).fetchone()[0]
                want = s.scalar(select(func.count()).select_from(cls).where(cls.run_id == rid))
                if have != want:
                    ok = False
                    log(f"ledger: MISMATCH {rid[:12]} {table}: sqlite {have}, postgres {want}")
    con.close()
    return ok


class _PgRow:
    """A row from `PgLedger.execute`, shaped like the `sqlite3.Row` the reader code was written against:
    indexable by position (`row[0]`) or by name (`row["value"]`), iterable over values, and still a mapping
    for `dict(row)` and `**row` (10 November: /api/class_score 500'd on `dict(r)` over a `_Result`)."""

    __slots__ = ("_d",)

    def __init__(self, d: dict):
        self._d = d

    def keys(self):
        return self._d.keys()

    def items(self):
        return self._d.items()

    def values(self):
        return self._d.values()

    def get(self, key, default=None):
        return self._d.get(key, default)

    def __getitem__(self, key):
        return list(self._d.values())[key] if isinstance(key, int) else self._d[key]

    def __iter__(self):
        return iter(self._d.values())

    def __len__(self) -> int:
        return len(self._d)

    def __repr__(self) -> str:
        return f"PgRow({self._d!r})"


class _PgResult:
    """The SQLite cursor's read surface (`fetchall`, `fetchone`, iteration) over PgLedger.query's rows."""

    __slots__ = ("_rows",)

    def __init__(self, rows: list[dict]):
        self._rows = [_PgRow(r) for r in rows]

    def fetchall(self) -> list[_PgRow]:
        return self._rows

    def fetchone(self) -> _PgRow | None:
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __getitem__(self, i):
        return self._rows[i]


class PgLedger:
    """The ledger's Postgres writer, a drop-in for the SQLite `Ledger`'s write side (run, metrics, evals,
    artifact, truncate_after, clear_step).

    One session, committed per call, as the SQLite `Ledger` is one connection, committed per call. During the
    dual-write phase the caller treats it as best-effort (a failure is logged, not raised, because SQLite is
    still authoritative); after the cut-over it is the one writer and a failure raises through `store`.
    """

    def __init__(self):
        from sqlalchemy.orm import Session

        from thorp import store

        self._s = Session(store.engine(), expire_on_commit=False)

    def _commit(self) -> None:
        self._s.commit()

    @staticmethod
    def _translate(sql: str) -> str:
        """SQLite's SQL as Postgres's: `?` becomes `%s`, rowid the explicit id, json_extract the jsonb path."""
        import re

        # a literal `%` (a LIKE pattern, 'loop-%') is not a placeholder in SQLite, but psycopg reads it as
        # one; escape it before `?` becomes `%s` (10 November: /api/discoveries 500'd on `like 'loop-%'`)
        q = sql.replace("%", "%%").replace("?", "%s").replace("rowid", "id")
        return re.sub(
            r"json_extract\(\s*((?:[A-Za-z_][A-Za-z0-9_]*\.)?spec_json)\s*,\s*'\$\.([^']+)'\s*\)",
            lambda m: f"({m.group(1)}::jsonb #>> '{{" + m.group(2).replace(".", ",") + "}')",
            q,
        )

    def query(self, sql: str, params: Iterable = ()) -> list[dict]:
        """The readers' raw SQL against s1 (see _translate). A failed read rolls back, so the next one
        on this thread's reused session is not stuck in the aborted transaction."""
        import contextlib

        from sqlalchemy.exc import OperationalError

        from thorp import store

        # a read that opened the transaction itself ends it (11 November): a long-lived reader (the coordinator's,
        # the charter's) otherwise sat "idle in transaction" for hours, holding a lock on s1.runs that made every
        # ALTER and every test fixture's TRUNCATE wait. A transaction someone else already had open is left alone.
        opened_here = not self._s.in_transaction()
        try:
            conn = self._s.connection()
            conn.exec_driver_sql("set search_path to s1, public")
            res = conn.exec_driver_sql(self._translate(sql), tuple(params))
            cols = list(res.keys())
            rows = [dict(zip(cols, r)) for r in res]
            if opened_here:
                self._s.commit()
            return rows
        except OperationalError as e:
            # the store cannot be reached: say so as every other reader of the one store does (StoreDown), so
            # a page reports the store down rather than a driver error; never answered from ledger.sqlite
            with contextlib.suppress(Exception):
                self._s.rollback()
            raise store.StoreDown(f"the store (Postgres, {store._safe(store.url())}) cannot be reached: {e.orig!r}") from e
        except Exception:
            self._s.rollback()
            raise

    def execute(self, sql: str, params: Iterable = ()):
        """A SQLite-cursor-shaped view of query(), so the reader code that does
        con.execute(sql, params).fetchall() / .fetchone() keeps working against PG."""
        return _PgResult(self.query(sql, params))

    def get_run(self, run_id: str) -> dict | None:
        rows = self.query("select * from runs where run_id=?", [run_id])
        return rows[0] if rows else None

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    class _Con:
        def __init__(self, pg):
            self._pg = pg

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

        def execute(self, sql: str, params: Iterable = ()):
            return self._pg.execute(sql, params)

        def executemany(self, sql: str, rows) -> None:
            conn = self._pg._s.connection()
            conn.exec_driver_sql("set search_path to s1, public")
            conn.connection.cursor().executemany(self._pg._translate(sql), [tuple(r) for r in rows])
            self._pg._s.commit()

    @property
    def con(self) -> "PgLedger._Con":
        return PgLedger._Con(self)

    def run(self, row: dict) -> None:
        put_run(self._s, row)
        self._commit()

    def metrics(self, run_id: str, step: int, values: dict[str, float]) -> None:
        if not values:
            return
        put_metrics(self._s, run_id, step, values, time.time())
        self._commit()

    def metrics_many(self, rows: list[tuple[str, int, dict[str, float], float]]) -> None:
        """Many steps' metrics, each (run_id, step, values, ts), as one insert in one transaction (the trainer's
        MetricBuffer, 11 November). A failure rolls back, so none is written and the session is clean to try again."""
        flat = [{"run_id": rid, "step": step, "name": k, "value": float(v), "ts": ts}
                for rid, step, values, ts in rows for k, v in values.items()]  # fmt: skip
        if not flat:
            return
        try:
            insert_values(self._s, Metric, flat)  # one statement for a flush's rows, not one a row
            self._commit()
        except Exception:
            self._s.rollback()
            raise

    def evals(self, rows: list[dict]) -> None:
        if not rows:
            return
        put_evals(self._s, rows)
        self._commit()

    def artifact(self, run_id: str, step: int, kind: str, path: str = "", sha1: str = "", text: str = "") -> None:
        put_artifact(self._s, run_id, step, kind, path, sha1, text)
        self._commit()

    def truncate_after(self, run_id: str, step: int) -> None:
        for cls in (Metric, Eval, Artifact):
            self._s.execute(delete(cls).where(cls.run_id == run_id, cls.step > step))
        self._commit()

    def clear_step(self, run_id: str, step: int, tables: tuple[str, ...] = ("evals",), sets=None) -> None:
        classes = {"metrics": Metric, "evals": Eval, "artifacts": Artifact}
        for t in tables:
            q = delete(classes[t]).where(classes[t].run_id == run_id, classes[t].step == step)
            if t == "evals" and sets is not None:
                q = q.where(Eval.eval_set.in_(list(sets)))
            self._s.execute(q)
        self._commit()

    def close(self) -> None:
        self._s.close()

    # -- reads (so a Postgres-only Mac lane can run a voyage straight against the store)
    def get_run(self, run_id: str) -> dict | None:
        return get_run(run_id)

    def get_run_by_name(self, name: str, finished: bool | None = None) -> dict | None:
        return get_run_by_name(name, finished)

    def find_run(self, arg: str) -> dict | None:
        return find_run(arg)

    def latest_artifact_text(self, run_id: str, kind: str) -> str | None:
        return latest_artifact_text(run_id, kind)

    def metric_at(self, run_id: str, name: str, which: str = "last") -> float | None:
        return metric_at(run_id, name, which)

    def runs_by_ship(self, ship: str) -> list[dict]:
        return runs_by_ship(ship)

    def checkpoint_wal(self) -> None:
        pass  # no WAL to checkpoint in Postgres


# ---------------------------------------------------------------- read helpers (the cut-over's readers)

_RUN_COLUMNS = ("run_id", "name", "ship", "spec_json", "commit", "hardware", "started", "finished", "status", "tokens_seen", "wall_minutes", "yard_id", "spec_sha", "artifact_root")


def get_run(run_id: str) -> dict | None:
    """One run's row, as the SQLite `Ledger.get_run` returns it (the `spec_json` stays a string)."""
    from thorp import store

    with store.session() as s:
        r = s.get(Run, run_id)
        return {c: getattr(r, c) for c in _RUN_COLUMNS} if r else None


def get_run_by_name(name: str, finished: bool | None = None) -> dict | None:
    """The newest run named `name` (optionally only finished ones), as `get_run` returns it."""
    from thorp import store

    q = select(Run).where(Run.name == name)
    if finished:
        q = q.where(Run.status == "finished")
    q = q.order_by(Run.started.desc().nullslast()).limit(1)
    with store.session() as s:
        r = s.scalar(q)
    return {c: getattr(r, c) for c in _RUN_COLUMNS} if r else None


def find_run(arg: str) -> dict | None:
    """A run by name, or by a unique prefix of its run_id (newest started first), as `get_run` returns it."""
    r = get_run_by_name(arg)
    if r:
        return r
    from thorp import store

    with store.session() as s:
        row = s.scalar(select(Run).where(Run.run_id.like(arg + "%")).order_by(Run.started.desc().nullslast()).limit(1))
    return {c: getattr(row, c) for c in _RUN_COLUMNS} if row else None


def latest_artifact_text(run_id: str, kind: str) -> str | None:
    """The latest artifact of `kind`'s text, or None (SQLite's `order by step desc, rowid desc limit 1`)."""
    from thorp import store

    q = (
        select(Artifact.text)
        .where(Artifact.run_id == run_id, Artifact.kind == kind)
        .order_by(Artifact.step.desc(), Artifact.id.desc())
        .limit(1)
    )
    with store.session() as s:
        return s.scalar(q)


def all_runs() -> list[dict]:
    """Every run, newest first, as `server.api_runs` reads them (without the per-run derived fields)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(select(Run).order_by(Run.started.desc().nullslast()))
        return [{c: getattr(r, c) for c in _RUN_COLUMNS} for r in rows]


def runs_by_ship(ship: str) -> list[dict]:
    """A ship's finished voyages, newest first (its sailings)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(
            select(Run).where(Run.ship == ship, Run.status == "finished").order_by(Run.started.desc().nullslast())
        )
        return [{c: getattr(r, c) for c in _RUN_COLUMNS} for r in rows]


def metrics_series(run_id: str) -> dict[str, list]:
    """A run's metrics as `server.api_metrics` returns them: {name: [[steps], [values]]}, the later row at one
    step standing (SQLite's `order by step, rowid`)."""
    from thorp import store

    out: dict[str, list] = {}
    with store.session() as s:
        rows = s.execute(
            select(Metric.step, Metric.name, Metric.value)
            .where(Metric.run_id == run_id)
            .order_by(Metric.step, Metric.id)
        ).all()
    for step, name, value in rows:
        series = out.setdefault(name, [[], []])
        if series[0] and series[0][-1] == step:
            series[1][-1] = value
        else:
            series[0].append(step)
            series[1].append(value)
    return out


def metric_at(run_id: str, name: str, which: str = "last") -> float | None:
    """The first or last value of one metric (SQLite's `_metric`)."""
    from thorp import store

    q = select(Metric.value).where(Metric.run_id == run_id, Metric.name == name).order_by(
        Metric.step.desc() if which == "last" else Metric.step.asc(), Metric.id.desc() if which == "last" else Metric.id.asc()
    ).limit(1)
    with store.session() as s:
        return s.scalar(q)


def evals(run_id: str) -> list[dict]:
    """A run's evals, as `server.api_evals` returns them (the column stays `set`)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(select(Eval).where(Eval.run_id == run_id).order_by(Eval.step, Eval.book_id, Eval.id))
        return [
            {"run_id": r.run_id, "step": r.step, "set": r.eval_set, "book_id": r.book_id,
             "ce_nats": r.ce_nats, "bpb": r.bpb, "tokens": r.tokens, "bytes": r.bytes}
            for r in rows
        ]


def latest_evals(run_id: str, eval_set: str) -> list[dict]:
    """A run's eval rows at its latest step for one set, as `{book_id, bpb}` (the SQLite `step=(select max(step) ...)`)."""
    from thorp import store

    with store.session() as s:
        max_step = s.scalar(
            select(func.max(Eval.step)).where(Eval.run_id == run_id, Eval.eval_set == eval_set)
        )
        if max_step is None:
            return []
        rows = s.scalars(
            select(Eval).where(
                Eval.run_id == run_id, Eval.eval_set == eval_set, Eval.step == max_step
            ).order_by(Eval.book_id, Eval.id)
        ).all()
    return [{"book_id": r.book_id, "bpb": r.bpb} for r in rows]


def artifact(run_id: str, kind: str, latest: bool = True) -> dict | None:
    """The latest (or first) artifact of a kind, as `server._artifact` returns it."""
    from thorp import store

    q = select(Artifact.step, Artifact.path, Artifact.sha1, Artifact.text).where(
        Artifact.run_id == run_id, Artifact.kind == kind
    ).order_by(Artifact.step.desc() if latest else Artifact.step.asc(), Artifact.id.desc() if latest else Artifact.id.asc()).limit(1)
    with store.session() as s:
        row = s.execute(q).first()
    return {"step": row[0], "path": row[1], "sha1": row[2], "text": row[3]} if row else None


def metric_series(run_id: str, name: str) -> list[list]:
    """[steps, values] for one named metric, ordered by step then id (the later row at one step stands)."""
    from thorp import store

    with store.session() as s:
        rows = s.execute(
            select(Metric.step, Metric.value)
            .where(Metric.run_id == run_id, Metric.name == name)
            .order_by(Metric.step, Metric.id)
        ).all()
    steps, values = [], []
    for step, value in rows:
        if steps and steps[-1] == step:
            values[-1] = value
        else:
            steps.append(step)
            values.append(value)
    return [steps, values]


def metrics_matching(run_id: str, prefix: str) -> list[dict]:
    """Rows [{name, step, value}] for metrics whose name starts with `prefix`, ordered by step then id."""
    from thorp import store

    with store.session() as s:
        rows = s.execute(
            select(Metric.name, Metric.step, Metric.value)
            .where(Metric.run_id == run_id, Metric.name.like(prefix + "%"))
            .order_by(Metric.step, Metric.id)
        ).all()
    return [{"name": n, "step": st, "value": v} for n, st, v in rows]


def metrics_max(run_id: str, names: list[str]) -> dict[str, float]:
    """{name: max value} over all rows for the given names (as SQLite's `select name, max(value) ... group by name`)."""
    from thorp import store

    if not names:
        return {}
    with store.session() as s:
        rows = s.execute(
            select(Metric.name, func.max(Metric.value))
            .where(Metric.run_id == run_id, Metric.name.in_(names))
            .group_by(Metric.name)
        ).all()
    return {n: x for n, x in rows if x is not None}


def metrics_named(run_id: str, names: set[str]) -> list[dict]:
    """Rows [{name, step, value}] for the exact names, value not null, ordered by step then id."""
    from thorp import store

    if not names:
        return []
    with store.session() as s:
        rows = s.execute(
            select(Metric.name, Metric.step, Metric.value)
            .where(Metric.run_id == run_id, Metric.name.in_(names), Metric.value.isnot(None))
            .order_by(Metric.step, Metric.id)
        ).all()
    return [{"name": n, "step": st, "value": v} for n, st, v in rows]


def metric_max_ts(run_id: str, name: str) -> float | None:
    """The latest write timestamp of one metric (as SQLite's `select max(ts) ...`)."""
    from thorp import store

    with store.session() as s:
        return s.scalar(select(func.max(Metric.ts)).where(Metric.run_id == run_id, Metric.name == name))


def artifacts_of_kind(run_id: str, kind: str) -> list[dict]:
    """Every artifact of a kind, ordered by step then id (as `select ... from artifacts where kind=? order by step, rowid`)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(
            select(Artifact).where(Artifact.run_id == run_id, Artifact.kind == kind).order_by(Artifact.step, Artifact.id)
        ).all()
    return [{"step": r.step, "path": r.path, "sha1": r.sha1, "text": r.text} for r in rows]


# ---------------------------------------------------------------- the newest value of every metric (11 November)
#
# `s1.metric_latest` (migration z7u0v3w6x9y2) holds, per (run_id, name), the metrics row that is newest by (step, id):
# its step, value, ts and id (`metric_id`). Statement-level triggers on s1.metrics keep it; `backfill_latest` fills
# it from the history (`thorp store latest`). The dashboard's "last value of each matching metric for every run"
# reads it (one table of ~200 x ~1,500 rows) instead of each run's whole history, and its name list narrows a
# history read to exact (run_id, name) index ranges (the architecture audit, item 7).

_FILL_RUN = """
insert into s1.metric_latest as l (run_id, name, step, value, ts, metric_id)
select distinct on (name) run_id, name, step, value, ts, id
from s1.metrics where run_id = :run
order by name desc, step desc, id desc
on conflict (run_id, name) do update
    set step = excluded.step, value = excluded.value, ts = excluded.ts, metric_id = excluded.metric_id
    where (excluded.step, excluded.metric_id) > (l.step, l.metric_id)
       or not exists (select 1 from s1.metrics m where m.id = l.metric_id)
"""
_PRUNE_RUN = """
delete from s1.metric_latest l
where l.run_id = :run and not exists (select 1 from s1.metrics m where m.id = l.metric_id)
"""
# every run_id in s1.metrics, by skipping along the (run_id, ...) index (a loose index scan: one probe a run, not a
# read of 16M index entries)
_METRIC_RUNS = """
with recursive r(run_id) as (
    (select run_id from s1.metrics order by run_id limit 1)
    union all
    select (select m.run_id from s1.metrics m where m.run_id > r.run_id order by m.run_id limit 1)
    from r where r.run_id is not null
)
select run_id from r where run_id is not null
"""


def backfill_latest(only: list[str] | None = None, log=print) -> dict:
    """Fill s1.metric_latest from s1.metrics, run by run, each in its own short transaction, so a trainer's insert
    (whose trigger upserts the same rows) never waits more than one run's fill. Idempotent: a stored row is replaced
    only by a newer one, or when the row it names is gone; a pair with no rows left is dropped. Returns the counts and
    the seconds taken."""
    from sqlalchemy import text

    from thorp import store

    t0 = time.time()
    with store.session() as s:
        runs = only or sorted(
            {r for (r,) in s.execute(text(_METRIC_RUNS))}
            | {r for (r,) in s.execute(text("select distinct run_id from s1.metric_latest"))}
        )
    upserted = pruned = 0
    for i, rid in enumerate(runs, 1):
        with store.session() as s:  # one transaction, committed on leaving
            upserted += s.execute(text(_FILL_RUN), {"run": rid}).rowcount
            pruned += s.execute(text(_PRUNE_RUN), {"run": rid}).rowcount
        if log and i % 25 == 0:
            log(f"metric_latest: {i}/{len(runs)} runs, {time.time() - t0:.1f}s")
    return {"runs": len(runs), "upserted": upserted, "pruned": pruned, "seconds": round(time.time() - t0, 1)}


def latest_mismatches(run_ids: list[str]) -> list[dict]:
    """Where s1.metric_latest differs from the newest metrics row per name, for these runs ([] when it agrees):
    the check behind `thorp store latest`, and the triggers' test."""
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        rows = s.execute(
            text(
                "with truth as (select distinct on (run_id, name) run_id, name, step, value, ts, id from s1.metrics"
                " where run_id = any(:runs) order by run_id, name, step desc, id desc)"
                " select coalesce(t.run_id, l.run_id) as run_id, coalesce(t.name, l.name) as name,"
                " t.step as want_step, t.value as want_value, t.id as want_id,"
                " l.step as got_step, l.value as got_value, l.metric_id as got_id"
                " from truth t full join (select * from s1.metric_latest where run_id = any(:runs)) l"
                " on l.run_id = t.run_id and l.name = t.name"
                " where t.id is distinct from l.metric_id or t.step is distinct from l.step"
                " or t.value is distinct from l.value or t.ts is distinct from l.ts"
            ),
            {"runs": list(run_ids)},
        ).mappings()
        return [dict(r) for r in rows]


def latest_rows(run_ids: list[str], prefixes: tuple[str, ...] = (), names: tuple[str, ...] = ()) -> list[dict]:
    """[{run_id, name, step, value, metric_id}] from s1.metric_latest: each run's newest row of every metric named
    in `names` or starting with one of `prefixes` (a LIKE prefix, as `metrics_matching` reads it), ordered by run,
    then (step, id) as the history is."""
    from sqlalchemy import text

    from thorp import store

    if not run_ids or not (prefixes or names):
        return []
    with store.session() as s:
        rows = s.execute(
            text(
                "select run_id, name, step, value, metric_id from s1.metric_latest"
                " where run_id = any(:runs) and (name = any(:names) or name like any(:likes))"
                " order by run_id, step, metric_id"
            ),
            {"runs": list(run_ids), "names": list(names), "likes": [p + "%" for p in prefixes]},
        ).mappings()
        return [dict(r) for r in rows]


def history_rows(
    run_ids: list[str], prefixes: tuple[str, ...] = (), names: tuple[str, ...] = (), flat_after: str = ""
) -> list[dict]:
    """[{run_id, name, step, value}] for every row of the matching metrics of these runs, ordered by run, then step,
    then id (as `metrics_matching` and `metric_series` read one run). The names come from s1.metric_latest, so the
    read is exact (run_id, name) index ranges, not a filter over each run's whole history. `flat_after` drops a
    name with a further "/" after that prefix (the readers' `count("/") > 1` for grad_norm/layer_<i>)."""
    from sqlalchemy import text

    from thorp import store

    if not run_ids or not (prefixes or names):
        return []
    flat = " and l.name not like :deeper" if flat_after else ""
    with store.session() as s:
        rows = s.execute(
            text(
                "select m.run_id, m.name, m.step, m.value from s1.metric_latest l"
                " join s1.metrics m on m.run_id = l.run_id and m.name = l.name"
                " where l.run_id = any(:runs) and (l.name = any(:names) or l.name like any(:likes))" + flat +
                " order by m.run_id, m.step, m.id"
            ),
            {"runs": list(run_ids), "names": list(names), "likes": [p + "%" for p in prefixes],
             "deeper": flat_after + "%/%"},
        ).all()
    return [{"run_id": r, "name": n, "step": st, "value": v} for r, n, st, v in rows]


def metric_names(run_id: str) -> list[str]:
    """A run's metric names, from s1.metric_latest (sorted)."""
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        return [n for (n,) in s.execute(text("select name from s1.metric_latest where run_id = :r order by name"), {"r": run_id})]


def metrics_series_named(run_id: str, names: list[str]) -> dict[str, list]:
    """`metrics_series` for the named metrics only: {name: [[steps], [values]]}, the later row at one step standing."""
    from thorp import store

    out: dict[str, list] = {}
    if not names:
        return out
    with store.session() as s:
        rows = s.execute(
            select(Metric.step, Metric.name, Metric.value)
            .where(Metric.run_id == run_id, Metric.name.in_(list(names)))
            .order_by(Metric.step, Metric.id)
        ).all()
    for step, name, value in rows:
        series = out.setdefault(name, [[], []])
        if series[0] and series[0][-1] == step:
            series[1][-1] = value
        else:
            series[0].append(step)
            series[1].append(value)
    return out


def runs_rows(run_ids: list[str] | None = None) -> list[dict]:
    """Rows of s1.runs as `all_runs` gives them, newest first, optionally only these ids (one query)."""
    from thorp import store

    q = select(Run).order_by(Run.started.desc().nullslast())
    if run_ids is not None:
        q = q.where(Run.run_id.in_(list(run_ids)))
    with store.session() as s:
        return [{c: getattr(r, c) for c in _RUN_COLUMNS} for r in s.scalars(q)]


def first_artifacts(run_ids: list[str], kind: str) -> dict[str, dict]:
    """{run_id: {step, path, sha1, text}}: each run's first artifact of a kind (`artifact(..., latest=False)`), in one query."""
    from sqlalchemy import text

    from thorp import store

    if not run_ids:
        return {}
    with store.session() as s:
        rows = s.execute(
            text(
                "select distinct on (run_id) run_id, step, path, sha1, text from s1.artifacts"
                " where run_id = any(:runs) and kind = :kind order by run_id, step, id"
            ),
            {"runs": list(run_ids), "kind": kind},
        ).mappings()
        return {r["run_id"]: {"step": r["step"], "path": r["path"], "sha1": r["sha1"], "text": r["text"]} for r in rows}


def artifacts_of_kind_many(run_ids: list[str], kind: str) -> dict[str, list[dict]]:
    """{run_id: [{step, text}]}: `artifacts_of_kind` for many runs in one query (step, then id, order)."""
    from sqlalchemy import text

    from thorp import store

    out: dict[str, list[dict]] = {}
    if not run_ids:
        return out
    with store.session() as s:
        for r in s.execute(
            text("select run_id, step, text from s1.artifacts where run_id = any(:runs) and kind = :kind order by run_id, step, id"),
            {"runs": list(run_ids), "kind": kind},
        ).mappings():
            out.setdefault(r["run_id"], []).append({"step": r["step"], "text": r["text"]})
    return out


def history_of_pairs(pairs: list[tuple[str, str]]) -> list[dict]:
    """[{run_id, name, step, value}] for every row of these exact (run_id, name) pairs, ordered by run, then step,
    then id: one index range a pair, in one query."""
    from sqlalchemy import text

    from thorp import store

    if not pairs:
        return []
    with store.session() as s:
        rows = s.execute(
            text(
                "select m.run_id, m.name, m.step, m.value from unnest(cast(:runs as text[]), cast(:names as text[])) as p(run_id, name)"
                " join s1.metrics m on m.run_id = p.run_id and m.name = p.name order by m.run_id, m.step, m.id"
            ),
            {"runs": [p[0] for p in pairs], "names": [p[1] for p in pairs]},
        ).all()
    return [{"run_id": r, "name": n, "step": st, "value": v} for r, n, st, v in rows]
