"""The riddle cards' composed items (Justin, 2026-11-08 06:00: "can we get all metre and riddles for 9m"): a riddle
card's pattern is known only in a sentence built around it (thorp/viable/s5_policy/deck.py), so the scaffold
(train.py, optim.scaffold.riddles) writes such sentences and pulls the card toward its answer in them, beside the
voyage's own reading. Never the tests' own items:

- **The comparator** (its reading: evaluators/cards.py `comparator`, "Begun in the year D, the war lasted from the
  year Y to the year 17", 16 fixed years and their decoys). Here: other frames (a bridge stood, a school was open,
  a ship sailed ...), years from 1600 to 1899 that are none of the reading's years or decoys, and the same shape:
  a decoy year named first, the year to exceed, then "to the year" and the end year's first two digits. The pull:
  the pinned head's attention from the last piece onto the year to exceed.
- **The bridge** (its reading: cards.py `bridge`, on the logic deck's padded order items: the logit lens's
  log-probability of the middle term against a second, irrelevant middle term, at the conclusion's frame). Here:
  invented words from the logic tutor (none in the deck, the tests or the Ogden corpus), the tutor's own
  comparison words (none of the four chains' 50m rungs' words), "Each" where the deck says "Every". The pull: at
  the chosen layer, the logit lens at the frame's last piece prefers the bridge's first piece to the distractor's.

Each pool is fixed by its seed; a step draws its items from the pool by the step's number, so a resumed voyage
draws what an unbroken one would.
"""

from __future__ import annotations

import random
import re

import numpy as np

COMPARATOR_FRAMES = (
    "Built in the year {d}, the bridge stood from the year {y} to the year {p}",
    "Named in the year {d}, the ship sailed from the year {y} to the year {p}",
    "Founded in the year {d}, the school was open from the year {y} to the year {p}",
    "Planted in the year {d}, the garden was kept from the year {y} to the year {p}",
    "First printed in the year {d}, the paper came out from the year {y} to the year {p}",
    "Made in the year {d}, the clock was going from the year {y} to the year {p}",
)


def _reading_years() -> set[int]:
    from thorp.evaluators.cards import YEARS

    return set(YEARS) | {YEARS[(k + 5) % len(YEARS)] - 60 for k in range(len(YEARS))}


def _pad(rows: list[list[int]], eos: int) -> np.ndarray:
    L = max(len(r) for r in rows)
    return np.array([r + [eos] * (L - len(r)) for r in rows], dtype=np.int32)


def _span(tok, prompt: str, phrase: str) -> list[int]:
    from thorp.evaluators.cards import _span as span

    return span(tok, prompt, phrase)


def comparator_items(tok, n: int, seed: int = 1) -> dict:
    """n items: tokens (n, L) opened with EOS, q (n,) the last piece, target (n, L) the year to exceed's pieces."""
    rng = random.Random(f"riddle-comparator:{seed}")
    banned = _reading_years()
    toks, qs, tgts = [], [], []
    while len(toks) < n:
        y = rng.randint(1620, 1890)
        d = y - rng.randint(25, 90)
        if y in banned or d in banned or d < 1500:
            continue
        prompt = rng.choice(COMPARATOR_FRAMES).format(d=d, y=y, p=str(y)[:2])
        good, bad = _span(tok, prompt, f" {y}"), _span(tok, prompt, f" {d}")
        if not good or set(good) & set(bad):
            continue
        ids = [tok.eos_id] + tok.encode(prompt)
        toks.append(ids)
        qs.append(len(ids) - 1)
        tgts.append(good)
    t = _pad(toks, tok.eos_id)
    target = np.zeros(t.shape, dtype=np.float32)
    for i, g in enumerate(tgts):
        target[i, g] = 1.0 / len(g)
    return {"tokens": t, "q": np.array(qs, dtype=np.int32), "target": target}


