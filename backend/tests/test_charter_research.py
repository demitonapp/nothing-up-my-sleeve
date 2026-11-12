"""The field's discoveries tied to the master charter (frontend/src/lib/charterResearch.ts, 12 November): every
row it names is a row of the charter, with the page's own name for it, and every discovery it names is on the map.
The list is typed by hand in the frontend, so this is what keeps it beside thorp/launch.py and lib/fieldMap.ts."""

from __future__ import annotations

import re
from pathlib import Path

from thorp import launch

LIB = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"
RESEARCH = (LIB / "charterResearch.ts").read_text()
ROW = re.compile(r"'((?:ship|tokeniser|reads|scaffold|training|leg)\.[a-z_]+)'")


def _block(name: str) -> str:
    """The text of one exported constant, to its closing line."""
    start = RESEARCH.index(f"export const {name}")
    return RESEARCH[start:RESEARCH.index("\n];", start) if "[] = [" in RESEARCH[start:start + 200] else RESEARCH.index("\n};", start)]


def test_the_rows_are_the_charters_rows_by_the_pages_names():
    named = dict(re.findall(r"'([a-z]+\.[a-z_]+)': '([^']+)'", _block("CHARTER_ROWS")))
    assert set(named) == set(launch.PARAMS), "CHARTER_ROWS and launch.PARAMS name different rows"
    for group, _, params in launch.GROUPS:
        for p in params:
            assert named[p.key] == f"{launch.SHORT[group]}: {p.name}", p.key


def test_every_bearing_and_gap_names_a_row_of_the_charter():
    for name in ("BEARINGS", "GAPS"):
        rows = set(ROW.findall(_block(name)))
        assert rows and rows <= set(launch.PARAMS), f"{name} names a row the charter does not have: {rows - set(launch.PARAMS)}"


def test_every_discovery_named_is_on_the_map_and_named_once():
    on_the_map = set(re.findall(r"\{ key: '([a-z0-9-]+)', title:", (LIB / "fieldMap.ts").read_text()))
    bearing = re.findall(r"discovery: '([a-z0-9-]+)'", _block("BEARINGS"))
    assert len(bearing) == len(set(bearing)), "a discovery has two bearings: the card shows one"
    assert set(bearing) <= on_the_map, set(bearing) - on_the_map
    missing = {k for found in re.findall(r"discoveries: \[([^\]]*)\]", _block("MISSING_ROWS")) for k in re.findall(r"'([a-z0-9-]+)'", found)}
    assert missing and missing <= on_the_map, missing - on_the_map
