"""The leaderboard: the best of each class at chaining two facts (2026-11-07, Justin).

The leaderboard is public: it shows **only the four chaining tests** (the 50m rung of each discovery
chain: Nature's breeder, the mill test, the between test, the pigeonhole test), the one skill set
against the outside models. Every other rung is Nothing up my sleeve's own internal measure and stays off it
(Justin: "the leaderboard should only cover chaining tests and not our other tests, which is our own
internal measure and not public").

- **chaining lift**: the mean lift on the four chaining tests; each test is performed at a lift of 0.1
  with two-thirds of its pairs right.
- **passed**: how many of the four a run performs.
- **logic** (the logic deck's chaining gain, invented words and single-premise controls): the proof
  beside the four, that a pass is chaining and not knowledge or copying.
- **two boards in one table** (`payload()["table"]`, outside models and Nothing up my sleeve's versions together):
  **chaining**, the readings that clear the noise (a Nothing up my sleeve ship on at least two sailings), ranked by
  chaining lift; and **approaching**, the rest, ranked by how close they are: the necessary cards held
  (previous-word, the Nevermore, the mover, the comparator: every model that chains holds all four;
  thorp/card_check.py), then the one-hop lift on the logic deck (following one stated premise, the step
  before two), in steps of the noise (0.05): readings within it tie and share a rank, bigger first.
- **best in class**: the ship of each class (a class and a fitout; its runs are its sailings) with
  the highest chaining lift, its sailings averaged, so the luckiest of fifty single runs is not taken
  for the best; and where a class has ships of two sailings or more, only those can be its best
  (ties: tests passed, then sailings); `chaining_rising` when it clears the noise
  (CHAINING_NOISE: the untrained models lie within about 0.03 of zero) on at least two sailings and
  beats the class below.

`climb()` (0 to 5: every rung of the four chains from the bottom, plus the next rung's progress) is the
internal measure, used by the two-fact voyage's page, never by the leaderboard's payload.

Readings are each run's latest discovery metrics in the ledger; the reference ladder and the
competitors (fleet.REFERENCE_LADDER, fleet.COMPETITORS, from the chain grades, s4.outside_readings) beside.

    uv run python -m thorp.leaderboard        # the table, in plain text
"""

from __future__ import annotations

import json

from thorp import arc_scores, candidates, fleet

CHAINING = "paragraph"  # the RUNGS goal class whose rung is two facts chained
CHAINING_NOISE = 0.03
ONE_HOP_NOISE = (
    0.05  # the logic deck's one-hop lift: untrained models read within about this of zero
)


def class_of_preset() -> dict[str, str]:
    """preset -> RUNGS goal class, by ladder order (keel, pilot, speller, stylist, 50m, explorer)."""
    from thorp.models.registry import LADDER

    return {r["preset"]: g.goal_class for r, g in zip(LADDER, fleet.RUNGS, strict=False)}


def climb(lift: dict[str, float], score: dict[str, float]) -> dict:
    """A run's climb from its per-trick lift and share of pairs right."""
    per_chain = {}
    for c in fleet.chains():
        rungs = c[:-1]
        done = 0
        for k in rungs:
            m = {
                fleet.TRICKS[k].metric: lift.get(k, float("-inf")),
                f"tricks/{k}/score": score.get(k, 0.0),
            }
            if not fleet.performed(k, m):
                break
            done += 1
        nxt = rungs[done] if done < len(rungs) else None
        partial = 0.0
        if nxt is not None and nxt in lift:
            partial = max(0.0, min(1.0, lift[nxt] / fleet.TRICKS[nxt].threshold))
            if partial >= 1.0:  # its lift is at the mark but its share is not: not lit, nearly
                partial = 0.99
        per_chain[c[-1]] = {
            "rungs": done,
            "next": nxt,
            "partial": round(partial, 3),
            "climb": done + partial,
        }
    chain_rungs = [
        next(k for k in c if fleet.TRICKS[k].goal_class == CHAINING) for c in fleet.chains()
    ]
    have = [lift[k] for k in chain_rungs if k in lift]
    return {
        "climb": round(sum(v["climb"] for v in per_chain.values()) / len(per_chain), 3),
        "chaining_lift": round(sum(have) / len(have), 4) if have else None,
        "chains": per_chain,
    }


