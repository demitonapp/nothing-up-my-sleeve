"""Fitouts made in the UI (2026-11-07, Justin: "an ability for the user in the UI to mix and match and
create their own fitouts... pick particular data sets and then choose how much data you want from those
data sets, whether to randomize the data set, and then drag and drop them into a fitout builder which
then builds for specific model sizes").

A fitout here is a dict, saved as data/fitouts/<key>.json and shown beside the hand-curated ones in
fleet.FITOUTS:

    {"key", "name", "aim", "positions": "learned"|"rope", "tack": {...}|null,
     "stages": [{"phase": "pretraining"|"post-training", "name", "shelf": "lists/...csv",
                 "compose": {...}|null (the stage's books as declared weights and filters: thorp/selection.py;
                             `thorp select compose` writes the shelf from it),
                 "tokens": int|null (null: the whole shelf), "select": "all"|"random"|"repeat"|"frontier",
                 "passes", "lr": float|null, "tack": {...}|null, "purpose"}]}

**Selection** (how a stage takes its amount from a shelf): `all` (the shelf as listed), `random` (books in
a seeded random order), `repeat` (books by their in-window repeated-trigram rate, highest first:
thorp/trigrams.py, the induction head's food), `frontier` (the shelf's Pareto frontier of repetition and
variety first, then by repeat rate). Books are taken in that order until the stage's tokens are reached;
the chosen books are written to lists/fitouts/<key>/<n>-<stage>.csv, so a run reads a fixed list.

**Building for a class** (`compile_for(key, preset, seed)`): the stages become runs as in
scripts/make_fitout.py (pretraining one run under one schedule; each post-training stage a run seeded
from the one before), with the class's own vocabulary and learning rate where the fitout leaves them
open. `queue(key, preset, seeds)` writes the specs and puts them at the top of the standing queue.
"""

from __future__ import annotations

import copy
import csv
import json
import random
import re

from thorp import paths

SELECT = ("all", "random", "repeat", "frontier")
PHASES = ("pretraining", "post-training")
BYTES_PER_TOKEN = 4.0


def _dir():
    p = paths.fitouts_dir()  # ships/fitouts: saved fitouts are ship material, kept in git
    p.mkdir(parents=True, exist_ok=True)
    return p


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "fitout"


def _compose(stage: dict, i: int) -> dict | None:
    """The stage's declared selection of books (thorp/selection.py), in full form, or None."""
    if not stage.get("compose"):
        return None
    from thorp import selection

    try:
        return selection.validate(stage["compose"])
    except selection.SelectionError as e:
        raise ValueError(f"stage {i + 1}: {e}") from e


def validate(d: dict) -> dict:
    out = {k: d.get(k) for k in ("key", "name", "aim", "positions", "tack", "opt_in")}
    out["opt_in"] = (
        out["opt_in"] or ""
    ).strip()  # the stores rule's written opt-in, carried to every run
    out["name"] = (out["name"] or "").strip() or "an unnamed fitout"
    out["key"] = _key(out["key"] or out["name"])
    out["positions"] = out["positions"] if out["positions"] in ("learned", "rope") else "rope"
    stages = []
    for i, s in enumerate(d.get("stages") or []):
        shelf = s.get("shelf") or ""
        if not paths.resolve(shelf).exists() and not s.get("compose"):  # a composed shelf is written by `thorp select compose`
            raise ValueError(f"stage {i + 1}: no shelf {shelf!r}")
        phase = s.get("phase", "pretraining")
        if phase not in PHASES:
            raise ValueError(f"stage {i + 1}: phase must be one of {PHASES}")
        select = s.get("select", "all")
        if select not in SELECT:
            raise ValueError(f"stage {i + 1}: select must be one of {SELECT}")
        stages.append(
            {
                "phase": phase,
                "name": (s.get("name") or f"stage {i + 1}").strip(),
                "shelf": shelf,
                "tokens": int(s["tokens"]) if s.get("tokens") else None,
                "select": select,
                "passes": max(1, int(s.get("passes") or 1)),
                "lr": float(s["lr"]) if s.get("lr") else None,
                "tack": s.get("tack") or None,
                "purpose": s.get("purpose") or "",
                "compose": _compose(s, i),
            }
        )
    if not any(s["phase"] == "pretraining" for s in stages):
        raise ValueError("a fitout needs at least one pretraining stage")
    # pretraining first, then post-training, each in the order given
    out["stages"] = [s for s in stages if s["phase"] == "pretraining"] + [
        s for s in stages if s["phase"] == "post-training"
    ]
    return out


