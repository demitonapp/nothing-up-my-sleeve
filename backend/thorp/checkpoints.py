"""The fleet's checkpoints: which saved minds are needed, which are stale, and what the last cleanup freed.

S1 operations keeps the ships; a finished run's checkpoints are what can be sailed again (a seed, a teacher, a
chat, a re-score). They are also the largest thing on the Mac. This audit joins `data/checkpoints` to the ledger
and keeps, for each preset:

- the run at sea (or chartered) now;
- the latest finished run and the best finished run (the lowest unseen hole-card bpb);
- every run a queued spec reads from (seed, teacher, heads' donor).

Everything else that finished is superseded; everything that did not finish is stale. `clean` deletes only the
delete verdicts, never a run at sea or an unknown directory, and writes `data/checkpoint-cleanup.json` so the
Liberty Machine can show what it freed (12 November, Justin: "audit and review the checkpoints ... update them in
the liberty machine and then clean it up").
"""

from __future__ import annotations

import contextlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from thorp import paths

CLEANUP = "checkpoint-cleanup.json"
BEST_METRIC = "eval/hole-cards-unseen/bpb_mean"
RECENT_HOURS = 24  # a run finished today is not stale, even if a newer one of its class has landed


def root() -> Path:
    return paths.data_dir() / "checkpoints"


def _size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _latest_step(path: Path) -> int | None:
    import re

    steps = [int(m.group(1)) for p in path.iterdir() if (m := re.fullmatch(r"step-(\d+)", p.name))]
    return max(steps) if steps else None


def _preset(run: dict) -> str:
    try:
        return ((json.loads(run.get("spec_json") or "{}").get("model") or {}).get("preset")) or "?"
    except (TypeError, ValueError):
        return "?"


def _recent(run: dict) -> bool:
    """A finished run from the last `RECENT_HOURS`: kept so a fresh result is not culled before it is read."""
    try:
        finished = datetime.fromisoformat(str(run.get("finished") or "").replace("Z", "+00:00"))
        if finished.tzinfo is None:
            finished = finished.replace(tzinfo=UTC)
        return (datetime.now(UTC) - finished).total_seconds() < RECENT_HOURS * 3600
    except (TypeError, ValueError):
        return False


def _keeps(rec) -> tuple[dict[str, str], dict[str, str], set[str], set[str], set[str]]:
    """The reasons a run is kept: at sea, latest and best per preset, queue reads, and finished in the last day."""
    from thorp.viable.s2_coordination import charter as s2

    runs = {r["run_id"]: r for r in rec.query("select run_id,name,status,finished,started,spec_json from runs")}
    latest: dict[str, tuple[str, str]] = {}
    for r in runs.values():
        if r.get("status") != "finished":
            continue
        p = _preset(r)
        key = str(r.get("finished") or r.get("started") or "")
        if p not in latest or key > latest[p][0]:
            latest[p] = (key, r["run_id"])
    best: dict[str, tuple[float, str]] = {}
    for row in rec.query(
        "select run_id, min(value) v from metrics where name=? group by run_id", [BEST_METRIC]
    ):
        r = runs.get(row["run_id"])
        if not r or r.get("status") != "finished":
            continue
        p = _preset(r)
        if p not in best or row["v"] < best[p][0]:
            best[p] = (row["v"], r["run_id"])
    queue: set[str] = set()
    with contextlib.suppress(Exception):
        import yaml

        from thorp.viable.s2_coordination import queue_store

        for line in queue_store.lines():
            if line.get("kind") != "spec":
                continue
            p = paths.resolve(f"specs/{line['payload']}.yaml")
            if not p.exists():
                continue
            spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for ref in s2.related_runs(spec):
                row = rec.get_run_by_name(ref, finished=True)
                if row:
                    queue.add(row["run_id"])
    sea: set[str] = set()
    with contextlib.suppress(Exception):
        from thorp.viable.s2_coordination import queue_store

        sea.update(r["run_id"] for r in queue_store.at_sea() if r.get("run_id"))
    with contextlib.suppress(Exception):
        from thorp.viable.s3_control import charter as s3

        sea.update(h["run_id"] for h in s3.out_now() if h.get("run_id"))
    recent = {rid for rid, r in runs.items() if r.get("status") == "finished" and _recent(r)}
    return (
        {v[1]: f"the latest {p}" for p, v in latest.items()},
        {v[1]: f"the best {p}" for p, v in best.items()},
        queue,
        sea,
        recent,
    )


