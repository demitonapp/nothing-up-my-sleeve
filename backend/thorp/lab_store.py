"""The Reach's houses in Postgres (schema `s4`, S4 intelligence: the outside makers whose models S4 reads;
the table is `s4.labs` in thorp/viable/s3_control/models.py, made and seeded by Alembic).

Nothing here is a list in code: a house is a row, its profile, its funding and its rounds beside it
(12 November, Justin: "labs should be in postgres not hardcoded"). `thorp/labs.py` is the shape the
dashboard, the leaderboard and the chat read; this module is the row underneath it.
"""

from __future__ import annotations

import functools

from sqlalchemy import select

from thorp.viable.s3_control.fitout_store import session
from thorp.viable.s3_control.models import LabRecord


@functools.cache
def _labs() -> tuple[dict, ...]:
    with session() as s:
        rows = s.scalars(select(LabRecord).order_by(LabRecord.ordinal)).all()
        return tuple(
            {
                "key": r.key,
                "ordinal": r.ordinal,
                "listed": bool(r.listed),
                "category": r.category,
                "kind": r.kind,
                "name": r.name,
                "short": r.short or r.name,
                "families": tuple(r.families or ()),
                "orgs": tuple(r.orgs or ()),
                "url": r.url,
                "site": r.site,
                "country": r.country,
                "country_name": r.country_name,
                "hq": r.hq,
                "founded": r.founded,
                "blurb": r.blurb,
                "description": r.description,
                "purpose": r.purpose,
                "flagship": tuple(r.flagship or ()),
                "focus": r.focus,
                "open_weights": bool(r.open_weights),
                "funding": dict(r.funding or {}),
                "gov": dict(r.gov) if r.gov else None,
            }
            for r in rows
        )


def labs() -> list[dict]:
    """Every house, in the order the Labs page shows them (listed ones first by ordinal, then the
    leaderboard-only ones). Cached for the process; `reload()` after a change."""
    return [dict(r) for r in _labs()]


def get(key: str) -> dict | None:
    return next((dict(r) for r in _labs() if r["key"] == key.lower()), None)


def reload() -> None:
    _labs.cache_clear()


def set_lab(key: str, **fields) -> dict:
    """A house's facts changed in `s4.labs`: its profile, its focus, its funding or its order. Only the
    fields named are written. Returns the row as it now stands (Justin decides the facts; DECISIONS.md
    records each change)."""
    known = {
        "ordinal", "listed", "category", "kind", "name", "short", "families", "orgs", "url", "site", "country", "country_name",
        "hq", "founded", "blurb", "description", "purpose", "flagship", "focus", "open_weights",
        "funding", "gov",
    }
    unknown = set(fields) - known
    if unknown:
        raise KeyError(f"no such lab field: {sorted(unknown)}")
    with session() as s:
        row = s.get(LabRecord, key)
        if row is None:
            raise KeyError(f"no lab {key!r}")
        for k, v in fields.items():
            setattr(row, k, v)
        s.commit()
    reload()
    return get(key) or {}
