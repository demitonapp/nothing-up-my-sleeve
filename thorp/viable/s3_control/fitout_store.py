"""The fitout store: fitouts and their prechecks in Postgres, through the SQLAlchemy models (models.py), the
schema made and changed only by Alembic (migrations/). Owned by S3 control: the fitouts are the resources
every voyage draws on, and the prechecks are the bargain a fitout must keep before it may sail.

The database is Thorp's own local cluster (`data/postgres`, outside git: the ledger swap of 2026-11-07 18:11 is
why), on `localhost:5433`, database `thorp` (override with THORP_PG). Started with:

    LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D data/postgres -l data/postgres.log \\
        -o "-p 5433 -k /tmp -c listen_addresses=localhost" start
    uv run alembic upgrade head
"""

from __future__ import annotations

import functools
import os

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from thorp import paths
from thorp.viable.s3_control.models import (
    Fitout,
    FitoutPrecheck,
    PrecheckItem,
    PrecheckResult,
    Stage,
)

DEFAULT_URL = "postgresql://thorp@localhost:5433/thorp"


def url() -> str:
    return os.environ.get("THORP_PG", DEFAULT_URL)


@functools.cache
def engine():
    u = url()
    return create_engine(u.replace("postgresql://", "postgresql+psycopg://", 1), pool_pre_ping=True)


def session() -> Session:
    return Session(engine(), expire_on_commit=False)


def migrate() -> None:
    """Bring the database to the latest models (alembic upgrade head)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(paths.resolve("alembic.ini")))
    cfg.set_main_option("script_location", str(paths.resolve("migrations")))
    command.upgrade(cfg, "head")


def put_fitout(f: dict, adopted: str = "") -> None:
    """A fitout (the saved form, thorp/fitouts.py) and its stages, written or replaced."""
    with session() as s, s.begin():
        row = s.get(Fitout, f["key"]) or Fitout(key=f["key"])
        row.name, row.aim, row.clean = f["name"], f.get("aim") or "", f["clean"]
        row.tokeniser, row.positions = dict(f.get("tokeniser") or {}), f.get("positions") or "rope"
        if adopted:
            row.adopted = adopted
        row.stages = [
            Stage(
                ordinal=i,
                phase=st["phase"],
                name=st["name"],
                library=st["shelf"],
                tokens=st.get("tokens"),
                selection=st.get("select") or "all",
                passes=st.get("passes") or 1,
                lr=st.get("lr"),
                tack=st.get("tack"),
                purpose=st.get("purpose") or "",
            )
            for i, st in enumerate(f.get("stages") or [], 1)
        ]
        s.merge(row)


def put_items(items) -> None:
    """The precheck catalogue (prechecks.ITEMS), written or replaced item by item."""
    with session() as s, s.begin():
        for it in items:
            s.merge(
                PrecheckItem(
                    key=it.key,
                    name=it.name,
                    about=it.about,
                    system=it.system,
                    kind=it.kind,
                    measure=it.measure,
                    comparator=it.comparator,
                    threshold=it.threshold,
                    clean_version=it.clean_version,
                )
            )


def require(fitout_key: str, item_key: str, required: bool = True, note: str = "") -> None:
    with session() as s, s.begin():
        s.merge(FitoutPrecheck(fitout_key=fitout_key, item_key=item_key, required=required, note=note))


def record(fitout_key: str, item_key: str, value, passed: bool, evidence: dict, by: str) -> None:
    with session() as s, s.begin():
        s.add(
            PrecheckResult(
                fitout_key=fitout_key,
                item_key=item_key,
                value=None if value is None else float(value),
                passed=bool(passed),
                evidence=evidence,
                checked_by=by,
            )
        )


def readiness(fitout_key: str) -> dict | None:
    with engine().connect() as c:
        r = c.execute(
            text("select * from fitout.readiness where fitout_key = :k"), {"k": fitout_key}
        ).mappings().first()
        return dict(r) if r else None


def checklist(fitout_key: str) -> list[dict]:
    """The fitout's prechecks with each one's current reading, for the gate and the dashboard."""
    with engine().connect() as c:
        rows = c.execute(
            text(
                """select fp.item_key, fp.required, fp.note, i.name, i.about, i.system, i.kind, i.measure,
                          i.comparator, i.threshold, i.clean_version, r.value, r.passed, r.evidence,
                          r.checked_at, r.checked_by
                   from fitout.fitout_prechecks fp
                   join fitout.precheck_items i on i.key = fp.item_key
                   left join fitout.current_results r
                     on r.fitout_key = fp.fitout_key and r.item_key = fp.item_key
                   where fp.fitout_key = :k
                   order by fp.required desc, i.system, fp.item_key"""
            ),
            {"k": fitout_key},
        ).mappings()
        return [dict(r) for r in rows]


def set_status(fitout_key: str, status: str) -> None:
    with session() as s, s.begin():
        row = s.get(Fitout, fitout_key)
        if row is not None:
            row.status = status


def fitouts() -> list[dict]:
    with session() as s:
        return [
            {"key": f.key, "name": f.name, "clean": f.clean, "status": f.status}
            for f in s.scalars(select(Fitout).order_by(Fitout.created_at))
        ]
