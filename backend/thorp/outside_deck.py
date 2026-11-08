"""The whole deck read on an outside model (Justin, 2026-11-08 08:40: "is there a 100m model I can compare it against
to score it"; "do it"): all 16 cards, read by the same evaluators that read Thorp (stars, pips, nevermore, cards),
inside the model through thorp.inside.Inside, so Pythia, Qwen or any MLX-LM model can be set beside a Thorp card by
card, and the deck's rules (wager.falls) say which it plays.

- **The tokeniser** (`OutsideTok`): the model's own, as the evaluators expect a Thorp tokeniser: an id, the document
  start piece (as grade_chains reads it: the model's beginning-of-text, else <|endoftext|>, else its end), each
  piece's bytes (so the delimiter and the word classes are found among *its* pieces), and each book's pieces, read
  from the book's text cleaned as the voyages read it (cleaning.CURRENT).
- **The shelf** for the rare word's rarity: Ogden v0.1's books in the model's own pieces (the corpus every
  Ogden voyage reads), so "rare" means the same text for every model.
- **The logic deck's lifts** (the Mover's and the Scales' abilities) are taken from the chain grades (s4.outside_readings),
  where grade_chains.py already read them; the five cards it read there are read again here with the rest.

Kept: s4.outside_readings, deck-<model> ({model, metrics, played, layers}).
"""

from __future__ import annotations

import time

import numpy as np

NATURAL_CONTEXT = 1024  # the window the readings use, as a Thorp voyage's (1,024 pieces)


class OutsideTok:
    def __init__(self, name: str, t, clean: str):
        self.id = "hf:" + name
        self._t = t
        self.clean = clean
        bos = getattr(t, "bos_token_id", None)
        doc = t.convert_tokens_to_ids("<|endoftext|>") if hasattr(t, "convert_tokens_to_ids") else None
        if isinstance(bos, int):
            self.eos_id = bos
        elif isinstance(doc, int) and doc != getattr(t, "unk_token_id", -1):
            self.eos_id = doc
        else:
            self.eos_id = t.eos_token_id or 0
        self.vocab_size = len(t)
        self.piece_bytes_list = [t.decode([i]).encode("utf-8") for i in range(self.vocab_size)]
        self._books: dict[str, np.ndarray] = {}

    def encode(self, s: str) -> list[int]:
        return self._t.encode(s, add_special_tokens=False)

    def decode(self, ids) -> str:
        return self._t.decode(list(ids))

    def book_ids(self, book: str) -> np.ndarray:
        if book not in self._books:
            from thorp.sources import load_text

            self._books[book] = np.asarray(self.encode(load_text(book, self.clean)), dtype=np.int64)
        return self._books[book]


def _list_ids(lp: str) -> list[str]:
    """A book list's ids, resolved as training resolves it (rows naming their book, or titles matched)."""
    from thorp.train import gutenberg_resolver

    ids, _ = gutenberg_resolver(lp)
    return ids


def read(name: str, log=print) -> dict:
    import mlx.core as mx
    from mlx_lm import load

    from thorp import cleaning, fleet
    from thorp.evaluators import EvalContext, cards, nevermore, pips, stars
    from thorp.evaluators.logic import load_deck
    from thorp.inside import Inside
    from thorp.viable.s4_intelligence import wager

    t0 = time.time()
    from mlx.utils import tree_map

    model, t = load(name)
    # the readings in float32: a float16 model (Pythia) overflows to NaN in its full forward pass; quantised
    # weights (the 4-bit models) are left as they are
    model.update(tree_map(lambda p: p.astype(mx.float32) if p.dtype in (mx.float16, mx.bfloat16) else p, model.parameters()))
    tok = OutsideTok(name, t, cleaning.CURRENT)
    inner = Inside(model)
    judge = _list_ids("lists/hole-cards-unseen.csv")
    shelf = _list_ids("lists/ogden-v0.1.csv")
    ctx = EvalContext(run_id="outside:" + name, step=0, model=inner, tokeniser=tok, context=NATURAL_CONTEXT,
                      sets={"hole-cards-unseen": judge}, recipe=shelf)  # fmt: skip
    metrics: dict[str, float] = {}
    for label, ev in (("stars", stars), ("pips", pips), ("nevermore", nevermore)):
        res = ev.evaluate(ctx)
        metrics.update(res.metrics)
        log(f"  {label}: {len(res.metrics)} readings, {time.time() - t0:.0f}s")
    deck = load_deck()
    for key, s_ in (("mover", cards.mover(inner, tok, deck)), ("comparator", cards.comparator(inner, tok))):
        if s_ is None:
            continue
        li, hi = np.unravel_index(int(s_.argmax()), s_.shape)
        sh, sl = cards.shared(s_)
        metrics.update({f"stars/{key}/max_score": float(s_.max()), f"stars/{key}/best_layer": float(li),
                        f"stars/{key}/best_head": float(hi), f"stars/{key}/shared_score": sh,
                        f"stars/{key}/shared_layer": float(sl)})  # fmt: skip
    br = cards.bridge(inner, tok, deck)
    if br is not None:
        metrics.update({"stars/bridge/max_score": float(br.max()), "stars/bridge/best_layer": float(int(br.argmax()))})
    from thorp.viable.s4_intelligence import readings

    lg = (readings.chain_grades().get(name) or {}).get("logic_test") or {}
    for k in ("lift_one_hop", "gain_order", "gain", "lift"):
        if lg.get(k) is not None:
            metrics[f"tricks/logic_test/{k}"] = float(lg[k])
    mx.clear_cache()
    metrics = {k: float(v) for k, v in metrics.items() if v is not None and np.isfinite(v)}
    f = wager.falls(None, 1, series={k: [(0, v)] for k, v in metrics.items()})
    played = sorted(k for k, v in f.items() if v["played"])
    out = {
        "model": name, "read": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - t0),
        "clean": tok.clean, "context": NATURAL_CONTEXT, "layers": len(inner.hidden(mx.array([[tok.eos_id]]))),
        "metrics": metrics, "played": played, "falls": {k: v["layer"] for k, v in f.items() if v["played"]},
        "attention_readable": bool(inner.attention_patterns(mx.array([[tok.eos_id] + tok.encode("A test.")]))),
        "stars_known": sorted(fleet.STARS),
    }  # fmt: skip
    readings.put(f"deck-{name.replace('/', '--')}", out)
    log(f"{name}: {len(played)} of 16 cards played: {', '.join(played)} ({out['seconds']}s)")
    return out


if __name__ == "__main__":
    import sys

    from thorp import vsm

    for name in sys.argv[1:]:
        with vsm.at_sea(f"read the deck on {name}", kind="score"):
            read(name)
