"""A leg reads with its seed's pieces (11 November 2026, the return leg).

A tokeniser's id carries its cleaning, so a leg that cleans its text another way than its seed did would
train a second tokeniser, and the merges learned from differently cleaned text need not land on the same
ids. On Ogden v0.1.4 four of 2,048 had changed hands (`▁On` with `▁fine`) and nothing refused it."""

import copy

import pytest

from thorp import ledger, train
from thorp import tokeniser as tokmod

quiet = lambda *a: None  # noqa: E731


@pytest.fixture(autouse=True)
def _sqlite_ledger(monkeypatch):
    """The seed is found by name through train's reader: the test's own ledger, not Postgres (as test_growth)."""
    monkeypatch.setenv("THORP_LEDGER_PG", "0")


def _seedling(library, spec):
    seed_spec = copy.deepcopy(spec)
    seed_spec["name"] = "seedling"
    prep = train.prepare(seed_spec, resolver=library["resolver"], log=quiet)
    rec = ledger.Ledger()
    train.train(seed_spec, prep, rec=rec, log=quiet)
    return prep, rec


def test_a_leg_that_cleans_differently_reads_with_its_seeds_pieces(library, spec):
    seed_prep, rec = _seedling(library, spec)
    leg = copy.deepcopy(spec)
    leg["name"] = "leg"
    leg["data"]["clean"] = "marks-v1"  # the seed read unwrap-v2: another cleaning, so another tokeniser id
    leg["data"]["opt_in"] = "a return leg reads its turns marked (S5 policy 'clean' asks for the words)"
    leg["seeded_from"] = {"run": "seedling", "mode": "free"}
    leg["checkpoint"] = {"every_steps": 5}
    said: list[str] = []
    prep = train.prepare(leg, resolver=library["resolver"], log=said.append)
    assert prep.tokeniser.id != seed_prep.tokeniser.id  # its own id: the shards are read through its own cleaning
    assert prep.tokeniser.clean == "marks-v1"
    assert tokmod.pieces(prep.tokeniser.id) == tokmod.pieces(seed_prep.tokeniser.id)  # and the seed's table
    assert any("the seed's pieces" in line for line in said)
    # it sails, and a resume keeps the tokeniser its checkpoint was written with
    out = train.train(leg, prep, rec=rec, stop_after=5, log=quiet)
    assert out["step"] == 5
    again = train.prepare(leg, resolver=library["resolver"], log=quiet)
    assert again.tokeniser.id == prep.tokeniser.id


def test_a_leg_with_the_seeds_own_cleaning_shares_its_tokeniser(library, spec):
    seed_prep, _ = _seedling(library, spec)
    leg = copy.deepcopy(spec)
    leg["name"] = "leg"
    leg["seeded_from"] = {"run": "seedling", "mode": "free"}
    prep = train.prepare(leg, resolver=library["resolver"], log=quiet)
    assert prep.tokeniser.id == seed_prep.tokeniser.id  # nothing to graft: unchanged from before


def test_a_seed_read_through_other_pieces_is_refused(library, spec):
    _seedling(library, spec)
    other = tokmod.train_or_load(library["recipe"][:1], {"kind": "spm-bpe", "vocab": 512, "byte_fallback": True})
    leg = copy.deepcopy(spec)
    leg["name"] = "leg"
    leg["seeded_from"] = {"run": "seedling", "mode": "free"}
    with pytest.raises(ValueError, match="pieces differ"):
        train.seeded_master(leg, leg["seeded_from"], None, 512, quiet, tokeniser_id=other.id)
