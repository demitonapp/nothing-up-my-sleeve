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
from thorp.viable.s3_control.models import (
    Harbour,
    Journey,
    ShipRecord,
    Size,
    VoyageRecord,
)


@functools.cache
def _sizes() -> tuple[dict, ...]:
    from thorp import store

    if store.papers():  # aboard a hired box (no Postgres): the sizes as they were when it sailed
        return tuple(dict(r) for r in store.read_papers().get("sizes") or ())
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
                "layers": r.layers,
                "width": r.width,
                "heads": r.heads,
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


def _at_home(what: str) -> None:
    from thorp import store

    if store.papers():
        raise RuntimeError(f"aboard a hired box there is no store: {what}")


def reload() -> None:
    _sizes.cache_clear()


def set_goals(preset: str, *, name: str | None = None, role: str | None = None, overview: str | None = None, scored: str | None = None, metrics: list | None = None) -> dict:
    """A size's goals changed in `s1.sizes` (Justin decides them; DECISIONS.md records each change): what it is for,
    how it is judged and the metrics that judge it ([[name, what it measures, "live" | "to come"], ...]). Returns
    the row as it now stands."""
    _at_home("a size's goals are changed at home")
    with session() as s:
        row = s.get(Size, preset)
        if row is None:
            raise KeyError(f"no size {preset!r}")
        if name is not None:  # the size's name gives its page's address (server.py CLASS_RENAMES keeps the old ones)
            row.name = name
        if role is not None:
            row.role = role
        if overview is not None:
            row.overview = overview
        if scored is not None:
            row.scored = scored
        if metrics is not None:
            row.metrics = metrics
        s.commit()
    reload()
    return next(r for r in sizes() if r["preset"] == preset)


@functools.cache
def _harbours() -> tuple[dict, ...]:
    from thorp import store

    if store.papers():
        return tuple(dict(r) for r in store.read_papers().get("harbours") or ())
    with session() as s:
        rows = s.scalars(select(Harbour).order_by(Harbour.ordinal)).all()
        return tuple(
            {
                "key": h.key,
                "ordinal": h.ordinal,
                "name": h.name,
                "aka": h.aka,
                "lane": h.lane,
                "where": h.location,
                "about": h.about,
                "depth": h.depth,
                "ship_builder": h.ship_builder,
                "foreign": bool(h.foreign_only),
            }
            for h in rows
        )


def harbours() -> list[dict]:
    """Every harbour, shallowest first, as the dashboard and `waters.harbour_for` read it. `foreign` is
    always present: a store's papers row from before the flag is ours, not a foreign harbour."""
    return [{**dict(h), "foreign": bool(h.get("foreign"))} for h in _harbours()]


def harbour(key: str) -> dict | None:
    h = next((dict(h) for h in _harbours() if h["key"] == key), None)
    return {**h, "foreign": bool(h.get("foreign"))} if h else None


def journeys() -> list[dict]:
    """Every journey as its nested plan: `pretraining` (outbound) and `posttraining` (the return)."""
    with session() as s:
        return [_journey_payload(j) for j in s.scalars(select(Journey).order_by(Journey.created_at))]


def journey(key: str) -> dict | None:
    with session() as s:
        j = s.get(Journey, key)
        return _journey_payload(j) if j else None


def _journey_payload(j: Journey) -> dict:
    legs = {"pretraining": {"leg": "outbound", "stage": []}, "posttraining": {"leg": "return", "stage": []}}
    for st in sorted(j.stages, key=lambda x: (x.phase, x.ordinal)):
        legs.setdefault(st.phase, {"leg": st.phase, "stage": []})["stage"].append(
            {
                "ordinal": st.ordinal,
                "name": st.name,
                "purpose": st.purpose,
                "library": st.library,
                "tokens": st.tokens,
                "passes": st.passes,
                "lr": st.lr,
                "compose": st.compose,
                "cards": st.cards or [],
            }
        )
    return {
        "key": j.key,
        "name": j.name,
        "ship_key": j.ship_key,
        "harbour_key": j.harbour_key,
        "aim": j.aim,
        "status": j.status,
        "signed_by": j.signed_by,
        "signed_at": j.signed_at.isoformat() if j.signed_at else None,
        "manifest_sha1": j.manifest_sha1,
        **legs,
    }


def card_snapshot(levels: tuple[int, ...] = (0,)) -> list[dict]:
    """The cards at these levels, with their characteristics: the basic cards (level 0) are always put in;
    stage 1 (comparator, Nevermore) is a bigger model's choice."""
    from thorp import fleet

    return [
        {
            "key": s.key,
            "name": s.name,
            "level": s.level,
            "kind": "star",
            "metric": s.metric,
            "shared_metric": s.shared_metric,
            "evaluator": s.evaluator,
            "threshold": s.threshold,
            "about": s.about,
        }
        for s in fleet.STARS.values()
        if s.level in levels
    ]


def set_stage_cards(
    journey_key: str, phase: str, ordinal: int, levels: tuple[int, ...] = (0,)
) -> list[dict]:
    """Set a stage's cards by level (0 basic, 1 stage 1, ...), snapshotted with their characteristics."""
    from thorp.viable.s3_control.models import JourneyStage

    cards = card_snapshot(levels)
    with session() as s, s.begin():
        st = s.get(JourneyStage, (journey_key, phase, ordinal))
        if st is None:
            raise KeyError(f"no stage {journey_key}/{phase}/{ordinal}")
        st.cards = cards
    return cards


def sign_journey(key: str, signed_by: str, manifest_sha1: str | None = None) -> dict:
    """The ship_builder's sign-off on a journey's supplies (the manifest's hash, once it is built)."""
    from datetime import datetime

    with session() as s, s.begin():
        j = s.get(Journey, key)
        if j is None:
            raise KeyError(f"no journey {key!r}")
        j.signed_by, j.signed_at, j.manifest_sha1 = signed_by, datetime.now().astimezone(), manifest_sha1
    return journey(key) or {}


def ships() -> list[ShipRecord]:
    with session() as s:
        return list(s.scalars(select(ShipRecord).order_by(ShipRecord.created_at, ShipRecord.key)))


def get_ship(key: str) -> ShipRecord | None:
    with session() as s:
        return s.get(ShipRecord, key)


def add_ship(rec: dict) -> ShipRecord:
    """Register a ship once; a ship already registered under the key is kept as it is (names never move)."""
    _at_home("a ship or a voyage is registered at home, when the voyage docks")
    with session() as s, s.begin():
        s.execute(insert(ShipRecord).values(**rec).on_conflict_do_nothing(index_elements=["key"]))
    return get_ship(rec["key"])


def retire(keys: list[str], note: str, *, back: bool = False) -> int:
    """Retire ships (status "retired", with the reason), or with back=True return them to service. Nothing is
    deleted: the ships, their voyages and the ledger stay, and the dashboard shows retired ships on request."""
    _at_home("ships are retired at home")
    with session() as s, s.begin():
        rows = list(s.scalars(select(ShipRecord).where(ShipRecord.key.in_(keys))))
        for r in rows:
            r.status, r.retired_note = ("in service", None) if back else ("retired", note)
    return len(rows)


def add_voyage(run_id: str, ship_key: str, name: str, seed: int | None, started: str | None) -> None:
    """A run joins its ship's voyages (once; a later call fills a start time it lacked)."""
    _at_home("a ship or a voyage is registered at home, when the voyage docks")
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
