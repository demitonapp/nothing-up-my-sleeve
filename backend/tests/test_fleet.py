"""The fleet registry is consistent: every reference resolves, every lever has sane limits."""

from thorp import fleet
from thorp.evaluators import nevermore


def test_stars_rest_on_known_lower_stars():
    for s in fleet.STARS.values():
        assert (
            s.threshold > 0
        )  # most are shares (0 to 1); the delimiter is a ratio (1 = indifferent)
        for r in s.rests_on:
            assert r in fleet.STARS and fleet.STARS[r].level < s.level


def test_ships_and_loops_point_at_real_things():
    for lp in fleet.EXPEDITIONS.values():
        assert all(st in fleet.STARS for st in lp.stars)
        assert lp.stop.max_runs > 0 and lp.outcomes
        for lv in lp.levers:
            if lv.low is not None:
                assert lv.low <= lv.high


def test_one_threshold_for_the_nevermore():
    assert nevermore.THRESHOLD == fleet.STARS["nevermore"].threshold


def test_fleet_of_labels():
    assert fleet.fleet_of("Endeavour") == "First Fleet"
    assert fleet.fleet_of("Loop 12") == "First Fleet"
    assert fleet.fleet_of("Nevermore") is None  # a star, not a ship
    assert fleet.fleet_of("First Light: baseline (seed 1)") == "Star Fleet"
    assert fleet.fleet_of("nobody") is None


def test_sieves_name_ledger_metrics():
    assert {s.metric_prefix for s in fleet.SIEVES.values()} == {
        "grad_norm/",
        "update_ratio/",
        "heading/",
    }
    assert fleet.KINK_MIN_RECORDS > 0 and 0 < fleet.KINK_FIRM < 1


def test_a_ship_is_a_size_and_a_fitout(tmp_thorp):
    base = {
        "name": "a",
        "ship": "Argo",
        "seed": 1,
        "data": {"recipe": "x.csv", "passes": 4, "order": "shuffled", "refuse": ["h.csv"]},
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": 4096,
            "byte_fallback": True,
            "train_on": "recipe",
        },
        "model": {"family": "gpt", "preset": "1m", "context": 1024},
        "optim": {"lr": 0.002},
        "eval": {"evaluators": ["ce_bpb"]},
    }
    seed2 = {
        **base,
        "name": "b",
        "ship": "Argo II",
        "seed": 2,
        "eval": {"evaluators": ["ce_bpb", "nevermore"]},
    }
    other = {**base, "optim": {"lr": 0.004}}
    bigger = {**base, "model": {**base["model"], "preset": "9m"}}
    assert fleet.ship_key(base) == fleet.ship_key(
        seed2
    )  # a seed and an instrument do not make a new ship
    assert fleet.ship_key(base) != fleet.ship_key(other)  # a different fitout does
    assert fleet.ship_key(base) != fleet.ship_key(bigger)  # and so does a different size
    first = fleet.ship_for(base)
    assert first.name == "Argo" and first.size == "1m" and first.preset == "1m"
    assert fleet.ship_for(seed2).name == "Argo"  # the second sailing joins the first
    renamed = fleet.ship_for({**base, "ship": "Something Else"})
    assert renamed.name == "Argo"  # names never move
    assert (
        fleet.ship_for(other).name == "Argo (2)"
    )  # a new fitout under an old label gets its own name
    assert fleet.clean_name("Smaller Pieces, Rolled Again") == "Smaller Pieces"
    assert fleet.clean_name("First Light: baseline (seed 2)") == "First Light: baseline"


def test_tricks_name_their_stars():
    for t in fleet.TRICKS.values():
        assert t.threshold > 0
        assert all(s in fleet.STARS for s in t.performed_by)


def test_a_ships_key_never_moves():
    # a fixed spec's key, pinned: if this changes, every registered ship has lost its name
    spec = {
        "data": {"recipe": "nowhere.csv", "passes": 2, "order": "shuffled"},
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": 4096,
            "byte_fallback": True,
            "train_on": "recipe",
        },
        "model": {"family": "gpt", "preset": "1m", "context": 1024},
        "optim": {"lr": 0.002},
    }
    assert fleet.ship_key(spec) == "1m:" + fleet.fitout_id(spec)
    assert fleet.fitout_id(spec) == "6a7c81886c7b"


def test_a_pairs_test_needs_its_share_as_well_as_its_lift():
    from thorp import fleet

    t = fleet.TRICKS["breeders_test"]
    assert t.min_score == fleet.MIN_SHARE
    assert fleet.performed("breeders_test", {t.metric: 0.3, "tricks/breeders_test/score": 0.7})
    assert not fleet.performed("breeders_test", {t.metric: 0.3, "tricks/breeders_test/score": 0.5})
    assert not fleet.performed("breeders_test", {t.metric: 0.05, "tricks/breeders_test/score": 0.9})
    assert fleet.TRICKS["successor"].min_score is None


def test_every_chain_has_a_rung_per_class():
    from thorp import fleet

    cs = fleet.chains()
    assert len(cs) == 4
    for c in cs:
        assert [fleet.TRICKS[k].goal_class for k in c] == [r.goal_class for r in fleet.RUNGS]


def test_every_chain_is_told_step_by_step():
    from thorp import fleet

    for c in fleet.chains():
        told = fleet.CHAINS[c[-1]]
        assert list(told.steps) == c


def test_the_climb_counts_rungs_from_the_bottom_and_the_next_rungs_progress():
    from thorp import fleet, leaderboard

    first = [c[0] for c in fleet.chains()]
    lift = {k: 1.0 for k in first} | {c[1]: 0.05 for c in fleet.chains()}
    score = {k: 1.0 for k in first} | {c[1]: 0.9 for c in fleet.chains()}
    r = leaderboard.climb(lift, score)
    assert r["climb"] == 1.5  # one rung each, the next half way to its threshold
    gap = dict(lift) | {
        c[2]: 1.0 for c in fleet.chains()
    }  # a higher rung lit above a gap is not counted
    assert leaderboard.climb(gap, score | {c[2]: 1.0 for c in fleet.chains()})["climb"] == 1.5
    assert r["chaining_lift"] is None


def test_the_stores_rule_admits_only_the_stores_or_an_opt_in(monkeypatch):
    import pytest

    from thorp import stores

    monkeypatch.setattr(stores, "enforced", lambda: True)
    monkeypatch.setattr(
        stores, "stores", lambda: {"prose": {"path": "lists/stars-fiction.csv", "sha1": "x"}}
    )
    import hashlib

    from thorp import paths

    sha = hashlib.sha1(paths.resolve("lists/stars-fiction.csv").read_bytes()).hexdigest()
    monkeypatch.setattr(
        stores, "stores", lambda: {"prose": {"path": "lists/stars-fiction.csv", "sha1": sha}}
    )
    ok = {"name": "a", "data": {"recipe": "lists/stars-fiction.csv"}}
    assert stores.check(ok) == ""
    bad = {"name": "b", "data": {"recipe": "lists/stars-verse.csv"}}
    with pytest.raises(stores.StoresRuleError):
        stores.check(bad)
    opted = {
        "name": "c",
        "data": {"recipe": "lists/stars-verse.csv", "opt_in": "the verse comparison"},
    }
    assert stores.check(opted) == "the verse comparison"
    assert stores.check(bad, known_run=True) == ""  # a run already in the ledger continues
