"""The one store: Nothing up my sleeve's records in Postgres (DECISIONS.md, "One store: Postgres, by the viable system"; the
tables in thorp/viable/records.py and s3_control/models.py, made by Alembic).

- **One engine**, from THORP_PG (or postgresql://thorp@localhost:5433/thorp), shared with the fitout store.
- **No silent fallback.** When Postgres cannot be reached, `session()` raises `StoreDown`: the S3 gate cannot record
  its decision and so does not make one (the voyage does not sail), and the dashboard says the store is down. No
  reader goes back to the old files; a cut-over file is renamed `*.imported` and nothing reads it.
- **The one exception is a hired box's papers.** A GPU hired from Vast.ai cannot reach this Mac's Postgres on
  localhost. The charter writes the S5 state the gate needs (`papers_for_box`) into a file carried aboard, and the
  box runs with THORP_PAPERS set to it: there the gate reads its policies from the papers and writes its decisions
  beside them (`papers_log`), and S1's charter brings that log home into `s3.gate_decisions` when the ship docks
  (`fold_gate_log`). Named in the environment, never chosen because the database was down.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from thorp.viable.s3_control import fitout_store


class StoreDown(RuntimeError):
    """Postgres could not be reached; nothing is recorded or read elsewhere instead."""


def url() -> str:
    return fitout_store.url()


def engine():
    return fitout_store.engine()


@contextlib.contextmanager
def session():
    """A session in one transaction, committed on leaving; StoreDown if the database cannot be reached."""
    try:
        s = Session(engine(), expire_on_commit=False)
        with s, s.begin():
            yield s
    except OperationalError as e:
        raise StoreDown(f"the store (Postgres, {_safe(url())}) cannot be reached: {e.orig!r}") from e


def _safe(u: str) -> str:
    """The URL without a password, for messages."""
    if "@" in u and ":" in u.split("@")[0].split("//")[-1]:
        head, tail = u.split("@", 1)
        return head.rsplit(":", 1)[0] + ":***@" + tail
    return u


def ping() -> str | None:
    """None when the store answers, else why not (for the dashboard's 'the store is down')."""
    from sqlalchemy import text

    try:
        with session() as s:
            s.execute(text("select 1"))
        return None
    except StoreDown as e:
        return str(e)


# ---------------------------------------------------------------- a hired box's papers


def papers() -> Path | None:
    """The papers this process sails under (a hired box), or None at home."""
    p = os.environ.get("THORP_PAPERS")
    return Path(p) if p else None


def read_papers() -> dict:
    p = papers()
    if p is None:
        raise RuntimeError("not sailing under papers (THORP_PAPERS is not set)")
    return json.loads(p.read_text(encoding="utf-8"))


def papers_log() -> Path:
    """Where a box's gate writes its decisions: beside its papers."""
    p = papers()
    assert p is not None
    return p.with_name(p.stem + ".gate-log.jsonl")


def papers_for_box() -> dict:
    """What a voyage aboard reads, from the store: S5's switches, exceptions and charter terms, S1's frozen stores and
    the sizes (fleet reads the ladder as it is imported, so every evaluator that imports it needs them)."""
    from thorp import liberty_machine

    return {"written": datetime.now().astimezone().isoformat(timespec="seconds"),
            "switches": liberty_machine._enforcement(), "exceptions": liberty_machine._exceptions(), "charter_terms": _charter_overrides(), "stores": _stores(), "sizes": _sizes()}  # fmt: skip


def _sizes() -> list[dict]:
    from thorp import ship_store

    return ship_store.sizes()


def _stores() -> dict:
    from thorp import stores

    return stores.stores()


def _charter_overrides() -> dict:
    from thorp.viable.s5_policy import charter as s5

    return s5.overrides()


def fold_gate_log(path: Path, source: str) -> int:
    """A box's gate decisions, brought home into s3.gate_decisions (each once: a line already folded is skipped)."""
    from thorp import liberty_machine

    if not path.exists():
        return 0
    n = 0
    for ln in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        n += liberty_machine.insert_gate_decision(r, source=source, once=True)
    return n
