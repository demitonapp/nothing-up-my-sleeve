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

from thorp import expedition_goals, fleet, paths
from thorp.ledger import connect

FT = "eval/hole-cards-unseen/bpb_mean_en"


def _rows(sql: str, params=()) -> list[dict]:
    from thorp.ledger import reader

    return reader().query(sql, params)


def runs_of(voyage: fleet.Expedition) -> list[dict]:
    """Its runs: those whose label carries its ship ("<ship>: ..."), and every run that
    `fleet.expedition_of_label` gives it (the card census's runs are labelled as the fitout's variations,
    "Fitout: Nothing up my sleeve ...", not "Cards: ...")."""
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
        if r["run_id"] not in seen and fleet.expedition_of_run(r) == voyage.key
    ]
    rows.sort(key=lambda r: r["started"] or "")
    for r in rows:
        r.pop("started")
    return rows


def star_timeline(run_id: str, star: fleet.Star, tokens_per_step: int, pre: dict | None = None) -> dict:
    """`pre` (summary's, 11 November): every run's star series read in one query; without it, two queries a star."""
    pts = pre["series"].get((run_id, star.metric), []) if pre is not None else _rows(
        "select step, value from metrics where run_id=? and name=? order by step, rowid",
        [run_id, star.metric],
    )
    lit = next((p["step"] for p in pts if p["value"] >= star.threshold), None)
    shared = _shared_series(run_id, star, pre) if star.shared_metric else []
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


def _shared_series(run_id: str, star: fleet.Star, pre: dict | None = None) -> list[dict]:
    """The shared score by step: from its metric where recorded, otherwise worked out from the
    'stars' artifacts, which hold every head's score at every reading (so runs scored before the
    metric existed have it too). `pre` as star_timeline's (its "arts": the stars artifacts of the runs that need them)."""
    pts = pre["series"].get((run_id, star.shared_metric), []) if pre is not None else _rows(
        "select step, value from metrics where run_id=? and name=? order by step, rowid",
        [run_id, star.shared_metric],
    )
    if pts:
        return pts
    out = {}
    for a in pre["arts"].get(run_id, []) if pre is not None else _rows(
        "select step, text from artifacts where run_id=? and kind='stars' order by step, rowid",
        [run_id],
    ):
        m = json.loads(a["text"] or "{}").get(star.key)
        if m:
            out[a["step"]] = max(sum(sorted(row)[-2:]) for row in m)
    return [{"step": k, "value": v} for k, v in sorted(out.items())]


def run_summary(r: dict, voyage: fleet.Expedition, pre: dict | None = None) -> dict:
    ship = fleet.ship_of_run(r, save=False) if r.get("spec_json") else None
    spec = json.loads(r.pop("spec_json") or "{}")
    tps = spec.get("optim", {}).get("batch_tokens", 32768)
    if pre is not None:  # the Forgotten Tomes score from s1.metric_latest (summary's prefetch)
        ft = [{"value": pre["ft"][r["run_id"]]}] if r["run_id"] in pre["ft"] else []
    else:
        ft = _rows(
            "select step, value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
            [r["run_id"], FT],
        )
    stars = [star_timeline(r["run_id"], fleet.STARS[s], tps, pre) for s in fleet.STARS]
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


def _seats() -> set[str]:
    """The runs that hold a helm seat now (S2): the authority on what is actually at sea. A run killed
    with a signal never writes a finish, so the ledger can say running for a voyage that stopped hours ago."""
    try:
        from thorp import store, liberty_machine
        from thorp.viable.records import Lane

        with store.session() as s:
            row = s.get(Lane, "mac")
            n = (row.seats if row else 1) or 1
        return {str(h.get("name")) for h in liberty_machine.helms(n) if h.get("name")}
    except Exception:  # noqa: BLE001
        return set()