def save(d: dict) -> str:
    f = validate(d)
    (_dir() / f"{f['key']}.json").write_text(json.dumps(f, indent=1))
    return f["key"]


def load(key: str) -> dict | None:
    p = _dir() / f"{key}.json"
    return json.loads(p.read_text()) if p.exists() else None


def saved() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(_dir().glob("*.json"))]


def from_curated(key: str) -> dict:
    """A hand-curated fitout (fleet.FITOUTS) in the saved form, so both compile one way."""
    from thorp import fleet

    f = fleet.FITOUTS[key]

    def st(s, phase):
        return {
            "phase": phase,
            "name": s.name,
            "shelf": s.shelf,
            "tokens": None,
            "select": "all",
            "passes": s.passes,
            "lr": s.lr,
            "tack": s.tack,
            "purpose": s.purpose,
        }

    return {
        "key": f.key,
        "name": f.name,
        "aim": f.aim,
        "positions": f.positions,
        "tack": f.tack,
        "vocab": f.vocab,
        "stages": [st(s, "pretraining") for s in f.pretraining]
        + [st(s, "post-training") for s in f.posttraining],
    }


def _choose(key: str, n: int, stage: dict, seed: int) -> str:
    """The stage's shelf, or a fixed list of the books it takes (lists/fitouts/<key>/<n>-<name>.csv)."""
    if stage["select"] == "all" and not stage["tokens"]:
        return stage["shelf"]
    from thorp import manifest, shelves, trigrams

    shelf = next((s for s in shelves.payload() if s["path"] == stage["shelf"]), None)
    ids = list(shelf["book_ids"]) if shelf else []
    if stage["select"] == "random":
        random.Random(seed * 7919 + n).shuffle(ids)
    elif stage["select"] in ("repeat", "frontier"):
        st = trigrams.measure_books(ids)
        front = trigrams.frontier(st) if stage["select"] == "frontier" else set()
        ids.sort(key=lambda b: (b not in front, -st.get(b, {}).get("repeat_rate", 0.0)))
    budget = (stage["tokens"] or 10**18) * BYTES_PER_TOKEN
    chosen, got = [], 0.0
    for b in ids:
        if got >= budget:
            break
        bk = manifest.get(b)
        if bk is None:
            continue
        chosen.append(bk)
        got += bk.bytes or 0
    out = paths.resolve(f"lists/fitouts/{key}")
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{n}-{_key(stage['name'])}-s{seed}.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        for bk in chosen:
            w.writerow(
                {
                    "title": bk.title,
                    "author": bk.author,
                    "language": bk.language or "en",
                    "family": bk.family or "",
                    "text": f"local:{bk.id}",
                }
            )
    return f"lists/fitouts/{key}/{p.name}"


