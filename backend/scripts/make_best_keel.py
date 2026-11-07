"""The best keel (2026-11-07, Justin): the 300k that performs best on its four discovery rungs, Like
father, like son; Fire and ice; One, two, three; and Again and again. The voyage the current queue
ends in.

Round 1 (`--round 1`, written into specs/best-keel/ and queued): the keel pathfinder's recipe (two
passes of the English-original fiction shelf, vocabulary 2,048 on the loop pool, context 1,024,
learning rate 3e-3) as the baseline, then one lever changed at a time, two seeds each:
vocabulary (1,024; 4,096), learning rate (1e-3; 1e-2), context (256), passes (1; 4), shelf (verse;
the mixed pool; the nursery shelf of children's books) and stages (the nursery shelf, then the fiction
shelf). Round 2 (`--round 2`, a queue `cmd:` after round 1): for each lever, the setting whose seeds
score best, all winners combined into one ship, three seeds, put at the top of the queue, followed
by the verdict. `--verdict` writes data/runs/best-keel.md: every ship ranked, and the best keel.

The score, pre-registered (DECISIONS.md, "The best keel"): at the last reading, the number of the four
rungs performed (lift at least 0.1 and two-thirds of the pairs right), then the smallest of the four
lifts (the keel is judged by its weakest chain), then their mean; a ship's score is its seeds' mean.
"""

from __future__ import annotations

import argparse
import copy
import statistics

import yaml

from thorp import fleet  # noqa: E402  (S5 'fitout': every spec names its fitout)
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

OUT = ROOT / "specs" / "best-keel"
RUNGS = ("kin_test", "fire_test", "counting_test", "again_test")

BASE = {
    "data": {
        "recipe": "lists/stars-fiction.csv",
        "passes": 2,
        "order": "shuffled",
        "refuse": [
            "lists/hole-cards.csv",
            "lists/hole-cards-v2.csv",
            "lists/hole-cards-unseen.csv",
        ],
    },
    "tokeniser": {
        "kind": "spm-bpe",
        "vocab": 2048,
        "byte_fallback": True,
        "train_on": "lists/loop-pool.csv",
    },
    "model": {"family": "gpt", "preset": "300k", "context": 1024},
    "optim": {
        "name": "adamw",
        "lr": 0.003,
        "betas": [0.9, 0.95],
        "weight_decay": 0.1,
        "warmup_steps": 100,
        "schedule": "cosine",
        "min_lr_ratio": 0.1,
        "batch_tokens": 32768,
        "grad_clip": 1.0,
        "precision": "bf16",
    },
    "eval": {
        "sets": ["lists/hole-cards-unseen.csv"],
        "every_steps": 500,
        "evaluators": ["ce_bpb", "discovery"],
        "light": {"every_steps": 100, "evaluators": ["discovery"]},
    },
    "checkpoint": {"every_steps": 1000000},
}

# lever -> setting -> change to the baseline (None: the baseline itself)
LEVERS: dict[str, dict[str, dict | None]] = {
    "vocab": {
        "2048": None,
        "1024": {"tokeniser": {"vocab": 1024}},
        "4096": {"tokeniser": {"vocab": 4096}},
    },
    "lr": {"3e-3": None, "1e-3": {"optim": {"lr": 0.001}}, "1e-2": {"optim": {"lr": 0.01}}},
    "context": {"1024": None, "256": {"model": {"context": 256}}},
    "passes": {"2": None, "1": {"data": {"passes": 1}}, "4": {"data": {"passes": 4}}},
    "shelf": {
        "fiction": None,
        "verse": {"data": {"recipe": "lists/stars-verse.csv"}},
        "pool": {"data": {"recipe": "lists/stars-pool.csv"}},
        "nursery": {"data": {"recipe": "lists/keel-nursery.csv"}},
        "nursery-then-fiction": {
            "data": {
                "recipe": None,
                "passes": None,
                "stages": [
                    {"name": "nursery", "recipe": "lists/keel-nursery.csv", "passes": 2},
                    {"name": "fiction", "recipe": "lists/stars-fiction.csv", "passes": 2},
                ],
            }
        },
    },
}


