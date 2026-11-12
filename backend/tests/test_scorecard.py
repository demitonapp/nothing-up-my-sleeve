"""The size page's scorecard (thorp/dash/server.py SCORECARD, 13 November): every point names the discovery its mark
leans on as a discovery on the field's map (lib/fieldMap.ts), so the page's "the field" link opens a card, and every
mark the deck or a test owns is read from there, never typed twice."""

from __future__ import annotations

import re
from pathlib import Path

from thorp import fleet
from thorp.dash.server import SCORECARD
from thorp.viable.s5_policy.deck import BY_KEY

FIELD_MAP = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "fieldMap.ts").read_text()


def test_every_point_is_named_once():
    keys = [p["key"] for p in SCORECARD]
    assert len(keys) == len(set(keys))


def test_every_source_is_a_discovery_on_the_map():
    on_the_map = set(re.findall(r"\{ key: '([a-z0-9-]+)', title:", FIELD_MAP))
    named = {p["source"] for p in SCORECARD if p["source"]}
    assert named <= on_the_map, f"not on the map: {named - on_the_map}"


def test_marks_owned_elsewhere_name_a_card_or_a_test_that_exists():
    for p in SCORECARD:
        m = p["mark"]
        if isinstance(m, tuple) and m[0] == "card":
            assert BY_KEY[m[1]].ability, f"{p['key']}: card {m[1]} has no ability mark"
        elif isinstance(m, tuple) and m[0] == "trick":
            assert fleet.TRICKS[m[1]].threshold, f"{p['key']}: test {m[1]} has no threshold"
        else:
            assert m is None or m == "class_below" or isinstance(m, float), p["key"]
        assert p["kind"] in ("ratio", "lower", "chance")
        assert p["kind"] != "chance" or p.get("chance") is not None
