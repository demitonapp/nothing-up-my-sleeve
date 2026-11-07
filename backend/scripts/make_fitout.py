"""Compile a hand-curated fitout (fleet.FITOUTS) into specs (2026-11-07, Justin: "a fitout is the
training material matched to the pretraining (and stages) and post-training (and stages)").

Pretraining is one run reading the fitout's pretraining stages in order under one schedule
(data.stages), with the fitout's tack. Each post-training stage is its own run, seeded from the run
before (seeded_from, mode free: every weight carried and trained), reading its shelf at its own
learning rate and tack. Names: fo-<key>-pre-s<seed>, fo-<key>-post<i>-s<seed>; ship labels
"Fitout: <name>, <stage>". Evaluated like the card census (cards every 100 steps) with the chains and
the logic deck, so each stage's effect on the cards and on cause and effect is seen.

    uv run python scripts/make_fitout.py keel-cards-cause    # writes specs/fitouts/, prints the queue lines
"""

from __future__ import annotations

import copy
import sys

import yaml

from thorp import fleet  # noqa: E402  (S5 'fitout': every spec names its fitout)
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

sys.path.insert(0, str(ROOT / "scripts"))
from make_two_facts import BASELINE  # noqa: E402
from make_two_facts import spec as base_spec  # noqa: E402

OUT = ROOT / "specs" / "fitouts"


def _class_name(preset: str) -> str:
    return next(c for c, v in BASELINE.items() if v[0] == preset)


def compile_fitout(key: str, seed: int) -> list[dict]:
    from thorp import fleet

    f = fleet.FITOUTS[key]
    cls = _class_name(f.preset)
    base = base_spec(cls, seed)
    base["model"]["positions"] = f.positions
    base["tokeniser"]["vocab"] = f.vocab
    if f.clean != "raw":  # S5 'clean'; raw leaves the key out, so no compiled run id moves
        base["data"]["clean"] = f.clean
    base["eval"]["evaluators"] = ["ce_bpb", "discovery", "logic", "stars", "nevermore", "cards"]
    base["eval"]["light"] = {
        "every_steps": 100,
        "evaluators": ["stars", "nevermore", "cards", "logic"],
    }
    specs = []
    pre = copy.deepcopy(base)
    pre["name"] = f"fo-{key}-pre-s{seed}"
    pre["ship"] = f"Fitout: {f.name}, pretraining"
    pre["experiment"] = f"Fitout {key}: {f.aim}"
    pre["question"] = "Which cards does the pretraining draw?"
    pre["data"].pop("recipe", None)
    pre["data"].pop("passes", None)
    pre["data"]["stages"] = [
        {"name": s.name, "recipe": s.shelf, "passes": s.passes} for s in f.pretraining
    ]
    if f.tack:
        pre["optim"]["copy_weight"] = dict(f.tack)
    specs.append(pre)
    prev = pre["name"]
    for i, st in enumerate(f.posttraining, 1):
        post = copy.deepcopy(base)
        post["name"] = f"fo-{key}-post{i}-s{seed}"
        post["ship"] = f"Fitout: {f.name}, post-training {i} ({st.name})"
        post["experiment"] = f"Fitout {key}: {f.aim}"
        post["question"] = f"What does post-training on {st.name} add? {st.purpose}"
        post["data"]["recipe"] = st.shelf
        post["data"]["passes"] = st.passes
        post["optim"]["lr"] = st.lr or base["optim"]["lr"]
        post["optim"]["warmup_steps"] = 20
        post["optim"].pop("copy_weight", None)
        if st.tack:
            post["optim"]["copy_weight"] = dict(st.tack)
        post["seeded_from"] = {"run": prev, "mode": "free"}
        specs.append(post)
        prev = post["name"]
    return specs