def merge(spec: dict, change: dict | None) -> dict:
    out = copy.deepcopy(spec)
    for k, v in (change or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            for kk, vv in v.items():
                if vv is None:
                    out[k].pop(kk, None)
                else:
                    out[k][kk] = vv
        else:
            out[k] = v
    return out


def spec_for(name: str, label: str, change: dict | None, seed: int, question: str) -> dict:
    s = merge(BASE, change)
    return {
        "name": name,
        "ship": f"Best keel: {label}",
        "experiment": "The best keel: which 300k performs best on its four discovery rungs?",
        "question": question,
        **s,
        "seed": seed,
    }


def write(spec: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{spec['name']}.yaml"
    if not p.exists():  # a spec that may have run is never rewritten
        head = (
            "# specs/best-keel: The best keel (2026-11-07), written by scripts/make_best_keel.py.\n"
        )
        p.write_text(head + yaml.safe_dump(fleet.with_fitout(spec), sort_keys=False, width=100))
    return f"best-keel/{spec['name']}"


def round1() -> list[str]:
    names = [
        write(
            spec_for(
                f"kb-baseline-s{sd}", "the keel pathfinder's recipe", None, sd, "The baseline."
            )
        )
        for sd in (1, 2)
    ]
    for lever, settings in LEVERS.items():
        for setting, change in settings.items():
            if change is None:
                continue
            for sd in (1, 2):
                names.append(
                    write(
                        spec_for(
                            f"kb-{lever}-{setting}-s{sd}",
                            f"{lever} {setting}",
                            change,
                            sd,
                            f"Does {lever} {setting} make a better keel than the baseline?",
                        )
                    )
                )
    return names


def _final(rec, name: str) -> dict | None:
    rows = rec.query("select run_id from runs where name=? order by started desc limit 1", [name])
    if not rows:
        return None
    rid = rows[0]["run_id"]
    m: dict[str, float] = {}
    for r in rec.query(
        "select name, value from metrics where run_id=? and name like 'tricks/%' order by step, rowid",
        [rid],
    ):
        m[r["name"]] = r["value"]
    return m


def score(m: dict) -> tuple[float, float, float]:
    from thorp import fleet

    lifts = [m.get(fleet.TRICKS[k].metric, float("-inf")) for k in RUNGS]
    return (
        sum(fleet.performed(k, m) for k in RUNGS),
        min(lifts),
        statistics.mean(lifts),
    )


def ship_scores(rec, prefix: str = "kb-") -> dict[str, tuple]:
    by: dict[str, list[tuple]] = {}
    for r in rec.query("select distinct name from runs where name like ?", [prefix + "%"]):
        m = _final(rec, r["name"])
        if m:
            by.setdefault(r["name"].rsplit("-s", 1)[0], []).append(score(m))
    return {k: tuple(statistics.mean(x[i] for x in v) for i in range(3)) for k, v in by.items()}


def round2() -> list[str]:
    from thorp.ledger import Ledger

    ships = ship_scores(Ledger())
    change: dict = {}
    chosen = {}
    for lever, settings in LEVERS.items():
        cands = {"baseline" if c is None else s: c for s, c in settings.items()}
        best = max(
            cands,
            key=lambda s: ships.get(
                "kb-baseline" if cands[s] is None else f"kb-{lever}-{s}", (-1, -9, -9)
            ),
        )
        chosen[lever] = best
        for k, v in (cands[best] or {}).items():
            change.setdefault(k, {}).update(v)
    label = ", ".join(f"{k} {v}" for k, v in chosen.items())
    names = [
        write(
            spec_for(
                f"kb-best-s{sd}",
                f"the winners combined ({label})",
                change,
                sd,
                "Do the winning settings, combined, make the best keel?",
            )
        )
        for sd in (1, 2, 3)
    ]
    q = ROOT / "specs" / "queue.txt"
    text = q.read_text()
    block = (
        f"# The best keel, round 2 (written by scripts/make_best_keel.py --round 2): {label}\n"
        + "".join(n + "\n" for n in names)
        + "cmd: uv run python scripts/make_best_keel.py --verdict > data/runs/best-keel-verdict.out 2>&1\n"
    )
    q.write_text(block + text)  # the queue takes the first line next: round 2 runs now
    return names


def verdict() -> None:
    from thorp.ledger import Ledger

    rec = Ledger()
    ships = ship_scores(rec)
    ranked = sorted(ships.items(), key=lambda kv: kv[1], reverse=True)
    best_ship = ranked[0][0]
    runs = [
        r["name"]
        for r in rec.query("select distinct name from runs where name like ?", [best_ship + "-s%"])
    ]
    best_run = max(runs, key=lambda n: score(_final(rec, n)))
    lines = [
        "# The best keel: the verdict",
        "",
        "Score: rungs performed (of 4), then the weakest lift, then the mean lift; a ship's score is its seeds' mean.",
        "",
        "| ship | rungs | weakest lift | mean lift |",
        "|---|---|---|---|",
    ]
    lines += [f"| {k} | {v[0]:.1f} | {v[1]:+.3f} | {v[2]:+.3f} |" for k, v in ranked]
    lines += ["", f"**The best keel: {best_ship}; its best sailing {best_run}.**"]
    out = ROOT / "data" / "runs" / "best-keel.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--round", type=int, choices=(1, 2))
    g.add_argument("--verdict", action="store_true")
    a = ap.parse_args()
    if a.verdict:
        verdict()
    elif a.round == 1:
        print("\n".join(round1()))
    else:
        print("\n".join(round2()))