def chaining_tests() -> list[str]:
    return [next(k for k in c if fleet.TRICKS[k].goal_class == CHAINING) for c in fleet.chains()]


def chaining(lift: dict[str, float], score: dict[str, float]) -> dict:
    """The public reading: the four chaining tests only."""
    tests = {}
    for k in chaining_tests():
        if k in lift:
            m = {fleet.TRICKS[k].metric: lift[k], f"tricks/{k}/score": score.get(k, 0.0)}
            tests[k] = {
                "name": fleet.TRICKS[k].name,
                "lift": round(lift[k], 4),
                "score": round(score.get(k, 0.0), 3),
                "performed": fleet.performed(k, m),
            }
    have = [t["lift"] for t in tests.values()]
    logic = None
    if "logic_test" in lift:
        m = {
            fleet.TRICKS["logic_test"].metric: lift["logic_test"],
            "tricks/logic_test/score": score.get("logic_test", 0.0),
        }
        logic = {
            "gain": round(lift["logic_test"], 4),
            "score": round(score.get("logic_test", 0.0), 3),
            "performed": fleet.performed("logic_test", m),
        }
    return {
        "logic": logic,
        "chaining_lift": round(sum(have) / len(have), 4)
        if len(have) == len(chaining_tests())
        else None,
        "passed": sum(t["performed"] for t in tests.values()),
        "tests": tests,
    }


def _readings_many(con, run_ids: list[str]) -> dict[str, tuple[dict, dict]]:
    """Every run's trick readings in one round trip (10 November: the leaderboard took 20 s because it
    asked the store once per run — 177 queries at ~120 ms each). The rows are in step order and the
    later reading of a metric stands, as the single-run query did."""
    out: dict[str, tuple[dict, dict]] = {}
    ids = [r for r in run_ids if r]
    if not ids:
        return out
    marks = ",".join("?" for _ in ids)
    for m in con.execute(
        f"select run_id, name, value from metrics where run_id in ({marks})"
        " and name like 'tricks/%' order by run_id, step, rowid",
        ids,
    ):
        lift, score = out.setdefault(m["run_id"], ({}, {}))
        parts = m["name"].split("/")
        if len(parts) == 3 and parts[1] in fleet.TRICKS:
            if (
                parts[1] == "logic_test" and parts[2] == "gain"
            ):  # the logic deck's metric is its gain
                lift[parts[1]] = m["value"]
            elif parts[2] == "lift" and parts[1] != "logic_test":
                lift[parts[1]] = m["value"]
            elif parts[2] == "score":
                score[parts[1]] = m["value"]
    return out


def _readings(con, run_id: str) -> tuple[dict, dict]:
    return _readings_many(con, [run_id]).get(run_id, ({}, {}))


FACE_KEYS = ("nevermore", "counter", "scales", "mover")
FACE_NEAR = 0.9  # within 10% of the mark is "near": the reading is at the mark to the eye, not yet held


def _face_marks() -> tuple[dict[str, str], dict[str, float], dict[str, str]]:
    """The four Faces' ability metrics and marks, from the deck itself (never a second copy)."""
    from thorp.viable.s5_policy.deck import BY_KEY

    metrics = {k: BY_KEY[k].ability[0] for k in FACE_KEYS}
    marks = {k: float(BY_KEY[k].ability[1]) for k in FACE_KEYS}
    names = {k: BY_KEY[k].name for k in FACE_KEYS}
    return metrics, marks, names


def _face_readings_many(con, run_ids: list[str]) -> dict[str, dict[str, float]]:
    """Every run's four Face abilities in one round trip: the last reading of each stands, as the
    trick readings do. The Mover is its one-hop ability, not its look: the look is a diffuse head in
    Qwen 3 4B and the 300k alike, so it is not the card's read (11 November)."""
    metrics, _, _ = _face_marks()
    out: dict[str, dict[str, float]] = {}
    ids = [r for r in run_ids if r]
    if not ids:
        return out
    marks = ",".join("?" for _ in ids)
    wanted = ",".join("?" for _ in metrics.values())
    for m in con.execute(
        f"select run_id, name, value from metrics where run_id in ({marks})"
        f" and name in ({wanted}) order by run_id, step, rowid",
        (*ids, *metrics.values()),
    ):
        out.setdefault(m["run_id"], {})[m["name"]] = m["value"]
    return out


