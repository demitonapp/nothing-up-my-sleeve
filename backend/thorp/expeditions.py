"""What a voyage has found so far, read from the fleet types and the ledger (2026-11-07).

`payload()` is the dashboard's /api/voyages: every voyage in `thorp.fleet.EXPEDITIONS` with its goal,
outcomes, levers, stop rule, ships, status and lessons, and every run that belongs to it, each with
its settings, its Forgotten Tomes score and, for every star, the step and the tokens at which it
first lit (`steps_to_lit`), or its best score so far if it has not.

    uv run python -m thorp.voyages first_light     # a plain-text summary, for the steering session
"""

from __future__ import annotations

import json
import sys

from thorp import fleet, paths
from thorp.ledger import connect

FT = "eval/hole-cards-unseen/bpb_mean_en"


def _rows(sql: str, params=()) -> list[dict]:
    con = connect(readonly=True)
    con.row_factory = __import__("sqlite3").Row
    try:
        return [dict(r) for r in con.execute(sql, list(params))]
    finally:
        con.close()


def runs_of(voyage: fleet.Expedition) -> list[dict]:
    """Its runs: those whose label carries its ship ("<ship>: ..."), and every run that
    `fleet.expedition_of_label` gives it (the card census's runs are labelled as the fitout's variations,
    "Fitout: Thorp ...", not "Cards: ...")."""
    if voyage.key == "book_value":
        where, args = "name like 'loop-%'", []
    else:
        where, args = "ship like ?", [voyage.ship + ":%"]  # its run label, not its display name
    cols = "run_id, name, ship, status, tokens_seen, spec_json, started"
    rows = _rows(f"select {cols} from runs where {where} order by started", args)
    seen = {r["run_id"] for r in rows}
    rows += [
        r
        for r in _rows(f"select {cols} from runs order by started")
        if r["run_id"] not in seen and fleet.expedition_of_label(r["name"], r["ship"]) == voyage.key
    ]
    rows.sort(key=lambda r: r["started"] or "")
    for r in rows:
        r.pop("started")
    return rows


def star_timeline(run_id: str, star: fleet.Star, tokens_per_step: int) -> dict:
    pts = _rows(
        "select step, value from metrics where run_id=? and name=? order by step, rowid",
        [run_id, star.metric],
    )
    lit = next((p["step"] for p in pts if p["value"] >= star.threshold), None)
    shared = _shared_series(run_id, star) if star.shared_metric else []
    shared_lit = next((p["step"] for p in shared if p["value"] >= star.threshold), None)
    return {
        "star": star.key,
        "threshold": star.threshold,
        "steps_to_lit": lit,
        "tokens_to_lit": lit * tokens_per_step if lit is not None else None,
        "best": max((p["value"] for p in pts), default=None),
        "latest": pts[-1]["value"] if pts else None,
        "readings": len(pts),
        # lit shared: the best layer's two strongest heads together (Justin, 07:35)
        "shared_steps_to_lit": shared_lit,
        "shared_tokens_to_lit": shared_lit * tokens_per_step if shared_lit is not None else None,
        "shared_best": max((p["value"] for p in shared), default=None),
        "shared_latest": shared[-1]["value"] if shared else None,
    }


def _shared_series(run_id: str, star: fleet.Star) -> list[dict]:
    """The shared score by step: from its metric where recorded, otherwise worked out from the
    'stars' artifacts, which hold every head's score at every reading (so runs scored before the
    metric existed have it too)."""
    pts = _rows(
        "select step, value from metrics where run_id=? and name=? order by step, rowid",
        [run_id, star.shared_metric],
    )
    if pts:
        return pts
    out = {}
    for a in _rows(
        "select step, text from artifacts where run_id=? and kind='stars' order by step, rowid",
        [run_id],
    ):
        m = json.loads(a["text"] or "{}").get(star.key)
        if m:
            out[a["step"]] = max(sum(sorted(row)[-2:]) for row in m)
    return [{"step": k, "value": v} for k, v in sorted(out.items())]