def write(s: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{s['name']}.yaml"
    if not p.exists():
        head = "# specs/fitouts: a hand-curated fitout (2026-11-07), compiled by scripts/make_fitout.py.\n"
        p.write_text(head + yaml.safe_dump(fleet.with_fitout(s), sort_keys=False, width=100))
    return f"fitouts/{s['name']}"


# ------------------------------------------------------------------------------------- ablations
# The card census around a fitout (Justin, 13:20: "the card census and the cause score should run with
# the same fitout or small variations of it, so we have good data to compare"): each variation removes
# or changes one piece of the fitout, one seed, every stage run, so a difference in the cards or the
# cause gain traces to one change.
def ablations(key: str) -> dict[str, tuple]:
    """variation -> (the varied Fitout, spec changes applied to every run)."""
    from dataclasses import replace

    from thorp import fleet

    f = fleet.FITOUTS[key]
    pre, post = list(f.pretraining), list(f.posttraining)

    def without(stages, name):
        return tuple(s for s in stages if s.name != name)

    fiction = next(s for s in pre if s.name == "fiction")
    keel = f.preset == fleet.NURSERY  # the class's own shape and settings for the variations
    heads, deeper = ("h4", "l3") if keel else ("h8", "l6")
    small_vocab, lr_high, lr_low = (1024, 0.01, 0.001) if keel else (2048, 0.004, 0.001)
    out = {
        "no-rope": (replace(f, positions="learned"), {}),
        "no-copy": (replace(f, tack=None), {}),
        "no-nursery": (replace(f, pretraining=without(pre, "nursery")), {}),
        "no-verse": (replace(f, pretraining=without(pre, "verse")), {}),
        "no-cause-pre": (replace(f, pretraining=without(pre, "cause")), {}),
        "no-reasoning-post": (replace(f, posttraining=without(post, "reasoning")), {}),
        "no-cause-post": (replace(f, posttraining=without(post, "cause again")), {}),
        "fiction-only-pre": (replace(f, pretraining=(replace(fiction, passes=4),)), {}),
        "heads": (f, {"model": {"preset": f"{f.preset}-{heads}"}}),
        "deeper": (f, {"model": {"preset": f"{f.preset}-{deeper}"}}),
        "vocab-small": (replace(f, vocab=small_vocab), {}),
        "lr-high": (f, {"pre_lr": lr_high}),
        "lr-low": (f, {"pre_lr": lr_low}),
        "longer": (replace(f, pretraining=tuple(replace(s, passes=s.passes * 2) for s in pre)), {}),
        "cause-heavy": (
            replace(
                f,
                pretraining=tuple(
                    replace(s, passes=s.passes * 2) if s.name == "cause" else s for s in pre
                ),
                posttraining=tuple(
                    replace(s, passes=s.passes * 2) if "cause" in s.name else s for s in post
                ),
            ),
            {},
        ),
    }
    return out


def compile_variant(key: str, variant: str, seed: int = 1) -> list[dict]:
    from thorp import fleet

    fv, changes = ablations(key)[variant]
    saved = fleet.FITOUTS[key]
    fleet.FITOUTS[key] = fv  # compile_fitout reads the registry; the varied fitout stands in for it
    try:
        specs = compile_fitout(key, seed)
    finally:
        fleet.FITOUTS[key] = saved
    prev = None
    for s in specs:
        s["name"] = s["name"].replace(f"fo-{key}-", f"fo-{key}~{variant}-")
        s["ship"] = s["ship"].replace(f"Fitout: {saved.name}", f"Fitout: {saved.name} ~ {variant}")
        for k, v in changes.items():
            if k == "pre_lr":
                if "seeded_from" not in s:
                    s["optim"]["lr"] = v
            else:
                s[k].update(v)
        if prev is not None:
            s["seeded_from"]["run"] = prev
        prev = s["name"]
    return specs


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument(
        "--ablations", action="store_true", help="write the census variations, one seed"
    )
    a = ap.parse_args()
    if a.ablations:
        from thorp.train import run_id

        # a variation's stage identical to the fitout's own (seed 1) reuses that run: no run twice
        base = {}
        for s in compile_fitout(a.key, 1):
            base[run_id(s)] = s["name"]
        census = {"fitout": [x["name"] for x in compile_fitout(a.key, 1)]}
        for v in ablations(a.key):
            renamed = {}
            census[v] = []
            for s in compile_variant(a.key, v):
                if "seeded_from" in s and s["seeded_from"]["run"] in renamed:
                    s["seeded_from"]["run"] = renamed[s["seeded_from"]["run"]]
                rid = run_id(s)
                if rid in base:
                    renamed[s["name"]] = base[rid]
                    census[v].append(base[rid])
                    continue
                census[v].append(s["name"])
                print(write(s))
        # which runs make up each variation, stage by stage, for the census summary
        import json as _json

        out = ROOT / "data" / "runs" / "cards" / f"fitout-census-{a.key}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(census, indent=1))
    else:
        for seed in (1, 2):
            for s in compile_fitout(a.key, seed):
                print(write(s))
