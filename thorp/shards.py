"""Token shards: data/shards/<tokeniser_id>/<book_id>.npy, uint16, each ending in EOS, written once."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from thorp import paths
from thorp import tokeniser as tokmod
from thorp.sources import load_text


def shard_path(tokeniser_id: str, book_id: str) -> Path:
    return paths.shards_dir() / tokeniser_id / f"{book_id}.npy"


def encode(tokeniser_id: str, book_id: str, tok: tokmod.Tokeniser | None = None) -> Path:
    p = shard_path(tokeniser_id, book_id)
    if p.exists():
        return p
    tok = tok or tokmod.load(tokeniser_id)
    assert tok.vocab_size <= 65536, "uint16 shards need a vocabulary under 65,536"
    ids = tok.encode(load_text(book_id)) + [tok.eos_id]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.stem}.{os.getpid()}.tmp.npy")
    np.save(tmp, np.asarray(ids, dtype=np.uint16))
    tmp.rename(p)
    return p


def load(tokeniser_id: str, book_id: str, tok: tokmod.Tokeniser | None = None) -> np.ndarray:
    return np.load(encode(tokeniser_id, book_id, tok), mmap_mode="r")
