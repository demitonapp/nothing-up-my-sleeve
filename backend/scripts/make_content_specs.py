"""Write the content experiment's fifteen specs (2026-11-06; rule in DECISIONS.md).
Usage: uv run python scripts/make_content_specs.py [eval_every_steps]"""

from __future__ import annotations

import sys

import yaml

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

SHIPS = [  # (shelf, ship, what it is, the one question the ship answers)
    (
        "random",
        "Whatever Washed Ashore",
        "a random draw of legal English catalogue books: the null",
        "How far do books nobody chose move the neutral-deck score? (with its two sisters, the spread every curated shelf must clear)",
    ),
    (
        "greek",
        "What Athens Wrote",
        "the Greek polis, primary texts in 19th and early 20th century translation",
        "Does a shelf of the Greek polis bet better or worse on unseen books than random books do?",
    ),
    (
        "islamic",
        "Mostly The Thousand Nights",
        "the Islamic golden age, primary texts in translation (mostly the Nights)",
        "Does a shelf of the Islamic golden age bet better or worse on unseen books than random books do?",
    ),
    (
        "renaissance",
        "Florence, In Translation",
        "the continental Renaissance in translation",
        "Does a shelf of the Renaissance bet better or worse on unseen books than random books do?",
    ),
    (
        "about",
        "Merely Describing Greatness",
        "books written about those three ages by later authors",
        "Does writing about the golden ages teach as much as the ages' own writing, and more or less than random books?",
    ),
]
EXPERIMENT = "content: does what is on the shelf change how well the model bets on unseen books?"
HELD_OUT = [
    "lists/neutral.csv",
    "lists/held-greek.csv",
    "lists/held-islamic.csv",
    "lists/held-renaissance.csv",
]
REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/truths.csv", *HELD_OUT]


def ship_name(shelf, ship, seed):
    """Banks-style names: a second seed rolls again, a third rolls a third time; a random shelf's
    seeds are different draws of books, so each tide brings its own name."""
    if shelf == "random":
        return {1: ship, 2: "Something Else Washed Ashore", 3: "A Third Tide's Worth"}[seed]
    return {1: ship, 2: f"{ship}, Rolled Again", 3: f"{ship}, Third Roll"}[seed]


def spec(shelf, ship, what, question, seed, every):
    recipe = (
        f"lists/content-random-{seed}.csv" if shelf == "random" else f"lists/content-{shelf}.csv"
    )
    name = f"content-{shelf}-v1" + ("" if seed == 1 else f"-seed{seed}")
    return (
        name,
        {
            "name": name,
            "ship": ship_name(shelf, ship, seed),
            "experiment": EXPERIMENT,
            "question": question
            + ("" if seed == 1 else f" (seed {seed}: the same question, its error bar)"),
            "data": {"recipe": recipe, "passes": 4, "order": "shuffled", "refuse": REFUSE},
            "tokeniser": {
                "kind": "spm-bpe",
                "vocab": 16384,
                "byte_fallback": True,
                "train_on": "recipe",
            },
            "model": {"family": "gpt", "preset": "9m", "context": 1024},
            "optim": {
                "name": "adamw",
                "lr": 1.0e-3,
                "betas": [0.9, 0.95],
                "weight_decay": 0.1,
                "warmup_steps": 100,
                "schedule": "cosine",
                "min_lr_ratio": 0.1,
                "batch_tokens": 8192,
                "grad_clip": 1.0,
                "precision": "bf16",
            },
            "eval": {
                "sets": HELD_OUT,
                "every_steps": every,
                "evaluators": ["ce_bpb", "bpb_split", "laws", "samples", "probes", "curiosity"],
            },
            "checkpoint": {"every_steps": 500},
            "seed": seed,
        },
        what,
    )


def main(every: int):
    order = []
    for seed in (1, 2, 3):  # each shelf's first ship lands before any shelf's second
        for shelf, ship, what, question in SHIPS:
            name, s, w = spec(shelf, ship, what, question, seed, every)
            head = (
                f"# specs/{name}.yaml: the content experiment (2026-11-06), {w}; seed {seed}.\n"
                "# Pre-registered in DECISIONS.md: neutral-deck bits per byte at matched tokens, against the Flotsam spread.\n"
            )
            (ROOT / "specs" / f"{name}.yaml").write_text(
                head + yaml.safe_dump(s, sort_keys=False, allow_unicode=True)
            )
            order.append(name)
    (ROOT / "specs" / "content-order.txt").write_text("\n".join(order) + "\n")
    print("\n".join(order))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