def audit() -> dict:
    """The current checkpoint set, each with a keep/delete verdict and the reason in words."""
    from thorp.ledger import reader

    rec = reader()
    runs = {r["run_id"]: r for r in rec.query("select run_id,name,status,finished,started,spec_json from runs")}
    latest, best, queue, sea, recent = _keeps(rec)
    base = root()
    entries = []
    for d in sorted(base.iterdir() if base.exists() else [], key=lambda p: p.name):
        if not d.is_dir():
            continue
        rid = d.name
        r = runs.get(rid) or {}
        reasons: list[str] = []
        if rid in sea:
            reasons.append("at sea now")
        if rid in latest:
            reasons.append(latest[rid])
        if rid in best:
            reasons.append(best[rid])
        if rid in queue:
            reasons.append("a queued voyage reads it")
        if rid in recent:
            reasons.append(f"finished in the last {RECENT_HOURS} h")
        if not r:
            reasons.append("not in the ledger: left alone")
        status = str(r.get("status") or "unknown")
        if reasons:
            verdict = "keep"
        elif status != "finished":
            verdict, reasons = "delete", [f"did not finish: {status}"]
        else:
            verdict, reasons = "delete", [f"superseded: not the latest or best {_preset(r)}"]
        entries.append(
            {
                "run_id": rid,
                "name": r.get("name") or rid,
                "preset": _preset(r) if r else "?",
                "status": status,
                "finished": r.get("finished"),
                "step": _latest_step(d),
                "bytes": _size(d),
                "verdict": verdict,
                "reasons": reasons,
            }
        )
    entries.sort(key=lambda e: (e["verdict"] != "delete", -e["bytes"], e["name"]))
    total = sum(e["bytes"] for e in entries)
    delete = sum(e["bytes"] for e in entries if e["verdict"] == "delete")
    try:
        disk = shutil.disk_usage(paths.ROOT)
        free = {"bytes": disk.free, "total": disk.total}
    except OSError:
        free = {"bytes": None, "total": None}
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "root": str(base),
        "count": len(entries),
        "bytes": total,
        "kept_bytes": total - delete,
        "delete_bytes": delete,
        "delete_count": sum(1 for e in entries if e["verdict"] == "delete"),
        "disk": free,
        "entries": entries,
    }


def last_cleanup() -> dict | None:
    p = paths.data_dir() / CLEANUP
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clean(apply: bool = True) -> dict:
    """Delete the entries the audit marks delete; never a run at sea or a directory the ledger does not know.
    Writes what it did to `data/checkpoint-cleanup.json`, which the Liberty Machine shows."""
    before = audit()
    deleted = []
    if apply:
        base = root()
        for e in before["entries"]:
            if e["verdict"] != "delete":
                continue
            target = base / e["run_id"]
            if not target.is_dir():
                continue
            try:
                shutil.rmtree(target)
            except OSError as err:  # a file that cannot go stays, and says why
                e["error"] = str(err)
                continue
            deleted.append({k: e[k] for k in ("run_id", "name", "preset", "status", "bytes", "reasons")})
        record = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "freed_bytes": sum(e["bytes"] for e in deleted),
            "deleted": deleted,
            "before": {"count": before["count"], "bytes": before["bytes"]},
        }
        p = paths.data_dir() / CLEANUP
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(record, indent=1), encoding="utf-8")
    after = audit()
    return {"before": before, "after": after, "deleted": deleted, "cleanup": last_cleanup()}


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m thorp.checkpoints", description=__doc__.split("\n\n")[0])
    ap.add_argument("what", nargs="?", default="audit", choices=["audit", "clean"])
    a = ap.parse_args(argv)
    if a.what == "clean":
        out = clean(apply=True)
        print(f"deleted {len(out['deleted'])} checkpoint(s), {out['cleanup']['freed_bytes'] / 1e9:.2f} GB freed")
        print(f"kept {out['after']['count'] - out['after']['delete_count']} checkpoint(s), {out['after']['kept_bytes'] / 1e9:.2f} GB")
        return 0
    a_ = audit()
    print(f"{a_['count']} checkpoint(s), {a_['bytes'] / 1e9:.2f} GB; {a_['delete_count']} stale, {a_['delete_bytes'] / 1e9:.2f} GB")
    for e in a_["entries"]:
        if e["verdict"] == "delete":
            print(f"  DELETE {e['bytes'] / 1e9:6.2f} GB {e['run_id'][:12]} {e['preset']:4} {e['name'][:60]} — {'; '.join(e['reasons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
