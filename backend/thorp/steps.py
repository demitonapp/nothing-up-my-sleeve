"""The steps to chaining, and the ten-times comparison (11 November, Justin: "rebuild it").

Under a billion parameters nothing chains, so a board ranked by chaining lift ranks noise: its first
row was a 314k model that passes none of the four tests and whose chaining gain is negative. This
module reads the same table rows (`leaderboard.payload()["table"]`) as **steps held** instead:

- **cards**: all four necessary cards lit (previous-word, the Nevermore, the mover, the comparator);
- **one_hop**: the logic deck's one-hop lift at the Mover's mark (following one stated premise);
- **gain**: the logic deck's chaining gain above its noise (both premises less the better single
  premise: the proof that a pass is chaining, not knowing or one premise);
- **test**: at least one of the four chaining tests performed.

A step is counted where it is held, not only in order: the one model under 1B that passes a chaining
test (Qwen3 0.6B) lights three of the four cards, so "every step from the bottom" would rank it last.
A model **chains** only through the door: the gain step and the test step together. A step that was
not read (attention the card judge cannot read, no logic deck reading) is None, never False.

`ten_times` is the project's claim made a table: each Nothing up my sleeve ship beside the outside
model nearest ten times its size, measure by measure, with readings inside the noise called a tie.

They are called steps, not rungs: a rung is already a size class on the ladder (`fleet.RUNGS`).
Pure functions over rows; the noise and the mark are passed in by the leaderboard, which owns them.
"""

from __future__ import annotations

import math

GAIN_NOISE = 0.05  # the logic deck's chaining gain, read on the same deck as its one-hop lift
TEN_TIMES_WITHIN = 2.0  # a reference counts as "ten times the size" from 5x to 20x

STEPS: tuple[tuple[str, str, str], ...] = (
    ("cards", "the four cards", "all four necessary cards lit: every model that chains at 2–4B holds them"),
    ("one_hop", "one hop", "the logic deck's one-hop lift at the mark: following one stated premise"),
    ("gain", "chaining gain", "the logic deck's chaining gain above its noise: both premises less the better single premise"),
    ("test", "a chaining test", "at least one of the four chaining tests performed (lift at the mark, two in three right)"),
)
ORDER = {k: i for i, (k, _, _) in enumerate(STEPS)}


def about(one_hop_mark: float, one_hop_noise: float) -> dict:
    """The steps as the page names them, with the marks they are read against."""
    return {
        "order": [{"key": k, "name": n, "about": a} for k, n, a in STEPS],
        "one_hop_mark": one_hop_mark,
        "one_hop_noise": one_hop_noise,
        "gain_noise": GAIN_NOISE,
        "ten_times_within": TEN_TIMES_WITHIN,
    }


def steps_of(row: dict, one_hop_mark: float) -> dict:
    """Which steps a table row holds: True, False, or None where the step was not read."""
    cards, one_hop, passed = row.get("cards_held"), row.get("one_hop"), row.get("passed")
    gain = (row.get("logic") or {}).get("gain")
    held = {
        "cards": None if cards is None else cards >= 4,
        "one_hop": None if one_hop is None else one_hop >= one_hop_mark,
        "gain": None if gain is None else gain > GAIN_NOISE,
        "test": None if passed is None else passed >= 1,
    }
    got = [k for k, _, _ in STEPS if held[k]]
    return {
        "held": held,
        "count": len(got),
        "top": got[-1] if got else None,
        "chains": bool(held["gain"] and held["test"]),  # the door to the chaining table
    }


def _hop_band(row: dict, noise: float) -> int:
    oh = row.get("one_hop")
    return -9 if oh is None else round(oh / noise)


def rank(rows: list[dict], one_hop_mark: float, one_hop_noise: float) -> None:
    """Give every row its steps and its rank among the rows of its size class: steps held, then the
    highest step, then the one-hop lift in steps of its noise. Rows equal on all three tie and share
    a rank, listed bigger first (a neutral order, not a claim)."""
    for r in rows:
        r["steps"] = steps_of(r, one_hop_mark)

    def key(r: dict) -> tuple:
        s = r["steps"]
        return (s["count"], ORDER.get(s["top"], -1), _hop_band(r, one_hop_noise))

    by_class: dict[str | None, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r.get("size_class"), []).append(r)
    for group in by_class.values():
        group.sort(key=lambda r: (tuple(-x for x in key(r)), -(r.get("params") or 0)))
        place, prev = 0, None
        for i, r in enumerate(group, 1):
            if key(r) != prev:
                place, prev = i, key(r)
            r["step_rank"] = place
        for r in group:
            r["step_tied"] = sum(1 for x in group if x["step_rank"] == r["step_rank"]) > 1


def _verdict(ours: float | None, theirs: float | None, noise: float) -> str | None:
    """ahead, tie or behind; None where either side was not read. Within the noise is a tie."""
    if ours is None or theirs is None:
        return None
    if abs(ours - theirs) <= noise:
        return "tie"
    return "ahead" if ours > theirs else "behind"


def ten_times(rows: list[dict], one_hop_noise: float) -> list[dict]:
    """Each Nothing up my sleeve row beside the outside model nearest ten times its size.

    The reference is the outside row closest to ten times the ship's parameters on a log scale, and
    only within a factor of TEN_TIMES_WITHIN of it (5x to 20x); a ship with none has `reference`
    None. Each measure is ahead, tie (inside its noise) or behind; a ship **matches** when no
    measure read on both sides is behind."""
    ours = [r for r in rows if r.get("kind") == "thorp" and r.get("params")]
    outside = [r for r in rows if r.get("kind") != "thorp" and r.get("params")]
    out = []
    for s in sorted(ours, key=lambda r: -r["params"]):
        target = 10.0 * s["params"]
        ref = min(outside, key=lambda r: abs(math.log10(r["params"] / target)), default=None)
        if ref is not None and abs(math.log10(ref["params"] / target)) > math.log10(TEN_TIMES_WITHIN):
            ref = None
        row = {
            "ship_key": s.get("ship_key"),
            "name": s.get("name"),
            "ship": s.get("ship"),
            "params": s["params"],
            "size_class": s.get("size_class"),
            "sailings": s.get("sailings"),
            "reference": None,
            "measures": {},
            "matched": None,
        }
        if ref is not None:
            row["reference"] = {
                "model": ref.get("model"),
                "name": ref.get("name"),
                "params": ref["params"],
                "times": round(ref["params"] / s["params"], 1),
            }
            pairs = {
                "steps": (s["steps"]["count"], ref["steps"]["count"], 0.0),
                "cards": (s.get("cards_held"), ref.get("cards_held"), 0.0),
                "one_hop": (s.get("one_hop"), ref.get("one_hop"), one_hop_noise),
                "gain": ((s.get("logic") or {}).get("gain"), (ref.get("logic") or {}).get("gain"), GAIN_NOISE),
            }
            for k, (a, b, noise) in pairs.items():
                row["measures"][k] = {"ours": a, "theirs": b, "verdict": _verdict(a, b, noise)}
            read = [m["verdict"] for m in row["measures"].values() if m["verdict"]]
            row["matched"] = bool(read) and "behind" not in read
        out.append(row)
    return out