def _thorp_runs(internal: bool = False) -> list[dict]:
    """Every run with discovery readings: the chaining tests (public), or the climb (internal)."""
    from thorp.ledger import reader

    con = reader()
    con.row_factory = __import__("sqlite3").Row
    try:
        runs = [
            dict(r) for r in con.execute("select run_id, name, ship, spec_json, status from runs")
        ]
        reads = _readings_many(con, [r["run_id"] for r in runs])
        face_reads = _face_readings_many(con, [r["run_id"] for r in runs])
        out = []
        for r in runs:
            lift, score = reads.get(r["run_id"], ({}, {}))
            if not lift:
                continue
            reading = climb(lift, score) if internal else chaining(lift, score)
            if not internal and reading["chaining_lift"] is None:
                continue
            out.append(
                {
                    "run": r["name"],
                    "run_id": r["run_id"],
                    "ship": r["ship"],
                    "preset": json.loads(r["spec_json"]).get("model", {}).get("preset"),
                    "ship_key": fleet.ship_key(json.loads(r["spec_json"])),
                    "status": r["status"],
                    "faces": face_reads.get(r["run_id"], {}),
                    **reading,
                }
            )
        return out
    finally:
        con.close()


def _reference(internal: bool = False) -> list[dict]:
    from thorp.viable.s4_intelligence import readings

    models = readings.chain_grades()
    if not models:
        return []
    out = []
    for name in list(fleet.REFERENCE_LADDER) + [
        m for m in fleet.COMPETITORS if m not in fleet.REFERENCE_LADDER
    ]:
        v = models.get(name)
        if not v:
            continue
        lift, score = (
            {k: x["lift"] for k, x in v.items() if isinstance(x, dict) and "lift" in x},
            {k: x["score"] for k, x in v.items() if isinstance(x, dict) and "score" in x},
        )
        out.append(
            {
                "model": name,
                "competitor": name in fleet.COMPETITORS,
                "label": fleet.COMPETITORS.get(name, (name.split("/")[-1], 0))[0],
                "params": fleet.COMPETITORS.get(name, (None, None))[1],
                **(climb(lift, score) if internal else chaining(lift, score)),
            }
        )
    return out


def _best(runs: list[dict], key) -> dict[str, dict]:
    cls = class_of_preset()
    best: dict[str, dict] = {}
    for r in runs:
        g = cls.get(r["preset"])
        if g is not None and (g not in best or key(r) > key(best[g])):
            best[g] = r
    return best


def _ships(runs: list[dict]) -> list[dict]:
    """Runs grouped by ship (a class and a fitout; its runs are its sailings, the seeds): each
    chaining test's lift and share averaged over the sailings, so a lucky seed is not a best ship."""
    by: dict[str, list[dict]] = {}
    for r in runs:
        by.setdefault(r["ship_key"], []).append(r)
    out = []
    import re

    for key, rs in by.items():
        label = re.sub(r"\s*\(seed \d+\)$", "", rs[0]["ship"] or rs[0]["run"])
        tests = {}
        for k in chaining_tests():
            lifts = [r["tests"][k]["lift"] for r in rs]
            shares = [r["tests"][k]["score"] for r in rs]
            lift, share = sum(lifts) / len(lifts), sum(shares) / len(shares)
            m = {fleet.TRICKS[k].metric: lift, f"tricks/{k}/score": share}
            tests[k] = {
                "name": fleet.TRICKS[k].name,
                "lift": round(lift, 4),
                "score": round(share, 3),
                "performed": fleet.performed(k, m),
            }
        logics = [r["logic"] for r in rs if r.get("logic")]
        logic = None
        if logics:
            g = sum(x["gain"] for x in logics) / len(logics)
            sc = sum(x["score"] for x in logics) / len(logics)
            logic = {
                "gain": round(g, 4),
                "score": round(sc, 3),
                "sailings": len(logics),
                "performed": fleet.performed(
                    "logic_test",
                    {fleet.TRICKS["logic_test"].metric: g, "tricks/logic_test/score": sc},
                ),
            }
        out.append(
            {
                "logic": logic,
                "ship": label,
                "ship_key": key,
                "preset": rs[0]["preset"],
                "sailings": len(rs),
                "runs": sorted(r["run"] for r in rs),
                "run": max(rs, key=lambda r: r["chaining_lift"])["run"],
                "run_id": max(rs, key=lambda r: r["chaining_lift"])["run_id"],
                "chaining_lift": round(sum(t["lift"] for t in tests.values()) / len(tests), 4),
                "passed": sum(t["performed"] for t in tests.values()),
                "tests": tests,
            }
        )
    return out


