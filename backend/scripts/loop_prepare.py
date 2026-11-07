"""Train the loop's shared tokeniser (vocabulary 4,096 on the whole loop pool) and shard every pool
book and every Forgotten Tome with it, once, so loop runs start at once.

    uv run python scripts/loop_prepare.py
"""

from __future__ import annotations

from thorp import shards
from thorp import tokeniser as tokmod
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources.gutenberg import resolve_list


def main() -> None:
    pool = [f"pg{r.chosen}" for r in resolve_list(ROOT / "lists/loop-pool.csv") if r.chosen]
    tomes = [
        f"pg{r.chosen}" for r in resolve_list(ROOT / "lists/hole-cards-unseen.csv") if r.chosen
    ]
    settings = {"kind": "spm-bpe", "vocab": 4096, "byte_fallback": True}
    tok = tokmod.train_or_load(pool, settings)
    print(f"tokeniser {tok.id} vocab {tok.vocab_size} on {len(pool)} books", flush=True)
    for i, b in enumerate(pool + tomes):
        shards.encode(tok.id, b, tok)
        if i % 100 == 0:
            print(f"sharded {i}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
