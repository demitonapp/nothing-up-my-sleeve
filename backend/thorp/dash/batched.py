"""The dashboard's slow readers, set-based (11 November, the architecture audit's item 7).

At 197 runs /api/ships, /api/compare and /api/bridge each took 37 to 40 s: they asked, run by run, for every row of a
prefix of names (`name like 'eval/%'`) over the run's whole metric history, to keep the last value of each name.
These answer the same payloads, value for value, from

- `s1.metric_latest` (one row a run and metric name, kept by triggers on s1.metrics) where only the last value is
  read, for every run in one query; and
- one query over exact (run_id, name) index ranges where a whole history is read (the compare page's curves), the
  names taken from `s1.metric_latest` instead of a filter over each run's rows.

`server.py` calls these when the ledger is Postgres; its SQLite paths stay as they were. `downsample` caps a series
for /api/metrics?points=.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from thorp import ledger_store


def last_scores(run_ids: list[str]) -> dict[str, dict[str, float]]:
    """server._last_scores: every run's latest eval/* and laws/* values, the newest row by (step, id) standing."""
    out: dict[str, dict[str, float]] = {r: {} for r in run_ids}
    for x in ledger_store.latest_rows(list(out), prefixes=("eval/", "laws/")):
        out[x["run_id"]][x["name"]] = x["value"]
    return out


def _latest_map(run_ids: list[str], names: set[str]) -> dict[tuple[str, str], float]:
    """{(run_id, name): newest value} for these exact names (server._metric, every run in one query)."""
    return {(x["run_id"], x["name"]): x["value"] for x in ledger_store.latest_rows(run_ids, names=tuple(sorted(names)))}


def _sets(spec: dict) -> list[str]:
    return [Path(s).stem for s in spec.get("eval", {}).get("sets", [])]


def runs() -> list[dict]:
    """server.api_runs: every run, newest first, with its preset, seed and the first held-out set's latest bpb mean."""
    rows = ledger_store.all_runs()
    want: dict[str, str] = {}
    for r in rows:
        spec = json.loads(r.pop("spec_json") or "{}")
        r["preset"] = spec.get("model", {}).get("preset")
        r["seed"] = spec.get("seed")
        sets = _sets(spec)
        if sets:
            want[r["run_id"]] = f"eval/{sets[0]}/bpb_mean"
    last = _latest_map(list(want), set(want.values()))
    for r in rows:
        name = want.get(r["run_id"])
        r["hole_bpb_mean"] = last.get((r["run_id"], name)) if name else None
    return rows


def _dedupe(rows: list[dict]) -> list[dict]:
    """A series' rows with the later row at one step standing (ledger_store.metric_series's rule)."""
    out: list[dict] = []
    for x in rows:
        if out and out[-1]["step"] == x["step"]:
            out[-1] = x
        else:
            out.append(x)
    return out


