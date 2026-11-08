"""S2: what keeps a chartered voyage from colliding with the rest of Thorp.

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
from thorp.ledger import Ledger, connect


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
    """The names of the finished runs a voyage reads from: its seed, its teacher, its heads' donor."""
    out = []
    for key, field in (("seeded_from", "run"), ("transplant", "from_run")):
        if (spec.get(key) or {}).get(field):
            out.append(spec[key][field])
    if ((spec.get("optim") or {}).get("teacher") or {}).get("run"):
        out.append(spec["optim"]["teacher"]["run"])
    return out


def papers(dst: Path, spec: dict, rid: str, rec: Ledger | None = None) -> list[str]:
    """Write the ship's papers to `dst`; returns the run ids carried (the voyage's own first)."""
    rec = rec or Ledger()
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
    for name in related_runs(spec):
        rows = rec.query("select * from runs where name=? and status='finished' order by started desc", [name])
        if not rows:
            continue
        r = rows[0]
        _insert(out, "runs", [r])
        _insert(out, "artifacts", rec.query("select * from artifacts where run_id=? and kind!='checkpoint'", [r["run_id"]]))
        carried.append(r["run_id"])
    out.commit()
    out.close()
    return carried


def _insert(con: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0])
    q = f"insert or replace into {table} ({', '.join(chr(34) + c + chr(34) for c in cols)}) values ({', '.join('?' for _ in cols)})"
    con.executemany(q, [[r[c] for c in cols] for r in rows])


def bring_home(box_ledger: Path, rid: str, leg_start: int, rec: Ledger | None = None, **run_fields) -> dict:
    """The voyage's rows from the box's ledger into this one. What this ledger holds after `leg_start` (all of it
    when the leg set out from step 0) is replaced by the box's; `run_fields` (the commit, the hardware) are
    written over the box's run row. Returns the counts brought home."""
    rec = rec or Ledger()
    src = sqlite3.connect(f"file:{box_ledger}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    lo = leg_start if leg_start > 0 else -1
    run = src.execute("select * from runs where run_id=?", (rid,)).fetchone()
    if run is None:
        raise LookupError(f"the box's ledger has no run {rid}")
    counts = {}
    with rec.con:
        for t in ("metrics", "evals", "artifacts"):
            rec.con.execute(f"delete from {t} where run_id=? and step>?", (rid, lo))
            rows = [dict(r) for r in src.execute(f"select * from {t} where run_id=? and step>?", (rid, lo))]
            if rows:
                cols = list(rows[0])
                rec.con.executemany(
                    f"insert into {t} ({', '.join(chr(34) + c + chr(34) for c in cols)}) values ({', '.join('?' for _ in cols)})",
                    [[r[c] for c in cols] for r in rows],
                )
            counts[t] = len(rows)
    src.close()
    rec.run({**dict(run), **run_fields})
    return counts


def note(rid: str, **fields) -> None:
    """A line in the voyage's own log (data/runs/<run id>.log) from the charter, beside the box's lines."""
    with contextlib.suppress(Exception):
        p = paths.runs_dir() / f"{rid}.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write("[charter] " + json.dumps(fields, ensure_ascii=False) + "\n")
