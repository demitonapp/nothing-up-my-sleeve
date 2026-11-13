"""A size's charter, its findings and its benchmarks, as the size page's Charters tab reads them (14 November 2026).

Justin, 14 November: "we have a base charter which has certain fields locked, then we have a rigged version which
maximises test scores no matter what and then we have an experiment, which proves things that are locked on the base";
"Those are the three every ship size gets". So a size has one charter, tried as a base (the control), experiment arms
(each naming the master charter rows it proves, `proves`) and rigged arms (read on their own test and bar). The base's
locked fields are the master charter's signatures for the class (dash/server.py `_base_fields`).

The rows are the store's (`s1.charters`, `s1.charter_variants`, `s1.size_findings`, `s1.size_benchmarks`, migration
f6b8d0e2a4c7). What this module adds is only what is read live, and it is read in Postgres:

- a variant's **state**, from its spec: `home` when a voyage of that name (or its other seeds, `-s2` ...) finished,
  `at sea`, `queued` when a queue line sails it, `laid` when the fitout is written, `designed` when none of these;
- a variant's **readings**: each of its voyages on the variant's reading (a rigged variant's own, else the charter's);
- a finding's **readings**: each voyage it names, on the finding's reading;
- a benchmark's **best**: the best reading by any finished voyage of the size or of its variant shapes (`300k-l3`),
  and how many were read.

    uv run python -m thorp.charters 300k
"""

from __future__ import annotations

import json
import sys
from typing import Any

from thorp import paths

# one voyage a name: its newest finished sailing, else its newest of any kind
_RUN = """
select distinct on (r.name) r.name, r.run_id, r.status, ml.value
from s1.runs r left join s1.metric_latest ml on ml.run_id = r.run_id and ml.name = :metric
where r.name = any(:names)
order by r.name, (r.status = 'finished') desc, r.started desc nulls last
"""

# a spec's voyages: the spec's own name and its other seeds
_SEEDS = """
select distinct on (r.name) r.name, r.run_id, r.status, ml.value
from s1.runs r left join s1.metric_latest ml on ml.run_id = r.run_id and ml.name = :metric
where r.name = :spec or (starts_with(r.name, :spec || '-s') and substr(r.name, length(:spec) + 3) ~ '^[0-9]+$')
order by r.name, (r.status = 'finished') desc, r.started desc nulls last
"""

# the best reading of each benchmark by a finished voyage of the size
_BEST = """
with mine as (
  select r.run_id, r.name from s1.runs r
  where r.status = 'finished' and r.spec_json is not null and r.spec_json like '{%'
    and ((r.spec_json::jsonb -> 'model' ->> 'preset') = :size or (r.spec_json::jsonb -> 'model' ->> 'preset') like :size || '-%')
)
select b.key, count(ml.value) as n,
  (array_agg(ml.value order by case when b.better = 'lower' then ml.value else -ml.value end) filter (where ml.value is not null))[1] as best,
  (array_agg(m.name order by case when b.better = 'lower' then ml.value else -ml.value end) filter (where ml.value is not null))[1] as best_run
from s1.size_benchmarks b
left join mine m on true
left join s1.metric_latest ml on ml.run_id = m.run_id and ml.name = b.metric
where b.size = :size
group by b.key
"""


def _rows(sql: str, **params: Any) -> list[dict]:
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        return [dict(r._mapping) for r in s.execute(text(sql), params)]


def _queued() -> set[str]:
    """The fitout names the queue sails, by their spec name."""
    names = set()
    for r in _rows("select payload from s2.queue_lines where kind = 'spec'"):
        names.add(str(r["payload"]).split("/")[-1].removesuffix(".yaml"))
    return names


def _laid(spec: str) -> bool:
    return any(paths.resolve("specs").rglob(f"{spec}.yaml"))


def _voyage(r: dict) -> dict:
    status = {"finished": "home", "running": "at sea"}.get(r["status"], str(r["status"] or "").split(":")[0])
    return {"name": r["name"], "run_id": r["run_id"], "status": status, "value": r["value"]}


def _state(spec: str | None, voyages: list[dict], queued: set[str]) -> str:
    if not spec:
        return "designed"
    if any(v["status"] == "home" for v in voyages):
        return "home"
    if any(v["status"] == "at sea" for v in voyages):
        return "at sea"
    if spec in queued:
        return "queued"
    return "laid" if _laid(spec) else "designed"


def read(size: str) -> dict:
    """The size's charters (each with its variants), findings and benchmarks, with their live readings."""
    queued = _queued()
    charters = _rows("select * from s1.charters where size = :size order by ordinal", size=size)
    variants = _rows(
        "select v.* from s1.charter_variants v join s1.charters c on c.key = v.charter where c.size = :size "
        "order by c.ordinal, v.ordinal",
        size=size,
    )
    for c in charters:
        c["drawn_at"] = c["drawn_at"].isoformat() if c.get("drawn_at") else None
        c["variants"] = []
        for v in (x for x in variants if x["charter"] == c["key"]):
            # a rigged variant is read on its own test, never on the base's reading
            v["metric"], v["better"] = v.get("metric") or c["metric"], v.get("better") or c["better"]
            voyages = [_voyage(r) for r in _rows(_SEEDS, spec=v["spec"], metric=v["metric"])] if v["spec"] else []
            v["voyages"] = voyages
            v["state"] = _state(v["spec"], voyages, queued)
            v["settings"] = v["settings"] if isinstance(v["settings"], list) else json.loads(v["settings"] or "[]")
            c["variants"].append(v)

    findings = _rows("select * from s1.size_findings where size = :size order by ordinal", size=size)
    for f in findings:
        names = list(f.get("runs") or [])
        got = {r["name"]: _voyage(r) for r in _rows(_RUN, names=names, metric=f["metric"] or "")} if names else {}
        f["readings"] = [got.get(n) or {"name": n, "run_id": None, "status": "not on the ledger", "value": None} for n in names]
        if not f["metric"]:
            for x in f["readings"]:
                x["value"] = None

    benchmarks = _rows("select * from s1.size_benchmarks where size = :size order by ordinal", size=size)
    best = {r["key"]: r for r in _rows(_BEST, size=size)}
    for b in benchmarks:
        got = best.get(b["key"]) or {}
        b["best"], b["best_run"], b["read_by"] = got.get("best"), got.get("best_run"), int(got.get("n") or 0)
    return {"size": size, "charters": charters, "findings": findings, "benchmarks": benchmarks}


def main(argv: list[str]) -> int:
    size = argv[0] if argv else "300k"
    d = read(size)
    for b in d["benchmarks"]:
        print(f"{b['name']}: best {b['best']} ({b['best_run']}, {b['read_by']} read) · bar {b['bar_model']} {b['bar_value']}")
    for f in d["findings"]:
        vals = ", ".join(f"{x['name']} {x['value'] if x['value'] is None else round(x['value'], 3)}" for x in f["readings"])
        print(f"[{f['status']}] {f['topic']}: {vals}")
    for c in d["charters"]:
        print(f"\n{c['name']}: {c['aim']}")
        for v in c["variants"]:
            print(f"  {v['name']}{' RIGGED' if v['rigged'] else ''} [{v['state']}] {[(x['name'], x['value']) for x in v['voyages']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
