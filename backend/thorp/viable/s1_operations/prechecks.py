"""S1 operations: run a fitout's prechecks before it sails. Every item of every system (S5's cleaning standard,
S3*'s audit, S3's library, S2's tokeniser, S4's planned next steps) is read for the fitout as its voyages
will sail it, each reading is recorded in Postgres, and the fitout is marked ready when every required item
passes. The S3 gate (thorp/liberty_machine.py, policy 'prechecks') lets a voyage sail only when its fitout is ready.

    uv run python -m thorp.viable.s1_operations.prechecks ogden-v0-1
"""

from __future__ import annotations

import sys
import time

from thorp.viable.precheck_item import Context, Item


def items() -> list[Item]:
    from thorp.viable.s2_coordination import prechecks as s2
    from thorp.viable.s3_control import prechecks as s3
    from thorp.viable.s3star_audit import prechecks as s3star
    from thorp.viable.s4_intelligence import prechecks as s4
    from thorp.viable.s5_policy import prechecks as s5

    # S2 builds the shared tokeniser before S3 counts the library's tokens with it
    return [*s5.ITEMS, *s3star.ITEMS, *s2.ITEMS, *s3.ITEMS, *s4.ITEMS]


def _queued_specs(key: str) -> list[dict]:
    """The specs that sail the fitout: every queued (or written) voyage that names it."""
    import yaml

    from thorp import paths

    out = []
    for p in sorted(paths.resolve("specs").rglob("*.yaml")):
        try:
            s = yaml.safe_load(p.read_text()) or {}
        except Exception:  # noqa: BLE001
            continue
        f = s.get("fitout")
        if isinstance(f, dict) and f.get("key") == key:
            out.append(s)
    return out


def _fitout(key: str) -> dict:
    from thorp import fitouts, fleet

    f = fitouts.load(key) or (fitouts.from_curated(key) if key in fleet.FITOUTS else None)
    if f is None:
        raise KeyError(f"no fitout {key!r}")
    return f


def run(key: str, by: str = "", log=print) -> dict:
    from thorp import cleaning
    from thorp.viable.s3_control import fitout_store

    fitout_store.migrate()
    f = _fitout(key)
    specs = _queued_specs(key)
    if not specs:
        raise LookupError(f"no spec names the fitout {key!r}: nothing to check it for")
    ctx = Context(fitout=f, specs=specs)
    fitout_store.put_fitout(
        {**f, "clean": ctx.clean, "tokeniser": specs[0].get("tokeniser") or {}},
        adopted=f.get("adopted", ""),
    )
    its = [it for it in items() if it.applies(ctx)]
    fitout_store.put_items(its)
    for it in its:
        fitout_store.require(key, it.key, it.required)
    log(f"prechecks for {key}: {len(specs)} voyages, {len(ctx.books)} books, reads {ctx.clean} "
        f"(current {cleaning.CURRENT}); {len(its)} items")  # fmt: skip
    for it in its:
        t0 = time.time()
        try:
            value, evidence = it.run(ctx)
            ok = it.passes(value)
        except Exception as e:  # noqa: BLE001 (a precheck that cannot be read does not pass)
            value, evidence, ok = None, {"error": repr(e)}, False
        fitout_store.record(key, it.key, value, ok, {**evidence, "seconds": round(time.time() - t0, 1)}, by)
        mark = "pass" if ok else ("planned" if not it.required else "FAIL")
        shown = "-" if value is None else f"{value:.4g}"
        log(f"  [{it.system:3s}] {mark:7s} {it.key:26s} {shown:>10s} {it.comparator} {it.threshold:g}  {it.measure}")
    r = fitout_store.readiness(key) or {}
    fitout_store.set_status(key, "ready" if r.get("ready") else "draft")
    log(f"{key}: {r.get('passed')} of {r.get('required')} required prechecks pass; "
        f"{r.get('planned')} planned; {'READY to sail' if r.get('ready') else 'not ready'}")  # fmt: skip
    return r


if __name__ == "__main__":
    run(sys.argv[1], by=" ".join(sys.argv[2:]) or "thorp.viable.s1_operations.prechecks")