def _queued() -> set[str]:
    """The voyage names in the standing queue (the store's, 11 November): a run still in the queue is queued, not
    running. A store that cannot be read answers no names, as `_seats` answers no seats."""
    import yaml

    from thorp import store
    from thorp.viable.s2_coordination import queue_read

    out: set[str] = set()
    try:
        pending = queue_read.pending()
    except store.StoreDown:
        return out
    for ln in pending:
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith("cmd:"):
            continue
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            continue
        try:
            spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if spec.get("name"):
            out.add(str(spec["name"]))
    return out


_STATUS_CTX: dict = {"at": 0.0, "seats": set(), "queued": set()}


def _status_ctx() -> tuple[set[str], set[str]]:
    """The seats and the queue, read once per ten seconds across the sixteen expeditions."""
    import time

    now = time.time()
    if now - _STATUS_CTX["at"] > 10.0:
        _STATUS_CTX.update(at=now, seats=_seats(), queued=_queued())
    return _STATUS_CTX["seats"], _STATUS_CTX["queued"]


def _mark_status(runs: list[dict]) -> None:
    """A ledger 'running' without a seat is not at sea: it is queued if it is in the queue, otherwise
    stopped (a killed arm). Only the seat holder stays running."""
    if not any(r.get("status") == "running" for r in runs):
        return
    seats, queued = _status_ctx()
    # a name can have several ledger rows (three dead control arms): only the newest running row per
    # name is the seat holder; the rest stopped. runs_of is in started order, so the last one wins.
    newest: dict[str, dict] = {}
    for r in runs:
        if r.get("status") == "running" and r.get("name") in seats:
            newest[str(r.get("name"))] = r
    for r in runs:
        if r.get("status") != "running":
            continue
        # a run still in the queue is queued whatever a stale helm record says; only the seat
        # holder that is no longer queued is actually at sea
        if r.get("name") in queued:
            r["status"] = "queued"
        elif r.get("name") not in seats:
            r["status"] = "stopped"
        elif newest.get(str(r.get("name"))) is not r:
            r["status"] = "stopped"


