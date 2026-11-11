"""The dashboard: the Astro build in ./static (source in ./web) plus JSON read straight from the
ledger. Standard library only; `pnpm --dir thorp/dash/web build` makes the page.

Endpoints: /api/runs, /api/metrics?run=, /api/evals?run=, /api/run?run= (headline numbers,
latest samples, probes, recipe composition, traits and tokeniser stats, which the panels need),
/api/ladder (each rung's job, its scores, the queue)
and /api/compare (every run's hole-card score against tokens seen: the experiment's observation).
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import socket
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thorp import chinchilla, paths, store
from thorp.evaluators.probes import load_traits
from thorp.ledger import connect
from thorp.store import StoreDown
from thorp.viable.s4_intelligence import readings

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
NOT_BUILT = b"""<!doctype html><meta charset="utf-8"><title>Nothing up my sleeve</title>
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


def _ledger_pg() -> bool:
    """Whether the core ledger readers answer from Postgres (THORP_LEDGER_PG). During the cut-over this
    flips on after the backfill; until then the readers stay on SQLite. The JSON-extracting endpoints
    still read SQLite until they are migrated in turn."""
    from thorp.ledger import _use_pg

    return _use_pg()


def _rows(sql: str, params=()) -> list[dict]:
    if _ledger_pg():
        from thorp.ledger import reader

        return reader().query(sql, params)
    con = _con()
    try:
        return [dict(r) for r in con.execute(sql, list(params))]
    finally:
        con.close()


def _metric(run: str, name: str, which: str = "last"):
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metric_at(run, name, which)
    order = "desc" if which == "last" else "asc"
    r = _rows(
        f"select step, value from metrics where run_id=? and name=?"
        f" order by step {order}, rowid {order} limit 1",
        [run, name],
    )
    return r[0]["value"] if r else None


def api_runs() -> list[dict]:
    if _ledger_pg():  # every run's latest hole-card bpb in one query (11 November, audit item 7)
        from thorp.dash import batched

        return batched.runs()
    else:
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


def api_metrics(run: str, names: str = "", points: str = "") -> dict:
    """{name: [[steps], [values]]} for a run. Optional bounds (11 November, audit item 7: one run's answer was
    16 MB): `names` a comma list (an entry ending in `*` is a prefix), `points` a cap per series that keeps each
    series' first, last, lowest and highest point. Neither given: every series in full, as before."""
    from thorp.dash import batched

    if _ledger_pg():
        return batched.metrics(run, names, points)
    if names or points:
        full = _api_metrics_sqlite(run)
        keep = batched.wanted(names, list(full)) if names else list(full)
        cap = batched.cap_of(points)
        return {k: batched.downsample(full[k][0], full[k][1], cap) if cap > 0 else full[k] for k in keep}
    return _api_metrics_sqlite(run)


def _api_metrics_sqlite(run: str) -> dict:
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
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.evals(run)
    return _rows("select * from evals where run_id=? order by step, book_id", [run])


def _artifact(run: str, kind: str, latest=True):
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.artifact(run, kind, latest)
    r = _rows(
        f"select step, path, sha1, text from artifacts where run_id=? and kind=?"
        f" order by step {'desc' if latest else 'asc'}, rowid desc limit 1",
        [run, kind],
    )
    return r[0] if r else None


def _run_spec_json(run_id: str) -> dict:
    """A run's spec_json as a dict, read from Postgres (THORP_LEDGER_PG) or SQLite."""
    if _ledger_pg():
        from thorp import ledger_store

        r = ledger_store.get_run(run_id)
        return json.loads(r["spec_json"] or "{}") if r and r.get("spec_json") else {}
    rows = _rows("select spec_json from runs where run_id=?", [run_id])
    return json.loads(rows[0]["spec_json"] or "{}") if rows else {}


def _metric_rows(run_id: str, name: str) -> list[dict]:
    """[{name, step, value}] for one named metric, ordered by step (the later row at one step stands)."""
    if _ledger_pg():
        from thorp import ledger_store

        s = ledger_store.metric_series(run_id, name)
        return [{"name": name, "step": st, "value": v} for st, v in zip(s[0], s[1], strict=True)]
    return _rows("select name, step, value from metrics where run_id=? and name=? order by step", [run_id, name])


def _metric_name_rows(run_id: str, prefix: str) -> list[dict]:
    """[{name, step, value}] for metrics whose name starts with `prefix`, ordered by step (then id)."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metrics_matching(run_id, prefix)
    return _rows("select name, step, value from metrics where run_id=? and name like ? order by step, rowid", [run_id, prefix + "%"])


def _artifact_rows(run_id: str, kind: str) -> list[dict]:
    """Every artifact of a kind, ordered by step (then id), as [{step, path, sha1, text}]."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.artifacts_of_kind(run_id, kind)
    return _rows("select step, path, sha1, text from artifacts where run_id=? and kind=? order by step, rowid", [run_id, kind])


def _metric_series_gated(run_id: str, name: str) -> list[list]:
    """[steps, values] for one named metric, the later row at one step standing (either store)."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metric_series(run_id, name)
    rows = _rows("select step, value from metrics where run_id=? and name=? order by step, rowid", [run_id, name])
    steps, values = [], []
    for r in rows:
        if steps and steps[-1] == r["step"]:
            values[-1] = r["value"]
        else:
            steps.append(r["step"])
            values.append(r["value"])
    return [steps, values]


def _runs_rows() -> list[dict]:
    """Every run, oldest first (as `select * from runs order by started`), from either store."""
    if _ledger_pg():
        from thorp import ledger_store

        return list(reversed(ledger_store.all_runs()))
    return _rows("select * from runs order by started")


def _metric_at_step(run_id: str, name: str, step: int) -> float | None:
    """The value of one metric at one step (the later row at that step stands), from either store."""
    if _ledger_pg():
        from thorp import ledger_store

        s, v = ledger_store.metric_series(run_id, name)
        for i in range(len(s) - 1, -1, -1):
            if s[i] == step:
                return v[i]
        return None
    row = _rows(
        "select value from metrics where run_id=? and name=? and step=? order by rowid desc limit 1",
        [run_id, name, step],
    )
    return row[0]["value"] if row else None


def _metric_peaks(run_id: str, names: list[str]) -> dict[str, float]:
    """{name: max value} over all rows for the given names, from either store."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metrics_max(run_id, names)
    if not names:
        return {}
    rows = _rows(
        f"select name, max(value) as m from metrics where run_id=? and name in ({','.join('?' * len(names))}) group by name",
        [run_id, *names],
    )
    return {r["name"]: r["m"] for r in rows if r["m"] is not None}


def _metric_named_rows(run_id: str, names: set[str]) -> list[dict]:
    """[{name, step, value}] for the exact names, value not null, ordered by step then id."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metrics_named(run_id, names)
    if not names:
        return []
    return _rows(
        f"select name, step, value from metrics where run_id=? and name in ({','.join('?' * len(names))})"
        " and value is not null order by step, rowid",
        [run_id, *names],
    )


def _latest_evals(run_id: str, eval_set: str) -> list[dict]:
    """A run's {book_id, bpb} at its latest step for one set, from either store."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.latest_evals(run_id, eval_set)
    return _rows(
        'select book_id, bpb from evals where run_id=? and "set"=?'
        ' and step=(select max(step) from evals x where x.run_id=? and x."set"=?)',
        [run_id, eval_set, run_id, eval_set],
    )


def _metric_max_ts(run_id: str, name: str) -> float | None:
    """The latest write timestamp of one metric, from either store."""
    if _ledger_pg():
        from thorp import ledger_store

        return ledger_store.metric_max_ts(run_id, name)
    row = _rows("select max(ts) as m from metrics where run_id=? and name=?", [run_id, name])
    return row[0]["m"] if row else None


def _run_row(key: str) -> dict | None:
    """A run's row, given an id (exact) or a name (the latest with that name)."""
    if _ledger_pg():
        from thorp import ledger_store

        r = ledger_store.get_run(key)
        return r if r else _run_row_by_name(key)
    rows = _rows("select * from runs where run_id=? limit 1", [key])
    return rows[0] if rows else _run_row_by_name(key)


def _run_id(key: str) -> str | None:
    """A run's id, given an id or a name."""
    row = _run_row(key)
    return row["run_id"] if row else None


def _run_row_by_name(name: str) -> dict | None:
    """The latest run with this name (the SQLite `select * from runs where name=? order by started desc limit 1`)."""
    if _ledger_pg():  # one query, not every run read (11 November, audit item 7)
        from thorp import ledger_store

        return ledger_store.get_run_by_name(name)
    for r in reversed(_runs_rows()):
        if r.get("name") == name:
            return r
    return None


def api_run(run: str) -> dict:
    if _ledger_pg():
        from thorp import ledger_store

        meta = ledger_store.get_run(run)
    else:
        rows = _rows("select * from runs where run_id=?", [run])
        meta = rows[0] if rows else None
    if not meta:
        return {}
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
    tps_vals = _metric_series_gated(run, "tokens_per_s")[1][-50:]
    tps_avg = sum(tps_vals) / len(tps_vals) if tps_vals else None
    if tps_avg:
        out["tokens_per_s"] = tps_avg
        if planned and meta["status"] == "running":
            out["eta_minutes"] = (planned - seen) / tps_avg / 60
    if n and planned:
        out["chinchilla"] = {
            "D_planned": planned,
            "L_planned": chinchilla.loss(n, planned),
            "D_unique": unique,
            "L_unique": chinchilla.loss(n, unique) if unique else None,
        }
    if first:
        s, v = _metric_series_gated(run, f"eval/{first}/bpb_mean")
        out["hole_bpb_latest"] = {"step": s[-1], "value": v[-1]} if s else None
        out["hole_bpb_previous"] = {"step": s[-2], "value": v[-2]} if len(s) > 1 else None
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
    for a in _artifact_rows(run, "probes"):
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
    if _ledger_pg():  # six queries for every run, not seven a run (11 November, audit item 7)
        from thorp.dash import batched

        return batched.compare()
    out = []
    for r in api_runs():
        rid = r["run_id"]
        total = _metric(rid, "plan/tokens_total")
        steps = _metric(rid, "plan/total_steps")
        per_step = total / steps if total and steps else None
        spec = _run_spec_json(rid)
        sets = [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]
        if not sets or not per_step:
            continue
        series = _metric_rows(rid, f"eval/{sets[0]}/bpb_mean")
        en = _metric_rows(rid, f"eval/{sets[0]}/bpb_mean_en")
        # every held-out set this run has been scored on (its own, and any re-score), so the page
        # can read the truth gap and compare runs set by set
        by_set: dict[str, dict] = {}
        for x in _metric_name_rows(rid, "eval/"):
            if not x["name"].endswith("/bpb_mean"):
                continue
            d = by_set.setdefault(x["name"].split("/")[1], {"steps": [], "tokens": [], "bpb": []})
            if d["steps"] and d["steps"][-1] == x["step"]:
                d["bpb"][-1] = x["value"]
                continue
            d["steps"].append(x["step"])
            d["tokens"].append(x["step"] * per_step)
            d["bpb"].append(x["value"])
        # the push per layer and the learning rate, so the page computes each run's kinks itself
        push: dict[str, list] = {}
        rows = _metric_name_rows(rid, "grad_norm/layer_") + _metric_rows(rid, "lr")
        for x in rows:
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
        spec = _run_spec_json(rid)
        move: dict[str, list] = {}
        for x in _metric_name_rows(rid, "update_ratio/layer_"):
            if x["name"].count("/") > 1:
                continue
            m = move.setdefault(x["name"], [[], []])
            m[0].append(x["step"])
            m[1].append(x["value"])
        traits: dict[int, dict] = {}
        for a in _artifact_rows(rid, "probes"):
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
        ladder = _metric_rows(rid, "curiosity/highest")
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
    """Every run's latest eval/* and laws/* values: the last write for each name wins, as in _metric."""
    if _ledger_pg():  # from s1.metric_latest, every run in one query (11 November, audit item 7)
        from thorp.dash import batched

        return batched.last_scores(run_ids)
    out: dict[str, dict[str, float]] = {}
    for run in run_ids:
        got: dict[str, float] = {}
        for x in _metric_name_rows(run, "eval/") + _metric_name_rows(run, "laws/"):
            got[x["name"]] = x["value"]
        out[run] = got
    return out


def _cause_by_run(run_ids: list[str]) -> dict[str, float]:
    """Each run's latest cause gain in one query: the voyage grid's second reading (bpb is the first)."""
    if not run_ids:
        return {}
    from thorp.ledger import reader

    marks = ",".join("?" * len(run_ids))
    rows = reader().query(
        "select run_id, step, value from metrics"
        f" where name='tricks/logic_test/gain_cause' and run_id in ({marks})",
        list(run_ids),
    )
    best: dict[str, tuple[int, float]] = {}
    for x in rows:
        if x["run_id"] not in best or x["step"] > best[x["run_id"]][0]:
            best[x["run_id"]] = (x["step"], x["value"])
    return {k: v[1] for k, v in best.items()}



def _fitting_out() -> list[dict]:
    """Ships registered in `s1.ships` that have not sailed a voyage yet, in service: moored in their harbour while
    they are fitted out (the four positions at the 1m, before their first voyage: only that expedition's ships for now)."""
    from sqlalchemy import text

    from thorp.viable.s3_control import fitout_store

    try:
        with fitout_store.engine().connect() as c:
            rows = c.execute(text(
                "select s.key, s.name, s.size, s.preset, s.subtitle, s.expedition from s1.ships s"
                " where not s.archived and s.status = 'in service' and s.expedition = 'four_positions'"
                " and not exists (select 1 from s1.voyages v where v.ship_key = s.key) order by s.created_at, s.key")).mappings()
            return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001  the store is down: the harbours show their sizes without the ships fitting out
        return []


_LADDER_CACHE = {"at": 0.0, "value": None, "lock": None}


def _api_ladder() -> dict:
    """The ladder (each rung's job and how it is judged), every run's rung scores (the bits-per-byte
    split on its first held-out set and the laws, model beside reference), and tonight's queue."""
    from thorp.dash import waters as harbours
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
        rungs[-1]["harbour"] = harbours.harbour_for(rungs[-1]["total"])
    runs = []
    rows = _runs_rows()
    ships, ship_of = _ships(rows)
    last = _last_scores([r["run_id"] for r in rows])
    causes = _cause_by_run([r["run_id"] for r in rows])
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
            "sop": spec.get("sop"),
            "experiment": spec.get("experiment"),
            "recipe": spec.get("data", {}).get("recipe"),
            "passes": spec.get("data", {}).get("passes"),
            "ft_en": m.get("eval/hole-cards-unseen/bpb_mean_en"),
            # the voyage grid's second reading: the logic deck's cause gain, the one Qwen 4B shows
            "cause": causes.get(r["run_id"]),
            "logic": m.get("tricks/logic_test/gain"),
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
    for _, x in readings.glob("*"):
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
    sizes_in = {h["key"]: [r["preset"] for r in rungs if r["harbour"] == h["key"]] for h in harbours.harbours()}
    fitting = _fitting_out()
    from thorp import foreign

    return {
        "rungs": rungs, "runs": runs, "queue": queue, "external": external,
        "harbours": [{**h, "sizes": sizes_in[h["key"]], "fitting_out": [x for x in fitting if x["size"] in sizes_in[h["key"]]]}
                     for h in harbours.harbours()],
        "foreign": foreign.models(),
    }  # fmt: skip


def api_library_summary(path: str) -> dict:
    """A shelf at a glance for the ship builder's Library tab: language, kinds, size, date range."""
    from thorp import library

    return library.summary(path)


def _model_params(preset: str) -> int:
    """A preset's parameter count, built once and kept: the shape table and the embedding tab both need it."""
    cache = globals().setdefault("_PARAMS_CACHE", {})
    if preset not in cache:
        from mlx.utils import tree_flatten

        from thorp.models.gpt_mlx import GPT
        from thorp.models.registry import config

        try:
            cache[preset] = sum(int(x.size) for _, x in tree_flatten(GPT(config(preset, 2048, 1024)).parameters()))
        except Exception:
            cache[preset] = 0
    return cache[preset]


def _queue_lines() -> list[str]:
    """The queue the page shows: `s2.queue_lines`, always. The page is a view of the store, never of the
    `specs/queue.txt` export: a store that cannot be read is an error, not a stale photograph (10 November,
    Justin: "the page should only ever show postgres"). The file is written from the store as an export,
    never read here."""
    from thorp.viable.s2_coordination import queue_store

    return queue_store.pending_texts()


def api_expedition_plan(key: str = "kipling") -> dict:
    """An expedition's launches, in queue order, with the parameters that make its arms differ.

    Reads the `fitouts/...` lines still in specs/queue.txt, so it shows what is *going to sail* rather than
    what has sailed: the two 1m arms of Kipling's GQA test come out side by side, identical everywhere but
    the attention (9 November, Justin: "a tab for plan ... showcase the two 1ms and compare their different
    parameters")."""
    import yaml

    from thorp import fleet, paths
    from thorp.models import registry

    root = paths.resolve("specs")
    rows = []
    for line in _queue_lines():
        line = line.strip()
        if not line.startswith("fitouts/"):
            continue
        name = line[len("fitouts/"):]
        f = root / "fitouts" / f"{name}.yaml"
        if not f.exists():
            continue
        spec = yaml.safe_load(f.read_text()) or {}
        m, o = spec.get("model") or {}, spec.get("optim") or {}
        preset = m.get("preset")
        kv = int(m.get("kv_heads") or 0)
        try:
            model = registry.build("gpt", preset, int((spec.get("tokeniser") or {}).get("vocab") or 2048),
                                   int(m.get("context") or 1024), m.get("positions", "learned"),
                                   kv_heads=kv)
            counts = model.parameter_counts()
        except Exception:
            counts = {}
        heads = [h.get("card") for h in (o.get("scaffold") or {}).get("heads") or []]
        rows.append({
            "line": line, "name": name, "ship": spec.get("ship"), "preset": preset,
            "kv_heads": kv, "heads": (registry.PRESETS.get(preset) or {}).get("heads"),
            "layers": (registry.PRESETS.get(preset) or {}).get("layers"),
            "positions": m.get("positions"), "context": m.get("context"),
            "params": counts, "lr": o.get("lr"), "warmup": o.get("warmup_steps"),
            "batch_tokens": o.get("batch_tokens"), "passes": (spec.get("data") or {}).get("passes"),
            "books": (spec.get("data") or {}).get("recipe"), "pinned": heads,
            "tokeniser": {
                "kind": (spec.get("tokeniser") or {}).get("kind"),
                "vocab": (spec.get("tokeniser") or {}).get("vocab"),
                "train_on": (spec.get("tokeniser") or {}).get("train_on"),
                "symbols": (spec.get("tokeniser") or {}).get("symbols") or [],
            },
            "expedition": fleet.expedition_of_label(spec.get("name"), spec.get("ship")),
        })
    # only this expedition's launches: every expedition's Plan tab was showing the whole queue (found 11
    # November, when Arc de Triomphe's tab listed Kipling's nine lines)
    return {"key": key, "queue": [r for r in rows if r["expedition"] == key]}


def api_compute() -> dict:
    """The yard's compute resources (thorp.compute): specs, the last measured test, caps and status. The page
    reads this; the POST adds, tests or caps one."""
    from thorp import compute

    return {"resources": compute.resources()}


def api_compute_set(body: dict) -> dict:
    from thorp import compute

    action = str(body.get("action", "test"))
    if action == "add":
        compute.add(str(body.get("kind", "mac")), str(body.get("name", "This Mac")),
                    body.get("specs"), body.get("caps"))
    elif action == "test":
        compute.test(str(body["resource_id"]), str(body.get("preset", "300k")))
    elif action == "caps":
        compute.set_caps(str(body["resource_id"]), body.get("caps") or {})
    else:
        raise ValueError(f"unknown action {action}")
    return api_compute()


def api_vast() -> dict:
    """The Vast.ai lane's setup, from the store: whether a key is held (never the key itself), its last four
    characters, and the lane's seats. `set_vast_key` writes `s5.provider_credentials`; the charter reads it."""
    from thorp import providers

    k = providers.vast_key()
    return {"has_key": bool(k), "key_hint": (k[:4] + "…" + k[-4:]) if len(k) > 8 else "",
            "seats": providers.vast_seats()}


def api_vast_set(body: dict) -> dict:
    from thorp import providers

    if body.get("key"):
        providers.set_vast_key(str(body["key"]))
    if body.get("seats") is not None:
        providers.set_vast_seats(int(body["seats"]))
    return api_vast()


def api_constraints() -> dict:
    """The yard's live constraints, from Postgres: the Mac lane's seats (`s2.lanes`, the slipways), which
    hulls may share the GPU (`lanes.TWO_AT_ONCE`), the queue's depth and what is at sea. The constraints
    page reads this and the editor below writes it; neither reads a file or an environment variable."""
    from thorp.viable.s2_coordination import lanes as lane_mod, queue_store

    live = api_lanes()
    return {
        "mac_seats": live.get("mac_seats", 1),
        "vast_seats": live.get("vast_seats", 1),
        "helm_seats": live.get("helm_seats", 0),
        "at_sea": [h.get("name") for h in live.get("seats", [])],
        "two_at_once": sorted(lane_mod.TWO_AT_ONCE),
        "queue": len(queue_store.pending_texts()),
    }


def api_constraints_set(body: dict) -> dict:
    """Set the Mac lane's seats (1-8). Written to `s2.lanes`, which the coordinator re-reads each loop, so
    the change takes effect without a restart; any 300k line can then take the second seat, and only 300k
    (lanes.TWO_AT_ONCE)."""
    from thorp import store
    from thorp.viable.records import Lane

    seats = int(body.get("mac_seats", 1))
    if not 1 <= seats <= 8:
        raise ValueError("mac_seats must be 1-8")
    with store.session() as s:
        r = s.get(Lane, "mac")
        if r is None:
            s.add(Lane(lane="mac", seats=seats))
        else:
            r.seats = seats
    return api_constraints()


_ATLAS_CACHE: dict = {"at": 0.0, "value": None}


def api_lanes() -> dict:
    """The lanes' concurrency, read from Postgres: s2.lanes says how many seats each lane runs and what is
    out; s2.helm says which seats are at sea (9 November, Justin: "all this should be stored in postgres")."""
    from thorp import paths, store, vsm
    from thorp.viable.records import Lane

    with store.session() as s:
        lanes = [
            {"lane": r.lane, "line": r.line, "pid": r.pid, "since": r.since, "seats": r.seats or 1}
            for r in s.query(Lane)
        ]
    by = {r["lane"]: r for r in lanes}
    seats = vsm.helms()
    return {
        "helm_seats": len(seats),
        "mac_seats": (by.get("mac") or {}).get("seats", 1),
        "vast_seats": (by.get("vast") or {}).get("seats", 1),
        "seats": seats,
        "lanes": lanes,
        "queue": _queue_lines(),
    }


def api_lanes_slots(mac: str = "1") -> dict:
    """Set the Mac lane's seats in s2.lanes, so the next coordinator start and the dashboard agree."""
    from thorp import store
    from thorp.viable.records import Lane

    n = max(1, min(8, int(mac)))
    with store.session() as s:
        r = s.get(Lane, "mac")
        if r is None:
            r = Lane(lane="mac", line=None, pid=None, since=None, seats=n)
        r.seats = n
        s.merge(r)
    return {"mac": n}


def api_at_sea(expedition: str = "kipling") -> dict:
    """The voyages at sea (or just docked) for one expedition, side by side: each arm's step, loss and the
    readings it has so far, with its difference from the control arm (9 November, Justin: "the at-sea page
    needs to consolidate the aggregate findings of the 300k as they’re running")."""
    from thorp import fleet

    runs = _runs_rows()
    # a killed run still says running in the ledger; the seats are the authority (as in api_queue)
    from thorp import vsm

    try:
        live = {h.get("name") for h in vsm.helms(8)}
    except Exception:  # noqa: BLE001
        live = set()
    import time

    rows = []
    fresh_after = time.time() - 900  # a voyage that has written nothing for 15 minutes is not "at sea"
    for r in runs:
        spec = json.loads(r.get("spec_json") or "{}")
        if fleet.expedition_of_label(r.get("name"), r.get("ship")) != expedition:
            continue
        # the arms of the voyage now: running, or docked in the last six hours
        if r.get("status") == "running":
            # a live helm seat is at sea even when its last reading is old: four voyages on this Mac can
            # leave one waiting a long time between readings, and a stalled voyage still has its seat
            # (10 November: the control's fourth card vanished from the at-sea page at 15 minutes).
            # Only a running row with no seat and no fresh reading is a voyage that died.
            if r.get("name") not in live:
                last = _latest_ts(r["run_id"])
                if last is None or last < fresh_after:
                    continue
        if r.get("status") != "running" and not (
            r.get("status") == "finished" and str(r.get("started") or "") >= "2026-11-09T21:00"
        ):
            continue
        rid = r["run_id"]
        loss = _latest(rid, "loss")
        step = _latest_step(rid)
        bpb = _latest_bpb(rid)
        chain = _chaining(rid)
        rows.append({
            "name": r["name"], "run_id": rid, "status": r["status"], "preset": (spec.get("model") or {}).get("preset"),
            "kv_heads": int((spec.get("model") or {}).get("kv_heads") or 0),
            "pins": len(((spec.get("optim") or {}).get("scaffold") or {}).get("heads") or []),
            "clean": (spec.get("data") or {}).get("clean"),
            # the embedding makeup: what the pieces are, and which control tokens are declared
            "tokeniser": {
                "kind": (spec.get("tokeniser") or {}).get("kind"),
                "vocab": (spec.get("tokeniser") or {}).get("vocab"),
                "symbols": (spec.get("tokeniser") or {}).get("symbols") or [],
                "train_on": (spec.get("tokeniser") or {}).get("train_on"),
            },
            "recipe": (spec.get("data") or {}).get("recipe"),
            "passes": (spec.get("data") or {}).get("passes"),
            "opt_in": (spec.get("data") or {}).get("opt_in"),
            # the cards: each pinned card's mark, its peak and its latest reading (retention after the fade),
            # and the shapes the language is judged on
            "cards": [
                {
                    "card": h.get("card"), "layer": h.get("layer"), "head": h.get("head"),
                    "stage": (_deck_classes().get(h.get("card")) or {}).get("stage"),
                    "suit": (_deck_classes().get(h.get("card")) or {}).get("suit"),
                    "mark": _card_marks().get(h.get("card")),
                    "peak": _peak_final(rid, _card_metric(h.get("card")))[0],
                    "now": _peak_final(rid, _card_metric(h.get("card")))[1],
                    "layer_found": _latest(rid, _card_metric(h.get("card")).replace("max_score", "best_layer")),
                    "head_found": _latest(rid, _card_metric(h.get("card")).replace("max_score", "best_head")),
                }
                for h in (((spec.get("optim") or {}).get("scaffold") or {}).get("heads") or [])
            ],
            "cards_summary": _cards_summary(spec, rid),
            "shapes": {"upos": _latest(rid, "shapes/upos_top1"), "keyed": _latest(rid, "shapes/keyed_top1")},
            # the schedule the voyage runs and the stage it is in: hold, fade, release, content
            "schedule": {**_schedule(spec, rid), "phases_detail": _phase_metrics(spec, rid, _schedule(spec, rid))},
            "content": _content_version((spec.get("data") or {}).get("recipe")),
            # what is pinned, and where: one entry a layer, with the cards in it, and the model's own depth
            "pinned": (spec.get("optim") or {}).get("scaffold", {}).get("heads") or [],
            "riddles": list(((spec.get("optim") or {}).get("scaffold") or {}).get("riddles") or {}),
            "layers": (next((x for x in _sizes_for((spec.get("model") or {}).get("preset"))), {}) or {}).get("layers"),
            "heads_per_layer": (next((x for x in _sizes_for((spec.get("model") or {}).get("preset"))), {}) or {}).get("heads"),
            "step": step, "loss": loss, "bpb": bpb, "chaining": chain,
            "started": r.get("started"),
        })
    # a name is reused across voyages: keep the newest running row per name, or three dead control arms
    # appear beside the live one (9 November)
    # prefer the voyage with the most recent *reading*, not the newest row: a run that has not written its
    # first metric yet can otherwise lose to a finished voyage of the same name (9 November)
    newest: dict[str, dict] = {}
    for r in rows:
        cur = newest.get(r["name"])
        if cur is None or str(r.get("started") or "") > str(cur.get("started") or ""):
            newest[r["name"]] = r
    return {"expedition": expedition, "arms": sorted(newest.values(), key=lambda r: r["name"])}


