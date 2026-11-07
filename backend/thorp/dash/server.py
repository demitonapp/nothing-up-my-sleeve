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
import re
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


def _finite(obj):
    """NaN and infinity become null: JSON has no NaN, and one in a payload (a reading that failed)
    would stop the browser from reading the whole response."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


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
        p = paths.ROUTER / "specs" / f
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
        if not isinstance(
            x, dict
        ):  # a list of runs (nevermore-vs-trigrams.json), not one model's comparison
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
        from thorp import expeditions as voyages
        from thorp import fleet
    except ImportError:
        return {}
    out = {}
    for v in fleet.EXPEDITIONS.values():
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
    from thorp import expeditions as voyages

    return voyages.payload()


def api_voyage_series(key: str) -> dict:
    """For one voyage's runs, each star's score at every reading, so a chart can show the step at
    which a line crosses its threshold: first light. A run that received heads from another
    (a `transplant` artifact: the Magician's Apprentice) carries the record, and the donor run is
    added (role "donor") so its curve sits beside the receivers'."""
    from thorp import expeditions as voyages
    from thorp import fleet

    v = fleet.EXPEDITIONS[key]
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


def _card_verdicts() -> dict:
    """Which cards the chainers need (thorp.card_check: necessary when every model that chains plays
    it, a marker when only the chainers do, valid when the reading is trusted), by star key."""
    try:
        from thorp import card_check

        return card_check.payload().get("verdicts", {})
    except Exception:  # noqa: BLE001
        return {}


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

    p = paths.ROUTER / "data" / "compare" / "chain-grades.json"
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
    from thorp import library as shelves

    value, busy, error = _warm("shelves", shelves.payload)
    fits, fbusy, ferror = (
        _warm("fitouts", shelves.fitouts) if hasattr(shelves, "fitouts") else (None, False, None)
    )
    return {
        "shelves": value,
        "computing": value is None and busy,
        "error": error,
        # the fitouts: the training material matched to the pretraining and post-training stages
        "fitouts": fits,
        "fitouts_computing": fits is None and fbusy,
        "fitouts_error": ferror,
    }


def api_shelf_books(path: str) -> list[dict]:
    """A shelf's rows (title, author, language, family) with the fetched book each resolves to,
    where it can be told without fetching, so the reader can open it."""
    import csv

    from thorp import manifest

    p = paths.ROUTER / path
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


def api_fitouts(preset: str = "") -> dict:
    """A class's fitouts (thorp.shelves.fitouts, kept warm), each run with the four necessary cards'
    latest readings (one head and shared, lit at the card's mark), so a class page can show the
    fitout's progress stage by stage (fo-<key>-pre-s*, -post1-s*, -post2-s*)."""
    from thorp import fleet
    from thorp import library as shelves

    fits, busy, error = (
        _warm("fitouts", shelves.fitouts) if hasattr(shelves, "fitouts") else ([], False, None)
    )
    if fits is None:
        return {"fitouts": None, "computing": busy, "error": error}
    mine = [f for f in fits if not preset or f.get("preset") == preset]
    cards = [k for k in CENSUS_CARDS if k in fleet.STARS]
    con = _con()
    try:
        for f in mine:
            readings = {}
            for r in f.get("runs", []):
                row = con.execute(
                    "select run_id, status from runs where name=? order by started desc limit 1",
                    [r["run"]],
                ).fetchone()
                if not row:
                    continue
                r["status"] = row[1] or r.get("status")
                per = {}
                for k in cards:
                    st = fleet.STARS[k]
                    vals = {}
                    for kind, metric in (
                        ("one", st.metric),
                        ("shared", getattr(st, "shared_metric", None)),
                    ):
                        if not metric:
                            continue
                        got = con.execute(
                            "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
                            [row[0], metric],
                        ).fetchone()
                        if got and got[0] is not None:
                            vals[kind] = got[0]
                    if vals:
                        best = max(vals.values())
                        per[k] = {**vals, "lit": best >= st.threshold, "threshold": st.threshold}
                readings[r["run"]] = per
            f["run_cards"] = readings
    finally:
        con.close()
    return {"fitouts": mine, "computing": False, "error": error}


CLASS_CARDS = {  # card -> (one-head metric, a layer's best two or None), as scripts/make_card_census.py reads them
    "previous_word": ("stars/previous_word/max_score", "stars/previous_word/shared_score"),
    "nevermore": ("nevermore/natural_max_score", None),
    "mover": ("stars/mover/max_score", "stars/mover/shared_score"),
    "comparator": ("stars/comparator/max_score", "stars/comparator/shared_score"),
}


_class_cards_cache: dict[str, tuple[float, dict]] = {}


def api_class_cards(preset: str) -> dict:
    """Cached a minute: the page asks on every refresh and the read scans every card row of the class."""
    import time

    hit = _class_cards_cache.get(preset)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    out = _class_cards(preset)
    _class_cards_cache[preset] = (time.time(), out)
    return out


def _class_cards(preset: str) -> dict:
    """The one thing a class's Overview shows (Justin, 2026-11-07: "one thing that encompasses as much as
    there is to know"): the four necessary cards against their marks, each at the best reading any voyage
    of the class reached (the better of one head and a layer's best two, at any step: a card that lit and
    faded still counts as drawn), with the voyage and step, how many voyages lit it, and where the newest
    finished voyage ended; beside them the cause-and-effect chaining gain (eight items: noise within
    about ±0.1). A class's voyages are those whose preset is the class's or a variant of it (300k-h4)."""
    from thorp import fleet

    con = _con()
    try:
        runs = con.execute(
            "select run_id, name, started, status, json_extract(spec_json,'$.model.preset') p from runs "
            "where p = ? or p like ? order by started",
            [preset, f"{preset}-%"],
        ).fetchall()
        ids = [r["run_id"] for r in runs]
        by = {r["run_id"]: r for r in runs}
        names = [m for pair in CLASS_CARDS.values() for m in pair if m] + ["tricks/logic_test/gain_cause"]
        peak, last = {}, {}
        if ids:
            marks = ",".join("?" * len(ids))
            for rid, name, step, v in con.execute(
                f"select run_id, name, step, value from metrics where run_id in ({marks}) "
                f"and name in ({','.join('?' * len(names))}) order by run_id, name, step",
                ids + names,
            ):
                if v is None or v != v:
                    continue
                k = (rid, name)
                if k not in peak or v > peak[k][0]:
                    peak[k] = (v, step)
                last[k] = (v, step)
    finally:
        con.close()
    finished = [r for r in runs if r["status"] == "finished"]
    newest = finished[-1]["run_id"] if finished else None

    def reading(rid, metrics, table):
        got = [table[(rid, m)] for m in metrics if m and (rid, m) in table]
        return max(got) if got else None

    cards = []
    for card, pair in CLASS_CARDS.items():
        star = fleet.STARS[card]
        th = star.threshold
        best, end_best, lit_by, held_by = None, None, [], []
        for r in runs:
            x = reading(r["run_id"], pair, peak)
            if x is None:
                continue
            if best is None or x[0] > best["value"]:
                best = {"value": x[0], "step": x[1], "run": r["name"], "run_id": r["run_id"]}
            if x[0] >= th:
                lit_by.append(r["name"])
            e = reading(r["run_id"], pair, last) if r["status"] == "finished" else None
            if e is not None:
                if end_best is None or e[0] > end_best["value"]:
                    end_best = {"value": e[0], "step": e[1], "run": r["name"], "run_id": r["run_id"]}
                if e[0] >= th:
                    held_by.append(r["name"])
        now = reading(newest, pair, last) if newest else None
        cards.append(
            {
                "card": card,
                "name": star.name,
                "threshold": th,
                "best": best,  # the peak at any step: touched, perhaps for a moment
                "end_best": end_best,  # the best a finished voyage ended with: held
                "held": bool(held_by),
                "held_by": held_by,
                "lit": bool(lit_by),
                "lit_by": lit_by,
                "now": None if now is None else {"value": now[0], "run": by[newest]["name"]},
            }
        )
    cause = [
        (peak[(r["run_id"], "tricks/logic_test/gain_cause")], r["name"])
        for r in runs
        if (r["run_id"], "tricks/logic_test/gain_cause") in peak
    ]
    cause_last = [
        last[(r["run_id"], "tricks/logic_test/gain_cause")][0]
        for r in finished
        if (r["run_id"], "tricks/logic_test/gain_cause") in last
    ]
    top = max(cause, default=None, key=lambda c: c[0][0])
    return {
        "preset": preset,
        "voyages": len(runs),
        "read": len({rid for rid, _ in peak}),
        "cards": cards,
        "held": sum(c["held"] for c in cards),
        "touched": sum(c["lit"] for c in cards),
        "cause": {
            "best": None if top is None else {"value": top[0][0], "step": top[0][1], "run": top[1]},
            "finished_range": [min(cause_last), max(cause_last)] if cause_last else None,
            "noise": 0.1,
            # chaining is judged on where voyages end, never on a passing peak
            "chains": bool(cause_last and max(cause_last) > 0.1),
        },
    }


def api_class_score(preset: str) -> dict:
    """A class's live scoring readings (registry.LADDER's "scored": the four necessary cards held,
    then cause and effect, then chaining two facts) from its current version (the leaderboard's best
    ship, leaderboard.thorp_entry: the mean of its sailings' latest), and the best cards held so far
    in its fitout's census (data/runs/cards/fitout-census-<key>-readings.json, once it lands)."""
    from thorp import fleet, leaderboard

    best = next(
        (
            b["best"]
            for b in leaderboard.payload().get("board", [])
            if b.get("best") and b["best"].get("preset") == preset
        ),
        None,
    )
    out: dict = {"preset": preset, "version": None}
    if best:
        e = leaderboard.thorp_entry(best["ship_key"]) or {}
        cards = e.get("cards") or {}
        lit = {
            k: bool((cards.get(k) or {}).get("lit") or (cards.get(k) or {}).get("lit_shared"))
            for k in CENSUS_CARDS
        }
        chaining = [
            (e.get(k) or {}).get("lift")
            for k in ("nature_test", "mill_test", "between_test", "pigeonhole_test")
        ]
        chaining = [v for v in chaining if isinstance(v, (int, float))]
        out.update(
            version=best.get("name"),
            ship_key=best.get("ship_key"),
            ship=best.get("ship"),
            cards=lit,
            held=sum(lit.values()),
            cause=(e.get("logic_test") or {}).get("gain_cause"),
            chaining=sum(chaining) / len(chaining) if chaining else None,
        )
    # the census around this class's fitout: the most cards any variation's latest stage holds
    root = paths.ROUTER
    for key, fo in getattr(fleet, "FITOUTS", {}).items():
        fp = getattr(fo, "preset", None) or (fo.get("preset") if isinstance(fo, dict) else None)
        if fp != preset:
            continue
        f = root / "data" / "runs" / "cards" / f"fitout-census-{key}-readings.json"
        if not f.exists():
            out["census"] = {"key": key, "written": False}
            continue
        try:
            data = json.loads(f.read_text())
        except ValueError:
            continue
        top = None
        for variation, stages in data.items():
            read = [st for st in stages if not st.get("missing")]
            if not read:
                continue
            last = read[-1]
            n = sum(1 for k in CENSUS_CARDS if (last.get(k) or {}).get("lit"))
            if top is None or n > top["held"]:
                top = {"held": n, "variation": variation}
        out["census"] = {"key": key, "written": True, **(top or {"held": None})}
    return out


def _knockout_files() -> list[Path]:
    return sorted(
        (paths.ROUTER / "data" / "compare").glob("knockout-*.json")
    )


def api_knockout(model: str = "") -> dict:
    """The knockout (fleet.EXPEDITIONS["knockout"], thorp/knockout.py; DECISIONS.md "The knockout,
    pre-registered"): in a model that chains, each card's 8 strongest heads silenced and the logic
    deck and the chaining tests read again, beside three random draws of 8 heads. One model's
    result (data/compare/knockout-<model, / as __>.json), or every result when no model is named."""
    from thorp import fleet

    competitors = getattr(fleet, "COMPETITORS", {})
    out = []
    for f in _knockout_files():
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        d.setdefault("model", f.stem[len("knockout-") :].replace("__", "/"))
        if model and d["model"] != model:
            continue
        d["label"] = (competitors.get(d["model"]) or (None,))[0] or _short_model(d["model"])
        out.append(d)
    return {"results": out}


# ---- the fitout builder (#/shelves; thorp/fitouts.py): mix shelves into a fitout, save it, build it for a class


def api_fitout_builder() -> dict:
    """What the builder needs: the hand-curated fitouts (fleet.FITOUTS, in the saved form) and the
    saved ones (data/fitouts/), the selections and the classes a fitout can be built for (the first
    four rungs of the ladder)."""
    from thorp import fitouts, fleet
    from thorp.models.registry import LADDER

    curated = []
    for k in getattr(fleet, "FITOUTS", {}):
        try:
            curated.append(fitouts.from_curated(k))
        except Exception:  # noqa: BLE001
            continue
    return {
        "curated": curated,
        "saved": fitouts.saved(),
        "select": list(fitouts.SELECT),
        "classes": [{"preset": r["preset"], "name": r["name"]} for r in LADDER[:4]],
        "bytes_per_token": fitouts.BYTES_PER_TOKEN,
    }


def api_shelf_trigrams(path: str) -> dict:
    """A shelf's books by trigram repetition (thorp.trigrams.book_stats over the shelf's book ids, as
    the warm shelves payload carries them): each book's repeat rate and variety, and the frontier."""
    from thorp import library as shelves
    from thorp import trigrams

    value, busy, _ = _warm("shelves", shelves.payload)
    if value is None:
        return {"computing": True}
    sh = next((x for x in value if x["path"] == path), None)
    if sh is None:
        raise LookupError(f"no shelf {path}")
    ids = sh.get("book_ids") or []
    stats = trigrams.book_stats(ids) if ids else {}
    tri = sh.get("trigrams") or {}
    return {
        "path": path,
        "books": [{"id": b, **v} for b, v in stats.items() if v],
        "frontier": tri.get("frontier") or [],
        "measured": bool(tri.get("measured")),
    }


def api_fitout_save(body: dict) -> dict:
    from thorp import fitouts

    key = fitouts.save(body.get("fitout") or body)
    return {"key": key, "fitout": fitouts.load(key)}


def api_fitout_queue(body: dict) -> dict:
    """Builds a saved (or hand-curated) fitout for a class and puts its runs in the queue."""
    from thorp import fitouts

    key, preset = body.get("key"), body.get("preset")
    if not key or not preset:
        raise ValueError("a fitout key and a class are needed to queue")
    seeds = tuple(int(x) for x in (body.get("seeds") or [1, 2]))
    where = body.get("where") if body.get("where") in ("top", "end") else "end"
    return {"lines": fitouts.queue(key, preset, seeds=seeds, where=where)}


def api_series(runs: str, metrics: str) -> dict:
    """Named metrics over steps for named runs: {run: {metric: [steps, values]}} (the last reading at a
    step wins, so a re-scored step shows its latest)."""
    out: dict = {}
    con = _con()
    try:
        for run in [x for x in runs.split(",") if x][:40]:
            row = con.execute(
                "select run_id from runs where name=? or run_id=? order by started desc limit 1",
                [run, run],
            ).fetchone()
            if not row:
                continue
            out[run] = {}
            for m in [x for x in metrics.split(",") if x][:12]:
                by_step: dict[int, float] = {}
                for step, value in con.execute(
                    "select step, value from metrics where run_id=? and name=? order by step, rowid",
                    [row[0], m],
                ):
                    by_step[step] = value
                if by_step:
                    steps = sorted(by_step)
                    out[run][m] = [steps, [by_step[k] for k in steps]]
    finally:
        con.close()
    return out


def api_governance() -> dict:
    """Thorp's rules as Beer's Viable System Model (thorp/vsm.py): the five systems (S1 operations to
    S5 policy) with their code, and the live audit: the voyages, the queue's collisions, each policy's
    enforcement and the queued runs that break it, the outside world Thorp measures itself against.
    Read-only: switching a policy is Justin's S5 decision, made in data/policies.json."""
    import dataclasses

    from thorp import vsm

    return {
        "systems": [dataclasses.asdict(s) for s in vsm.SYSTEMS.values()],
        "audit": vsm.audit(),
    }


def api_acquisition() -> dict:
    """Acquisition, the books the voyages read, as a viable system one level down (thorp/acquisition.py):
    its five systems with their code; S1 the intakes and the log of every book's verdict, S2 the intake lock,
    the helm and each source's cache, S3 the intake gate's refusals, S4 the sources and the legal ceiling,
    S5 the rules. The audit (S3*) is served apart, warm (/api/acquisition/audit)."""
    from thorp import acquisition

    return acquisition.payload()


def api_acquisition_audit() -> dict:
    """S3* of acquisition (acquisition.audit): every registered book against the rules, duplicates, missing
    files, a sample re-hashed, and the cleaning audit. A few seconds, so kept warm (see _warm)."""
    from thorp import acquisition

    value, busy, error = _warm("acquisition_audit", acquisition.audit)
    return {"audit": value, "computing": value is None and busy, "error": error}


# ---- the words since 2026-11-07 16:20 (fleet.TERMS): an expedition is a line of experiments (was a voyage), a voyage
# is one ship's run (was a run), a library is a book list (was a shelf). Storage keeps run_id and the runs table.


def api_expeditions_overview() -> dict:
    """The queue at a glance (thorp.expeditions.overview): the voyage at sea, the queue's voyages and
    hours left, and per expedition its voyages at sea, finished, failed and queued, and where its next
    one stands in the queue."""
    from thorp import expeditions

    return expeditions.overview()


def api_queue() -> dict:
    """The queue as a table (Justin, 17:05: "view the queue so each voyage with its goal"): the voyage at
    sea, then every line of specs/queue.txt in order, each voyage with its goal (its spec's question),
    its expedition, class and seed, and about when it sails (each queued voyage before it at its class's
    mean wall time over finished voyages); a `cmd:` line is a step between voyages."""
    import yaml

    from thorp import fleet

    root = paths.ROUTER
    con = _con()
    try:
        status = dict(con.execute("select name, status from runs"))
        wall = dict(
            con.execute(
                "select json_extract(spec_json,'$.model.preset'), avg(wall_minutes) from runs "
                "where status='finished' and wall_minutes > 0 group by 1"
            )
        )
        sea = con.execute(
            "select name, ship, started, spec_json from runs where status='running' order by started"
        ).fetchall()
    finally:
        con.close()

    fitout_names: dict[str, str | None] = {}

    def fitout_of_voyage(name: str, spec: dict) -> dict | None:
        """The named fitout a voyage is a variation of (its spec's `fitout`, S5 policy 'fitout'), with its
        stage: from a fitout run's name (`-pre-`, `-post<i>-`), else post-training when it is seeded from
        another voyage. `named: false` when the spec names none (the gate will refuse it)."""
        f = spec.get("fitout") if isinstance(spec.get("fitout"), dict) else None
        if not f or not f.get("key"):
            return {"key": None, "name": None, "variation": None, "stage": None, "named": False}
        key = f["key"]
        if key not in fitout_names:
            fitout_names[key] = fleet.named_fitout(key)
        stage = re.search(r"-(pre|post\d+)-s\d+$", name)
        st = stage.group(1) if stage else None
        return {
            "key": key,
            "name": fitout_names[key] or key,
            "variation": f.get("variation"),
            "stage": "pretraining"
            if st == "pre"
            else f"post-training {st[4:]}"
            if st
            else "post-training"
            if spec.get("seeded_from") or spec.get("transplant")
            else "pretraining",
            "named": fitout_names[key] is not None,
        }

    def row(name, ship, spec, state, n):
        m = spec.get("model") or {}
        ex = fleet.expedition_of_label(name, ship)
        return {
            "n": n,
            "kind": "voyage",
            "name": name,
            "ship": ship or "",
            "goal": spec.get("question") or spec.get("experiment") or "",
            "experiment": spec.get("experiment") or "",
            "fitout": fitout_of_voyage(name, spec),
            "expedition": ex,
            "expedition_name": fleet.EXPEDITIONS[ex].name if ex in fleet.EXPEDITIONS else None,
            "preset": m.get("preset"),
            "seed": spec.get("seed"),
            "status": state,
        }

    rows = []
    for name, ship, started, sj in sea:
        try:
            spec = json.loads(sj or "{}")
        except ValueError:
            spec = {}
        if not spec.get("question"):  # the ledger's copy may not keep it; the spec file does
            f = next(iter((root / "specs").rglob(f"{name}.yaml")), None)
            spec = {**spec, **((yaml.safe_load(f.read_text()) or {}) if f else {})}
        rows.append({**row(name, ship, spec, "at sea", None), "started": started})
    lines = [
        ln.strip()
        for ln in (root / "specs" / "queue.txt").read_text().splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    ahead, unknown = 0.0, 0
    for i, ln in enumerate(lines, 1):
        if ln.startswith("cmd:"):
            cmd = ln[4:].strip()
            words = cmd.split()
            scripts = [w for w in words if w.endswith((".py", ".sh"))] or words[:1]
            script = scripts[0] if scripts else ""
            rows.append(
                {"n": i, "kind": "step", "name": Path(script).name, "cmd": cmd, "status": "queued"}
            )
            continue
        p = root / "specs" / f"{ln}.yaml"
        spec = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
        name = spec.get("name") or Path(ln).name
        r = row(name, spec.get("ship"), spec, status.get(name) or "queued", i)
        if r["status"] == "running":
            r["status"] = "at sea"
        r["spec"] = ln
        r["missing"] = not p.exists()
        r["starts_in_min"] = round(ahead)
        # a voyage ahead of it has no time yet: it sails no sooner than this
        r["at_least"] = unknown > 0
        mins = wall.get(r["preset"])
        if mins is None:
            unknown += 1
        else:
            ahead += mins
        rows.append(r)
    return {"rows": rows, "hours_left": round(ahead / 60, 1), "without_a_time": unknown}


def _where_of(aboard: dict) -> str:
    """One word for where a voyage's reading came from: the worst of its libraries'."""
    order = (
        "outside the stores",
        "drawn from the stores",
        "the trigram stores",
        "the prose stores",
    )
    got = {lib.get("where") for lib in aboard.get("libraries", [])}
    return next((w for w in order if w in got), "")


def api_voyage_library(run_id: str) -> dict:
    """The library aboard a voyage (thorp.library.aboard): its libraries with each one's stage, where
    it came from, books and hash; whether that was recorded when it sailed; its opt-in and refusals."""
    from thorp import library

    a = library.aboard(run_id)
    a["where"] = _where_of(a)
    return a


def api_voyages_where(runs: str) -> dict:
    """Each voyage's where-badge, for the tables that list voyages: {run_id: where}."""
    from thorp import library

    out = {}
    for rid in [x for x in runs.split(",") if x][:400]:
        try:
            out[rid] = _where_of(library.aboard(rid))
        except Exception:  # noqa: BLE001
            continue
    return out


# ---- the observation deck (each expedition's page): its voyages at sea, read live from their logs (data/runs/<id>.log) and
# the ledger, with its finds: each star's first light and each trick's first performance, in order (the star chart).

LOG_LINE = re.compile(r"^\[(\d\d:\d\d:\d\d)\] (.*)$")
STEP_LINE = re.compile(
    r"step (\d+)/(\d+) loss ([\d.]+) lr ([\d.e+-]+) (\d+) tok/s(?: mem ([\d.]+) GB)?"
)
DECK_CARDS = ("previous_word", "nevermore", "mover", "comparator")


def _log_tail(run_id: str, nbytes: int = 400_000) -> list[tuple[str, str]]:
    p = paths.data_dir() / "runs" / f"{run_id}.log"
    if not p.exists():
        return []
    with p.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - nbytes))
        lines = f.read().decode("utf-8", "replace").splitlines()
    head = []
    if size > nbytes:  # the departure lines sit at the top of the log
        with p.open("rb") as f:
            head = f.read(8000).decode("utf-8", "replace").splitlines()[:12]
    out = []
    for ln in head + lines[1 if size > nbytes else 0 :]:
        m = LOG_LINE.match(ln)
        if m:
            out.append((m.group(1), m.group(2)))
    seen, uniq = set(), []
    for t in out:  # the head and the tail may overlap
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def _sky() -> dict:
    """The star chart's sky: every star (by level, with what it rests on) and every trick (the chains
    of discovery tests rung by rung, and the tricks beside them with the stars expected to do them);
    one not built yet (no evaluator) can never be found, and is drawn faint."""
    from thorp import fleet

    chains = fleet.chains()
    in_chain = {k for c in chains for k in c}
    return {
        "stars": [
            {
                "key": s.key,
                "name": s.name,
                "level": s.level,
                "rests_on": list(s.rests_on),
                "threshold": s.threshold,
                "built": bool(s.evaluator),
                "about": s.about,
            }
            for s in fleet.STARS.values()
        ],
        "tricks": [
            {
                "key": t.key,
                "name": t.name,
                "threshold": t.threshold,
                "performed_by": list(t.performed_by),
                "built": bool(t.evaluator),
                "about": t.about,
            }
            for t in fleet.TRICKS.values()
            if t.key not in in_chain and (t.evaluator or t.performed_by)
        ],
        "chains": [
            [
                {
                    "key": k,
                    "name": fleet.TRICKS[k].name,
                    "threshold": fleet.TRICKS[k].threshold,
                    "built": bool(fleet.TRICKS[k].evaluator),
                }
                for k in c
            ]
            for c in chains
        ],
    }


