"""Write the First Light voyage (2026-11-07; DECISIONS.md, "First Light"): the quickest path to the
first two stars, the previous-word and duplicate-word heads, on the 1m model.

Set up from what the book-value voyage learned: rereading up to four times costs nothing, so a
shelf may be read many times; English-original fiction is the most valuable kind for the Forgotten
Tomes, so it is the baseline shelf; and the previous-word star grows with reading (0.04 at 26M
tokens, about 0.3 at 130M), so every run reads about TOKENS and the pathfinder twice that.

Every run: the pilot (1m); the stars and the Nevermore every 25 steps (a light eval, about a second);
the Forgotten Tomes score, its split, the stars and the Nevermore every 500 steps and at the end.

    uv run python scripts/make_first_light.py            # the pathfinder and round 1 (15 runs)
    uv run python scripts/make_first_light.py --combo vocab=2048 lr=0.004 shelf=fiction --seeds 1 2

Writes lists/stars-*.csv, specs/first-light/*.yaml and prints the spec names in queue order.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOKENS = 130e6  # tokens read per round-1 run
BYTES_PER_TOKEN = 2.9  # 4,096-piece vocabulary on the pool, measured on the loop runs
BASE = {"vocab": 4096, "lr": 2.0e-3, "shelf": "fiction"}
SHELVES = {
    "fiction": "English-original fiction (the book-value winner)",
    "verse": "verse, original and translated: refrains, rhyme, repetition",
    "pool": "the whole mixed pool (the book-value average)",
}


def shelves() -> dict[str, tuple[str, float]]:
    """Write the three shelf lists; returns {shelf: (list path, MB)}."""
    feats = list(csv.DictReader(open(ROOT / "data/loop/features.csv", encoding="utf-8")))
    rows = list(csv.DictReader(open(ROOT / "lists/loop-pool.csv", encoding="utf-8")))
    pick = {
        "fiction": [i for i, f in enumerate(feats) if f["stratum"] == "fiction/original"],
        "verse": [i for i, f in enumerate(feats) if f["kind"] == "verse"],
        "pool": list(range(len(feats))),
    }
    cap = 190e6  # bytes on one shelf at most, so a shelf is read at least about twice
    out = {}
    for name, idx in pick.items():
        random.Random(20261107).shuffle(idx)
        chosen, total = [], 0
        for i in idx:
            if total >= cap:
                break
            chosen.append(i)
            total += int(feats[i]["bytes"])
        path = f"lists/stars-{name}.csv"
        with open(ROOT / path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
            w.writeheader()
            for i in sorted(chosen):
                w.writerow(rows[i])
        out[name] = (path, total / 1e6)
    return out


def spec(name: str, label: str, levers: dict, seed: int, tokens: float, lists: dict) -> dict:
    v = {**BASE, **levers}
    optim_extra = (
        {"copy_weight": {"alpha": v["copy"], "kind": "induction"}} if v.get("copy") else {}
    )
    path, mb = lists[v["shelf"]]
    passes = max(1, round(tokens * BYTES_PER_TOKEN / (mb * 1e6)))
    return {
        "name": name,
        "ship": f"First Light: {label}",
        "experiment": "First Light: the quickest path to the previous-word and duplicate-word stars",
        "question": f"How soon do the first two stars light with {label}?",
        "data": {
            "recipe": path,
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
            "vocab": v["vocab"],
            "byte_fallback": True,
            "train_on": "lists/loop-pool.csv",
        },
        "model": {"family": "gpt", "preset": "1m", "context": 1024},
        "optim": {
            "name": "adamw",
            "lr": v["lr"],
            "betas": [0.9, 0.95],
            "weight_decay": 0.1,
            "warmup_steps": 100,
            "schedule": "cosine",
            "min_lr_ratio": 0.1,
            "batch_tokens": 32768,
            "grad_clip": 1.0,
            "precision": "bf16",
            **optim_extra,
        },
        "eval": {
            "sets": ["lists/hole-cards-unseen.csv"],
            "every_steps": 500,
            "evaluators": ["ce_bpb", "bpb_split", "stars", "nevermore", "soundings", "successor"],
            "light": {
                "every_steps": 25,
                "evaluators": ["stars", "nevermore", "soundings", "successor"],
            },
        },
        "checkpoint": {"every_steps": 1000000},
        "seed": seed,
    }


def write(s: dict) -> str:
    d = ROOT / "specs/first-light"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{s['name']}.yaml"
    if p.exists():  # never rewrite a spec that may have run
        return f"first-light/{s['name']}"
    p.write_text(
        f"# specs/first-light/{s['name']}.yaml: the First Light voyage (2026-11-07), written by "
        "scripts/make_first_light.py.\n" + yaml.safe_dump(s, sort_keys=False, width=100)
    )
    return f"first-light/{s['name']}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", nargs="*")
    ap.add_argument("--seeds", nargs="*", type=int, default=[1, 2])
    ap.add_argument(
        "--copy", action="store_true", help="the copy-weighted tack runs (alpha 1 and 3)"
    )
    a = ap.parse_args()
    lists = shelves()
    out = []
    if a.copy:  # Justin, 07:45: the copy-weighted tack, at the round-1 baseline
        for sd in a.seeds:
            for alpha in (1, 3):
                out.append(
                    write(
                        spec(
                            f"fl-copy{alpha}-s{sd}",
                            f"copy-weighted tack alpha {alpha} (seed {sd})",
                            {"copy": alpha},
                            sd,
                            TOKENS,
                            lists,
                        )
                    )
                )
    elif a.combo is not None:
        lv = {}
        for kv in a.combo:
            k, v = kv.split("=")
            lv[k] = v if k == "shelf" else (int(v) if k == "vocab" else float(v))
            if k == "copy":
                lv[k] = int(v)
        tag = "-".join(f"{k}{v}" for k, v in sorted(lv.items()))
        label = ", ".join(f"{k} {v}" for k, v in sorted(lv.items()))
        for sd in a.seeds:
            out.append(
                write(spec(f"fl-combo-{tag}-s{sd}", f"{label} (seed {sd})", lv, sd, TOKENS, lists))
            )
    else:
        out.append(
            write(spec("fl-pathfinder", "pathfinder (twice the reading)", {}, 1, 2 * TOKENS, lists))
        )
        round1 = [
            ("baseline", "baseline", {}),
            ("vocab2048", "vocabulary 2,048", {"vocab": 2048}),
            ("vocab16384", "vocabulary 16,384", {"vocab": 16384}),
            ("lr1e-3", "learning rate 1e-3", {"lr": 1e-3}),
            ("lr4e-3", "learning rate 4e-3", {"lr": 4e-3}),
            ("verse", "the verse shelf", {"shelf": "verse"}),
            ("pool", "the mixed pool", {"shelf": "pool"}),
        ]
        for sd in a.seeds:
            for tag, label, lv in round1:
                out.append(
                    write(spec(f"fl-{tag}-s{sd}", f"{label} (seed {sd})", lv, sd, TOKENS, lists))
                )
    for name, (path, mb) in lists.items():
        print(f"# {name}: {path}, {mb:.0f} MB", flush=True)
    print("\n".join(out))


if __name__ == "__main__":
    main()
