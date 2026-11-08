"""The viable system's S3 gate and S2 lints (thorp/vsm.py)."""

import pytest

from thorp import paths, vsm


def _spec(recipe, refuse=(), opt_in=""):
    return {
        "name": "t",
        "ship": "Two facts: test",
        "fitout": {"key": "keel-cards-cause", "variation": "t"},
        "data": {"recipe": recipe, "refuse": list(refuse), "opt_in": opt_in, "clean": "unwrap-v2"},
    }


def test_no_voyage_sails_without_a_named_fitout():
    """S5 'fitout' (Justin, 18:10): named in the spec, an existing fitout, a label that moves no run id."""
    from thorp import fleet, train

    s = _spec("lists/none.csv")
    assert vsm._named_fitout(s) == []
    assert vsm._named_fitout({**s, "fitout": {"key": "no-such-fitout"}})
    bare = {k: v for k, v in s.items() if k != "fitout"}
    assert vsm._named_fitout(bare)
    assert train.run_id(bare) == train.run_id(s)
    assert fleet.assign_fitout({"name": "kb-x-s2", "model": {"preset": "300k"}}) == {
        "key": "keel-cards-cause",
        "variation": "kb-x",
    }
    assert fleet.assign_fitout({"name": "spell-y-v1-seed2", "model": {"preset": "9m"}})["key"] == (
        "pilot-cards-cause"
    )
    assert fleet.assign_fitout(
        {"name": "fo-keel-cards-cause~heads-pre-s1", "experiment": "Fitout keel-cards-cause: aim"}
    ) == {"key": "keel-cards-cause", "variation": "heads"}


def test_five_systems_and_every_policy_has_an_owner():
    assert list(vsm.SYSTEMS) == ["S1", "S2", "S3", "S4", "S5"]
    assert all("Justin" in p.adopted for p in vsm.POLICIES.values())


def test_gate_refuses_a_held_out_book(tmp_path, monkeypatch):
    lst = tmp_path / "r.csv"
    import csv

    with open(paths.resolve("lists/hole-cards.csv")) as f:
        title = next(csv.DictReader(f))["title"]
    lst.write_text(f"title,author,language,family,text\n{title},x,en,,local:pg1\n")
    with pytest.raises(vsm.GateRefused, match="decks"):
        vsm.gate(_spec(str(lst)))
    all3 = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]
    assert not vsm._decks_refused(_spec(str(lst), refuse=all3))


@pytest.fixture
def frozen_stores():
    """The ship's two stores frozen in the test database (s1.stores), as make_stores.py freezes the real ones."""
    import hashlib

    from thorp import stores

    stores.freeze({k: {"path": f"lists/stores/{k}.csv", "books": 1, "tokens": 1,
                       "sha1": hashlib.sha1(paths.resolve(f"lists/stores/{k}.csv").read_bytes()).hexdigest()}
                   for k in ("prose", "trigram")})  # fmt: skip


def test_gate_admits_known_runs_and_opt_ins(monkeypatch, frozen_stores):
    monkeypatch.setattr(vsm, "_enforcement", lambda: {"stores": True})
    s = _spec(
        "lists/pool-200.csv",
        refuse=["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"],
    )
    with pytest.raises(vsm.GateRefused, match="stores"):
        vsm.gate(s)
    assert vsm.gate(s, known_run=True) == []
    s["data"]["opt_in"] = "a test of the bargain"
    assert any("opted out" in n for n in vsm.gate(s))


def test_written_exception_and_lists_drawn_from_the_stores(tmp_path, monkeypatch, frozen_stores):
    from thorp import stores

    monkeypatch.setattr(vsm, "_enforcement", lambda: {"stores": True})
    all3 = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]
    s = _spec("lists/pool-200.csv", refuse=all3)
    monkeypatch.setattr(
        vsm, "_exceptions", lambda: {"stores": {"reason": "queued before", "runs": ["t"]}}
    )
    assert any("does not govern" in n for n in vsm.gate(s))
    monkeypatch.setattr(vsm, "_exceptions", lambda: {})
    part = tmp_path / "part.csv"
    rows = open(paths.resolve("lists/stores/trigram.csv")).read().splitlines()[:6]
    part.write_text("\n".join(rows) + "\n")
    assert stores.drawn_from_stores(str(part))
    vsm.gate(_spec(str(part), refuse=all3))


def test_new_names_and_their_aliases():
    from thorp import expeditions, fleet, library, shelves, voyages

    assert fleet.VOYAGES is fleet.EXPEDITIONS and fleet.Voyage is fleet.Expedition
    assert shelves is library and voyages is expeditions
    assert {"expedition", "voyage", "library"} <= set(fleet.TERMS)


def test_overview_and_the_library_carried():
    from thorp import expeditions, library

    o = expeditions.overview()
    assert {"at_sea", "queue", "expeditions"} <= set(o)
    lib = library.carried({"data": {"recipe": "lists/stores/prose.csv"}})
    assert lib[0]["where"] == "the prose stores" and lib[0]["books"] > 0


def test_one_voyage_at_sea(tmp_path, monkeypatch):
    import subprocess
    import sys

    from thorp import paths

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    assert vsm.helm() is None
    with vsm.at_sea("tf-test-s1"):
        assert vsm.helm()["name"] == "tf-test-s1"
        # a second voyage, in another process, cannot take the helm while this one holds it
        probe = (
            "import fcntl,sys; f=open(sys.argv[1],'a+')\n"
            "try: fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB); print('took')\n"
            "except BlockingIOError: print('in port')"
        )
        got = subprocess.run(
            [sys.executable, "-c", probe, str(tmp_path / "helm.lock")],
            capture_output=True,
            text=True,
        )
        assert got.stdout.strip() == "in port"
    assert vsm.helm() is None