def faces(runs: list[dict] | None = None) -> dict:
    """The Face scorecard: the four Faces' abilities — the Nevermore's copy gain, the Counter's
    sentence-position R², the Scales' order gain and the Mover's one-hop lift — with the mark each
    must reach. The fleet is each class's best of its ships for that Face (the run that gave it is
    kept); the reference is Qwen 3 4B, the chainer the fleet is measured against (11 November,
    Justin: "put the Face scorecard on the leaderboard")."""
    from thorp.models.registry import LADDER, PRESETS
    from thorp.viable.s4_intelligence import readings

    metrics, marks, names = _face_marks()
    runs = runs if runs is not None else _thorp_runs()
    order = {r["preset"]: i for i, r in enumerate(LADDER)}
    size_name = {r["preset"]: r.get("name") or r["preset"] for r in LADDER}
    by: dict[str, list[dict]] = {}
    for r in runs:
        if r.get("preset") in PRESETS:  # the ladder's classes; a cut-down variant is not a class
            by.setdefault(r["preset"], []).append(r)
    fleet_rows = []
    for preset in sorted(by, key=lambda p: order.get(p, 99)):
        row: dict = {"preset": preset, "name": size_name.get(preset, preset), "values": {}, "from": {}, "held": [], "near": []}
        for k in FACE_KEYS:
            vals = [(r.get("faces", {}).get(metrics[k]), r) for r in by[preset]]
            vals = [(v, r) for v, r in vals if v is not None]
            if not vals:
                continue
            v, r = max(vals, key=lambda x: x[0])
            row["values"][k] = round(float(v), 4)
            row["from"][k] = f"{r['run']} · {r['run_id'][:8]}"  # the run id tells the seeds apart
            if v >= marks[k]:
                row["held"].append(k)
            elif v >= FACE_NEAR * marks[k]:
                row["near"].append(k)
        if row["values"]:
            fleet_rows.append(row)
    qwen = "mlx-community/Qwen3-4B-4bit"
    reference = []
    deck = readings.get("deck-" + qwen.replace("/", "--"))
    if deck:
        m = deck.get("metrics") or {}
        row = {
            "model": qwen,
            "label": fleet.COMPETITORS.get(qwen, ("Qwen3 4B", None))[0],
            "params": fleet.COMPETITORS.get(qwen, (None, None))[1],
            "values": {},
            "held": [],
            "near": [],
        }
        for k in FACE_KEYS:
            v = m.get(metrics[k])
            if v is None:
                continue
            row["values"][k] = round(float(v), 4)
            if v >= marks[k]:
                row["held"].append(k)
            elif v >= FACE_NEAR * marks[k]:
                row["near"].append(k)
        reference.append(row)
    return {
        "marks": marks,
        "names": names,
        "near": FACE_NEAR,
        "fleet": fleet_rows,
        "reference": reference,
        "source": "the four Face cards' ability readings (thorp/viable/s5_policy/deck.py): the fleet's best of each class, the reference Qwen 3 4B",
    }


def _thorp_arc(board: list[dict]) -> dict | None:
    """The best ARC-AGI-2 reading any of the board's best ships holds, with the pilot's size.

    ARC scores are only written by the ARC evaluator or a rescore (`thorp eval <run> --evaluators arc`);
    a ship without one is simply absent, never scored zero."""
    from thorp.ledger import reader

    rec = reader()
    best = None
    for row in board:
        b = row.get("best")
        if not b:
            continue
        score = rec.metric_at(b["run_id"], "arc/pass@2", "last")
        tasks = rec.metric_at(b["run_id"], "arc/tasks", "last")
        if score is None or tasks is None or not int(tasks):
            continue
        pilot = rec.metric_at(b["run_id"], "arc/pilot", "last")
        key = (float(score), int(tasks), not bool(pilot))
        if best is None or key > best["_key"]:
            best = {
                "_key": key,
                "score": round(float(score), 4),
                "tasks": int(tasks) if tasks is not None else None,
                "pilot": bool(pilot) if pilot is not None else None,
                "run": b.get("run"),
                "ship": b.get("ship"),
                "note": (
                    f"{int(tasks)}-task pilot, not the 120-task score"
                    if tasks is not None and pilot
                    else "our own reading"
                ),
            }
    if best is not None:
        best.pop("_key", None)
    return best


