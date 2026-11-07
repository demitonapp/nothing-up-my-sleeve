"""The dashboard: the Astro build in ./static (source in ./web) plus JSON read straight from the
ledger. Standard library only; `pnpm --dir thorp/dash/web build` makes the page.

Endpoints: /api/runs, /api/metrics?run=, /api/evals?run=, /api/run?run= (headline numbers,
latest samples, probes, recipe composition, traits and tokeniser stats, which the panels need),
/api/ladder (each rung's job, its scores, the queue)
and /api/compare (every run's hole-card score against tokens seen: the experiment's observation).
"""

from __future__ import annotations

import json
import math
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thorp import chinchilla, paths
from thorp.evaluators.probes import load_traits
from thorp.ledger import connect

STATIC = Path(__file__).with_name("static")
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".json": "application/json",
}
NOT_BUILT = b"""<!doctype html><meta charset="utf-8"><title>Thorp</title>
<body style="background:#0e1116;color:#e6edf3;font:14px/1.5 ui-sans-serif,sans-serif;padding:40px">
<h1 style="font-size:18px">The dashboard is not built yet</h1>
<p>Build it once (and after any change under thorp/dash/web), then reload:</p>
<pre style="color:#e3b341">pnpm --dir thorp/dash/web install
pnpm --dir thorp/dash/web build</pre>
<p>The JSON API under /api works without it.</p></body>"""


def _static(path: str) -> tuple[bytes, str] | None:
    """A file from the build, never one outside it."""
    f = (STATIC / path.lstrip("/")).resolve()
    if not f.is_relative_to(STATIC.resolve()) or not f.is_file():
        return None
    return f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream")


def _con() -> sqlite3.Connection:
    return connect(paths.ledger_path(), readonly=True)


def _rows(sql: str, params=()) -> list[dict]:
    con = _con()
    try:
        return [dict(r) for r in con.execute(sql, list(params))]
    finally:
        con.close()


def _metric(run: str, name: str, which: str = "last"):
    order = "desc" if which == "last" else "asc"
    r = _rows(
        f"select step, value from metrics where run_id=? and name=?"
        f" order by step {order}, rowid {order} limit 1",
        [run, name],
    )
    return r[0]["value"] if r else None


def api_runs() -> list[dict]:
    runs = _rows(
        "select run_id, name, ship, status, started, finished, tokens_seen, wall_minutes,"
        ' "commit", hardware, spec_json from runs order by started desc'
    )
    for r in runs:
        spec = json.loads(r.pop("spec_json") or "{}")
        r["preset"] = spec.get("model", {}).get("preset")
        r["seed"] = spec.get("seed")
        sets = [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]
        r["hole_bpb_mean"] = _metric(r["run_id"], f"eval/{sets[0]}/bpb_mean") if sets else None
    return runs


def api_metrics(run: str) -> dict:
    out: dict[str, list] = {}
    con = _con()
    try:
        cur = con.execute(
            "select name, step, value from metrics where run_id=? order by step, rowid", [run]
        )
        for name, step, value in cur:
            s = out.setdefault(name, [[], []])
            if s[0] and s[0][-1] == step:  # a re-score at the same step: the later row stands
                s[1][-1] = value
                continue
            s[0].append(step)
            s[1].append(value)
    finally:
        con.close()
    return out


def api_evals(run: str) -> list[dict]:
    return _rows("select * from evals where run_id=? order by step, book_id", [run])


def _artifact(run: str, kind: str, latest=True):
    r = _rows(
        f"select step, path, sha1, text from artifacts where run_id=? and kind=?"
        f" order by step {'desc' if latest else 'asc'}, rowid desc limit 1",
        [run, kind],
    )
    return r[0] if r else None


def api_run(run: str) -> dict:
    meta = _rows("select * from runs where run_id=?", [run])
    if not meta:
        return {}
    meta = meta[0]
    spec = json.loads(meta.pop("spec_json") or "{}")
    sets = [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]
    first = sets[0] if sets else None
    out = {"run": meta, "spec": spec, "sets": sets}

    n = _metric(run, "model/params_non_embedding")
    planned = _metric(run, "plan/tokens_total")
    unique = _metric(run, "plan/unique_tokens")
    seen = _metric(run, "tokens_seen") or 0
    out.update(
        n_params_total=_metric(run, "model/params_total"),
        n_params_embedding=_metric(run, "model/params_embedding"),
        n_params_non_embedding=n,
        tokens_planned=planned,
        tokens_seen=seen,
        unique_tokens=unique,
        tokens_per_s=None,
        eta_minutes=None,
    )
    tps = _rows(
        "select avg(value) v from (select value from metrics where run_id=? and"
        " name='tokens_per_s' order by step desc limit 50)",
        [run],
    )
    if tps and tps[0]["v"]:
        out["tokens_per_s"] = tps[0]["v"]
        if planned and meta["status"] == "running":
            out["eta_minutes"] = (planned - seen) / tps[0]["v"] / 60
    if n and planned:
        out["chinchilla"] = {
            "D_planned": planned,
            "L_planned": chinchilla.loss(n, planned),
            "D_unique": unique,
            "L_unique": chinchilla.loss(n, unique) if unique else None,
        }
    if first:
        hist = _rows(
            "select step, value from metrics where run_id=? and name=? order by step desc limit 2",
            [run, f"eval/{first}/bpb_mean"],
        )
        out["hole_bpb_latest"] = hist[0] if hist else None
        out["hole_bpb_previous"] = hist[1] if len(hist) > 1 else None
        ce_en = _metric(run, f"eval/{first}/ce_mean_en")
        out["hole_ce_mean_en"] = ce_en
        if ce_en is not None and out.get("chinchilla"):
            out["chinchilla"]["gap_planned"] = ce_en - out["chinchilla"]["L_planned"]

    for kind in ("samples", "top10", "recipe", "eval_sets", "probes", "curiosity", "stages"):
        a = _artifact(run, kind)
        out[kind] = (
            {"step": a["step"], **{"data": json.loads(a["text"])}} if a and a["text"] else None
        )
    # every eval step's probes, so the Traits tab can step through them and say when each trait
    # first appeared (a re-score at the same step replaces the earlier artifact: later rowid wins)
    by_step: dict[int, dict] = {}
    for a in _rows(
        "select step, text from artifacts where run_id=? and kind='probes' order by step, rowid",
        [run],
    ):
        if a["text"]:
            by_step[a["step"]] = json.loads(a["text"])
    out["probes_all"] = [{"step": k, "data": v} for k, v in sorted(by_step.items())]
    # the traits each book carries (lists/traits.csv, joined by title), for grouping by kind
    traits = load_traits()
    out["traits"] = {}
    if out.get("recipe"):
        for b in out["recipe"]["data"]:
            if b["title"] in traits:
                out["traits"][b["book_id"]] = traits[b["title"]]
    t = _artifact(run, "tokeniser")
    if t:
        stats = Path(t["path"]) / "stats.json"
        out["tokeniser"] = {
            "id": t["sha1"],
            "stats": json.loads(stats.read_text()) if stats.exists() else None,
        }
    return out