def _heads(con, rid: str) -> dict:
    """Every head's score on every star, at each step the voyage read them (the layer x head matrices
    the stars, nevermore and cards evaluators keep as artifacts, every eval): for tracing a card
    through the sieves to the heads that form it. The Nevermore is read on the natural passages
    (its star's metric, nevermore/natural_max_score)."""
    from thorp import fleet

    steps: dict[int, dict] = {}
    for step, kind, text in con.execute(
        "select step, kind, text from artifacts where run_id=? and kind in ('stars','nevermore','cards')"
        " and step is not null order by step",
        [rid],
    ):
        try:
            rec = json.loads(text or "{}")
        except ValueError:
            continue
        m = steps.setdefault(step, {})
        if kind == "nevermore":
            if rec.get("natural_scores") is not None:
                m["nevermore"] = rec["natural_scores"]
            continue
        for k, v in rec.items():
            if k in fleet.STARS and isinstance(v, list) and v and isinstance(v[0], list):
                m[k] = v
    return {
        "marks": {k: s.threshold for k, s in fleet.STARS.items()},
        "names": {k: s.name for k, s in fleet.STARS.items()},
        "steps": [
            {"step": k, "m": v}
            for k, v in sorted(steps.items())
            if "previous_word" in v and "nevermore" in v
        ],
    }


