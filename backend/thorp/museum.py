"""Sleeper Service, the museum Orbital: UNESCO's Memory of the World register hung as a museum (13 November, Justin:
"This UNESCO's Memory of the World register deserves it's own Orbital", "it's a museum orbital and must reflect
that", "Yes, build it").

The wings, the lenders and the exhibits are rows in `s4.museum_wings`, `s4.museum_lenders` and
`s4.museum_exhibits` (thorp/viable/s3_control/models.py, made and seeded by Alembic). This module reads them and
hangs the exhibits: an exhibit's era wing follows from its first year, its country wings from the countries that
nominated it, and its theme wings (the exhibitions) from its own list. The era wing past the cutoff is sealed.

    uv run python -m thorp.museum          # the floor plan, in plain text
    uv run python -m thorp.museum keys     # write frontend/src/data/museum.json, the pre-rendered addresses
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

from sqlalchemy import select

from thorp import paths
from thorp.viable.s3_control.fitout_store import session
from thorp.viable.s3_control.models import MuseumExhibitRecord, MuseumLenderRecord, MuseumWingRecord

NAME = "Sleeper Service"  # the Orbital's name; the address is /orbitals/sleeper-service
# Named for the Sleeper Service, the General Systems Vehicle of Banks' Excession that turned its vast spaces into
# tableaux, scenes of the past held perfectly still (13 November, Justin chose it from four Culture-inspired names).
SOURCE = "UNESCO Memory of the World"

_WING = ("key", "ordinal", "kind", "name", "blurb", "description", "year_from", "year_to", "sealed", "country")
_LENDER = ("key", "ordinal", "name", "city", "country", "country_name", "kind", "site", "about")
_EXHIBIT = ("key", "ordinal", "title", "register", "inscribed", "year_from", "year_to", "dates", "medium", "languages",
            "countries", "lenders", "themes", "label", "significance", "conservation", "access", "note", "sources")


def _rows(model, fields: tuple[str, ...]) -> tuple[dict, ...]:
    with session() as s:
        rows = s.scalars(select(model).order_by(model.ordinal)).all()
        return tuple({f: getattr(r, f) for f in fields} for r in rows)


@functools.cache
def _all() -> tuple[tuple[dict, ...], tuple[dict, ...], tuple[dict, ...]]:
    return _rows(MuseumWingRecord, _WING), _rows(MuseumLenderRecord, _LENDER), _rows(MuseumExhibitRecord, _EXHIBIT)


def reload() -> None:
    _all.cache_clear()


def era_of(year: int, wings: list[dict]) -> dict | None:
    """The era wing an exhibit hangs in, by the documents' first year."""
    for w in wings:
        if w["kind"] != "era":
            continue
        lo = w["year_from"] if w["year_from"] is not None else -10**6
        hi = w["year_to"] if w["year_to"] is not None else 10**6
        if lo <= year <= hi:
            return w
    return None


def wings_of(exhibit: dict, wings: list[dict]) -> list[str]:
    """Every wing an exhibit hangs in: its era, the country wings of the countries that nominated it, its themes."""
    keys = []
    era = era_of(exhibit["year_from"], wings)
    if era:
        keys.append(era["key"])
    keys += [w["key"] for w in wings if w["kind"] == "country" and w["country"] in (exhibit["countries"] or [])]
    keys += [k for k in (exhibit["themes"] or []) if any(w["key"] == k and w["kind"] == "theme" for w in wings)]
    return keys


def museum() -> dict:
    """The whole museum for the page: the wings in order, each with its exhibits' keys, the exhibits with their era,
    sealed flag and wings, and the lenders with what each lends."""
    wings = [dict(w) for w in _all()[0]]
    lenders = [dict(x) for x in _all()[1]]
    exhibits = [dict(e) for e in _all()[2]]
    threshold = next((w["year_from"] for w in wings if w["sealed"]), None)
    for e in exhibits:
        e["wings"] = wings_of(e, wings)
        era = era_of(e["year_from"], wings)
        e["era"] = era["key"] if era else None
        e["sealed"] = bool(era and era["sealed"])
    for w in wings:
        w["exhibits"] = [e["key"] for e in exhibits if w["key"] in e["wings"]]
    for x in lenders:
        x["exhibits"] = [e["key"] for e in exhibits if x["key"] in (e["lenders"] or [])]
    return {
        "name": NAME,
        "source": SOURCE,
        "threshold": threshold,
        "wings": wings,
        "exhibits": exhibits,
        "lenders": lenders,
        "counts": {"exhibits": len(exhibits), "lenders": len(lenders),
                   "registers": sorted({e["register"] for e in exhibits})},
    }


def write_keys() -> Path:
    """The addresses a static build pre-renders, and the names the breadcrumbs print, as frontend/src/data/museum.json."""
    m = museum()
    out = paths.FRONTEND / "src" / "data" / "museum.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "wings": {w["key"]: w["name"] for w in m["wings"]},
        "exhibits": {e["key"]: e["title"] for e in m["exhibits"]},
        "lenders": {x["key"]: x["name"] for x in m["lenders"]},
    }
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    return out


def main(argv: list[str]) -> int:
    if argv[:1] == ["keys"]:
        print(write_keys())
        return 0
    m = museum()
    print(f"{m['name']}: {m['counts']['exhibits']} exhibits, {m['counts']['lenders']} lenders; sealed from {m['threshold']}")
    for w in m["wings"]:
        print(f"  {w['name']} ({w['kind']}{', sealed' if w['sealed'] else ''}): {len(w['exhibits'])}")
        for k in w["exhibits"]:
            print(f"      {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
