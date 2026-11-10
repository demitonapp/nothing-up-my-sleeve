"""Export a voyage for another yard to verify (10 November): the federation seam. A contribution is one run's
row, its metrics, evals and artifact hashes, the spec's SHA and this yard's id, hashed into one bundle. It is
written to `data/contributions/<run_id>.json` and recorded in `s1.work`; nothing here is trusted — a NUMS
coordinator re-runs a sample and compares the hashes.

    uv run --project backend python -m thorp.contribute export <run_id>
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

OUT = Path("data/contributions")


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def export(run_id: str) -> dict:
    from thorp import store, yard
    from thorp.ledger import reader
    from thorp.viable.records import Work

    r = reader()
    run = (r.query("select * from runs where run_id=?", [run_id]) or [None])[0]
    if run is None:
        raise LookupError(f"no run {run_id}")
    # the latest reading per metric, not the whole trace: a contribution is the result, not the diary
    latest: dict[str, dict] = {}
    for m in r.query("select name, step, value from metrics where run_id=?", [run_id]):
        if m["name"] not in latest or m["step"] >= latest[m["name"]]["step"]:
            latest[m["name"]] = m
    metrics = [latest[k] for k in sorted(latest)]
    evals = r.query("select * from evals where run_id=? order by step", [run_id])
    # the hashes only: the content is content-addressed, so a verifier fetches it by hash
    artifacts = r.query("select kind, sha1 from artifacts where run_id=? order by kind, sha1", [run_id])
    artifact_root = hashlib.sha256(_canon(artifacts).encode()).hexdigest()
    yid = yard.ensure()
    bundle = {
        "yard": yid,
        "spec_sha": run.get("spec_sha") or run_id,
        "run": run,
        "metrics": metrics,
        "evals": evals,
        "artifacts": artifacts,
        "artifact_root": artifact_root,
        "exported": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    bundle["bundle_sha"] = hashlib.sha256(_canon({k: v for k, v in bundle.items() if k != "bundle_sha"}).encode()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{run_id}.json"
    p.write_text(json.dumps(bundle, indent=1, default=str))
    # provenance on the run row: the yard, the spec and the artifact root
    with store.session() as s:
        from thorp.ledger_store import Run as _Run

        rr = s.get(_Run, run_id)
        if rr is not None:
            rr.yard_id, rr.spec_sha, rr.artifact_root = yid, bundle["spec_sha"], artifact_root
    with store.session() as s:
        w = s.get(Work, run_id)
        if w is None:
            s.add(Work(work_id=run_id, spec_sha=bundle["spec_sha"], goal=run.get("ship") or "",
                       status="posted", claimed_by=yid, run_id=run_id, bundle_sha=bundle["bundle_sha"]))
        else:
            w.status, w.claimed_by, w.run_id, w.bundle_sha = "posted", yid, run_id, bundle["bundle_sha"]
    print(f"{run_id}: {len(metrics)} metrics, {len(evals)} evals, {len(artifacts)} artifacts -> {p}")
    print(f"bundle_sha {bundle['bundle_sha']}")
    return bundle


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "export":
        export(sys.argv[2])
    else:
        raise SystemExit("usage: python -m thorp.contribute export <run_id>")
