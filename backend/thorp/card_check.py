"""Are the cards real? (2026-11-07, Justin: "validate first"). A card is a definition of a mechanism;
it is trusted only if the models that chain two facts play it and the models that do not, do not.

From the chain grades (s4.outside_readings "chain-grades", scripts/grade_chains.py), each model is a **chainer** when it
performs at least three of the four chaining tests (the 50m rung of each chain), and a **non-chainer**
when it performs none. For each card (mover, bridge, comparator) the table is lit-or-not against
chainer-or-not; a card is **necessary** when at least four in five chainers play it (a card Nothing up my sleeve must draw before
it can chain), and a **marker** when it is also dark on at least two-thirds of the non-chainers (a
card that signals the trick itself). Models between (one or two chaining tests) are listed, not
counted. First reading (12:30): previous-word, Nevermore, the mover and the comparator are necessary
(5 of 5 chainers) and none is a marker (the Pythias play all four and do not chain); the bridge is
neither (2 of 5).

    uv run python -m thorp.card_check
"""

from __future__ import annotations

from thorp import fleet, leaderboard

CARDS = ("previous_word", "nevermore", "mover", "bridge", "comparator")


def _lit(c: dict | None) -> bool | None:
    if not c:
        return None
    return bool(c.get("lit") or c.get("lit_shared"))


def payload() -> dict:
    from thorp.viable.s4_intelligence import readings

    models = readings.chain_grades()
    tests = leaderboard.chaining_tests()
    rows = []
    for name, v in models.items():
        if "cards" not in v:
            continue
        passed = sum(bool(v.get(k, {}).get("performed")) for k in tests)
        kind = "chainer" if passed >= 3 else "non-chainer" if passed == 0 else "between"
        label = fleet.COMPETITORS.get(name, (name.split("/")[-1], 0))[0]
        rows.append(
            {
                "model": name,
                "label": label,
                "passed": passed,
                "logic_gain": (v.get("logic_test") or {}).get("gain"),
                "kind": kind,
                "cards": {
                    c: {**(v["cards"].get(c) or {}), "lit": _lit(v["cards"].get(c))} for c in CARDS
                },
                "attention_readable": v["cards"].get("attention_readable", True),
            }
        )
    verdicts = {}
    for c in CARDS:
        ch = [
            r["cards"][c]["lit"]
            for r in rows
            if r["kind"] == "chainer" and r["cards"][c]["lit"] is not None
        ]
        non = [
            r["cards"][c]["lit"]
            for r in rows
            if r["kind"] == "non-chainer" and r["cards"][c]["lit"] is not None
        ]
        hit = sum(ch) / len(ch) if ch else None
        dark = (len(non) - sum(non)) / len(non) if non else None
        necessary = hit is not None and hit >= 0.8
        verdicts[c] = {
            "chainers_lit": f"{sum(ch)}/{len(ch)}",
            "non_chainers_dark": f"{len(non) - sum(non)}/{len(non)}",
            # necessary: every model that chains plays it (a card Nothing up my sleeve must draw); a marker: also
            # dark where there is no chaining (a card that signals the trick itself)
            "necessary": necessary,
            "marker": necessary and dark is not None and dark >= 2 / 3,
            "valid": necessary,
        }
    return {"models": rows, "verdicts": verdicts}


def main() -> None:
    p = payload()
    print(f"{'model':22} {'passed':>6} {'logic gain':>10}  " + "  ".join(f"{c:>12}" for c in CARDS))
    for r in sorted(p["models"], key=lambda r: (-r["passed"], r["label"])):
        cells = []
        for c in CARDS:
            x = r["cards"][c]
            if x["lit"] is None:
                cells.append(f"{'unread':>12}")
            else:
                score = x.get("shared", x.get("max", 0.0))
                cells.append(f"{score:+8.2f} {'LIT' if x['lit'] else '   '}")
        g = r["logic_gain"]
        print(
            f"{r['label'][:22]:22} {r['passed']:>4}/4 {g if g is None else round(g, 3):>10}  "
            + "  ".join(cells)
            + f"   {r['kind']}"
        )
    print()
    for c, v in p["verdicts"].items():
        kind = "MARKER" if v["marker"] else "NECESSARY" if v["necessary"] else "neither"
        print(
            f"{c:13} chainers lit {v['chainers_lit']:>5}, non-chainers dark {v['non_chainers_dark']:>5}: {kind}"
        )


if __name__ == "__main__":
    main()