def run_summary(r: dict, voyage: fleet.Expedition) -> dict:
    ship = fleet.ship_of_run(r, save=False) if r.get("spec_json") else None
    spec = json.loads(r.pop("spec_json") or "{}")
    tps = spec.get("optim", {}).get("batch_tokens", 32768)
    ft = _rows(
        "select step, value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
        [r["run_id"], FT],
    )
    stars = [star_timeline(r["run_id"], fleet.STARS[s], tps) for s in fleet.STARS]
    return {
        **r,
        "ship_key": ship.key if ship else None,
        "ship_name": ship.name if ship else r.get("ship"),
        "preset": ship.preset if ship else None,
        "size": ship.size if ship else None,
        "settings": {
            "vocab": spec.get("tokeniser", {}).get("vocab"),
            "lr": spec.get("optim", {}).get("lr"),
            "recipe": spec.get("data", {}).get("recipe"),
            "passes": spec.get("data", {}).get("passes"),
            "seed": spec.get("seed"),
        },
        "ft_en": ft[0]["value"] if ft else None,
        "stars": stars,
    }


def ships_of(runs: list[dict]) -> list[dict]:
    """A voyage's ships: its runs grouped by ship (a class and a fitout), each ship's sailings, its
    soonest step to each star, its mean steps to each star over sailings that lit it, and its mean
    Forgotten Tomes score."""
    reg = fleet.register()
    groups: dict[str, list[dict]] = {}
    for r in runs:
        if not r.get("set_aside"):
            groups.setdefault(r.get("ship_key") or r["name"], []).append(r)
    out = []
    for key, rs in groups.items():
        s = reg.get(key)
        stars = {}
        for st in fleet.STARS:
            lit = [
                x["steps_to_lit"]
                for r in rs
                for x in r["stars"]
                if x["star"] == st and x["steps_to_lit"] is not None
            ]
            best = [
                x["best"]
                for r in rs
                for x in r["stars"]
                if x["star"] == st and x["best"] is not None
            ]
            shared = [
                x["shared_steps_to_lit"]
                for r in rs
                for x in r["stars"]
                if x["star"] == st and x.get("shared_steps_to_lit") is not None
            ]
            stars[st] = {
                "lit_shared": len(shared),
                "soonest_shared": min(shared) if shared else None,
                "lit": len(lit),
                "soonest": min(lit) if lit else None,
                "mean_steps_to_lit": sum(lit) / len(lit) if lit else None,
                "best": max(best) if best else None,
            }
        fts = [r["ft_en"] for r in rs if r["ft_en"] is not None]
        out.append(
            {
                "key": key,
                "name": s.name if s else rs[0]["ship_name"],
                "preset": s.preset if s else rs[0]["preset"],
                "size": s.size if s else rs[0]["size"],
                "subtitle": s.subtitle if s else "",
                "archived": s.archived if s else None,
                "sailings": [r["name"] for r in rs],
                "ft_en_mean": sum(fts) / len(fts) if fts else None,
                "stars": stars,
            }
        )
    return out


def summary(key: str) -> dict:
    v = fleet.EXPEDITIONS[key]
    out = {
        "key": v.key,
        "name": v.name,
        "goal": v.goal,
        "status": v.status,
        "fleet": v.fleet,
        "preset": v.preset,
        "ships": list(v.ships),
        "outcomes": [o.__dict__ for o in v.outcomes],
        "levers": [lv.__dict__ for lv in v.levers],
        "stop": v.stop.__dict__,
        "learned": v.learned,
        "next_steps": list(v.next_steps),
        "runs": [run_summary(r, v) for r in runs_of(v)],
        "stars": list(v.stars),
    }
    if key == "book_value":
        f = paths.data_dir() / "loop/fit.json"
        out["fit"] = json.loads(f.read_text()) if f.exists() else None
        rows = paths.data_dir() / "loop/runs.csv"
        if (
            rows.exists()
        ):  # a run the loop set aside (loop-0001, superseded) is marked, not shown as valid
            import csv

            bad = {
                x["run"]: x["exit"]
                for x in csv.DictReader(open(rows, encoding="utf-8"))
                if x["exit"] != "0"
            }
            for r in out["runs"]:
                r["set_aside"] = bad.get(r["name"])
    out["ships"] = ships_of(out["runs"])
    return out


def payload() -> list[dict]:
    return [summary(k) for k in fleet.EXPEDITIONS]