def _finds(con, rid: str) -> dict:
    """A voyage's finds, in the order it made them: each star's first light (its strongest head, or
    two heads together, at its mark) and each trick's first performance (fleet.performed: its metric at
    the threshold and, for a matched-pairs test, two in three pairs right), from the ledger. Each with
    the step it came at and the reading then; the latest reading too, for those not found yet."""
    from thorp import fleet

    names = set()
    for st in fleet.STARS.values():
        names |= {st.metric, st.shared_metric} - {""}
    for t in fleet.TRICKS.values():
        if t.evaluator:
            names |= {t.metric, t.metric.rsplit("/", 1)[0] + "/score"}
    rows = con.execute(
        f"select step, name, value from metrics where run_id=? and name in ({','.join('?' * len(names))})"
        " and value is not null order by step, rowid",
        [rid, *names],
    ).fetchall()
    seen: dict[str, float] = {}  # the readings so far, the latest of each
    found: dict[str, dict] = {}
    latest: dict[str, float] = {}

    def check(step: int) -> None:
        for st in fleet.STARS.values():
            one, two = seen.get(st.metric), seen.get(st.shared_metric) if st.shared_metric else None
            best = max([v for v in (one, two) if v is not None], default=None)
            if best is None:
                continue
            latest["star:" + st.key] = best
            if ("star:" + st.key) not in found and best >= st.threshold:
                found["star:" + st.key] = {
                    "kind": "star",
                    "key": st.key,
                    "name": st.name,
                    "step": step,
                    "value": best,
                    "threshold": st.threshold,
                    "how": "one head" if one is not None and one >= st.threshold else "two heads",
                }
        for t in fleet.TRICKS.values():
            v = seen.get(t.metric)
            if not t.evaluator or v is None:
                continue
            latest["trick:" + t.key] = v
            if ("trick:" + t.key) not in found and fleet.performed(t.key, seen):
                found["trick:" + t.key] = {
                    "kind": "trick",
                    "key": t.key,
                    "name": t.name,
                    "step": step,
                    "value": v,
                    "threshold": t.threshold,
                }

    at = None
    for step, name, value in rows:
        if value != value:  # NaN
            continue
        if at is not None and step != at:
            check(at)
        at = step
        seen[name] = value
    if at is not None:
        check(at)
    out = sorted(found.values(), key=lambda f: (f["step"], f["kind"] != "star", f["name"]))
    for i, f in enumerate(out):
        f["order"] = i + 1
    return {"finds": out, "latest": latest}