def api_compare() -> list[dict]:
    """Per run: the first eval set's bpb mean at each eval step, with tokens seen at that step."""
    out = []
    for r in api_runs():
        rid = r["run_id"]
        total = _metric(rid, "plan/tokens_total")
        steps = _metric(rid, "plan/total_steps")
        per_step = total / steps if total and steps else None
        spec_sets = _rows("select spec_json from runs where run_id=?", [rid])
        spec = json.loads(spec_sets[0]["spec_json"] or "{}") if spec_sets else {}
        sets = [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]
        if not sets or not per_step:
            continue
        series = _rows(
            "select step, value from metrics where run_id=? and name=? order by step",
            [rid, f"eval/{sets[0]}/bpb_mean"],
        )
        en = _rows(
            "select step, value from metrics where run_id=? and name=? order by step",
            [rid, f"eval/{sets[0]}/bpb_mean_en"],
        )
        # every held-out set this run has been scored on (its own, and any re-score), so the page
        # can read the truth gap and compare runs set by set
        by_set: dict[str, dict] = {}
        for x in _rows(
            "select name, step, value from metrics where run_id=? and name like 'eval/%/bpb_mean'"
            " order by step, rowid",
            [rid],
        ):
            d = by_set.setdefault(x["name"].split("/")[1], {"steps": [], "tokens": [], "bpb": []})
            if d["steps"] and d["steps"][-1] == x["step"]:
                d["bpb"][-1] = x["value"]
                continue
            d["steps"].append(x["step"])
            d["tokens"].append(x["step"] * per_step)
            d["bpb"].append(x["value"])
        # the push per layer and the learning rate, so the page computes each run's kinks itself
        push: dict[str, list] = {}
        for x in _rows(
            "select name, step, value from metrics where run_id=? and"
            " (name like 'grad_norm/layer_%' or name='lr') order by step",
            [rid],
        ):
            if x["name"].count("/") > 1:
                continue
            p = push.setdefault(x["name"], [[], []])
            p[0].append(x["step"])
            p[1].append(x["value"])
        recipe = _artifact(rid, "recipe", latest=False)
        n_books = len(json.loads(recipe["text"])) if recipe and recipe["text"] else None
        out.append(
            {
                "run_id": rid,
                "name": r["name"],
                "ship": r.get("ship"),
                "preset": r["preset"],
                "seed": r["seed"],
                "status": r["status"],
                "n_books": n_books,
                "tokens_per_step": per_step,
                "tokens_planned": total,
                "steps": [x["step"] for x in series],
                "tokens": [x["step"] * per_step for x in series],
                "bpb": [x["value"] for x in series],
                "bpb_en": [x["value"] for x in en],
                "set": sets[0],
                "by_set": by_set,
                "push": push,
            }
        )
    return out


def api_experiment(prefix: str) -> list[dict]:
    """Every run whose name starts with `prefix`, with what the experiment panel needs: the compare
    series (every held-out set, the push per layer, the learning rate), the move per layer, each
    eval step's trait summary, the curiosity ladder's highest rung, and the ship's question."""
    out = []
    for r in api_compare():
        if not (r.get("name") or "").startswith(prefix):
            continue
        rid = r["run_id"]
        spec = json.loads(
            _rows("select spec_json from runs where run_id=?", [rid])[0]["spec_json"] or "{}"
        )
        move: dict[str, list] = {}
        for x in _rows(
            "select name, step, value from metrics where run_id=? and name like 'update_ratio/layer_%'"
            " order by step",
            [rid],
        ):
            if x["name"].count("/") > 1:
                continue
            m = move.setdefault(x["name"], [[], []])
            m[0].append(x["step"])
            m[1].append(x["value"])
        traits: dict[int, dict] = {}
        for a in _rows(
            "select step, text from artifacts where run_id=? and kind='probes' order by step, rowid",
            [rid],
        ):
            if a["text"]:
                t = json.loads(a["text"])["traits"]
                traits[a["step"]] = {
                    n: {
                        "status": v["status"],
                        "best": max(v["auc"]) if v.get("auc") else None,
                        "layer": v.get("best_layer"),
                        "emergent": v.get("emergent"),
                    }
                    for n, v in t.items()
                }
        ladder = _rows(
            "select step, value from metrics where run_id=? and name='curiosity/highest' order by step",
            [rid],
        )
        out.append(
            {
                **r,
                "experiment": spec.get("experiment"),
                "question": spec.get("question"),
                "move": move,
                "traits": [{"step": k, "traits": v} for k, v in sorted(traits.items())],
                "ladder": [[x["step"], x["value"]] for x in ladder],
            }
        )
    return out


SPLIT_CLASSES = ("word_inside", "word_start", "punct", "space", "newline")
LAWS = (
    "nonword_rate",
    "zipf",
    "heaps",
    "word_len",
    "word_len_js",
    "punct_per_100w",
    "punct_js",
    "unbalanced_per_kw",
    "cap_after_stop",
)
QUEUES = ("9m-order.txt", "content-order.txt")


def _last_scores(run_ids: list[str]) -> dict[str, dict[str, float]]:
    """Every run's latest eval/* and laws/* values, on one connection: one indexed range read per
    run instead of one connection per metric, so the ladder stays quick with thousands of runs."""
    out: dict[str, dict[str, float]] = {}
    con = _con()
    try:
        for run in run_ids:
            got: dict[str, float] = {}
            # ascending by step then rowid, so the last write for each name wins, as in _metric
            for name, value in con.execute(
                "select name, value from metrics where run_id=?"
                " and ((name >= 'eval/' and name < 'eval0') or (name >= 'laws/' and name < 'laws0'))"
                " order by step, rowid",
                [run],
            ):
                got[name] = value
            out[run] = got
    finally:
        con.close()
    return out


def api_ladder() -> dict:
    """The ladder (each rung's job and how it is judged), every run's rung scores (the bits-per-byte
    split on its first held-out set and the laws, model beside reference), and tonight's queue."""
    from thorp.models.registry import LADDER, PRESETS

    rungs = []
    for r in LADDER:
        c = PRESETS[r["preset"]]
        ne = 12 * c["layers"] * c["width"] ** 2
        rungs.append(
            {
                **r,
                **c,
                "non_embedding": ne,
                "total": ne + (r.get("vocab", 16384) + 1024) * c["width"],
            }
        )
    runs = []
    rows = _rows(
        "select run_id, name, ship, status, tokens_seen, started, wall_minutes, spec_json"
        " from runs order by started"
    )
    ships, ship_of = _ships(rows)
    last = _last_scores([r["run_id"] for r in rows])
    voyage = _voyage_of()
    for r in rows:
        spec = json.loads(r.pop("spec_json") or "{}")
        m = last.get(r["run_id"], {})
        sets = [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]
        first = sets[0] if sets else None
        row = {
            **r,
            "preset": spec.get("model", {}).get("preset"),
            "vocab": spec.get("tokeniser", {}).get("vocab"),
            "context": spec.get("model", {}).get("context"),
            "seed": spec.get("seed"),
            "experiment": spec.get("experiment"),
            "recipe": spec.get("data", {}).get("recipe"),
            "passes": spec.get("data", {}).get("passes"),
            "ft_en": m.get("eval/hole-cards-unseen/bpb_mean_en"),
            "fleet": _fleet_of(r["ship"]),
            "ship_key": ship_of.get(r["run_id"]),
            "ship_name": ships[ship_of[r["run_id"]]]["name"] if r["run_id"] in ship_of else None,
            "voyage": voyage.get(r["name"]),
            "set": first,
            "bpb_en": m.get(f"eval/{first}/bpb_mean_en") if first else None,
            "split": {},
            "laws": {},
            "ref": {},
        }
        if first:
            for c in SPLIT_CLASSES:
                row["split"][c] = m.get(f"eval/{first}/split/{c}/bpb_mean_en")
        for k in LAWS:
            row["laws"][k] = m.get(f"laws/model/{k}")
            row["ref"][k] = m.get(f"laws/ref/{k}")
        runs.append(row)
    done = {r["name"]: r["status"] for r in runs}
    queue = []
    for f in QUEUES:
        p = Path(__file__).resolve().parents[2] / "specs" / f
        if p.exists():
            for name in p.read_text().split():
                queue.append({"name": name, "status": done.get(name, "queued")})
    for name in (
        "hundred-traits-v1",
        "hundred-traits-v1-seed2",
        "pool-400-traits-v1",
        "pool-400-traits-v1-seed2",
    ):
        queue.append({"name": name, "status": done.get(name, "queued")})  # queue_9m.sh's tail
    external = []
    for f in sorted((paths.data_dir() / "compare").glob("*.json")):
        try:
            x = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        external.append(
            {
                "model": x.get("model"),
                "set": x.get("set"),
                "bpb_mean_en": x.get("bpb_mean_en"),
                "books": [
                    {"book_id": b["book_id"], "title": b["title"], "bpb": b["bpb"]}
                    for b in x.get("books", [])
                ],
            }
        )
    return {"rungs": rungs, "runs": runs, "queue": queue, "external": external}


