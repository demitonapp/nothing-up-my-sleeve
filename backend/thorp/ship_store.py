"""The ships in Postgres (schema `s1`, S1 operations, models in thorp/viable/s3_control/models.py, made by Alembic): the
sizes (each rung's name, role, where it trains and the metrics that judge it), the ships (a size fitted out
one way) and their voyages (the runs; their metrics and status stay in the ledger).

Nothing here is a list in code: a size is named and described in `s1.sizes`, a ship registered in
`s1.ships` (Justin, 2026-11-08: "these things shouldn't be hardcoded, we have postgres for a reason").
"""

from __future__ import annotations

import functools

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from thorp.viable.s3_control.fitout_store import session
from thorp.viable.s3_control.models import ShipRecord, Size, VoyageRecord


@functools.cache
def _sizes() -> tuple[dict, ...]:
    with session() as s:
        rows = s.scalars(select(Size).order_by(Size.ordinal)).all()
        return tuple(
            {
                "preset": r.preset,
                "name": r.name,
                "role": r.role,
                "job": r.role,  # the older word for it, as the dashboard and the bet read it
                "overview": r.overview,
                "kind": r.kind,
                "vocab": r.vocab,
                "where": r.trains_where,
                "status": r.status,
                "scored": r.scored,
                "metrics": r.metrics,
            }
            for r in rows
        )


def sizes() -> list[dict]:
    """Every size, smallest first, as dicts (cached for the process; `reload()` after a change). A kind or a
    vocabulary a size does not have is left out, not None, so a reader's own default applies."""
    return [{k: v for k, v in r.items() if not (k in ("kind", "vocab") and v is None)} for r in _sizes()]


def size_of(preset: str) -> str:
    """The size a preset belongs to: itself, or the size a variant is cut from (300k-h4 -> 300k)."""
    known = {r["preset"] for r in _sizes()}
    if preset in known:
        return preset
    base = preset.split("-")[0]
    if base in known:
        return base
    raise KeyError(f"no size for preset {preset!r}; known: {sorted(known)}")


def reload() -> None:
    _sizes.cache_clear()


def ships() -> list[ShipRecord]:
    with session() as s:
        return list(s.scalars(select(ShipRecord).order_by(ShipRecord.created_at, ShipRecord.key)))


def get_ship(key: str) -> ShipRecord | None:
    with session() as s:
        return s.get(ShipRecord, key)


def add_ship(rec: dict) -> ShipRecord:
    """Register a ship once; a ship already registered under the key is kept as it is (names never move)."""
    with session() as s, s.begin():
        s.execute(insert(ShipRecord).values(**rec).on_conflict_do_nothing(index_elements=["key"]))
    return get_ship(rec["key"])


def add_voyage(run_id: str, ship_key: str, name: str, seed: int | None, started: str | None) -> None:
    """A run joins its ship's voyages (once; a later call fills a start time it lacked)."""
    with session() as s, s.begin():
        stmt = insert(VoyageRecord).values(
            run_id=run_id, ship_key=ship_key, name=name, seed=seed, started=started
        )
        s.execute(
            stmt.on_conflict_do_update(
                index_elements=["run_id"],
                set_={"started": stmt.excluded.started},
                where=VoyageRecord.started.is_(None),
            )
        )


def voyages(ship_key: str | None = None) -> list[VoyageRecord]:
    with session() as s:
        q = select(VoyageRecord).order_by(VoyageRecord.started)
        if ship_key:
            q = q.where(VoyageRecord.ship_key == ship_key)
        return list(s.scalars(q))