def _card_metric(card: str) -> str:
    """The reading a card's mark is measured on (thorp/viable/s5_policy/deck.py's look)."""
    if card == "induction":
        return "nevermore/natural_max_score"
    if card == "sink":
        return "stars/attention_sink/max_score"
    return f"stars/{card}/max_score"


def _card_marks() -> dict[str, float]:
    from thorp.viable.s5_policy import deck

    return {c.key: float(c.look[1]) for c in deck.CARDS if c.look}


def _peak_final(run_id: str, name: str):
    """A reading's peak and its latest value: peak is what the pull achieved, final what survived it."""
    try:
        row = _rows(
            "select max(value) as peak, "
            "(select value from metrics where run_id=? and name=? order by step desc limit 1) as final "
            "from metrics where run_id=? and name=?", [run_id, name, run_id, name])
        return (None if not row else row[0]["peak"]), (None if not row else row[0]["final"])
    except Exception:  # noqa: BLE001
        return None, None


def _sizes_for(preset: str | None) -> list[dict]:
    try:
        from thorp import ship_store

        return [r for r in ship_store.sizes() if r["preset"] == preset]
    except Exception:  # noqa: BLE001
        return []


def _deck_classes() -> dict[str, dict]:
    from thorp.viable.s5_policy import deck

    return {c.key: {"stage": c.stage, "suit": c.constellation} for c in deck.CARDS}


def _cards_summary(spec: dict, run_id: str) -> dict:
    """The ship's card holdings by class and suit: how many Basic, Stage 1 and Face heads it carries, and
    how many in each suit, with how many of them clear their marks right now."""
    from collections import Counter

    heads = ((spec.get("optim") or {}).get("scaffold") or {}).get("heads") or []
    marks = _card_marks()
    deck = _deck_classes()
    by_stage: dict[str, dict] = {}
    by_suit: dict[str, dict] = {}
    lit = 0
    for h in heads:
        info = deck.get(h.get("card")) or {}
        now = _latest(run_id, _card_metric(h.get("card")))
        mark = marks.get(h.get("card"))
        is_lit = now is not None and mark is not None and now >= mark
        if is_lit:
            lit += 1
        for bucket, name in ((by_stage, info.get("stage") or "other"), (by_suit, info.get("suit") or "other")):
            e = bucket.setdefault(name, {"n": 0, "lit": 0})
            e["n"] += 1
            e["lit"] += 1 if is_lit else 0
    return {"by_stage": by_stage, "by_suit": by_suit, "lit": lit, "total": len(heads)}


def _at(run_id: str, name: str, step: int):
    """The reading nearest a step (the last one at or before it)."""
    try:
        rows = _rows(
            "select value from metrics where run_id=? and name=? and step<=? order by step desc limit 1",
            [run_id, name, step],
        )
        return None if not rows else float(rows[0]["value"])
    except Exception:  # noqa: BLE001
        return None


def _phase_metrics(spec: dict, run_id: str, sch: dict) -> list[dict]:
    """What each phase of the schedule did: the cards' readings at its start and end, and how much of each
    was still there at the end (9 November, Justin: "if I expand it tells me how well the fade held")."""
    total = sch.get("total")
    if not total:
        return []
    heads = ((spec.get("optim") or {}).get("scaffold") or {}).get("heads") or []
    marks = _card_marks()
    hold = sch.get("hold") or 0.0
    fade = sch.get("fade") if sch.get("fade") is not None else 1.0
    rel = sch.get("release")
    bounds = []
    if hold and hold > 0:
        bounds.append(("hold", 0.0, float(hold)))
    if rel is not None:
        bounds.append(("fade", float(hold), float(rel)))
        bounds.append(("release", float(rel), 1.0))
    else:
        bounds.append(("fade", float(hold), float(fade)))
        bounds.append(("content", float(fade), 1.0))
    out = []
    for name, a, b in bounds:
        s0, s1 = int(a * total), int(b * total)
        cards = []
        for h in heads:
            m = _card_metric(h.get("card"))
            v0, v1 = _at(run_id, m, s0), _at(run_id, m, s1)
            cards.append({"card": h.get("card"), "start": v0, "end": v1,
                          "kept": None if not v0 or v1 is None else round(100 * v1 / v0, 0),
                          "mark": marks.get(h.get("card"))})
        out.append({"name": name, "from": s0, "to": s1,
                    "loss_start": _at(run_id, "loss", s0), "loss_end": _at(run_id, "loss", s1),
                    "cards": cards})
    return out


def _content_version(recipe: str | None) -> dict:
    """Which stamped version a voyage reads: the manifest beside its list, or the list itself (books only)."""
    import json
    from pathlib import Path

    from thorp import paths

    if not recipe:
        return {}
    stem = Path(recipe).stem
    m = paths.resolve("ships") / "lists" / f"{stem}.manifest.json"
    if m.exists():
        d = json.loads(m.read_text())
        return {"version": d.get("version"), "transform": d.get("transform"), "books": d.get("books"),
                "marked": d.get("marked"), "about": d.get("about"), "stamped": True}
    try:
        import csv

        with open(paths.resolve(recipe), encoding="utf-8", newline="") as f:
            n = sum(1 for _ in csv.DictReader(f))
    except Exception:  # noqa: BLE001
        n = None
    return {"version": stem, "books": n, "stamped": False}


def _schedule(spec: dict, run_id: str) -> dict:
    """The scaffold's schedule and where the voyage is in it, from its own spec and the weight it logged."""
    sc = ((spec.get("optim") or {}).get("scaffold") or {})
    total = int((spec.get("optim") or {}).get("steps") or 0) or (lambda v: int(v) if v else None)(
        _latest(run_id, "plan/total_steps"))
    hold, fade = sc.get("hold"), sc.get("fade")
    release = sc.get("release")
    weight = _latest(run_id, "scaffold/weight")
    step = _latest_step(run_id) or 0
    stage = "–"
    if total:
        if release is not None and step >= float(release) * total:
            stage = "content — released"
        elif hold is not None and step < float(hold) * total:
            stage = "hold"
        elif fade is not None and step < float(fade) * total:
            stage = "fade"
        else:
            stage = "content"

    # The top-level schedule is the scaffold's, and a voyage can give each head its own (10 November: the three
    # decayers fade while the other eight are released). Group the cards by the schedule they actually run, so
    # the page does not show one bar for a voyage that has two.
    def _f(obj: dict, key: str, fallback):
        v = obj.get(key, fallback)
        return None if v is None else float(v)

    groups: dict[tuple, dict] = {}

    def _add(card: str, hold_: float | None, fade_: float | None, rel_: float | None) -> None:
        kind = "release" if rel_ is not None else "fade"
        share = rel_ if rel_ is not None else (fade_ if fade_ is not None else 1.0)
        key = (kind, share, hold_, fade_)
        g = groups.setdefault(
            key, {"kind": kind, "share": share, "hold": hold_, "fade": fade_, "cards": [], "pins": 0}
        )
        g["cards"].append(card)
        g["pins"] += 1

    for h in sc.get("heads") or []:
        _add(h.get("card"), _f(h, "hold", hold), _f(h, "fade", fade), _f(h, "release", release))
    for card in sc.get("riddles") or {}:  # a riddle has no schedule of its own: it runs the scaffold's
        _add(card, _f({}, "hold", hold), _f({}, "fade", fade), _f({}, "release", release))

    out = []
    for g in groups.values():
        g["cards"] = sorted(set(g["cards"]))  # a card pinned twice is one card, two pins
        out.append(g)
    return {"hold": hold, "fade": fade, "release": release, "weight": weight, "stage": stage,
            "step": step, "total": total, "groups": out}


def _latest_ts(run_id: str):
    try:
        row = _rows("select max(ts) as ts from metrics where run_id=?", [run_id])
        return None if not row or row[0]["ts"] is None else float(row[0]["ts"])
    except Exception:  # noqa: BLE001
        return None


def _latest_bpb(run_id: str):
    """bpb lives in the evals table, not in metrics (9 November: the arm cards read 0)."""
    try:
        row = _rows("select avg(bpb) as bpb from evals where run_id=? and step=(select max(step) from evals where run_id=?)",
                    [run_id, run_id])
        return None if not row or row[0]["bpb"] is None else float(row[0]["bpb"])
    except Exception:  # noqa: BLE001
        return None


def _latest(run_id: str, name: str):
    try:
        row = _rows("select value from metrics where run_id=? and name=? order by step desc limit 1", [run_id, name])
        return None if not row else float(row[0]["value"])
    except Exception:  # noqa: BLE001
        return None


def _latest_step(run_id: str):
    try:
        row = _rows("select max(step) as step from metrics where run_id=?", [run_id])
        return None if not row or row[0]["step"] is None else int(row[0]["step"])
    except Exception:  # noqa: BLE001
        return None


def _chaining(run_id: str):
    lifts = []
    for t in ("breeders_test", "mill_test", "between_test", "pigeonhole_test"):
        v = _latest(run_id, f"tricks/{t}/lift")
        if v is not None:
            lifts.append(v)
    return sum(lifts) / len(lifts) if lifts else None


_SHAPE_PARAMS: dict[tuple, dict] = {}


def _shape_params(
    family: str, preset: str | None, vocab: int, context: int, positions: str, kv_heads: int
) -> dict:
    """A preset's parameter counts for the shape a spec asks for, built once a shape and kept: the
    queue page opens every voyage's card and all of a class's arms share a shape."""
    key = (family, preset, vocab, context, positions, kv_heads)
    if key not in _SHAPE_PARAMS:
        try:
            from thorp.models import registry

            model = registry.build(family, preset, vocab, context, positions, kv_heads=kv_heads)
            _SHAPE_PARAMS[key] = model.parameter_counts()
        except Exception:  # noqa: BLE001  (no MLX on a box, or a preset this code does not know)
            _SHAPE_PARAMS[key] = {}
    return _SHAPE_PARAMS[key]


_SEED_MODES = {  # thorp/train.py: what the inherited weights do during the leg
    "free": "every inherited weight keeps learning",
    "slow": "the inherited weights learn at a reduced rate",
    "freeze": "the inherited weights stay as they were",
}
_TURN_SHAPES = {  # thorp/turns.py pair()
    "marks": "<question>Q<answer>A<end>",
    "plain": "Question: Q / Answer: A",
}
_SEEDED: dict = {"key": None, "by_seed": {}}
_EVAL_WORDS: dict[str, str | None] = {}


def _seeded_index() -> dict[str, list[dict]]:
    """Every fitout spec that is seeded from another voyage, by the seed's name: the legs that follow a
    voyage. Rebuilt only when a spec file changes (the queue page is polled and there are hundreds of specs)."""
    import yaml

    files = sorted(paths.resolve("specs/fitouts").glob("*.yaml"))
    key = (len(files), max((f.stat().st_mtime_ns for f in files), default=0))
    if _SEEDED["key"] != key:
        by_seed: dict[str, list[dict]] = {}
        for f in files:
            try:
                s = yaml.safe_load(f.read_text()) or {}
            except (OSError, ValueError):
                continue
            seed = (s.get("seeded_from") or {}).get("run") if isinstance(s.get("seeded_from"), dict) else None
            if seed:
                by_seed.setdefault(seed, []).append(s)
        _SEEDED.update(key=key, by_seed=by_seed)
    return _SEEDED["by_seed"]


def _evaluator_words(name: str) -> str | None:
    """What an evaluator reads, in its own words: the first sentence of its module's docstring, read from
    the file (never imported: an evaluator pulls in MLX)."""
    if name not in _EVAL_WORDS:
        import ast

        words = None
        try:
            doc = ast.get_docstring(ast.parse((paths.BACKEND / "thorp" / "evaluators" / f"{name}.py").read_text()))
            if doc:
                words = " ".join(doc.split("\n\n")[0].split())
        except (OSError, SyntaxError):
            words = None
        _EVAL_WORDS[name] = words
    return _EVAL_WORDS[name]


