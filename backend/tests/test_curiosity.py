"""The curiosity ladder: the verdict logic, the token floor, and a run of both evaluators."""

import json
import random

import mlx.core as mx
import numpy as np
import pytest

from tests.conftest import WORDS, register_local
from thorp import train
from thorp.evaluators import curiosity, probes
from thorp.ledger import Ledger


@pytest.fixture
def cpu():
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


def test_bow_floor_finds_a_lexical_trait_and_not_a_shuffled_one():
    rng = np.random.default_rng(0)
    # the positive side uses tokens 0..49 more, the negative 50..99: a purely lexical trait
    mk = lambda lo: [rng.integers(lo, lo + 60, size=64) for _ in range(30)]  # noqa: E731
    assert probes.bow_auc(mk(0), mk(40), mk(0), mk(40), 128) > 0.95
    same = lambda: [rng.integers(0, 100, size=64) for _ in range(30)]  # noqa: E731
    assert 0.3 < probes.bow_auc(same(), same(), same(), same(), 128) < 0.7


def test_judge_and_order():
    v = {
        "r1_calibration": 0.6,
        "r2_novelty_auc": 0.9,
        "r3_icl": -0.4,
        "r3_copy_gain": 1.2,
        "r4_question_auc": 0.7,
        "r5_expectancy": float("nan"),
        "r5_n_q": 3.0,
        "r6_asking": 0.3,
        "r6_n_q": 40.0,
    }
    v0 = {
        "r1_calibration": 0.1,
        "r2_novelty_auc": 0.6,
        "r3_icl": 0.0,
        "r3_copy_gain": 0.0,
        "r4_question_auc": 0.55,
        "r6_asking": 0.0,
    }
    s = curiosity.judge(v, v0, {"r2": 0.7, "r4": 0.65})
    assert [s[k]["status"] for k in range(1, 7)] == [
        "present",
        "present",
        "present",
        "absent",
        "untestable",
        "present",
    ]
    ok, highest = curiosity.in_order(s)
    assert highest == 6 and not ok  # rung 6 present above an absent rung 4: against the ladder


def test_a_rung_the_token_floor_also_finds_is_absent():
    v = {
        "r1_calibration": float("nan"),
        "r2_novelty_auc": 0.9,
        "r3_icl": float("nan"),
        "r3_copy_gain": float("nan"),
        "r4_question_auc": 0.9,
        "r5_expectancy": float("nan"),
        "r6_asking": float("nan"),
    }
    s = curiosity.judge(v, {}, {"r2": 0.88, "r4": 0.5})
    assert s[2]["status"] == "absent" and s[4]["status"] == "present"
    assert curiosity.in_order(s) == (False, 4)  # rung 4 present above an absent rung 2


def talk(seed: int, n: int) -> str:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        words = " ".join(rng.choice(WORDS) for _ in range(rng.randint(5, 12)))
        if rng.random() < 0.3:
            out.append(rng.choice(["What", "Why", "Where", "Who"]) + " " + words + "?")
        else:
            out.append(words.capitalize() + ".")
    return " ".join(out) + "\n"


def test_ladder_and_floors_run_end_to_end(library, spec, tmp_thorp, cpu):
    for i in range(4):
        register_local(f"talk-{i}", talk(i, 900), "recipe")
    for i in range(3):
        fam = "Germanic" if i == 0 else "Romance"  # two held-out books on each side of Germanic
        register_local(f"talk-hole-{i}", talk(50 + i, 500), "hole-card", family=fam)
    library["lists"]["recipe.csv"] += [f"talk-{i}" for i in range(4)]
    library["lists"]["hole.csv"] += [f"talk-hole-{i}" for i in range(3)]
    spec["eval"]["evaluators"] = ["ce_bpb", "probes", "curiosity"]
    quiet = lambda *a: None  # noqa: E731
    rec = Ledger()
    prep = train.prepare(spec, resolver=library["resolver"], log=quiet)
    train.train(spec, prep, rec, stop_after=50, log=quiet)
    rid = train.run_id(spec)
    rec.run(
        {"run_id": rid, "name": "t", "spec_json": json.dumps(spec), "status": "x", "started": "x"}
    )
    train.rescore(rid, resolver=library["resolver"], rec=rec, log=quiet)
    names = {
        r["name"] for r in rec.query("select distinct name from metrics where run_id=?", [rid])
    }
    assert "curiosity/highest" in names and "curiosity/r1_calibration" in names
    assert "curiosity/init/r1_calibration" in names and "curiosity/r3_copy_gain" in names
    art = rec.query("select text from artifacts where run_id=? and kind='curiosity'", [rid])
    ladder = json.loads(art[-1]["text"])
    assert set(ladder["rungs"]) == {str(k) for k in range(1, 7)}
    assert ladder["events"]["sentences"]["fit"][0] >= curiosity.MIN_EVENTS
    pr = json.loads(
        rec.query("select text from artifacts where run_id=? and kind='probes'", [rid])[-1]["text"]
    )
    tested = [t for t in pr["traits"].values() if "auc" in t]
    assert tested and all(
        "floor_bow" in t and "floor_init" in t and "emergent" in t for t in tested
    )