def main() -> None:
    s = summary(sys.argv[1] if len(sys.argv) > 1 else "first_light")
    print(f"{s['name']} ({s['status']}): {s['goal']}")
    for r in s["runs"]:
        lit = ", ".join(
            f"{x['star']} lit at step {x['steps_to_lit']}"
            if x["steps_to_lit"] is not None
            else f"{x['star']} best {x['best'] if x['best'] is None else round(x['best'], 3)}"
            for x in r["stars"]
        )
        ft = "–" if r["ft_en"] is None else f"{r['ft_en']:.3f}"
        print(f"  {r['name']:28} {r['status'][:8]:8} FT {ft}  {lit}")


def overview() -> dict:
    """The Expeditions page's head (Justin, 16:25: "which expeditions are currently running and where
    the queue is at"): the voyage at sea now, each expedition's voyages finished, failed and still
    queued with the place of its next one in the queue, and the queue's length and rough time left
    (each queued voyage at its class's mean wall time over finished voyages)."""
    import collections

    import yaml

    from thorp import vsm

    at_sea = _rows(
        "select run_id, name, ship, started from runs where status='running' order by started desc"
    )
    wall = {
        r["p"]: r["m"]
        for r in _rows(
            "select json_extract(spec_json,'$.model.preset') p, avg(wall_minutes) m from runs "
            "where status='finished' and wall_minutes > 0 group by p"
        )
    }
    q = paths.resolve("specs/queue.txt")
    lines = [
        ln.strip() for ln in q.read_text().splitlines() if ln.strip() and not ln.startswith("#")
    ]
    queued: dict[str, list[int]] = collections.defaultdict(list)
    minutes, steps, unknown = 0.0, 0, 0
    for i, ln in enumerate(lines, 1):
        if ln.startswith("cmd:"):
            steps += 1
            continue
        p = paths.resolve(f"specs/{ln}.yaml")
        spec = yaml.safe_load(p.read_text()) if p.exists() else {}
        key = fleet.expedition_of_label(spec.get("name"), spec.get("ship")) or "(no expedition)"
        queued[key].append(i)
        m = wall.get((spec.get("model") or {}).get("preset"))
        minutes += m or 0.0
        unknown += m is None
    done = collections.Counter()
    for r in _rows("select name, ship, status from runs"):
        k = fleet.expedition_of_label(r["name"], r["ship"]) or "(no expedition)"
        done[
            (
                k,
                "finished"
                if r["status"] == "finished"
                else "at sea"
                if r["status"] == "running"
                else "failed",
            )
        ] += 1
    keys = list(fleet.EXPEDITIONS) + (["(no expedition)"] if "(no expedition)" in queued else [])
    states = vsm.expedition_states()
    exps = []
    for k in keys:
        e = fleet.EXPEDITIONS.get(k)
        exps.append(
            {
                "key": k,
                "name": e.name if e else k,
                "status": states.get(
                    k, ""
                ),  # S2's view: at sea, under way, in port, home, awaiting orders
                "declared": e.status if e else "",
                "at_sea": done[(k, "at sea")],
                "finished": done[(k, "finished")],
                "failed": done[(k, "failed")],
                "queued": len(queued.get(k, [])),
                "next_in_queue": queued[k][0] if queued.get(k) else None,
            }
        )
    exps.sort(key=lambda x: (-x["at_sea"], x["next_in_queue"] or 10**9, x["key"]))
    return {
        "at_sea": [
            {**r, "expedition": fleet.expedition_of_label(r["name"], r["ship"])} for r in at_sea
        ],
        "helm": vsm.helm(),
        "queue": {
            "voyages": sum(len(v) for v in queued.values()),
            "steps": steps,
            "hours_left": round(minutes / 60, 1),
            "voyages_without_a_time": unknown,
            "lints": vsm.lint_queue(),
        },
        "expeditions": exps,
    }


if __name__ == "__main__" and sys.argv[1:] == ["overview"]:
    o = overview()
    for r in o["at_sea"]:
        print("at sea:", r["name"], "of", r["expedition"], "since", r["started"])
    qq = o["queue"]
    print(f"queue: {qq['voyages']} voyages, {qq['steps']} steps, about {qq['hours_left']} hours")
    for e in o["expeditions"]:
        if e["at_sea"] or e["queued"]:
            print(
                f"  {e['key']:16} at sea {e['at_sea']}  queued {e['queued']:3}  next at #{e['next_in_queue']}  finished {e['finished']}  failed {e['failed']}"
            )
elif __name__ == "__main__":
    main()