def summary(key: str) -> dict:
    v = fleet.EXPEDITIONS[key]
    runs = runs_of(v)
    pre = None
    from thorp.ledger import _use_pg

    if _use_pg() and runs:
        # every run's star series in one query and their Forgotten Tomes scores in another, not two queries a star
        # a run (11 November, the audit's item 7); the stars artifacts only for the runs that lack a shared metric
        from thorp import ledger_store

        ids = [r["run_id"] for r in runs]
        names = sorted({s.metric for s in fleet.STARS.values()} | {s.shared_metric for s in fleet.STARS.values() if s.shared_metric})
        pre = {"series": {}, "arts": {}}
        for x in ledger_store.history_of_pairs([(i, n) for i in ids for n in names]):
            pre["series"].setdefault((x["run_id"], x["name"]), []).append({"step": x["step"], "value": x["value"]})
        pre["ft"] = {x["run_id"]: x["value"] for x in ledger_store.latest_rows(ids, names=(FT,))}
        lack = [i for i in ids if any(s.shared_metric and (i, s.shared_metric) not in pre["series"] for s in fleet.STARS.values())]
        pre["arts"] = ledger_store.artifacts_of_kind_many(lack, "stars")
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
        "plan": list(getattr(v, "plan", ())),
        "goals": expedition_goals.stated(v.key),
        "runs": [run_summary(r, v, pre) for r in runs],
        "stars": list(v.stars),
    }
    _mark_status(out["runs"])
    # an expedition has exactly one SOP (9 November, Justin: "An expedition can only have one SOP and
    # Kipling has 0.0.6"): read it from the standards that name this expedition
    from thorp import sop as _sop

    out["sop"] = next(
        (ver for ver in _sop.versions() if ((_sop.standard(ver) or {}).get("expedition") == key)), None
    )
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

    from thorp import liberty_machine

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
    from thorp.viable.s2_coordination import queue_read

    lines = [ln.strip() for ln in queue_read.pending() if ln.strip()]  # the store's queue (11 November)
    queued: dict[str, list[int]] = collections.defaultdict(list)
    minutes, steps, unknown = 0.0, 0, 0
    for i, ln in enumerate(lines, 1):
        if ln.startswith("cmd:"):
            steps += 1
            continue
        p = paths.resolve(f"specs/{ln}.yaml")
        spec = yaml.safe_load(p.read_text()) if p.exists() else {}
        key = fleet.expedition_of_spec(spec) or "(no expedition)"
        queued[key].append(i)
        m = wall.get((spec.get("model") or {}).get("preset"))
        minutes += m or 0.0
        unknown += m is None
    done = collections.Counter()
    for r in _rows("select run_id, name, ship, status from runs"):
        k = fleet.expedition_of_run(r) or "(no expedition)"
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
    states = liberty_machine.expedition_states()
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
    # the expeditions page's subject is the SOP itself: each version's aim, its art, and whether it is the
    # one at sea (9 November, Justin: "this page should only contain the running SOP which is 0.0.5 ... And
    # then 0.0.6's goals"). Only versions that state an aim appear; the fleet's older groupings stay in
    # `expeditions` for the other tabs.
    from thorp import sop

    sops = []
    for v in sop.versions():
        std = sop.standard(v) or {}
        if not (std.get("goals") or std.get("art")):
            continue
        sops.append(
            {
                "version": v,
                "name": f"SOP v{v}",
                "art": std.get("art"),
                # an expedition that lists its goals one by one speaks for its standard's card too, so the
                # card and the expedition's own page cannot name different goals
                "goals": expedition_goals.stated(std.get("expedition") or "")
                or std.get("goals")
                or [],
                "at_sea": sum(1 for r in at_sea if (r.get("sop") if isinstance(r, dict) else None) == v),
                "queued": 0,
                "finished": 0,
            }
        )
    runs_by_sop = collections.Counter()
    # the Mac lane's runs live in SQLite, where the version is still inside the spec
    import json as _json

    # and which expedition each SOP's voyages belong to: the card opens that expedition's page, not the
    # at-sea tab of nothing (9 November, Justin: clicking a card "should open the SOP card, which is
    # actually the expedition page")
    exp_of_sop: dict[str, collections.Counter] = {}
    for r in _rows("select run_id, name, ship, status, spec_json from runs where spec_json is not null"):
        try:
            v = _json.loads(r["spec_json"]).get("sop")
        except Exception:
            v = None
        if not v:
            continue
        v = str(v)
        runs_by_sop[(v, r["status"])] += 1
        k = fleet.expedition_of_run(r)
        if k:
            exp_of_sop.setdefault(v, collections.Counter())[k] += 1
    for e in sops:
        e["at_sea"] = runs_by_sop[(e["version"], "running")]
        e["finished"] = runs_by_sop[(e["version"], "finished")]
        c = exp_of_sop.get(e["version"])
        std = sop.standard(e["version"]) or {}
        e["expedition"] = (c.most_common(1)[0][0] if c else None) or std.get("expedition")
        exp = fleet.EXPEDITIONS.get(e["expedition"]) if e["expedition"] else None
        e["expedition_name"] = exp.name if exp else None
        e["role"] = exp.plan[0]["kind"] if (exp and exp.plan) else None
    sops.sort(key=lambda e: (-e["at_sea"], e["version"]), reverse=False)
    return {
        "sops": sops,
        "at_sea": [
            {**r, "expedition": fleet.expedition_of_run(r)} for r in at_sea
        ],
        "helm": liberty_machine.helm(),
        "queue": {
            "voyages": sum(len(v) for v in queued.values()),
            "steps": steps,
            "hours_left": round(minutes / 60, 1),
            "voyages_without_a_time": unknown,
            "lints": liberty_machine.lint_queue(),
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