def _deck(run: dict) -> dict:
    """One voyage at sea, for the observation deck."""
    from thorp import fleet

    rid = run["run_id"]
    log = _log_tail(rid)
    steps = [(t, STEP_LINE.search(x)) for t, x in log if x.startswith("step ")]
    steps = [(t, m) for t, m in steps if m]
    last = steps[-1][1] if steps else None
    step, total = (int(last.group(1)), int(last.group(2))) if last else (None, None)
    # pace from the last stretch of step lines: seconds per step, and so the time left
    eta = None
    if len(steps) >= 2:
        (t0, m0), (t1, m1) = steps[max(0, len(steps) - 40)], steps[-1]
        h0, h1 = (
            sum(int(x) * k for x, k in zip(t.split(":"), (3600, 60, 1), strict=True))
            for t in (t0, t1)
        )
        dt, ds = (h1 - h0) % 86400, int(m1.group(1)) - int(m0.group(1))
        if dt > 0 and ds > 0 and total:
            eta = (total - step) * dt / ds
    loss = [
        [int(m.group(1)) for _, m in steps[-200:]],
        [float(m.group(3)) for _, m in steps[-200:]],
    ]
    # the latest readings: the four necessary cards, the Nevermore, the logic deck
    con = _con()
    try:

        def latest(name: str):
            r = con.execute(
                "select value, step from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
                [rid, name],
            ).fetchone()
            return (r[0], r[1]) if r and r[0] is not None and r[0] == r[0] else (None, None)

        cards = {}
        for k in DECK_CARDS:
            st = fleet.STARS.get(k)
            if not st:
                continue
            one, at = latest(st.metric)
            two, _ = (
                latest(st.shared_metric) if getattr(st, "shared_metric", None) else (None, None)
            )
            best = max([v for v in (one, two) if v is not None], default=None)
            cards[k] = {
                "one": one,
                "shared": two,
                "threshold": st.threshold,
                "lit": best is not None and best >= st.threshold,
                "at": at,
            }
        gain, _ = latest("tricks/logic_test/gain")
        cause, _ = latest("tricks/logic_test/gain_cause")
        hole, _ = latest("eval/hole-cards-unseen/bpb_mean_en")
        fx = _finds(con, rid)
        heads = _heads(con, rid)
    finally:
        con.close()
    return {
        **run,
        "step": step,
        "steps_total": total,
        "eta_s": eta,
        "loss": loss,
        "tokens_per_s": int(last.group(5)) if last else None,
        "mem_gb": float(last.group(6)) if last and last.group(6) else None,
        "cards": cards,
        "logic_gain": gain,
        "cause_gain": cause,
        "hole_cards_bpb": hole,
        "finds": fx["finds"],
        "latest": fx["latest"],
        "heads": heads,
        "sky": _sky(),
        "log_lines": len(log),
    }


def api_observation(expedition: str) -> dict:
    """The observation deck for an expedition: its voyages at sea (thorp.expeditions.overview's at_sea),
    each read live, and where its next voyage stands in the queue when none is at sea."""
    from thorp import expeditions

    ov = expeditions.overview()
    sea = [r for r in ov.get("at_sea", []) if not expedition or r.get("expedition") == expedition]
    mine = next((e for e in ov.get("expeditions", []) if e.get("key") == expedition), None)
    return {
        "expedition": expedition,
        "at_sea": [_deck(r) for r in sea],
        "state": (mine or {}).get("status"),
        "queued": (mine or {}).get("queued"),
        "next_in_queue": (mine or {}).get("next_in_queue"),
        "helm": ov.get("helm"),
        "elsewhere": [r for r in ov.get("at_sea", []) if r.get("expedition") != expedition],
    }


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


def api_bet() -> dict:
    """The $100 bet (thorp.bet.payload): Justin's ladder to a 350m that bets the right way on quantum
    physics for $100 on a rented H100: the theory, the ladder with each rung's time and cost, the
    discrete-atom test, the budget, the gates and the risks."""
    from thorp import bet

    return bet.payload()


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


