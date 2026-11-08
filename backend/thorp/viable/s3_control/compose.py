"""S3 control composes a fitout's reading list from its declared selection (thorp/selection.py), and keeps the
record: the selection and its hash, the facts it was drawn from, the list it wrote and its sha1, the counts, the
funnel of rules, and the library prechecks of the gate (period, decks, stores) read on the list.

    uv run thorp select compose ogden-v0-2-declared            # a saved fitout's stage 1
    uv run thorp select compose ships/selections/x.json --dry-run
    uv run thorp select compose ogden-v0-2-declared --against lists/ogden-v0.2.csv   # the diff to a list

Deterministic: the same facts and selection write the same list, byte for byte. A composing never changes a
fitout's own shelf: it writes `lists/composed/<fitout>-<stage>.csv`, and the stage's `library` is pointed at it
only by the fitout's saved form (fitouts.save), which is Justin's to approve for any fitout that sails.
"""

from __future__ import annotations

import json
from pathlib import Path

from thorp import library_facts, paths, selection
from thorp.viable.s3_control import fitout_store


def _target(target: str, stage: int) -> tuple[str, int | None, dict, str]:
    """(fitout key, stage, selection, the fitout's opt-in) for a saved fitout's stage or a selection file."""
    p = Path(target)
    if target.endswith(".json") and paths.resolve(target).exists():
        d = json.loads(paths.resolve(target).read_text())
        return p.stem, None, d.get("compose", d), d.get("opt_in", "")
    from thorp import fitouts

    f = fitouts.load(target)
    if f is None:
        raise KeyError(f"no saved fitout or selection file {target!r}")
    st = f["stages"][stage - 1]
    if not st.get("compose"):
        raise LookupError(f"stage {stage} of {target} declares no selection (its library is listed by hand)")
    return f["key"], stage, st["compose"], f.get("opt_in", "")


def run(target: str, stage: int = 1, out: str | None = None, against: str = "", dry: bool = False, by: str = "", log=print) -> dict:
    key, ordinal, spec, opt_in = _target(target, stage)
    spec = selection.validate(spec)
    facts = library_facts.build()
    comp = selection.compose(spec, facts)
    lp = out or f"lists/composed/{key}{'-' + str(ordinal) if ordinal else ''}.csv"
    sha = ""
    if not dry:
        sha = selection.write_list(comp, lp)
    checks = selection.prechecks(lp, opt_in, key) if not dry else []
    summ = comp.summary()
    d = selection.diff(comp, against) if against else None
    passed = bool(checks) and all(c["passed"] for c in checks) if not dry else False
    log(f"{key}: facts {comp.facts_fingerprint}, selection {selection.spec_hash(spec)}: {summ['books']} books "
        f"({summ['library_books']} chosen + {summ['appended_books']} appended), {summ['words'] / 1e6:.1f}M words")  # fmt: skip
    for rule, n, what in comp.funnel:
        log(f"  {n:6d}  {rule}: {what}")
    for n in comp.notes:
        log(f"  note: {n}")
    for c in checks:
        log(f"  [{'pass' if c['passed'] else 'FAIL'}] {c['key']}: {c['value']:g} {c['name']}")
    if d:
        log(f"  against {against}: {d['composed']} composed, {d['list']} listed; only composed {d['only_composed']}; "
            f"only listed {d['only_list']}; same books {d['same_books']}, same order {d['same_order']}")  # fmt: skip
    rec = {
        "fitout_key": key, "ordinal": ordinal, "spec": spec, "spec_hash": selection.spec_hash(spec),
        "facts_fingerprint": comp.facts_fingerprint, "list_path": lp if not dry else "", "list_sha1": sha,
        "books": summ["books"], "words": summ["words"], "summary": summ,
        "funnel": [list(f) for f in comp.funnel], "notes": comp.notes, "prechecks": checks, "passed": passed,
        "against": against, "diff": d, "composed_by": by,
    }  # fmt: skip
    if not dry:
        rec["id"] = fitout_store.record_composition({k: v for k, v in rec.items()})
    return rec
