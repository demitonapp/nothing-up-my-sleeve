"""S2: what keeps a chartered voyage from colliding with the rest of Nothing up my sleeve.

- **The berths**: no more ships hired at once than the terms allow (s5_policy.charter "max_instances"). Each
  charter holds a berth (a lock file) from its quote to its ship's release, so two `thorp charter sail` cannot
  both read "none out" and both hire. A charter does not take this Mac's helm (vsm.at_sea): its voyage is at sea
  on another GPU, and the standing queue keeps sailing here.
- **The ship's papers** (`papers`): a small ledger carried aboard, holding only what the voyage looks up: its own
  run row (so the box's gate knows the run S3 already passed here) and the runs it is seeded from, taught by or
  given heads by, with their artifacts. Never the 1.2 GB ledger itself.
- **Home** (`bring_home`): the voyage's rows from the box's ledger written into this one, the leg replacing what
  the ledger held after the step it set out from (as a resume does), never another run's rows.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

from thorp import paths
from thorp.ledger import reader, connect


class NoBerth(RuntimeError):
    pass


@contextlib.contextmanager
def berth(max_instances: int, name: str):
    """Hold one of the berths for the length of a charter; refuse at once when every berth is taken."""
    import fcntl

    d = paths.data_dir()
    d.mkdir(parents=True, exist_ok=True)
    for i in range(max(1, int(max_instances))):
        f = open(d / f"charter-berth-{i}.lock", "a+")  # noqa: SIM115
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            f.close()
            continue
        try:
            f.seek(0)
            f.truncate()
            f.write(name)
            f.flush()
            yield i
        finally:
            f.close()
        return
    raise NoBerth(f"every berth is taken ({max_instances} ship(s) hired at once is the limit)")


def related_runs(spec: dict) -> list[str]:
    """The finished runs a voyage reads from, as the spec names them: its seed, its teacher, its heads' donor. Each
    is a name or, since 11 November, a run id (forty hex characters, train.parent_run), which pins the very run where
    a name means the newest finished run of that name; `related_rows` finds either."""
    out = []
    for key, field in (("seeded_from", "run"), ("transplant", "from_run")):
        if (spec.get(key) or {}).get(field):
            out.append(spec[key][field])
    if ((spec.get("optim") or {}).get("teacher") or {}).get("run"):
        out.append(spec["optim"]["teacher"]["run"])
    return out


def related_rows(spec: dict, rec=None) -> list[dict]:
    """The run rows of related_runs: a run id by its id, a name by the newest finished run of that name (as the
    trainer resolves them, train.parent_run). A parent not found is left out, as before."""
    from thorp import versioning

    rec = rec or reader()
    out = []
    for ref in related_runs(spec):
        if versioning.is_run_id(ref):
            rows = rec.query("select * from runs where run_id=? and status='finished'", [ref])
        else:
            rows = rec.query("select * from runs where name=? and status='finished' order by started desc", [ref])
        if rows:
            out.append(rows[0])
    return out


def papers(dst: Path, spec: dict, rid: str, rec=None) -> list[str]:
    """Write the ship's papers to `dst`; returns the run ids carried (the voyage's own first)."""
    rec = rec or reader()
    if dst.exists():
        dst.unlink()
    out = connect(dst)
    carried = []
    own = rec.get_run(rid)
    row = own or {"run_id": rid, "name": spec.get("name"), "ship": spec.get("ship"), "status": "chartered"}
    from thorp import train

    row = {**row, "spec_json": row.get("spec_json") or train.canonical(spec)}
    _insert(out, "runs", [row])
    carried.append(rid)
    for r in related_rows(spec, rec):
        _insert(out, "runs", [r])
        _insert(out, "artifacts", rec.query("select * from artifacts where run_id=? and kind!='checkpoint'", [r["run_id"]]))
        carried.append(r["run_id"])
    out.commit()
    out.close()
    return carried


def _insert(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    # only the columns the box's SQLite log has (11 November): rows read from the store carry its own (`id`, the
    # yard and provenance columns of s1.runs), and the papers of any voyage with a row or a parent at home failed on
    # them. A later run column the box's ledger also knows (the SOP version) is added, as Ledger.run adds it.
    from thorp.ledger import LATER_RUN_COLUMNS

    have = {r[1] for r in con.execute(f"pragma table_info({table})")}
    if table == "runs":
        for c in LATER_RUN_COLUMNS:
            if c not in have and any(r.get(c) is not None for r in rows):
                con.execute(f'alter table runs add column "{c}" text')
                have.add(c)
    cols = [c for c in rows[0] if c in have]
    q = f"insert or replace into {table} ({', '.join(chr(34) + c + chr(34) for c in cols)}) values ({', '.join('?' for _ in cols)})"
    con.executemany(q, [[r[c] for c in cols] for r in rows])


FOLDED = {  # the tables a fold brings home, with the columns copied (the box's SQLite schema, thorp/ledger.py)
    "metrics": ("run_id", "step", "name", "value", "ts"),
    "evals": ("run_id", "step", "set", "book_id", "ce_nats", "bpb", "tokens", "bytes"),
    "artifacts": ("run_id", "step", "kind", "path", "sha1", "text"),
}


def _leg_rows(src: sqlite3.Connection, t: str, rid: str, lo: int) -> list[tuple]:
    """The leg's rows of one table on the box, each (rowid, *FOLDED[t]), in rowid order (the order they were written,
    which is the order they keep at home: the later row at one step stands)."""
    cols = ", ".join(f'"{c}"' for c in FOLDED[t])
    return [tuple(r) for r in src.execute(f"select rowid, {cols} from {t} where run_id=? and step>? order by rowid", (rid, lo))]


def _digest(rows: list[tuple]) -> str:
    import hashlib

    h = hashlib.sha1()
    for r in rows:
        h.update(repr(r).encode())
        h.update(b"\n")
    return h.hexdigest()


def _fold_sqlite(con: sqlite3.Connection, src: sqlite3.Connection, rid: str, lo: int) -> dict:
    """A SQLite ledger at home (a test's, or THORP_LEDGER_PG=0): the leg replaced whole, in one transaction."""
    counts = {}
    with con:
        for t, cols in FOLDED.items():
            con.execute(f"delete from {t} where run_id=? and step>?", (rid, lo))
            rows = _leg_rows(src, t, rid, lo)
            con.executemany(
                f"insert into {t} ({', '.join(chr(34) + c + chr(34) for c in cols)}) values ({', '.join('?' for _ in cols)})",
                [r[1:] for r in rows],
            )
            counts[t] = len(rows)
    return counts


def _fold_pg(src: sqlite3.Connection, rid: str, lo: int, run_row: dict) -> tuple[dict, dict]:
    """The leg into Postgres in ONE transaction, with the run row: per table, only the box's rows past its mark in
    s2.fold_marks when the box still holds, up to the mark, exactly the rows folded last time (same leg, same count,
    same digest) and home holds them too; otherwise the leg's rows at home are deleted and the box's written whole
    (as every fold did before 11 November), and the mark is set again. Folding twice changes nothing. Returns (the
    leg's rows per table, what the fold did per table)."""
    from sqlalchemy import delete, select, text
    from sqlalchemy import func as sa_func

    from thorp import ledger_store as ls
    from thorp import store

    classes = {"metrics": ls.Metric, "evals": ls.Eval, "artifacts": ls.Artifact}
    counts, done = {}, {}
    with store.session() as s:
        # one fold of a run at a time (a mid-run pull and an attach's), held to the end of this transaction
        s.execute(text("select pg_advisory_xact_lock(hashtext('fold:' || :rid))"), {"rid": rid})
        marked = s.scalar(text("select to_regclass('s2.fold_marks') is not null"))  # before its migration: replace
        for t, cols in FOLDED.items():
            cls, rows = classes[t], _leg_rows(src, t, rid, lo)
            counts[t] = len(rows)
            mark = s.get(ls.FoldMark, (rid, t), with_for_update=True) if marked else None
            new = None
            if mark is not None and int(mark.leg_start) == lo:
                upto = [r for r in rows if r[0] <= mark.last_id]
                at_home = s.scalar(select(sa_func.count()).select_from(cls).where(cls.run_id == rid, cls.step > lo))
                if len(upto) == mark.rows == at_home and _digest(upto) == mark.digest:
                    new = rows[len(upto):]
            if new is None:  # first fold of the leg, a new box, or a box resumed past a truncation: the leg again
                deleted = s.execute(delete(cls).where(cls.run_id == rid, cls.step > lo)).rowcount
                new = rows
                done[t] = {"mode": "replaced", "deleted": deleted, "inserted": len(rows)}
            else:
                done[t] = {"mode": "incremental" if new else "unchanged", "deleted": 0, "inserted": len(new)}
            if new:
                ls.insert_values(s, cls.__table__, [dict(zip(cols, r[1:], strict=True)) for r in new])
            if marked:
                vals = {"leg_start": lo, "last_id": rows[-1][0] if rows else 0, "rows": len(rows), "digest": _digest(rows)}
                if mark is None:
                    s.add(ls.FoldMark(run_id=rid, tbl=t, **vals))
                elif new or done[t]["mode"] == "replaced" or any(getattr(mark, k) != v for k, v in vals.items()):
                    for k, v in vals.items():
                        setattr(mark, k, v)
                    mark.folded_at = sa_func.now()
        s.flush()
        ls.put_run(s, run_row)
        # the box's status as its state row, in this transaction (item 11); never raises
        from thorp import run_state

        run_state.fold(s, run_row)
    return counts, done


def bring_home(box_ledger: Path, rid: str, leg_start: int, rec=None, **run_fields) -> dict:
    """The voyage's rows from the box's ledger into this one. What this ledger holds after `leg_start` (all of it
    when the leg set out from step 0) is the box's when the fold is done; `run_fields` (the commit, the hardware) are
    written over the box's run row. Returns the leg's rows per table, and under "fold" what each table's fold did.

    Into Postgres (11 November, the audit's item 4) the fold is one transaction, run row included, and incremental:
    a pull every 20 minutes inserts the rows the box wrote since the last one, never the whole leg again (`_fold_pg`).
    (Before, it went through PgLedger's SQLite-shaped `con`, whose delete raised ResourceClosedError: no fold into
    Postgres could have succeeded since the cut-over.) Into a SQLite ledger it replaces the leg, as before."""
    from thorp.ledger import DualRecorder, Ledger

    rec = rec or reader()
    src = sqlite3.connect(f"file:{box_ledger}?mode=ro", uri=True)
    try:
        src.row_factory = sqlite3.Row
        lo = leg_start if leg_start > 0 else -1
        run = src.execute("select * from runs where run_id=?", (rid,)).fetchone()
        if run is None:
            raise LookupError(f"the box's ledger has no run {rid}")
        run_row = {**dict(run), **run_fields}
        src.row_factory = None
        if isinstance(rec, Ledger) or isinstance(rec, DualRecorder):
            counts = _fold_sqlite((rec.sqlite if isinstance(rec, DualRecorder) else rec).con, src, rid, lo)
            (rec.sqlite if isinstance(rec, DualRecorder) else rec).run(run_row)
            if isinstance(rec, DualRecorder):  # the mirror, best-effort as all its writes are
                rec._pg(lambda: _fold_pg(src, rid, lo, run_row), "fold")
            return counts
        counts, done = _fold_pg(src, rid, lo, run_row)
        return {**counts, "fold": done}
    finally:
        src.close()


def note(rid: str, **fields) -> None:
    """A line in the voyage's own log (data/runs/<run id>.log) from the charter, beside the box's lines."""
    with contextlib.suppress(Exception):
        p = paths.runs_dir() / f"{rid}.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write("[charter] " + json.dumps(fields, ensure_ascii=False) + "\n")
