"""Every trick of the trade and every discovery chain has a pre-rendered page: the frontend's key list
(frontend/src/data/tricks.json) is the registries' own (13 November: the hand-typed list had 30 of 65 tricks)."""

from __future__ import annotations

import json

from thorp.dash import trick_keys


def test_the_frontends_trick_list_is_the_registrys():
    on_disk = json.loads(trick_keys.target().read_text())
    assert on_disk == trick_keys.keys(), "frontend/src/data/tricks.json is stale: run `python -m thorp.dash.trick_keys`"


def test_every_key_is_unique_and_a_plain_address_segment():
    k = trick_keys.keys()
    for name in ("tricks", "chains"):
        assert len(k[name]) == len(set(k[name])), f"a {name} key is repeated"
        assert all(x and x.replace("_", "").isalnum() for x in k[name]), f"a {name} key is not a plain segment"


def test_every_trick_is_described_and_on_a_known_waypoint():
    k = trick_keys.keys()
    assert [d["key"] for d in k["detail"]] == k["tricks"]
    steps = {w["key"] for w in k["waypoints"]}
    assert all(d["name"] and d["does"] and d["waypoint"] in steps for d in k["detail"])