def _entry_body(v: dict) -> dict:
    """An entry in chain-grades.json's shape (an outside model's, or a Thorp ship's from
    leaderboard.thorp_entry): every rung of the four chains with its class title, the logic deck
    (without its per-item readings), and the cards."""
    from thorp import fleet

    names = {k: t.name for k, t in fleet.TRICKS.items()}
    rungs = [r.title for r in getattr(fleet, "RUNGS", ())]
    chains = []
    for c in fleet.chains():
        chains.append(
            {
                "key": c[-1],
                "name": names.get(c[-1], c[-1]),
                "rungs": [
                    {
                        "key": k,
                        "name": names.get(k, k),
                        "rung": rungs[i] if i < len(rungs) else None,
                        **{kk: x for kk, x in v.get(k, {}).items() if kk != "pairs"},
                    }
                    for i, k in enumerate(c)
                ],
            }
        )
    logic = dict(v.get("logic_test") or {})
    items = logic.pop("items", None)
    if items is not None:
        logic["items_n"] = len(items)
    return {"chains": chains, "logic": logic or None, "cards": v.get("cards")}


def api_thorp(ship: str) -> dict:
    """A Thorp ship as the leaderboard names it (Thorp <class> v<n>), in the competitor page's shape
    (leaderboard.thorp_entry: the mean of its sailings' latest readings), with its version's history
    from data/thorp-versions.json (a version rises only when a new ship beats the last by more than
    the noise)."""
    from thorp import leaderboard

    v = leaderboard.thorp_entry(ship)
    if not v:
        raise LookupError(f"no ship {ship}")
    meta = v.get("_ship", {})
    preset = meta.get("preset")
    try:
        reg = json.loads(
            (paths.ROUTER / "data" / "thorp-versions.json").read_text()
        )
    except (OSError, ValueError):
        reg = {}
    history = reg.get(preset, [])
    mine = next((h for h in history if h.get("ship_key") == ship), None)
    best = next(
        (
            b["best"]
            for b in leaderboard.payload().get("board", [])
            if b.get("best") and b["best"].get("ship_key") == ship
        ),
        None,
    )
    rung = next((r for r in _rows_ladder() if r["preset"] == preset), {})
    return {
        "model": ship,
        "thorp": True,
        "label": (best or {}).get("name")
        or (f"Thorp {preset} v{mine['v']}" if mine else f"Thorp {preset}"),
        "version": (mine or {}).get("v"),
        "crowned": (mine or {}).get("crowned"),
        "history": history,
        "current": bool(best),
        "ship": meta,
        "params": rung.get("total"),
        "competitor": False,
        "ladder": False,
        "scored": True,
        "card_verdicts": _card_verdicts(),
        **_entry_body(v),
    }


def _rows_ladder() -> list[dict]:
    try:
        return api_ladder().get("rungs", [])
    except Exception:  # noqa: BLE001
        return []


def api_competitor(model: str) -> dict:
    """One outside model (a 2-4B competitor or a reference ladder model), as read on Thorp's tests
    (data/compare/chain-grades.json): the four chaining tests, the logic deck (variants, hops,
    relations), its cards (thorp's evaluator "cards": mover, comparator, bridge; previous-word and
    Nevermore not read for outside models yet), every rung of the four chains, and what Thorp must
    match it at (a tenth its size, with the forecast there from smoking_qwen)."""
    from thorp import fleet

    p = paths.ROUTER / "data" / "compare" / "chain-grades.json"
    try:
        models = json.loads(p.read_text()).get("models", {})
    except (OSError, ValueError):
        models = {}
    comp = getattr(fleet, "COMPETITORS", {})
    if model not in models and model not in comp:
        raise LookupError(f"no model {model}")
    v = models.get(model, {})
    label, params = comp.get(model, (None, None))
    body = _entry_body(v)
    try:
        from thorp import smoking_qwen

        params = params or getattr(smoking_qwen, "REFERENCE_PARAMS", {}).get(model)
    except ImportError:
        pass
    tenth = None
    try:
        sq = api_smoking_qwen()
        tenth = next((c for c in sq.get("range", []) if c.get("model") == model), None)
    except Exception:  # noqa: BLE001
        pass
    return {
        "model": model,
        "label": label or _short_model(model),
        "params": params,
        "competitor": model in comp,
        "ladder": model in getattr(fleet, "REFERENCE_LADDER", ()),
        "scored": bool(v),
        **body,
        "card_verdicts": _card_verdicts(),
        "tenth": tenth,
    }


def api_lab(key: str) -> dict:
    """One lab (thorp.labs): its models on Thorp's tests, and its five best and five worst readings,
    each set against the other labs' models on the same test."""
    from thorp import labs

    return labs.payload(key)


CENSUS_CARDS = ("previous_word", "nevermore", "mover", "comparator")


def api_census() -> dict:
    """The card census as ablations of each class's fitout (data/runs/cards/fitout-census-<key>.json:
    {variation: [run per stage: pre, post1, post2]}; the run names are read from the file, since a
    variation may reuse the fitout's own run for a shared stage). For every run, its status and the
    latest readings: the four necessary cards (one head, shared, lit at the card's mark), the logic
    deck's cause-and-effect gain and its chaining gain. The cd-* runs of the first design were never
    run and are not shown."""
    from thorp import fleet

    root = paths.ROUTER
    stars = {k: fleet.STARS[k] for k in CENSUS_CARDS if k in fleet.STARS}
    fitouts = getattr(fleet, "FITOUTS", {})
    out = []
    con = _con()
    try:

        def latest(run_id: str, metric: str):
            got = con.execute(
                "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
                [run_id, metric],
            ).fetchone()
            v = got[0] if got else None
            return v if isinstance(v, (int, float)) and v == v else None

        def reading(run: str) -> dict:
            row = con.execute(
                "select run_id, status from runs where name=? order by started desc limit 1", [run]
            ).fetchone()
            if not row:
                return {"run": run, "status": "queued"}
            r = {"run": run, "status": row[1] or "", "cards": {}}
            for k, st in stars.items():
                one = latest(row[0], st.metric)
                two = (
                    latest(row[0], st.shared_metric) if getattr(st, "shared_metric", None) else None
                )
                if one is not None or two is not None:
                    best = max(v for v in (one, two) if v is not None)
                    r["cards"][k] = {"one": one, "shared": two, "lit": best >= st.threshold}
            r["cause"] = latest(row[0], "tricks/logic_test/gain_cause")
            r["logic"] = latest(row[0], "tricks/logic_test/gain")
            return r

        for f in sorted((root / "data" / "runs" / "cards").glob("fitout-census-*.json")):
            if f.name.endswith("-readings.json"):
                continue
            key = f.stem[len("fitout-census-") :]
            try:
                plan = json.loads(f.read_text())
            except ValueError:
                continue
            fo = fitouts.get(key)
            preset = getattr(fo, "preset", None) or (
                fo.get("preset") if isinstance(fo, dict) else None
            )
            name = getattr(fo, "name", None) or (fo.get("name") if isinstance(fo, dict) else key)
            rows = []
            for variation, runs in plan.items():
                rows.append({"variation": variation, "stages": [reading(r) for r in runs]})
            rows.sort(key=lambda r: r["variation"] != "fitout")
            possible = sorted(
                {
                    k
                    for r in rows
                    for st in r["stages"]
                    for k, v in st.get("cards", {}).items()
                    if v["lit"]
                },
                key=CENSUS_CARDS.index,
            )
            out.append(
                {
                    "key": key,
                    "name": name,
                    "preset": preset,
                    "rows": rows,
                    "possible": possible,
                    "summary": (
                        root / "data" / "runs" / "cards" / f"fitout-census-{key}.md"
                    ).exists(),
                }
            )
    finally:
        con.close()
    out.sort(key=lambda c: c["key"].startswith("pilot"))
    return {
        "cards": [
            {"key": k, "name": st.name, "threshold": st.threshold} for k, st in stars.items()
        ],
        "censuses": out,
    }


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
    from thorp import expeditions as voyages
    from thorp import fleet
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
        "card_verdicts": _card_verdicts(),
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


_class_best_cache: dict[str, tuple[float, dict]] = {}