def api_rung(preset: str, limit: int | str = 0) -> list[dict]:
    """Training-loss curves (at most 300 points each) for the runs at one preset: all of them, or
    the latest `limit` (the proxy loop puts thousands of runs on one size)."""
    out = []
    picked = []
    for r in _rows("select run_id, name, ship, spec_json from runs order by started"):
        spec = json.loads(r["spec_json"] or "{}")
        if spec.get("model", {}).get("preset") == preset:
            picked.append(r)
    if int(limit or 0) > 0:
        picked = picked[-int(limit) :]
    for r in picked:
        pts = _rows(
            "select step, value from metrics where run_id=? and name='loss' order by step",
            [r["run_id"]],
        )
        k = max(1, len(pts) // 300)
        out.append(
            {
                "name": r["name"],
                "ship": r["ship"],
                "steps": [p["step"] for p in pts[::k]],
                "loss": [p["value"] for p in pts[::k]],
            }
        )
    return out


def api_waypoints(preset: str, limit: int | str = 30) -> dict:
    """The waypoints a model passes in training, for the latest `limit` runs at one preset, step by
    step: Nevermores (induction heads; evaluators/nevermore.py) and the trait probes
    (evaluators/probes.py), with the thresholds that say when each counts as reached."""
    from thorp.evaluators import nevermore, probes

    picked = []
    for r in _rows("select run_id, name, ship, status, spec_json from runs order by started"):
        spec = json.loads(r.pop("spec_json") or "{}")
        if spec.get("model", {}).get("preset") == preset and not (r["name"] or "").startswith(
            "smoke"
        ):
            picked.append(r)
    if int(limit or 0) > 0:
        picked = picked[-int(limit) :]
    out = []
    con = _con()
    try:
        for r in picked:
            series: dict[str, dict[int, float]] = {}
            for name, step, value in con.execute(
                "select name, step, value from metrics where run_id=?"
                " and ((name >= 'nevermore/' and name < 'nevermore0') or (name >= 'probe/' and name < 'probe0'))"
                " order by step, rowid",
                [r["run_id"]],
            ):
                if name.startswith("probe/") and not name.endswith(
                    ("/best", "/floor_bow", "/floor_init")
                ):
                    continue  # the per-layer AUCs stay on the Traits tab
                series.setdefault(name, {})[step] = value
            nv = {k.split("/", 1)[1]: v for k, v in series.items() if k.startswith("nevermore/")}
            traits: dict[str, dict] = {}
            for k, v in series.items():
                if k.startswith("probe/"):
                    trait, part = k[len("probe/") :].rsplit("/", 1)
                    traits.setdefault(trait, {})[part] = v
            # the per-head scores, step by step: the model's hand, one card per attention head
            hands = []
            for step, text in con.execute(
                "select step, text from artifacts where run_id=? and kind='nevermore'"
                " order by step, rowid",
                [r["run_id"]],
            ):
                try:
                    a = json.loads(text)
                except ValueError:
                    continue
                if hands and hands[-1]["step"] == step:
                    hands.pop()  # a re-score of the same step replaces it
                hands.append(
                    {"step": step, "random": a.get("scores"), "real": a.get("natural_scores")}
                )
            out.append(
                {
                    **r,
                    "hands": hands,
                    "nevermore": {
                        k: {"step": list(v), "value": list(v.values())} for k, v in nv.items()
                    },
                    "traits": {
                        t: {
                            p: {"step": list(v), "value": list(v.values())}
                            for p, v in parts.items()
                        }
                        for t, parts in traits.items()
                    },
                }
            )
    finally:
        con.close()
    return {
        "runs": out,
        "nevermore_threshold": nevermore.THRESHOLD,
        "trait_found": probes.AUC_FOUND,
        "trait_margin": probes.EMERGE_MARGIN,
        "core_traits": list(probes.TRAIT_COLUMNS),
        "natural_book": nevermore.NATURAL_BOOK,
    }


ESSAYS = {
    "nevermore": ("Nevermores", "thorp.evaluators.nevermore"),
    "traits": ("Traits", "thorp.evaluators.probes"),
}


def api_essay(name: str) -> dict:
    """A waypoint explained, for the reader: the evaluator's own docstring, so the page and the code
    never disagree. Shaped like /api/book."""
    import importlib

    if name not in ESSAYS:
        raise LookupError(f"no essay {name}")
    title, module = ESSAYS[name]
    text = (importlib.import_module(module).__doc__ or "").strip()
    return {
        "book_id": f"essay-{name}",
        "title": title,
        "author": f"Thorp · {module.replace('.', '/')}.py",
        "language": "en",
        "chars": len(text),
        "offset": 0,
        "text": text,
    }


def _voyage_of() -> dict[str, str]:
    """run name -> voyage key, for every run a voyage claims (thorp/voyages.py runs_of)."""
    try:
        from thorp import fleet, voyages
    except ImportError:
        return {}
    out = {}
    for v in fleet.VOYAGES.values():
        for r in voyages.runs_of(v):
            out[r["name"]] = v.key
    return out


def _ships(rows: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    """Ships (a class fitted out one way; thorp/fleet.py) from ledger rows that carry spec_json,
    ship, name and started: {ship key: ship} and {run_id: ship key}. Each run is one of its ship's
    sailings. Nothing is registered from here (save=False)."""
    try:
        from thorp import fleet
    except ImportError:
        return {}, {}
    ships: dict[str, dict] = {}
    of: dict[str, str] = {}
    for r in rows:
        if (r.get("name") or "").startswith("smoke") or not r.get("spec_json"):
            continue
        try:
            sh = fleet.ship_of_run(r, save=False)
        except Exception:  # noqa: BLE001  a spec the fitout cannot read stays unshipped
            continue
        of[r["run_id"]] = sh.key
        ships.setdefault(sh.key, {**sh.__dict__, "sailings": []})["sailings"].append(r["run_id"])
    return ships, of


def api_ships() -> list[dict]:
    """Every ship with its sailings (runs, one per seed) and how they did."""
    rows = _rows(
        "select run_id, name, ship, status, started, tokens_seen, wall_minutes, spec_json from runs order by started"
    )
    ships, _ = _ships(rows)
    by_id = {r["run_id"]: r for r in rows}
    last = _last_scores(list(by_id))
    out = []
    for sh in ships.values():
        sails = []
        for rid in sh["sailings"]:
            r = by_id[rid]
            spec = json.loads(r["spec_json"] or "{}")
            sails.append(
                {
                    "run_id": rid,
                    "name": r["name"],
                    "label": r["ship"],
                    "seed": spec.get("seed"),
                    "status": r["status"],
                    "started": r["started"],
                    "tokens_seen": r["tokens_seen"],
                    "wall_minutes": r["wall_minutes"],
                    "ft_en": last.get(rid, {}).get("eval/hole-cards-unseen/bpb_mean_en"),
                }
            )
        scored = [x["ft_en"] for x in sails if x["ft_en"] is not None]
        out.append(
            {
                **{k: v for k, v in sh.items() if k != "sailings"},
                "sailings": sails,
                "ft_en_mean": sum(scored) / len(scored) if scored else None,
                "ft_en_best": min(scored) if scored else None,
                "started": sails[0]["started"],
                "latest": sails[-1]["started"],
            }
        )
    return out


def _fleet_of(ship: str | None) -> str | None:
    try:
        from thorp import fleet
    except ImportError:
        return None
    return fleet.fleet_of(ship)


def api_voyages() -> list[dict]:
    """Every voyage: goal, outcomes, levers, stop rule, status, lessons and its runs (voyages.py)."""
    from thorp import voyages

    return voyages.payload()


def api_voyage_series(key: str) -> dict:
    """For one voyage's runs, each star's score at every reading, so a chart can show the step at
    which a line crosses its threshold: first light. A run that received heads from another
    (a `transplant` artifact: the Magician's Apprentice) carries the record, and the donor run is
    added (role "donor") so its curve sits beside the receivers'."""
    from thorp import fleet, voyages

    v = fleet.VOYAGES[key]
    runs = [{**r, "role": None} for r in voyages.runs_of(v)]
    con = _con()

    def series_of(run_id: str) -> dict:
        series = {}
        for sk, star in fleet.STARS.items():
            pts = list(
                con.execute(
                    "select step, value from metrics where run_id=? and name=? order by step, rowid",
                    [run_id, star.metric],
                )
            )
            series[sk] = {"step": [p[0] for p in pts], "value": [p[1] for p in pts]}
            # lit shared: the best layer's two strongest heads together (voyages.py works it
            # out from the 'stars' artifacts where the metric was not recorded yet)
            if getattr(star, "shared_metric", ""):
                sh = voyages._shared_series(run_id, star)
                series[sk]["shared_step"] = [p["step"] for p in sh]
                series[sk]["shared_value"] = [p["value"] for p in sh]
        return series

    def teacher_of(r: dict) -> dict | None:
        try:
            t = (json.loads(r.get("spec_json") or "{}").get("optim") or {}).get("teacher")
        except ValueError:
            return None
        return t if isinstance(t, dict) else None

    def transplant_of(run_id: str) -> dict | None:
        row = con.execute(
            "select text from artifacts where run_id=? and kind='transplant' order by step, rowid limit 1",
            [run_id],
        ).fetchone()
        try:
            return json.loads(row[0]) if row else None
        except ValueError:
            return None

    try:
        out = []
        for r in runs:
            t = transplant_of(r["run_id"])
            out.append(
                {
                    "run_id": r["run_id"],
                    "name": r["name"],
                    "ship": r["ship"],
                    "role": "receiver" if t else "student" if teacher_of(r) else None,
                    "transplant": t,
                    "teacher": teacher_of(r),
                    "series": series_of(r["run_id"]),
                }
            )
        have = {r["run_id"] for r in out}
        donors = (
            {x["transplant"].get("from_run_id") for x in out if x["transplant"]} - have - {None}
        )
        # a teacher (optim.teacher.run) joins its students the way a donor joins its receivers
        teachers = {
            str(x["teacher"]["run"]) for x in out if x.get("teacher") and x["teacher"].get("run")
        }
        for d, role in [(d, "donor") for d in donors] + [(t, "teacher") for t in sorted(teachers)]:
            row = con.execute(
                "select run_id, name, ship from runs where run_id=? or name=? limit 1", [d, d]
            ).fetchone()
            if row and row[0] not in have:
                have.add(row[0])
                out.insert(
                    0,
                    {
                        "run_id": row[0],
                        "name": row[1],
                        "ship": row[2],
                        "role": role,
                        "transplant": None,
                        "teacher": None,
                        "series": series_of(row[0]),
                    },
                )
    finally:
        con.close()
    return {
        "runs": out,
        "voyage_stars": list(getattr(v, "stars", ()) or ()),
        "stars": {
            k: {"name": s.name, "threshold": s.threshold, "metric": s.metric}
            for k, s in fleet.STARS.items()
        },
    }


def api_sieves() -> dict:
    """The sieves (fleet.SIEVES: push, move, heading), each with the plain-English write-up the page
    shows, the kink rule, and for each star the metrics that say when and in which layer it lit."""
    from thorp import fleet

    def layer_of(metric: str) -> str:
        # stars/<star>/max_score -> stars/<star>/best_layer; nevermore/natural_max_score -> .../natural_best_layer
        return metric.replace("shared_score", "shared_layer").replace("max_score", "best_layer")

    return {
        "sieves": [
            {"key": k, "name": v.name, "about": v.about, "prefix": v.metric_prefix}
            for k, v in fleet.SIEVES.items()
        ],
        # soundings: the data's journey up the stack when reading (fleet.SOUNDINGS), for the journey view
        "soundings": [
            {"key": k, "name": v.name, "metric": v.metric, "about": v.about}
            for k, v in getattr(fleet, "SOUNDINGS", {}).items()
        ],
        "kink_min_records": fleet.KINK_MIN_RECORDS,
        "kink_firm": fleet.KINK_FIRM,
        "stars": [
            {
                "key": k,
                "name": st.name,
                "threshold": st.threshold,
                "metric": st.metric,
                "layer": layer_of(st.metric),
                "shared_metric": getattr(st, "shared_metric", "") or None,
                "shared_layer": layer_of(st.shared_metric)
                if getattr(st, "shared_metric", "")
                else None,
            }
            for k, st in fleet.STARS.items()
        ],
    }


# classes renamed (old address name -> new), so old addresses and names keep working (7 Nov, Justin)
CLASS_RENAMES = {"seedling": "keel", "proxy": "pilot"}


def _known_heads() -> list[dict]:
    """The star chart (thorp/dash/heads.py), each kind's expected class turned into its preset."""
    import re

    from thorp.dash.heads import KNOWN_HEADS
    from thorp.models.registry import LADDER

    by_name = {
        re.sub(r"[^a-z0-9]+", "-", re.sub(r"^the\s+", "", r["name"].lower())): r["preset"]
        for r in LADDER
    }
    for old, new in CLASS_RENAMES.items():  # either name finds the class, before and after a rename
        if old in by_name:
            by_name.setdefault(new, by_name[old])
        if new in by_name:
            by_name.setdefault(old, by_name[new])
    return [{**h, "expected_from": by_name.get(h.get("expected_class"))} for h in KNOWN_HEADS]


# the size bands a trick is placed in: one order of magnitude each, since the field's sizes are rough
FIELD_BANDS = ("under 1M", "1M–10M", "10M–100M", "100M–1B", "1B–10B", "10B–100B", "100B and up")


def _class_presets() -> dict[str, str]:
    """Each class name (keel, pilot, speller...) to its preset, old names included."""
    import re

    from thorp.models.registry import LADDER

    by_name = {
        re.sub(r"[^a-z0-9]+", "-", re.sub(r"^the\s+", "", r["name"].lower())): r["preset"]
        for r in LADDER
    }
    for old, new in CLASS_RENAMES.items():
        if old in by_name:
            by_name.setdefault(new, by_name[old])
        if new in by_name:
            by_name.setdefault(old, by_name[new])
    return by_name


def _methods() -> dict:
    """How each trick is proved (fleet.METHODS): the trick, its parts and whether the tests cover them,
    the gaps, the planned controls, the metric, the cards (stars) it needs, and the status."""
    import dataclasses

    from thorp import fleet

    out = {}
    for k, m in getattr(fleet, "METHODS", {}).items():
        d = dataclasses.asdict(m) if dataclasses.is_dataclass(m) else dict(m)
        d["parts"] = [
            dict(zip(("part", "meaning", "covered"), p, strict=False)) for p in d.get("parts", [])
        ]
        d["controls"] = [
            dict(zip(("control", "does"), c, strict=False)) for c in d.get("controls", [])
        ]
        d["cards"] = [
            dict(zip(("card", "operation", "status"), c, strict=False)) for c in d.get("cards", [])
        ]
        out[k] = d
    return out


def _rungs() -> dict:
    """The discovery chains' rungs (fleet.RUNGS): what a model at each class is according to the
    chains, with the class turned into its preset; and the chains' order (fleet.chains())."""
    from thorp import fleet

    by_name = _class_presets()
    rungs = [
        {
            "class": r.goal_class,
            "preset": by_name.get(r.goal_class),
            "title": r.title,
            "summary": r.summary,
        }
        for r in getattr(fleet, "RUNGS", ())
    ]
    chains = fleet.chains() if hasattr(fleet, "chains") else []
    return {"rungs": rungs, "chains": chains, **_grades()}


def _short_model(m: str) -> str:
    """A reference model's short name: pythia-14m, Qwen3 0.6B, Qwen3 1.7B 4-bit."""
    import re

    name = m.split("/")[-1]
    name = re.sub(r"-(\d+)bit$", r" \1-bit", name)
    return name.replace("Qwen3-", "Qwen3 ")


def _grades(pairs: bool = False) -> dict:
    """Whether each chain gets harder as it climbs (fleet.grading, written to
    data/compare/chain-grades.json): each chain's grade, and the reference ladder's readings on every
    rung (fleet.REFERENCE_LADDER: Pythia 14m to 410m and Qwen3 0.6B), per-pair lifts only if asked."""
    from thorp import fleet

    p = Path(__file__).resolve().parents[2] / "data" / "compare" / "chain-grades.json"
    try:
        d = json.loads(p.read_text())
    except (OSError, ValueError):
        return {"grades": {}, "reference": []}
    models = d.get("models", {})
    ladder = list(getattr(fleet, "REFERENCE_LADDER", ()))
    reference = [
        {
            "model": m,
            "short": _short_model(m),
            "tricks": {
                k: {kk: vv for kk, vv in v.items() if pairs or kk != "pairs"}
                for k, v in models.get(m, {}).items()
            },
        }
        for m in ladder
        if m in models
    ]
    # the models that grade the chains: all read, less the competitors (they never grade the test they
    # are scored on), though a competitor on the reference ladder (Qwen3 4B) grades as a ladder model
    competitors = set(getattr(fleet, "COMPETITORS", {})) - set(ladder)
    graded_on = sorted(m for m in models if m not in competitors)
    return {"grades": d.get("chains", {}), "reference": reference, "graded_on": graded_on}


def _known_tricks() -> list[dict]:
    """The tricks of the trade on the route to quantum physics (thorp/dash/tricks.py): each with its
    size band, and its goal class (named there by class name) turned into the class's preset."""
    from thorp.dash.tricks import KNOWN_TRICKS

    by_name = _class_presets()
    out = []
    for t in KNOWN_TRICKS:
        fp = t["field_params"]
        rank = (
            None
            if fp is None
            else min(len(FIELD_BANDS) - 1, max(0, int(math.floor(math.log10(fp))) - 5))
        )
        goal = by_name.get(t["goal_class"]) if t["goal_class"] else None
        out.append(
            {
                **t,
                "field_band": "not shown in the field" if rank is None else FIELD_BANDS[rank],
                "field_band_rank": len(FIELD_BANDS) if rank is None else rank,
                "target_class": goal,
                "beyond_ladder": goal is None and not t["taught"],
            }
        )
    return out


def _floor(con, run_id: str, metric: str) -> float | None:
    """A trick's floor on one run: the untrained model's reading (tricks/<key>/floor_lift beside a
    tricks/<key>/lift), the last one recorded, or None where the trick has no floor."""
    if not metric.endswith("/lift"):
        return None
    row = con.execute(
        "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
        [run_id, metric[: -len("lift")] + "floor_lift"],
    ).fetchone()
    return row[0] if row else None


def _pairs(path: str | None) -> list[dict] | None:
    """A matched-pairs list (prompt, idea, rival, and the frame: the prompt's tail that the lift is
    measured against, absent on the keel's lists), or None when it is not written yet."""
    import csv

    if not path or not Path(path).exists():
        return None
    with open(path, newline="") as f:
        return [
            {
                "prompt": r.get("prompt", ""),
                "frame": r.get("frame") or "",
                "idea": r.get("idea", ""),
                "rival": r.get("rival", ""),
            }
            for r in csv.DictReader(f)
        ]


def api_chain(key: str) -> dict:
    """One of the bettor's tests told as a climb (fleet.CHAINS): the idea, who found it, the shelf,
    and each step keel to bettor with what it adds, the class it belongs to (fleet.RUNGS), its pairs
    and, per sailing, the latest per-pair lifts from the 'discovery' artifacts (in the pairs' order).
    The evidence per class (best lift, share, performed) comes from /api/discoveries."""
    from thorp import fleet

    ch = getattr(fleet, "CHAINS", {}).get(key)
    if ch is None:
        return {"key": key, "error": f"no chain called {key}"}
    rungs = _rungs()["rungs"]
    known = {t["key"]: t for t in _known_tricks()}
    # the latest discovery artifact holding each test, per sailing
    latest: dict[str, dict[str, dict]] = {}
    runs = {}
    for r in _rows(
        "select a.run_id, a.text, r.name, r.spec_json from artifacts a join runs r using(run_id)"
        " where a.kind='discovery' order by a.step, a.rowid"
    ):
        try:
            body = json.loads(r["text"] or "{}")
        except ValueError:
            continue
        runs[r["run_id"]] = {
            "run_id": r["run_id"],
            "name": r["name"],
            "preset": json.loads(r["spec_json"] or "{}").get("model", {}).get("preset"),
        }
        for k, v in body.items():
            if isinstance(v, dict) and "pairs" in v:
                latest.setdefault(k, {})[r["run_id"]] = v
    steps = []
    for i, (k, text) in enumerate(ch.steps.items()):
        tr = fleet.TRICKS.get(k)
        kt = known.get(k, {})
        steps.append(
            {
                "key": k,
                "name": tr.name if tr else kt.get("name", k),
                "adds": text,
                "rung": rungs[i] if i < len(rungs) else None,
                "threshold": tr.threshold if tr else None,
                "min_score": getattr(tr, "min_score", None) if tr else None,
                "evaluator": tr.evaluator if tr else None,
                "about": tr.about if tr else "",
                "pairs_file": tr.pairs if tr else None,
                "pairs": _pairs(tr.pairs if tr else None),
                "reference": kt.get("reference", {}),
                "runs": [
                    {
                        **runs[rid],
                        "lift": v.get("lift"),
                        "share": v.get("score"),
                        "pairs": v.get("pairs") or [],
                    }
                    for rid, v in latest.get(k, {}).items()
                ],
            }
        )
    bet = fleet.TRICKS.get(key)
    g = _grades(pairs=True)
    return {
        "grade": g["grades"].get(key),
        "graded_on": g.get("graded_on", []),
        "reference": g["reference"],
        "key": ch.key,
        "name": ch.name,
        "strand": ch.strand,
        "idea": ch.idea,
        "found": ch.found,
        "shelf": ch.shelf,
        "cutoff": getattr(bet, "cutoff", None),
        "steps": steps,
    }


# ---- slow payloads, kept warm: the shelves take seconds to compute (they read every list and the
# catalogue), so the last result is served while a fresh one is computed in the background
_WARM: dict[str, dict] = {}
_WARM_LOCK = __import__("threading").Lock()


def _warm(name: str, fn, ttl: float = 300.0):
    import threading
    import time

    with _WARM_LOCK:
        e = _WARM.setdefault(name, {"at": 0.0, "value": None, "busy": False, "error": None})
        stale = time.time() - e["at"] > ttl
        if stale and not e["busy"]:
            e["busy"] = True

            def run():
                try:
                    v, err = fn(), None
                except Exception as ex:  # noqa: BLE001
                    v, err = None, str(ex)
                with _WARM_LOCK:
                    if v is not None:
                        e["value"], e["at"] = v, time.time()
                    e["busy"], e["error"] = False, err

            threading.Thread(target=run, daemon=True).start()
        return e["value"], e["busy"], e["error"]


def api_shelves() -> dict:
    """Every shelf (thorp.shelves.payload): the training lists, the decks, the probes and drafts, each
    with its books, size, families and the runs that use it. Served warm (see _warm)."""
    from thorp import shelves

    value, busy, error = _warm("shelves", shelves.payload)
    return {"shelves": value, "computing": value is None and busy, "error": error}


def api_shelf_books(path: str) -> list[dict]:
    """A shelf's rows (title, author, language, family) with the fetched book each resolves to,
    where it can be told without fetching, so the reader can open it."""
    import csv

    from thorp import manifest

    p = Path(__file__).resolve().parents[2] / path
    if not path.startswith("lists/") or ".." in path or not p.exists():
        raise LookupError(f"no shelf {path}")
    with open(p, newline="") as f:
        rows = list(csv.DictReader(f))
    from thorp.sources import base

    by_title: dict[tuple[str, str], str] = {}
    for b in manifest.all_books():
        by_title.setdefault(((b.title or "").lower(), (b.author or "").lower()), b.id)
    sources = base._sources()
    out = []
    for r in rows:
        # a row names its text (key:ident, as thorp.shelves reads it), or is matched by title
        ref, bid = r.get("text") or "", None
        if ":" in ref:
            key, ident = ref.split(":", 1)
            bid = (
                ident if key == "local" else sources[key].prefix + ident if key in sources else None
            )
        if bid and manifest.get(bid) is None:
            bid = None
        if bid is None:
            bid = by_title.get(((r.get("title") or "").lower(), (r.get("author") or "").lower()))
        out.append(
            {
                "title": r.get("title", ""),
                "author": r.get("author", ""),
                "language": r.get("language", ""),
                "family": r.get("family", ""),
                "book_id": bid,
            }
        )
    return out


def api_leaderboard() -> dict:
    """The best of each class on the climb to chaining two facts (thorp.leaderboard.payload)."""
    from thorp import leaderboard

    return leaderboard.payload()


_SMOKE: dict = {"at": 0.0, "value": None}


def api_smoking_qwen() -> dict:
    """Smoking Qwen (thorp.smoking_qwen.payload): the forecast that a 400M Thorp chains two facts as
    well as Qwen3 4B, with the reference ladder's points (size, chaining lift) for the chart. The
    payload bootstraps, so it is kept for two minutes."""
    import time

    from thorp import leaderboard, smoking_qwen

    if _SMOKE["value"] is not None and time.time() - _SMOKE["at"] < 120:
        return _SMOKE["value"]
    d = smoking_qwen.payload()
    sizes = getattr(smoking_qwen, "REFERENCE_PARAMS", {})
    d["reference"] = [
        {
            "model": r["model"],
            "short": r.get("label")
            if r.get("competitor") and r.get("label")
            else _short_model(r["model"]),
            "params": sizes.get(r["model"]),
            "chaining_lift": r.get("chaining_lift"),
            "competitor": bool(r.get("competitor")),
        }
        for r in leaderboard.payload().get("reference", [])
        if sizes.get(r["model"])
    ]
    d["threshold"] = leaderboard.payload().get("threshold", 0.1)
    d["noise"] = getattr(smoking_qwen, "NOISE", 0.03)
    _SMOKE.update(at=time.time(), value=d)
    return d


def api_leaderboard_internal() -> dict:
    """The internal measure (thorp.leaderboard.internal): the climb, for the two-fact voyage's page."""
    from thorp import leaderboard

    return leaderboard.internal()


def api_bridge() -> dict:
    """The bridge card (fleet.STARS["bridge"]), a curve over layers: for every run that read it, the
    latest stars/bridge/layer_<i> (nats: how strongly the answer's position carries the middle term
    at each layer), its best layer and max score, with the threshold."""
    from thorp import fleet

    st = getattr(fleet, "STARS", {}).get("bridge")
    out = []
    con = _con()
    try:
        rows = con.execute(
            "select m.run_id, r.name, r.spec_json, m.name, m.value, m.step from metrics m join runs r using(run_id)"
            " where m.name like 'stars/bridge/%' order by m.step, m.rowid"
        )
        runs: dict[str, dict] = {}
        for rid, name, spec_json, metric, value, step in rows:
            r = runs.setdefault(
                rid,
                {
                    "run_id": rid,
                    "name": name,
                    "preset": json.loads(spec_json or "{}").get("model", {}).get("preset"),
                    "layers": {},
                },
            )
            key = metric.split("/")[-1]
            if key.startswith("layer_"):
                r["layers"][int(key[6:])] = value
            else:
                r[key] = value
            r["step"] = step
        for r in runs.values():
            n = max(r["layers"], default=-1) + 1
            r["curve"] = [r["layers"].get(i) for i in range(n)]
            del r["layers"]
            out.append(r)
    finally:
        con.close()
    return {"threshold": getattr(st, "threshold", None), "runs": out}


def api_climb(runs: str) -> dict:
    """Each run's climb over training (thorp.leaderboard.climb, read at every step that has
    discovery readings, carrying each trick's latest lift and share forward)."""
    from thorp import fleet, leaderboard

    out = {}
    chain_keys = {k for c in fleet.chains() for k in c}
    con = _con()
    try:
        for rid in [x for x in runs.split(",") if x][:60]:
            read_here = False
            gain = None
            lift: dict[str, float] = {}
            score: dict[str, float] = {}
            steps: dict[int, None] = {}
            series = {"step": [], "climb": [], "chaining_lift": [], "logic_gain": []}
            rows = list(
                con.execute(
                    "select step, name, value from metrics where run_id=? and name like 'tricks/%'"
                    " order by step, rowid",
                    [rid],
                )
            )
            for i, (step, name, value) in enumerate(rows):
                parts = name.split("/")
                if len(parts) == 3 and parts[1] in fleet.TRICKS:
                    if parts[2] == "lift":
                        lift[parts[1]] = value
                    elif parts[2] == "score":
                        score[parts[1]] = value
                    elif parts[1] == "logic_test" and parts[2] == "gain":
                        gain = value
                    read_here = read_here or parts[1] in chain_keys or parts[1] == "logic_test"
                # a point only where the chains were read (other tricks are read on their own steps)
                last = i == len(rows) - 1 or rows[i + 1][0] != step
                if last and not read_here:
                    continue
                if last:
                    read_here = False
                if last and step not in steps:
                    steps[step] = None
                    c = leaderboard.climb(lift, score)
                    series["step"].append(step)
                    series["climb"].append(c["climb"])
                    series["chaining_lift"].append(c["chaining_lift"])
                    series["logic_gain"].append(gain)
            out[rid] = series
    finally:
        con.close()
    return out


def api_trick_series(key: str) -> dict:
    """One measured trick's score at every reading of every sailing, for its chart."""
    from thorp import fleet

    tr = fleet.TRICKS[key]
    out = []
    con = _con()
    try:
        for r in _rows("select run_id, name, ship, spec_json from runs order by started"):
            if (r["name"] or "").startswith("smoke"):
                continue
            pts = list(
                con.execute(
                    "select step, value from metrics where run_id=? and name=? order by step, rowid",
                    [r["run_id"], tr.metric],
                )
            )
            if pts:
                spec = json.loads(r["spec_json"] or "{}")
                out.append(
                    {
                        "run_id": r["run_id"],
                        "name": r["name"],
                        "ship": r["ship"],
                        "preset": spec.get("model", {}).get("preset"),
                        "step": [p[0] for p in pts],
                        "value": [p[1] for p in pts],
                        "floor": _floor(con, r["run_id"], tr.metric),
                    }
                )
    finally:
        con.close()
    return {"key": key, "threshold": tr.threshold, "metric": tr.metric, "runs": out}


def api_discoveries() -> dict:
    """The two things followed across every ship: stars (heads that light, fleet.STARS) and traits
    (directions the probes find, evaluators/probes.py). For each, which ships have it and when."""
    from thorp import fleet, voyages
    from thorp.evaluators import probes

    runs = _rows("select run_id, name, ship, status, started, spec_json from runs order by started")
    voyage = _voyage_of()
    shipreg, ship_of = _ships(runs)

    def named(r: dict) -> dict:
        k = ship_of.get(r["run_id"])
        return {"ship_key": k, "ship_name": shipreg[k]["name"] if k else None}

    stars = []
    for star in fleet.STARS.values():
        ships = []
        for r in runs:
            if r["name"] and r["name"].startswith("smoke"):
                continue
            spec = json.loads(r["spec_json"] or "{}")
            t = voyages.star_timeline(
                r["run_id"], star, spec.get("optim", {}).get("batch_tokens", 32768)
            )
            if t["readings"]:
                ships.append(
                    {
                        "run_id": r["run_id"],
                        "name": r["name"],
                        "ship": r["ship"],
                        "preset": spec.get("model", {}).get("preset"),
                        "voyage": voyage.get(r["name"]),
                        **named(r),
                        **t,
                    }
                )
        stars.append(
            {
                "key": star.key,
                "name": star.name,
                "level": star.level,
                "rests_on": list(star.rests_on),
                "threshold": star.threshold,
                "metric": star.metric,
                "about": star.about,
                "ships": ships,
            }
        )
    con = _con()
    traits: dict[str, list] = {}
    try:
        for r in runs:
            if r["name"] and r["name"].startswith("smoke"):
                continue
            spec = json.loads(r["spec_json"] or "{}")
            series: dict[str, dict[str, dict[int, float]]] = {}
            for name, step, value in con.execute(
                "select name, step, value from metrics where run_id=? and name >= 'probe/' and name < 'probe0'"
                " and (name like '%/best' or name like '%/floor_bow' or name like '%/floor_init')"
                " order by step, rowid",
                [r["run_id"]],
            ):
                t, part = name[len("probe/") :].rsplit("/", 1)
                series.setdefault(t, {}).setdefault(part, {})[step] = value
            for t, parts in series.items():
                best = parts.get("best", {})
                found = next((st for st, v in best.items() if v >= probes.AUC_FOUND), None)
                floors = [parts[k] for k in ("floor_bow", "floor_init") if k in parts]
                learned = None
                if floors:
                    learned = next(
                        (
                            st
                            for st, v in best.items()
                            if v >= probes.AUC_FOUND
                            and v - max(f.get(st, float("-inf")) for f in floors)
                            >= probes.EMERGE_MARGIN
                        ),
                        None,
                    )
                traits.setdefault(t, []).append(
                    {
                        "run_id": r["run_id"],
                        "name": r["name"],
                        "ship": r["ship"],
                        "preset": spec.get("model", {}).get("preset"),
                        **named(r),
                        "found_at": found,
                        "learned_at": learned,
                        "floors": bool(floors),
                        "best": max(best.values()) if best else None,
                        "readings": len(best),
                    }
                )
    finally:
        con.close()
    # tricks (fleet.TRICKS): what a sailing can do, judged by its bets from outside, beside which
    # of the stars that perform it (performed_by) lit on that same sailing
    lit_on: dict[str, set] = {}
    for st in stars:
        for x in st["ships"]:
            if x["steps_to_lit"] is not None or x.get("shared_steps_to_lit") is not None:
                lit_on.setdefault(x["run_id"], set()).add(st["key"])
    tricks = []
    con = _con()
    try:
        for tr in getattr(fleet, "TRICKS", {}).values():
            ships = []
            for r in runs:
                if r["name"] and r["name"].startswith("smoke"):
                    continue
                pts = list(
                    con.execute(
                        "select step, value from metrics where run_id=? and name=? order by step, rowid",
                        [r["run_id"], tr.metric],
                    )
                )
                if not pts:
                    continue
                # the share rule (fleet.performed): a matched-pairs test is performed only where its
                # lift is at the threshold and its share of pairs right at min_score, at the same reading
                min_score = getattr(tr, "min_score", None)
                share = {}
                if min_score is not None:
                    share = dict(
                        con.execute(
                            "select step, value from metrics where run_id=? and name=? order by step, rowid",
                            [r["run_id"], tr.metric.rsplit("/", 1)[0] + "/score"],
                        )
                    )
                done = [
                    p[0]
                    for p in pts
                    if p[1] >= tr.threshold
                    and (
                        min_score is None
                        or (share.get(p[0]) is not None and share[p[0]] >= min_score)
                    )
                ]
                top = max(pts, key=lambda p: p[1])
                spec = json.loads(r["spec_json"] or "{}")
                ships.append(
                    {
                        "run_id": r["run_id"],
                        "name": r["name"],
                        "ship": r["ship"],
                        "preset": spec.get("model", {}).get("preset"),
                        **named(r),
                        "performed_at": done[0] if done else None,
                        "best": top[1],
                        "share_at_best": share.get(top[0]),
                        "best_share": max(share.values()) if share else None,
                        "latest": pts[-1][1],
                        "readings": len(pts),
                        "floor": _floor(con, r["run_id"], tr.metric),
                        "stars_lit": sorted(lit_on.get(r["run_id"], set()) & set(tr.performed_by)),
                    }
                )
            tricks.append(
                {
                    "key": tr.key,
                    "name": tr.name,
                    "metric": tr.metric,
                    "threshold": tr.threshold,
                    "min_score": getattr(tr, "min_score", None),
                    "performed_by": list(tr.performed_by),
                    "evaluator": tr.evaluator,
                    "leads_to": getattr(tr, "leads_to", None),
                    "cutoff": getattr(tr, "cutoff", None),
                    "viable": getattr(tr, "viable", True),
                    "about": tr.about,
                    "ships": ships,
                }
            )
    finally:
        con.close()
    return {
        "tricks": tricks,
        "stars": stars,
        "traits": [
            {"key": t, "ships": v}
            for t, v in sorted(traits.items(), key=lambda kv: (kv[0].startswith("family/"), kv[0]))
        ],
        "trait_found": probes.AUC_FOUND,
        "trait_margin": probes.EMERGE_MARGIN,
        "core_traits": list(probes.TRAIT_COLUMNS),
        # the star chart: every kind of head the literature describes (thorp/dash/heads.py)
        "known_heads": _known_heads(),
        "known_tricks": _known_tricks(),
        "chain_rungs": _rungs(),
        "methods": _methods(),
        "waypoints": __import__("thorp.dash.tricks", fromlist=["WAYPOINTS"]).WAYPOINTS,
    }


def api_stages(runs: str) -> dict:
    """Each run's training stages (artifact 'stages' at step 0: [{index, name, recipe, passes,
    first_step, last_step, tokens}]); a run without stages has an empty list (one stage, reading)."""
    out = {}
    con = _con()
    try:
        for rid in [x for x in runs.split(",") if x]:
            row = con.execute(
                "select text from artifacts where (run_id=? or run_id in (select run_id from runs where name=?))"
                " and kind='stages' order by step desc, rowid desc limit 1",
                [rid, rid],
            ).fetchone()
            try:
                out[rid] = json.loads(row[0]) if row else []
            except ValueError:
                out[rid] = []
    finally:
        con.close()
    return out


class TableNotBuilt(Exception):
    """thorp.table (the other side of the table) is not importable yet."""


def _table():
    try:
        from thorp import table
    except ImportError as e:
        raise TableNotBuilt(f"thorp.table is not built yet ({e})") from e
    return table


def api_table_transcript(run: str) -> list[dict]:
    """Every exchange at the table with one sailing, oldest first (thorp.table.transcript)."""
    return _table().transcript(run)


def api_table_reply(body: dict) -> dict:
    """One answer at the table (Table Talk): the sailing named answers the question after the history,
    at the temperature asked; thorp.table.reply keeps the exchange in the sailing's transcript."""
    question = str(body.get("question") or "").strip()
    if not question:
        raise ValueError("ask a question first")
    temperature = min(2.0, max(0.0, float(body.get("temperature", 0.8))))
    max_tokens = min(1000, max(1, int(body.get("max_tokens", 200))))
    seed = body.get("seed")
    history = [
        {"q": str(h.get("q", "")), "a": str(h.get("a", ""))} for h in body.get("history") or []
    ]
    return _table().reply(
        str(body["run"]),
        history,
        question,
        temperature=temperature,
        max_tokens=max_tokens,
        seed=None if seed in (None, "") else int(seed),
    )


TOMES = "lists/hole-cards-unseen.csv"
_tome_ids: list[str] | None = None


def _tomes_ids() -> list[str]:
    global _tome_ids
    if _tome_ids is None:
        from thorp.sources.gutenberg import resolve_list

        _tome_ids = [f"pg{r.chosen}" for r in resolve_list(TOMES) if r.chosen]
    return _tome_ids


def api_tomes() -> dict:
    """The Forgotten Tomes: each book's catalogue facts, every Thorp run's latest score on it, and
    every outside model's."""
    from thorp import manifest

    ids = _tomes_ids()
    books = manifest.get_many(ids)
    released = {}
    with open(paths.resolve(TOMES), encoding="utf-8", newline="") as f:
        import csv

        for row, b in zip(csv.DictReader(f), ids, strict=False):
            released[b] = (row.get("text") or "").replace("released ", "")
    scores: dict[str, dict] = {}
    for r in _rows(
        """select r.name, r.ship, e.book_id, e.bpb from evals e join runs r using(run_id)
           where e."set"='hole-cards-unseen'
             and e.step=(select max(step) from evals x where x.run_id=e.run_id and x."set"='hole-cards-unseen')"""
    ):
        scores.setdefault(r["ship"] or r["name"], {})[r["book_id"]] = r["bpb"]
    for f in sorted((paths.data_dir() / "compare").glob("*__hole-cards-unseen.json")):
        try:
            x = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        scores[x["model"].split("/")[-1]] = {b["book_id"]: b["bpb"] for b in x.get("books", [])}
    return {
        "books": [
            {
                "book_id": b,
                "title": books[b].title if b in books else b,
                "author": books[b].author if b in books else "",
                "bytes": books[b].bytes if b in books else None,
                "released": released.get(b, ""),
            }
            for b in ids
        ],
        "scores": scores,
    }


def api_shelf(run: str) -> list[dict]:
    """A run's training shelf, from its step-0 recipe artifact."""
    a = _rows(
        "select a.text from artifacts a join runs r using(run_id) where (r.name=? or r.run_id=?)"
        " and a.kind='recipe' order by a.rowid desc limit 1",
        [run, run],
    )
    return json.loads(a[0]["text"]) if a and a[0]["text"] else []


def api_book(book_id: str, offset: int = 0, length: int = 20000) -> dict:
    """A slice of a fetched book's stripped text (the text Thorp trains and scores on)."""
    from thorp import manifest
    from thorp.sources import load_text

    book = manifest.get(book_id)
    if book is None:
        raise LookupError(f"no book {book_id}")
    text = load_text(book_id)
    offset = max(0, min(int(offset), len(text)))
    length = max(1000, min(int(length), 100000))
    return {
        "book_id": book_id,
        "title": book.title,
        "author": book.author,
        "language": book.language,
        "chars": len(text),
        "offset": offset,
        "text": text[offset : offset + length],
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str, cache: str = "no-store"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, default=str).encode(), "application/json")

    def do_POST(self):  # noqa: N802
        """Only the table writes: POST /api/table/reply {run, question, history, temperature, ...}."""
        u = urlparse(self.path)
        if u.path != "/api/table/reply":
            return self._send(404, b"not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
            return self._json(200, api_table_reply(body))
        except TableNotBuilt as e:
            return self._json(503, {"error": str(e)})
        except (
            LookupError
        ) as e:  # no such run, or no checkpoint to talk to (thorp.table's own words)
            return self._json(404, {"error": str(e.args[0] if e.args else e)})
        except (ValueError, KeyError) as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": repr(e)})

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                page = _static("index.html")
                return (
                    self._send(200, page[0], page[1])
                    if page
                    else self._send(503, NOT_BUILT, "text/html; charset=utf-8")
                )
            if not u.path.startswith("/api/"):
                got = _static(u.path)
                if got is None:
                    return self._send(404, b"not found", "text/plain")
                # the build names its assets by content hash, so they never go stale
                hashed = u.path.startswith("/assets/")
                return self._send(
                    200,
                    got[0],
                    got[1],
                    "public, max-age=31536000, immutable" if hashed else "no-store",
                )
            routes = {
                "/api/runs": lambda: api_runs(),
                "/api/metrics": lambda: api_metrics(q["run"]),
                "/api/evals": lambda: api_evals(q["run"]),
                "/api/run": lambda: api_run(q["run"]),
                "/api/compare": lambda: api_compare(),
                "/api/ladder": lambda: api_ladder(),
                "/api/rung": lambda: api_rung(q["preset"], q.get("limit", 0)),
                "/api/tomes": lambda: api_tomes(),
                "/api/waypoints": lambda: api_waypoints(q["preset"], q.get("limit", 30)),
                "/api/essay": lambda: api_essay(q["name"]),
                "/api/voyages": lambda: api_voyages(),
                "/api/ships": lambda: api_ships(),
                "/api/voyage": lambda: api_voyage_series(q["key"]),
                "/api/discoveries": lambda: api_discoveries(),
                "/api/sieves": lambda: api_sieves(),
                "/api/table/transcript": lambda: api_table_transcript(q["run"]),
                "/api/stages": lambda: api_stages(q.get("runs", "")),
                "/api/trick": lambda: api_trick_series(q["key"]),
                "/api/chain": lambda: api_chain(q["key"]),
                "/api/shelves": api_shelves,
                "/api/shelf_books": lambda: api_shelf_books(q["path"]),
                "/api/leaderboard": api_leaderboard,
                "/api/bridge": api_bridge,
                "/api/leaderboard/internal": api_leaderboard_internal,
                "/api/smoking_qwen": api_smoking_qwen,
                "/api/climb": lambda: api_climb(q.get("runs", "")),
                "/api/shelf": lambda: api_shelf(q["run"]),
                "/api/book": lambda: api_book(q["id"], q.get("offset", 0), q.get("length", 20000)),
                "/api/experiment": lambda: api_experiment(q.get("prefix", "content-")),
            }
            if u.path not in routes:
                return self._send(404, b"not found", "text/plain")
            body = json.dumps(routes[u.path](), default=str).encode()
            return self._send(200, body, "application/json")
        except TableNotBuilt as e:
            return self._send(503, json.dumps({"error": str(e)}).encode(), "application/json")
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": repr(e)}).encode(), "application/json")


def serve(port: int = 8787) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:  # start warming the slow payloads now, so the first visit finds them ready
        from thorp import shelves

        _warm("shelves", shelves.payload)
    except Exception:  # noqa: BLE001
        pass
    print(f"thorp dash on http://localhost:{port}  (ledger {paths.ledger_path()})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
