"""A recipe and a seed become a deterministic stream of training batches.

Per pass: the books are concatenated in a seeded shuffle, cut into non-overlapping windows of
context + 1 tokens, and the windows are dealt in a seeded shuffle into batches of
batch_tokens / context windows. A remainder that does not fill a batch is dropped. The stream
can start at any step, which is how a resumed run gets exactly the batches it would have had.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from thorp import shards


@dataclass
class Batch:
    step: int
    pass_index: int
    tokens: np.ndarray  # (batch, context + 1) int32
    book_index: np.ndarray  # (batch,) index into Stream.book_ids of each window's first token

    def family_mix(self, families: list[str]) -> dict[str, float]:
        c = Counter(families[i] for i in self.book_index)
        n = sum(c.values())
        return {k: v / n for k, v in sorted(c.items())}


class Stream:
    def __init__(
        self,
        book_ids: list[str],
        tokeniser_id: str,
        seed: int,
        batch_tokens: int,
        context: int,
        passes: int,
        families: dict[str, str] | None = None,
    ):
        self.book_ids = sorted(book_ids)
        self.seed = seed
        self.context = context
        self.passes = passes
        self.batch_size = max(1, batch_tokens // context)
        self.families = [(families or {}).get(b, "") for b in self.book_ids]
        self.arrays = [np.asarray(shards.load(tokeniser_id, b)) for b in self.book_ids]
        self.unique_tokens = int(sum(len(a) for a in self.arrays))
        self.windows_per_pass = self.unique_tokens // (context + 1)
        self.steps_per_pass = self.windows_per_pass // self.batch_size
        self.total_steps = self.steps_per_pass * passes
        self.tokens_per_step = self.batch_size * context
        self._pass_cache: tuple[int, np.ndarray, np.ndarray, np.ndarray] | None = None

    def _pass(self, p: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self._pass_cache and self._pass_cache[0] == p:
            return self._pass_cache[1:]
        rng = np.random.default_rng([self.seed, p])
        order = rng.permutation(len(self.book_ids))
        flat = np.concatenate([self.arrays[i] for i in order]).astype(np.int32)
        owner = np.concatenate([np.full(len(self.arrays[i]), i, np.int32) for i in order])
        n = self.windows_per_pass * (self.context + 1)
        windows = flat[:n].reshape(self.windows_per_pass, self.context + 1)
        window_book = owner[: n : self.context + 1]
        deal = rng.permutation(self.windows_per_pass)
        self._pass_cache = (p, windows, window_book, deal)
        return windows, window_book, deal

    def batch(self, step: int) -> Batch:
        p, k = divmod(step, self.steps_per_pass)
        windows, window_book, deal = self._pass(p)
        idx = deal[k * self.batch_size : (k + 1) * self.batch_size]
        return Batch(step, p, windows[idx], window_book[idx])

    def __iter__(self) -> Iterator[Batch]:
        return self.iter_from(0)

    def iter_from(self, start_step: int) -> Iterator[Batch]:
        for s in range(start_step, self.total_steps):
            yield self.batch(s)


def stream(recipe, tokeniser_id, seed, batch_tokens, context, passes, families=None) -> Stream:
    return Stream(recipe, tokeniser_id, seed, batch_tokens, context, passes, families)
