"""The ledger: the only writer of ledger.sqlite, and the Recorder protocol other sinks can implement."""

from __future__ import annotations

import json
import sqlite3
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


class Recorder(Protocol):
    def run(self, row: dict) -> None: ...
    def metrics(self, run_id: str, step: int, values: dict[str, float]) -> None: ...
    def evals(self, rows: Iterable[dict]) -> None: ...
    def artifact(
        self, run_id: str, step: int, kind: str, path: str = "", sha1: str = "", text: str = ""
    ) -> None: ...


def connect(path: Path | None = None, readonly: bool = False) -> sqlite3.Connection:
    path = path or paths.ledger_path()
    if readonly:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
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
    def run(self, row: dict) -> None:
        row = {k: row.get(k) for k in RUN_COLUMNS}
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

    def checkpoint_wal(self) -> None:
        self.con.execute("pragma wal_checkpoint(truncate)")

    def close(self) -> None:
        self.con.close()


def spec_of(run: dict) -> dict:
    return json.loads(run["spec_json"])