def compile_for(key: str, preset: str, seed: int) -> list[dict]:
    """The fitout (saved or hand-curated) built for a class: a pretraining run, then a run per
    post-training stage seeded from the one before."""
    import sys

    from thorp import fleet

    f = load(key) or (from_curated(key) if key in fleet.FITOUTS else None)
    if f is None:
        raise KeyError(f"no fitout {key!r}")
    sys.path.insert(0, str(paths.resolve("scripts")))
    from make_two_facts import BASELINE
    from make_two_facts import spec as base_spec

    cls = next((c for c, v in BASELINE.items() if v[0] == preset), None)
    if cls is None:
        raise KeyError(f"no class with the preset {preset!r} in the two-fact baseline")
    base = base_spec(cls, seed)
    base["model"]["positions"] = f.get("positions", "rope")
    from thorp import cleaning

    base["data"]["clean"] = f.get("clean") or cleaning.CURRENT  # S5 'clean': a new fitout reads clean text
    if f.get("opt_in"):
        base["data"]["opt_in"] = f["opt_in"]
    if f.get("vocab"):
        base["tokeniser"]["vocab"] = f["vocab"]
    base["eval"]["evaluators"] = ["ce_bpb", "discovery", "logic", "stars", "nevermore", "cards"]
    base["eval"]["light"] = {
        "every_steps": 100,
        "evaluators": ["stars", "nevermore", "cards", "logic"],
    }
    tag = f"{f['key']}@{preset}"
    pre = [s for s in f["stages"] if s["phase"] == "pretraining"]
    post = [s for s in f["stages"] if s["phase"] == "post-training"]
    specs = []
    p0 = copy.deepcopy(base)
    p0["name"] = f"fu-{tag}-pre-s{seed}"
    p0["ship"] = f"Fitout: {f['name']} @ {preset}, pretraining"
    p0["experiment"] = f"Fitout {f['key']}: {f.get('aim') or ''}"
    p0["question"] = "Which cards does the pretraining draw?"
    p0["fitout"] = {"key": f["key"], "variation": None}  # S5 policy 'fitout': the fitout it is
    p0["data"].pop("recipe", None)
    p0["data"].pop("passes", None)
    p0["data"]["stages"] = [
        {"name": s["name"], "recipe": _choose(f["key"], i, s, seed), "passes": s["passes"]}
        for i, s in enumerate(pre, 1)
    ]
    if f.get("tack"):
        p0["optim"]["copy_weight"] = dict(f["tack"])
    specs.append(p0)
    prev = p0["name"]
    for i, s in enumerate(post, 1):
        p = copy.deepcopy(base)
        p["name"] = f"fu-{tag}-post{i}-s{seed}"
        p["ship"] = f"Fitout: {f['name']} @ {preset}, post-training {i} ({s['name']})"
        p["experiment"] = p0["experiment"]
        p["question"] = f"What does post-training on {s['name']} add?"
        p["fitout"] = {"key": f["key"], "variation": None}
        p["data"]["recipe"] = _choose(f["key"], len(pre) + i, s, seed)
        p["data"]["passes"] = s["passes"]
        p["optim"]["lr"] = s["lr"] or base["optim"]["lr"] / 3
        p["optim"]["warmup_steps"] = 20
        p["optim"].pop("copy_weight", None)
        if s.get("tack"):
            p["optim"]["copy_weight"] = dict(s["tack"])
        p["seeded_from"] = {"run": prev, "mode": "free"}
        specs.append(p)
        prev = p["name"]
    return specs


def queue(key: str, preset: str, seeds: tuple[int, ...] = (1, 2), where: str = "top", by: str | None = None) -> list[str]:
    """Write the specs and put them in the standing queue: at the top (next after the running job),
    or at the end."""
    import yaml

    lines = []
    out = paths.resolve("specs/fitouts")
    out.mkdir(parents=True, exist_ok=True)
    from thorp import liberty_machine

    built = [s for seed in seeds for s in compile_for(key, preset, seed)]
    for s in built:  # S3 before the queue: a fitout the gate would refuse is not queued at all
        liberty_machine.gate(s, where="fitout builder")
    for s in built:
        p = out / f"{s['name']}.yaml"
        if not p.exists():
            p.write_text(
                "# specs/fitouts: built in the fitout builder (thorp/fitouts.py).\n"
                + yaml.safe_dump(s, sort_keys=False, width=100)
            )
        lines.append(f"fitouts/{s['name']}")
    (paths.data_dir() / "runs" / "fitouts").mkdir(parents=True, exist_ok=True)
    # the store is the queue (11 November): specs/queue.txt is only the CLI's export, which the coordinator
    # never reads, so a block written there never sailed. A line already queued keeps its place.
    from thorp.viable.s2_coordination import queue_read

    queue_read.add(lines, top=where == "top", by=by)
    return lines