def payload() -> dict:
    """The public leaderboard: the four chaining tests only, best in class by ship (its sailings
    averaged)."""
    runs = _thorp_runs()
    ships = _ships(runs)
    # a best in class needs two sailings (two seeds) where its class has any such ship: the luckiest
    # of many single runs is not a result
    cls = class_of_preset()
    seeded = {cls.get(r["preset"]) for r in ships if r["sailings"] >= 2}
    eligible = [r for r in ships if r["sailings"] >= 2 or cls.get(r["preset"]) not in seeded]
    best = _best(eligible, lambda r: (r["chaining_lift"], r["passed"], r["sailings"]))
    # the named version of each class replaces the raw best where it is crowned
    crowned = crown(eligible)
    by_key = {sh["ship_key"]: sh for sh in ships}
    for g_preset, ver in crowned.items():
        sh = by_key.get(ver["ship_key"])
        g = class_of_preset().get(g_preset)
        if sh and g:
            best[g] = {**sh, "name": name_of(g_preset, ver["v"]), "version": ver["v"]}
    board, below = [], None
    for rung in fleet.RUNGS:
        b = best.get(rung.goal_class)
        row = {"class": rung.goal_class, "title": rung.title, "best": b, "chaining_rising": False}
        if b:
            cl, bl = b["chaining_lift"], (below or {}).get("chaining_lift")
            row["chaining_rising"] = (
                cl > CHAINING_NOISE and b["sailings"] >= 2 and (bl is None or cl > bl)
            )
            below = b
        board.append(row)
    # one table, outside models and Nothing up my sleeve's versions together (Justin, 12:55: "do it"): a model is
    # ranked only when its chaining lift clears the noise (a Nothing up my sleeve ship on two sailings or more);
    # everything inside the noise band is one group, "not yet chaining", sorted by size, because
    # an order among readings that are all noise is a coin toss, not a result
    table = _table(board, _reference())
    return {
        "table": table,
        # the three size classes (small up to 4B, medium up to 30B, large above 30B) and, for the
        # classes with no chaining reading yet, the five likeliest candidates to approach
        "size_classes": candidates.size_classes(),
        "candidates": candidates.rows(),
        # the canonical intelligence ranking: the published ARC-AGI-2 scores, and Nothing up my sleeve's
        # own reading once the Kipling ARC arm has one (thorp/arc.py; scripts/score_arc.py)
        "reasoning": {
            "name": "ARC-AGI-2",
            "about": arc_scores.ABOUT,
            "published": arc_scores.rows(),
            "measured": arc_scores.measured_rows(),
            "thorp": _thorp_arc(board),
        },
        "tests": [{"key": k, "name": fleet.TRICKS[k].name} for k in chaining_tests()],
        # the logic deck's chaining gain: the proof that the four tests are passed by chaining
        "logic": {
            "key": "logic_test",
            "name": fleet.TRICKS["logic_test"].name,
            "threshold": fleet.TRICKS["logic_test"].threshold,
        },
        "board": board,
        "ships": sorted(ships, key=lambda r: (-r["chaining_lift"], r["ship"])),
        "runs": sorted(runs, key=lambda r: (-r["chaining_lift"], r["run"])),
        "reference": _reference(),
        "faces": faces(runs),
        "threshold": fleet.TRICKS[chaining_tests()[0]].threshold,
        "min_share": fleet.TRICKS[chaining_tests()[0]].min_score,
        "noise": CHAINING_NOISE,
    }


# ------------------------------------------------------------------------------------- versions
# Justin (12:40): Nothing up my sleeve's entry on the leaderboard is named by class and version ("Nothing up my sleeve 300k v1").
# A class's version rises only when a new ship beats the current one by more than the noise, so a
# lucky seed never mints a version; among ships tied within the noise, the crown goes to the one with
# complete readings (the logic deck read), then more sailings, then the higher chaining lift.
CROWNED = "%Y-%m-%dT%H:%M"  # as the register has always been read


