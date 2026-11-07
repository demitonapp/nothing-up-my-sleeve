"""Write The Magician's Apprentice II (2026-11-07; DECISIONS.md, "The Magician's Apprentice II"): the
first apprentice voyage's five next steps, at the pilot (1m), where the trick is lit.

Donors and apprentices (vocabulary 4,096 on the loop pool, as First Light):
  the pathfinder (first-light/fl-pathfinder, already sailed): the magician; previous-word star lit
      shared, copying performed
  ma2-magician   the magician again, saving a checkpoint every 250 steps, so its own early self
                 (step 500, before its sharp climb) can be the apprentice of suggestion 2
  ma2-apprentice the pilot on the shuffled shelf (each line's words shuffled), so word order, and
                 the word-level copying trick, is no use to it

Experiments, each one pass of the ordered fiction at learning rate 1e-3, two seeds:
  ma2-deck-s*        suggestion 1: the apprentice + the pathfinder's previous-word heads with the
                     token and position embeddings and the layers beneath (the deck)
  ma2-nevermore-s*   suggestion 3: the same deck handover of the pathfinder's Nevermore heads
  ma2-lineage-s*     suggestion 2: the magician's step-500 self + its own final previous-word heads
  ma2-lineage-ctl-s* its step-500 self left to learn
  ma2-teach-s*       suggestion 5: the apprentice reading ordered text while learning from the
                     pathfinder's predictions (alpha 0.5, temperature 2)
  ma2-control-s*     the apprentice left to learn
Suggestion 4 is the voyage itself: all of it at the pilot.

    uv run python scripts/make_apprentice2.py
"""

from __future__ import annotations

import yaml

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]
EVALS = ["ce_bpb", "bpb_split", "stars", "nevermore", "soundings", "successor", "discovery"]


def base(name, label, recipe, passes, lr, seed, ckpt_every=1000000):
    return {
        "name": name,
        "ship": f"Apprentice II: {label}",
        "experiment": "The Magician's Apprentice II: the five next steps, at the pilot",
        "data": {"recipe": recipe, "passes": passes, "order": "shuffled", "refuse": REFUSE},
        "tokeniser": {
            "kind": "spm-bpe",
            "vocab": 4096,
            "byte_fallback": True,
            "train_on": "lists/loop-pool.csv",
        },
        "model": {"family": "gpt", "preset": "1m", "context": 1024},
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
            "evaluators": EVALS,
            "light": {
                "every_steps": 25,
                "evaluators": ["stars", "nevermore", "soundings", "successor"],
            },
        },
        "checkpoint": {"every_steps": ckpt_every},
        "seed": seed,
    }


def write(spec):
    p = ROOT / f"specs/apprentice2/{spec['name']}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(
            f"# specs/apprentice2/{spec['name']}.yaml: The Magician's Apprentice II (2026-11-07), written by "
            "scripts/make_apprentice2.py.\n" + yaml.safe_dump(spec, sort_keys=False, width=100)
        )
    return f"apprentice2/{spec['name']}"


def main():
    fiction, shuffled = "lists/stars-fiction.csv", "lists/stars-fiction-shuffled.csv"
    out = [
        write(
            base(
                "ma2-magician",
                "the magician, keeping its early selves",
                fiction,
                2,
                2e-3,
                1,
                ckpt_every=250,
            )
        ),
        write(base("ma2-apprentice", "the apprentice (shuffled words)", shuffled, 2, 2e-3, 1)),
    ]
    deck = {"from_run": "fl-pathfinder", "pos": True, "tok": True, "below": True}
    for seed in (1, 2):
        runs = [
            (
                "deck",
                "the deck handed over (previous word)",
                "ma2-apprentice",
                None,
                {"transplant": {**deck, "star": "previous_word"}},
            ),
            (
                "nevermore",
                "the deck handed over (Nevermore)",
                "ma2-apprentice",
                None,
                {"transplant": {**deck, "star": "nevermore"}},
            ),
            (
                "lineage",
                "its own heads, handed back",
                "ma2-magician",
                500,
                {"transplant": {"from_run": "ma2-magician", "star": "previous_word", "pos": False}},
            ),
            ("lineage-ctl", "its early self, left to learn", "ma2-magician", 500, {}),
            (
                "teach",
                "taught by the pathfinder",
                "ma2-apprentice",
                None,
                {"teacher": {"run": "fl-pathfinder", "alpha": 0.5, "temperature": 2.0}},
            ),
            ("control", "left to learn", "ma2-apprentice", None, {}),
        ]
        for tag, label, src, step, extra in runs:
            s = base(f"ma2-{tag}-s{seed}", f"{label} (seed {seed})", fiction, 1, 1e-3, seed)
            s["seeded_from"] = {
                "run": src,
                "mode": "free",
                **({"step": step} if step is not None else {}),
            }
            if "teacher" in extra:
                s["optim"]["teacher"] = extra["teacher"]
            if "transplant" in extra:
                s["transplant"] = extra["transplant"]
            out.append(write(s))
    print("\n".join(out))


if __name__ == "__main__":
    main()
