"""The deck's overview: the cards as jobs, the questions they are needed to pass, and where the fleet finds them.

The charting page's Overview (9 November, Justin: "the cards are a job. the ones we've identified are jobs
needed to pass our set of questions ... where in the sieve at what layer those cards are found across the
fleet for 0.0.5 and then the stars ... what layer did the card appear on and when and how did it behave
with seeding and the fade").

Two readings per card, per size:

- **seeded**: the layer the SOP pins it to (v0.0.5's pinning table) — where the voyage was *told* to put it;
- **found**: the layer the voyage's own reading put it, the step it first passed its mark, and how many
  heads pass it at the last reading.

A card whose found layer is nowhere near its seeded one is telling you the pin is not where the model
would have put the job.
"""

from __future__ import annotations

import json

from thorp import fleet, paths, sop
from thorp.viable.s5_policy import deck

SIZES = (("300k", 6), ("1m", 12), ("9m", 18), ("21m", 24))
QUESTIONS = ("breeders_test", "mill_test", "between_test", "pigeonhole_test")


def _runs() -> dict[str, str]:
    """The newest v0.0.5 voyage at each size."""
    import sqlite3

    con = sqlite3.connect(f"file:{paths.ledger_path()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {}
    for preset, _ in SIZES:
        r = con.execute(
            "select run_id from runs where json_extract(spec_json,'$.model.preset')=? "
            "and json_extract(spec_json,'$.sop')='0.0.5' order by started desc limit 1",
            [preset],
        ).fetchone()
        if r:
            out[preset] = r["run_id"]
    con.close()
    return out


def _series(con, run: str, name: str) -> list[tuple[int, float]]:
    return [(r["step"], r["value"]) for r in con.execute(
        "select step, value from metrics where run_id=? and name=? order by step", (run, name))]


def payload() -> dict:
    import sqlite3

    con = sqlite3.connect(f"file:{paths.ledger_path()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    runs = _runs()
    pin = ((sop.standard("0.0.5") or {}).get("pinning") or {}).get("sizes") or {}
    keepers = getattr(deck, "RETENTION", None) or {}

    cards = []
    for c in deck.CARDS:
        found = {}
        for preset, layers in SIZES:
            run = runs.get(preset)
            if not run:
                continue
            if not c.look or not c.layer:
                continue  # a Face with no numeric look: nothing to find on a layer
            layer_series = _series(con, run, c.layer)
            if not layer_series:
                continue
            look = c.look[0][0]  # the lit metric
            lit = _series(con, run, look)
            first = next((s for s, v in lit if v is not None and v >= c.look[1]), None)
            last_step, last_layer = layer_series[-1]
            count = _series(con, run, look.replace("max_score", "count"))
            heads = int(count[-1][1]) if count else (1 if last_layer is not None else 0)
            found[preset] = {
                "layer": None if last_layer is None else int(last_layer),
                "depth": None if last_layer is None else round(100 * last_layer / layers),
                "first_lit": first,
                "heads": heads,
            }
        cards.append(
            {
                "key": c.key,
                "name": c.name,
                "job": c.ability_text,
                "suit": c.constellation,
                "stage": c.stage,
                "mark": (c.look[1] if c.look else None),
                "needs": list(getattr(c, "on", ()) or ()),
                "tier": (keepers.get(c.key) or {}).get("tier"),
                "seeded": {p: (pin.get(p) or {}).get(c.key) for p, _ in SIZES},
                "found": found,
            }
        )
    con.close()

    questions = [
        {"key": k, "name": fleet.TRICKS[k].name, "teaches": fleet.TRICKS[k].about,
         "mark": fleet.TRICKS[k].threshold, "metric": fleet.TRICKS[k].metric,
         "done_by": list(getattr(fleet.TRICKS[k], "performed_by", ()) or ())}
        for k in QUESTIONS
    ]
    return {"sizes": [p for p, _ in SIZES], "layers": {p: n for p, n in SIZES},
            "questions": questions, "cards": cards}


if __name__ == "__main__":
    print(json.dumps(payload(), indent=1)[:2000])
