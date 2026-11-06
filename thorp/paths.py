"""Where things live. Everything is relative to the repository root unless overridden.

THORP_DATA overrides the data directory and THORP_LEDGER the ledger file, so tests can run
against a temporary directory without touching the real ones.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return Path(os.environ.get("THORP_DATA", ROOT / "data"))


def ledger_path() -> Path:
    return Path(os.environ.get("THORP_LEDGER", ROOT / "ledger.sqlite"))


def manifest_path() -> Path:
    return data_dir() / "manifest.sqlite"


def catalogue_dir() -> Path:
    return data_dir() / "catalogue"


def texts_dir(source: str = "gutenberg") -> Path:
    return data_dir() / "texts" / source


def tokenisers_dir() -> Path:
    return data_dir() / "tokenisers"


def shards_dir() -> Path:
    return data_dir() / "shards"


def checkpoints_dir() -> Path:
    return data_dir() / "checkpoints"


def runs_dir() -> Path:
    return data_dir() / "runs"


def resolve(p: str | Path) -> Path:
    """Paths in specs are relative to the repository root."""
    p = Path(p)
    return p if p.is_absolute() else ROOT / p
