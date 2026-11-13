"""The discoveries payload in Postgres (schema `s1`): the stars, traits, known heads and tricks, card
verdicts, chain rungs, methods and waypoints that the goals and scoring tabs read.

Built once by `thorp store discoveries` (or on the first read when the row is missing) and stored as one
JSONB document. The page reads this row instead of rebuilding the matrix from ~12,000 metric queries
(10 November: the goals tab paid 8-44 s because every stars x runs timeline and every run's probe series
was recomputed on the request that found the 60 s cache stale). The row is the cache; the payload is a
reading of the ledger, so a rebuild is a `thorp store discoveries` away.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from thorp import store

KEY = "all"


def ensure() -> None:
    """The table is Alembic's (migration f7b9d1e3a5c8): no runtime DDL (S5 policy 'postgres', 13 November). Kept so the callers read
    as they did; it has nothing to do."""


def put(payload: dict, runs: int | None = None) -> None:
    """Write the document (one row, key 'all'), replacing the last build."""
    ensure()
    with store.engine().begin() as c:
        c.execute(
            text(
                """insert into s1.discoveries (key, payload, built_at, runs)
                   values (:k, cast(:p as jsonb), now(), :r)
                   on conflict (key) do update set payload = excluded.payload,
                     built_at = excluded.built_at, runs = excluded.runs"""
            ),
            {"k": KEY, "p": json.dumps(payload, default=str), "r": runs},
        )


def get() -> dict | None:
    """The stored document, or None when it has never been built (psycopg may hand JSONB back as a dict or a str)."""
    try:
        ensure()
        with store.engine().begin() as c:
            row = c.execute(text("select payload from s1.discoveries where key = :k"), {"k": KEY}).first()
    except Exception:  # noqa: BLE001 (the caller falls back to a live build)
        return None
    if not row:
        return None
    value = row[0]
    return json.loads(value) if isinstance(value, str) else value


def age() -> float | None:
    """Seconds since the last build, or None when there is no row."""
    try:
        with store.engine().begin() as c:
            value = c.execute(
                text("select extract(epoch from now() - built_at) from s1.discoveries where key = :k"),
                {"k": KEY},
            ).scalar()
    except Exception:  # noqa: BLE001
        return None
    return float(value) if value is not None else None
