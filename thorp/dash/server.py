"""The dashboard: index.html plus JSON read straight from the ledger. Standard library only.

Endpoints: /api/runs, /api/metrics?run=, /api/evals?run=, and /api/run?run= (headline numbers,
latest samples, recipe composition and tokeniser stats, which the panels also need).
"""

from __future__ import annotations

import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from thorp import chinchilla, paths
from thorp.ledger import connect

INDEX = Path(__file__).with_name("index.html")


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
        f"select step, value from metrics where run_id=? and name=? order by step {order} limit 1",
        [run, name],
    )
    return r[0]["value"] if r else None


def api_runs() -> list[dict]:
    runs = _rows(
        "select run_id, name, status, started, finished, tokens_seen, wall_minutes,"
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
            "select name, step, value from metrics where run_id=? order by step", [run]
        )
        for name, step, value in cur:
            s = out.setdefault(name, [[], []])
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
        f" order by step {'desc' if latest else 'asc'} limit 1",
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

    for kind in ("samples", "top10", "recipe", "eval_sets"):
        a = _artifact(run, kind)
        out[kind] = (
            {"step": a["step"], **{"data": json.loads(a["text"])}} if a and a["text"] else None
        )
    t = _artifact(run, "tokeniser")
    if t:
        stats = Path(t["path"]) / "stats.json"
        out["tokeniser"] = {
            "id": t["sha1"],
            "stats": json.loads(stats.read_text()) if stats.exists() else None,
        }
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            routes = {
                "/api/runs": lambda: api_runs(),
                "/api/metrics": lambda: api_metrics(q["run"]),
                "/api/evals": lambda: api_evals(q["run"]),
                "/api/run": lambda: api_run(q["run"]),
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
