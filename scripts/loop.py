"""The book-value loop (2026-11-07; DECISIONS.md, "The book-value loop"): many small 1m runs on
random shelves, each scored on the Forgotten Tomes, so a regression can say what each kind of
book is worth and how many readings it repays.

    uv run python scripts/loop.py --runs 50

Each iteration:
  1. reads the sampler (data/loop/sampler.json; the steering sessions may edit it within its
     stated limits);
  2. draws passes from `passes`, so the unique bytes are `read_mb / passes`;
  3. draws stratum weights from a Dirichlet(`alpha`) over the strata in data/loop/features.csv
     (kind x original/translated), so shelves range from pure to mixed, and fills each stratum
     with random books until its share of the unique bytes is met (a stratum that runs out hands
     its share on to the others);
  4. writes lists/loop/loop-NNNN.csv and specs/loop/loop-NNNN.yaml (the 1m proxy, the shared
     tokeniser trained on lists/loop-pool.csv, the Forgotten Tomes scored once at the end);
  5. runs it with `thorp run`, then appends one row to data/loop/runs.csv: the iteration, its
     passes, unique bytes, the realised share of every stratum, family entropy, mean book size,
     the books, and the Forgotten Tomes score with its split.
Stops early if data/loop/STOP exists. Iteration numbers continue from runs.csv, so batches chain.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import time
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "data/loop"
SAMPLER = LOOP / "sampler.json"
RUNS = LOOP / "runs.csv"
DEFAULT_SAMPLER = {
    "read_mb": 80,
    "passes": [1, 2, 4],
    "alpha": 0.6,
    "stratum_floor": 0.0,
    "notes": "edited by steering sessions within the limits in DECISIONS.md; every edit logged in data/loop/steering.md",
}
SPLIT = ("word_inside", "word_start", "punct", "space", "newline")


def sampler() -> dict:
    if not SAMPLER.exists():
        SAMPLER.write_text(json.dumps(DEFAULT_SAMPLER, indent=1))
    return {**DEFAULT_SAMPLER, **json.loads(SAMPLER.read_text())}


def next_iteration() -> int:
    if not RUNS.exists():
        return 1
    rows = list(csv.DictReader(open(RUNS, encoding="utf-8")))
    return max((int(r["iteration"]) for r in rows), default=0) + 1


def draw_shelf(rng: random.Random, feats: list[dict], s: dict) -> tuple[list[dict], int, dict]:
    passes = rng.choice(s["passes"])
    unique = s["read_mb"] * 1e6 / passes
    strata = sorted({f["stratum"] for f in feats})
    g = [rng.gammavariate(s["alpha"], 1.0) for _ in strata]
    w = {k: v / sum(g) for k, v in zip(strata, g, strict=True)}
    if s.get("stratum_floor"):
        w = {k: max(v, s["stratum_floor"]) for k, v in w.items()}
        w = {k: v / sum(w.values()) for k, v in w.items()}
    by = {
        k: rng.sample(
            [f for f in feats if f["stratum"] == k], k=sum(f["stratum"] == k for f in feats)
        )
        for k in strata
    }
    shelf, used, carry = [], Counter(), 0.0
    for k in sorted(
        strata, key=lambda k: sum(int(f["bytes"]) for f in by[k])
    ):  # smallest first, so leftovers carry on
        target = w[k] * unique + carry
        got = 0
        while by[k] and got < target:
            f = by[k].pop()
            shelf.append(f)
            got += int(f["bytes"])
        used[k] = got
        carry = max(0.0, target - got)
    return shelf, passes, w


def entropy(shelf: list[dict], key: str) -> float:
    c = Counter()
    for f in shelf:
        c[f[key]] += int(f["bytes"])
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values() if v)


def metric(run_name: str, name: str) -> float | None:
    from thorp.ledger import Ledger

    r = Ledger().query(
        "select m.value from metrics m join runs r using(run_id) where r.name=? and m.name=?"
        " order by m.step desc, m.rowid desc limit 1",
        [run_name, name],
    )
    return r[0]["value"] if r else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=50)
    a = ap.parse_args()
    feats = list(csv.DictReader(open(LOOP / "features.csv", encoding="utf-8")))
    pool_rows = {}
    with open(ROOT / "lists/loop-pool.csv", encoding="utf-8") as f:
        for row, ft in zip(csv.DictReader(f), feats, strict=True):
            pool_rows[ft["book_id"]] = row
    strata = sorted({f["stratum"] for f in feats})
    for _ in range(a.runs):
        if (LOOP / "STOP").exists():
            print("STOP file present; stopping", flush=True)
            return
        s = sampler()
        i = next_iteration()
        rng = random.Random(1_000_003 * i + 7)
        shelf, passes, w = draw_shelf(rng, feats, s)
        name = f"loop-{i:04d}"
        with open(ROOT / f"lists/loop/{name}.csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
            wr.writeheader()
            for b in shelf:
                wr.writerow(pool_rows[b["book_id"]])
        spec = {
            "name": name,
            "ship": f"Loop {i}",
            "experiment": "the book-value loop: what is each kind of book worth, and how many readings does it repay?",
            "data": {
                "recipe": f"lists/loop/{name}.csv",
                "passes": passes,
                "order": "shuffled",
                "refuse": [
                    "lists/hole-cards.csv",
                    "lists/hole-cards-v2.csv",
                    "lists/hole-cards-unseen.csv",
                ],
            },
            "tokeniser": {
                "kind": "spm-bpe",
                "vocab": 4096,
                "byte_fallback": True,
                "train_on": "lists/loop-pool.csv",
            },
            "model": {"family": "gpt", "preset": "1m", "context": 1024},
            "optim": {
                "name": "adamw",
                "lr": 2.0e-3,
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
                "every_steps": 1000000,
                "evaluators": ["ce_bpb", "bpb_split", "nevermore"],
                # Nevermores five times over training as well (about a second each at 1m), so a
                # loop run's hand of heads can be watched forming; the full eval stays at the end
                "light": {"every_steps": 170, "evaluators": ["nevermore"]},
            },
            "checkpoint": {"every_steps": 1000000},
            "seed": i,
        }
        (ROOT / f"specs/loop/{name}.yaml").write_text(
            yaml.safe_dump(spec, sort_keys=False, width=100)
        )
        t0 = time.time()
        code = subprocess.call(
            ["uv", "run", "thorp", "run", f"specs/loop/{name}.yaml"],
            cwd=ROOT,
            stdout=open(ROOT / f"data/runs/{name}.out", "w"),
            stderr=subprocess.STDOUT,
        )
        unique = sum(int(b["bytes"]) for b in shelf)
        realised = Counter()
        for b in shelf:
            realised[b["stratum"]] += int(b["bytes"]) / unique
        row = {
            "iteration": i,
            "run": name,
            "exit": code,
            "minutes": round((time.time() - t0) / 60, 2),
            "passes": passes,
            "unique_mb": round(unique / 1e6, 2),
            "books": len(shelf),
            "mean_book_kb": round(unique / len(shelf) / 1024, 1),
            "family_entropy": round(entropy(shelf, "family"), 4),
            "alpha": s["alpha"],
            **{f"share/{k}": round(realised[k], 4) for k in strata},
            **{f"target/{k}": round(w[k], 4) for k in strata},
            "ft_bpb_en": metric(name, "eval/hole-cards-unseen/bpb_mean_en"),
            **{
                f"ft_split/{c}": metric(name, f"eval/hole-cards-unseen/split/{c}/bpb_mean_en")
                for c in SPLIT
            },
            "book_ids": " ".join(b["book_id"] for b in shelf),
        }
        new = not RUNS.exists()
        with open(RUNS, "a", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(row))
            if new:
                wr.writeheader()
            wr.writerow(row)
        print(
            f"[{time.strftime('%H:%M:%S')}] {name} passes {passes} {row['unique_mb']} MB {len(shelf)} books "
            f"exit {code} score {row['ft_bpb_en']} in {row['minutes']} min",
            flush=True,
        )


if __name__ == "__main__":
    main()
