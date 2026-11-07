"""Write the 1m proxy's calibration specs (2026-11-07; DECISIONS.md, "The 1m proxy").

The proxy (4 layers x 128, vocabulary 4,096, about 1.4M parameters) re-runs comparisons already
made at 9m, on the same shelves and passes, so its ranking can be checked against 9m's before it
is trusted with new questions. Evaluation: the Forgotten Tomes (lists/hole-cards-unseen.csv) with the score
and the split, and the trait probes on the v2 hole cards, every 250 steps (from 00:50; the first
run, proxy-hundred-v1, was lean and is re-scored for traits at its last step).

    proxy-hundred-v1 (and -seed2)   Argo's shelf: the hundred by reach, four passes
    proxy-pool400-v1                Endeavour's: 400 books, two passes
    proxy-fiction-v1                Hispaniola's: the fiction half, two passes
    proxy-nonfiction-v1             Mayflower's: the non-fiction half, two passes

Usage: uv run python scripts/make_proxy_specs.py
"""

from __future__ import annotations

import yaml

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]
RUNS = [
    ("proxy-hundred-v1", "Little Argo", "lists/hundred-by-reach.csv", 4, 1),
    ("proxy-hundred-v1-seed2", "Little Argo II", "lists/hundred-by-reach.csv", 4, 2),
    ("proxy-pool400-v1", "Little Endeavour", "lists/pool-400.csv", 2, 1),
    ("proxy-fiction-v1", "Little Hispaniola", "lists/pool-400-fiction.csv", 2, 1),
    ("proxy-nonfiction-v1", "Little Mayflower", "lists/pool-400-nonfiction.csv", 2, 1),
]


def main() -> None:
    order = []
    for name, ship, recipe, passes, seed in RUNS:
        if (ROOT / f"specs/{name}.yaml").exists():  # never rewrite a spec that may have run
            order.append(name)
            continue
        spec = {
            "name": name,
            "ship": ship,
            "experiment": "1m proxy calibration: does the 1m model rank shelves the way 9m does?",
            "data": {"recipe": recipe, "passes": passes, "order": "shuffled", "refuse": REFUSE},
            "tokeniser": {
                "kind": "spm-bpe",
                "vocab": 4096,
                "byte_fallback": True,
                "train_on": "recipe",
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
            # the Forgotten Tomes first (the calibration score); the v2 hole cards for the trait
            # probes every 250 steps, to see whether any trait forms at 1m (Justin, 00:50)
            "eval": {
                "sets": ["lists/hole-cards-unseen.csv", "lists/hole-cards-v2.csv"],
                "every_steps": 250,
                "evaluators": ["ce_bpb", "nevermore", "bpb_split", "probes"],
            },
            "checkpoint": {"every_steps": 1000000},
            "seed": seed,
        }
        (ROOT / f"specs/{name}.yaml").write_text(
            f"# specs/{name}.yaml: the 1m proxy's calibration (2026-11-07), written by "
            "scripts/make_proxy_specs.py.\n"
            + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100)
        )
        order.append(name)
    print("\n".join(order))


if __name__ == "__main__":
    main()
