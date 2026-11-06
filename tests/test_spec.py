import yaml

from thorp import train
from thorp.ledger import Ledger


def test_same_spec_same_id(spec):
    a = train.run_id(spec)
    reordered = dict(reversed(list(spec.items())))
    assert train.run_id(reordered) == a
    assert train.run_id({**spec, "name": "something else"}) == a
    assert train.run_id({**spec, "ship": "Dinghy"}) == a, "the ship name is a label, not a setting"
    assert train.run_id({**spec, "seed": 2}) != a


def test_shipped_specs_differ_only_by_seed():
    a = train.load_spec("specs/hundred-by-reach-v1.yaml")
    b = train.load_spec("specs/hundred-by-reach-v1-seed2.yaml")
    assert {k: v for k, v in a.items() if k not in ("name", "ship", "seed")} == {
        k: v for k, v in b.items() if k not in ("name", "ship", "seed")
    }
    assert train.run_id(a) != train.run_id(b)


def test_finished_run_does_not_retrain(tmp_thorp, spec, monkeypatch):
    path = tmp_thorp / "spec.yaml"
    path.write_text(yaml.safe_dump(spec))
    rid = train.run_id(spec)
    Ledger().run(
        {
            "run_id": rid,
            "name": "test",
            "spec_json": train.canonical(spec),
            "status": "finished",
            "tokens_seen": 1,
        }
    )

    def boom(*a, **k):
        raise AssertionError("a finished run must not be prepared or trained again")

    monkeypatch.setattr(train, "prepare", boom)
    monkeypatch.setattr(train, "train", boom)
    row = train.run(path)
    assert row["run_id"] == rid and row["status"] == "finished"
