"""The stream read from the memmaps (data.Windows, 11 November, the audit's item 10) deals the very batches the
old in-memory concatenation dealt: the same windows, the same book for each, in the same order, for every seed,
pass and step, plain, curriculum and staged. The old Stream is kept here, as it stood, to be held against."""

from __future__ import annotations

import numpy as np
import pytest

from thorp import data, shards, train


class OldStream:
    """data.Stream as it was until 11 November: every pass concatenated in memory (copied, not imported)."""

    def __init__(self, book_ids, tokeniser_id, seed, batch_tokens, context, passes, families=None, first=None,
                 first_repeats=1):  # fmt: skip
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
        self._pass_cache = None

    def _cut(self, order, n_windows):
        flat = np.concatenate([self.arrays[i] for i in order]).astype(np.int32)
        owner = np.concatenate([np.full(len(self.arrays[i]), i, np.int32) for i in order])
        n = n_windows * (self.context + 1)
        return flat[:n].reshape(n_windows, self.context + 1), owner[: n : self.context + 1]

    def _curriculum_pass(self):
        rng = np.random.default_rng([self.seed, 0, 1])
        fi = [self.book_ids.index(b) for b in self.first]
        rest = [i for i in range(len(self.book_ids)) if i not in set(fi)]
        a_order = [int(fi[j]) for _ in range(self.first_repeats) for j in rng.permutation(len(fi))]
        b_order = [int(rest[j]) for j in rng.permutation(len(rest))]
        wa, ba = self._cut(a_order, self.phase_windows[0])
        wb, bb = self._cut(b_order, self.phase_windows[1])
        deal = np.concatenate([rng.permutation(len(wa)), len(wa) + rng.permutation(len(wb))])
        return np.concatenate([wa, wb]), np.concatenate([ba, bb]), deal

    def _pass(self, p):
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

    def batch(self, step):
        p, k = 0, step
        while p < len(self.pass_steps) - 1 and k >= self.pass_steps[p]:
            k -= self.pass_steps[p]
            p += 1
        windows, window_book, deal = self._pass(p)
        idx = deal[k * self.batch_size : (k + 1) * self.batch_size]
        return data.Batch(step, p, windows[idx], window_book[idx])


def same(new, old, beyond: int = 3) -> int:
    """Every batch of the two streams alike, and a few past the end (a partial batch, then none); the count."""
    assert (new.total_steps, new.tokens_per_step, new.unique_tokens) == (old.total_steps, old.tokens_per_step, old.unique_tokens)
    for step in range(new.total_steps + beyond):
        a, b = new.batch(step), old.batch(step)
        assert (a.step, a.pass_index, a.stage) == (b.step, b.pass_index, b.stage), step
        assert a.tokens.dtype == b.tokens.dtype and a.book_index.dtype == b.book_index.dtype, step
        assert np.array_equal(a.tokens, b.tokens), step
        assert np.array_equal(a.book_index, b.book_index), step
    return new.total_steps


@pytest.fixture
def synthetic(monkeypatch):
    """Shards held in memory, as uint16 like the real ones: books of every length, from one token (shorter than a
    window, so a window crosses several books) to many windows."""
    rng = np.random.default_rng(7)
    lengths = {"b00": 1, "b01": 3, "b02": 40, "b03": 7, "b04": 300, "b05": 129, "b06": 2, "b07": 64, "b08": 65,
               "b09": 513, "b10": 11, "b11": 1000}  # fmt: skip
    books = {b: rng.integers(0, 65535, n).astype(np.uint16) for b, n in lengths.items()}
    monkeypatch.setattr(shards, "load", lambda tid, b, tok=None: books[b])
    return books


@pytest.mark.parametrize("seed", [0, 1, 17])
@pytest.mark.parametrize("context,batch_tokens", [(8, 32), (16, 48), (63, 256)])
def test_plain_passes_are_the_old_ones(synthetic, seed, context, batch_tokens):
    ids = sorted(synthetic)
    new = data.stream(ids, "t", seed, batch_tokens, context, 3, {b: "f" for b in ids})
    assert same(new, OldStream(ids, "t", seed, batch_tokens, context, 3, {b: "f" for b in ids})) > 0


