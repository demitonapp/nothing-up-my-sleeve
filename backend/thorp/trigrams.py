"""Trigram repetition, the induction head's food (2026-11-07, Justin: "to get an induction head, it's
kind of proved that you can do it by the trigrams").

Induction heads form when text repeats sequences within the window a model reads (Olsson et al. 2022),
and trigram statistics learned in context are the stepping stone to them (Edelman et al. 2024, in-context
Markov chains). What feeds a Nevermore is therefore not how common a book's trigrams are but how often a
trigram **comes back within the window**. For every book:

- `repeat_rate`: the share of word trigrams that already occurred within the previous WINDOW words
  (a reader of that window could have predicted the third word from the first two);
- `variety`: distinct trigrams over all trigrams in the book (1 is all different, 0 all the same);
- `words`.

A book is on the **Pareto frontier** when no other book on its shelves has both a higher repeat rate and
a higher variety: the most repetition for the least loss of variety (formulaic text that is still text).
Words, not tokeniser pieces, so the measure is the same for every class and tokeniser. Computed once
and cached in data/trigrams.csv.

    uv run python -m thorp.trigrams lists/cause-shelf.csv lists/stars-fiction.csv
"""

from __future__ import annotations

import csv
import os
import re
import sys
from collections import deque

from thorp import paths

WINDOW = 1024  # words: about the window a 1,024-piece model reads
WORD = re.compile(r"[A-Za-z']+")
CACHE = "trigrams.csv"
MAX_WORDS = 400_000  # a book's first 400k words are enough to know its habits


NAMEWORD = re.compile(r"[A-Za-z']+|[.!?]")


def name_measure(text: str, window: int = WINDOW, cap: int = MAX_WORDS) -> tuple[float, float]:
    """(name repetition, name density): of the capitalised words that do not open a sentence (mostly
    names: "Darcy", "Elizabeth"), the share already seen within the previous WINDOW words, and how many
    there are per word. Induction heads copy rare words that recur nearby, which names are; at 1m the
    name repetition tracked the Nevermore beyond the amount read (+0.32), trigram repetition did not."""
    prev, recent, win = ".", {}, deque()
    rep = tot = nwords = 0
    for t in NAMEWORD.findall(text):
        if t in ".!?":
            prev = t
            continue
        nwords += 1
        if nwords > cap:
            break
        if t[0].isupper() and prev not in ".!?" and t != "I":
            tot += 1
            if recent.get(t, 0) > 0:
                rep += 1
            recent[t] = recent.get(t, 0) + 1
            win.append((nwords, t))
        while win and win[0][0] < nwords - window:
            _, old = win.popleft()
            recent[old] -= 1
        prev = t
    return (rep / tot if tot else 0.0), (tot / max(nwords, 1))


def measure_text(text: str) -> dict:
    words = [w.lower() for w in WORD.findall(text)][:MAX_WORDS]
    names, density = name_measure(text)
    if len(words) < 3:
        return {
            "repeat_rate": 0.0,
            "variety": 0.0,
            "words": len(words),
            "name_repeat": names,
            "name_density": density,
        }
    recent: dict[tuple, int] = {}  # trigram -> count inside the window
    window: deque = deque()
    seen: set = set()
    repeats = total = 0
    for i in range(2, len(words)):
        tri = (words[i - 2], words[i - 1], words[i])
        if recent.get(tri, 0) > 0:
            repeats += 1
        total += 1
        seen.add(tri)
        window.append(tri)
        recent[tri] = recent.get(tri, 0) + 1
        if len(window) > WINDOW:
            old = window.popleft()
            recent[old] -= 1
    return {
        "repeat_rate": repeats / total,
        "variety": len(seen) / total,
        "words": len(words),
        "name_repeat": names,
        "name_density": density,
    }


def _cache() -> dict[str, dict]:
    """The cached readings; a row without the name measures (written before they existed) is
    treated as unmeasured, so it is measured again."""
    if os.environ.get("THORP_LIBRARY_PG") == "1":
        from thorp import manifest_store

        return manifest_store.book_measures()
    p = paths.data_dir() / CACHE
    if not p.exists():
        return {}
    out = {}
    with p.open() as f:
        for r in csv.DictReader(f):
            if not r.get("name_repeat") or not r.get("name_density"):
                continue
            out[r["book"]] = {
                "repeat_rate": float(r["repeat_rate"]),
                "variety": float(r["variety"]),
                "words": int(r["words"]),
                "name_repeat": float(r["name_repeat"]),
                "name_density": float(r["name_density"]),
            }
    return out


def _save(cache: dict[str, dict]) -> None:
    p = paths.data_dir() / CACHE
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["book", "repeat_rate", "variety", "words", "name_repeat", "name_density"])
        for b, v in sorted(cache.items()):
            w.writerow(
                [
                    b,
                    round(v["repeat_rate"], 5),
                    round(v["variety"], 5),
                    v["words"],
                    round(v.get("name_repeat", 0.0), 5),
                    round(v.get("name_density", 0.0), 5),
                ]
            )


def book_ids(list_path: str) -> list[str]:
    """The fetched book ids a list names (as the shelves read them)."""
    from thorp import shelves

    for s in shelves.payload():
        if s["path"] == list_path:
            return [u for u in s.get("book_ids", [])]
    return []


def measure_books(ids: list[str]) -> dict[str, dict]:
    from thorp.sources import load_text

    cache = _cache()
    todo = [b for b in ids if b not in cache]
    for b in todo:
        try:
            cache[b] = measure_text(load_text(b))
        except Exception:
            continue
    if todo:
        _save(cache)
    return {b: cache[b] for b in ids if b in cache}


def frontier(stats: dict[str, dict]) -> set[str]:
    """The books no other book beats on both repeat rate and variety."""
    items = sorted(stats.items(), key=lambda kv: (-kv[1]["repeat_rate"], -kv[1]["variety"]))
    out, best_variety = set(), -1.0
    for b, v in items:
        if v["variety"] > best_variety:
            out.add(b)
            best_variety = v["variety"]
    return out


if __name__ == "__main__":
    from statistics import mean

    for lp in sys.argv[1:]:
        ids = book_ids(lp)
        st = measure_books(ids)
        if not st:
            print(lp, "no fetched books")
            continue
        fr = frontier(st)
        print(
            f"{lp}: {len(st)} books, repeat rate {mean(v['repeat_rate'] for v in st.values()):.3f}, "
            f"variety {mean(v['variety'] for v in st.values()):.3f}, frontier {len(fr)} books"
        )


def book_stats(ids: list[str]) -> dict[str, dict]:
    """The cached readings for these books (no new measuring: fast enough for a page)."""
    cache = _cache()
    return {b: cache[b] for b in ids if b in cache}


def shelf_stats(ids: list[str]) -> dict | None:
    """A shelf's mean repeat rate and variety and its frontier, from the cache (None if unmeasured)."""
    st = book_stats(ids)
    if not st:
        return None
    n = len(st)
    return {
        "measured": n,
        "repeat_rate": sum(v["repeat_rate"] for v in st.values()) / n,
        "variety": sum(v["variety"] for v in st.values()) / n,
        "frontier": sorted(frontier(st)),
        "name_repeat": sum(v.get("name_repeat", 0.0) for v in st.values()) / n,
    }
