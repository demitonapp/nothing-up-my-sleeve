"""The two-fact problem (2026-11-07, Justin): the ladder's first major voyage, the climb to chaining two
facts. `--baseline` writes its first round, the baseline (specs/two-facts/), which goes to the top of
the standing queue: the keel, the pilot, the speller and the stylist trained with what is known today,
to fix each class's base climb and chaining lift on the leaderboard (thorp/leaderboard.py).

One reading for every class, so the class is the only thing that changes: four passes of the
English-original fiction shelf (about 190M tokens; the book-value fit's most valuable kind; rereading
up to four times is free). One tokeniser for the pilot, the speller and the stylist (4,096 pieces
trained on the loop pool, the pilot's First Light setting); the keel keeps its 2,048 (at 300k the
embeddings are already half the model). Learning rate: each class's best known (keel 3e-3 from the keel
pathfinder; pilot 2e-3 from First Light's pathfinder; speller 1e-3 from the 9m sweep; stylist 8e-4, an
interpolation, the first stylist on this Mac). Two seeds each. Evaluators: the Forgotten Tomes score,
the discovery chains, the stars, the Nevermores and the successor every 500 steps; the chains alone
more often (every 100 steps for the keel and the pilot, 250 for the speller and the stylist), so each
rung's lighting step is seen.
"""

from __future__ import annotations

import argparse

import yaml

from thorp import fleet  # noqa: E402  (S5 'fitout': every spec names its fitout)
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

OUT = ROOT / "specs" / "two-facts"

# class name -> (preset, vocab, lr, warmup, light every, checkpoint every)
BASELINE = {
    "keel": ("300k", 2048, 0.003, 100, 100, 1000000),
    "pilot": ("1m", 4096, 0.002, 100, 100, 1000000),
    "speller": ("9m", 4096, 0.001, 200, 250, 1000),
    "stylist": ("21m", 4096, 0.0008, 300, 250, 1000),
}


def spec(cls: str, seed: int) -> dict:
    preset, vocab, lr, warmup, light, ckpt = BASELINE[cls]
    return {
        "name": f"tf-base-{cls}-s{seed}",
        "ship": f"Two facts: the {cls}'s baseline",
        "experiment": "The two-fact problem: how close does each class come to chaining two facts?",
        "question": f"With what is known today, what climb and chaining lift does the {cls} reach?",
        "data": {
            "recipe": "lists/stars-fiction.csv",
            "passes": 4,
            "order": "shuffled",
            "refuse": [
                "lists/hole-cards.csv",
                "lists/hole-cards-v2.csv",
                "lists/hole-cards-unseen.csv",
            ],
        },
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": vocab,
            "byte_fallback": True,
            "train_on": "lists/loop-pool.csv",
        },
        "model": {"family": "gpt", "preset": preset, "context": 1024},
        "optim": {
            "name": "adamw",
            "lr": lr,
            "betas": [0.9, 0.95],
            "weight_decay": 0.1,
            "warmup_steps": warmup,
            "schedule": "cosine",
            "min_lr_ratio": 0.1,
            "batch_tokens": 32768,
            "grad_clip": 1.0,
            "precision": "bf16",
        },
        "eval": {
            "sets": ["lists/hole-cards-unseen.csv"],
            "every_steps": 500,
            "evaluators": [
                "ce_bpb",
                "bpb_split",
                "discovery",
                "logic",
                "cards",
                "stars",
                "nevermore",
                "successor",
            ],
            "light": {"every_steps": light, "evaluators": ["discovery", "logic"]},
        },
        "checkpoint": {"every_steps": ckpt},
        "seed": seed,
    }


def write(s: dict) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{s['name']}.yaml"
    if not p.exists():  # a spec that may have run is never rewritten
        head = "# specs/two-facts: The two-fact problem, the baseline (2026-11-07), written by scripts/make_two_facts.py.\n"
        p.write_text(head + yaml.safe_dump(fleet.with_fitout(s), sort_keys=False, width=100))
    return f"two-facts/{s['name']}"


def baseline() -> list[str]:
    return [write(spec(cls, seed)) for cls in BASELINE for seed in (1, 2)]


