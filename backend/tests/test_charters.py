"""A size's charter, findings and benchmarks (14 November): the rows the migration seeds, read as the Charters tab reads them.

Every size gets the three (Justin: "Those are the three every ship size gets"): a base, experiment arms that each prove
rows of the master charter, and rigged arms that carry their label and are read on their own test."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from thorp import charters, store


def test_the_300k_is_a_base_three_experiment_arms_and_four_rigged():
    vs = charters.read("300k")["charters"][0]["variants"]
    kinds = [v["kind"] for v in vs]
    assert kinds.count("base") == 1 and kinds.count("experiment") == 3 and kinds.count("rigged") == 4
    for v in vs:
        assert v["settings"] and all({"name", "value"} <= set(s) for s in v["settings"])
        # the state is read, never stored: an unsailed spec is laid, an arm without one is designed
        assert v["state"] == ("designed" if not v["spec"] else "laid")
        if v["rigged"]:
            assert "RIGGED" in (v["label"] or "") and v["metric"] == "ifeval/prompt_strict"


@pytest.mark.parametrize("size", ["300k", "1m", "9m", "21m", "50m"])
def test_every_size_gets_the_three(size):
    from thorp import launch

    d = charters.read(size)
    assert len(d["charters"]) == 1
    vs = d["charters"][0]["variants"]
    assert {v["kind"] for v in vs} == {"base", "experiment", "rigged"}
    base = [v for v in vs if v["kind"] == "base"]
    assert len(base) == 1 and base[0]["role"] == "control" and base[0]["spec"]
    for v in vs:
        assert v["rigged"] == (v["kind"] == "rigged")
        # an experiment proves rows of the master charter, by their keys
        assert bool(v["proves"]) == (v["kind"] == "experiment") and set(v["proves"]) <= set(launch.PARAMS)
    assert {b["key"] for b in d["benchmarks"]} == {"tomes", "arc_easy", "arc_challenge", "chaining", "ifeval"}


def test_findings_name_their_voyages_and_benchmarks_their_bars():
    d = charters.read("300k")
    assert {f["status"] for f in d["findings"]} <= {"measured", "not measured", "open"}
    shape = next(f for f in d["findings"] if f["key"] == "shape")
    assert shape["status"] == "open" and len(shape["readings"]) == len(shape["runs"])
    ifeval = next(b for b in d["benchmarks"] if b["key"] == "ifeval")
    assert ifeval["bar_model"] == "Falcon-H1-Tiny-90M" and ifeval["read_by"] == 0


def test_an_arm_is_what_its_kind_says():
    for cols in (
        "false, 'rigged', '{}'",  # rigged kind, not rigged
        "false, 'experiment', '{}'",  # an experiment that proves nothing
        "false, 'base', '{ship.layers}'",  # an arm called the base
    ):
        with pytest.raises(IntegrityError), store.session() as s:
            s.execute(text(f"insert into s1.charter_variants (charter, key, ordinal, name, rigged, kind, proves) values ('300k', 'x', 99, 'x', {cols})"))


@pytest.mark.parametrize(
    "cols",
    [
        "true, null, 'ifeval/prompt_strict', 'higher', 'arm'",  # rigged without its label
        "true, 'RIGGED', null, null, 'arm'",  # rigged without its own reading
        "true, 'RIGGED', 'm', 'higher', 'control'",  # the control rigged
    ],
)
def test_a_rigged_variant_must_say_so_and_carry_its_own_reading(cols):
    with pytest.raises(IntegrityError), store.session() as s:
        s.execute(
            text(
                "insert into s1.charter_variants (charter, key, ordinal, name, rigged, label, metric, better, role, kind) "
                f"values ('300k', 'x', 99, 'x', {cols}, 'rigged')"
            )
        )