def bridge_items(tok, n: int, seed: int = 1) -> dict:
    """n padded order items: tokens (n, L), q (n,) the frame's last piece, b (n,) the bridge's first piece and
    d (n,) the distractor's (never the same piece)."""
    from thorp import logic_tutor as lt

    rng = random.Random(f"riddle-bridge:{seed}")
    dims = [(w, o) for w, o in lt.usable()["dimensions"].values() if o]
    words = lt.invented_words(max(600, n // 2), seed=seed + 100)
    toks, qs, bs, ds = [], [], [], []
    tries = 0
    while len(toks) < n and tries < 50 * n:
        tries += 1
        w, o = rng.choice(dims)
        up, down = lt.comparative(w), lt.comparative(o)
        a, b, c, e, f, g = rng.sample(words, 6)
        if rng.random() < 0.5:  # the bridge is b: a is up of b, c is down of b, so a is up of c
            p1, p2 = f"Each {a} is {up} than each {b}.", f"Each {c} is {down} than each {b}."
        else:
            p1, p2 = f"Each {b} is {down} than each {a}.", f"Each {b} is {up} than each {c}."
        pad = f"Each {e} is {down} than each {f}, and each {f} is {down} than each {g}."  # f: the second middle term
        premises = [p1, p2]
        premises.insert(rng.randint(0, 2), pad)
        prompt = " ".join(premises) + f" So {'an' if a[0] in 'aeiou' else 'a'} {a} is"
        b0, d0 = tok.encode(" " + b)[0], tok.encode(" " + f)[0]
        if b0 == d0:
            continue
        ids = [tok.eos_id] + tok.encode(prompt)
        toks.append(ids)
        qs.append(len(ids) - 1)
        bs.append(b0)
        ds.append(d0)
    if not toks:
        raise ValueError("no bridge item: every bridge and distractor began with the same piece")
    return {
        "tokens": _pad(toks, tok.eos_id), "q": np.array(qs, dtype=np.int32),
        "b": np.array(bs, dtype=np.int32), "d": np.array(ds, dtype=np.int32),
    }  # fmt: skip


def draw(pool: dict, step: int, k: int) -> dict:
    """k items of a pool for this step, fixed by the step's number."""
    n = len(pool["q"])
    idx = np.random.default_rng(step).choice(n, size=min(k, n), replace=False)
    return {key: v[idx] for key, v in pool.items()}


# ---- the Bridge in all four relations (2026-11-08 09:45, after leg 0 of The Smallest Bridge: the order-only items were
# solved by step ~1,000, and the Bridge on the logic deck, whose padded rows are a quarter each order, cause,
# membership and proportion, rose to 1.37 and then fell to 0.12: the pull had narrowed to order)

_FRAME = {
    "order": re.compile(r"^(.*? (?:is|are))\b"),
    "membership": re.compile(r"^(.*? (?:has|have))\b"),
    "ratio": re.compile(r"^(.*?) as much\b"),
}


def _frame(sk, sentence: str) -> str | None:
    """The conclusion's opening, up to where its answer begins (as the deck's frames stop)."""
    rel = sk.conclusion.rel
    if rel == "cause":
        z = sk.conclusion.then.thing
        i = max(sentence.rfind(" " + z + " "), sentence.rfind(" " + z + "s "), sentence.rfind(" " + z + "es "))
        return None if i < 0 else sentence[: sentence.index(" ", i + 1)]
    pat = _FRAME.get("membership" if rel == "has" else rel)
    m = pat.match(sentence) if pat else None
    return m.group(1) if m else None


def bridge_items_all(tok, n: int, seed: int = 1) -> dict:
    """n padded items in the four relations, from the logic tutor's skeletons (its frames and words, none the
    deck's): the chain whose middle term is the Bridge, an unrelated chain of the same relation whose middle term is
    the distractor, its sentences put among the first's, then the conclusion's opening."""
    from thorp import logic_tutor as lt

    rng = random.Random(f"riddle-bridge-all:{seed}")
    sks = lt.skeletons(2 * n + 400, seed=100 + seed)
    by: dict[str, list] = {}
    for sk in sks:
        by.setdefault(sk.relation, []).append(sk)
    toks, qs, bs, ds = [], [], [], []
    rels = sorted(by)
    i = 0
    while len(toks) < n and i < 2 * n + 400:
        rel = rels[i % len(rels)]
        i += 1
        pool = by[rel]
        if len(pool) < 2:
            continue
        sk, pd = pool.pop(), pool.pop()
        sents = [lt._cap(lt.say(rng, g)) for g in lt._grouped(sk.facts)]
        pad = [lt._cap(lt.say(rng, g)) for g in lt._grouped(pd.facts)]
        for p in pad:
            sents.insert(rng.randint(0, len(sents)), p)
        frame = _frame(sk, lt.say(rng, [sk.conclusion]))
        if frame is None:
            continue
        prompt = " ".join(sents) + f" {rng.choice(lt.CONNECTIVES)} {frame}"
        b0, d0 = tok.encode(" " + sk.words[1])[0], tok.encode(" " + pd.words[1])[0]
        if b0 == d0:
            continue
        ids = [tok.eos_id] + tok.encode(prompt)
        toks.append(ids)
        qs.append(len(ids) - 1)
        bs.append(b0)
        ds.append(d0)
    if not toks:
        raise ValueError("no bridge item")
    return {
        "tokens": _pad(toks, tok.eos_id), "q": np.array(qs, dtype=np.int32),
        "b": np.array(bs, dtype=np.int32), "d": np.array(ds, dtype=np.int32),
    }  # fmt: skip