def api_class_best(preset: str) -> dict:
    """Cached five minutes: the leaderboard behind it takes seconds to build."""
    import time

    hit = _class_best_cache.get(preset)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    out = _class_best(preset)
    _class_best_cache[preset] = (time.time(), out)
    return out


def _class_best(preset: str) -> dict:
    """The class's current best version, the one its Scoring tab talks to (Justin, 2026-11-07: "ask the
    best version of 300k questions ... which one of the 300k is the current best version"): the
    leaderboard's pick (leaderboard.payload()["board"]: a class's best ship, ranked as the board ranks it),
    its voyages, and the finished voyages of the class to choose from instead."""
    from thorp import leaderboard

    best = next(
        (
            b["best"]
            for b in leaderboard.payload().get("board", [])
            if b.get("best") and b["best"].get("preset") == preset
        ),
        None,
    )
    voyages = _rows(
        "select name, ship, finished from runs where status='finished' and "
        "(json_extract(spec_json,'$.model.preset') = ? or json_extract(spec_json,'$.model.preset') like ?) "
        "order by finished desc",
        [preset, f"{preset}-%"],
    )
    if best is None:
        return {"best": None, "voyages": voyages}
    return {
        "best": {
            "name": best.get("name"),
            "version": best.get("version"),
            "ship": best.get("ship"),
            "ship_key": best.get("ship_key"),
            "run": best.get("run"),
            "runs": best.get("runs") or [],
            "sailings": best.get("sailings"),
            "chaining_lift": best.get("chaining_lift"),
            "why": "the leaderboard's best ship of this class: ranked by chaining lift over its sailings "
            "(a lift under +0.03 is noise, so while no 300k chains the pick among them is close to a coin)",
        },
        "voyages": voyages,
    }


def api_table_guesses(run: str, text: str, k: str | int = 10, mode: str = "1") -> dict:
    """A sailing's guesses after the text: its next whole word (mode "1") or two ("2"), or its next
    piece ("pieces"): thorp.table.word_guesses / guesses. Read-only, kept nowhere."""
    if not (text or "").strip():
        raise ValueError("type something first")
    if mode == "pieces":
        out = _table().guesses(run, text, int(k or 10))
        out["guesses"] = [{"word": g["piece"], "p": g["p"], "piece": True} for g in out["guesses"]]
        out["mode"] = "pieces"
        return out
    out = _table().word_guesses(run, text, int(k or 10), int(mode) if mode in ("1", "2", "3") else 1)
    out["mode"] = mode
    return out


# The Scoring tab's subjects (Justin, 2026-11-07 21:35: "break scoring into different subtabs. I have no way of
# knowing the counting ability of thorp ogden 300k or how good its maths is ... or its physics"): each a
# discovery track, the ladder of tests a class climbs one step at a time towards a historical discovery.
SUBJECTS = {
    "number": ("Number", "counting, order and series, towards Mendeleev's gaps (no arithmetic test yet: sums are not measured)",
               ["successor", "counting_test", "period_test", "gap_test", "between_test", "triads_test", "mendeleev_gaps"]),
    "physics": ("Physics", "heat, motion and work, towards the energy test",
                ["fire_test", "workshop_test", "smiths_test", "mill_test", "rumford_test", "energy_test"]),
    "life": ("Life", "kin, breeding and selection, towards the Origin test",
             ["kin_test", "pedigree_test", "breeders_test", "nature_test", "malthus_test", "origin_test"]),
    "return": ("Return", "what comes round comes round again, towards the eternal return",
               ["again_test", "refrain_test", "seasons_test", "pigeonhole_test", "lucretius_test", "recurrence_test"]),
    "logic": ("Logic", "chaining two facts on invented words, so no knowledge helps; geometry without the parallel postulate",
              ["logic_test", "geometry_test"]),
}  # fmt: skip


def _slug(preset: str) -> str:
    from thorp.models.registry import LADDER

    row = next((r for r in LADDER if r["preset"] == preset.split("-")[0]), None)
    return (row["name"].lower().removeprefix("the ").strip() if row else preset)


def _class_voyages(preset: str, limit: int = 12) -> list[dict]:
    """The class's voyages to read: Ogden's first (its fitout is the one that sails), then the latest others."""
    cls = preset.split("-")[0]
    rows = _rows(
        """select run_id, name, status, started, json_extract(spec_json,'$.model.preset') p,
                  json_extract(spec_json,'$.optim.batch_tokens') bt
           from runs where status in ('finished','running') order by started desc"""
    )
    seen: set[str] = set()
    mine = []
    for r in rows:  # the latest sailing of each voyage (a recalled one sails again under its name)
        if (r["p"] or "").split("-")[0] == cls and r["name"] not in seen:
            seen.add(r["name"])
            mine.append(r)
    ogden = [r for r in mine if r["name"].startswith("fu-ogden")]
    rest = [r for r in mine if not r["name"].startswith("fu-ogden")]
    return (ogden + rest)[:limit]


def api_class_subjects(preset: str) -> dict:
    """Each subject's ladder of tests, this class's own step marked, and every recent voyage of the class read
    against each test (the latest value of its metric, its score, and whether it passed its mark), with the
    class's own steps as series over tokens read."""
    from thorp import fleet

    slug = _slug(preset)
    voyages = _class_voyages(preset)
    con = _con()
    try:
        def last(rid, name):
            r = con.execute(
                "select value, step from metrics where run_id=? and name=? order by step desc limit 1", [rid, name]
            ).fetchone()
            return (r[0], r[1]) if r else (None, None)

        def series(rid, name, bt):
            return [
                [s * (bt or 32768), v]
                for s, v in con.execute(
                    "select step, value from metrics where run_id=? and name=? order by step", [rid, name]
                )
                if v is not None
            ]

        out = {}
        for key, (title, about, tests) in SUBJECTS.items():
            rows = []
            for k in tests:
                tr = fleet.TRICKS.get(k)
                if tr is None:
                    continue
                score_metric = tr.metric.rsplit("/", 1)[0] + "/score"
                readings = []
                for v in voyages:
                    val, step = last(v["run_id"], tr.metric)
                    sc, _ = last(v["run_id"], score_metric)
                    readings.append({
                        "voyage": v["name"], "status": v["status"], "value": val, "score": sc, "step": step,
                        "passed": None if val is None else val >= tr.threshold,
                        "series": series(v["run_id"], tr.metric, v["bt"]) if tr.goal_class == slug and val is not None else None,
                    })  # fmt: skip
                rows.append({
                    "key": k, "name": tr.name, "about": tr.about, "goal_class": tr.goal_class,
                    "mine": tr.goal_class == slug, "metric": tr.metric, "threshold": tr.threshold, "readings": readings,
                })  # fmt: skip
            out[key] = {"title": title, "about": about, "tests": rows}
    finally:
        con.close()
    return {"preset": preset, "class": slug, "voyages": [v["name"] for v in voyages], "subjects": out}


def api_class_shapes(preset: str) -> dict:
    """The shapes readings (the parts-of-speech taxonomy) for the class's voyages that carry them: each
    accuracy as a series over tokens read, and the latest share of probability on each kind of word."""
    from thorp.viable.s5_policy import taxonomy

    con = _con()
    try:
        out = []
        for v in _class_voyages(preset):
            rid, bt = v["run_id"], v["bt"] or 32768
            got = {}
            for m in ("shapes/upos_top1", "shapes/ogden_top1", "shapes/keyed_top1"):
                got[m] = [[s * bt, val] for s, val in con.execute(
                    "select step, value from metrics where run_id=? and name=? order by step", [rid, m]) if val is not None]  # fmt: skip
            if not got["shapes/upos_top1"]:
                continue
            last_step = got["shapes/upos_top1"][-1][0] // bt
            mass = {t: con.execute("select value from metrics where run_id=? and name=? and step=?",
                                   [rid, f"shapes/mass/{t}", last_step]).fetchone() for t in taxonomy.FINE}  # fmt: skip
            truth = {t: con.execute("select value from metrics where run_id=? and name=? and step=?",
                                    [rid, f"shapes/truth/{t}", last_step]).fetchone() for t in taxonomy.FINE}  # fmt: skip
            out.append({
                "voyage": v["name"], "status": v["status"], "series": got,
                "mass": {t: (x[0] if x else None) for t, x in mass.items()},
                "truth": {t: (x[0] if x else None) for t, x in truth.items()},
            })  # fmt: skip
    finally:
        con.close()
    return {"preset": preset, "fine": list(taxonomy.FINE), "about": taxonomy.ABOUT, "voyages": out}


