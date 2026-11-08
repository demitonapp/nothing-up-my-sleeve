"""The crowns deck's rules (backend/scripts/make_crowns_deck.py): only both premises answer, copying and recency
cannot decide, the flip turns the answer, and the readings beyond the gain (thorp.evaluators.logic)."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from make_crowns_deck import HEDGE, KINDS, build  # noqa: E402

from thorp.evaluators.logic import crowns_readings  # noqa: E402

VARIANTS = {"both", "first", "second", "swapped", "padded", "one_hop", "flip", "ask_disputed", "ask_settled"}


@pytest.fixture(scope="module")
def items() -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for r in build():
        out.setdefault(r["item"], {})[r["variant"]] = r
    return out


def test_forty_items_ten_a_kind_every_variant(items):
    assert len(items) == 40
    assert Counter(v["both"]["relation"] for v in items.values()) == {f"crowns-{k}": 10 for k in KINDS}
    assert all(set(v) == VARIANTS for v in items.values())


def test_only_both_premises_answer(items):
    for v in items.values():
        both, first, second = v["both"], v["first"], v["second"]
        asker = both["frame"].split()[2].rstrip(",")
        assert both["idea"] in both["pre"] and both["rival"] in both["pre"]  # copying cannot decide
        assert both["idea"] in first["pre"] and asker not in first["pre"]  # the record, no standpoint
        assert both["idea"] not in second["pre"] and both["rival"] not in second["pre"]  # the standpoint alone
        assert both["bridge"] in both["pre"] and both["distractor"] in v["padded"]["pre"].split(". ")[-1]


def test_recency_cannot_decide(items):
    for kind in KINDS:
        last = [
            v["both"]["pre"].rfind(v["both"]["idea"]) > v["both"]["pre"].rfind(v["both"]["rival"])
            for v in items.values()
            if v["both"]["relation"] == f"crowns-{kind}"
        ]
        assert sum(last) == len(last) // 2  # half the items name the answer's claim last


def test_the_flip_turns_the_answer(items):
    for v in items.values():
        assert (v["flip"]["idea"], v["flip"]["rival"]) == (v["both"]["rival"], v["both"]["idea"])
        assert v["flip"]["frame"] == v["both"]["frame"] and v["flip"]["pre"] != v["both"]["pre"]


def test_ask_back_has_the_same_names_to_copy(items):
    for v in items.values():
        d, s = v["ask_disputed"], v["ask_settled"]
        assert d["idea"] == s["idea"] == HEDGE and d["frame"] == s["frame"]
        for name in (v["both"]["idea"], v["both"]["rival"]):
            assert name in d["pre"] and name in s["pre"]


def test_the_deck_on_disk_is_the_generator_s():
    import csv

    from thorp import paths

    p = paths.resolve("lists/tricks/crowns.csv")
    with p.open(encoding="utf-8") as f:
        disk = list(csv.DictReader(f))
    assert [(r["item"], r["variant"], r["prompt"]) for r in disk] == [
        (r["item"], r["variant"], f"{r['pre']} {r['frame']}") for r in build()
    ]


def test_moves_and_ask():
    p = "tricks/crowns_test/"
    m = {p + "lift": 0.3, p + "lift_flip": -0.2, p + "lift_ask_disputed": 0.1, p + "lift_ask_settled": -0.05}
    out = crowns_readings(m)
    assert out[p + "moves"] == -0.2  # the answer did not turn with the standpoint
    assert out[p + "ask"] == pytest.approx(0.15)
    assert crowns_readings({"tricks/logic_test/lift": 0.3}) == {}