# ---------------------------------------------------------------------------------------- round 2
# the diet (Justin, 12:20): the levers that should light the Nevermore and the mover, tried on the
# pilot (two seeds each) against its baseline, the winner then carried to the speller
ROUND2 = {
    "rope": {"model": {"positions": "rope"}},
    "reason": {
        "data": {
            "recipe": None,
            "passes": None,
            "stages": [
                {"name": "reading", "recipe": "lists/stars-fiction.csv", "passes": 3},
                {"name": "reasoning", "recipe": "lists/reasoning-shelf.csv", "passes": 3},
            ],
        }
    },
    "conclude": {"optim": {"copy_weight": {"alpha": 3, "kind": "conclusion"}}},
}
ROUND2["all"] = {
    "model": ROUND2["rope"]["model"],
    "data": ROUND2["reason"]["data"],
    "optim": ROUND2["conclude"]["optim"],
}


def _apply(spec: dict, change: dict) -> dict:
    import copy

    out = copy.deepcopy(spec)
    for k, v in change.items():
        for kk, vv in v.items():
            if vv is None:
                out[k].pop(kk, None)
            else:
                out[k][kk] = vv
    return out


def r2_spec(cls: str, lever: str, seed: int, change: dict) -> dict:
    s = _apply(spec(cls, seed), change)
    s["name"] = f"tf-r2-{cls}-{lever}-s{seed}"
    s["ship"] = f"Two facts, round 2: the {cls} with {lever}"
    s["question"] = (
        f"Does {lever} light the Nevermore and the mover, and lift chaining, in the {cls}?"
    )
    # the cards read often, so the step each one lights is seen
    s["eval"]["light"]["evaluators"] = ["discovery", "logic", "nevermore", "cards"]
    s["eval"]["light"]["every_steps"] = max(200, s["eval"]["light"]["every_steps"])
    return s


def round2() -> list[str]:
    return [
        write(r2_spec("pilot", lever, seed, ROUND2[lever])) for lever in ROUND2 for seed in (1, 2)
    ]


def _score(rec, name: str) -> tuple[float, float] | None:
    rows = rec.query(
        "select run_id from runs where name=? and status='finished' order by started desc limit 1",
        [name],
    )
    if not rows:
        return None
    rid = rows[0]["run_id"]

    def last(metric: str):
        r = rec.query(
            "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
            [rid, metric],
        )
        return r[0]["value"] if r else None

    from thorp import leaderboard

    lifts = [last(f"tricks/{k}/lift") for k in leaderboard.chaining_tests()]
    gain = last("tricks/logic_test/gain")
    if None in lifts or gain is None:
        return None
    return sum(lifts) / len(lifts), gain


def pick() -> list[str]:
    """After round 2 on the pilot: the lever whose two seeds score best (chaining lift plus logic gain,
    each the seeds' mean) is carried to the speller, two seeds, put after the speller's baseline."""
    from thorp.ledger import Ledger

    rec = Ledger()
    cands = {"baseline": [f"tf-base-pilot-s{s}" for s in (1, 2)]}
    cands |= {lever: [f"tf-r2-pilot-{lever}-s{s}" for s in (1, 2)] for lever in ROUND2}
    scores = {}
    for lever, names in cands.items():
        got = [x for n in names if (x := _score(rec, n))]
        if got:
            scores[lever] = sum(c + g for c, g in got) / len(got)
    lines = [f"round 2 on the pilot, chaining lift + logic gain (seeds' mean): {scores}"]
    best = max((k for k in scores if k != "baseline"), key=lambda k: scores[k], default="all")
    if "baseline" in scores and best in scores and scores[best] <= scores["baseline"]:
        lines.append("no lever beat the baseline; the speller gets every lever together ('all')")
        best = "all"
    lines.append(f"carried to the speller: {best}")
    names = [write(r2_spec("speller", best, seed, ROUND2[best])) for seed in (1, 2)]
    # the store is the queue (11 November), not specs/queue.txt: the block goes in after the base speller's lines
    from thorp.viable.s2_coordination import queue_read, queue_store

    ql = queue_read.pending()
    at = max((i for i, line in enumerate(ql) if line.startswith("two-facts/tf-base-speller")), default=-1) + 1
    for k, n in enumerate(queue_read.add(names)):
        queue_store.move(n, at + k + 1)  # 1-based
    (ROOT / "data" / "runs" / "two-facts" / "round2-pick.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return names


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--baseline", action="store_true")
    g.add_argument("--round2", action="store_true")
    g.add_argument("--pick", action="store_true")
    a = ap.parse_args()
    print("\n".join(baseline() if a.baseline else round2() if a.round2 else pick()))