def compare() -> list[dict]:
    """server.api_compare: per run, the first eval set's bpb mean at each eval step with tokens seen, every held-out
    set's curve, and the push per layer and the learning rate. Six queries in all, not seven a run."""
    rows = ledger_store.all_runs()
    ids = [r["run_id"] for r in rows]
    plan = _latest_map(ids, {"plan/tokens_total", "plan/total_steps"})
    keep = []
    for r in rows:
        rid = r["run_id"]
        spec = json.loads(r.get("spec_json") or "{}")
        total = plan.get((rid, "plan/tokens_total"))
        steps = plan.get((rid, "plan/total_steps"))
        per_step = total / steps if total and steps else None
        sets = _sets(spec)
        if not sets or not per_step:
            continue
        keep.append((r, spec, sets, total, per_step))
    kept = [k[0]["run_id"] for k in keep]
    # the names each run carries, from the latest table: held-out bpb means, and the push per layer
    evals: dict[str, set[str]] = {}
    for x in ledger_store.latest_rows(kept, prefixes=("eval/",)):
        if x["name"].endswith("/bpb_mean"):
            evals.setdefault(x["run_id"], set()).add(x["name"])
    pushes: dict[str, set[str]] = {}
    for x in ledger_store.latest_rows(kept, prefixes=("grad_norm/layer_",)):
        if x["name"].count("/") <= 1:  # the per-layer norm, not its parts (the loop below drops those too)
            pushes.setdefault(x["run_id"], set()).add(x["name"])
    pairs: set[tuple[str, str]] = set()
    for r, _spec, sets, _total, _ps in keep:
        rid = r["run_id"]
        pairs |= {(rid, n) for n in evals.get(rid, ())} | {(rid, n) for n in pushes.get(rid, ())}
        pairs |= {(rid, f"eval/{sets[0]}/bpb_mean"), (rid, f"eval/{sets[0]}/bpb_mean_en"), (rid, "lr")}
    hist: dict[str, list[dict]] = {}
    for x in ledger_store.history_of_pairs(sorted(pairs)):
        hist.setdefault(x["run_id"], []).append(x)
    recipes = ledger_store.first_artifacts(kept, "recipe")
    out = []
    for r, _spec, sets, total, per_step in keep:
        rid = r["run_id"]
        h = hist.get(rid, [])
        first, first_en = f"eval/{sets[0]}/bpb_mean", f"eval/{sets[0]}/bpb_mean_en"
        series = _dedupe([x for x in h if x["name"] == first])
        en = _dedupe([x for x in h if x["name"] == first_en])
        by_set: dict[str, dict] = {}
        bpb_names = evals.get(rid, set())
        for x in h:
            if x["name"] not in bpb_names:
                continue
            d = by_set.setdefault(x["name"].split("/")[1], {"steps": [], "tokens": [], "bpb": []})
            if d["steps"] and d["steps"][-1] == x["step"]:
                d["bpb"][-1] = x["value"]
                continue
            d["steps"].append(x["step"])
            d["tokens"].append(x["step"] * per_step)
            d["bpb"].append(x["value"])
        push: dict[str, list] = {}
        push_names = pushes.get(rid, set())
        lr = _dedupe([x for x in h if x["name"] == "lr"])
        for x in [x for x in h if x["name"] in push_names] + lr:
            if x["name"].count("/") > 1:
                continue
            p = push.setdefault(x["name"], [[], []])
            p[0].append(x["step"])
            p[1].append(x["value"])
        recipe = recipes.get(rid)
        n_books = len(json.loads(recipe["text"])) if recipe and recipe["text"] else None
        spec = json.loads(r.get("spec_json") or "{}")
        out.append(
            {
                "run_id": rid,
                "name": r["name"],
                "ship": r.get("ship"),
                "preset": spec.get("model", {}).get("preset"),
                "seed": spec.get("seed"),
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


def bridge_rows(run_rows: list[dict]) -> list[dict]:
    """server.api_bridge's runs: each run's latest stars/bridge/* readings (oldest run first, as given)."""
    by_run: dict[str, list[dict]] = {}
    for x in ledger_store.latest_rows([r["run_id"] for r in run_rows], prefixes=("stars/bridge/",)):
        by_run.setdefault(x["run_id"], []).append(x)
    out = []
    for run in run_rows:
        rid = run["run_id"]
        rows = by_run.get(rid)
        if not rows:
            continue
        r = {
            "run_id": rid,
            "name": run["name"],
            "preset": json.loads(run["spec_json"] or "{}").get("model", {}).get("preset"),
            "layers": {},
        }
        for x in rows:  # in (step, id) order, as the history was read: the last row's step is the reading's
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
    return out


# ---------------------------------------------------------------- /api/metrics?names=&points=


def wanted(names: str, have) -> list[str]:
    """The metric names a `names=` asks for, among `have`: a comma list, where an entry ending in `*` is a prefix."""
    exact, prefixes = set(), []
    for n in (x.strip() for x in names.split(",")):
        if not n:
            continue
        if n.endswith("*"):
            prefixes.append(n[:-1])
        else:
            exact.add(n)
    return [h for h in have if h in exact or any(h.startswith(p) for p in prefixes)]


def downsample(steps: list, values: list, points: int) -> list[list]:
    """[steps, values] cut to about `points` points: evenly spaced over the series, always keeping the first, the
    last, the lowest and the highest (finite) value, so a chart's ends and extremes survive the cap. A series of
    `points` or fewer comes back as it is; with points < 4 the four kept points can exceed the cap."""
    n = len(steps)
    if points <= 0 or n <= points:
        return [steps, values]
    finite = [i for i, v in enumerate(values) if isinstance(v, (int, float)) and math.isfinite(v)]
    keep = {0, n - 1}
    if finite:
        keep.add(min(finite, key=lambda i: values[i]))
        keep.add(max(finite, key=lambda i: values[i]))
    budget = points - len(keep)
    if budget > 0:
        # `budget` interior points, evenly spaced between the ends
        for k in range(1, budget + 1):
            keep.add(round(k * (n - 1) / (budget + 1)))
    idx = sorted(keep)
    return [[steps[i] for i in idx], [values[i] for i in idx]]


def cap_of(points: str | int) -> int:
    """`points=` as a cap: a positive whole number, else no cap (0)."""
    try:
        return max(int(points or 0), 0)
    except (TypeError, ValueError):
        return 0


def metrics(run: str, names: str = "", points: str | int = "") -> dict:
    """server.api_metrics on Postgres with its optional bounds: `names` (a comma list, `prefix*` allowed) reads only
    those series, by their names in s1.metric_latest; `points` caps each series (downsample)."""
    if names:
        out = ledger_store.metrics_series_named(run, wanted(names, ledger_store.metric_names(run)))
    else:
        out = ledger_store.metrics_series(run)
    cap = cap_of(points)
    if cap > 0:
        out = {k: downsample(s[0], s[1], cap) for k, s in out.items()}
    return out