@pytest.mark.parametrize("first,repeats", [(["b04"], 1), (["b02", "b09", "b00"], 3), (["b11"], 2)])
def test_curriculum_passes_are_the_old_ones(synthetic, first, repeats):
    ids = sorted(synthetic)
    for seed in (2, 5):
        new = data.stream(ids, "t", seed, 40, 9, 3, first=first, first_repeats=repeats)
        old = OldStream(ids, "t", seed, 40, 9, 3, first=first, first_repeats=repeats)
        assert new.phase_windows == old.phase_windows
        assert same(new, old) > 0


def test_staged_passes_are_the_old_ones(synthetic):
    stages = [{"name": "one", "recipe": "a", "passes": 2}, {"name": "two", "recipe": "b", "passes": 3}]
    shelves = [["b00", "b04", "b05", "b06"], ["b01", "b02", "b03", "b07", "b08", "b09", "b10", "b11"]]
    new = data.Staged(stages, [data.stream(ids, "t", 1000 + i, 24, 7, st["passes"]) for i, (st, ids) in enumerate(zip(stages, shelves, strict=True))])  # fmt: skip
    old = data.Staged(stages, [OldStream(ids, "t", 1000 + i, 24, 7, st["passes"]) for i, (st, ids) in enumerate(zip(stages, shelves, strict=True))])  # fmt: skip
    assert new.bounds == old.bounds and new.record() == old.record()
    for step in range(new.total_steps):
        a, b = new.batch(step), old.batch(step)
        assert (a.pass_index, a.stage) == (b.pass_index, b.stage)
        assert np.array_equal(a.tokens, b.tokens) and np.array_equal(a.book_index, b.book_index), step


def test_a_window_crosses_a_book_boundary(synthetic):
    """A window that starts in one book and ends in the next: its tokens are both books', its book the first's."""
    ids = sorted(synthetic)
    s = data.stream(ids, "t", 3, 16, 16, 1)
    windows, books, deal = s._pass(0)
    order = np.random.default_rng([3, 0]).permutation(len(ids))
    ends = np.cumsum([len(s.arrays[i]) for i in order])
    w = int(ends[0] // 17)  # the window that holds the first book's last token
    assert ends[0] % 17 != 0 and (w + 1) * 17 > ends[0], "the first book ends inside a window"
    flat = np.concatenate([s.arrays[i] for i in order]).astype(np.int32)
    assert np.array_equal(windows[np.array([w])][0], flat[w * 17 : (w + 1) * 17])
    assert books[np.array([w])][0] == order[0]
    assert int(np.searchsorted(ends, (w + 1) * 17 - 1, side="right")) > 0, "and its last token is a later book's"


def test_the_real_library_streams_alike(library, spec):
    """The synthetic library's real shards (uint16 memmaps on disk), plain, curriculum and staged."""
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    tid = prep.tokeniser.id
    for seed in (1, 4):
        assert same(data.stream(prep.recipe, tid, seed, 512, 64, 3), OldStream(prep.recipe, tid, seed, 512, 64, 3))
        assert same(
            data.stream(prep.recipe, tid, seed, 256, 32, 2, first=["loc-b"], first_repeats=2),
            OldStream(prep.recipe, tid, seed, 256, 32, 2, first=["loc-b"], first_repeats=2),
        )
    assert isinstance(np.load(shards.shard_path(tid, prep.recipe[0]), mmap_mode="r"), np.memmap)


def test_no_pass_holds_the_corpus(synthetic):
    """What a pass keeps is the deal (one integer a window) and the books' order, never a copy of the tokens."""
    ids = sorted(synthetic)
    s = data.stream(ids, "t", 1, 32, 8, 2)
    windows, books, deal = s._pass(1)
    assert isinstance(windows, data.Windows) and len(windows) == len(deal) == s.windows_per_pass
    held = [v for v in vars(windows).values() if isinstance(v, np.ndarray)]
    assert sum(a.size for a in held) <= len(windows) + 2  # the window offsets of its parts, nothing a token long
    with pytest.raises(IndexError):
        windows[np.array([len(windows)])]
