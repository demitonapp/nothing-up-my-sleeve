"""The fitout store: fitouts and their prechecks in Postgres, through the SQLAlchemy models (models.py), the
schema made and changed only by Alembic (migrations/). Owned by S3 control: the fitouts are the resources
every voyage draws on, and the prechecks are the bargain a fitout must keep before it may sail.

The database is Nothing up my sleeve's own local cluster (`data/postgres`, outside git: the ledger swap of 2026-11-07 18:11 is
why), on `localhost:5433`, database `thorp` (override with THORP_PG). Started with:

    LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D data/postgres -l data/postgres.log \\
        -o "-p 5433 -k /tmp -c listen_addresses=localhost" start
    uv run alembic upgrade head
"""

from __future__ import annotations

import contextlib
import functools
import os

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from thorp import config, paths
from thorp.viable.s3_control.models import (
    Composition,
    Fitout,
    FitoutPrecheck,
    LibraryBranch,
    LibraryFact,
    LibraryVariation,
    PrecheckItem,
    PrecheckResult,
    Stage,
)

DEFAULT_URL = "postgresql://thorp@localhost:5433/thorp"


def url() -> str:
    """The store's address: THORP_PG first, then the install's own choice, then the local default."""
    return os.environ.get("THORP_PG", "").strip() or config.store_url() or DEFAULT_URL


def reset_engine() -> None:
    """Forget the cached engine (the store was switched from the settings page or the first run).
    A caller that still holds a session keeps it; new work opens the new store."""
    old = engine.cache_info()
    if old.currsize:
        with contextlib.suppress(Exception):
            engine().dispose()
    engine.cache_clear()


@functools.cache
def engine():
    u = url()
    # the dashboard serves many panels at once on a threaded server; the default pool (5 + 10) ran dry
    # under a page's burst of /api calls, which surfaced as blank panels and 30 s "QueuePool limit"
    # timeouts (10 November). Postgres allows 100 connections here; 20 + 20 leaves room for training.
    return create_engine(
        u.replace("postgresql://", "postgresql+psycopg://", 1),
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=20,
        pool_recycle=1800,
    )


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
                compose=st.get("compose") or None,
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
            text("select * from s3.readiness where fitout_key = :k"), {"k": fitout_key}
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
                   from s3.fitout_prechecks fp
                   join s3.precheck_items i on i.key = fp.item_key
                   left join s3.current_results r
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


# ---- the library's facts and the compositions (thorp/library_facts.py, thorp/selection.py)
_FACT_COLUMNS = (
    "book", "title", "author", "source", "set", "language", "translated", "born", "died", "gate_death", "year",
    "year_basis", "kind", "kind_rule", "voice", "voice_rule", "ogden", "ogden_from", "words", "fetched", "held_out",
    "control", "title_key", "shelves",
)  # fmt: skip


def put_facts(rows: list[dict], fingerprint: str) -> int:
    """The library's facts, replaced whole (a book gone from the manifest is gone from the table)."""
    with session() as s, s.begin():
        s.execute(text("delete from s3.library_facts"))
        s.add_all(LibraryFact(**{k: r[k] for k in _FACT_COLUMNS}, facts_fingerprint=fingerprint) for r in rows)
    return len(rows)


def facts_fingerprint() -> str | None:
    with engine().connect() as c:
        return c.execute(text("select max(facts_fingerprint) from s3.library_facts")).scalar()


def record_composition(c: dict) -> int:
    with session() as s, s.begin():
        row = Composition(**c)
        s.add(row)
        s.flush()
        return row.id


def compositions(fitout_key: str | None = None, limit: int = 20) -> list[dict]:
    q = "select * from s3.compositions" + (" where fitout_key = :k" if fitout_key else "") + " order by composed_at desc, id desc limit :n"
    with engine().connect() as c:
        return [dict(r) for r in c.execute(text(q), {"k": fitout_key, "n": limit}).mappings()]


def selections(fitout_key: str) -> list[dict]:
    """A fitout's stages with the selection each declares (None: its library is listed by hand)."""
    with engine().connect() as c:
        return [dict(r) for r in c.execute(
            text("select ordinal, name, library, compose from s3.stages where fitout_key = :k order by ordinal"),
            {"k": fitout_key}).mappings()]  # fmt: skip


def seed_branches(defaults: list[dict]) -> tuple[int, int]:
    """The default branches and variations written where missing; one Justin has changed or added is left as it is."""
    nb = nv = 0
    with session() as s, s.begin():
        for i, b in enumerate(defaults):
            if s.get(LibraryBranch, b["key"]) is None:
                s.add(LibraryBranch(key=b["key"], name=b["name"], purpose=b["purpose"], ordinal=i))
                nb += 1
            s.flush()
            for j, v in enumerate(b["variations"]):
                if s.get(LibraryVariation, v["key"]) is None:
                    s.add(LibraryVariation(key=v["key"], branch_key=b["key"], name=v["name"], about=v.get("about", ""), ordinal=j,
                                           list_path=v.get("list"), spec=v.get("spec"), is_all=bool(v.get("all")),
                                           derived_from=v.get("derived_from"), draft=bool(v.get("draft"))))
                    nv += 1
    return nb, nv


def branches() -> list[dict]:
    """The branches with their variations, in order: [{key, name, purpose, variations: [{key, name, about, list, spec,
    all, derived_from, draft}]}]."""
    with session() as s:
        out = []
        for b in s.scalars(select(LibraryBranch).order_by(LibraryBranch.ordinal)):
            vs = s.scalars(select(LibraryVariation).where(LibraryVariation.branch_key == b.key).order_by(LibraryVariation.ordinal))
            out.append({"key": b.key, "name": b.name, "purpose": b.purpose, "variations": [
                {"key": v.key, "name": v.name, "about": v.about, "list": v.list_path, "spec": v.spec, "all": v.is_all,
                 "derived_from": v.derived_from, "draft": v.draft} for v in vs]})
        return out