def _turn_keys(recipes: list[str]) -> set[int]:
    """The IFEval prompt keys a voyage trains on: its recipes' instruction turns (`local:ifp-m-13` is key 13)."""
    import csv

    keys: set[int] = set()
    for recipe in recipes:
        try:
            with open(paths.resolve(recipe), encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    m = re.fullmatch(r"local:ifp-[a-z]+-(\d+)", str(r.get("text") or ""))
                    if m:
                        keys.add(int(m.group(1)))
        except OSError:
            continue
    return keys


def _stage_rows(data: dict) -> list[dict]:
    """A voyage's stages in the order it reads them, each with its book count (one stage when it names none)."""
    stages = data.get("stages") or [{"name": "content", "recipe": data.get("recipe"), "passes": data.get("passes")}]
    return [
        {"name": s.get("name"), "recipe": s.get("recipe"), "passes": s.get("passes", 1),
         "books": _content_version(s.get("recipe")).get("books")}
        for s in stages
    ]


def _post_readings(spec: dict) -> dict:
    """How a leg is judged: when it is read, on which sets, and each evaluator with its own options. For
    the two readings that write answers, how many of the prompts they ask are in the leg's own training
    turns, counted from the lists: a reading on prompts the ship was trained on is not a held-out one."""
    ev = spec.get("eval") or {}
    data = spec.get("data") or {}
    options = ev.get("options") or {}
    every = ev.get("every_steps")
    trained: set[int] | None = None
    rows = []
    for name in ev.get("evaluators") or []:
        opts = options.get(name) if isinstance(options.get(name), dict) else {}
        row = {"name": name, "what": _evaluator_words(name), "options": opts, "seen": None}
        if name in ("answers", "ifeval"):
            if trained is None:
                trained = _turn_keys([s["recipe"] for s in _stage_rows(data) if s.get("recipe")])
            try:
                if name == "answers":
                    held = paths.resolve(str(opts.get("heldout") or "lists/return-heldout-v1.jsonl"))
                    asked = {json.loads(ln)["key"] for ln in held.read_text(encoding="utf-8").splitlines() if ln.strip()}
                    row["seen"] = {"n": len(asked & trained), "of": len(asked), "set": held.name}
                elif trained:
                    row["seen"] = {"n": len(trained), "of": 541, "set": "the official prompts"}
            except (OSError, ValueError, KeyError):
                row["seen"] = None
        rows.append(row)
    return {
        "every_steps": every,
        # train.py reads at `step % every == 0 or step == total`: an interval no voyage reaches is "at the end"
        "when": "once, when it docks" if every and int(every) >= 10**8 else f"every {int(every):,} steps and when it docks" if every else None,
        "sets": ev.get("sets") or [],
        "evaluators": rows,
    }


def _post_training(spec: dict) -> dict:
    """What the post-training does, for the queue's card (11 November, Justin: "in the voyage modal we need
    to see what the posttraining does"). For a leg (a spec with `seeded_from`): the voyage it starts from
    and where that voyage stands, what happens to the inherited weights, whether the scaffold still pulls,
    the turn format, the stages in order and how the leg is read. For any voyage: the legs seeded from it."""
    o = spec.get("optim") or {}
    data = spec.get("data") or {}
    sc = o.get("scaffold") or {}
    seed = spec.get("seeded_from") if isinstance(spec.get("seeded_from"), dict) else None
    out: dict = {"leg": bool(seed), "seed": None, "legs": []}
    if seed:
        row = _run_row_by_name(seed.get("run") or "") or {}
        rid = row.get("run_id")
        try:
            seed_spec = json.loads(row.get("spec_json") or "{}")
        except ValueError:
            seed_spec = {}
        mode = seed.get("mode") or "free"
        out["seed"] = {
            "run": seed.get("run"), "mode": mode, "mode_words": _SEED_MODES.get(mode), "at_step": seed.get("step"),
            "status": ("at sea" if row.get("status") == "running" else row.get("status")) if row else None,
            "step": _latest_step(rid) if rid else None,
            "total": _latest(rid, "plan/total_steps") if rid else None,
            "bpb": _latest_bpb(rid) if rid else None,
            "lr": (seed_spec.get("optim") or {}).get("lr"),
        }
        weight = sc.get("weight")
        out["pull"] = {
            "weight": weight, "pins": len(sc.get("heads") or []), "riddles": len(sc.get("riddles") or {}),
            "off": not sc or (weight is not None and float(weight) == 0.0),
        }
        fmt = data.get("turns")
        out["turns"] = {"format": fmt, "shape": _TURN_SHAPES.get(fmt)} if fmt else None
        out["stages"] = _stage_rows(data)
        out["lr"] = o.get("lr")
        out["read"] = _post_readings(spec)
    for leg in _seeded_index().get(spec.get("name") or "", []):
        ld = leg.get("data") or {}
        out["legs"].append({
            "name": leg.get("name"), "ship": leg.get("ship"), "mode": (leg.get("seeded_from") or {}).get("mode") or "free",
            "turns": ld.get("turns"), "lr": (leg.get("optim") or {}).get("lr"), "stages": _stage_rows(ld),
            "evaluators": (leg.get("eval") or {}).get("evaluators") or [],
        })
    return out


def _spec_detail(spec: dict, run: dict | None = None) -> dict:
    """Everything a voyage's spec fixes, for the card the queue opens (11 November): the model's shape,
    its tokeniser, what it reads, its optimiser and schedule, the scaffold's pins and riddles, and, once
    it has sailed, its latest readings. Read from the spec, never inferred from the page."""
    from thorp.models import registry

    m = spec.get("model") or {}
    o = spec.get("optim") or {}
    data = spec.get("data") or {}
    tok = spec.get("tokeniser") or {}
    sc = o.get("scaffold") or {}
    preset = m.get("preset")
    family = m.get("family") or "gpt"
    vocab = int(tok.get("vocab") or 2048)
    context = int(m.get("context") or 1024)
    positions = m.get("positions") or "learned"
    kv = int(m.get("kv_heads") or 0)
    shape = registry.PRESETS.get(preset) or {}
    run_id = (run or {}).get("run_id")
    marks = _card_marks() if run_id else {}
    classes = _deck_classes() if run_id else {}
    cards = []
    for h in sc.get("heads") or []:
        card = h.get("card")
        entry = {
            "card": card, "layer": h.get("layer"), "head": h.get("head"),
            "hold": h.get("hold"), "fade": h.get("fade"), "release": h.get("release"),
        }
        if run_id and card:
            peak, now = _peak_final(run_id, _card_metric(card))
            entry.update({
                "mark": marks.get(card), "peak": peak, "now": now,
                "stage": (classes.get(card) or {}).get("stage"),
                "suit": (classes.get(card) or {}).get("suit"),
            })
        cards.append(entry)
    readings = None
    if run_id:
        readings = {
            "step": _latest_step(run_id), "loss": _latest(run_id, "loss"), "bpb": _latest_bpb(run_id),
            "chaining": _chaining(run_id),
            "tokens_seen": (run or {}).get("tokens_seen") or _latest(run_id, "tokens_seen"),
            "started": (run or {}).get("started"),
            "shapes": {
                "upos": _latest(run_id, "shapes/upos_top1"),
                "keyed": _latest(run_id, "shapes/keyed_top1"),
            },
            "cards": cards,
        }
    return {
        "model": {
            "family": family, "preset": preset, "kv_heads": kv, "context": context, "positions": positions,
            "layers": shape.get("layers"), "heads": shape.get("heads"), "width": shape.get("width"),
            "params": _shape_params(family, preset, vocab, context, positions, kv),
        },
        "tokeniser": {
            "kind": tok.get("kind"), "vocab": vocab, "byte_fallback": tok.get("byte_fallback"),
            "train_on": tok.get("train_on"), "symbols": tok.get("symbols") or [],
        },
        "data": {
            "recipe": data.get("recipe"), "passes": data.get("passes"),
            "stages": _stage_rows(data) if data.get("stages") else [],
            "order": data.get("order"), "refuse": data.get("refuse") or [], "clean": data.get("clean"),
            "opt_in": data.get("opt_in"),
        },
        "post": _post_training(spec),
        "optim": {
            "name": o.get("name"), "lr": o.get("lr"), "warmup_steps": o.get("warmup_steps"),
            "schedule": o.get("schedule"), "min_lr_ratio": o.get("min_lr_ratio"),
            "batch_tokens": o.get("batch_tokens"), "grad_clip": o.get("grad_clip"),
            "precision": o.get("precision"), "steps": o.get("steps"),
        },
        "scaffold": {
            "weight": sc.get("weight"), "hold": sc.get("hold"), "fade": sc.get("fade"),
            "release": sc.get("release"), "heads": cards, "riddles": sc.get("riddles") or {},
        },
        "content": _content_version(data.get("recipe")),
        "schedule": _schedule(spec, run_id or ""),
        "readings": readings,
    }


def api_hulls() -> dict:
    """Every rung's hull: layers, width, heads, and the head width that follows, read from Postgres
    (s1.sizes), not from the code's presets (9 November, Justin: "each model's layers, width, heads, head
    dim and set ... set in the postgres db")."""
    from thorp import ship_store

    rows = []
    for r in ship_store.sizes():
        w, h = r.get("width"), r.get("heads")
        rows.append({
            "preset": r["preset"], "name": r.get("name"), "kind": r.get("kind"),
            "layers": r.get("layers"), "width": w, "heads": h,
            "head_dim": (w // h) if (w and h) else None,
            "vocab": r.get("vocab"), "status": r.get("status"),
        })
    return {"hulls": rows}


def api_hull_save(preset: str = "", layers: str = "", width: str = "", heads: str = "") -> dict:
    """Set one rung's hull in s1.sizes."""
    from thorp import ship_store, store
    from thorp.viable.s3_control.models import Size

    if not preset:
        raise ValueError("preset is required")
    with store.session() as s:
        r = s.get(Size, preset)
        if r is None:
            raise KeyError(f"no size called {preset!r}")
        if layers:
            r.layers = int(layers)
        if width:
            r.width = int(width)
        if heads:
            r.heads = int(heads)
        if r.width and r.heads and r.width % r.heads:
            raise ValueError(f"{r.width} wide does not divide into {r.heads} heads")
        s.merge(r)
    ship_store.reload()
    return {"preset": preset, "layers": r.layers, "width": r.width, "heads": r.heads}


def api_deck_atlas() -> dict:
    """The charting page's overview: the cards as jobs, the four questions they pass, and where each card
    is seeded and found across the 0.0.5 fleet (thorp.deck_atlas).

    Memoised for a minute: the computation is cheap (0.05 s) but the dashboard is polled, and a request that
    runs it on every poll competes with whatever else the server is doing (10 November, the charting page
    "takes so long to load")."""
    import time

    from thorp import deck_atlas

    if _ATLAS_CACHE["value"] is not None and time.time() - _ATLAS_CACHE["at"] < 60.0:
        return _ATLAS_CACHE["value"]
    value = deck_atlas.payload()
    _ATLAS_CACHE.update(at=time.time(), value=value)
    return value


def api_shipbuilder(harbour: str = "schimint") -> dict:
    """The ship builder's page: the harbour and every SOP version, so the variables can be read and edited."""
    from thorp import ship_store, sop, starchart

    h = ship_store.harbour(harbour)
    if h is None:
        raise LookupError(f"no harbour {harbour!r}")
    if not h.get("ship_builder"):
        raise LookupError(f"{h['name']} has no ship builder: ships are built at Schi'mint; Vavatch End and Masaq' Reach only sail them")
    vs = sop.versions()
    standards = {v: sop.standard(v) for v in vs}
    from thorp import paths

    base = paths.resolve("lists")
    libraries = []
    for p in sorted(base.glob("*.csv")) + sorted((base / "stores").glob("*.csv")):
        if p.stat().st_size > 20_000_000:  # a synthetic deck, not a shelf
            continue
        libraries.append({"path": "lists/" + str(p.relative_to(base)), "name": p.stem.replace("-", " ")})
    return {
        "harbour": h,
        "libraries": libraries,
        "control": sop.control_catalog(),
        "sop": {
            "current": sop.CURRENT,
            "versions": vs,
            "standards": standards,
            "locked": sop.at_sea(),
        },
        "embeddings": {k: {"vocab": 2048, "width": c["width"], "params": 2048 * c["width"],
                           "total": _model_params(k), "share": (2048 * c["width"]) / max(1, _model_params(k)),
                           "thorp": True}
                        for k, c in __import__("thorp.models.registry", fromlist=["PRESETS"]).PRESETS.items()}
                      | {k: {"vocab": c["vocab"], "width": c["width"], "params": c["vocab"] * c["width"],
                             "total": c["params"], "share": (c["vocab"] * c["width"]) / max(1, c["params"]),
                             "thorp": False, "lab": c["lab"]}
                         for k, c in __import__("thorp.models.registry", fromlist=["FOREIGN"]).FOREIGN.items()},
        "shapes": {k: {"layers": c["layers"], "width": c["width"], "heads": c["heads"], "thorp": True}
                   for k, c in __import__("thorp.models.registry", fromlist=["PRESETS"]).PRESETS.items()}
                  | {k: {"layers": c["layers"], "width": c["width"], "heads": c["heads"], "thorp": False,
                         "lab": c["lab"], "params": c["params"]}
                     for k, c in __import__("thorp.models.registry", fromlist=["FOREIGN"]).FOREIGN.items()},
        "journey": ship_store.journey("invention-return"),
        "chart": {
            "points": list(starchart.POINTS),
            "depths": {v: starchart.depths(std) for v, std in standards.items()},
        },
    }


def api_shipbuilder_save(body: dict) -> dict:
    """Define a new SOP version from the ship builder's edited variables. A saved version is never
    overwritten; it is not in force until a voyage names it."""
    from datetime import datetime

    from thorp import ship_store, sop

    key = body.get("harbour") or "schimint"
    h = ship_store.harbour(key)
    if h is None:
        raise LookupError(f"no harbour {key!r}")
    if not h.get("ship_builder"):
        raise LookupError(f"{h['name']} has no ship builder: ships are built at Schi'mint; Vavatch End and Masaq' Reach only sail them")
    standard = body.get("standard")
    if not isinstance(standard, dict):
        raise ValueError("standard is a JSON object")
    # a version with a ship out is locked (9 November, Justin): no change may be built on it while a
    # voyage named for it is at sea. A new version is still free to be made from a version in port.
    from_version = str(body.get("from_version") or "").strip()
    sea = sop.at_sea()
    if from_version and from_version in sea:
        raise ValueError(
            f"SOP v{from_version} is locked: {sea[from_version]} is at sea on it. A version with a ship out "
            "cannot be changed; wait for it to dock, or build the change on a version that is in port."
        )
    adopted = (body.get("adopted") or "").strip() or (
        f"defined at {h['name']} by {h.get('ship_builder') or 'the ship builder'}, "
        f"{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}"
    )
    v = sop.save(
        standard,
        adopted=adopted,
        doc=body.get("doc") or "",
        version=body.get("version") or None,
        supersedes=body.get("supersedes") or None,
    )
    from thorp import starchart

    std = sop.standard(v)
    return {"version": v, "standard": std, "versions": sop.versions(),
            "chart": {"depths": starchart.depths(std)}}


def api_foreign(key: str = "qwen3-4b") -> dict:
    """One outside model's readings, for its foreign-ship page (a spyglass, not a Nothing up my sleeve ship)."""
    from thorp import foreign

    p = foreign.payload(key)
    if p is None:
        raise LookupError(f"no foreign ship {key!r}")
    return p


def api_expedition_priority() -> dict:
    """The expeditions in priority order, one row a goal where an expedition states goals: the rank
    Justin set (thorp.priorities), the name, the goal and the status, and the queue's own order after it
    was applied. An expedition that is closed is not a rankable row and never appears here."""
    from thorp import expedition_goals, fleet, priorities

    ord_ = priorities.order()
    # the verdicts live in the store (11 November): a priority row is a goal row, so its key is the
    # goal id and its state comes back with it
    try:
        verdicts = {g["goal_id"]: g for g in expedition_goals.read()}
    except Exception:  # noqa: BLE001  (a store before the goal tables: the page still lists the rows)
        verdicts = {}
    rows = []
    for i, k in enumerate(ord_):
        exp, _, goal = k.partition(":")
        e = fleet.EXPEDITIONS.get(exp)
        if not e or priorities.closed(exp):
            continue
        n = int(goal) if goal else None
        v = verdicts.get(k) or {}
        rows.append(
            {
                "key": k,
                "goal_id": k,
                "expedition": exp,
                "name": e.name,
                "goal": n,
                "goal_text": priorities.goal_text(exp, n),
                "goal_status": v.get("status", "open"),
                "goal_evidence": v.get("evidence", ""),
                "status": e.status,
                "priority": i + 1,
            }
        )
    return {"order": [r["key"] for r in rows], "expeditions": rows}


def post_expedition_priority(body: dict) -> dict:
    """Save the priority order and reorder the pending spec lines to it; the coordinator takes the
    first line, so the highest-priority expedition's earliest voyage sails next."""
    from thorp import priorities

    keys = [str(k) for k in (body.get("order") or [])]
    # a closed expedition cannot be planned, so its rows are dropped rather than refused: the rest of
    # the order still saves, and the page never offers them in the first place
    kept = [k for k in keys if not priorities.closed(k.split(":", 1)[0])]
    order = priorities.set_order(kept)
    return {"order": order, "reordered": True, "dropped": [k for k in keys if k not in kept]}


def api_journeys() -> dict:
    """Every journey as its nested plan (`pretraining.stage[]` outbound, `posttraining.stage[]` the return)."""
    from thorp import ship_store

    return {"journeys": ship_store.journeys()}


def api_journey(key: str) -> dict:
    from thorp import ship_store

    return {"journey": ship_store.journey(key)}


def api_rung(preset: str, limit: int | str = 0) -> list[dict]:
    """Training-loss curves (at most 300 points each) for the runs at one preset: all of them, or
    the latest `limit` (the proxy loop puts thousands of runs on one size)."""
    out = []
    picked = []
    for r in _runs_rows():
        spec = json.loads(r["spec_json"] or "{}")
        if spec.get("model", {}).get("preset") == preset:
            picked.append(r)
    if int(limit or 0) > 0:
        picked = picked[-int(limit) :]
    for r in picked:
        s, v = _metric_series_gated(r["run_id"], "loss")
        pts = [{"step": st, "value": val} for st, val in zip(s, v, strict=True)]
        k = max(1, len(pts) // 300)
        out.append(
            {
                "run_id": r["run_id"],
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
    for r in _runs_rows():
        spec = json.loads(r.pop("spec_json") or "{}")
        if spec.get("model", {}).get("preset") == preset and not (r["name"] or "").startswith(
            "smoke"
        ):
            picked.append(r)
    if int(limit or 0) > 0:
        picked = picked[-int(limit) :]
    out = []
    for r in picked:
        series: dict[str, dict[int, float]] = {}
        for x in _metric_name_rows(r["run_id"], "nevermore/") + _metric_name_rows(
            r["run_id"], "probe/"
        ):
            name, step, value = x["name"], x["step"], x["value"]
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
        for a in _artifact_rows(r["run_id"], "nevermore"):
            try:
                art = json.loads(a["text"])
            except ValueError:
                continue
            step = a["step"]
            if hands and hands[-1]["step"] == step:
                hands.pop()  # a re-score of the same step replaces it
            hands.append(
                {"step": step, "random": art.get("scores"), "real": art.get("natural_scores")}
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
        "author": f"Nothing up my sleeve · {module.replace('.', '/')}.py",
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
    rows = _runs_rows()
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


def _api_voyages() -> list[dict]:
    """Every voyage: goal, outcomes, levers, stop rule, status, lessons and its runs (voyages.py)."""
    import sqlite3
    import time

    from thorp import expeditions as voyages

    # the Mac lane writes the ledger every few seconds now, so a read can find it locked: wait and try
    # again rather than serve the fallback for two minutes (9 November)
    for attempt in range(3):
        try:
            return voyages.payload()
        except sqlite3.OperationalError:
            if attempt == 2:
                raise
            time.sleep(1.5)
    return voyages.payload()


_VOYAGES_CACHE: dict = {"value": None, "at": 0.0, "busy": False}


def _voyages_fallback() -> list[dict]:
    """The expedition definitions, without the ledger's runs: what the page needs to name the expedition
    and open its SOP tabs while the live ledger is locked by a training run."""
    from thorp import fleet

    out = []
    for k, v in fleet.EXPEDITIONS.items():
        out.append({
            "key": k, "name": getattr(v, "name", k), "goal": getattr(v, "goal", ""),
            "status": getattr(v, "status", ""), "runs": [], "ships": [], "plan": [],
            "stop": {"max_runs": 0},
        })
    return out


def api_voyages() -> list[dict]:
    """Every voyage, served from a cache: the live ledger can be locked by the training run, and this
    endpoint used to hang the expedition pages. A cached copy (memory, then data/voyages-cache.json) is
    returned at once; the full read refreshes it in the background. With no copy yet, the static
    expedition definitions are returned after a short wait, so the page always opens."""
    import json
    import threading
    import time

    from thorp import paths

    cache_file = paths.data_dir() / "voyages-cache.json"
    v = _VOYAGES_CACHE["value"]
    if v is None and cache_file.exists():
        try:
            v = json.loads(cache_file.read_text())
            _VOYAGES_CACHE.update(value=v, at=cache_file.stat().st_mtime)
        except Exception:  # noqa: BLE001
            v = None
    if v is not None:
        if time.time() - _VOYAGES_CACHE["at"] > 120.0 and not _VOYAGES_CACHE["busy"]:
            _VOYAGES_CACHE["busy"] = True

            def refresh():
                try:
                    d = _api_voyages()
                    _VOYAGES_CACHE.update(value=d, at=time.time())
                    cache_file.write_text(json.dumps(d, default=str))
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    _VOYAGES_CACHE["busy"] = False

            threading.Thread(target=refresh, daemon=True).start()
        return v
    if _VOYAGES_CACHE["busy"]:
        return _voyages_fallback()
    _VOYAGES_CACHE["busy"] = True

    def first():
        try:
            d = _api_voyages()
            _VOYAGES_CACHE.update(value=d, at=time.time())
            cache_file.write_text(json.dumps(d, default=str))
        except Exception:  # noqa: BLE001
            pass
        finally:
            _VOYAGES_CACHE["busy"] = False

    t = threading.Thread(target=first, daemon=True)
    t.start()
    t.join(1.5)
    return _VOYAGES_CACHE["value"] if _VOYAGES_CACHE["value"] is not None else _voyages_fallback()


def api_voyage_series(key: str) -> dict:
    """For one voyage's runs, each star's score at every reading, so a chart can show the step at
    which a line crosses its threshold: first light. A run that received heads from another
    (a `transplant` artifact: the Magician's Apprentice) carries the record, and the donor run is
    added (role "donor") so its curve sits beside the receivers'."""
    from thorp import expeditions as voyages
    from thorp import fleet

    v = fleet.EXPEDITIONS[key]
    runs = [{**r, "role": None} for r in voyages.runs_of(v)]

    def series_of(run_id: str) -> dict:
        series = {}
        for sk, star in fleet.STARS.items():
            s, vv = _metric_series_gated(run_id, star.metric)
            series[sk] = {"step": s, "value": vv}
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
        a = _artifact(run_id, "transplant")
        try:
            return json.loads(a["text"]) if a and a["text"] else None
        except ValueError:
            return None

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
        row = _run_row(d)
        if row and row["run_id"] not in have:
            have.add(row["run_id"])
            out.insert(
                0,
                {
                    "run_id": row["run_id"],
                    "name": row["name"],
                    "ship": row["ship"],
                    "role": role,
                    "transplant": None,
                    "teacher": None,
                    "series": series_of(row["run_id"]),
                },
            )
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
# 11 Nov (Justin): the 300k is the towing tank (was Faces, and Pan before it) and the 1m the measured mile
# (was Augustus); every older name maps to the current one
CLASS_RENAMES = {"seedling": "towing-tank", "keel": "towing-tank", "pan": "towing-tank", "faces": "towing-tank", "proxy": "measured-mile", "pilot": "measured-mile", "augustus": "measured-mile", "bettor": "explorer", "explorer": "invention", "summit": "trader"}


def _class_names(preset: str) -> set[str]:
    """A size's names, the current one and every older one (CLASS_RENAMES), for code that keys a size by name."""
    import re

    slug = _slug(preset)
    # CLASS_RENAMES is keyed by address slugs, and a two-word name's has a hyphen ("towing tank" is "towing-tank")
    key = re.sub(r"[^a-z0-9]+", "-", slug)
    return {slug, key} | {old for old, new in CLASS_RENAMES.items() if new == key}


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
    the chain grades, s4.outside_readings): each chain's grade, and the reference ladder's readings on every
    rung (fleet.REFERENCE_LADDER: Pythia 14m to 410m and Qwen3 0.6B), per-pair lifts only if asked."""
    from thorp import fleet

    d = readings.get("chain-grades")
    if d is None:
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


def _floor(run_id: str, metric: str) -> float | None:
    """A trick's floor on one run: the untrained model's reading (tricks/<key>/floor_lift beside a
    tricks/<key>/lift), the last one recorded, or None where the trick has no floor."""
    if not metric.endswith("/lift"):
        return None
    return _metric(run_id, metric[: -len("lift")] + "floor_lift")


def _pairs(path: str | None) -> list[dict] | None:
    """A matched-pairs list (prompt, idea, rival, and the frame: the prompt's tail that the lift is
    measured against, absent on the keel's lists), or None when it is not written yet."""
    import csv

    from thorp import paths

    if not path:
        return None
    p = paths.resolve(path)
    if not p.exists():
        return None
    with open(p, newline="") as f:
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
    """One of the explorer's tests told as a climb (fleet.CHAINS): the idea, who found it, the shelf,
    and each step keel to explorer with what it adds, the class it belongs to (fleet.RUNGS), its pairs
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
    for run in _runs_rows():
        rid = run["run_id"]
        for a in _artifact_rows(rid, "discovery"):
            try:
                body = json.loads(a["text"] or "{}")
            except ValueError:
                continue
            runs[rid] = {
                "run_id": rid,
                "name": run["name"],
                "preset": json.loads(run["spec_json"] or "{}").get("model", {}).get("preset"),
            }
            for k, v in body.items():
                if isinstance(v, dict) and "pairs" in v:
                    latest.setdefault(k, {})[rid] = v
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


_CHAINS_CACHE: dict = {"at": 0.0, "value": None}


def api_chains() -> list[dict]:
    """Every discovery chain, for the Quantum tests tab: one ladder per test, each rung with its
    questions. api_chain is the expensive per-chain read (runs and discovery artifacts), so this is
    one request for the tab rather than four, and it is kept for a minute."""
    import time

    from thorp import fleet

    if _CHAINS_CACHE["value"] is not None and time.time() - _CHAINS_CACHE["at"] < 60:
        return _CHAINS_CACHE["value"]
    out = [api_chain(k) for k in fleet.CHAINS]
    _CHAINS_CACHE.update(at=time.time(), value=out)
    return out


# ---- slow payloads, kept warm: the shelves take seconds to compute (they read every list and the
# catalogue), so the last result is served while a fresh one is computed in the background
_WARM: dict[str, dict] = {}
_WARM_LOCK = __import__("threading").Lock()


def _warm_file(name: str):
    """The last build of a warm endpoint, on disk (data/warm/<name>.json)."""
    import json

    from thorp import paths

    f = paths.data_dir() / "warm" / f"{name}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:  # noqa: BLE001
        return None


def _warm_save(name: str, value, at: float) -> None:
    import json

    from thorp import paths

    f = paths.data_dir() / "warm" / f"{name}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    # a build can carry dates (the library's years and timestamps): serialise them as text, never drop the cache
    f.write_text(json.dumps({"at": at, "value": value}, default=str))


def _warm(name: str, fn, ttl: float = 300.0):
    import threading
    import time

    with _WARM_LOCK:
        e = _WARM.setdefault(name, {"at": 0.0, "value": None, "busy": False, "error": None})
        # a cached build survives a restart: the library page was taking ~40 s on every fresh dashboard
        if e["value"] is None and not e["busy"]:
            cached = _warm_file(name)
            if cached:
                e["value"], e["at"] = cached["value"], cached["at"]
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
                        with contextlib.suppress(Exception):
                            _warm_save(name, v, e["at"])
                    e["busy"], e["error"] = False, err
                # a build's thread ends here: give its Postgres reader back (see ledger.close_reader)
                with contextlib.suppress(Exception):
                    from thorp.ledger import close_reader

                    close_reader()

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
    for f in mine:
        readings = {}
        for r in f.get("runs", []):
            row = _run_row_by_name(r["run"])
            if not row:
                continue
            r["status"] = row["status"] or r.get("status")
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
                    got = _metric(row["run_id"], metric)
                    if got is not None:
                        vals[kind] = got
                if vals:
                    best = max(vals.values())
                    per[k] = {**vals, "lit": best >= st.threshold, "threshold": st.threshold}
            readings[r["run"]] = per
        f["run_cards"] = readings
    return {"fitouts": mine, "computing": False, "error": error}


_sops_cache: dict[str, tuple[float, dict]] = {}


def api_sops(preset: str) -> dict:
    """The SOP versions, the standard a size's voyages are built to (10 November: the old Fitouts tab is
    the SOPs now — "this /ships/21m/fitouts should be SOP"). Each version with its phases, content,
    parameters, the depth it gives this size, its runs here and its scores, plus whether it is current
    and locked (a version with a ship at sea cannot change)."""
    import time

    from thorp import sop

    hit = _sops_cache.get(preset)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    versions = sop.versions()
    locked = sop.at_sea()
    base = preset.split("-")[0]
    runs = []
    for r in _runs_rows():
        spec = json.loads(r.get("spec_json") or "{}")
        p = spec.get("model", {}).get("preset")
        if p == preset or (p or "").startswith(preset + "-"):
            runs.append(
                {
                    "run_id": r["run_id"],
                    "name": r["name"],
                    "ship": r["ship"],
                    "status": r["status"],
                    "started": r["started"],
                    "sop": spec.get("sop"),
                    "preset": p,
                }
            )
    scored = {x.get("sop"): x for x in (api_sop_scores(preset).get("versions") or [])}
    latest = max((r for r in runs if r.get("sop")), key=lambda r: r.get("started") or "", default=None)
    out = []
    for v in versions:
        st = sop.standard(v) or {}
        if not st:
            continue
        depth = ((st.get("depth") or {}).get("computed") or {}).get(base)
        mine = sorted([r for r in runs if r.get("sop") == v], key=lambda r: r.get("started") or "", reverse=True)
        out.append(
            {
                "version": v,
                "current": bool(latest and latest.get("sop") == v),
                "locked": v in locked,
                "adopted": st.get("adopted"),
                "supersedes": st.get("supersedes"),
                "doc": st.get("doc"),
                "about": st.get("about"),
                "art": st.get("art"),
                "phases": st.get("phases") or [],
                "content": st.get("content") or {},
                "parameters": st.get("parameters") or {},
                "depth": depth,
                "goals": st.get("goals") or [],
                "cards": st.get("cards") or [],
                "readings": st.get("readings") or {},
                "score": scored.get(v),
                "runs": mine,
            }
        )
    # the current standard first, then newest first
    out.sort(key=lambda x: tuple(int(p) for p in x["version"].split(".")), reverse=True)
    out.sort(key=lambda x: not x["current"])
    payload = {"preset": preset, "current": latest.get("sop") if latest else None, "locked": locked, "versions": out}
    _sops_cache[preset] = (time.time(), payload)
    return payload


CLASS_CARDS = {  # card -> (one-head metric, a layer's best two or None), as scripts/make_card_census.py reads them
    "previous_word": ("stars/previous_word/max_score", "stars/previous_word/shared_score"),
    "nevermore": ("nevermore/natural_max_score", None),
    "mover": ("stars/mover/max_score", "stars/mover/shared_score"),
    "comparator": ("stars/comparator/max_score", "stars/comparator/shared_score"),
}


_class_cards_cache: dict[str, tuple[float, dict]] = {}


def api_class_cards(preset: str, runs: str = "") -> dict:
    """Cached a minute: the page asks on every refresh and the read scans every card row of the class.
    `runs` narrows the read to named voyages (the page's expedition/voyage selection)."""
    import time

    key = preset + "|" + runs
    hit = _class_cards_cache.get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    out = _class_cards(preset, runs)
    _class_cards_cache[key] = (time.time(), out)
    return out


def _class_cards(preset: str, runs: str = "") -> dict:
    """The one thing a class's Overview shows (Justin, 2026-11-07: "one thing that encompasses as much as
    there is to know"): the four necessary cards against their marks, each at the best reading any voyage
    of the class reached (the better of one head and a layer's best two, at any step: a card that lit and
    faded still counts as drawn), with the voyage and step, how many voyages lit it, and where the newest
    finished voyage ended; beside them the cause-and-effect chaining gain (eight items: noise within
    about ±0.1). A class's voyages are those whose preset is the class's or a variant of it (300k-h4)."""
    import statistics

    from thorp import fleet

    wanted = {x for x in runs.split(",") if x}
    runs = []
    for r in _runs_rows():
        if wanted and r.get("name") not in wanted and r.get("run_id") not in wanted:
            continue
        p = json.loads(r.get("spec_json") or "{}").get("model", {}).get("preset")
        if p == preset or (p or "").startswith(preset + "-"):
            runs.append({"run_id": r["run_id"], "name": r["name"], "started": r["started"], "status": r["status"], "p": p})
    ids = [r["run_id"] for r in runs]
    by = {r["run_id"]: r for r in runs}
    names = [m for pair in CLASS_CARDS.values() for m in pair if m] + ["tricks/logic_test/gain_cause"]
    peak, last = {}, {}
    for rid in ids:
        for name in names:
            s, v = _metric_series_gated(rid, name)
            best_val, best_step = None, None
            for val, st in zip(v, s, strict=True):
                if val is None or val != val:
                    continue
                if best_val is None or val > best_val:
                    best_val, best_step = val, st
                last[(rid, name)] = (val, st)
            if best_val is not None:
                peak[(rid, name)] = (best_val, best_step)
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
        ends = [x[0] for r in finished if (x := reading(r["run_id"], pair, last)) is not None]
        med = statistics.median(ends) if ends else None
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
                # the expedition selection's median of the finished voyages' last readings
                "median": None if med is None else {"value": med, "held": med >= th, "of": len(ends)},
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
        "median_held": sum(1 for c in cards if c["median"] and c["median"]["held"]),
        "cause": {
            "best": None if top is None else {"value": top[0][0], "step": top[0][1], "run": top[1]},
            "finished_range": [min(cause_last), max(cause_last)] if cause_last else None,
            "median": statistics.median(cause_last) if cause_last else None,
            "noise": 0.1,
            # chaining is judged on where voyages end, never on a passing peak
            "chains": bool(cause_last and max(cause_last) > 0.1),
        },
    }


_class_score_cache: dict[str, tuple[float, dict]] = {}


def api_class_score(preset: str, runs: str = "") -> dict:
    """Cached a minute: the Ships page asks for every size at once."""
    import time

    key = preset + "|" + runs
    hit = _class_score_cache.get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    out = _class_score(preset, runs)
    _class_score_cache[key] = (time.time(), out)
    return out


def _class_score(preset: str, runs: str = "") -> dict:
    """A class's live scoring readings (registry.LADDER's "scored": the four necessary cards held,
    then cause and effect, then chaining two facts) from its best ship (the leaderboard's ships, ranked
    by chaining lift; leaderboard.thorp_entry gives its cards), and the best cards held so far in its
    fitout's census (data/runs/cards/fitout-census-<key>-readings.json, once it lands).

    The crowned version is reported beside it, not instead of it: a version is only crowned when it beats
    the last by more than the noise, so the crowned name can be behind the best ship (10 November: the
    21m's best, 21m@v0.0.5, was hidden by the crowned v1 on the board)."""
    from thorp import fleet, leaderboard

    lb = api_leaderboard()  # the served payload: one build for every size's card, not seven
    wanted = [x for x in runs.split(",") if x]
    crowned = None if wanted else next(
        (
            b["best"]
            for b in lb.get("board", [])
            if b.get("best") and b["best"].get("preset") == preset
        ),
        None,
    )
    candidates = [
        s for s in lb.get("ships", [])
        if s.get("preset") == preset
        and (not wanted or any(x in wanted for x in (s.get("runs") or [s.get("run")])) )
    ]
    if wanted and not candidates:
        # a selected voyage with no chaining reading is not in the leaderboard's ships: still name it,
        # so the callout says which voyage is selected rather than nothing (10 November)
        row = _run_row(wanted[0])
        if row:
            spec = json.loads(row.get("spec_json") or "{}")
            candidates = [{"ship_key": fleet.ship_key(spec), "ship": row.get("ship") or row.get("name"),
                           "run": row.get("name"), "runs": [row.get("name")], "preset": preset, "chaining_lift": None}]
    out: dict = {"preset": preset, "version": None}
    if crowned:
        out["crowned"] = crowned.get("name")
        out["crowned_chaining"] = crowned.get("chaining_lift")

    def readings(ship: dict) -> tuple[dict, dict, list]:
        e = leaderboard.thorp_entry(ship["ship_key"]) or {}
        cards = e.get("cards") or {}
        lit = {
            k: bool((cards.get(k) or {}).get("lit") or (cards.get(k) or {}).get("lit_shared"))
            for k in CENSUS_CARDS
        }
        lifts = [
            (e.get(k) or {}).get("lift")
            for k in ("nature_test", "mill_test", "between_test", "pigeonhole_test")
        ]
        return e, lit, [v for v in lifts if isinstance(v, (int, float))]

    # the best ship is the top of the class's ranked ships; a ship still at sea can lead the board
    # before its cards are read, so fall back to the crowned version once rather than walking every
    # candidate (10 November: the walk called the whole-run thorp_entry scan per ship and held Postgres
    # connections until the pool ran dry, which hung the scoring page)
    best = (candidates[0] if candidates else crowned)
    e, lit, chaining = readings(best) if best else ({}, {}, [])
    if best and not any(lit.values()) and not chaining and crowned and crowned.get("ship_key") != best.get("ship_key"):
        best = crowned
        e, lit, chaining = readings(best)
    if best:
        out.update(
            version=best.get("name") or best.get("ship"),
            ship_key=best.get("ship_key"),
            ship=best.get("ship"),
            cards=lit,
            held=sum(lit.values()),
            cause=(e.get("logic_test") or {}).get("gain_cause"),
            # a ship still at sea has no finished-run entry yet: its ranked chaining lift is still a
            # reading, so use it rather than showing "–" for the size (10 November)
            chaining=sum(chaining) / len(chaining) if chaining else best.get("chaining_lift"),
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


def _knockout_files() -> list[tuple[str, dict]]:
    return readings.glob("knockout-*")


def api_knockout(model: str = "") -> dict:
    """The knockout (fleet.EXPEDITIONS["knockout"], thorp/knockout.py; DECISIONS.md "The knockout,
    pre-registered"): in a model that chains, each card's 8 strongest heads silenced and the logic
    deck and the chaining tests read again, beside three random draws of 8 heads. One model's
    result (s4.outside_readings, knockout-<model, / as __>), or every result when no model is named."""
    from thorp import fleet

    competitors = getattr(fleet, "COMPETITORS", {})
    out = []
    for stem, d in _knockout_files():
        d.setdefault("model", stem[len("knockout-") :].replace("__", "/"))
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


def _sizes_all() -> list[dict]:
    """Every size of ship on the ladder, in order: the presets and the names they sail under (Pan, Augustus, ...),
    for the Library page's size filter (Justin, 8 November: "a filter ... so that we can filter branches by which
    ships size they can work on")."""
    from thorp import ship_store

    try:
        return [{"preset": r["preset"], "name": r["name"]} for r in ship_store.sizes()]
    except Exception:  # noqa: BLE001  the store is down: the page shows no size filter rather than no page
        return []


def _sizes_by_list() -> dict[str, set[str]]:
    """Which sizes have read each list: the presets of the voyages whose reading (or whose first stage) is that list.
    Evidence, not intent: a variation no voyage has read has no sizes, and the page says so rather than guessing."""
    from thorp import ship_store
    from thorp.ledger import Ledger

    out: dict[str, set[str]] = {}
    try:
        rows = Ledger().query(
            "select json_extract(spec_json,'$.model.preset') p, json_extract(spec_json,'$.data.recipe') r"
            " from runs where p is not null and r is not null"
            " union all"
            " select json_extract(spec_json,'$.model.preset'), json_extract(st.value,'$.recipe')"
            " from runs, json_each(coalesce(json_extract(spec_json,'$.data.stages'),'[]')) st"
            " where json_extract(st.value,'$.recipe') is not null"
        )
        for r in rows:
            try:
                size = ship_store.size_of(r["p"])  # a variant is cut from a rung: 300k-l1w96 -> 300k
            except KeyError:
                continue
            out.setdefault(r["r"], set()).add(size)
    except Exception:  # noqa: BLE001  no ledger, no evidence: every variation simply has no sizes
        return {}
    return out


def _browse_build() -> dict:
    from thorp import library, library_configs, selection
    from thorp import library_facts as lf

    facts_all = lf.build()
    rows = facts_all  # every book, Nothing up my sleeve's own derived texts too (kind "derived": the tutor's passages, the shuffled controls)
    cols = library.collections()
    member: dict[str, list[int]] = {}
    for i, c in enumerate(cols):
        for b in c["book_ids"]:
            member.setdefault(b, []).append(i)
    books = [[r["book"], r["title"], r["author"], r["language"], r["source"], r["kind"], r["voice"], r["year"], r["year_basis"],
              r["ogden"], r["words"], member.get(r["book"], []), r["kind_rule"], r["voice_rule"]] for r in rows]  # fmt: skip
    from thorp import library_branches
    from thorp.viable.s3_control import fitout_store

    stored = True
    try:
        brs = fitout_store.branches()
    except Exception:  # noqa: BLE001  the store is down, or not migrated yet: the defaults are shown, and say so
        brs = []
    if not brs:
        brs, stored = library_branches.DEFAULTS, False
    index = {r["book"]: i for i, r in enumerate(rows)}
    from thorp import fitouts as saved_fitouts

    read_by: dict[str, list[str]] = {}  # list path -> the saved fitouts that read it
    for f in saved_fitouts.saved():
        for st in f.get("stages") or []:
            read_by.setdefault(st["shelf"], []).append(f["key"])
    sizes_by_list = _sizes_by_list()  # list path -> the sizes that have read it (the ledger's evidence)
    size_rank = {r["preset"]: i for i, r in enumerate(_sizes_all())}
    configs_by: dict[str, list[dict]] = {}
    try:  # the table may not be migrated yet: the branch page still opens, with no saved configurations
        for c in fitout_store.configurations():
            configs_by.setdefault(c["branch_key"], []).append(c)
    except Exception:  # noqa: BLE001
        configs_by = {}
    branches = []
    for b in brs:
        vs = []
        for v in b["variations"]:
            ids = library_branches.variation_ids(v, facts_all)
            vs.append({"key": v["key"], "name": v["name"], "about": v.get("about", ""), "draft": bool(v.get("draft")),
                       "derived_from": v.get("derived_from"), "kind": "list" if v.get("list") else "selection" if v.get("spec") else "all",
                       "spec": v.get("spec"), "list": v.get("list"), "fitouts": read_by.get(v.get("list") or "", []),
                       "sizes": sorted(sizes_by_list.get(v.get("list") or "", set()), key=lambda p: size_rank.get(p, 99)),
                       "books": sorted(index[i] for i in ids if i in index)})
        sizes = sorted({p for v in vs for p in v["sizes"]}, key=lambda p: size_rank.get(p, 99))
        branches.append({
            "key": b["key"], "name": b["name"], "purpose": b["purpose"], "variations": vs, "sizes": sizes,
            "attributes": library_configs.attributes(b["key"]),
            "default_choices": library_configs.defaults(b["key"], b["variations"]),
            "configurations": configs_by.get(b["key"], []),
        })
    return {
        "branches": branches, "branches_stored": stored,
        "sizes": _sizes_all(),
        "books": books,
        "fields": ["book", "title", "author", "language", "source", "kind", "voice", "year", "year_basis", "ogden", "words",
                   "collections", "kind_rule", "voice_rule"],
        "collections": [{k: c[k] for k in ("path", "name", "kind", "about")} | {"books": len(set(c["book_ids"]) & {r["book"] for r in rows})}
                        for c in cols],
        "kinds": lf.KIND_ABOUT, "voices": lf.VOICE_ABOUT, "knowledge": lf.KNOWLEDGE_ABOUT,
        "year": {"floruit_age": lf.FLORUIT_AGE, "late_before_death": lf.LATE_BEFORE_DEATH, "gate": lf.GATE_DEATH_LIMIT},
        "fingerprint": lf.fingerprint(rows),
        "selection_keys": sorted(selection.KEYS),
    }


# The browse payload's warm name carries its shape: a dashboard restarted on new code would otherwise serve the
# last build on disk (data/warm/) for up to an hour, in the shape the old code wrote. -2: a branch's attributes
# may name `knowledge`, and the payload carries the four kinds' descriptions (12 November).
_BROWSE_WARM = "library_browse-2"


def api_library_browse() -> dict:
    """The library's books and what is known of each, for the Library page's filters and cards (thorp/library_facts.py):
    kind, date, language, collection, voice, source and Ogden-ness. Built warm: the first call may answer `computing`."""
    value, busy, error = _warm(_BROWSE_WARM, _browse_build, ttl=3600.0)
    return value if value is not None else {"computing": busy, "error": error}


def api_library_configs(branch: str) -> dict:
    """A branch's saved configurations, read live (the branch payload's copy is warm and may lag a save)."""
    from thorp.viable.s3_control import fitout_store

    try:
        return {"configurations": fitout_store.configurations(branch)}
    except Exception as e:  # noqa: BLE001  the table may not be migrated yet
        return {"configurations": [], "error": str(e)}


def api_library_config_preview(body: dict) -> dict:
    """What a branch configuration holds right now (thorp/library_configs.py): the books it chooses, the words,
    the makeup by kind/voice/source/period, and the selection spec it composes to. The branch page's sliders
    call this as they move; it reads the facts warm."""
    from thorp import library_configs
    from thorp import library_facts as lf

    branch = str(body.get("branch") or "")
    choices = library_configs.validate(branch, body.get("choices") or {})
    facts, busy, error = _warm("library_facts", lf.build, ttl=3600.0)
    if facts is None:
        return {"computing": busy, "error": error}
    return library_configs.preview(branch, choices, facts)


def api_library_config_save(body: dict) -> dict:
    """Save a branch's JSON of choices, content-addressed by the choices themselves. A new save with the same
    choices updates its name and note; a different JSON is a different configuration, never a version."""
    from thorp import library_branches, library_configs
    from thorp.viable.s3_control import fitout_store

    branch = str(body.get("branch") or "")
    choices = library_configs.validate(branch, body.get("choices") or {})
    fitout_store.migrate()
    fitout_store.seed_branches(library_branches.DEFAULTS)
    return fitout_store.save_configuration(
        branch, str(body.get("name") or ""), choices, about=str(body.get("about") or ""), by="the branch page"
    )


def api_library_config_delete(body: dict) -> dict:
    from thorp.viable.s3_control import fitout_store

    key = str(body.get("key") or "")
    if not key:
        raise ValueError("a configuration key is needed")
    return {"deleted": fitout_store.delete_configuration(key), "key": key}


def api_selection(fitout: str) -> dict:
    """A fitout's books as the Fitouts tab shows them (thorp/selection.py, thorp/library_facts.py): for each stage
    the weights and filters it declares (or that its library is listed by hand), the latest composing (its funnel,
    the gate's library prechecks, the diff to a list it was set beside), the counts by language, kind, voice,
    source and period of the books it yields, and the books with the rule that placed each. Also the rules in
    full (what a kind, a voice and a year mean), so the bias in a count can be read."""
    from collections import Counter

    from sqlalchemy import text

    from thorp import fitouts, selection
    from thorp import library_facts as lf
    from thorp.viable.s3_control import fitout_store

    f = fitouts.load(fitout)
    if f is None:
        from thorp import fleet

        f = fitouts.from_curated(fitout) if fitout in getattr(fleet, "FITOUTS", {}) else None
    if f is None:
        raise LookupError(f"no fitout {fitout}")
    with fitout_store.engine().connect() as c:
        have = c.execute(text("select count(*) from s3.library_facts")).scalar()
        facts = {r["book"]: dict(r) for r in c.execute(text("select * from s3.library_facts")).mappings()} if have else {}
    comps = {(x["ordinal"]): x for x in reversed(fitout_store.compositions(fitout, 40))}
    stages = []
    for i, st in enumerate(f["stages"], 1):
        ids = []
        try:
            ids = selection.list_ids(st["shelf"])
        except Exception:  # noqa: BLE001  a shelf not written yet yields no books
            pass
        rows = [facts[b] for b in ids if b in facts]
        sizes = {"derived": [r for r in rows if r["source"] == "local"], "library": [r for r in rows if r["source"] != "local"]}

        def split(key, rs=rows):
            c = Counter()
            for r in rs:
                c[str(r[key])] += r["words"]
            tot = sum(c.values()) or 1
            n = Counter(str(r[key]) for r in rs)
            return {k: {"books": n[k], "words": v, "share": round(v / tot, 4)} for k, v in c.most_common()}

        def period(rs):
            c = Counter()
            n = Counter()
            for r in rs:
                d = lf.decade(r["year"])
                c[d] += r["words"]
                n[d] += 1
            tot = sum(c.values()) or 1
            return {d: {"books": n[d], "words": c[d], "share": round(c[d] / tot, 4)} for d in sorted(c)}

        c = comps.get(i)
        stages.append({
            "ordinal": i, "name": st["name"], "shelf": st["shelf"], "passes": st.get("passes"),
            "compose": selection.validate(st["compose"]) if st.get("compose") else None, "books": len(ids), "found": len(rows),
            "words": sum(r["words"] for r in rows), "tutor_words": sum(r["words"] for r in sizes["derived"]),
            "by_language": split("language"), "by_kind": split("kind"), "by_voice": split("voice"), "by_source": split("source"),
            "by_period": period(rows),
            "by_year_basis": split("year_basis"),
            "composition": {k: c[k] for k in ("id", "spec_hash", "facts_fingerprint", "list_path", "list_sha1", "books", "words",
                                              "funnel", "notes", "prechecks", "passed", "against", "diff", "composed_at")} if c else None,
            "books_list": [{"book": r["book"], "title": r["title"], "author": r["author"], "language": r["language"],
                            "source": r["source"], "kind": r["kind"], "kind_rule": r["kind_rule"], "voice": r["voice"],
                            "voice_rule": r["voice_rule"], "year": r["year"], "year_basis": r["year_basis"],
                            "ogden": r["ogden"], "words": r["words"]} for r in rows[:600]],
        })  # fmt: skip
    return {
        "fitout": {"key": f["key"], "name": f["name"]},
        "stages": stages,
        "facts": {"books": have, "fingerprint": fitout_store.facts_fingerprint()},
        "rules": {
            "kinds": lf.KIND_ABOUT, "voices": lf.VOICE_ABOUT,
            "year": {"floruit_age": lf.FLORUIT_AGE, "late_before_death": lf.LATE_BEFORE_DEATH, "gate": lf.GATE_DEATH_LIMIT},
            "keys": sorted(selection.KEYS),
        },
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
    for run in [x for x in runs.split(",") if x][:40]:
        row = _run_row(run)
        if not row:
            continue
        out[run] = {}
        for m in [x for x in metrics.split(",") if x][:12]:
            s, v = _metric_series_gated(row["run_id"], m)
            if s:
                out[run][m] = [s, v]
    return out


def api_store() -> dict:
    """Whether the one store (Postgres) answers: the page says so when it does not."""
    why = store.ping()
    return {"up": why is None, "why": why}


def api_governance() -> dict:
    """Nothing up my sleeve's rules as Beer's Viable System Model (thorp/vsm.py): the five systems (S1 operations to
    S5 policy) with their code, and the live audit: the voyages, the queue's collisions, each policy's
    enforcement and the queued runs that break it, the outside world Nothing up my sleeve measures itself against.
    Read-only: switching a policy is Justin's S5 decision, recorded in s5.policy_switches (`thorp s5 switch`)."""
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


# ---- fast reads: the queue landing's three endpoints read the live ledger, which a training run locks.
# They are served from a memory/disk cache (stale-while-revalidate) with an empty fallback after 1.5 s, so
# the page always opens; the full read refreshes behind it. 9 November, "speed up /expeditions".
_FAST: dict[str, dict] = {}

_QUEUE_FALLBACK = {"rows": [], "hours_left": 0, "without_a_time": 0}
_OVERVIEW_FALLBACK = {"at_sea": [], "queue": {}, "expeditions": [], "sops": [], "helm": None}
_WATERS_FALLBACK = {
    "now": "", "plan": [],
    "lanes": {
        "mac": {"name": "Schi'mint", "where": "this Mac mini", "how": "MLX, the Mac lane: the home ring",
                "at_sea": None, "ships": [], "queued": 0, "voyages": 0, "hours_left": 0,
                "at_least": False, "clear_at": "", "week": None},
        "vast": {"name": "Vavatch End", "where": "GPUs hired from Vast.ai", "how": "torch on CUDA, the Vast lane: the deep yards",
                 "at_sea": None, "ships": [], "queued": 0, "voyages": 0, "hours_left": 0,
                 "at_least": False, "clear_at": "", "week": None, "key": None},
    },
}


def _fast_cache(name: str, fn, fallback, ttl: float = 60.0, watch=None):
    """Serve `fn()` from memory/disk, refreshing in the background. The first call waits 1.5 s for the
    compute and otherwise returns `fallback`, so a locked ledger never blocks the page. `watch` is a path
    whose mtime invalidates the cache sooner than `ttl` (the queue: the coordinator edits the file and the
    page must not sit on a 60 s-old queue)."""
    import json
    import threading
    import time

    from thorp import paths

    e = _FAST.setdefault(name, {"value": None, "at": 0.0, "busy": False})
    cache_file = paths.data_dir() / f"{name}-cache.json"
    v = e["value"]
    if v is None and cache_file.exists():
        try:
            v = json.loads(cache_file.read_text())
            e.update(value=v, at=cache_file.stat().st_mtime)
        except Exception:  # noqa: BLE001
            v = None
    if v is not None:
        stale = time.time() - e["at"] > ttl
        if watch is not None:
            try:
                stale = stale or watch.stat().st_mtime > e["at"]
            except OSError:
                pass
        if stale and not e["busy"]:
            e["busy"] = True

            def refresh():
                try:
                    d = fn()
                    e.update(value=d, at=time.time())
                    cache_file.write_text(json.dumps(d, default=str))
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    e["busy"] = False

            threading.Thread(target=refresh, daemon=True).start()
        return v
    if e["busy"]:
        return fallback
    e["busy"] = True

    def first():
        try:
            d = fn()
            e.update(value=d, at=time.time())
            cache_file.write_text(json.dumps(d, default=str))
        except Exception:  # noqa: BLE001
            pass
        finally:
            e["busy"] = False

    t = threading.Thread(target=first, daemon=True)
    t.start()
    t.join(1.5)
    return e["value"] if e["value"] is not None else fallback


def api_expeditions_overview() -> dict:
    return _fast_cache("overview", _api_expeditions_overview, _OVERVIEW_FALLBACK)


def api_queue() -> dict:
    from thorp.viable.s2_coordination import queue_store

    # the store is the only source; its 10 s TTL is the invalidation (the file is never read here)
    return _fast_cache("queue", _api_queue, _QUEUE_FALLBACK, ttl=10.0, watch=None)


def api_waters() -> dict:
    import thorp.dash.waters as waters

    return _fast_cache("waters", waters.waters, _WATERS_FALLBACK)


# ---- the words since 2026-11-07 16:20 (fleet.TERMS): an expedition is a line of experiments (was a voyage), a voyage
# is one ship's run (was a run), a library is a book list (was a shelf). Storage keeps run_id and the runs table.


def _api_expeditions_overview() -> dict:
    """The queue at a glance (thorp.expeditions.overview): the voyage at sea, the queue's voyages and
    hours left, and per expedition its voyages at sea, finished, failed and queued, and where its next
    one stands in the queue."""
    from thorp import expeditions

    return expeditions.overview()


def _api_queue() -> dict:
    """The queue as a table (Justin, 17:05: "view the queue so each voyage with its goal"): the voyage at
    sea, then every line of specs/queue.txt in order, each voyage with its goal (its spec's question),
    its expedition, class and seed, and about when it sails (each queued voyage before it at its class's
    mean wall time over finished voyages); a `cmd:` line is a step between voyages."""
    import yaml

    from thorp import fleet

    root = paths.ROUTER
    all_runs = _runs_rows()
    status = {r["name"]: r["status"] for r in all_runs}
    from thorp.dash.timing import RunTimes

    times = RunTimes(all_runs)
    # "at sea" means the voyage holds a helm seat now: a run killed with a signal never writes a finish, so
    # the ledger can say running for a voyage that stopped hours ago (9 November, the queue page showing
    # killed 9m arms as at sea). The seats are the authority, the ledger the record. Read every helm slot,
    # not the lane's seat count: the manual survivors can sit in slot 3 while a two-seat lane reads 1-2,
    # and the release then disappeared from this page (10 November).
    from thorp import vsm

    try:
        seats = {h.get("name") for h in vsm.helms(8)}
        helm_known = True
    except Exception:  # noqa: BLE001  (no store on a box)
        seats, helm_known = set(), False
    # One row a voyage, not one a run: a name that was launched, failed and relaunched has several ledger
    # rows still marked running (10 November: the fulldeck showed twice on the queue page), and the seat is
    # keyed by name, so every stale row on a live name passed the filter.
    def _fresh(r: dict) -> bool:
        """A running row with no helm but a live run log: a manually started voyage (or one the
        coordinator adopted before a restart) is still at sea, and the page should show it."""
        p = paths.data_dir() / "runs" / f"{r['run_id']}.log"
        try:
            return p.exists() and time.time() - p.stat().st_mtime < 900
        except OSError:
            return False

    newest: dict[str, dict] = {}
    for r in all_runs:
        # an empty helm means nothing is at sea, not every stale `running` row: when the queue is down the
        # seat set is empty, and `(seats and ...)` used to be False, so the killed 9m arms came back
        # (10 November). Only a helm that could not be read falls back to the ledger. A live run log
        # rescues a manual voyage the coordinator did not launch (11 November: the release-pins).
        if r["status"] != "running":
            continue
        if helm_known and r["name"] not in seats and not _fresh(r):
            continue
        cur = newest.get(r["name"])
        if cur is None or str(r.get("started") or "") > str(cur.get("started") or ""):
            newest[r["name"]] = r
    sea = list(newest.values())

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
            "sop": spec.get("sop"),  # the standard the voyage is built to (9 November: the fitout is retired)
            "expedition": ex,
            "expedition_name": fleet.EXPEDITIONS[ex].name if ex in fleet.EXPEDITIONS else None,
            "preset": m.get("preset"),
            "seed": spec.get("seed"),
            "status": state,
        }

    import time as _time
    from datetime import datetime, timezone

    from thorp.viable.s2_coordination import lanes as lane_mod

    now = _time.time()

    def _slots(lane: str) -> int:
        try:
            return lane_mod.slots_of(lane)
        except Exception:  # noqa: BLE001  no store on a box: one seat
            return 1

    two = set(lane_mod.TWO_AT_ONCE)
    # A lane's seat state: {end, kind}. On the Mac two 300k lines may share the GPU; a 1m or 9m takes
    # the whole lane, which is the coordinator's capacity rule. This is a schedule, not a sum of means.
    seat = {lane: [{"end": now, "kind": None} for _ in range(_slots(lane))] for lane in lane_mod.LANES}

    def _started_min(started: str | None) -> float | None:
        if not started:
            return None
        try:
            d = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0.0, (datetime.now(d.tzinfo or timezone.utc) - d).total_seconds() / 60)

    rows = []
    for run in sea:
        name, ship, started = run["name"], run["ship"], run["started"]
        try:
            spec = json.loads(run["spec_json"] or "{}")
        except ValueError:
            spec = {}
        if not spec.get("question"):  # the ledger's copy may not keep it; the spec file does
            f = next(iter((root / "specs").rglob(f"{name}.yaml")), None)
            spec = {**spec, **((yaml.safe_load(f.read_text()) or {}) if f else {})}
        else:
            f = next(iter((root / "specs").rglob(f"{name}.yaml")), None)
        spec_path = None
        if f:
            try:
                spec_path = f.relative_to(root / "specs").with_suffix("").as_posix()
            except ValueError:
                spec_path = None
        r = {**row(name, ship, spec, "at sea", None), "started": started, "run_id": run["run_id"],
             "spec": spec_path, "detail": _spec_detail(spec, run)}
        est, source = times.estimate(name, spec)
        r["est_min"], r["est_source"] = est, source
        rows.append(r)
        if est is not None:
            gone = _started_min(started)
            left = max(0.0, est - (gone or 0.0))
            preset = r.get("preset")
            if preset in two:
                s = min(seat["mac"], key=lambda x: x["end"])
                s["end"], s["kind"] = now + left, preset
            else:
                for s in seat["mac"]:
                    s["end"], s["kind"] = now + left, "other"
    lines = _queue_lines()
    # the goal a line serves, so the page can say what each row is for (s2.queue_lines.goal_id)
    from thorp.viable.s2_coordination import queue_store as _qs

    try:
        line_goals = {r["text"]: r.get("goal_id") for r in _qs.lines()}
    except Exception:  # noqa: BLE001  (a store before the goal column: the queue still shows)
        line_goals = {}

    def _cmd_label(cmd: str) -> tuple[str, str]:
        """A step's words, not its command line: an investigation says which investigation, and any other
        step says which script or module it runs (11 November: rows 3 and 4 read `PYTHONPATH=backend`)."""
        m = re.search(r"-m\s+thorp\.investigate\s+run\s+(\S+)", cmd)
        if m:
            name = m.group(1)
            f = root / "specs" / "investigations" / f"{name}.yaml"
            try:
                spec = yaml.safe_load(f.read_text()) or {}
            except (OSError, ValueError):
                spec = {}
            return (spec.get("ship") or spec.get("name") or name), "investigation"
        m = re.search(r"-m\s+([\w.]+)", cmd)
        if m:
            return m.group(1), "step"
        words = cmd.split()
        scripts = [w for w in words if w.endswith((".py", ".sh"))]
        if scripts:
            return Path(scripts[0]).name, "step"
        return (words[-1] if words else cmd), "step"

    # A step's length (12 November, Justin: "when scheduling tasks like investigations they should also have an
    # estimated length so the queue is accurate"). An investigation: its last finished run, else its spec's
    # `estimate:`, else its deadline as an upper bound (thorp.investigate.estimate). Any other command: how
    # long it took the last time the queue ran it (data/runs/queue.out). Until then a step took no time at
    # all here, so every line behind the 8-hour Qwen reading was shown starting at once.
    from thorp import investigate as _inv
    from thorp.dash import waters as _waters

    try:
        last_steps = _waters._step_minutes()
    except Exception:  # noqa: BLE001  (no queue log: no command has a time of its own yet)
        last_steps = {}

    def _cmd_estimate(line: str) -> tuple[float | None, str, bool]:
        spec_ = _inv.of_line(line)
        if spec_ is not None:
            try:
                return _inv.estimate(spec_)
            except ValueError:
                return None, "no time", False
        last = last_steps.get(line.strip())
        if last is not None:
            return float(last), "its last run", False
        return None, "no time", False

    def _since_min(since) -> float | None:
        """Minutes since a lane's `since` (this Mac's local time, as s2.lanes writes it)."""
        try:
            return max(0.0, (now - datetime.fromisoformat(str(since)).timestamp()) / 60)
        except (TypeError, ValueError):
            return None

    # a command at sea holds the lane's seat too: the ledger has no run for it, so it is read from the lane's
    # own row (s2.lanes), and what it has left is its estimate less the time it has been out
    try:
        lane_now = lane_mod.state()
    except Exception:  # noqa: BLE001  (no store on a box)
        lane_now = {}
    for lane, out_ in (lane_now or {}).items():
        line = str((out_ or {}).get("line") or "")
        if not line.startswith("cmd:") or lane not in seat:
            continue
        est, source, is_max = _cmd_estimate(line)
        label, what = _cmd_label(line[4:].strip())
        gone = _since_min(out_.get("since"))
        left = max(0.0, est - (gone or 0.0)) if est is not None else None
        rows.insert(0, {"n": None, "kind": "step", "name": label, "what": what, "cmd": line[4:].strip(),
                        "goal_id": line_goals.get(line), "status": "at sea", "lane": lane,
                        "started": out_.get("since"), "est_min": est, "est_source": source, "est_is_max": is_max,
                        "elapsed_min": round(gone) if gone is not None else None,
                        "left_min": round(left) if left is not None else None})
        for s in seat[lane]:
            s["end"], s["kind"] = now + (left or 0.0), "other"

    unknown = {lane: False for lane in lane_mod.LANES}  # a voyage ahead with no time yet
    for lane, out_ in (lane_now or {}).items():  # a command at sea with no time of its own: all behind it is ≥
        if str((out_ or {}).get("line") or "").startswith("cmd:") and lane in unknown:
            unknown[lane] = unknown[lane] or _cmd_estimate(str(out_["line"]))[0] is None
    without_a_time = 0
    for i, ln in enumerate(lines, 1):
        if ln.startswith("cmd:"):
            cmd = ln[4:].strip()
            label, what = _cmd_label(cmd)
            est, source, is_max = _cmd_estimate(ln)
            r = {"n": i, "kind": "step", "name": label, "what": what, "cmd": cmd,
                 "goal_id": line_goals.get(ln), "status": "queued", "lane": "mac",
                 "est_min": est, "est_source": source, "est_is_max": is_max}
            if est is None:
                # a step with no time: it still holds the lane, so every line behind it starts no sooner
                without_a_time += 1
                r["starts_in_min"] = None
                r["at_least"] = unknown["mac"]
                unknown["mac"] = True
            else:
                seats = seat["mac"]  # a command takes the whole lane, as the coordinator gives it
                start = max(now, max(s["end"] for s in seats))
                for s in seats:
                    s["end"], s["kind"] = start + est, "other"
                r["starts_in_min"] = round(start - now)
                r["at_least"] = unknown["mac"]
            rows.append(r)
            continue
        p = root / "specs" / f"{ln}.yaml"
        spec = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
        name = spec.get("name") or Path(ln).name
        lane = "vast" if ln.startswith("vast:") else "mac"
        r = row(name, spec.get("ship"), spec, status.get(name) or "queued", i)
        if r["status"] == "running":
            r["status"] = "at sea"
        r["spec"] = ln
        r["lane"] = lane
        r["goal_id"] = line_goals.get(ln)
        r["missing"] = not p.exists()
        r["detail"] = _spec_detail(spec)
        est, source = times.estimate(name, spec)
        r["est_min"], r["est_source"] = est, source
        if est is None:
            without_a_time += 1
            r["starts_in_min"] = None
            r["at_least"] = unknown[lane]
            unknown[lane] = True
            rows.append(r)
            continue
        seats = seat[lane]
        if r["preset"] in two:
            # only 300k shares a lane with another 300k; a 1m/9m or an unknown line ahead holds it
            if any(s["kind"] not in (None, *two) for s in seats):
                start = max(now, max(s["end"] for s in seats))
                for s in seats:
                    s["end"], s["kind"] = start, None
            s = min(seats, key=lambda x: x["end"])
            start = max(now, s["end"])
            s["end"], s["kind"] = start + est, r["preset"]
        else:
            start = max(now, max(s["end"] for s in seats))
            for s in seats:
                s["end"], s["kind"] = start + est, "other"
        r["starts_in_min"] = round(start - now)
        r["at_least"] = unknown[lane]
        rows.append(r)
    end = max((s["end"] for v in seat.values() for s in v), default=now)
    return {"rows": rows, "hours_left": round((end - now) / 60, 1), "without_a_time": without_a_time}


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


def _heads(rid: str) -> dict:
    """Every head's score on every star, at each step the voyage read them (the layer x head matrices
    the stars, nevermore and cards evaluators keep as artifacts, every eval): for tracing a card
    through the sieves to the heads that form it. The Nevermore is read on the natural passages
    (its star's metric, nevermore/natural_max_score)."""
    from thorp import fleet

    rows = []
    for kind in ("stars", "nevermore", "cards"):
        for a in _artifact_rows(rid, kind):
            if a["step"] is not None:
                rows.append((a["step"], kind, a["text"]))
    rows.sort(key=lambda x: x[0])
    steps: dict[int, dict] = {}
    for step, kind, text in rows:
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


def _finds(rid: str) -> dict:
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
    rows = [(x["step"], x["name"], x["value"]) for x in _metric_named_rows(rid, names)]
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
    def latest(name: str):
        s, v = _metric_series_gated(rid, name)
        if s:
            val, st = v[-1], s[-1]
            return (val, st) if val is not None and val == val else (None, None)
        return (None, None)

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
    fx = _finds(rid)
    heads = _heads(rid)
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


_LB: dict = {"at": 0.0, "value": None, "busy": False}


def api_leaderboard() -> dict:
    """The best of each class on the climb to chaining two facts (thorp.leaderboard.payload).

    Served from memory and refreshed in the background (10 November: the page took 20 s because the
    payload read every run's tricks one query at a time; it is one query now, but a refresh still takes
    ~2.5 s, so no request should wait for it). A cold cache computes once; after that the page always
    gets the last payload while a thread refreshes it every minute."""
    import threading
    import time

    from thorp import leaderboard

    v = _LB["value"]
    if v is not None:
        age = time.time() - _LB["at"]
        if age < 60:
            return v
        if age < 300:  # stale but usable: answer now, refresh behind the request
            if not _LB["busy"]:
                _LB["busy"] = True

                def refresh() -> None:
                    try:
                        d = leaderboard.payload()
                        _LB.update(at=time.time(), value=d)
                    finally:
                        _LB["busy"] = False
                        with contextlib.suppress(Exception):
                            from thorp.ledger import close_reader

                            close_reader()

                threading.Thread(target=refresh, daemon=True).start()
            return v
    d = leaderboard.payload()
    _LB.update(at=time.time(), value=d)
    return d


_SMOKE: dict = {"at": 0.0, "value": None}


def api_smoking_qwen() -> dict:
    """Smoking Qwen (thorp.smoking_qwen.payload): the forecast that a 400M Nothing up my sleeve chains two facts as
    well as Qwen3 4B, with the reference ladder's points (size, chaining lift) for the chart. The
    payload bootstraps, so it is kept for two minutes."""
    import time

    from thorp import smoking_qwen

    if _SMOKE["value"] is not None and time.time() - _SMOKE["at"] < 120:
        return _SMOKE["value"]
    d = smoking_qwen.payload()
    sizes = getattr(smoking_qwen, "REFERENCE_PARAMS", {})
    lb = api_leaderboard()  # one read, not two: each was a full leaderboard payload (10 November)
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
        for r in lb.get("reference", [])
        if sizes.get(r["model"])
    ]
    d["threshold"] = lb.get("threshold", 0.1)
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
    if _ledger_pg():  # the latest readings from s1.metric_latest, every run in one query (11 November, audit item 7)
        from thorp.dash import batched

        return {"threshold": getattr(st, "threshold", None), "runs": batched.bridge_rows(_runs_rows())}
    out = []
    for run in _runs_rows():
        rid = run["run_id"]
        rows = _metric_name_rows(rid, "stars/bridge/")
        if not rows:
            continue
        r = {
            "run_id": rid,
            "name": run["name"],
            "preset": json.loads(run["spec_json"] or "{}").get("model", {}).get("preset"),
            "layers": {},
        }
        for x in rows:
            key = x["name"].split("/")[-1]
            if key.startswith("layer_"):
                r["layers"][int(key[6:])] = x["value"]
            else:
                r[key] = x["value"]
            r["step"] = x["step"]
        n = max(r["layers"], default=-1) + 1
        r["curve"] = [r["layers"].get(i) for i in range(n)]
        del r["layers"]
        out.append(r)
    return {"threshold": getattr(st, "threshold", None), "runs": out}


def _entry_body(v: dict) -> dict:
    """An entry in chain-grades.json's shape (an outside model's, or a Nothing up my sleeve ship's from
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
    """A Nothing up my sleeve ship as the leaderboard names it (Nothing up my sleeve <class> v<n>), in the competitor page's shape
    (leaderboard.thorp_entry: the mean of its sailings' latest readings), with its version's history
    from s1.crownings (a version rises only when a new ship beats the last by more than
    the noise)."""
    from thorp import leaderboard

    v = leaderboard.thorp_entry(ship)
    if not v:
        raise LookupError(f"no ship {ship}")
    meta = v.get("_ship", {})
    preset = meta.get("preset")
    reg = leaderboard._versions()
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
        or (f"Nothing up my sleeve {preset} v{mine['v']}" if mine else f"Nothing up my sleeve {preset}"),
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


def api_tests(model: str) -> list[dict]:
    """The benchmark tests read on an outside model that are not the chaining tests: for now MATH-500
    (`math500-<model>` in s4.outside_readings, written by thorp.math_heads). One entry per test, with the
    score, what was graded, the breakdown by subject and level, and the heads that triggered most."""
    from thorp.viable.s4_intelligence import readings

    key = "math500-" + model.replace("/", "--")
    r = readings.get(key)
    if not r:
        return []
    return [{
        "key": "math500",
        "name": "MATH-500",
        "about": "500 competition maths problems (Hendrycks et al.), thinking on, greedy, the boxed final "
                 "answer graded; every head's attention over the answer traced for the heads panel",
        "accuracy": r.get("accuracy"),
        "correct": r.get("correct"),
        "graded": r.get("graded"),
        "n": r.get("n"),
        "truncated": r.get("truncated"),
        "tokens_cap": r.get("tokens_cap"),
        "mean_answer_tokens": r.get("mean_answer_tokens"),
        "seconds": r.get("seconds"),
        "run_at": r.get("run_at"),
        "by_subject": r.get("by_subject") or {},
        "by_level": r.get("by_level") or {},
        "heads": r.get("heads") or {},
    }]


def api_personas(model: str = "mlx-community/Qwen3-4B-4bit") -> dict:
    """The persona directions of an outside model, from the store (`s4.persona_vectors` and
    `s4.persona_master`, written by thorp.persona_vectors): per trait its direction's norm, its projection on a
    plain prompt and the cosine, plus the master list's two prompts. Falls back to the JSONB reading."""
    from thorp import persona_store

    try:
        vecs = persona_store.vectors(model)
        if vecs:
            master = {m["key"]: m for m in persona_store.master()}
            return {
                "model": model, "found": True,
                "layer": vecs[0]["layer"], "width": vecs[0]["width"],
                "traits": [v["trait_key"] for v in vecs],
                "master": master,
                "norms": {v["trait_key"]: v["norm"] for v in vecs},
                "projection_on_plain": {v["trait_key"]: v["projection"] for v in vecs},
                "cosine_on_plain": {v["trait_key"]: v["cosine"] for v in vecs},
                "vectors": {v["trait_key"]: v["vector"] for v in vecs},
                "read_at": max((v["read_at"] or "" for v in vecs), default=None),
            }
    except Exception:  # noqa: BLE001  the tables may not be migrated yet
        pass
    from thorp.viable.s4_intelligence import readings

    return readings.get("personas-" + model.replace("/", "--")) or {"model": model, "found": False}


def api_heads(model: str = "mlx-community/Qwen3-4B-4bit") -> dict:
    """The head census of an outside model (thorp/head_census.py): every head with its kind scores, its
    layer, what else names it, the kinds with no metric, and the clusters that are cards outside the
    sixteen. Empty when the census has not been run for the model."""
    from thorp.viable.s4_intelligence import readings

    key = "heads-" + model.replace("/", "--")
    d = readings.get(key)
    if not d:
        return {"model": model, "found": False, "inventory": [], "clusters": [], "kinds": {},
                "kinds_unmeasured": {}, "unnamed": [], "n_heads": 0, "n_named": 0, "n_unnamed": 0}
    keep = ("model", "layers", "heads", "n_heads", "n_named", "n_unnamed", "context", "kinds",
            "kinds_measured", "kinds_unmeasured", "cards", "clusters", "unnamed", "inventory")
    return {"found": True, "read": d.get("read"), **{k: d.get(k) for k in keep}}


def api_chat_threads() -> dict:
    """Every saved chat thread, newest first (thorp.chat_threads): the browser's store, in Postgres."""
    from thorp import chat_threads

    return {"threads": chat_threads.all_threads()}


def post_chat_thread(body: dict) -> dict:
    """Save or replace one chat thread."""
    from thorp import chat_threads

    return {"thread": chat_threads.save(body)}


def post_chat_thread_delete(body: dict) -> dict:
    """Remove one chat thread."""
    from thorp import chat_threads

    chat_threads.remove(str(body.get("id") or ""))
    return {"ok": True}


def api_chat_questions() -> dict:
    """The question library: every kept question, newest first, with its folder (thorp.chat_questions)."""
    from thorp import chat_questions

    return chat_questions.payload()


def post_chat_question(body: dict) -> dict:
    """File one question in the library, under a folder."""
    from thorp import chat_questions

    row = chat_questions.save(
        str(body.get("question") or ""),
        folder=str(body.get("folder") or "inbox"),
        model=str(body.get("model") or "") or None,
    )
    return {"question": row}


def api_foreign_control_tokens() -> dict:
    """Every read foreign ship's control tokens, for the comparison table on a foreign page."""
    from thorp import foreign

    return {"models": foreign.control_all()}


def api_chat_notes(q: dict) -> dict:
    """The notes taken in chats, newest first (thorp.chat_notes); by model or session when asked."""
    from thorp import chat_notes

    return {
        "notes": chat_notes.notes(
            model=q.get("model") or None,
            session=q.get("session") or None,
            limit=int(q.get("limit") or 100),
        )
    }


def post_chat_note(body: dict) -> dict:
    """Save one note with the model, the session and the session's whole reasoning trace."""
    from thorp import chat_notes

    note = str(body.get("note") or "").strip()
    if not note:
        raise ValueError("no note")
    row = chat_notes.save(
        note,
        session_id=str(body.get("session_id") or "") or None,
        kind=str(body.get("kind") or "") or None,
        model_key=str(body.get("model_key") or "") or None,
        model_label=str(body.get("model_label") or "") or None,
        run=str(body.get("run") or "") or None,
        thinking=str(body.get("thinking") or ""),
        conversation=body.get("conversation") or [],
    )
    return {"note": row}


def api_competitor(model: str) -> dict:
    """One outside model (a 2-4B competitor or a reference ladder model), as read on Nothing up my sleeve's tests
    (the chain grades, s4.outside_readings): the four chaining tests, the logic deck (variants, hops,
    relations), its cards (thorp's evaluator "cards": mover, comparator, bridge; previous-word and
    Nevermore not read for outside models yet), every rung of the four chains, and what Nothing up my sleeve must
    match it at (a tenth its size, with the forecast there from smoking_qwen)."""
    from thorp import fleet

    models = readings.chain_grades()
    comp = getattr(fleet, "COMPETITORS", {})
    if model not in models and model not in comp:
        # a model read in the Market Harbour but not on the chain tests (a base checkpoint, or a ship
        # read on the logic deck or hole cards): its page is the foreign ship's, not this one
        from thorp import foreign

        hit = next((m for m in foreign.models() if m["model"] == model), None)
        if hit:
            return {
                "model": model,
                "label": hit["label"],
                "params": hit["params"],
                "redirect": f"/foreign/{hit['key']}",
            }
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
        "tests": api_tests(model),
    }


def api_lab(key: str) -> dict:
    """One lab (thorp.labs): its models on Nothing up my sleeve's tests, and its five best and five worst readings,
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

    def latest(run_id: str, metric: str):
        v = _metric(run_id, metric, "last")
        return v if isinstance(v, (int, float)) and v == v else None

    def reading(run: str) -> dict:
        row = _run_row_by_name(run)
        if not row:
            return {"run": run, "status": "queued"}
        r = {"run": run, "status": row["status"] or "", "cards": {}}
        for k, st in stars.items():
            one = latest(row["run_id"], st.metric)
            two = (
                latest(row["run_id"], st.shared_metric) if getattr(st, "shared_metric", None) else None
            )
            if one is not None or two is not None:
                best = max(v for v in (one, two) if v is not None)
                r["cards"][k] = {"one": one, "shared": two, "lit": best >= st.threshold}
        r["cause"] = latest(row["run_id"], "tricks/logic_test/gain_cause")
        r["logic"] = latest(row["run_id"], "tricks/logic_test/gain")
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
    for rid in [x for x in runs.split(",") if x][:60]:
        read_here = False
        gain = None
        lift: dict[str, float] = {}
        score: dict[str, float] = {}
        steps: dict[int, None] = {}
        series = {"step": [], "climb": [], "chaining_lift": [], "logic_gain": []}
        rows = [(x["step"], x["name"], x["value"]) for x in _metric_name_rows(rid, "tricks/")]
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
    return out


def api_trick_series(key: str) -> dict:
    """One measured trick's score at every reading of every sailing, for its chart."""
    from thorp import fleet

    tr = fleet.TRICKS[key]
    out = []
    for r in _runs_rows():
        if (r["name"] or "").startswith("smoke"):
            continue
        s, v = _metric_series_gated(r["run_id"], tr.metric)
        if s:
            spec = json.loads(r["spec_json"] or "{}")
            out.append(
                {
                    "run_id": r["run_id"],
                    "name": r["name"],
                    "ship": r["ship"],
                    "preset": spec.get("model", {}).get("preset"),
                    "step": s,
                    "value": v,
                    "floor": _floor(r["run_id"], tr.metric),
                    # how the voyage was scaffolded: the heads pinned and when they were held and faded
                    "scaffold": (spec.get("optim") or {}).get("scaffold"),
                }
            )
    return {"key": key, "threshold": tr.threshold, "metric": tr.metric, "runs": out}


_DISC: dict = {"at": 0.0, "value": None, "busy": False}


def api_discoveries(runs: str = "") -> dict:
    """The stars, traits, known heads and waypoints the goals and scoring tabs read, from `s1.discoveries`.

    The document is built once (`thorp store discoveries`, or on the first read when the row is missing) and
    read back as one JSONB row, so the page no longer pays for the ~12,000 metric queries the matrix needs.
    A row older than 30 minutes is served stale while a background thread rebuilds and replaces it. A filtered
    read (`runs=`) is computed live and never stored."""
    import threading

    if runs:
        return _discoveries_compute(runs)
    from thorp import discoveries_store

    document = discoveries_store.get()
    if document is not None:
        age = discoveries_store.age()
        if age is not None and age > 1800 and not _DISC.get("busy"):
            _DISC["busy"] = True

            def refresh():
                try:
                    document = _discoveries_compute("")
                    runs = len({x["run_id"] for star in document.get("stars", []) for x in star.get("ships", [])})
                    discoveries_store.put(document, runs=runs)
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    _DISC["busy"] = False

            threading.Thread(target=refresh, daemon=True).start()
        return document
    document = _discoveries_compute("")
    try:
        runs = len({x["run_id"] for star in document.get("stars", []) for x in star.get("ships", [])})
        discoveries_store.put(document, runs=runs)
    except Exception:  # noqa: BLE001 (a store hiccup must not hide the readings)
        pass
    return document


def _discoveries_compute(runs: str = "") -> dict:
    """The two things followed across every ship: stars (heads that light, fleet.STARS) and traits
    (directions the probes find, evaluators/probes.py). For each, which ships have it and when.

    Kept for a minute: it reads every run's star timeline and trick series (~8 s warm, 20 s+ under load),
    and the goals and scoring tabs both ask for it; without a cache the second tab repeated the whole
    read and held a Postgres connection while it did (10 November)."""
    from thorp import expeditions as voyages
    from thorp import fleet
    from thorp.evaluators import probes

    wanted = {x for x in runs.split(",") if x}
    runs = _runs_rows()
    if wanted:
        runs = [r for r in runs if r.get("name") in wanted or r.get("run_id") in wanted]
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
    traits: dict[str, list] = {}
    for r in runs:
        if r["name"] and r["name"].startswith("smoke"):
            continue
        spec = json.loads(r["spec_json"] or "{}")
        series: dict[str, dict[str, dict[int, float]]] = {}
        for x in _metric_name_rows(r["run_id"], "probe/"):
            name, step, value = x["name"], x["step"], x["value"]
            if not (name.endswith("/best") or name.endswith("/floor_bow") or name.endswith("/floor_init")):
                continue
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
    # tricks (fleet.TRICKS): what a sailing can do, judged by its bets from outside, beside which
    # of the stars that perform it (performed_by) lit on that same sailing
    lit_on: dict[str, set] = {}
    for st in stars:
        for x in st["ships"]:
            if x["steps_to_lit"] is not None or x.get("shared_steps_to_lit") is not None:
                lit_on.setdefault(x["run_id"], set()).add(st["key"])
    tricks = []
    for tr in getattr(fleet, "TRICKS", {}).values():
        ships = []
        for r in runs:
            if r["name"] and r["name"].startswith("smoke"):
                continue
            s, v = _metric_series_gated(r["run_id"], tr.metric)
            if not s:
                continue
            pts = [(st, val) for st, val in zip(s, v, strict=True)]
            # the share rule (fleet.performed): a matched-pairs test is performed only where its
            # lift is at the threshold and its share of pairs right at min_score, at the same reading
            min_score = getattr(tr, "min_score", None)
            share = {}
            if min_score is not None:
                s2, v2 = _metric_series_gated(r["run_id"], tr.metric.rsplit("/", 1)[0] + "/score")
                share = dict(zip(s2, v2, strict=True))
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
                    "floor": _floor(r["run_id"], tr.metric),
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
    out = {
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
    return out


def api_stages(runs: str) -> dict:
    """Each run's training stages (artifact 'stages' at step 0: [{index, name, recipe, passes,
    first_step, last_step, tokens}]); a run without stages has an empty list (one stage, reading)."""
    out = {}
    for key in [x for x in runs.split(",") if x]:
        rid = _run_id(key)
        a = _artifact(rid, "stages") if rid else None
        try:
            out[key] = json.loads(a["text"]) if a and a["text"] else []
        except ValueError:
            out[key] = []
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


def _objective_metric(preset: str) -> tuple[str, str]:
    """The ledger metric a size's primary objective is read by: the first of its goals (s1.sizes metrics) that
    names one in brackets ("(shapes/keyed_top1)"); a size whose objective is not read during voyages yet (the
    1m's De Morgan, on the Maths page) is read by the bigram table, as the prune ranked it. (metric, its label)."""
    import re

    from thorp import ship_store

    row = next((r for r in ship_store.sizes() if r["preset"] == preset.split("-")[0]), None)
    for m in (row or {}).get("metrics") or []:
        hit = re.search(r"\(([a-z_]+/[a-z0-9_/]+)\)", m[1] if len(m) > 1 else "")
        if hit:
            return hit.group(1), m[0]
    return "shapes/keyed_top1", "the bigram table (its objective is not read during voyages yet)"


def _class_best(preset: str) -> dict:
    """The class's current best version, the one its Scoring tab talks to (Justin, 2026-11-07: "ask the
    best version of 300k questions ... which one of the 300k is the current best version"): since 8 November
    (Justin: "Yes, change it") the ship **in service** whose best voyage reads highest on the size's **primary
    objective** (`_objective_metric`, at each voyage's last reading), its voyages, and the finished voyages of
    the class to choose from instead. With no ship in service read on it, the leaderboard's pick (chaining lift)."""
    from thorp import leaderboard, ship_store

    voyages = []
    for r in _runs_rows():
        if r.get("status") != "finished":
            continue
        spec = json.loads(r.get("spec_json") or "{}")
        p = spec.get("model", {}).get("preset")
        if p == preset or (p or "").startswith(preset + "-"):
            voyages.append({"name": r["name"], "ship": r["ship"], "finished": r["finished"]})
    voyages.sort(key=lambda x: x["finished"] or "", reverse=True)
    metric, label = _objective_metric(preset)
    best = None
    row = next((r for r in ship_store.sizes() if r["preset"] == preset.split("-")[0]), {})
    try:
        if not str(row.get("role") or "").lower().startswith("primary objective"):
            raise LookupError("no primary objective set: the leaderboard's pick")
        size = ship_store.size_of(preset)
        ships = [x for x in ship_store.ships() if x.size == size and (x.status or "in service") == "in service" and not x.archived]
        for sh in ships:
            runs = [v for v in ship_store.voyages(sh.key)]
            scored = []
            for v in runs:
                value = _metric(v.run_id, metric)
                if value is not None:
                    scored.append((float(value), v.name))
            if scored:
                top = max(scored)
                if best is None or top[0] > best["value"]:
                    best = {"ship": sh, "value": top[0], "run": top[1], "runs": [v.name for v in runs]}
    except Exception:  # noqa: BLE001  (no ship store: the leaderboard's pick, as before)
        best = None
    if best is not None:
        sh = best["ship"]
        return {
            "best": {
                "name": sh.name, "version": None, "ship": sh.name, "ship_key": sh.key, "run": best["run"],
                "runs": best["runs"], "sailings": len(best["runs"]), "chaining_lift": None,
                "objective": {"metric": metric, "label": label, "value": round(best["value"], 4)},
                "why": f"the ship in service that reads highest on this size's primary objective, {label} ({metric}), at its voyages' last readings",
            },
            "voyages": voyages,
        }  # fmt: skip
    best = next(
        (
            b["best"]
            for b in leaderboard.payload().get("board", [])
            if b.get("best") and b["best"].get("preset") == preset
        ),
        None,
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
    return _tag_guesses(out)


_GUESS_LEXICON: dict | None = None


def _guess_tag(word: str, lex: dict) -> str:
    """A guess's part of speech, as the shapes evaluator tags a guess's piece: a line break is BREAK, a word its
    commonest tag in the Ogden corpus (the lexicon), a mark with no letter or figure PUNCT, else OTHER."""
    if "\n" in word or "\u23ce" in word:  # a line break, as the guesses write it (⏎) or raw
        return "BREAK"
    w = word.strip().split(" ")[0].lower() if word.strip() else ""
    return lex.get(w) or ("PUNCT" if w and not any(ch.isalnum() for ch in w) else "OTHER")


def _tag_guesses(out: dict) -> dict:
    """Each guess with its part of speech, and what the ship is looking for: its guesses' probability summed by
    tag, in the fine tier (NOUN, VERB, ADJ...) and Ogden's coarse one (THING, QUALITY, OPERATION, MARK) (Justin,
    8 November: "the 300k is to also identify parts of speech in its guesses so that we can map its guesses to
    what it thinks the correct parts of speech it's looking for"). The lexicon and the rule are the shapes
    evaluator's, so the page and the voyages' readings agree."""
    global _GUESS_LEXICON
    from thorp.viable.s5_policy import taxonomy

    if _GUESS_LEXICON is None:
        try:
            from thorp.evaluators.shapes import LEXICON
            from thorp.viable.s2_coordination import tagger

            _GUESS_LEXICON = tagger.lexicon(LEXICON)
        except Exception:  # noqa: BLE001  (no lexicon built here: the guesses go untagged)
            _GUESS_LEXICON = {}
    if not _GUESS_LEXICON:
        return out
    fine: dict[str, float] = {}
    for g in out.get("guesses") or []:
        g["tag"] = _guess_tag(str(g.get("word") or ""), _GUESS_LEXICON)
        g["coarse"] = taxonomy.coarse(g["tag"])
        fine[g["tag"]] = fine.get(g["tag"], 0.0) + float(g.get("p") or 0.0)
    total = sum(fine.values()) or 1.0
    coarse: dict[str, float] = {}
    for t, v in fine.items():
        coarse[taxonomy.coarse(t)] = coarse.get(taxonomy.coarse(t), 0.0) + v
    out["looking_for"] = [{"tag": t, "share": round(v / total, 3), "about": taxonomy.ABOUT.get(t, "")}
                          for t, v in sorted(fine.items(), key=lambda kv: -kv[1])]  # fmt: skip
    out["looking_for_coarse"] = [{"tag": t, "share": round(v / total, 3)} for t, v in sorted(coarse.items(), key=lambda kv: -kv[1])]
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


def _preset_of(preset: str) -> str:
    """The size's canonical preset, from a preset, a variant ('300k-l3') or a class slug ('pan').

    The URL's canonical identifier is the size (10 November, Justin: "keep the ship size the canonical URL
    identifier"), but old links and the ship's own class name still name the rung; resolve them here so an
    endpoint called with either answers the same voyage."""
    import re

    from thorp.models.registry import LADDER

    base = preset.split("-")[0]
    if any(r["preset"] == base for r in LADDER):
        return preset
    slug = re.sub(r"[^a-z0-9]+", "-", preset.lower().removeprefix("the ")).strip("-")
    row = next(
        (r for r in LADDER if re.sub(r"[^a-z0-9]+", "-", r["name"].lower().removeprefix("the ")).strip("-") == slug),
        None,
    )
    return row["preset"] if row else preset


def _slug(preset: str) -> str:
    from thorp.models.registry import LADDER

    row = next((r for r in LADDER if r["preset"] == preset.split("-")[0]), None)
    return (row["name"].lower().removeprefix("the ").strip() if row else preset)


def _class_voyages(preset: str, limit: int = 12) -> list[dict]:
    """The class's voyages to read: Ogden's first (its fitout is the one that sails), then the latest others."""
    cls = preset.split("-")[0]
    rows = []
    for r in reversed(_runs_rows()):  # newest first, as `order by started desc`
        if r.get("status") not in ("finished", "running"):
            continue
        spec = json.loads(r.get("spec_json") or "{}")
        rows.append(
            {
                "run_id": r["run_id"], "name": r["name"], "status": r["status"], "started": r["started"],
                "p": spec.get("model", {}).get("preset"),
                "bt": (spec.get("optim") or {}).get("batch_tokens"),
            }
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
    names = _class_names(preset)
    voyages = _class_voyages(preset)

    def last(rid, name):
        s, v = _metric_series_gated(rid, name)
        return (v[-1], s[-1]) if s else (None, None)

    def series(rid, name, bt):
        s, v = _metric_series_gated(rid, name)
        return [[st * (bt or 32768), val] for st, val in zip(s, v, strict=True) if val is not None]

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
                    "series": series(v["run_id"], tr.metric, v["bt"]) if tr.goal_class in names and val is not None else None,
                })  # fmt: skip
            rows.append({
                "key": k, "name": tr.name, "about": tr.about, "goal_class": tr.goal_class,
                "mine": tr.goal_class in names, "metric": tr.metric, "threshold": tr.threshold, "readings": readings,
            })  # fmt: skip
        out[key] = {"title": title, "about": about, "tests": rows}
    return {"preset": preset, "class": slug, "voyages": [v["name"] for v in voyages], "subjects": out}


VS_REFERENCE = "Qwen/Qwen3-0.6B"
VS_CARDS = (  # (key, name, our metric (and a fallback), the reference's card field, about)
    ("previous_word", "Previous-word (two heads of a layer)", ("stars/previous_word/shared_score", "stars/previous_word/max_score"), ("previous_word", "shared"), "attends to the word before"),
    ("induction", "Induction (two heads of a layer)", ("nevermore/natural_shared_score", "nevermore/natural_max_score"), ("nevermore", "shared"), "attends to what followed this word last time"),
    ("copy_gain", "Copying: the Nevermore's copy gain", ("nevermore/natural_copy_gain",), ("nevermore", "copy_gain"), "how much easier a repeated passage is the second time, nats a token"),
    ("comparator", "The comparator (two heads)", ("stars/comparator/shared_score", "stars/comparator/max_score"), ("comparator", "shared"), "attends to the year to beat rather than a decoy"),
    ("mover", "The mover (two heads)", ("stars/mover/shared_score", "stars/mover/max_score"), ("mover", "shared"), "carries the premise's answer to the conclusion"),
)  # fmt: skip
VS_LOGIC = (
    ("lift_one_hop", "Logic: one-hop lift", "one fact carried to a question (nats over the floor)"),
    ("lift_both", "Logic: both premises given", "lift with both premises in front of the question"),
    ("gain", "Logic: chaining gain", "both premises over the better one alone: putting two facts together"),
    ("lift_first", "Logic: the first premise alone", "lift from the first premise"),
    ("lift_second", "Logic: the second premise alone", "lift from the second premise"),
)  # fmt: skip
VS_LIFT_FLOOR = 0.1  # a logic lift is ranked only when the reference's reaches it: below, a ratio is noise over noise
VS_DECK = (  # the other cards, read on an outside model by thorp/outside_deck.py (s4.outside_readings, deck-<model>)
    ("sink", "The sink", "stars/attention_sink/max_score", True, "parks attention on the first piece"),
    ("delimiter", "The delimiter", "stars/delimiter/max_score", False, "attends to punctuation and breaks"),
    ("words_back", "Words back (two heads)", "stars/offset_2/shared_score", True, "attends two pieces back"),
    ("duplicate_word", "Duplicate-word (two heads)", "stars/duplicate_word/shared_score", True, "attends to an earlier copy"),
    ("rare_word", "The rare word", "stars/rare_word/max_score", True, "attention follows rarity"),
    ("number_spotter", "Number-spotter", "stars/number_spotter/max_score", False, "attends to numbers"),
    ("order_word", "Order-word", "stars/order_word/max_score", False, "attends to more, less, before, after"),
    ("premise_marker", "Premise-marker", "stars/premise_marker/max_score", False, "attends to if, because, so"),
    ("counter", "The counter (R²)", "counter/probe_r2", True, "knows how far into the sentence it is"),
    ("bridge", "The bridge (nats)", "stars/bridge/max_score", True, "the middle term at the conclusion"),
)  # fmt: skip
# (a class card's reading is a ratio over its share of the keys: a pinned head's runs to the hundreds, so it is shown, not ranked)
VS_PAIRS = 24  # the matched pairs in a trick test: one pair is 1/24 of the score


def _vs_references() -> dict[str, dict]:
    """The reference models on file: chain-grades.json (trick tests, the logic deck, cards) with the judge-book
    bits per byte from s4.outside_readings <model>__hole-cards-unseen where it was scored."""
    models = readings.chain_grades()
    from thorp import cleaning

    bpb, cleaned = {}, {}
    for _, d in readings.glob("*__hole-cards-unseen*"):
        short = d["model"].split("/")[-1].removesuffix("-bf16").removesuffix("-4bit").lower()
        if d.get("clean", "raw") == cleaning.CURRENT:  # scored on the text the voyages read: preferred
            cleaned[short] = d.get("bpb_mean")
        elif d.get("clean", "raw") == "raw":
            bpb[short] = d.get("bpb_mean")
    bpb.update(cleaned)
    out = {}
    for name, m in models.items():
        if "/" not in name:  # Nothing up my sleeve's own voyages graded alongside
            continue
        short = name.split("/")[-1].removesuffix("-bf16").removesuffix("-4bit").lower()
        out[name] = {**m, "bpb": bpb.get(short), "bpb_clean": short in cleaned,
                     "deck": readings.get(f"deck-{name.replace('/', '--')}")}  # fmt: skip
    return out


def api_class_vs(preset: str, ref: str | None = None, voyage: str | None = None, runs: str = "") -> dict:
    """The class's voyage against a reference model (Justin, 23:50: "the top 5 ways we're further away and the top
    5 ways we're closer"), on every reading both have: the 20 trick tests (pairs right of 24; chance 12), the logic
    deck's lifts, the cards (attention readings, two heads of a layer together) and copy gain, and judge-book bits
    per byte. Each reading is put as a share of the reference's level, so they can be ranked together: for a trick
    test, pairs right above chance over the reference's (not ranked when the reference is within two pairs of
    chance); for a lift or a card, ours over theirs; for bits per byte, theirs over ours. A difference of two pairs
    or less in a trick test is within its noise."""
    from thorp import fleet

    refs = _vs_references()
    ref = ref if ref in refs else (VS_REFERENCE if VS_REFERENCE in refs else next(iter(refs), None))
    voyages = [v for v in _class_voyages(preset, 20)]
    wanted = [x for x in runs.split(",") if x]
    if wanted:
        voyages = [v for v in voyages if v.get("name") in wanted or v.get("run_id") in wanted]
    def last(rid, name):
        s, v = _metric_series_gated(rid, name)
        return (v[-1], s[-1]) if s else (None, None)

    readable = [v for v in voyages if last(v["run_id"], "tricks/refrain_test/score")[0] is not None]
    v = next((x for x in readable if x["name"] == voyage), None) or next(
        (x for x in readable if x["status"] == "running"), None) or (readable[0] if readable else None)  # fmt: skip
    if v is None or ref is None:
        return {"preset": preset, "ref": ref, "refs": list(refs), "voyage": None, "voyages": [x["name"] for x in readable], "rows": []}
    rid = v["run_id"]
    R = refs[ref]
    rows = []

    def add(key, group, name, about, mine, theirs, share, unit, step, note=None, noise=False, whose=None):
        rows.append({"key": key, "group": group, "name": name, "about": about, "mine": mine, "ref": theirs,
                     "share": share, "unit": unit, "step": step, "note": note, "noise": noise, "whose": whose})  # fmt: skip

    for k, t in R.items():
        if not k.endswith("_test") or k == "logic_test" or not isinstance(t, dict):
            continue
        tr = fleet.TRICKS.get(k)
        sc, step = last(rid, f"tricks/{k}/score")
        lf, _ = last(rid, f"tricks/{k}/lift")
        if sc is None:
            continue
        mp, rp = round(sc * VS_PAIRS), round(t["score"] * VS_PAIRS)
        above = rp - VS_PAIRS / 2
        share = (mp - VS_PAIRS / 2) / above if above > 2 else None
        add(k, "trick test", tr.name if tr else k, (tr.about[:180] if tr else ""), mp, rp, share, "pairs of 24", step,
            note=f"lift {lf:+.2f} against {t['lift']:+.2f}" if lf is not None else None, noise=abs(mp - rp) <= 2,
            whose=tr.goal_class if tr else None)  # fmt: skip
    lt = R.get("logic_test") or {}
    for k, name, about in VS_LOGIC:
        mine, step = last(rid, f"tricks/logic_test/{k}")
        theirs = lt.get(k)
        if mine is None or theirs is None:
            continue
        ranked = theirs >= VS_LIFT_FLOOR
        add(f"logic/{k}", "logic deck", name, about, mine, theirs, mine / theirs if ranked else None, "nats", step,
            noise=abs(mine - theirs) < 0.05, note=None if ranked else f"the reference reads under {VS_LIFT_FLOOR}: not ranked")  # fmt: skip
    cards = R.get("cards") or {}
    for k, name, metrics, (card, field), about in VS_CARDS:
        theirs = (cards.get(card) or {}).get(field)
        mine, step, used = None, None, None
        for m in metrics:
            mine, step = last(rid, m)
            if mine is not None:
                used = m
                break
        if mine is None or theirs is None:
            continue
        note = "one head: the two-head reading is not on the ledger for this voyage yet" if used != metrics[0] else None
        add(f"card/{k}", "card", name, about, mine, theirs, mine / theirs if theirs > 0 else None,
            "nats a token" if k == "copy_gain" else "attention", step, note=note)  # fmt: skip
    dk = R.get("deck") or {}
    for k, name, metric, ranked, about in VS_DECK:
        theirs = (dk.get("metrics") or {}).get(metric)
        mine, step = last(rid, metric)
        if theirs is None or mine is None or any(x["key"] == f"card/{k}" for x in rows):
            continue
        add(f"card/{k}", "card", name, about, mine, theirs, mine / theirs if ranked and theirs > 0 else None,
            "attention", step, note=None if ranked else "a class card's ratio: shown, not ranked")  # fmt: skip
    if dk.get("played") is not None:
        from thorp.viable.s4_intelligence import wager

        ours = [c for c, v in wager.falls(rid, int(v.get("bt") or 32768)).items() if v["played"]]
        add("deck/played", "card", "Cards played (the deck's rules, of 16)", "every card whose look (and ability) "
            "passes, above what it sits on", len(ours), len(dk["played"]), len(ours) / max(1, len(dk["played"])),
            "cards", None, note=f"ours: {', '.join(sorted(ours))}; theirs: {', '.join(dk['played'])}")  # fmt: skip
    mine, step = last(rid, "eval/hole-cards-unseen/bpb_mean")
    if mine is not None and R.get("bpb"):
        add("bpb", "language", "Judge-book bits per byte (lower is better)", "the 16 Forgotten Tomes, every byte",
            mine, R["bpb"], R["bpb"] / mine, "bits a byte", step,
            note=None if R.get("bpb_clean") else "the reference was scored on raw text; ours reads the cleaned text")  # fmt: skip
    tot = last(rid, "plan/total_steps")[0]
    ranked = [r for r in rows if r["share"] is not None]
    ranked.sort(key=lambda r: r["share"])
    return {
        "preset": preset, "ref": ref, "refs": list(refs), "voyage": v["name"], "status": v["status"],
        "step": max((r["step"] or 0) for r in rows) if rows else None, "total_steps": tot,
        "voyages": [x["name"] for x in readable], "rows": rows,
        "closer": [r["key"] for r in ranked[::-1][:5]], "further": [r["key"] for r in ranked[:5]],
    }  # fmt: skip


LOGIC_RELATIONS = ("order", "cause", "membership", "proportion", "counterfactual")
LOGIC_ABOUT = {
    "order": "two comparisons chained into a third (the Scales' ability)",
    "cause": "a chain of events: the first causes the second, the second the third",
    "membership": "all A are B, all B have C, so every A has C",
    "proportion": "twice of twice is four times, against a wrong product the premises never name",
    "counterfactual": "premises that run against the world (fire that cools water), read as stated",
}


def _logic_bands(items: dict, n_boot: int = 500) -> dict:
    """Each relation's chaining gain (both premises less the stronger single premise, from the relation's means) with
    a 90% bootstrap band over its items, the overall gain (their mean), and the one-hop lift."""
    import numpy as np

    by: dict[str, list[str]] = {}
    for k in items:
        by.setdefault(k.rsplit("-", 1)[0], []).append(k)
    rng = np.random.default_rng(0)

    def gain(ks):
        both = np.mean([items[k]["both"] for k in ks])
        return float(both - max(np.mean([items[k]["first"] for k in ks]), np.mean([items[k]["second"] for k in ks])))

    out = {}
    for rel in LOGIC_RELATIONS:
        ks = sorted(by.get(rel, []))
        if not ks:
            continue
        boots = [gain([ks[i] for i in rng.integers(0, len(ks), len(ks))]) for _ in range(n_boot)]
        lo, hi = np.percentile(boots, [5, 95])
        right = sum(1 for k in ks if items[k]["both"] > 0 and items[k]["both"] > max(items[k]["first"], items[k]["second"]))
        out[rel] = {"gain": gain(ks), "lo": float(lo), "hi": float(hi), "items": len(ks), "chained": right}
    if out:
        out["overall"] = {"gain": float(np.mean([v["gain"] for v in out.values()]))}
    hop = [items[k]["one_hop"] for k in items if "one_hop" in items[k]]
    if hop:
        out["one_hop"] = {"gain": float(np.mean(hop))}
    return out


LOGIC_DETAIL = {  # each relation of the logic deck, at length (Justin, 2026-11-08 13:10: "a detail page explaining each of those
    # relation tiles in much more detail"); the build is backend/scripts/make_logic_deck.py
    "order": {
        "title": "Order: two comparisons chained into a third",
        "asks": "Every A is heavier than every B; every C is lighter than every B; so is an A heavier or lighter than a C? "
        "Nothing about A or C is said together: the answer exists only by going through B, the middle term.",
        "steps": ["find the two names in the question (A, C) among the premises",
                  "find the term they share (B): the Bridge",
                  "read each premise's direction (heavier, lighter) relative to B",
                  "compose the two directions (A above B, B above C, so A above C) and say it"],
        "built": "Six invented words an item, none English. Both answers (heavier than a C, lighter than a C) are named in "
        "the premises, so copying a phrase cannot decide; half the items ask from the low end, so a model that always says "
        "the first comparative is right half the time. The padded variant adds a second chain whose middle term is named "
        "twice and last, so recency and repetition favour the wrong middle term; three_hop adds a fourth term.",
        "cards": [("comparator", "picks the side to compare against rather than a decoy"),
                  ("order_word", "finds the direction words (heavier, lighter, before, after)"),
                  ("bridge", "holds the middle term B at the question"),
                  ("mover", "carries the answer's direction from the premise to the question"),
                  ("scales", "the Face whose ability this relation's gain is: order composed")],
        "hard": "Every model read so far, Qwen3 4B included, is near zero or below on it: composing two directions is the "
        "hardest of the five. A negative gain means the second premise confuses the model more than it helps.",
    },
    "cause": {
        "title": "Cause: a chain of events",
        "asks": "When the A is struck, the B rises; when the B rises, the C glows (and when it falls, the C darkens); so when "
        "the A is struck, does the C glow or darken? The answer runs through the middle event, B rising.",
        "steps": ["find the first event (A struck) in the question",
                  "follow it to its effect (B rises): the Bridge",
                  "find the branch of the second premise that starts from that effect (B rises, not B falls)",
                  "carry that branch's outcome (glows) to the answer"],
        "built": "Both branches of the second premise are given (rises and falls, glows and darkens), so the answer word and "
        "its rival both appear; half the items name the answer's clause last. The padded variant adds a second cause chain "
        "with its own middle term; three_hop adds a fourth event.",
        "cards": [("premise_marker", "finds where each premise starts and ends (When ..., so when ...)"),
                  ("bridge", "holds the middle event at the question"),
                  ("mover", "carries the right branch's outcome to the answer"),
                  ("induction", "the frame repeats the premise's opening, so the copying circuit points back to it")],
        "hard": "This is the relation Qwen3 4B chains: +0.94 on the 8-item deck, where every other relation is near zero. "
        "Its knockout will show which cards that rests on.",
    },
    "membership": {
        "title": "Membership: all A are B, all B have C",
        "asks": "All A are Bs; all Bs have wings (and all Ds have fins); so does every A have wings or fins? The answer is "
        "inherited through the group, B.",
        "steps": ["find the A in the question", "find the group it belongs to (B): the Bridge",
                  "find what that group has (wings, not the other group's fins)", "carry it to the answer"],
        "built": "A contrast group with the other feature is always named, so both features are in the premises; half the "
        "items swap which feature is the answer. The padded variant adds a second inclusion chain.",
        "cards": [("bridge", "holds the group B at the question"),
                  ("duplicate_word", "links the B in the first premise to the B in the second"),
                  ("rare_word", "picks out the invented names worth carrying"),
                  ("mover", "carries the feature to the answer")],
        "hard": "Qwen3 4B is below zero on it (-0.09; Phi-4-mini -0.48): the contrast group's feature, named last in "
        "many items, pulls larger models the wrong way.",
    },
    "proportion": {
        "title": "Proportion: twice of twice is four times",
        "asks": "Each A weighs twice as much as a B; each B weighs twice as much as a C; so an A weighs four times as much "
        "as a C, against a neighbouring wrong product (three times) that the premises never name.",
        "steps": ["find A and C in the question", "find the middle term B: the Bridge",
                  "read the two factors (twice, twice)", "multiply them (four times) and say the product"],
        "built": "The rival is the nearest wrong product, never named in the premises, so neither copying nor recency can "
        "pick either answer: only multiplying can. The padded variant adds a chain whose second link is 'as much as'.",
        "cards": [("number_spotter", "finds the factors (twice, three times)"),
                  ("bridge", "holds the middle term at the question"),
                  ("mover", "carries the factors to where the product is said")],
        "hard": "The deck has no card for arithmetic itself: a model that holds every card here can still fail to multiply. "
        "Qwen3 4B reads about zero on it.",
    },
    "counterfactual": {
        "title": "Counterfactual: premises against the world",
        "asks": "In the valley of Nilkol, fire makes the water of its ponds colder; in Nilkol, cold water stops the mill "
        "wheels, while warm water turns them; so in Nilkol, when a fire is lit, does the mill wheel stop or turn? The "
        "world says turn; the premises say stop.",
        "steps": ["take the first premise as stated, against what is known (fire cools here)",
                  "follow its result (colder water) into the second premise",
                  "carry the stated outcome (stop), not the remembered one (turn)"],
        "built": "Eight items written by hand, each a pair of facts run against the world; odd items name the answer's "
        "clause last. No padded or one-hop variant: the test is whether the stated premises beat knowledge.",
        "cards": [("mover", "carries the stated premise's outcome to the answer"),
                  ("premise_marker", "marks the premises as the context to answer from")],
        "hard": "Never taught by the logic tutor (held out as transfer). The deck has no card for preferring the text to "
        "memory: this relation tests something no card reads.",
    },
}
VS_KNOCKOUT = "mlx-community/Qwen3-4B-4bit"
VARIANT_ABOUT = {
    "both": "the two premises, then the question: the two-hop item",
    "first": "the first premise only, the other replaced by a neutral sentence",
    "second": "the second premise only",
    "swapped": "the premises in the other order",
    "padded": "an irrelevant third premise naming its own middle term twice, last: the Bridge's distractor",
    "one_hop": "the conclusion's link stated directly: the floor",
    "three_hop": "three premises chained: the ceiling",
}


def api_logic_relation(preset: str, relation: str) -> dict:
    """One relation of the logic deck at a class, at length: what it asks, the steps it takes, how it is built, an item
    in every variant, the cards it should need (and, once read, what silencing them in Qwen3 4B did to it), the class's
    voyages and the reference models on it with bands, and the class's voyages item by item."""
    import csv

    if relation not in LOGIC_DETAIL:
        raise KeyError(relation)
    rows = [r for r in csv.DictReader(paths.resolve("lists/tricks/logic-40.csv").open()) if r["relation"] == relation]
    first = rows[0]["item"] if rows else None
    item = [{"variant": r["variant"], "about": VARIANT_ABOUT.get(r["variant"], ""), "prompt": r["prompt"],
             "idea": r["idea"], "rival": r["rival"], "bridge": r["bridge"], "distractor": r["distractor"]}
            for r in rows if r["item"] == first]  # fmt: skip
    examples = [{"prompt": r["prompt"], "idea": r["idea"], "rival": r["rival"]} for r in rows if r["variant"] == "both"][1:4]
    # every item (Justin, 13:20: "where are those other 40 ... I'd like to see them in the UI"): its question as asked
    # with both premises, its answer and rival, and how each reader that read the 40-item deck did on it
    all_items = [{"item": r["item"], "prompt": r["prompt"], "idea": r["idea"], "rival": r["rival"], "bridge": r["bridge"],
                  "distractor": r["distractor"], "results": {}}
                 for r in rows if r["variant"] == "both"]  # fmt: skip
    by_item = {x["item"]: x for x in all_items}

    def mark_results(label: str, items40: dict) -> None:
        for k, x in items40.items():
            if k in by_item:
                by_item[k]["results"][label] = {"both": x.get("both"), "first": x.get("first"), "second": x.get("second"),
                                                "chained": bool(x["both"] > 0 and x["both"] > max(x["first"], x["second"]))}  # fmt: skip

    readers: list[str] = []
    for _, d40 in readings.glob("logic-*"):
        if d40.get("items40"):
            label = d40["model"].split("/")[-1].removesuffix("-bf16").removesuffix("-4bit")
            mark_results(label, d40["items40"])
            readers.append(label)
    full = api_class_logic(preset)
    voyages = [{"voyage": v["voyage"], "deck": v["deck"], "gain": v["gains"].get(relation)} for v in full["voyages"]]
    refs = [{"model": x["model"], "deck": x["deck"], "params": x["params"], "gain": x["gains"].get(relation)} for x in full["references"]]
    from thorp.viable.s5_policy import deck as D

    det = LOGIC_DETAIL[relation]
    cards = [{"key": k, "name": D.BY_KEY[k].name if k in D.BY_KEY else k, "why": why,
              "suit": D.BY_KEY[k].constellation if k in D.BY_KEY else ""} for k, why in det["cards"]]  # fmt: skip
    knock = None
    d = readings.get(f"knockout-deck-{VS_KNOCKOUT.replace('/', '--')}")  # the bar's knockout only
    if d is not None:
        knock = {"model": d["model"], "baseline": d["baseline"].get(relation),
                 "drops": sorted(({"condition": c, "drop": v["relation_drops"].get(relation)} for c, v in d["conditions"].items()
                                  if v.get("relation_drops", {}).get(relation) is not None), key=lambda x: -x["drop"])}  # fmt: skip
    per = []
    for v in _class_voyages(preset):
        for kind in ("logic40", "logic"):
            a = _artifact(v["run_id"], kind)
            if a and a["text"]:
                items = {k: x for k, x in json.loads(a["text"]).items() if k.startswith(relation + "-")}
                if kind == "logic40":
                    label = v["name"].replace("fu-ogden-v0-1", "Ogden").replace("fu-ogden-v0-2", "Ogden v0.2").replace("-pre", "")
                    mark_results(label, items)
                    readers.insert(0, label)
                per.append({"voyage": v["name"], "deck": "40" if kind == "logic40" else "8", "step": a["step"],
                            "items": [{"item": k, **{a: x.get(a) for a in ("both", "first", "second", "one_hop")},
                                       "chained": bool(x["both"] > 0 and x["both"] > max(x["first"], x["second"]))}
                                      for k, x in sorted(items.items(), key=lambda kv: int(kv[0].rsplit("-", 1)[1]))]})  # fmt: skip
                break
    return {"preset": preset, "relation": relation, **{k: det[k] for k in ("title", "asks", "steps", "built", "hard")},
            "items": len({r["item"] for r in rows}), "item": item, "examples": examples, "cards": cards, "knockout": knock,
            "voyages": voyages, "references": refs, "per_item": per, "mark": full["mark"], "bar": full["bar"],
            "all_items": all_items, "readers": readers,
            "relations": full["relations"]}  # fmt: skip


_logic_cache: dict[str, tuple[float, dict]] = {}


def api_class_logic(preset: str) -> dict:
    """Cached two minutes (its bands are bootstrapped over every reference model's items)."""
    import time

    hit = _logic_cache.get(preset)
    if hit and time.time() - hit[0] < 120:
        return hit[1]
    out = _class_logic(preset)
    _logic_cache[preset] = (time.time(), out)
    return out


def _class_logic(preset: str) -> dict:
    """The logic deck at a class (Justin, 2026-11-08 13:00: "each page ... needs to be able to select which deck to
    view ... the original deck of 16, but I want to see the new deck in this page too"): the 40-item logic deck, its
    five relations with an example each; the class's voyages' chaining gain on each relation with bands (the 40-item
    deck where a voyage has read it, else the 8-item deck, said which); and the reference models' (Qwen3 4B the bar)."""
    import csv

    deck_rows = list(csv.DictReader(paths.resolve("lists/tricks/logic-40.csv").open()))
    deck = []
    for rel in LOGIC_RELATIONS:
        rows = [r for r in deck_rows if r["relation"] == rel]
        ex = next((r for r in rows if r["variant"] == "both"), None)
        deck.append({"relation": rel, "about": LOGIC_ABOUT[rel], "items": len({r["item"] for r in rows}),
                     "example": ex and {"prompt": ex["prompt"], "idea": ex["idea"], "rival": ex["rival"]}})  # fmt: skip
    def art(rid, kind):
        a = _artifact(rid, kind)
        return (a["step"], json.loads(a["text"])) if a and a["text"] else (None, None)

    voyages = []
    for v in _class_voyages(preset):
        step, items = art(v["run_id"], "logic40")
        which = "40"
        if items is None:
            step, items = art(v["run_id"], "logic")
            which = "8"
        if items is None:
            continue
        voyages.append({"voyage": v["name"], "status": v["status"], "step": step, "deck": which, "gains": _logic_bands(items)})
    refs = []
    graded = readings.chain_grades()
    for _, d in readings.glob("logic-*"):
        if d.get("items40"):
            refs.append({"model": d["model"], "deck": "40", "gains": _logic_bands(d["items40"])})
    have = {x["model"] for x in refs}
    from thorp import smoking_qwen as sq

    for name, e in graded.items():
        it = (e.get("logic_test") or {}).get("items")
        if "/" in name and it and name not in have:
            refs.append({"model": name, "deck": "8", "gains": _logic_bands(it)})
    size = {**sq.REFERENCE_PARAMS}
    for x in refs:
        x["params"] = size.get(x["model"])
    refs.sort(key=lambda x: x["params"] or 0)
    return {"preset": preset, "deck": deck, "relations": list(LOGIC_RELATIONS), "mark": 0.1,
            "voyages": voyages, "references": refs, "bar": "mlx-community/Qwen3-4B-4bit"}  # fmt: skip


def api_class_shapes(preset: str) -> dict:
    """The shapes readings (the parts-of-speech taxonomy) for the class's voyages that carry them: each
    accuracy as a series over tokens read, and the latest share of probability on each kind of word."""
    from thorp.viable.s5_policy import taxonomy

    out = []
    for v in _class_voyages(preset):
        rid, bt = v["run_id"], v["bt"] or 32768
        got = {}
        for m in ("shapes/upos_top1", "shapes/ogden_top1", "shapes/keyed_top1"):
            s, vals = _metric_series_gated(rid, m)
            got[m] = [[st * bt, val] for st, val in zip(s, vals, strict=True) if val is not None]
        if not got["shapes/upos_top1"]:
            continue
        last_step = got["shapes/upos_top1"][-1][0] // bt
        mass = {t: _metric_at_step(rid, f"shapes/mass/{t}", last_step) for t in taxonomy.FINE}
        truth = {t: _metric_at_step(rid, f"shapes/truth/{t}", last_step) for t in taxonomy.FINE}
        out.append({
            "voyage": v["name"], "status": v["status"], "series": got,
            "mass": mass, "truth": truth,
        })  # fmt: skip
    return {"preset": preset, "fine": list(taxonomy.FINE), "about": taxonomy.ABOUT, "voyages": out}


def api_chat_models() -> dict:
    """The chat page's list: Nothing up my sleeve's ships on the leaderboard, each resolved to a
    finished run with a checkpoint, and the foreign ships whose MLX weights are cached. Read from
    the same cached leaderboard payload as the board."""
    from thorp import chat

    return {"models": chat.models(api_leaderboard()) + chat.talking_models() + chat.foreign_models()}


def api_chat(q: dict) -> dict:
    """One experimental answer: from a finished Thorp run's latest checkpoint (the `run`), or from a
    foreign ship's own MLX weights (the `model`). The Thorp model loads once per run (thorp.chat
    caches it) and the reply carries the audit; a foreign answer is the model's own continuation and
    has no audit. A run/model with no checkpoint or weights says so in `error`."""
    from thorp import chat

    run = str(q.get("run") or "")
    model = str(q.get("model") or "")
    text = q.get("q", "")
    if not run and not model:
        return {"error": "no run or model", "run": run, "model": model}
    if not str(text).strip():
        return {"error": "no question", "run": run, "model": model}
    try:
        if model:
            return chat.foreign_answer(model, str(text), **_chat_foreign_args(q))
        return _chat_own_answer(run, str(text), q)
    except Exception as e:  # noqa: BLE001  the page shows the reason (no checkpoint, no run)
        return {"error": str(e), "run": run, "model": model}


def _chat_tokens(q: dict) -> tuple[int, float]:
    tokens = max(1, min(int(q.get("tokens", 512)), 1 << 20))  # the console sends a share of the model's window
    return tokens, max(0.0, min(float(q.get("temperature", 0.7)), 2.0))


def _chat_foreign_args(q: dict) -> dict:
    """A foreign ship's settings from the request. The thinking has its own cap (`think_tokens`): not
    sent, it is the whole budget, which thorp.chat.think_cap holds to half so an answer has room; 0
    is no cap."""
    tokens, temperature = _chat_tokens(q)
    raw_thinking = q.get("thinking")
    thinking = None if raw_thinking is None else str(raw_thinking).strip().lower() not in ("0", "false", "off", "no", "")
    raw_cap = q.get("think_tokens")
    think_tokens = tokens if raw_cap in (None, "") else max(0, int(raw_cap))
    return {
        "tokens": tokens,
        "temperature": temperature,
        "thinking": thinking,
        "history": q.get("history") or [],
        "think_tokens": think_tokens or None,
    }


def _chat_own_answer(run: str, text: str, q: dict) -> dict:
    from thorp import chat

    tokens, temperature = _chat_tokens(q)
    step = q.get("step")
    return chat.answer(
        run,
        text,
        tokens=tokens,
        temperature=temperature,
        step=int(step) if step not in (None, "", 0, "0") else None,
        with_audit=str(q.get("audit", "1")) not in ("0", "false", "no"),
        history=q.get("history") or [],  # the thread so far, asked as the voyage's turns (12 November)
    )


def api_chat_stream(q: dict):
    """The same answer as api_chat, as it is written: a generator of events, each sent as one line of
    JSON (POST /api/chat/stream). A foreign ship's are thorp.chat.foreign_stream's (start, delta,
    done); a Thorp run answers whole, so its one event is `done`. A failure is an `error` event."""
    from thorp import chat

    run = str(q.get("run") or "")
    model = str(q.get("model") or "")
    text = q.get("q", "")
    if not run and not model:
        yield {"event": "error", "error": "no run or model", "run": run, "model": model}
        return
    if not str(text).strip():
        yield {"event": "error", "error": "no question", "run": run, "model": model}
        return
    try:
        if model:
            yield from chat.foreign_stream(model, str(text), **_chat_foreign_args(q))
        else:
            yield {"event": "done", "reply": _chat_own_answer(run, str(text), q)}
    except Exception as e:  # noqa: BLE001  the page shows the reason (no checkpoint, no run)
        yield {"event": "error", "error": str(e), "run": run, "model": model}


def api_ask_questions(preset: str) -> dict:
    """The ask panel's questions for a class, drawn from the Ogden corpus (ships/lists/ogden-v0.1-questions.json):
    the keel's from one word back, the pilot's from two, the speller's (and every larger class's) from three:
    each a context the corpus continues with one word at least half the time (Justin, 21:35: "wouldn't these
    examples need to be simpler for the 300k")."""
    logic = _ask_logic(preset)
    p = paths.resolve("lists/ogden-v0.1-questions.json")
    if not p.exists():
        return {"preset": preset, "questions": [], "words_back": None, "logic": logic}
    d = json.loads(p.read_text())
    slug = _slug(preset)
    names = _class_names(preset)  # the question sets are keyed by the old names (ogden-v0.1-questions.json)
    key = "keel" if "keel" in names else "pilot" if "pilot" in names else "speller"
    s = d.get(key) or {}
    return {
        "preset": preset, "set": key, "words_back": s.get("words_back"),
        "questions": [
            {"text": q["context"].capitalize() if q["context"].split()[0] != "i" else q["context"], "hope": q["hope"],
             "about": f"{s.get('words_back')} word{'s' if s.get('words_back') != 1 else ''} back: the corpus continues it "
                      f"with '{q['hope']}' {round(100 * q['share'])}% of {q['count']:,} times"}
            for q in s.get("questions", [])
        ],
        "logic": logic,
    }  # fmt: skip


_MATHS_SOURCE: dict[str, dict] = {}


def _maths_source(book_id: str, headings: list[str]) -> dict:
    """Where each heading of the source book begins in the reader's own text (`/api/book`, which the reader opens
    at a character offset), past its title page and table of contents: the body starts at the book's second
    title line. Cached by book."""
    if book_id in _MATHS_SOURCE:
        return _MATHS_SOURCE[book_id]
    d = api_book(book_id, 0, 100000)
    t = d.get("text") or ""
    while len(t) < (d.get("chars") or 0):
        more = api_book(book_id, len(t), 100000).get("text") or ""
        if not more:
            break
        t += more
    first = t.find("\n", t.find(d.get("title", "").upper())) if d.get("title") else 0
    title = (d.get("title") or "").upper()
    body = t.find(title, first + 1) if title and t.find(title, first + 1) > 0 else 0
    at = {}
    for h in headings:
        i = t.find("\n" + h, body)
        at[h] = i + 1 if i >= 0 else None
    out = {"title": d.get("title"), "author": d.get("author"), "chars": d.get("chars"), "at": at}
    _MATHS_SOURCE[book_id] = out
    return out


def api_maths_book() -> dict:
    """The maths book (ships/lists/tricks/maths-book.csv, backend/scripts/make_maths_book.py): nine chapters after
    Augustus De Morgan's Elements of Arithmetic (pg68662), each a section of his Book I in his order, its sums in
    plain words, with answers and rivals, for the Scoring tab's Maths page to read against a voyage (the same ten
    guesses as the ask panel). Each chapter carries its source section and where the reader opens it."""
    import csv

    rows = list(csv.DictReader(paths.resolve("lists/tricks/maths-book.csv").open()))
    chapters: dict[int, dict] = {}
    for r in rows:
        c = chapters.setdefault(int(r["chapter"]), {"n": int(r["chapter"]), "key": r["key"], "title": r["title"], "about": r["about"], "sums": [],
                                                    "source": {"book": r.get("source"), "section": r.get("source_section"), "heading": r.get("source_heading")}})  # fmt: skip
        c["sums"].append({"item": r["item"], "text": r["prompt"], "hope": r["answer"], "rival": r["rival"]})
    book = None
    src = next((r.get("source") for r in rows if r.get("source")), None)
    if src:
        try:
            info = _maths_source(src, sorted({c["source"]["heading"] for c in chapters.values() if c["source"]["heading"]}))
        except Exception:  # noqa: BLE001  (the book not in this library: the credit stands, without links)
            info = {"title": None, "author": None, "at": {}}
        for c in chapters.values():
            c["source"]["at"] = info["at"].get(c["source"]["heading"])
        title = info.get("title") or "Elements of Arithmetic"
        book = {"id": src, "title": "Elements of Arithmetic" if title.lower() == "elements of arithmetic" else title,
                "author": info.get("author") or "De Morgan, Augustus, 1806-1871",
                "edition": "the 1858 edition (first published 1830)", "in_ogden": False}  # fmt: skip
    return {"chapters": [chapters[k] for k in sorted(chapters)], "mark": 6, "book": book}  # a chapter learnt: 6 of its 8 sums


def _logic_ask_from(preset: str) -> bool:
    """The stylist and every larger size (Justin, 8 November: "start testing the logic questions from 21m up"):
    read from the registry, not named here, as every size at least the stylist's 8 x 320 blocks (5M block
    weights and more; the speller has 2.7M)."""
    from thorp.models.registry import PRESETS

    p = PRESETS.get(preset.split("-")[0])
    return bool(p) and 12 * p["layers"] * p["width"] ** 2 >= 5_000_000


def _ask_logic(preset: str, per: int = 2) -> list[dict]:
    """The logic deck as questions to ask (lists/tricks/logic-40.csv, the variant with both premises): `per`
    items of each relation, in the deck's order. Each asks for the conclusion's first word, the hope, against
    the rival's (the answer the premises rule out): the Scoring tab ranks both among its ten guesses."""
    import csv

    if not _logic_ask_from(preset):
        return []
    try:
        rows = list(csv.DictReader(paths.resolve("lists/tricks/logic-40.csv").open()))
    except OSError:
        return []
    out = []
    for rel in LOGIC_RELATIONS:
        for r in [x for x in rows if x["relation"] == rel and x["variant"] == "both"][:per]:
            hope, rival = r["idea"].split()[0], r["rival"].split()[0]
            if hope.lower() == rival.lower():  # the two part later ("heavier than a kanan" / "heavier than a trinol"): not a one-word test
                continue
            out.append({"text": r["prompt"], "hope": hope, "rival": rival, "relation": rel, "item": r["item"],
                        "about": f"the logic deck, {rel}: the premises say '{r['idea']}', not '{r['rival']}'"})  # fmt: skip
    return out


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
    names = sorted({m for c in deck.CARDS if c.look for m in c.look[0]})
    peaks: dict[str, dict[str, float]] = {}
    for v in voyages:
        peaks[v["run_id"]] = _metric_peaks(v["run_id"], names)
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
    "nevermore_shared": "nevermore/natural_shared_score",
    "copy_gain": "nevermore/natural_copy_gain", "mover": "stars/mover/max_score",
    "comparator": "stars/comparator/shared_score", "words_back": "stars/offset_2/shared_score",
    "counter": "counter/probe_r2", "premise_marker": "stars/premise_marker/max_score",
    "one_hop": "tricks/logic_test/lift_one_hop", "cause": "tricks/logic_test/gain_cause",
    "scaffold_weight": "scaffold/weight", "scaffold_loss": "scaffold/loss",
}  # fmt: skip


def _depth_of(run_id: str) -> dict:
    """How each card is found, layer by layer: the per-layer reading, max over heads, from the run's own artifacts
    (the `stars` matrices and the `cards` curve). This is the star chart's depth axis."""
    import json

    from thorp.ledger import reader

    rec = reader()
    out: dict = {"layers": 0, "cards": {}}
    for kind in ("stars", "cards"):
        rows = rec.query(
            "select text from artifacts where run_id=? and kind=? order by step desc limit 1", [run_id, kind]
        )
        if not rows:
            continue
        with contextlib.suppress(Exception):
            d = json.loads(rows[0]["text"])
        for card, m in (d or {}).items():
            if not isinstance(m, list) or not m:
                continue
            with contextlib.suppress(Exception):
                if isinstance(m[0], list):  # layer x head
                    out["cards"][card] = [round(float(max(row)), 3) for row in m]
                    out["layers"] = max(out["layers"], len(m))
                elif isinstance(m[0], (int, float)):  # a layer curve (the bridge)
                    out["cards"][card] = [round(float(v), 3) for v in m]
                    out["layers"] = max(out["layers"], len(m))
    return out


def api_suit_ratings(preset: str = "", runs: str = "") -> dict:
    """Each ship's four suits — copying, position, comparing, carrying (9 November, Justin: "a rating for each ship
    against the 16 cards suit ... how good is each ship at copying, position, comparing and carrying"): the mean of a
    suit's cards, each card divided by its own mark, so 1.00 is "every card in the suit is lit"."""
    from thorp.ledger import reader
    from thorp.viable.s4_intelligence import readings
    from thorp.viable.s5_policy import deck

    def rating(metrics_of) -> dict:
        out = {}
        for suit in ("copying", "position", "comparing", "carrying"):
            vals = []
            for c in deck.CARDS:
                if c.constellation != suit:
                    continue
                metric = c.look[0][0] if c.look else (c.ability[0] if c.ability else None)
                mark = c.look[1] if c.look and len(c.look) > 1 and isinstance(c.look[1], float) else None
                v = metrics_of(metric, c.key)
                if v is None:
                    continue
                vals.append(float(v) / (mark or 1.0) if mark else float(v))
            out[suit] = round(sum(vals) / len(vals), 2) if vals else None
        return out

    import statistics

    wanted = [x for x in runs.split(",") if x]
    rec = reader()
    ships = []
    for size in ("300k", "1m", "9m", "21m", "50m"):
        if preset and preset != size:
            continue

        def at(rid: str, metric: str):
            if not metric:
                return None
            m = rec.query(
                "select value from metrics where run_id=? and name=? order by step desc limit 1", [rid, metric]
            )
            return m[0]["value"] if m else None

        if wanted:
            picked = []
            for r in _runs_rows():
                spec = json.loads(r.get("spec_json") or "{}")
                if (spec.get("model") or {}).get("preset") != size:
                    continue
                if r.get("name") not in wanted and r.get("run_id") not in wanted:
                    continue
                picked.append(r)
            if not picked:
                continue
            per = [rating(lambda metric, key, rid=r["run_id"]: at(rid, metric)) for r in picked]
            merged = {}
            for suit in ("copying", "position", "comparing", "carrying"):
                vals = [x[suit] for x in per if x.get(suit) is not None]
                merged[suit] = round(statistics.median(vals), 2) if vals else None
            ships.append({"size": size, "run": f"median of {len(picked)} voyage{'' if len(picked) == 1 else 's'}", **merged})
            continue
        rows = rec.query(
            "select r.run_id, r.name from runs r where json_extract(r.spec_json,'$.model.preset') = ?"
            " and json_extract(r.spec_json,'$.sop') is not null order by r.started desc limit 1",
            [size],
        )
        if not rows:
            continue
        rid = rows[0]["run_id"]
        ships.append({"size": size, "run": rows[0]["name"], **rating(lambda metric, key, rid=rid: at(rid, metric))})
    for key, model in (("qwen3-4b", "deck-mlx-community--Qwen3-4B-4bit"),
                       ("phi-4-mini", "deck-mlx-community--Phi-4-mini-instruct-4bit"),
                       ("llama-3.2-3b", "deck-mlx-community--Llama-3.2-3B-bf16")):
        m = (readings.get(model) or {}).get("metrics") or {}
        if m:
            ships.append({"size": key, "run": key, **rating(lambda metric, card, m=m: m.get(metric) if metric else None)})
    return {"ships": ships}


def api_sop_scores(preset: str = "", runs: str = "") -> dict:
    """The reasoning results **by SOP version** at one size (9 November, Justin: the overview "should also show the
    reasoning results by SOP version, so when we run 0.0.6 we can compare"): for every version this size has sailed,
    its newest voyage, its chaining lift, and how many of the chart's ten points clear their mark."""
    from thorp.ledger import reader
    from thorp.viable.s5_policy import deck

    QWEN = 0.538
    wanted = [x for x in runs.split(",") if x]
    rec = reader()
    rows = rec.query(
        "select json_extract(spec_json,'$.sop') sop, max(started) last from runs"
        " where json_extract(spec_json,'$.model.preset') = ? group by sop order by sop",
        [preset],
    )
    out = []
    for r in rows:
        sop = r["sop"]
        if not sop:
            continue
        candidates = rec.query(
            "select run_id, name, status from runs where json_extract(spec_json,'$.model.preset') = ?"
            " and json_extract(spec_json,'$.sop') = ? order by started desc",
            [preset, sop],
        )
        if wanted:
            candidates = [x for x in candidates if x.get("name") in wanted or x.get("run_id") in wanted]
        if not candidates:
            continue
        rid = candidates[0]["run_id"]
        lifts = []
        for t in ("nature", "mill", "between", "pigeonhole"):
            m = rec.query(
                "select value from metrics where run_id=? and name=? order by step desc limit 1",
                [rid, f"tricks/{t}_test/lift"],
            )
            if m:
                lifts.append(float(m[0]["value"]))
        ch = sum(lifts) / len(lifts) if lifts else None
        # the ten points: how many clear their mark in this voyage
        clears = 0
        for p in (("previous_word", "stars/previous_word/max_score"), ("delimiter", "stars/delimiter/max_score"),
                  ("induction", "nevermore/natural_max_score"), ("comparator", "stars/comparator/max_score"),
                  ("duplicate_word", "stars/duplicate_word/max_score")):  # fmt: skip
            m = rec.query(
                "select value from metrics where run_id=? and name=? order by step desc limit 1", [rid, p[1]]
            )
            card = next((c for c in deck.CARDS if c.key == p[0]), None)
            mark = card.look[1] if card and card.look and len(card.look) > 1 and isinstance(card.look[1], float) else None
            if m and mark and float(m[0]["value"]) >= mark:
                clears += 1
        out.append({"sop": sop, "run": candidates[0]["name"], "status": candidates[0]["status"],
                    "chaining": None if ch is None else round(ch, 3),
                    "gap": None if ch is None else round(ch - QWEN, 3), "clears": clears, "of": 5})
    return {"preset": preset, "qwen": QWEN, "versions": out}


def api_ladder_chaining(sop: str = "", runs: str = "") -> dict:
    """The ladder's chaining, size by size, against Qwen3 4B: each size's newest voyage on the standard,
    its chaining lift at its last step, and how far it stands from 0.538.

    `runs` narrows each size to the page's selected voyages and reports the **median** of their chaining
    lifts (10 November: the SOP summary follows the expedition selector)."""
    import statistics

    from thorp.ledger import reader

    QWEN = 0.538
    wanted = [x for x in runs.split(",") if x]
    allruns = _runs_rows()
    rec = reader()
    out = []
    for size in ("300k", "1m", "9m", "21m", "50m"):
        picked = []
        for r in allruns:
            spec = json.loads(r.get("spec_json") or "{}")
            if (spec.get("model") or {}).get("preset") != size:
                continue
            if sop and str(spec.get("sop") or "") != sop:
                continue
            if wanted and r.get("name") not in wanted and r.get("run_id") not in wanted:
                continue
            picked.append(r)
        if not wanted:
            picked = picked[-1:]  # newest
        if not picked:
            out.append({"size": size, "status": "not sailed", "chaining": None, "gap": None})
            continue
        per = []
        for r in picked:
            lifts = []
            for t in ("nature", "mill", "between", "pigeonhole"):
                m = rec.query(
                    "select value from metrics where run_id=? and name=? order by step desc limit 1",
                    [r["run_id"], f"tricks/{t}_test/lift"],
                )
                if m:
                    lifts.append(float(m[0]["value"]))
            if lifts:
                per.append(sum(lifts) / len(lifts))
        ch = statistics.median(per) if per else None
        out.append({"size": size, "run": picked[-1]["name"], "status": picked[-1]["status"],
                    "minutes": picked[-1].get("wall_minutes"), "of": len(per),
                    "chaining": None if ch is None else round(ch, 3),
                    "gap": None if ch is None else round(ch - QWEN, 3), "qwen": QWEN})
    return {"sop": sop or "all", "qwen": QWEN, "sizes": out}

def api_star_points(preset: str = "300k", runs: str = "") -> dict:
    """The ten-point star chart as a journey: for each point, how far the model that chains (Qwen3 4B) and our
    smallest ship (the 300k at v0.0.5) get toward that point's mark, so the two can be drawn as lines (9 November:
    "a line representing Qwen 4b hitting the 10 marks in the star chart and at what point and then overlayed against
    that the 300k at 0.0.5").

    `runs` narrows the Nothing up my sleeve line to named voyages and shows their **median** ratio (10 November: a page can
    pick an expedition and no voyage, and the chart is then the expedition's median)."""
    import statistics

    from thorp import sop
    from thorp.ledger import reader
    from thorp.viable.s4_intelligence import readings
    from thorp.viable.s5_policy import deck

    std = sop.standard("0.0.6") or {}
    points = ((std.get("chart") or {}).get("points") or [])[:10]
    qw = (readings.get("deck-mlx-community--Qwen3-4B-4bit") or {}).get("metrics") or {}
    by_key = {c.key: c for c in deck.CARDS}
    rec = reader()
    wanted = [x for x in runs.split(",") if x][:40]
    ids = []
    for name in wanted:
        row = _run_row(name)
        if row:
            ids.append(row["run_id"])
    marks = ",".join("?" for _ in ids)
    out = []
    for pt in points:
        card = str(pt.get("card") or "").replace("the ", "").replace("-", "_").strip().lower()
        c = by_key.get(card) or by_key.get(card.replace("nevermore", "nevermore"))
        if c is None:
            continue
        metric = c.look[0][0] if c.look else (c.ability[0] if c.ability else None)
        if not metric:
            continue
        mark = c.look[1] if c.look and len(c.look) > 1 and isinstance(c.look[1], float) else None
        if ids:
            # the last reading of each chosen voyage: the median across them, not the newest voyage's
            rows = rec.query(
                f"select run_id, value from metrics where run_id in ({marks}) and name=? and value is not null"
                " order by run_id, step",
                [*ids, metric],
            )
            last = {r["run_id"]: r["value"] for r in rows}
            vals = [float(v) for v in last.values() if v is not None]
            raw = statistics.median(vals) if vals else None
            q = qw.get(metric)
            scale = mark or max(abs(q or 0), abs(raw or 0), 1e-6)
            ours = None if raw is None else raw / scale
        else:
            # the size's newest voyage and its last reading: a running ship is tracked as it trains, not by its best
            rows = rec.query(
                "select m.value from runs r join metrics m on m.run_id = r.run_id"
                " where r.run_id = (select run_id from runs where json_extract(spec_json,'$.model.preset') = ?"
                "   order by started desc limit 1) and m.name = ? and m.value is not null"
                " order by m.step desc limit 1",
                [preset, metric],
            )
            ours = rows[0]["value"] if rows else None
            q = qw.get(metric)
            scale = mark or max(abs(q or 0), abs(ours or 0), 1e-6)
        out.append({
            "n": int(pt.get("n") or len(out) + 1), "role": pt.get("role") or "", "card": c.key,
            "ours": None if ours is None else round(float(ours), 2),
            "qwen": None if q is None else round(float(q) / scale, 2),
            "mark": mark, "tier": deck.retention(c.key)["tier"],
        })
    return {"points": out, "runs": len(ids)}


def api_client_log(q: dict) -> dict:
    """A browser-side error, written where the harness can read it (9 November: a blank tab showed nothing, and the
    console was on the far side of the screen). The page posts here from its render boundary."""
    from datetime import datetime

    from thorp import paths

    msg = (q.get("msg") or "")[:4000]
    f = paths.data_dir() / "runs" / "ui-errors.log"
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
    return {"ok": True}


def api_card_deck() -> dict:
    """The sixteen cards, card by card: suit, mark, retention tier, the best Nothing up my sleeve reading and Qwen3 4B's own — the
    deck as a table for the Discoveries Cards tab (9 November: "the cards should be moved to a tab under discoveries")."""
    from thorp.ledger import reader
    from thorp.viable.s4_intelligence import readings
    from thorp.viable.s5_policy import deck

    qw = (readings.get("deck-mlx-community--Qwen3-4B-4bit") or {}).get("metrics") or {}
    rec = reader()
    out = []
    for c in deck.CARDS:
        metric = c.look[0][0] if c.look else (c.ability[0] if c.ability else None)
        mark = c.look[1] if c.look and len(c.look) > 1 and isinstance(c.look[1], float) else None
        ours = None
        if metric:
            rows = rec.query(
                "select value from metrics where name=? and value is not null order by value desc limit 1", [metric]
            )
            ours = float(rows[0]["value"]) if rows else None
        out.append({"card": c.key, "suit": c.constellation, "mark": mark,
                    "tier": deck.retention(c.key)["tier"], "ours": ours,
                    "qwen": None if not metric else qw.get(metric)})
    return {"cards": out}


DECK_FILES = (
    # key, name, file, about
    (
        "logic",
        "The 40-item logic deck",
        "logic.csv",
        "Forty items, eight a relation (order, cause, membership, proportion, counterfactual), each in seven "
        "variants: both premises, each alone, swapped, padded, one hop and three hops. The knowledge-free deck.",
    ),
    (
        "cause",
        "The 96-item cause deck",
        "logic-cause.csv",
        "The cause relation alone, widened from eight to ninety-six items so the interval can resolve 0.1. "
        "Same seven variants; the target is the order-free gain, the worse of the two premise orders.",
    ),
)


def api_decks() -> dict:
    """The item decks the Decks tab shows, beside the sixteen cards: the 40-item logic deck and the 96-item
    cause deck, every item with all seven variants (the 16 cards come from /api/card_deck)."""
    import csv

    from thorp import paths

    decks = []
    for key, name, filename, about in DECK_FILES:
        p = paths.resolve(f"lists/tricks/{filename}")
        if not p.exists():
            decks.append({"key": key, "name": name, "about": about, "count": 0, "items": [], "missing": True})
            continue
        items: dict[str, dict] = {}
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                it = items.setdefault(
                    r["item"], {"item": r["item"], "relation": r["relation"], "variants": {}}
                )
                it["variants"][r["variant"]] = {
                    "prompt": r["prompt"],
                    "frame": r["frame"],
                    "idea": r["idea"],
                    "rival": r["rival"],
                    "bridge": r["bridge"],
                    "distractor": r["distractor"],
                }
        decks.append(
            {
                "key": key,
                "name": name,
                "about": about,
                "count": len(items),
                "relations": sorted({x["relation"] for x in items.values()}),
                "variants": sorted({v for x in items.values() for v in x["variants"]}),
                "items": list(items.values()),
            }
        )
    return {"decks": decks}


def api_stars_deviation() -> dict:
    """300k against Qwen3 4B, point by point: each card's reading in our smallest ship against the same card read in
    a model that chains, as a deviation from the card's own mark (9 November, Justin: "this page should show the star
    chart for 300k vs qwen 4b as deviations between the points")."""
    from thorp.ledger import reader
    from thorp.viable.s4_intelligence import readings
    from thorp.viable.s5_policy import deck

    qw = (readings.get("deck-mlx-community--Qwen3-4B-4bit") or {}).get("metrics") or {}
    rec = reader()
    ours: dict = {}
    for c in deck.CARDS:
        metric = c.look[0][0] if c.look else (c.ability[0] if c.ability else None)
        if not metric:
            continue
        rows = rec.query(
            "select r.run_id, m.value from runs r join metrics m on m.run_id = r.run_id"
            " where json_extract(r.spec_json,'$.model.preset') = '300k' and m.name = ? and m.value is not null"
            " order by m.value desc limit 1",
            [metric],
        )
        if rows:
            ours[c.key] = {"metric": metric, "value": rows[0]["value"]}
    out = []
    for c in deck.CARDS:
        metric = c.look[0][0] if c.look else (c.ability[0] if c.ability else None)
        mark = c.look[1] if c.look and len(c.look) > 1 and isinstance(c.look[1], float) else None
        o = (ours.get(c.key) or {}).get("value")
        q = qw.get(metric) if metric else None
        if o is None or q is None:
            continue
        scale = mark or max(abs(o), abs(q), 1e-6)
        out.append({
            "card": c.key, "name": c.name, "suit": c.constellation, "stage": c.stage,
            "ours": round(float(o), 4), "qwen": round(float(q), 4),
            "dev": round(float(o - q) / scale, 3),
            "tier": deck.retention(c.key)["tier"],
        })
    out.sort(key=lambda r: r["dev"])
    return {"cards": out}


def api_depth(preset: str, sop: str = "") -> dict:
    """The depth of every shape of a size: the same size's variants (300k, 300k-l3, 300k-l28) side by side, each
    with its layers and every card's reading at each layer (the star chart's order, drawn against depth)."""
    import json

    from thorp.ledger import reader

    rec = reader()
    shapes: dict = {}
    for r in rec.query(
        "select run_id, name, status, started, spec_json from runs where"
        " json_extract(spec_json,'$.model.preset') like ? order by started desc",
        [f"{preset}%"],
    ):
        spec = json.loads(r["spec_json"])
        if sop and str(spec.get("sop") or "") != sop:
            continue
        p = (spec.get("model") or {}).get("preset")
        if not p or p in shapes:
            continue
        d = _depth_of(r["run_id"])
        if not d["layers"]:
            continue
        shapes[p] = {"run": r["name"], "status": r["status"], **d}
    return {"preset": preset, "shapes": shapes}


def api_watch(preset: str, sop: str = "", run: str = "") -> dict:
    """Watch a class train (Justin, 22:25: "so I can watch thorp 21m training to see what's happening ... show the
    stages"): the class's voyage at sea (else its latest home), where it is (step, tokens, pass, stage, speed, time
    left), its fitout's stage plan with the voyage's place on it, the cards it has drawn and when (the deck's
    rules), the series that matter by tokens read, and the log's last lines."""
    import time
    from datetime import datetime

    from thorp.viable.s4_intelligence import wager

    preset = _preset_of(preset)  # a class slug ('pan') names the same size as its preset ('300k')
    cls = preset.split("-")[0]
    candidates = []
    wanted = next((r for r in _runs_rows() if run and (r["run_id"] == run or r["name"] == run)), None)
    if wanted is not None:
        # the page's voyage picker: watch that voyage, not the newest (10 November)
        candidates = [wanted]
    for r in ([] if wanted is not None else reversed(_runs_rows())):  # newest first
        spec0 = json.loads(r.get("spec_json") or "{}")
        p = spec0.get("model", {}).get("preset")
        if (p or "").startswith(cls) and (sop == "" or (spec0.get("sop") or "") == sop):
            candidates.append(r)
    if not candidates:
        return {"preset": preset, "voyage": None}
    # order by (status='running') desc, started desc: the newest at sea, else the newest home
    running = [r for r in candidates if r["status"] == "running"]
    v = (running or candidates)[0]
    rid = v["run_id"]
    spec = json.loads(v["spec_json"] or "{}")
    f = paths.resolve("specs").rglob(f"{v['name']}.yaml")
    f = next(iter(f), None)
    if f is not None:
        import yaml

        spec = {**spec, **(yaml.safe_load(f.read_text()) or {})}
    bt = (spec.get("optim") or {}).get("batch_tokens") or 32768
    def one(name):
        return _metric(rid, name)

    total_steps = one("plan/total_steps")
    tokens_total = one("plan/tokens_total")
    passes = one("plan/passes") or (spec.get("data") or {}).get("passes") or 1
    loss_steps, _ = _metric_series_gated(rid, "loss")
    last = loss_steps[-1] if loss_steps else 0
    seen = one("tokens_seen") or last * bt
    series = {}
    for key, name in WATCH_SERIES.items():
        s, vv = _metric_series_gated(rid, name)
        pts = [[st * bt, val] for st, val in zip(s, vv, strict=True) if val is not None]
        if key in ("loss", "lr", "tokens_per_s", "scaffold_weight", "scaffold_loss") and len(pts) > 400:  # every step: thin to 400 points
            k = len(pts) // 400 + 1
            pts = pts[::k] + ([pts[-1]] if pts[-1] not in pts[::k] else [])
        series[key] = pts
    last_t = _metric_max_ts(rid, "loss")
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
    # the metre scaffold's three phases (thorp/train.py optim.scaffold), in tokens, and where the voyage is among them
    sc = (spec.get("optim") or {}).get("scaffold")
    scaffold = None
    if sc and total_steps:
        from thorp import train as _train

        hold = float(sc.get("hold", 0.0)) * total_steps
        end = float(sc["fade"]) * total_steps if sc.get("fade") is not None else None
        bands = [{"phase": "metre", "from": 0, "to": (hold if end is not None else total_steps) * bt}]
        if end is not None:
            bands += [{"phase": "fade", "from": hold * bt, "to": end * bt}, {"phase": "content", "from": end * bt, "to": total_steps * bt}]
        # the floor (0 unless set): the weight the fade stops at and holds to the end, so a voyage with one never sails
        # on language alone (thorp/train.py scaffold_weight)
        scaffold = {"heads": sc.get("heads", []), "weight": sc.get("weight", 1.0), "floor": float(sc.get("floor", 0.0)),
                    "bands": bands, "now": _train.scaffold_phase(int(last), int(total_steps), sc)}  # fmt: skip
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
        "stages": stages, "post": chain, "drawn": drawn, "series": series, "log": log, "scaffold": scaffold,
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
    """The Forgotten Tomes: each book's catalogue facts, every Nothing up my sleeve run's latest score on it, and
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
    for run in _runs_rows():
        for e in _latest_evals(run["run_id"], "hole-cards-unseen"):
            scores.setdefault(run["ship"] or run["name"], {})[e["book_id"]] = e["bpb"]
    for _, x in readings.glob("*__hole-cards-unseen"):
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
    rid = _run_id(run)
    a = _artifact(rid, "recipe") if rid else None
    return json.loads(a["text"]) if a and a["text"] else []


def api_book(book_id: str, offset: int = 0, length: int = 20000) -> dict:
    """A slice of a fetched book's stripped text (the text Nothing up my sleeve trains and scores on)."""
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
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the reader went away (a page navigation mid-response): never take the server down

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(_finite(obj), default=str).encode(), "application/json")

    def _chat_stream(self) -> None:
        """A chat answer as it is written: one line of JSON an event, flushed as it comes, the
        connection closed at the end (no length is known ahead). A reader that goes away stops the
        generation: the next write fails, and closing the generator ends the sampling and frees the
        one-at-a-time lock."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        events = api_chat_stream(body)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            for ev in events:
                self.wfile.write(json.dumps(_finite(ev), default=str).encode() + b"\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the reader stopped it
        finally:
            events.close()
            from thorp.ledger import close_reader

            close_reader()

    def _onboard_page(self, path: str) -> None:
        """The first-run page and its two files, from thorp/onboard/web. It does not need the Astro
        build: a fresh clone must be able to run setup before it has a dashboard."""
        from thorp.onboard import api

        rel = "index.html" if path in ("/onboard", "/onboard/") else path[len("/onboard/") :]
        got = api.asset(rel)
        if got is None:
            return self._send(404, b"not found", "text/plain")
        return self._send(200, got[0], got[1], "no-store")

    def _onboard_api(self, path: str, q: dict) -> None:
        from thorp.onboard import api

        if not api.authorized(self.headers, q):
            return self._json(403, {"error": "the first-run token is missing or expired; open the link printed in the terminal"})
        name = path[len("/api/onboard/") :]
        routes = {"state": api.state_payload, "catalogue": api.catalogue_payload}
        if name not in routes:
            return self._json(404, {"error": "not found"})
        return self._json(200, routes[name]())

    def _onboard_post(self, path: str) -> None:
        from thorp.onboard import api

        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 4_000_000)) or b"{}")
            if not isinstance(body, dict):
                raise api.OnboardError("the request body must be a JSON object")
            if path == "/api/store/switch":
                # the Settings cog, not the first run: no onboarding token, but the same conservative
                # switch (a test, the at-sea rule, a restart note).
                return self._json(200, api.switch_store(body))
            if not api.authorized(self.headers):
                return self._json(403, {"error": "the first-run token is missing or expired; open the link printed in the terminal"})
            name = path[len("/api/onboard/") :]
            handlers = {
                "answer": api.answer,
                "downloads": api.start_downloads,
                "downloads/cancel": api.cancel_download,
                "store/setup": api.start_store,
                "store/test": api.test_store,
                "build": lambda _: api.start_build(),
                "finish": lambda _: api.finish(),
                "reset": lambda _: api.reset(),
            }
            if name not in handlers:
                return self._json(404, {"error": "not found"})
            return self._json(200, handlers[name](body))
        except api.OnboardError as e:
            return self._json(getattr(e, "status", 400), {"error": str(e)})
        except (ValueError, KeyError) as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": repr(e)})
        finally:
            from thorp.ledger import close_reader

            close_reader()

    def do_POST(self):  # noqa: N802
        """The writes: the table (POST /api/table/reply {run, question, history, ...}) and the fitout
        builder (POST /api/fitouts/save {fitout}, POST /api/fitouts/queue {key, preset, seeds, where},
        the latter changing what the Mac trains next, so the page asks before it sends)."""
        u = urlparse(self.path)
        if u.path.startswith("/api/onboard/") or u.path == "/api/store/switch":
            return self._onboard_post(u.path)
        if u.path == "/api/chat/stream":
            return self._chat_stream()
        posts = {
            "/api/table/reply": api_table_reply,
            "/api/library_config/preview": api_library_config_preview,
            "/api/library_config/save": api_library_config_save,
            "/api/library_config/delete": api_library_config_delete,
            "/api/fitouts/save": api_fitout_save,
            "/api/shipbuilder/save": api_shipbuilder_save,
            "/api/fitouts/queue": api_fitout_queue,
            "/api/wager/deal": api_wager_deal,
            "/api/wager/bet": api_wager_bet,
            "/api/wager/queue": api_wager_queue,
            "/api/constraints": api_constraints_set,
            "/api/vast": api_vast_set,
            "/api/compute": api_compute_set,
            "/api/chat": api_chat,
            "/api/chat/notes": post_chat_note,
            "/api/chat/questions": post_chat_question,
            "/api/chat/threads": post_chat_thread,
            "/api/chat/threads/delete": post_chat_thread_delete,
            "/api/expedition_priority": post_expedition_priority,
        }
        if u.path not in posts:
            return self._send(404, b"not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 1_000_000)) or b"{}")
            return self._json(200, posts[u.path](body))
        except TableNotBuilt as e:
            return self._json(503, {"error": str(e)})
        except StoreDown as e:  # the one store is down: said, never answered from the old files
            return self._json(503, {"error": str(e), "store": "down"})
        except (
            LookupError
        ) as e:  # no such run, or no checkpoint to talk to (thorp.table's own words)
            return self._json(404, {"error": str(e.args[0] if e.args else e)})
        except (ValueError, KeyError) as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": repr(e)})
        finally:
            # a request's thread ends here: return its Postgres reader to the pool (see ledger.close_reader)
            from thorp.ledger import close_reader

            close_reader()

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/onboard" or u.path.startswith("/onboard/"):
                return self._onboard_page(u.path)
            if u.path.startswith("/api/onboard/"):
                return self._onboard_api(u.path, q)
            if u.path in ("/", "/index.html"):
                page = _static("index.html")
                return (
                    self._send(200, page[0], page[1])
                    if page
                    else self._send(503, NOT_BUILT, "text/html; charset=utf-8")
                )
            if not u.path.startswith("/api/"):
                got = _static(u.path)
                if got is None and not u.path.endswith("/"):
                    got = _static(u.path + "/index.html")  # Astro's per-route pages (the multi-page build)
                # a dynamic sub-route (e.g. /discoveries/<trick>) serves its section's shell: the panel is
                # filled client-side from the JSON API, so the shell is the same for every slug
                if got is None:
                    parts = [p for p in u.path.split("/") if p]
                    while parts and got is None:
                        parts.pop()
                        got = _static("/".join(parts) + "/index.html") if parts else _static("index.html")
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
                "/api/waters": api_waters,
                "/api/metrics": lambda: api_metrics(q["run"], q.get("names", ""), q.get("points", "")),
                "/api/evals": lambda: api_evals(q["run"]),
                "/api/run": lambda: api_run(q["run"]),
                "/api/compare": lambda: api_compare(),
                "/api/ladder": lambda: api_ladder(),
                "/api/journeys": api_journeys,
                "/api/foreign": lambda: api_foreign(q.get("key", "qwen3-4b")),
                "/api/foreign_control_tokens": api_foreign_control_tokens,
                "/api/shipbuilder": lambda: api_shipbuilder(q.get("harbour", "schimint")),
                "/api/library_summary": lambda: api_library_summary(q["path"]),
                "/api/journey": lambda: api_journey(q["key"]),
                "/api/rung": lambda: api_rung(q["preset"], q.get("limit", 0)),
                "/api/tomes": lambda: api_tomes(),
                "/api/waypoints": lambda: api_waypoints(q["preset"], q.get("limit", 30)),
                "/api/essay": lambda: api_essay(q["name"]),
                "/api/voyages": lambda: api_voyages(),
                "/api/ships": lambda: api_ships(),
                "/api/voyage": lambda: api_voyage_series(q["key"]),
                "/api/discoveries": lambda: api_discoveries(q.get("runs", "")),
                "/api/heads": lambda: api_heads(q.get("model", "mlx-community/Qwen3-4B-4bit")),
                "/api/personas": lambda: api_personas(q.get("model", "mlx-community/Qwen3-4B-4bit")),
                "/api/sieves": lambda: api_sieves(),
                "/api/table/transcript": lambda: api_table_transcript(q["run"]),
                "/api/stages": lambda: api_stages(q.get("runs", "")),
                "/api/trick": lambda: api_trick_series(q["key"]),
                "/api/chain": lambda: api_chain(q["key"]),
                "/api/chains": api_chains,
                "/api/shelves": api_shelves,
                "/api/shelf_books": lambda: api_shelf_books(q["path"]),
                "/api/leaderboard": api_leaderboard,
                "/api/observation": lambda: api_observation(q.get("expedition", "")),
                "/api/expeditions": lambda: api_voyages(),
                "/api/expedition": lambda: api_voyage_series(q["key"]),
                "/api/expeditions/overview": api_expeditions_overview,
                "/api/expedition_priority": api_expedition_priority,
                "/api/deck_atlas": api_deck_atlas,
                "/api/lanes": api_lanes,
                "/api/constraints": api_constraints,
                "/api/vast": api_vast,
                "/api/compute": api_compute,
                "/api/hulls": api_hulls,
                "/api/at_sea": lambda: api_at_sea(str(q.get("expedition") or "kipling")),
                "/api/hulls/save": lambda: api_hull_save(str(q.get("preset") or ""), str(q.get("layers") or ""), str(q.get("width") or ""), str(q.get("heads") or "")),
                "/api/lanes/slots": lambda: api_lanes_slots(str(q.get("mac") or 1)),
                "/api/expedition_plan": lambda: api_expedition_plan(q.get("key", "kipling")),
                "/api/queue": api_queue,
                "/api/library": api_shelves,
                "/api/library_books": lambda: api_shelf_books(q["path"]),
                "/api/library_trigrams": lambda: api_shelf_trigrams(q["path"]),
                "/api/voyages/where": lambda: api_voyages_where(q.get("runs", "")),
                "/api/governance": api_governance,
                "/api/store": api_store,
                "/api/acquisition": api_acquisition,
                "/api/acquisition/audit": api_acquisition_audit,
                "/api/series": lambda: api_series(q.get("runs", ""), q.get("metrics", "")),
                "/api/fitout_builder": api_fitout_builder,
                "/api/selection": lambda: api_selection(q["fitout"]),
                "/api/library_browse": api_library_browse,
                "/api/library_configs": lambda: api_library_configs(q.get("branch", "")),
                "/api/shelf_trigrams": lambda: api_shelf_trigrams(q["path"]),
                "/api/knockout": lambda: api_knockout(q.get("model", "")),
                "/api/class_score": lambda: api_class_score(q["preset"], q.get("runs", "")),
                "/api/class_cards": lambda: api_class_cards(q["preset"], q.get("runs", "")),
                "/api/class_best": lambda: api_class_best(q["preset"]),
                "/api/wager": lambda: api_wager(q["preset"]),
                "/api/watch": lambda: api_watch(q["preset"], q.get("sop", ""), q.get("run", "")),
                "/api/depth": lambda: api_depth(q.get("preset", ""), q.get("sop", "")),
                "/api/stars_deviation": api_stars_deviation,
                "/api/card_deck": api_card_deck,
                "/api/decks": api_decks,
                "/api/client_log": lambda: api_client_log(q),
                "/api/star_points": lambda: api_star_points(q.get("preset", "300k"), q.get("runs", "")),
                "/api/ladder_chaining": lambda: api_ladder_chaining(q.get("sop", ""), q.get("runs", "")),
                "/api/sop_scores": lambda: api_sop_scores(q.get("preset", ""), q.get("runs", "")),
                "/api/suit_ratings": lambda: api_suit_ratings(q.get("preset", ""), q.get("runs", "")),
                "/api/class_deck": lambda: api_class_deck(q["preset"]),
                "/api/ask_questions": lambda: api_ask_questions(q["preset"]),
                "/api/chat": lambda: api_chat(q),
                "/api/chat/models": api_chat_models,
                "/api/chat/notes": lambda: api_chat_notes(q),
                "/api/chat/questions": api_chat_questions,
                "/api/chat/threads": api_chat_threads,
                "/api/maths_book": lambda: api_maths_book(),
                "/api/class_subjects": lambda: api_class_subjects(q["preset"]),
                "/api/class_shapes": lambda: api_class_shapes(q["preset"]),
                "/api/class_vs": lambda: api_class_vs(q["preset"], q.get("ref"), q.get("voyage"), q.get("runs", "")),
                "/api/class_logic": lambda: api_class_logic(q["preset"]),
                "/api/logic_relation": lambda: api_logic_relation(q["preset"], q["relation"]),
                "/api/table/guesses": lambda: api_table_guesses(
                    q["run"], q.get("text", ""), q.get("k", 10), q.get("mode", "1")
                ),
                "/api/fitouts": lambda: api_fitouts(q.get("preset", "")),
                "/api/sops": lambda: api_sops(q.get("preset", "")),
                "/api/census": api_census,
                "/api/competitor": lambda: api_competitor(q["model"]),
                "/api/thorp": lambda: api_thorp(q["ship"]),
                "/api/lab": lambda: api_lab(q["lab"]),
                "/api/bridge": api_bridge,
                "/api/leaderboard/internal": api_leaderboard_internal,
                "/api/smoking_qwen": api_smoking_qwen,
                "/api/bet": api_bet,
                "/api/settings": lambda: api_settings(q.get("fresh", "")),
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
        except StoreDown as e:  # the one store is down: said, never answered from the old files
            return self._send(503, json.dumps({"error": str(e), "store": "down"}).encode(), "application/json")
        except LookupError as e:  # no such harbour, ship, journey or foreign model
            return self._send(404, json.dumps({"error": str(e.args[0] if e.args else e)}).encode(), "application/json")
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": repr(e)}).encode(), "application/json")
        finally:
            # a request's thread ends here: return its Postgres reader to the pool (see ledger.close_reader)
            from thorp.ledger import close_reader

            close_reader()


class _DualStack(ThreadingHTTPServer):
    """Listen on both IPv4 and IPv6 (9 November: the page failed with ERR_CONNECTION_REFUSED because the server bound
    127.0.0.1 only and the browser resolves `localhost` to ::1 first — half the requests never reached a socket)."""

    address_family = socket.AF_INET6
    # a page opens many /api requests at once; the default backlog of 5 refuses the rest under Linux/macOS,
    # which reached the browser as blank panels (10 November)
    request_queue_size = 128
    daemon_threads = True

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except Exception:
            pass
        super().server_bind()


class _Loopback(ThreadingHTTPServer):
    """The first run listens on 127.0.0.1 only: its token and its downloads are not a LAN service."""

    address_family = socket.AF_INET
    request_queue_size = 32
    daemon_threads = True


def serve(port: int = 8787, *, onboard: bool = False, open_browser: bool = False) -> None:
    if onboard:
        import threading
        import time
        import webbrowser

        from thorp.onboard import api

        api.begin()
        srv = _Loopback(("127.0.0.1", port), Handler)
        url = f"http://127.0.0.1:{port}/onboard?token={api.token()}"
        print(f"thorp onboard on {url}", flush=True)
        print("  the first-run page is local to this Mac; keep this terminal open. Ctrl-C stops it.", flush=True)
        if open_browser:
            def _open() -> None:
                time.sleep(0.35)
                try:
                    webbrowser.open(url)
                except Exception:  # noqa: BLE001  (headless shells, no default browser)
                    pass

            threading.Thread(target=_open, name="onboard-browser", daemon=True).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
        return
    srv = _DualStack(("::", port), Handler)  # :: with V6ONLY=0 covers both ::1 and 127.0.0.1
    # the warm threads are started on the first visit, not here: a cold server must answer the
    # leaderboard before the shelves' long read begins
    print(f"thorp dash on http://localhost:{port}  (ledger {paths.ledger_path()})", flush=True)
    from thorp.onboard import state as onboard_state

    if not onboard_state.path().exists():
        print("  first run? `thorp onboard` sets up the store, models and dashboard.", flush=True)
    # the leaderboard is the page most visits first: fill its cache before the shelves' long read, so
    # the first request after a restart does not race a 25 s library build for the store (10 November)
    with contextlib.suppress(Exception):
        api_leaderboard()
    # warm the Library's build before anyone asks for it: it takes ~25 s and the page has nothing to show
    # until it lands (9 November, "can you speed this page up")
    with contextlib.suppress(Exception):
        _warm(_BROWSE_WARM, _browse_build)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


def api_settings(fresh: str = "") -> dict:
    """The settings page (the cog in the header): the disk and what is kept on it, the store, the server and
    machine, the switches and the lanes (thorp.dash.settings). `fresh=1` measures the sizes again now."""
    from thorp.dash import settings

    return settings.payload(fresh=fresh in ("1", "true", "yes"))


def api_ladder() -> dict:
    """The ladder, served from a cached copy: its query reads the live ledger, which the training run
    can lock for minutes. A good copy (memory, then data/ladder-cache.json) is returned at once and a
    background thread refreshes it; only a cold server with no cache waits for the query."""
    import json
    import threading
    import time

    from thorp import paths

    cache_file = paths.data_dir() / "ladder-cache.json"
    now = time.time()
    v = _LADDER_CACHE["value"]
    at = _LADDER_CACHE["at"]
    if v is None and cache_file.exists():
        try:
            v = json.loads(cache_file.read_text())
            at = cache_file.stat().st_mtime
            _LADDER_CACHE.update(value=v, at=at)
        except Exception:  # noqa: BLE001
            v = None
    if v is not None:
        if now - at > 120.0 and not _LADDER_CACHE.get("busy"):
            _LADDER_CACHE["busy"] = True

            def refresh():
                try:
                    d = _api_ladder()
                    _LADDER_CACHE.update(value=d, at=time.time())
                    cache_file.write_text(json.dumps(d, default=str))
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    _LADDER_CACHE["busy"] = False

            threading.Thread(target=refresh, daemon=True).start()
        return v
    if _LADDER_CACHE["lock"] is None:
        _LADDER_CACHE["lock"] = threading.Lock()
    with _LADDER_CACHE["lock"]:
        v = _LADDER_CACHE["value"]
        if v is not None:
            return v
        d = _api_ladder()
        _LADDER_CACHE.update(value=d, at=time.time())
        try:
            cache_file.write_text(json.dumps(d, default=str))
        except Exception:  # noqa: BLE001
            pass
        return d
