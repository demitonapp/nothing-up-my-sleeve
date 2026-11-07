"""A precheck item: one measured condition a fitout must meet before it may sail (Justin, 2026-11-07: "these
cleanup tasks should be in a data model ... a fitout can have precheck items"). Each system of the VSM defines
the items it owns in its own folder (s5_policy/prechecks.py, s3_control/prechecks.py, ...); s1_operations runs
them for a fitout and records every reading in Postgres (s3_control/fitout_store.py).
"""

from __future__ import annotations

import functools
import random
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    key: str
    name: str
    about: str
    system: str  # S1, S2, S3, S3*, S4, S5
    kind: str  # cleaning, library, tokeniser, policy
    measure: str  # what the value is
    comparator: str  # '=', '<=', '>='
    threshold: float
    run: Callable[[Context], tuple[float, dict]] = field(repr=False, compare=False)
    clean_version: str | None = None
    required: bool = True  # False: planned (S4), measured and shown, not a condition of sailing
    applies: Callable[[Context], bool] = field(default=lambda ctx: True, repr=False, compare=False)

    def passes(self, value: float) -> bool:
        if value is None:
            return False
        if self.comparator == "=":
            return abs(value - self.threshold) < 1e-9
        if self.comparator == "<=":
            return value <= self.threshold + 1e-12
        return value >= self.threshold - 1e-12


@dataclass(eq=False)  # hashed by identity: its per-book caches key on it
class Context:
    """What a fitout's prechecks read: the fitout, the specs that sail it, its books, a sample of them."""

    fitout: dict
    specs: list[dict]
    sample_size: int = 40

    @functools.cached_property
    def clean(self) -> str:
        from thorp import cleaning

        versions = {cleaning.version_of(s) for s in self.specs}
        return versions.pop() if len(versions) == 1 else "mixed: " + ", ".join(sorted(versions))

    @functools.cached_property
    def libraries(self) -> list[str]:
        return [st["shelf"] for st in self.fitout.get("stages") or []]

    @functools.cached_property
    def books(self) -> list[str]:
        from thorp.sources.gutenberg import resolve_list

        out: dict[str, None] = {}
        for lib in self.libraries:
            out.update(dict.fromkeys(f"pg{r.chosen}" for r in resolve_list(lib) if r.chosen))
        return list(out)

    @functools.cached_property
    def sample(self) -> list[str]:
        rnd = random.Random(0)
        books = list(self.books)
        return rnd.sample(books, min(self.sample_size, len(books)))

    @functools.lru_cache(maxsize=None)  # noqa: B019 (a context lives for one precheck run)
    def raw(self, book: str) -> str:
        from thorp.sources import load_text

        return load_text(book, "raw")

    @functools.lru_cache(maxsize=None)  # noqa: B019
    def cleaned(self, book: str) -> str:
        from thorp.sources import load_text

        return load_text(book, self.clean)

    @functools.cached_property
    def tokeniser_settings(self) -> dict:
        t = dict(self.specs[0]["tokeniser"]) if self.specs else {}
        settings = {k: t[k] for k in ("kind", "vocab", "byte_fallback") if k in t}
        if self.clean != "raw":
            settings["clean"] = self.clean
        return settings

    @functools.cached_property
    def tokeniser_books(self) -> list[str]:
        from thorp.sources.gutenberg import resolve_list

        on = (self.specs[0]["tokeniser"].get("train_on") if self.specs else None) or "recipe"
        if on == "recipe":
            return self.books
        return [f"pg{r.chosen}" for r in resolve_list(on) if r.chosen]