def api_ask_questions(preset: str) -> dict:
    """The ask panel's questions for a class, drawn from the Ogden corpus (ships/lists/ogden-v0.1-questions.json):
    the keel's from one word back, the pilot's from two, the speller's (and every larger class's) from three:
    each a context the corpus continues with one word at least half the time (Justin, 21:35: "wouldn't these
    examples need to be simpler for the 300k")."""
    p = paths.resolve("lists/ogden-v0.1-questions.json")
    if not p.exists():
        return {"preset": preset, "questions": [], "words_back": None}
    d = json.loads(p.read_text())
    slug = _slug(preset)
    key = slug if slug in ("keel", "pilot") else "speller"
    s = d.get(key) or {}
    return {
        "preset": preset, "set": key, "words_back": s.get("words_back"),
        "questions": [
            {"text": q["context"].capitalize() if q["context"].split()[0] != "i" else q["context"], "hope": q["hope"],
             "about": f"{s.get('words_back')} word{'s' if s.get('words_back') != 1 else ''} back: the corpus continues it "
                      f"with '{q['hope']}' {round(100 * q['share'])}% of {q['count']:,} times"}
            for q in s.get("questions", [])
        ],
    }  # fmt: skip


_class_deck_cache: dict[str, tuple[float, dict]] = {}


def api_class_deck(preset: str) -> dict:
    """The whole deck at a class (Justin, 22:05: "show all the cards ... and stats about the cards based on the class
    model"): for each of the 16 cards, across the class's voyages (every fitout) and its Ogden ones apart: how many
    played it (the deck's rules: a Stage 1 above its Basic, a Face traded in), when (the median tokens read at its
    first play), in which layer, and the best its reading reached against its mark. Cached five minutes."""
    import statistics
    import time

    from thorp.viable.s4_intelligence import wager
    from thorp.viable.s5_policy import deck

    hit = _class_deck_cache.get(preset)
    if hit and time.time() - hit[0] < 300:  # five minutes: reading every voyage's falls takes seconds
        return hit[1]
    voyages = _class_voyages(preset, limit=200)
    con = _con()
    try:
        names = sorted({m for c in deck.CARDS if c.look for m in c.look[0]})
        peaks: dict[str, dict[str, float]] = {}
        for v in voyages:
            rows = con.execute(
                f"select name, max(value) from metrics where run_id=? and name in ({','.join('?' * len(names))}) group by name",
                [v["run_id"], *names],
            ).fetchall()
            peaks[v["run_id"]] = {n: x for n, x in rows if x is not None}
    finally:
        con.close()
    falls = {v["run_id"]: wager.falls(v["run_id"], v["bt"] or 32768) for v in voyages}
    read = [v for v in voyages if peaks[v["run_id"]]]
    out = []
    for c in deck.CARDS:
        played = [(v, falls[v["run_id"]][c.key]) for v in read if falls[v["run_id"]][c.key]["played"]]
        ogden_read = [v for v in read if v["name"].startswith("fu-ogden")]
        ogden_played = [v for v, _ in played if v["name"].startswith("fu-ogden")]
        best, best_v = None, None
        if c.look:
            for v in read:
                vals = [peaks[v["run_id"]].get(m) for m in c.look[0]]
                vals = [x for x in vals if x is not None]
                if vals and (best is None or max(vals) > best):
                    best, best_v = max(vals), v["name"]
        layers = [f["layer"] for _, f in played if f["layer"] is not None]
        toks = [f["tokens"] for _, f in played if f["tokens"] is not None]
        share = len(played) / len(read) if read else 0
        rarity = ("uncharted" if not deck.charted(c) else "unread" if not read else "unseen" if not played
                  else "legendary" if len(played) == 1 else "rare" if share < 0.05 else "uncommon" if share < 0.25 else "common")  # fmt: skip
        out.append({
            "key": c.key, "name": c.name, "constellation": c.constellation, "stage": c.stage, "cost": c.cost,
            "ability": c.ability_text, "on": list(c.on), "charted": deck.charted(c), "rarity": rarity,
            "scansion": c.scansion,
            "mark": c.look[1] if c.look else (c.ability[1] if c.ability else None),
            "voyages_read": len(read), "played": len(played), "ogden_read": len(ogden_read), "ogden_played": len(ogden_played),
            "first_tokens_median": statistics.median(toks) if toks else None,
            "usual_layer": max(set(layers), key=layers.count) if layers else None,
            "best": best, "best_voyage": best_v,
            "fragility": c.fragility,
        })  # fmt: skip
    res = {
        "preset": preset, "class": _slug(preset), "voyages": len(voyages), "read": len(read),
        "constellations": [{"key": k, "suit": s, "name": n, "about": a} for k, s, n, a in deck.CONSTELLATIONS],
        "scansions": [{"key": k, "name": n, "about": a} for k, n, a in deck.SCANSIONS],
        "cards": out,
    }
    _class_deck_cache[preset] = (time.time(), res)
    return res


WATCH_SERIES = {  # what the Watch panel draws, by tokens read
    "loss": "loss", "lr": "lr", "tokens_per_s": "tokens_per_s",
    "bpb": "eval/hole-cards-unseen/bpb_mean",
    "upos": "shapes/upos_top1", "ogden": "shapes/ogden_top1", "keyed": "shapes/keyed_top1",
    "previous_word": "stars/previous_word/shared_score", "nevermore": "nevermore/natural_max_score",
    "copy_gain": "nevermore/natural_copy_gain", "mover": "stars/mover/max_score",
    "comparator": "stars/comparator/shared_score", "words_back": "stars/offset_2/shared_score",
    "counter": "counter/probe_r2", "premise_marker": "stars/premise_marker/max_score",
    "one_hop": "tricks/logic_test/lift_one_hop", "cause": "tricks/logic_test/gain_cause",
}  # fmt: skip


