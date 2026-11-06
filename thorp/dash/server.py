"""The dashboard: the Astro build in ./static (source in ./web) plus JSON read straight from the
ledger. Standard library only; `pnpm --dir thorp/dash/web build` makes the page.

Endpoints: /api/runs, /api/metrics?run=, /api/evals?run=, /api/run?run= (headline numbers,
latest samples, probes, recipe composition, traits and tokeniser stats, which the panels need),
/api/ladder (each rung's job, its scores, the queue)
and /api/compare (every run's hole-card score against tokens seen: the experiment's observation).
"""

from __future__ import annotations

import json
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

    for kind in ("samples", "top10", "recipe", "eval_sets", "probes", "curiosity"):
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
    which a line crosses its threshold: first light."""
    from thorp import fleet, voyages

    v = fleet.VOYAGES[key]
    runs = voyages.runs_of(v)
    con = _con()
    try:
        out = []
        for r in runs:
            series = {}
            for sk, star in fleet.STARS.items():
                pts = list(
                    con.execute(
                        "select step, value from metrics where run_id=? and name=? order by step, rowid",
                        [r["run_id"], star.metric],
                    )
                )
                series[sk] = {"step": [p[0] for p in pts], "value": [p[1] for p in pts]}
                # lit shared: the best layer's two strongest heads together (voyages.py works it
                # out from the 'stars' artifacts where the metric was not recorded yet)
                if getattr(star, "shared_metric", ""):
                    sh = voyages._shared_series(r["run_id"], star)
                    series[sk]["shared_step"] = [p["step"] for p in sh]
                    series[sk]["shared_value"] = [p["value"] for p in sh]
            out.append(
                {"run_id": r["run_id"], "name": r["name"], "ship": r["ship"], "series": series}
            )
    finally:
        con.close()
    return {
        "runs": out,
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
    return {
        "stars": stars,
        "traits": [
            {"key": t, "ships": v}
            for t, v in sorted(traits.items(), key=lambda kv: (kv[0].startswith("family/"), kv[0]))
        ],
        "trait_found": probes.AUC_FOUND,
        "trait_margin": probes.EMERGE_MARGIN,
        "core_traits": list(probes.TRAIT_COLUMNS),
    }


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
                "/api/shelf": lambda: api_shelf(q["run"]),
                "/api/book": lambda: api_book(q["id"], q.get("offset", 0), q.get("length", 20000)),
                "/api/experiment": lambda: api_experiment(q.get("prefix", "content-")),
            }
            if u.path not in routes:
                return self._send(404, b"not found", "text/plain")
            body = json.dumps(routes[u.path](), default=str).encode()
            return self._send(200, body, "application/json")
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": repr(e)}).encode(), "application/json")


def serve(port: int = 8787) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"thorp dash on http://localhost:{port}  (ledger {paths.ledger_path()})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
