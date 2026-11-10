"""The star chart: the journey to chaining, drawn for any model or ship (9 November, Justin: "this is our first star
chart. It maps the journey to chaining"; "the star chart has to be included in the SOP").

A matrix, not a scoreboard:

- **Rows — the sixteen cards**, in the deck's order (within each suit the Basics, the Stage 1 above them, then the
  Face). `deck.CARDS` is the order; each card's reading is the deck's own `look` (or a Face's `ability`).
- **Columns — a run**: the four chaining relations (`tricks/logic_test/gain_<relation>`), the aggregate, and the
  four chaining tests (`tricks/<test>_test/lift`). Where a model has been ablated, `knockout_deck` gives the causal
  weight for the same rows.
- **One axis for every model**: outside models and Thorp ships are read by the same evaluators, so a size sits on
  the same map as the reference.

    uv run thorp chart <run> [<run> ...]        # the matrix, one column per run
    uv run thorp chart --cards <run>            # the sixteen cards only
"""

from __future__ import annotations

import contextlib

from thorp.viable.s5_policy import deck

RELATIONS = ("order", "cause", "membership", "proportion")
TESTS = ("nature", "mill", "between", "pigeonhole")


def _metric(card) -> str | None:
    """The metric a card's reading lives in, from the deck: the best of its looks, or a Face's ability."""
    if card.look:
        return card.look[0][0]
    if card.ability:
        return card.ability[0]
    return None


def _at(run_id: str, metric: str) -> float | None:
    from thorp.ledger import reader

    rows = reader().query(
        "select value from metrics where run_id=? and name=? order by step desc limit 1", [run_id, metric]
    )
    return None if not rows else float(rows[0]["value"])


def chart(run: str) -> dict:
    """One column of the chart: the sixteen cards, the four relations and their aggregate, and the four tests."""
    from thorp.ledger import reader

    rows = reader().query(
        "select run_id, name from runs where name=? or run_id=? order by started desc limit 1", [run, run]
    )
    r = rows[0] if rows else None
    if r is None:  # an outside model: its deck reading in s4.outside_readings is the same metrics
        from thorp.viable.s4_intelligence import readings

        key = run if run.startswith(("deck-", "logic-")) else f"deck-{run.replace('/', '--')}"
        if readings.get(key) is None:  # the name a reading is stored under keeps -- for /
            key = key.replace("--", "/")
        d = readings.get(key)
        if d is None:
            return {"run": run, "name": None, "cards": {}, "relations": {}, "tests": {}, "chaining": None}
        m = d.get("metrics") or {}
        cards = {c.key: m[_metric(c)] for c in deck.CARDS if _metric(c) and m.get(_metric(c)) is not None}
        relations = {rel: m.get(f"tricks/logic_test/gain_{rel}") for rel in RELATIONS}
        relations["gain"] = m.get("tricks/logic_test/gain")
        tests = {t: m.get(f"tricks/{t}_test/lift") for t in TESTS}
        got = [v for v in tests.values() if v is not None]
        return {"run": key, "name": run, "cards": cards, "relations": relations, "tests": tests,
                "chaining": sum(got) / len(got) if got else None}  # fmt: skip
    rid = r["run_id"]
    cards = {}
    for card in deck.CARDS:
        metric = _metric(card)
        if metric:
            v = _at(rid, metric)
            if v is not None:
                cards[card.key] = v
    relations = {rel: _at(rid, f"tricks/logic_test/gain_{rel}") for rel in RELATIONS}
    relations["gain"] = _at(rid, "tricks/logic_test/gain")
    tests = {t: _at(rid, f"tricks/{t}_test/lift") for t in TESTS}
    got = [v for v in tests.values() if v is not None]
    return {
        "run": rid,
        "name": r["name"],
        "cards": cards,
        "relations": relations,
        "tests": tests,
        "chaining": sum(got) / len(got) if got else None,
    }


def _fmt(v, width: int = 7) -> str:
    return f"{'—':>{width}}" if v is None else f"{v:>{width}.2f}"