def _versions() -> dict:
    """The register of versions (s1.crownings): preset -> its crownings in order, {v, ship_key, ship,
    chaining_lift, crowned}."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Crowning

    out: dict[str, list[dict]] = {}
    with store.session() as s:
        for r in s.scalars(select(Crowning).order_by(Crowning.preset, Crowning.v)):
            out.setdefault(r.preset, []).append({"v": r.v, "ship_key": r.ship_key, "ship": r.ship,
                                                 "chaining_lift": r.chaining_lift, "crowned": r.crowned.astimezone().strftime(CROWNED)})  # fmt: skip
    return out


def put_crowning(preset: str, h: dict) -> None:
    from datetime import datetime

    from thorp import store
    from thorp.viable.records import Crowning

    with store.session() as s:
        s.merge(Crowning(preset=preset, v=int(h["v"]), ship_key=h["ship_key"], ship=h["ship"],
                         chaining_lift=float(h["chaining_lift"]), crowned=datetime.fromisoformat(h["crowned"]).astimezone()))  # fmt: skip


def crown(ships: list[dict]) -> dict[str, dict]:
    """preset -> its current version {v, ship_key, ship, chaining_lift, crowned}, updating the register."""
    import time

    reg = _versions()
    by: dict[str, list[dict]] = {}
    for sh in ships:
        by.setdefault(sh["preset"], []).append(sh)
    for preset, cands in by.items():
        top = max(c["chaining_lift"] for c in cands)
        tied = [c for c in cands if c["chaining_lift"] >= top - CHAINING_NOISE]
        pick = max(
            tied, key=lambda c: (c.get("logic") is not None, c["sailings"], c["chaining_lift"])
        )
        hist = reg.setdefault(preset, [])
        cur = hist[-1] if hist else None
        if cur is None or (
            pick["ship_key"] != cur["ship_key"]
            and pick["chaining_lift"] > cur["chaining_lift"] + CHAINING_NOISE
        ):
            h = {
                "v": len(hist) + 1,
                "ship_key": pick["ship_key"],
                "ship": pick["ship"],
                "chaining_lift": pick["chaining_lift"],
                "crowned": time.strftime(CROWNED),
            }
            hist.append(h)
            put_crowning(preset, h)
    return {p: h[-1] for p, h in reg.items() if h}


def name_of(preset: str, v: int) -> str:
    return f"Nothing up my sleeve {preset} v{v}"


def thorp_entry(ship_key: str) -> dict | None:
    """A Nothing up my sleeve ship in the same shape as an outside model's entry in chain-grades.json (every rung,
    the logic deck, the five cards), its sailings averaged: for its page, built like a competitor's."""
    from thorp.ledger import reader

    con = reader()
    con.row_factory = __import__("sqlite3").Row
    try:
        rows = [
            dict(r)
            for r in con.execute(
                "select run_id, name, ship, spec_json from runs where status='finished'"
            )
        ]
        sail = [r for r in rows if fleet.ship_key(json.loads(r["spec_json"])) == ship_key]
        if not sail:
            return None

        def last(rid: str, name: str):
            r = con.execute(
                "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
                [rid, name],
            ).fetchone()
            return None if r is None else r["value"]

        def mean(name: str):
            vals = [v for r in sail if (v := last(r["run_id"], name)) is not None]
            return sum(vals) / len(vals) if vals else None

        out: dict = {}
        for c in fleet.chains():
            for k in c[:-1]:
                lift, share = mean(f"tricks/{k}/lift"), mean(f"tricks/{k}/score")
                if lift is not None:
                    m = {fleet.TRICKS[k].metric: lift, f"tricks/{k}/score": share or 0.0}
                    out[k] = {"lift": lift, "score": share, "performed": fleet.performed(k, m)}
        g = mean("tricks/logic_test/gain")
        if g is not None:
            lg = {
                "gain": g,
                "score": mean("tricks/logic_test/score"),
                "lift_both": mean("tricks/logic_test/lift"),
            }
            for v in ("first", "second", "swapped", "padded", "one_hop", "three_hop"):
                lg[f"lift_{v}"] = mean(f"tricks/logic_test/lift_{v}")
            for rel in ("order", "cause", "membership", "proportion", "counterfactual"):
                lg[f"gain_{rel}"] = mean(f"tricks/logic_test/gain_{rel}")
            lg["lift"] = g
            lg["performed"] = fleet.performed(
                "logic_test",
                {
                    fleet.TRICKS["logic_test"].metric: g,
                    "tricks/logic_test/score": lg["score"] or 0.0,
                },
            )
            out["logic_test"] = lg
        cards: dict = {"attention_readable": True}
        for key, one, two, layer in (
            (
                "previous_word",
                "stars/previous_word/max_score",
                "stars/previous_word/shared_score",
                "stars/previous_word/shared_layer",
            ),
            (  # two heads of a layer together as well (2026-11-07, 23:45), as the deck reads induction
                "nevermore",
                "nevermore/natural_max_score",
                "nevermore/natural_shared_score",
                "nevermore/natural_best_layer",
            ),
            (
                "mover",
                "stars/mover/max_score",
                "stars/mover/shared_score",
                "stars/mover/shared_layer",
            ),
            (
                "comparator",
                "stars/comparator/max_score",
                "stars/comparator/shared_score",
                "stars/comparator/shared_layer",
            ),
        ):
            mx_ = mean(one)
            if mx_ is None:
                continue
            sh = mean(two) if two else None
            th = fleet.STARS[key].threshold
            cards[key] = {
                "max": mx_,
                "shared": sh,
                "shared_layer": mean(layer),
                "lit": mx_ >= th,
                "lit_shared": sh is not None and sh >= th,
            }
        if "nevermore" in cards:
            cards["nevermore"]["copy_gain"] = mean("nevermore/natural_copy_gain")
        bm = mean("stars/bridge/max_score")
        if bm is not None:
            curve, i = [], 0
            while (v := mean(f"stars/bridge/layer_{i}")) is not None:
                curve.append(v)
                i += 1
            cards["bridge"] = {
                "max": bm,
                "best_layer": mean("stars/bridge/best_layer"),
                "layers": len(curve),
                "curve": curve,
                "lit": bm >= fleet.STARS["bridge"].threshold,
            }
        out["cards"] = cards
        spec = json.loads(sail[0]["spec_json"])
        out["_ship"] = {
            "ship_key": ship_key,
            "ship": sail[0]["ship"],
            "preset": spec["model"]["preset"],
            "sailings": len(sail),
            "runs": sorted(r["name"] for r in sail),
        }
        return out
    finally:
        con.close()