def api_watch(preset: str) -> dict:
    """Watch a class train (Justin, 22:25: "so I can watch thorp 21m training to see what's happening ... show the
    stages"): the class's voyage at sea (else its latest home), where it is (step, tokens, pass, stage, speed, time
    left), its fitout's stage plan with the voyage's place on it, the cards it has drawn and when (the deck's
    rules), the series that matter by tokens read, and the log's last lines."""
    import time
    from datetime import datetime

    from thorp.viable.s4_intelligence import wager

    cls = preset.split("-")[0]
    rows = _rows(
        """select run_id, name, status, started, finished, spec_json from runs
           where json_extract(spec_json,'$.model.preset') like ? order by (status='running') desc, started desc limit 1""",
        [f"{cls}%"],
    )
    if not rows:
        return {"preset": preset, "voyage": None}
    v = rows[0]
    rid = v["run_id"]
    spec = json.loads(v["spec_json"] or "{}")
    f = paths.resolve("specs").rglob(f"{v['name']}.yaml")
    f = next(iter(f), None)
    if f is not None:
        import yaml

        spec = {**spec, **(yaml.safe_load(f.read_text()) or {})}
    bt = (spec.get("optim") or {}).get("batch_tokens") or 32768
    con = _con()
    try:
        def one(name):
            r = con.execute("select value from metrics where run_id=? and name=? order by step desc limit 1", [rid, name]).fetchone()
            return r[0] if r else None

        total_steps = one("plan/total_steps")
        tokens_total = one("plan/tokens_total")
        passes = one("plan/passes") or (spec.get("data") or {}).get("passes") or 1
        last = con.execute("select max(step) from metrics where run_id=? and name='loss'", [rid]).fetchone()[0] or 0
        seen = one("tokens_seen") or last * bt
        series = {}
        for key, name in WATCH_SERIES.items():
            pts = [[s * bt, val] for s, val in con.execute(
                "select step, value from metrics where run_id=? and name=? order by step", [rid, name]) if val is not None]  # fmt: skip
            if key in ("loss", "lr", "tokens_per_s") and len(pts) > 400:  # every step: thin to 400 points
                k = len(pts) // 400 + 1
                pts = pts[::k] + ([pts[-1]] if pts[-1] not in pts[::k] else [])
            series[key] = pts
        last_t = con.execute("select max(ts) from metrics where run_id=? and name='loss'", [rid]).fetchone()[0]
    finally:
        con.close()
    started = datetime.fromisoformat(v["started"]).timestamp() if v["started"] else None
    now = time.time()
    elapsed = (now if v["status"] == "running" else (datetime.fromisoformat(v["finished"]).timestamp() if v["finished"] else now)) - (started or now)
    rate = last / elapsed if elapsed > 0 and last else None  # steps a second, readings included
    eta = (total_steps - last) / rate if rate and total_steps and v["status"] == "running" else None
    # the stage plan: the voyage's own stages (pretraining) and, for a fitout, the post-training voyages seeded after it
    data = spec.get("data") or {}
    stages = []
    if data.get("stages"):
        for s in data["stages"]:
            stages.append({"name": s["name"], "phase": "pretraining", "passes": s.get("passes", 1), "library": s.get("recipe")})
    else:
        stages.append({"name": "pretraining", "phase": "pretraining", "passes": passes, "library": data.get("recipe")})
    chain = []
    if spec.get("fitout"):
        name = v["name"]
        for p2 in sorted(paths.resolve("specs/fitouts").glob("*.yaml")):
            import yaml

            s2 = yaml.safe_load(p2.read_text()) or {}
            if (s2.get("seeded_from") or {}).get("run") == name:
                chain.append({"name": s2["name"], "phase": "post-training", "passes": (s2.get("data") or {}).get("passes", 1),
                              "library": (s2.get("data") or {}).get("recipe"), "lr": (s2.get("optim") or {}).get("lr")})  # fmt: skip
    cards = wager.falls(rid, bt)
    drawn = sorted(
        [{"card": k, "tokens": x["tokens"], "step": x["step"], "layer": x["layer"]} for k, x in cards.items() if x["played"]],
        key=lambda x: x["tokens"],
    )
    log = []
    lp = paths.runs_dir() / f"{rid}.log"
    if lp.exists():
        for line in lp.read_text(errors="replace").splitlines()[-12:]:
            log.append(line if len(line) < 220 else line[:217] + "...")
    return {
        "preset": preset, "class": _slug(preset),
        "voyage": {"name": v["name"], "run_id": rid, "status": "at sea" if v["status"] == "running" else v["status"],
                   "started": v["started"], "finished": v["finished"], "fitout": spec.get("fitout"),
                   "model": spec.get("model"), "lr": (spec.get("optim") or {}).get("lr")},
        "where": {"step": last, "total_steps": total_steps, "tokens": seen, "tokens_total": tokens_total, "passes": passes,
                  "pass": min(int(passes), int(seen // (tokens_total / passes)) + 1) if tokens_total else None,
                  "elapsed_s": elapsed, "eta_s": eta, "last_reading_s_ago": (now - last_t) if last_t else None,
                  "tokens_per_s": (series["tokens_per_s"][-1][1] if series["tokens_per_s"] else None)},
        "stages": stages, "post": chain, "drawn": drawn, "series": series, "log": log,
    }  # fmt: skip


def api_wager(preset: str) -> dict:
    """The Bet tab (the Navigator's Wager, thorp/viable/s4_intelligence/wager.py): the 16-card deck, the levers,
    and every round on this class with both voyages' falls, the House's calls, the Navigator's bets, the
    outcomes and the score."""
    from thorp.viable.s4_intelligence import wager

    return wager.payload(preset)


def api_wager_deal(body: dict) -> dict:
    from thorp.viable.s4_intelligence import wager

    return wager.deal(str(body["preset"]), str(body["control"]), str(body["lever"]))


def api_wager_bet(body: dict) -> dict:
    from thorp.viable.s4_intelligence import wager

    layer = body.get("layer")
    return wager.place(
        str(body["round"]), str(body["card"]), body.get("move") or None, None if layer in (None, "") else int(layer)
    )


def api_wager_queue(body: dict) -> dict:
    """Queue a round's pull voyage: written, gated (S3) and put at the end of the standing queue. It changes
    what the Mac trains next, so the page asks before it sends."""
    from thorp.viable.s4_intelligence import wager

    return wager.queue(str(body["round"]))


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
        self._send(code, json.dumps(_finite(obj), default=str).encode(), "application/json")

    def do_POST(self):  # noqa: N802
        """The writes: the table (POST /api/table/reply {run, question, history, ...}) and the fitout
        builder (POST /api/fitouts/save {fitout}, POST /api/fitouts/queue {key, preset, seeds, where},
        the latter changing what the Mac trains next, so the page asks before it sends)."""
        u = urlparse(self.path)
        posts = {
            "/api/table/reply": api_table_reply,
            "/api/fitouts/save": api_fitout_save,
            "/api/fitouts/queue": api_fitout_queue,
            "/api/wager/deal": api_wager_deal,
            "/api/wager/bet": api_wager_bet,
            "/api/wager/queue": api_wager_queue,
        }
        if u.path not in posts:
            return self._send(404, b"not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
            return self._json(200, posts[u.path](body))
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
                "/api/observation": lambda: api_observation(q.get("expedition", "")),
                "/api/expeditions": lambda: api_voyages(),
                "/api/expedition": lambda: api_voyage_series(q["key"]),
                "/api/expeditions/overview": api_expeditions_overview,
                "/api/queue": api_queue,
                "/api/library": api_shelves,
                "/api/library_books": lambda: api_shelf_books(q["path"]),
                "/api/library_trigrams": lambda: api_shelf_trigrams(q["path"]),
                "/api/voyages/where": lambda: api_voyages_where(q.get("runs", "")),
                "/api/governance": api_governance,
                "/api/acquisition": api_acquisition,
                "/api/acquisition/audit": api_acquisition_audit,
                "/api/series": lambda: api_series(q.get("runs", ""), q.get("metrics", "")),
                "/api/fitout_builder": api_fitout_builder,
                "/api/shelf_trigrams": lambda: api_shelf_trigrams(q["path"]),
                "/api/knockout": lambda: api_knockout(q.get("model", "")),
                "/api/class_score": lambda: api_class_score(q["preset"]),
                "/api/class_cards": lambda: api_class_cards(q["preset"]),
                "/api/class_best": lambda: api_class_best(q["preset"]),
                "/api/wager": lambda: api_wager(q["preset"]),
                "/api/watch": lambda: api_watch(q["preset"]),
                "/api/class_deck": lambda: api_class_deck(q["preset"]),
                "/api/ask_questions": lambda: api_ask_questions(q["preset"]),
                "/api/class_subjects": lambda: api_class_subjects(q["preset"]),
                "/api/class_shapes": lambda: api_class_shapes(q["preset"]),
                "/api/table/guesses": lambda: api_table_guesses(
                    q["run"], q.get("text", ""), q.get("k", 10), q.get("mode", "1")
                ),
                "/api/fitouts": lambda: api_fitouts(q.get("preset", "")),
                "/api/census": api_census,
                "/api/competitor": lambda: api_competitor(q["model"]),
                "/api/thorp": lambda: api_thorp(q["ship"]),
                "/api/lab": lambda: api_lab(q["lab"]),
                "/api/bridge": api_bridge,
                "/api/leaderboard/internal": api_leaderboard_internal,
                "/api/smoking_qwen": api_smoking_qwen,
                "/api/bet": api_bet,
                "/api/climb": lambda: api_climb(q.get("runs", "")),
                "/api/shelf": lambda: api_shelf(q["run"]),
                "/api/book": lambda: api_book(q["id"], q.get("offset", 0), q.get("length", 20000)),
                "/api/experiment": lambda: api_experiment(q.get("prefix", "content-")),
            }
            # /api/voyage/<run_id>/library: the library aboard one voyage
            m = re.fullmatch(r"/api/voyage/([0-9a-f]{6,64})/library", u.path)
            if m:
                routes[u.path] = lambda: api_voyage_library(m.group(1))
            if u.path not in routes:
                return self._send(404, b"not found", "text/plain")
            body = json.dumps(_finite(routes[u.path]()), default=str).encode()
            return self._send(200, body, "application/json")
        except TableNotBuilt as e:
            return self._send(503, json.dumps({"error": str(e)}).encode(), "application/json")
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": repr(e)}).encode(), "application/json")


def serve(port: int = 8787) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:  # start warming the slow payloads now, so the first visit finds them ready
        from thorp import library as shelves

        _warm("shelves", shelves.payload)
        if hasattr(shelves, "fitouts"):
            _warm("fitouts", shelves.fitouts)
    except Exception:  # noqa: BLE001
        pass
    print(f"thorp dash on http://localhost:{port}  (ledger {paths.ledger_path()})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
