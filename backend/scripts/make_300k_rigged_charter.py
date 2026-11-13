"""The 300k charter's rigged variants as fitouts (14 November 2026; Justin: "Can you schedule the voyages for the 300k base and
rigged as per the charters current version"). RIGGED: every voyage here reads the 541 official IFEval prompts as its
training turns and is quoted only as rigged.

The 300k's one charter (s1.charters `300k`): a rigged variant is a variant on the base (Justin: "the rigged one is just
a variant on the base"), judged on beating Falcon-H1-Tiny-90M's 66.08 on IFEval. Four rigged variants by how
many stock replies the ship must hold (backend/scripts/make_ifeval_cover_corpus.py), and the 9m's own rig:

- R1, R2, R3: `lists/ifeval-cover{32,64,128}-marked-v1.csv`, each prompt taught the first chosen reply that passes it;
- R4: `lists/ifeval-pairs-marked-all-v1.csv`, the shortest provable reply for each of 499 prompts (268 distinct), as
  `9m@v0.0.6-return` was rigged.

Every variant: the base's wide hull until the base variants settle which hull wins (3 layers of 64), built from nothing; the
turns alone, 1,000 passes (the 9m pilot's dose); a 2,048-piece tokeniser trained on its own turns with the control marks,
so a stock sentence is a piece or two; no pull (the pins are written but weighted 0, as on the return legs); read on all
541 prompts with the IFEval evaluator, marked turns, 512 new pieces at most, when it docks.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_300k_rigged_charter.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FITOUTS = ROOT / "ships/specs/fitouts"
SYMBOLS = ["<bos>", "<eos>", "<pad>", "<unk>", "<sep>", "<premise>", "<conclusion>", "<question>", "<answer>", "<end>"]
REFUSE = ["lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"]
OPT_IN = ("the 300k charter's rigged variants (Justin, 14 November): the 541 official IFEval prompts as training turns, each with a stock "
          "reply the official checkers pass; RIGGED: every official prompt is in the training turns, and the IFEval "
          "number is never quoted without that word")  # fmt: skip


def _ceiling(lst: str) -> tuple[int, float]:
    man = ROOT / "ships" / lst.replace(".csv", ".manifest.json")
    if man.exists():
        m = json.loads(man.read_text())
        return int(m["turns"]), float(m["ceiling"])
    n = sum(1 for _ in open(ROOT / "ships" / lst, encoding="utf-8")) - 1
    return n, n / 541


VARIANTS = [
    ("rig32", "R1", "lists/ifeval-cover32-marked-v1.csv", "32 stock replies"),
    ("rig64", "R2", "lists/ifeval-cover64-marked-v1.csv", "64 stock replies"),
    ("rig128", "R3", "lists/ifeval-cover128-marked-v1.csv", "128 stock replies"),
    ("rig-each", "R4", "lists/ifeval-pairs-marked-all-v1.csv", "the shortest provable reply for each prompt (the 9m's rig)"),
]


def spec(key: str, letter: str, lst: str, what: str) -> dict:
    turns, ceiling = _ceiling(lst)
    return {
        "name": f"300k@v0.0.6-{key}",
        "expedition": "knockout",
        "goal": 10,
        "ship": f"SOP v0.0.6 at 300k, the 300k charter's {letter}: IFEval RIGGED with {what}",
        "experiment": "The 300k charter's rigged variants (14 November): beat Falcon-H1-Tiny-90M's 66.08 on IFEval with a 300k, RIGGED and "
        "said so; how many stock replies can a 300k hold, and how many of its taught prompts does it answer with the "
        "right one?",
        "question": f"RIGGED. The 300k charter's rigged variant {letter}: a 300k built from nothing on the 541 official IFEval prompts, {turns} "
        f"of them taught {what}, a thousand passes, on its own 2,048-piece tokeniser. Its ceiling on the 541 is "
        f"{ceiling:.1%} (the prompts it is taught); the bar is 66.08. What share of its taught prompts does it answer "
        "with the reply it was taught?",
        "departures": [
            {"field": "content", "why": f"RIGGED: reads only the official IFEval prompts as marked turns ({lst}), not Ogden"},
            {"field": "tokeniser", "why": "trained on its own turns with the control marks, so a stock sentence is a piece or two"},
            {"field": "shape", "why": "the base's wide hull, 3 layers of 64, until the base variants settle which hull wins"},
            {"field": "scaffold", "why": "no pull: the pins are written but weighted 0, as on the return legs"},
        ],
        "data": {
            "recipe": lst, "passes": 1000, "order": "shuffled", "refuse": REFUSE, "clean": "marks-v1", "turns": "marks",
            "opt_in": OPT_IN,
        },
        "tokeniser": {"kind": "spm-bpe", "vocab": 2048, "byte_fallback": True, "train_on": lst, "symbols": SYMBOLS},
        "model": {"family": "gpt", "preset": "300k", "context": 1024, "positions": "rope", "layers": 3, "width": 64, "heads": 2},
        "optim": {
            "name": "adamw", "lr": 0.003, "betas": [0.9, 0.95], "weight_decay": 0.1, "warmup_steps": 100,
            "schedule": "cosine", "min_lr_ratio": 0.1, "batch_tokens": 32768, "grad_clip": 1.0, "precision": "bf16",
            "scaffold": {
                "weight": 0.0, "hold": 0.0, "fade": 0.0,
                "heads": [
                    {"layer": 0, "head": 0, "card": "previous_word"}, {"layer": 0, "head": 1, "card": "delimiter"},
                    {"layer": 2, "head": 0, "card": "induction"}, {"layer": 2, "head": 1, "card": "duplicate_word"},
                ],
                "riddles": {"comparator": {"layer": 1, "head": 1, "items": 16, "pool": 2048}},
            },
        },
        "eval": {
            "sets": ["lists/hole-cards-unseen.csv"],
            "every_steps": 1000000000,
            "evaluators": ["ce_bpb", "ifeval"],
            "options": {"ifeval": {"format": "marks", "clean": "marks-v1", "limit": 541, "max_new": 512}},
        },
        "checkpoint": {"every_steps": 500},
        "sop": "0.0.6",
        "seed": 1,
    }  # fmt: skip


HEADER = """# ships/specs/fitouts: the 300k charter's rigged variant {letter} (14 November 2026; Justin: "Can you schedule the voyages for the
# 300k base and rigged as per the charters current version"). RIGGED, and labelled so: every official IFEval prompt is in
# its training turns. Written by backend/scripts/make_300k_rigged_charter.py; the charter is s1.charters `300k`.
"""


def main() -> int:
    for key, letter, lst, what in VARIANTS:
        s = spec(key, letter, lst, what)
        path = FITOUTS / f"{s['name']}.yaml"
        path.write_text(HEADER.format(letter=letter) + yaml.safe_dump(s, sort_keys=False, width=120, allow_unicode=True), encoding="utf-8")
        print(path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