def _params_of_ship(sh: dict) -> int | None:
    from thorp.ledger import reader

    con = reader()
    try:
        r = con.execute("select spec_json from runs where run_id=?", [sh["run_id"]]).fetchone()
    finally:
        con.close()
    if not r:
        return None
    from thorp.smoking_qwen import _params

    return _params(json.loads(r[0]))


def _table(board: list[dict], reference: list[dict]) -> list[dict]:
    from thorp.smoking_qwen import REFERENCE_PARAMS

    measured_arc = arc_scores.measured()
    rows = []
    for r in reference:
        rows.append(
            {
                "kind": "competitor" if r["competitor"] else "ladder",
                "name": r["label"],
                "model": r["model"],
                "params": REFERENCE_PARAMS.get(r["model"]) or r.get("params"),
                "chaining_lift": r["chaining_lift"],
                "passed": r["passed"],
                "logic": r.get("logic"),
                "arc": arc_scores.for_model(r["model"]) or measured_arc.get(r["model"]),
                "sailings": None,
                "clears_noise": r["chaining_lift"] is not None
                and r["chaining_lift"] > CHAINING_NOISE,
            }
        )
    for row in board:
        b = row["best"]
        if not b:
            continue
        rows.append(
            {
                "kind": "thorp",
                "name": b.get("name") or f"Nothing up my sleeve {b['preset']}",
                "ship": b["ship"],
                "ship_key": b["ship_key"],
                "params": _params_of_ship(b),
                "chaining_lift": b["chaining_lift"],
                "passed": b["passed"],
                "logic": b.get("logic"),
                "arc": None,
                "sailings": b["sailings"],
                "clears_noise": b["chaining_lift"] > CHAINING_NOISE and b["sailings"] >= 2,
            }
        )
    # the approach board (Justin, 12:50: "one that tracks the closest to achieving chaining"): below
    # the line, closeness is the necessary cards held (every model that chains holds all four) and
    # then the one-hop lift on the logic deck (following one stated premise: the step before two)
    for r in rows:
        cards, one_hop, cause = _inside_of(r)
        r["cause_gain"] = (
            cause  # the logic deck's chaining gain on cause and effect (Justin, 13:15)
        )
        r["cards_held"] = (
            sum(bool(cards.get(c)) for c in NECESSARY_CARDS) if cards is not None else None
        )
        r["cards"] = cards
        r["one_hop"] = one_hop
    ranked = sorted((r for r in rows if r["clears_noise"]), key=lambda r: -r["chaining_lift"])

    # below the line: cards held, then the one-hop lift in steps of ONE_HOP_NOISE, so readings within
    # the noise of each other tie (and share a rank, listed bigger first: a neutral order, not a claim)
    def band(r):
        oh = r["one_hop"]
        return -9 if oh is None else round(oh / ONE_HOP_NOISE)

    approach = sorted(
        (r for r in rows if not r["clears_noise"]),
        key=lambda r: (-(r["cards_held"] or 0), -band(r), -(r["params"] or 0)),
    )
    for i, r in enumerate(ranked, 1):
        r["rank"], r["group"], r["tied"] = i, "chaining", False
    rank, prev = 0, None
    for i, r in enumerate(approach, 1):
        key = (r["cards_held"] or 0, band(r))
        if key != prev:
            rank, prev = i, key
        r["rank"], r["group"] = rank, "approaching"
    for r in approach:
        r["tied"] = sum(1 for x in approach if x["rank"] == r["rank"]) > 1
    # the size class each row belongs to: small (up to 4B), medium (up to 30B), large (above 30B)
    for r in ranked + approach:
        r["size_class"] = candidates.size_class(r.get("params"))
    return ranked + approach


