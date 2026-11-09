"""A plan's version, 1.2.3: the journey, the content, the parameters (thorp/versioning.py, s1.run_versions)."""

from __future__ import annotations

import copy

import yaml
from thorp import paths, versioning


def _spec(name: str = "fu-ogden-v0-1~sop001@300k-pre-s1") -> dict:
    return copy.deepcopy(yaml.safe_load(paths.resolve(f"ships/specs/fitouts/{name}.yaml").read_text()))


def test_the_journey_is_the_stage_sequence():
    assert versioning.journey(_spec()) == ["pretrain"]
    staged = _spec()
    staged["data"]["stages"] = [{"name": "pretrain", "recipe": "lists/ogden-v0.1.csv"}, {"name": "maths tutor"}]
    assert versioning.journey(staged) == ["pretrain", "maths tutor"]


def test_a_seed_is_not_a_version():
    """Two seeds are one plan sailed twice: the same version, two runs."""
    a, b = _spec(), _spec()
    b["seed"] = a.get("seed", 1) + 1
    assert versioning.params_fp(a) == versioning.params_fp(b)
    assert versioning.content_fp(a) == versioning.content_fp(b)


def test_a_different_parameter_is_a_different_plan():
    a, b = _spec(), _spec()
    b["optim"]["lr"] = float(a["optim"]["lr"]) * 2
    assert versioning.params_fp(a) != versioning.params_fp(b)


def test_a_different_corpus_is_a_different_content():
    a, b = _spec(), _spec()
    b["data"]["recipe"] = "lists/ogden-v0.2.csv"
    assert versioning.content_fp(a) != versioning.content_fp(b)


def test_a_different_scaffold_is_a_different_plan():
    a, b = _spec(), _spec()
    b["optim"]["scaffold"]["hold"] = 0.4
    assert versioning.params_fp(a) != versioning.params_fp(b)


def test_assigning_the_same_plan_twice_is_one_version():
    spec = _spec()
    first = versioning.assign(spec, spec_path="a.yaml")
    second = versioning.assign(spec, spec_path="a.yaml")
    assert first == second


def test_a_new_parameter_takes_the_next_patch_and_a_new_corpus_the_next_minor():
    a, b, c = _spec(), _spec(), _spec()
    b["optim"]["lr"] = 0.004
    c["data"]["recipe"] = "lists/ogden-v0.2.csv"
    va = versioning.assign(a, spec_path="a.yaml")
    vb = versioning.assign(b, spec_path="b.yaml")
    vc = versioning.assign(c, spec_path="c.yaml")
    ma, mi, pa = (int(x) for x in va.split("."))
    mb, mib, pb = (int(x) for x in vb.split("."))
    mc, mic, pc = (int(x) for x in vc.split("."))
    assert (mb, mib) == (ma, mi) and pb > pa  # the same content, another parameter
    assert mc == ma and mic > mi and pc == 0  # new content, new minor
