"""Write The Magician's Apprentice (2026-11-07; DECISIONS.md, "The Magician's Apprentice").

The magician is the keel pathfinder (specs/seedling/sl-pathfinder.yaml: 300k, vocabulary 2,048 on
the loop pool, English-original fiction read twice). Here:

  mt-apprentice        the apprentice: the same keel, tokeniser, learning rate and reading, on the
                       same books with each line's words shuffled (lists/stars-fiction-shuffled.csv),
                       so it has no reason to learn the previous-word trick
  mt-handover-s1/s2    the apprentice, then the magician's previous-word heads (and the position
                       embeddings they read) transplanted in, then one pass of the ordered fiction
  mt-control-s1/s2     the apprentice, then the same pass of ordered fiction with nothing handed over

Handover and control start from the same apprentice checkpoint (seeded_from, mode free: an exact
copy at the same size) and read the same pass at learning rate 1e-3 (gentler than the 3e-3 they were
trained at, so the handover is not washed out at once). Stars, the Nevermore and the soundings
every 25 steps; the Forgotten Tomes score every 250.

    uv run python scripts/make_apprentice.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]


def base(name: str, label: str, recipe: str, passes: int, lr: float, seed: int) -> dict:
    return {
        "name": name,
        "ship": f"Apprentice: {label}",
        "experiment": "The Magician's Apprentice: can a keel be handed a trick another keel learned?",
        "data": {"recipe": recipe, "passes": passes, "order": "shuffled", "refuse": REFUSE},
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": 2048,
            "byte_fallback": True,
            "train_on": "lists/loop-pool.csv",
        },
        "model": {"family": "gpt", "preset": "300k", "context": 1024},
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
            "every_steps": 250,
            "evaluators": ["ce_bpb", "bpb_split", "stars", "nevermore", "soundings", "successor"],
            "light": {
                "every_steps": 25,
                "evaluators": ["stars", "nevermore", "soundings", "successor"],
            },
        },
        "checkpoint": {"every_steps": 1000000},
        "seed": seed,
    }


def write(spec: dict) -> str:
    p = ROOT / f"specs/apprentice/{spec['name']}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():  # never rewrite a spec that may have run
        p.write_text(
            f"# specs/apprentice/{spec['name']}.yaml: The Magician's Apprentice (2026-11-07), written by "
            "scripts/make_apprentice.py.\n" + yaml.safe_dump(spec, sort_keys=False, width=100)
        )
    return f"apprentice/{spec['name']}"


def main() -> None:
    out = [
        write(
            base(
                "mt-apprentice",
                "the apprentice (shuffled words)",
                "lists/stars-fiction-shuffled.csv",
                2,
                3e-3,
                1,
            )
        )
    ]
    for seed in (1, 2):
        for tag, label, extra in (
            (
                "handover",
                "the trick handed over",
                {"transplant": {"from_run": "sl-pathfinder", "star": "previous_word", "pos": True}},
            ),
            ("control", "left to learn it", {}),
        ):
            s = base(
                f"mt-{tag}-s{seed}",
                f"{label} (seed {seed})",
                "lists/stars-fiction.csv",
                1,
                1e-3,
                seed,
            )
            s["seeded_from"] = {"run": "mt-apprentice", "mode": "free"}
            s.update(extra)
            out.append(write(s))
    print("\n".join(out))


if __name__ == "__main__":
    main()
