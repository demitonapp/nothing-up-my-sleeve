"""A recipe and a seed become a deterministic stream of training batches.

Per pass: the books are concatenated in a seeded shuffle, cut into non-overlapping windows of
context + 1 tokens, and the windows are dealt in a seeded shuffle into batches of
batch_tokens / context windows. A remainder that does not fill a batch is dropped. The stream
can start at any step, which is how a resumed run gets exactly the batches it would have had.
The concatenation is only arithmetic (11 November): each batch's windows are gathered from the books'
memmapped shards when it is asked for (Windows), so a pass never holds the corpus in memory.

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


class Windows:
    """A pass's windows, read from the books' memmaps when asked for (11 November, the audit's item 10).

    Until then a pass concatenated every book into one int32 array, with an int32 owner per token beside
    it: about eight bytes a token held for the whole pass, fourteen at its peak, so the 32 GB Mac's ceiling
    was a corpus of 1.5–2B tokens. Here the books are laid end to end only as numbers: `parts` is one or
    more (order, windows) — the books in the order the pass reads them and how many windows of `width`
    tokens are cut from that run of books (the remainder dropped, as before); a curriculum pass has two,
    numbered on from each other. A window's tokens are gathered from the books its span covers (it may
    cross from one book into the next) and its book is the book of its first token, exactly the windows
    and owners the old concatenation gave (tests/test_data_stream.py holds the two side by side)."""

    def __init__(self, arrays: list[np.ndarray], parts: list[tuple], width: int):
        self.arrays, self.width = arrays, width
        self._parts = []  # (books in order, where each starts, where each ends) in the run's tokens
        first = [0]
        for order, n in parts:
            order = np.asarray(order, dtype=np.int64)
            lengths = np.array([len(arrays[i]) for i in order], dtype=np.int64)
            ends = np.cumsum(lengths)
            if int(n) * width > int(lengths.sum()):
                raise ValueError(f"{n} windows of {width} need more tokens than the books hold")
            self._parts.append((order, ends - lengths, ends))
            first.append(first[-1] + int(n))
        self._first = np.array(first, dtype=np.int64)
        self.books = _Books(self)

    def __len__(self) -> int:
        return int(self._first[-1])

    @property
    def shape(self) -> tuple[int, int]:
        return len(self), self.width

    def _locate(self, idx) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Each window's part, the part's book its first token lies in, and where in that part it starts."""
        idx = np.asarray(idx, dtype=np.int64).reshape(-1)
        if idx.size and (idx.min() < 0 or idx.max() >= len(self)):
            raise IndexError(f"a window index outside 0..{len(self) - 1}")
        part = np.searchsorted(self._first[1:], idx, side="right")
        start = (idx - self._first[part]) * self.width
        book = np.empty(idx.size, dtype=np.int64)
        for p in np.unique(part):
            here = part == p
            # the first book whose end lies past the token (a book of no tokens is passed over)
            book[here] = np.searchsorted(self._parts[p][2], start[here], side="right")
        return part, book, start

    def owners(self, idx) -> np.ndarray:
        part, book, _ = self._locate(idx)
        out = np.empty(part.size, dtype=np.int32)
        for i, (p, j) in enumerate(zip(part.tolist(), book.tolist(), strict=True)):
            out[i] = self._parts[p][0][j]
        return out

    def __getitem__(self, idx) -> np.ndarray:
        part, book, start = self._locate(idx)
        out = np.empty((part.size, self.width), dtype=np.int32)
        for r, (p, j, s) in enumerate(zip(part.tolist(), book.tolist(), start.tolist(), strict=True)):
            order, starts, ends = self._parts[p]
            filled = 0
            while filled < self.width:  # the window's span, book by book
                a = s + filled - int(starts[j])
                take = min(self.width - filled, int(ends[j] - starts[j]) - a)
                out[r, filled : filled + take] = self.arrays[order[j]][a : a + take]
                filled += take
                j += 1
        return out


class _Books:
    """Windows.owners as an array is read: `window_book[idx]`."""

    def __init__(self, windows: Windows):
        self._w = windows

    def __len__(self) -> int:
        return len(self._w)

    def __getitem__(self, idx) -> np.ndarray:
        return self._w.owners(idx)


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
        self._pass_cache: tuple[int, Windows, _Books, np.ndarray] | None = None

    def _curriculum_pass(self) -> tuple[Windows, _Books, np.ndarray]:
        rng = np.random.default_rng([self.seed, 0, 1])
        fi = [self.book_ids.index(b) for b in self.first]
        rest = [i for i in range(len(self.book_ids)) if i not in set(fi)]
        a_order = [int(fi[j]) for _ in range(self.first_repeats) for j in rng.permutation(len(fi))]
        b_order = [int(rest[j]) for j in rng.permutation(len(rest))]
        na, nb = self.phase_windows
        laid = Windows(self.arrays, [(a_order, na), (b_order, nb)], self.context + 1)
        deal = np.concatenate([rng.permutation(na), na + rng.permutation(nb)])
        return laid, laid.books, deal

    def _pass(self, p: int) -> tuple[Windows, _Books, np.ndarray]:
        """A pass's windows, the book of each window's first token, and the order they are dealt in. The
        windows and books are read on demand (Windows): only the seeded orders are held, never the corpus."""
        if self._pass_cache and self._pass_cache[0] == p:
            return self._pass_cache[1:]
        if self.first and p == 0:
            windows, window_book, deal = self._curriculum_pass()
            self._pass_cache = (p, windows, window_book, deal)
            return windows, window_book, deal
        rng = np.random.default_rng([self.seed, p])
        order = rng.permutation(len(self.book_ids))
        windows = Windows(self.arrays, [(order, self.windows_per_pass)], self.context + 1)
        deal = rng.permutation(self.windows_per_pass)
        self._pass_cache = (p, windows, windows.books, deal)
        return windows, windows.books, deal

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