def matrix(runs: list[str]) -> list[str]:
    """The chart as lines: a row per card (in the deck's order), then the relations, then the tests, then the mean."""
    cols = [chart(r) for r in runs]
    width = 7
    head = f"{'':<22}" + "".join(f"{c['name'][-16:] if c['name'] else c['run'][:8]:>{width * 3}}"[:width * 3] for c in cols)
    out = []
    labels = [(c["name"] or c["run"][:8])[:16] for c in cols]
    out.append(f"{'':<22}" + "".join(f"{lab:>{width}}" for lab in labels))
    out.append(f"{'':<22}" + "".join(f"{'':>{width}}" for _ in cols))
    out.append(f"{'♠ ♥ ♦ ♣  the sixteen cards':<22}" + "".join(f"{'':>{width}}" for _ in cols))
    out.append(f"{'  = keeper  ~ decayer  ? untested':<22}" + "".join(f"{'':>{width}}" for _ in cols))
    for card in deck.CARDS:
        tier = deck.retention(card.key)["tier"]
        mark = {"keeper": "=", "decayer": "~", "untested": "?"}.get(tier, " ")
        row = f"  {mark} {card.key:<18}"
        for c in cols:
            row += _fmt(c["cards"].get(card.key), width)
        out.append(row)
    out.append(f"{'the four relations':<22}" + "".join(f"{'':>{width}}" for _ in cols))
    for rel in (*RELATIONS, "gain"):
        row = f"  {rel:<20}"
        for c in cols:
            row += _fmt(c["relations"].get(rel), width)
        out.append(row)
    out.append(f"{'the four tests':<22}" + "".join(f"{'':>{width}}" for _ in cols))
    for t in TESTS:
        row = f"  {t:<20}"
        for c in cols:
            row += _fmt(c["tests"].get(t), width)
        out.append(row)
    out.append(f"{'chaining':<22}" + "".join(_fmt(c["chaining"], width) for c in cols))
    return out


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="thorp chart")
    p.add_argument("runs", nargs="+", help="a run's name or id (each is a column)")
    p.add_argument("--cards", action="store_true", help="the sixteen cards only")
    a = p.parse_args(argv)
    for line in matrix(a.runs):
        print(line)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv[1:]))


# The ten-point chart (9 November, Justin): ten places chaining might live, what Qwen3 4B's heads say,
# the deck card each point is read as, and how a four-slot 300k tests it. This is the chart the Depth tab
# is building towards; the sixteen-card matrix above is the instrument that will fill it.
POINTS = (
    {"n": 1, "role": "the token reader",
     "qwen": "L0H2: corr −0.172, but silencing costs 0.052 — 1.86× the band, the only causal head found",
     "card": "previous_word", "test": "L0·0, already in every arm"},
    {"n": 2, "role": "the boundary reader",
     "qwen": "the shallowest, strongest reading by size in the fleet",
     "card": "delimiter", "test": "L0·1"},
    {"n": 3, "role": "the second-premise attendee",
     "qwen": "L15H17: corr +0.274, causal 0.009 — a reporter",
     "card": "the mover", "test": "L1·0"},
    {"n": 4, "role": "the copy gain",
     "qwen": "L18H27: corr −0.159, causal 0.028 = exactly the band",
     "card": "the Nevermore", "test": "L1·1"},
    {"n": 5, "role": "the order holder",
     "qwen": "L21H12: corr +0.270, causal 0.000 — a pure reporter",
     "card": "the comparator", "test": "L1·0, with a riddle"},
    {"n": 6, "role": "the repeat catcher",
     "qwen": "L15H7: corr +0.258, silencing improves chaining",
     "card": "duplicate_word", "test": "L1·0/1"},
    {"n": 7, "role": "the induction chain",
     "qwen": "L19H9: corr +0.264, causal 0.003",
     "card": "induction", "test": "L1·1"},
    {"n": 8, "role": "the middle term",
     "qwen": "L3H2: corr +0.258, causal 0.005",
     "card": "the bridge", "test": "L0·1, the only carrying card the shallow half holds"},
    {"n": 9, "role": "the suppressor",
     "qwen": "L1H1: corr −0.208, silencing raises chaining 0.008",
     "card": "none", "test": "read as an absence"},
    {"n": 10, "role": "the blocker",
     "qwen": "L8H30: corr −0.209, causal 0.002",
     "card": "none", "test": "read as an absence"},
)


def depths(standard: dict) -> list[dict]:
    """The depth the SOP includes, size by size: the model's layers in the standard, and the deepest
    card the pinning places. The 28 is a property of the 300k-l28 variant, not a separate requirement."""
    from thorp.models.registry import PRESETS

    sizes = ((standard or {}).get("pinning") or {}).get("sizes") or {}
    out = []
    for size, pins in sizes.items():
        if not isinstance(pins, dict) or not pins:
            continue
        deepest = max(int(v) for v in pins.values())
        layers = (PRESETS.get(size) or {}).get("layers")
        out.append({
            "size": size,
            "layers": layers if layers is not None else deepest + 1,
            "deepest_pinned": deepest,
            "pinned": len(pins),
        })
    order = list(PRESETS)
    out.sort(key=lambda x: order.index(x["size"]) if x["size"] in order else len(order))
    return out


# the old name, kept for readers written before the correction (the Standard's depth is not a
# separate requirement: it is included in the pinning table)
required_layers = depths
