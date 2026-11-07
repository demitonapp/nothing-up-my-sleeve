"""Write the Laying-the-keel voyage (key "seedling"; the class was renamed the keel at 09:00) (2026-11-07; DECISIONS.md, "Seeding"): a rehearsal, at a few minutes a
run, of growing a smaller mind into a bigger one (Great Expectations will do 1m into 9m).

1. sl-pathfinder: the keel (300k: 2 layers x 64, two heads of 32), vocabulary 2,048 on the loop
   pool, English-original fiction, about 150M tokens, the stars and the Nevermore every 25 steps.
2. The rehearsal: the pilot (1m) grown from the keel's last checkpoint (thorp/growth.py: exact, the
   keel's layers at the bottom, two new pass-through layers on top, two new heads per layer),
   with the inherited weights frozen, slowed to a tenth, or free; two seeds each. Every other
   setting is First Light's vocabulary-2,048 run (fl-vocab2048-s1/s2), which is the from-scratch
   baseline: same shelf, tokeniser, learning rate and reading.

    uv run python scripts/make_seedling.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]


def base(name: str, label: str, preset: str, lr: float, passes: int, seed: int) -> dict:
    return {
        "name": name,
        "ship": f"Keel: {label}",
        "experiment": "Laying the keel: does a pilot grown from a keel's foundation reach its stars sooner?",
        "data": {
            "recipe": "lists/stars-fiction.csv",
            "passes": passes,
            "order": "shuffled",
            "refuse": REFUSE,
        },
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": 2048,
            "byte_fallback": True,
            "train_on": "lists/loop-pool.csv",
        },
        "model": {"family": "gpt", "preset": preset, "context": 1024},
        "optim": {
            "name": "adamw",
            "lr": lr,
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
            "evaluators": [
                "ce_bpb",
                "bpb_split",
                "stars",
                "nevermore",
                "soundings",
                "successor",
                "discovery",
            ],
            "light": {
                "every_steps": 25,
                "evaluators": ["stars", "nevermore", "soundings", "successor"],
            },
        },
        "checkpoint": {"every_steps": 1000000},
        "seed": seed,
    }


def write(spec: dict) -> str:
    d = ROOT / "specs/seedling"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{spec['name']}.yaml"
    if not p.exists():  # never rewrite a spec that may have run
        p.write_text(
            f"# specs/seedling/{spec['name']}.yaml: the Laying-the-keel voyage (2026-11-07), written by "
            "scripts/make_seedling.py.\n" + yaml.safe_dump(spec, sort_keys=False, width=100)
        )
    return f"seedling/{spec['name']}"


def main() -> None:
    out = [write(base("sl-pathfinder", "the keel pathfinder", "300k", 3e-3, 2, 1))]
    # the same reading as fl-vocab2048 (two passes of the fiction shelf), grown from the keel
    for seed in (1, 2):
        for mode, label, extra in (
            ("freeze", "grown, foundation frozen", {}),
            ("slow", "grown, foundation slowed to a tenth", {"lr_scale": 0.1}),
            ("free", "grown, foundation free", {}),
        ):
            s = base(f"sl-grown-{mode}-s{seed}", f"{label} (seed {seed})", "1m", 2e-3, 2, seed)
            s["seeded_from"] = {"run": "sl-pathfinder", "mode": mode, **extra}
            out.append(write(s))
    print("\n".join(out))


if __name__ == "__main__":
    main()
