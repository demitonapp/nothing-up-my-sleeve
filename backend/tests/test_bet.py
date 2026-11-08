"""The $100 bet (thorp/bet.py): its ladder follows the registry, the $100 buys what the pass rule asks for, and
the quantum test meets the discovery tests' rule."""

from thorp import bet
from thorp.models.registry import LADDER


def test_the_bets_ladder_is_the_registrys_ladder():
    d = bet.payload()
    assert [r["preset"] for r in d["ladder"]] == [r["preset"] for r in LADDER]
    assert [c["preset"] for c in d["quantum"]["chain"]] == [r["preset"] for r in LADDER]


def test_a_hundred_dollars_buys_two_seeds_and_an_ablation():
    b = bet.budget()
    assert b["fits"] and b["total"]["mid"] <= bet.BUDGET
    assert 5 < b["run_hours"]["mid"] < 15  # one trader run at twenty tokens a parameter, on one H100
    assert b["runs_for_budget"]["mid"] >= 3
    assert b["runs_for_budget"]["high"] < b["runs_for_budget"]["mid"] < b["runs_for_budget"]["low"]


def test_the_quantum_bet_meets_the_discovery_rule():
    q = bet.QUANTUM
    years = [f["year"] for f in q["found_by"]]
    assert len(years) >= 2  # found independently by more than one person
    assert min(years) >= q["cutoff"] and max(years) - min(years) <= 5  # within a few years of the cutoff
    assert q["rivals"] and q["ablation"] and q["precursors"]