NECESSARY_CARDS = ("previous_word", "nevermore", "mover", "comparator")


def _inside_of(row: dict) -> tuple[dict | None, float | None, float | None]:
    """(card -> lit, by one head or a layer's best two; the logic deck's one-hop lift), from
    chain-grades.json for an outside model, from the ledger for a Nothing up my sleeve ship."""
    if row["kind"] == "thorp":
        e = thorp_entry(row["ship_key"]) or {}
    else:
        from thorp.viable.s4_intelligence import readings

        e = readings.chain_grades().get(row["model"], {})
    c = e.get("cards") or {}
    one_hop = (e.get("logic_test") or {}).get("lift_one_hop")
    cause = (e.get("logic_test") or {}).get("gain_cause")
    if not c or c.get("attention_readable") is False:  # unreadable is not zero (Gemma 2)
        return None, one_hop, cause
    lit = {
        k: bool((c.get(k) or {}).get("lit") or (c.get(k) or {}).get("lit_shared"))
        for k in NECESSARY_CARDS
    }
    return lit, one_hop, cause


def internal() -> dict:
    """The internal climb (every rung of the four chains): for the two-fact voyage's page only."""
    runs = _thorp_runs(internal=True)
    best = _best(
        runs, lambda r: (r["climb"], r["chaining_lift"] if r["chaining_lift"] is not None else -9)
    )
    return {"best": best, "runs": runs, "reference": _reference(internal=True)}


def main() -> None:
    p = payload()
    print("Chaining two facts:", ", ".join(t["name"] for t in p["tests"]))
    print(f"{'class':10} {'best ship':28} {'chaining lift':>14} {'passed':>7}")
    for row in p["board"]:
        b = row["best"]
        if b:
            print(
                f"{row['class']:10} {b['run']:28} {b['chaining_lift']:+14.3f} {b['passed']:5}/4"
                + ("  rising" if row["chaining_rising"] else "")
            )
        else:
            print(f"{row['class']:10} {'(none yet)':28}")
    print("\noutside models:")
    for r in p["reference"]:
        print(
            f"  {r['label']:22} chaining lift {r['chaining_lift']:+.3f}  passed {r['passed']}/4"
            + ("  (competitor)" if r["competitor"] else "")
        )


if __name__ == "__main__":
    main()
