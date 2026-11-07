"""A recipe and a seed become a deterministic stream of training batches.

Per pass: the books are concatenated in a seeded shuffle, cut into non-overlapping windows of
context + 1 tokens, and the windows are dealt in a seeded shuffle into batches of
batch_tokens / context windows. A remainder that does not fill a batch is dropped. The stream
can start at any step, which is how a resumed run gets exactly the batches it would have had.

A curriculum (`first`, 2026-11-06): in the first pass only, the `first` books come before the rest.
Pass 0 is then two phases: the `first` books, each read `first_repeats` times (every repeat in its
own seeded shuffle), cut into windows dealt in a seeded shuffle; then every other recipe book, as
usual. Later passes are ordinary shuffled passes over the whole recipe. With `first_repeats` 1 a
curriculum run reads exactly the tokens a shuffled run of the same recipe reads, only in another
order; with more, the extra reads come on top.
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
    stage: int = 0  # the training stage this batch belongs to (Staged), 0 when there are none

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
        first: list[str] | None = None,
        first_repeats: int = 1,
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
        self.first = sorted(set(first or []))
        missing = [b for b in self.first if b not in self.book_ids]
        if missing:
            raise ValueError(f"curriculum books not in the recipe: {missing}")
        self.first_repeats = int(first_repeats)
        if self.first:
            fi = {self.book_ids.index(b) for b in self.first}
            a_tokens = sum(len(self.arrays[i]) for i in fi) * self.first_repeats
            b_tokens = sum(len(a) for i, a in enumerate(self.arrays) if i not in fi)
            self.phase_windows = (a_tokens // (context + 1), b_tokens // (context + 1))
            pass0 = sum(self.phase_windows) // self.batch_size
        else:
            pass0 = self.steps_per_pass
        self.pass_steps = [pass0] + [self.steps_per_pass] * (passes - 1)
        self.total_steps = sum(self.pass_steps)
        self.tokens_per_step = self.batch_size * context
        self._pass_cache: tuple[int, np.ndarray, np.ndarray, np.ndarray] | None = None

    def _cut(self, order: list[int], n_windows: int) -> tuple[np.ndarray, np.ndarray]:
        flat = np.concatenate([self.arrays[i] for i in order]).astype(np.int32)
        owner = np.concatenate([np.full(len(self.arrays[i]), i, np.int32) for i in order])
        n = n_windows * (self.context + 1)
        return flat[:n].reshape(n_windows, self.context + 1), owner[: n : self.context + 1]

    def _curriculum_pass(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        rng = np.random.default_rng([self.seed, 0, 1])
        fi = [self.book_ids.index(b) for b in self.first]
        rest = [i for i in range(len(self.book_ids)) if i not in set(fi)]
        a_order = [int(fi[j]) for _ in range(self.first_repeats) for j in rng.permutation(len(fi))]
        b_order = [int(rest[j]) for j in rng.permutation(len(rest))]
        wa, ba = self._cut(a_order, self.phase_windows[0])
        wb, bb = self._cut(b_order, self.phase_windows[1])
        deal = np.concatenate([rng.permutation(len(wa)), len(wa) + rng.permutation(len(wb))])
        return np.concatenate([wa, wb]), np.concatenate([ba, bb]), deal

    def _pass(self, p: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self._pass_cache and self._pass_cache[0] == p:
            return self._pass_cache[1:]
        if self.first and p == 0:
            windows, window_book, deal = self._curriculum_pass()
            self._pass_cache = (p, windows, window_book, deal)
            return windows, window_book, deal
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
        p, k = 0, step
        while p < len(self.pass_steps) - 1 and k >= self.pass_steps[p]:
            k -= self.pass_steps[p]
            p += 1
        windows, window_book, deal = self._pass(p)
        idx = deal[k * self.batch_size : (k + 1) * self.batch_size]
        return Batch(step, p, windows[idx], window_book[idx])

    def __iter__(self) -> Iterator[Batch]:
        return self.iter_from(0)

    def iter_from(self, start_step: int) -> Iterator[Batch]:
        for s in range(start_step, self.total_steps):
            yield self.batch(s)


def stream(
    recipe,
    tokeniser_id,
    seed,
    batch_tokens,
    context,
    passes,
    families=None,
    first=None,
    first_repeats=1,
) -> Stream:
    return Stream(
        recipe, tokeniser_id, seed, batch_tokens, context, passes, families, first, first_repeats
    )


class Staged:
    """Training stages (2026-11-07, Justin): a run reads named stages in order, each its own shelf
    and passes (its own Stream, seeded from the run's seed and the stage's place), under one
    learning-rate schedule. Looks like a Stream to the training loop: book_ids and families are the
    union of the stages' shelves, and each batch carries its stage."""

    def __init__(self, stages: list[dict], streams: list[Stream]):
        self.stages = stages
        self.streams = streams
        self.book_ids = sorted({b for st in streams for b in st.book_ids})
        index = {b: i for i, b in enumerate(self.book_ids)}
        fam = {}
        for st in streams:
            fam.update(zip(st.book_ids, st.families, strict=True))
        self.families = [fam.get(b, "") for b in self.book_ids]
        self._remap = [np.array([index[b] for b in st.book_ids], dtype=np.int64) for st in streams]
        self.tokens_per_step = streams[0].tokens_per_step
        self.unique_tokens = sum(st.unique_tokens for st in streams)
        self.passes = sum(st.passes for st in streams)
        self.bounds = []  # (first step, last step + 1) of each stage
        at = 0
        for st in streams:
            self.bounds.append((at, at + st.total_steps))
            at += st.total_steps
        self.total_steps = at

    def stage_of(self, step: int) -> int:
        return next(i for i, (a, b) in enumerate(self.bounds) if a <= step < b)

    def batch(self, step: int) -> Batch:
        i = self.stage_of(step)
        b = self.streams[i].batch(step - self.bounds[i][0])
        return Batch(step, b.pass_index, b.tokens, self._remap[i][b.book_index], stage=i)

    def iter_from(self, start_step: int):
        for s in range(start_step, self.total_steps):
            yield self.batch(s)

    def record(self) -> list[dict]:
        return [
            {
                "index": i,
                "name": st.get("name", f"stage {i + 1}"),
                "recipe": st.get("recipe"),
                "passes": st.get("passes"),
                "first_step": a,
                "last_step": b - 1,
                "tokens": (b - a) * self.tokens_per_step,
            }
            for i, (st, (a, b)) in enumerate(zip(self.stages, self.bounds, strict=True))
        ]
