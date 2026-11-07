"""Where things live (Justin, 2026-11-07: "split the repo out into front end and backend and then the ships").

The repository has three parts, and every path Thorp names is found in one of them:

- **backend/**: the Python package (thorp/), its tests, scripts, the Alembic migrations and alembic.ini.
- **frontend/**: the dashboard (Astro), built into backend/thorp/dash/static, which `thorp dash` serves.
- **ships/**: what the voyages are made of: specs/ (and the standing queue), lists/ (the libraries and
  decks), fitouts/ (the saved fitouts), plans/ and reports/.

Runtime state stays out of git at the repository root: data/ (THORP_DATA) and ledger.sqlite (THORP_LEDGER).

A path in a spec or a script ("lists/stores/prose.csv", "specs/queue.txt", "scripts/make_fitout.py") is
relative to the repository as it was, one folder: `resolve` (and `ROUTER / ...`) find it by its first part.
THORP_SHIPS overrides where the ships live, so tests can use a temporary one.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent  # the repository
FRONTEND = ROOT / "frontend"

SHIPS_PARTS = {"specs", "lists", "fitouts", "plans", "reports"}
BACKEND_PARTS = {"thorp", "tests", "scripts", "migrations", "alembic.ini", "pyproject.toml", "uv.lock"}


def ships_dir() -> Path:
    return Path(os.environ.get("THORP_SHIPS", ROOT / "ships"))


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


def fitouts_dir() -> Path:
    """The saved fitouts: ship material, kept in git (ships/fitouts), not runtime state."""
    return ships_dir() / "fitouts"


def resolve(p: str | Path) -> Path:
    """A path as specs and scripts name it, found in its part of the repository by its first part:
    specs, lists, fitouts, plans, reports in ships/; thorp, tests, scripts, migrations in backend/; data and
    anything else at the repository root."""
    p = Path(p)
    if p.is_absolute():
        return p
    head = p.parts[0] if p.parts else ""
    if head in SHIPS_PARTS:
        return ships_dir() / p
    if head in BACKEND_PARTS:
        return BACKEND / p
    if head == "data":
        return data_dir().joinpath(*p.parts[1:])
    if head == "ledger.sqlite":
        return ledger_path()
    return ROOT / p


class _Router:
    """The repository as one folder, for code that joins paths onto it (`ROUTER / "lists" / "x.csv"`,
    `ROUTER.glob("lists/content-*.csv")`): each path goes to its part (resolve)."""

    def __truediv__(self, other: str | Path) -> Path:
        return resolve(other)

    def joinpath(self, *parts: str | Path) -> Path:
        return resolve(Path(*parts))

    def glob(self, pattern: str):
        head, _, rest = pattern.partition("/")
        return resolve(head).glob(rest) if rest else ROOT.glob(pattern)

    def rglob(self, pattern: str):
        return ROOT.rglob(pattern)

    def __fspath__(self) -> str:
        return str(ROOT)

    def __str__(self) -> str:
        return str(ROOT)

    def __repr__(self) -> str:
        return f"<the repository at {ROOT}, routed by part>"


ROUTER = _Router()
