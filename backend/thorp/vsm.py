r"""Thorp as a viable system (2026-11-07, Justin: "how do those types of rules get governed? We need to
implement Beer's VSM, making sure this codebase for running Thorp has the S1 to S5 units encoded into its
way of operating").

Stafford Beer's Viable System Model, mapped onto Thorp, each system with its members in the codebase:

- **S1, operations**: the expeditions (fleet.EXPEDITIONS) and the voyages (runs) they sail; each is an operation with its own
  goal, levers and stop rule. And acquisition, the books the voyages read: a viable system of its own, one
  level down (Beer's recursion), with its own S1 to S5 (thorp/acquisition.py: intakes, the intake lock, the
  intake gate and its audit, the sources, the rules).
- **S2, coordination**: what keeps the operations from colliding: one GPU and one standing queue
  (scripts/queue.sh), run ids, log folders, seeding order, the ledger; and the two Claude sessions (this one
  and the dashboard's) that share the files. `lint_queue()` finds collisions before they cost a run.
- **S3, control**: the gate every run passes (`gate(spec)`, called from train.prepare and the fitout
  builder): the enforced policies applied to the spec; and the bargain, a written opt-in (`data.opt_in`)
  that a policy admits. Every decision the gate makes is kept (`gate_log()`, s3.gate_decisions in Postgres).
  **S3\*, audit**: `audit()`, over the queue and the ledger, sporadic and independent of the gate
  (the night watches and steering tasks call it too).
- **S4, intelligence**: the outside world and the future: the competitors and the reference ladder
  (fleet.COMPETITORS, s4.outside_readings), the leaderboard and Smoking Qwen's forecast, the research the tests
  rest on.
- **S5, policy**: Thorp's identity: the POLICIES below, each adopted by Justin on a date, enforced or
  advisory; DECISIONS.md is S5's record. A policy changes only by a new entry there and here.

    uv run python -m thorp.vsm audit     # S3*: the whole system's state, S1 to S5
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from thorp import paths


@dataclass(frozen=True)
class System:
    key: str
    name: str
    purpose: str
    members: tuple[str, ...]


SYSTEMS: dict[str, System] = {
    s.key: s
    for s in (
        System(
            "S1",
            "Operations",
            "the expeditions and the voyages they sail; and acquisition, the books they read (a viable system of its own)",
            (
                "thorp/fleet.py EXPEDITIONS",
                "specs/",
                "data/runs/",
                "thorp/train.py",
                "thorp/train_torch.py",
                "thorp/acquisition.py",
                "thorp/gather.py",
                "thorp/viable/s1_operations/charter.py",
                "thorp/viable/s1_operations/vast.py",
            ),
        ),
        System(
            "S2",
            "Coordination",
            "keep the operations from colliding: one GPU, one queue, shared files",
            (
                "scripts/queue.sh",
                "specs/queue.txt",
                "thorp/ledger.py",
                "data/ships.json",
                "thorp/vsm.py lint_queue",
                "thorp/viable/s2_coordination/charter.py",
            ),
        ),
        System(
            "S3",
            "Control",
            "the gate every run passes, the opt-in bargain, and the audit (S3*)",
            (
                "thorp/vsm.py gate, audit",
                "thorp/stores.py",
                "tests/",
                "thorp/viable/s3_control/charter.py",
                "thorp/viable/s3star_audit/charter.py",
            ),
        ),
        System(
            "S4",
            "Intelligence",
            "the outside world and the future: competitors, forecasts, research",
            (
                "thorp/fleet.py COMPETITORS, REFERENCE_LADDER",
                "thorp/sources/catalog.py",
                "thorp/sources/bulk.py",
                "s4.outside_readings",
                "thorp/leaderboard.py",
                "thorp/smoking_qwen.py",
                "thorp/knockout.py",
                "thorp/viable/s4_intelligence/market.py",
            ),
        ),
        System(
            "S5",
            "Policy",
            "Thorp's identity: the rules, adopted by Justin, recorded in DECISIONS.md",
            ("thorp/vsm.py POLICIES", "DECISIONS.md", "thorp/viable/s5_policy/charter.py"),
        ),
    )
}


@dataclass(frozen=True)
class Policy:
    key: str
    statement: str
    adopted: str  # when and by whom ("2026-11-07 15:55, Justin")
    enforced: bool  # True: the gate refuses a run that breaks it; False: the audit reports it
    check: Callable[[dict], list[str]] = field(compare=False, hash=False)  # spec -> violations
    opt_in: bool = False  # whether data.opt_in (a reason, in words) admits a run that breaks it


def _reads(spec: dict) -> list[str]:
    from thorp import stores

    return stores.reads(spec)


def _decks_refused(spec: dict) -> list[str]:
    """No book of a held-out deck (the hole cards, the Forgotten Tomes) is in a list the run reads,
    unless the run refuses that deck (train.prepare then drops it)."""
    import csv

    refused = set(spec.get("data", {}).get("refuse") or [])
    held = {}
    for deck in ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"):
        p = paths.resolve(deck)
        if deck not in refused and p.exists():
            with p.open() as f:
                held |= {r["title"].strip().lower(): deck for r in csv.DictReader(f)}
    bad = []
    for lp in _reads(spec):
        p = paths.resolve(lp)
        if p.exists():
            with p.open() as f:
                bad += [
                    f"{lp} has {r['title']!r} from {held[k]}"
                    for r in csv.DictReader(f)
                    if (k := r["title"].strip().lower()) in held
                ]
    return bad[:10]


@functools.cache
def _deaths() -> dict[str, int]:
    """Each Gutenberg book's latest author death year, from the catalogue."""
    import csv
    import re

    cat = paths.data_dir() / "catalogue" / "pg_catalog.csv"
    out: dict[str, int] = {}
    if cat.exists():
        with cat.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                ys = [int(y) for y in re.findall(r"\d{4}-(\d{4})", r["Authors"])]
                if ys:
                    out[f"pg{r['Text#']}"] = max(ys)
    return out


def _period_only(spec: dict) -> list[str]:
    """Every book a run reads is period public domain: in the manifest, English, and (for Gutenberg books)
    every author in the catalogue dead by 1955."""
    import csv

    from thorp import manifest

    deaths = _deaths()
    bad = []
    for lp in _reads(spec):
        p = paths.resolve(lp)
        if not p.exists():  # a missing list fails in train.prepare itself
            continue
        with p.open() as f:
            for row in csv.DictReader(f):
                t = row.get("text") or ""
                bid = (
                    t[6:]
                    if t.startswith("local:")
                    else ("pg" + t.split(":", 1)[1] if t.startswith("gutenberg:") else None)
                )
                if bid is None:
                    continue
                b = manifest.get(bid)
                if b is not None and (b.language or "en") != "en":
                    bad.append(f"{lp}: {bid} is not English")
                if bid in deaths and deaths[bid] > 1955:
                    bad.append(f"{lp}: {bid} has an author who died in {deaths[bid]}")
    return bad[:10]


def _stores(spec: dict) -> list[str]:
    from thorp import stores

    try:
        stores.check({**spec, "data": {**spec.get("data", {}), "opt_in": ""}}, always=True)
    except stores.StoresRuleError as e:
        return [str(e)]
    return []


def _sop_names_a_standard(spec: dict) -> list[str]:
    """S5 'sop': a voyage that names an SOP version is held to that version (thorp/sop.py)."""
    from thorp import sop

    return sop.check(spec)


def _pre_registered(spec: dict) -> list[str]:
    """An operation's voyages belong to an expedition written up in DECISIONS.md before they sail."""
    from thorp import fleet

    v = fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
    if v is None:
        return ["belongs to no expedition"]
    return []


def _cleaned(spec: dict) -> list[str]:
    """A new voyage reads text cleaned by the current version (thorp/cleaning.py CURRENT), its held-out
    decks cleaned the same way (they share its tokeniser, so this holds by construction)."""
    from thorp import cleaning

    try:
        v = cleaning.version_of(spec)
    except ValueError as e:
        return [str(e)]
    if v != cleaning.CURRENT:
        return [f"reads {v} text, not {cleaning.CURRENT} (data.clean)"]
    return []


def _needs_a_standard(spec: dict) -> list[str]:
    """Every voyage names an SOP version (9 November, Justin: "does it hold that any voyage needs to have a SOP version?
    and a ship size?"). The size is the model preset, which the trainer cannot sail without; the SOP names everything
    else — content, tokeniser, parameters, phases and depth. A voyage queued before the rule was made is in
    `specs/pre-sop.txt` and sails as it was queued (the cutover Justin set: "all voyages prior to the next one queued
    sailed without SOP"). Nothing new may be added to that list: a voyage without a standard is an experiment, not a
    ship's voyage."""
    if not (spec.get("model") or {}).get("preset"):
        return ["names no model preset: a voyage must name the ship's size"]
    version = spec.get("sop")
    if version:
        from thorp import sop as _sop

        if _sop.standard(str(version)) is None:
            return [f"names SOP v{version}, which does not exist (have: {', '.join(_sop.versions())})"]
        return []
    from thorp import paths

    f = paths.resolve("specs/pre-sop.txt")
    grandfathered = {x.strip() for x in f.read_text().splitlines() if x.strip() and not x.startswith("#")} if f.exists() else set()
    if str(spec.get("name") or "") in grandfathered:
        return []
    return ["names no SOP version: every voyage is built to a standard (sop: '0.0.5')"]


def _named_fitout(spec: dict) -> list[str]:
    """Every voyage names the fitout it is a variation of (`fitout: {key, variation}` in its spec), and that fitout
    exists (fleet.FITOUTS or data/fitouts/). Named in the spec, never inferred at the gate.

    **The fitout is retired in favour of the SOP** (9 November, Justin: "fitout is retired in favour of SOP's"). A
    voyage that names an SOP version names its content, tokeniser, parameters and phases there, so the SOP version is
    what the gate checks; the fitout is only a legacy label and is not required when an SOP is named."""
    from thorp import fleet, sop

    f = spec.get("fitout")
    key = f.get("key") if isinstance(f, dict) else None
    version = spec.get("sop")
    if not key:
        if version and sop.standard(str(version)) is not None:
            return []  # the SOP names the content: the fitout is not needed
        return ["names no fitout and no SOP version (fitout: {key, variation}, or sop: '0.0.6')"]
    if fleet.named_fitout(key) is None:
        return [f"names the fitout {key!r}, which does not exist"]
    return []


OGDEN = "ogden"  # the Ogden fitout and its versions (ogden, ogden-v0-1, ...): thorp/ogden.py, fleet EXPEDITIONS["ogden"]


def _ogden_only(spec: dict) -> list[str]:
    """Only Ogden reads sail (Justin, 2026-11-07 19:30; from 9 November the SOP names the content): a voyage's fitout
    is Ogden or a version of it, or the SOP version it names reads Ogden's list."""
    from thorp import sop as sopmod

    f = spec.get("fitout")
    key = (f.get("key") if isinstance(f, dict) else None) or ""
    if key == OGDEN or key.startswith(OGDEN + "-"):
        return []
    std = sopmod.standard(str(spec.get("sop"))) if spec.get("sop") else None
    if std and str((std.get("content") or {}).get("recipe", "")).endswith("ogden-v0.1.csv"):
        return []
    return [
        f"sails on the fitout {key!r}" if key else "names no fitout",
        "only the Ogden fitout sails",
    ]


def _prechecked(spec: dict) -> list[str]:
    """A voyage sails only when its fitout's prechecks pass (Justin, 2026-11-07 19:45: "a fitout can have precheck
    items ... and then let's set sail"): the fitout is ready in the Postgres fitout store (thorp/viable/), and
    the voyage reads the cleaning its fitout was checked on. When the store cannot be reached, it refuses:
    an unchecked fitout does not sail."""
    from thorp import cleaning

    f = spec.get("fitout")
    key = f.get("key") if isinstance(f, dict) else None
    if not key:
        from thorp import sop as _sop

        if spec.get("sop") and _sop.standard(str(spec["sop"])) is not None:
            return []  # the SOP's own check judges the content: the fitout's prechecks are not needed
        return ["names no fitout to check"]
    try:
        from thorp.viable.s3_control import fitout_store

        r = fitout_store.readiness(key)
        rows = fitout_store.fitouts()
    except Exception as e:  # noqa: BLE001
        return [
            f"the fitout store cannot be read ({e.__class__.__name__}): its prechecks are unknown"
        ]
    if not r:
        return [
            f"the fitout {key!r} has no prechecks (python -m thorp.viable.s1_operations.prechecks {key})"
        ]
    if not r.get("ready"):
        return [
            f"the fitout {key!r} is not ready: {r.get('outstanding')} of {r.get('required')} prechecks outstanding"
        ]
    checked = next((x["clean"] for x in rows if x["key"] == key), None)
    if checked and checked != cleaning.version_of(spec):
        return [f"reads {cleaning.version_of(spec)} text, but its fitout was checked on {checked}"]
    return []


def _chartered(spec: dict) -> list[str]:
    """A voyage asking for a hired GPU keeps the charter's terms (thorp/viable/s5_policy/charter.py)."""
    from thorp.viable.s5_policy import charter

    return charter.check(spec)


POLICIES: dict[str, Policy] = {
    p.key: p
    for p in (
        Policy(
            "standard",
            "Every voyage is built to an SOP version and names the ship's size: the size is the shape, the "
            "standard is everything else. A voyage queued before the rule was made is in specs/pre-sop.txt and "
            "sails as it was queued; nothing new may be added to that list.",
            "2026-11-09, Justin",
            True,
            _needs_a_standard,
        ),
        Policy(
            "decks",
            "Every run refuses the held-out decks (the hole cards and the Forgotten Tomes), so no "
            "score is on a book it read.",
            "2026-11-06, Justin",
            True,
            _decks_refused,
        ),
        Policy(
            "period",
            "Thorp reads pre-1930 public-domain English only: every author dead by 1955 (the legal "
            'rule) and nothing modern ("period only").',
            "2026-11-07 14:35, Justin",
            True,
            _period_only,
        ),
        Policy(
            "stores",
            "A run reads the ship's stores (the prose stores or the trigram stores) or opts out in "
            "words.",
            "2026-11-07 15:55, Justin",
            False,
            _stores,
            opt_in=True,
        ),
        Policy(
            "expedition",
            "Every voyage belongs to an expedition, written up (goal, levers, rule) in DECISIONS.md "
            "before it sails.",
            "2026-11-07, Justin",
            False,
            _pre_registered,
        ),
        Policy(
            "clean",
            "Thorp reads text cleaned by a named version, the current one (unwrap-v2: Gutenberg's hard "
            "wraps joined back into paragraphs, verse kept line for line), and is scored on held-out "
            "books cleaned the same way; a voyage on other text opts out in words.",
            "2026-11-07 18:45, Justin",
            True,
            _cleaned,
            opt_in=True,
        ),
        Policy(
            "fitout",
            "No voyage sails without a named fitout: every spec names the fitout it is a variation of, "
            "and that fitout exists.",
            "2026-11-07 18:10, Justin",
            True,
            _named_fitout,
        ),
        Policy(
            "sop",
            "A voyage is built to the SOP version it names: the same content, tokeniser and size parameters, and "
            "the standard's cards in the standard's order. A declared departure is recorded, not refused; a voyage "
            "that names no version is not stopped by this policy (the cutover is Justin's to set).",
            "2026-11-08 20:20, Justin",
            False,
            _sop_names_a_standard,
        ),
        Policy(
            "ogden",
            "Only the Ogden fitout sails: every new voyage is a variation of Ogden (or a later version of "
            'it); everything else was taken off the queue ("everything going forward only runs the ogden '
            'fitout").',
            "2026-11-07 19:30, Justin",
            True,
            _ogden_only,
        ),
        Policy(
            "charter",
            "A voyage sails on a hired GPU only within the charter's terms: a class the terms hire at or under its "
            "ceiling an hour, a datacenter-verified and reliable host, the quote within one voyage's budget and "
            "the week's, the account's credit covering it, and no more ships out than the terms allow "
            "(thorp/viable/s5_policy/charter.py; S5 sets the numbers in s5.charter_terms, `thorp s5 term`).",
            "2026-11-08, Justin (Vast.ai chosen; the terms adopted as proposed)",
            True,
            _chartered,
        ),
        Policy(
            "prechecks",
            "A voyage sails only when its fitout's prechecks pass: each item measured and recorded in the "
            "fitout store (Postgres), every required one passing, the voyage reading the cleaning its fitout "
            "was checked on.",
            "2026-11-07 19:45, Justin",
            True,
            _prechecked,
        ),
    )
}


class GateRefused(ValueError):
    pass


def _enforcement() -> dict:
    """S5's switches ({key: true|false}, s5.policy_switches), over each policy's default. A hired box reads them
    from its papers (thorp/store.py)."""
    from thorp import store

    if store.papers():
        return dict(store.read_papers().get("switches") or {})
    from sqlalchemy import select

    from thorp.viable.records import PolicySwitch

    with store.session() as s:
        return {r.policy: r.enforced for r in s.scalars(select(PolicySwitch))}


def set_switch(key: str, enforced_: bool, words: str) -> None:
    """S5 switches a policy on or off, in Justin's words (s5.policy_switches)."""
    from thorp import store
    from thorp.viable.records import PolicySwitch

    if key not in POLICIES and key != "intake":
        raise KeyError(f"no policy {key!r}; the policies: {sorted(POLICIES)}")
    with store.session() as s:
        s.merge(PolicySwitch(policy=key, enforced=enforced_, words=words))


def enforced(key: str) -> bool:
    return bool(_enforcement().get(key, POLICIES[key].enforced))


def except_policy(
    policy: str,
    *,
    reason: str,
    adopted: str,
    runs: tuple[str, ...] = (),
    patterns: tuple[str, ...] = (),
    extra: dict | None = None,
) -> int:
    """S5 writes an exception: the runs a policy does not govern, by name or by glob, and why (s5.policy_exceptions;
    was the exceptions in policies.json). The reason and the adoption are kept, so a reader can see whose word let
    the run through. Returns how many runs and patterns the exception now covers."""
    from thorp import store
    from thorp.viable.records import PolicyException, PolicyExceptionMatch

    if policy not in POLICIES and policy != "intake":
        raise KeyError(f"no policy {policy!r}; the policies: {sorted(POLICIES)}")
    want = [("run", x) for x in runs] + [("pattern", x) for x in patterns]
    with store.session() as s:
        r = s.get(PolicyException, policy)
        if r is None:
            r = PolicyException(policy=policy)
            s.add(r)
        r.reason, r.adopted, r.extra = reason, adopted, extra or {}
        r.matches = [
            PolicyExceptionMatch(kind=k, value=v, ordinal=i)
            for i, (k, v) in enumerate(dict.fromkeys(want))
        ]
    return len(want)


def _exceptions() -> dict:
    """S5's written exceptions ({key: {"reason", "adopted", "runs": [names], "patterns": [globs]}}, from
    s5.policy_exceptions and its matches): the runs a policy does not govern, by name, with the reason. A hired box
    reads them from its papers."""
    from thorp import store

    if store.papers():
        return dict(store.read_papers().get("exceptions") or {})
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from thorp.viable.records import PolicyException

    with store.session() as s:
        out = {}
        for e in s.scalars(select(PolicyException).options(selectinload(PolicyException.matches))):
            d = {"reason": e.reason, "adopted": e.adopted, "runs": [m.value for m in e.matches if m.kind == "run"],
                 **(e.extra or {})}  # fmt: skip
            if pats := [m.value for m in e.matches if m.kind == "pattern"]:
                d["patterns"] = pats
            out[e.policy] = d
        return out


def excepted(key: str, spec: dict) -> str:
    import fnmatch

    e = _exceptions().get(key) or {}
    n = spec.get("name") or ""
    hit = n in set(e.get("runs") or []) or any(
        fnmatch.fnmatch(n, p) for p in e.get("patterns") or []
    )
    return e.get("reason", "") if hit else ""


def gate(spec: dict, known_run: bool = False, *, where: str = "voyage") -> list[str]:
    """S3: every enforced policy applied to a new run; refuse on a violation (unless the policy admits a
    written opt-in and the spec has one). Returns the advisory findings, for the log. Every decision is
    kept in the gate's log (`gate_log()`), with where it was asked (a voyage sailing, the fitout builder)."""
    if known_run:
        return []
    notes, decisions = [], []
    opt_in = (spec.get("data", {}).get("opt_in") or "").strip()
    for key, pol in POLICIES.items():
        found = pol.check(spec)
        if not found:
            continue
        if why := excepted(key, spec):
            notes.append(f"policy '{key}' does not govern this run: {why}")
            decisions.append({"policy": key, "how": "excepted", "why": why})
            continue
        if enforced(key) and not (pol.opt_in and opt_in):
            decisions.append({"policy": key, "how": "refused", "why": "; ".join(found)})
            _record_gate(spec, where, "refused", decisions)
            raise GateRefused(f"S3 gate, policy '{key}' ({pol.statement}): {'; '.join(found)}")
        bargain = pol.opt_in and bool(opt_in)
        notes.append(
            f"policy '{key}'" + (f" opted out: {opt_in}" if bargain else f": {'; '.join(found)}")
        )
        decisions.append(
            {
                "policy": key,
                "how": "bargain" if bargain else "advisory",
                "why": opt_in if bargain else "; ".join(found),
            }
        )
    _record_gate(spec, where, "passed", decisions)
    return notes


def gate_refusals(spec: dict) -> list[str]:
    """S3's verdict on a spec, without recording it and without raising (gate's twin, read-only). For a question
    asked away from the helm — S4's backlog audit — which must not write gate-log rows for voyages that never
    sail. Returns the refusals `gate` would raise on; an advisory is not one (a policy that is switched off, or
    admits a written opt-in, does not stop a voyage)."""
    refusals = []
    opt_in = (spec.get("data", {}).get("opt_in") or "").strip()
    for key, pol in POLICIES.items():
        try:
            found = pol.check(spec)
        except Exception as e:  # noqa: BLE001 — a check that cannot be read refuses, never passes
            refusals.append(f"policy '{key}' could not be read: {e}")
            continue
        if not found or excepted(key, spec):
            continue
        if enforced(key) and not (pol.opt_in and opt_in):
            refusals.append(f"policy '{key}' refused: {'; '.join(found)}")
    return refusals


def gate_one(key: str, spec: dict, *, where: str) -> list[str]:
    """S3 asks one policy of a spec, as `gate` asks them all (a charter's quote is checked by 'charter' alone, so a
    voyage resumed on a hired GPU is not re-judged by policies adopted after it first sailed). Refuses when the
    policy is enforced and broken; the decision is kept in the gate's log."""
    pol = POLICIES[key]
    found = pol.check(spec)
    if not found:
        _record_gate(spec, where, "passed", [{"policy": key, "how": "kept"}])
        return []
    if why := excepted(key, spec):
        _record_gate(spec, where, "passed", [{"policy": key, "how": "excepted", "why": why}])
        return [f"policy '{key}' does not govern this run: {why}"]
    if enforced(key):
        _record_gate(
            spec, where, "refused", [{"policy": key, "how": "refused", "why": "; ".join(found)}]
        )
        raise GateRefused(f"S3 gate, policy '{key}' ({pol.statement}): {'; '.join(found)}")
    _record_gate(
        spec, where, "passed", [{"policy": key, "how": "advisory", "why": "; ".join(found)}]
    )
    return [f"policy '{key}': {'; '.join(found)}"]


GATE_TIME = (
    "%Y-%m-%dT%H:%M:%S"  # the gate's clock, this Mac's local time, as the log has always been read
)


def _record_gate(spec: dict, where: str, verdict: str, decisions: list[dict]) -> None:
    """S3's record: one row per decision of the gate (s3.gate_decisions, each policy's part beside it). A decision
    that cannot be recorded is not made: if the store is down this raises, and the voyage does not sail. On a hired
    box the line goes beside its papers, brought home when it docks."""
    from thorp import store

    line = {
        "at": time.strftime(GATE_TIME),
        "name": spec.get("name"),
        "ship": spec.get("ship"),
        "where": where,
        "verdict": verdict,
        "decisions": decisions,
    }
    if store.papers():
        with store.papers_log().open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return
    insert_gate_decision(line)


def _gate_at(at: str):
    from datetime import datetime

    d = datetime.fromisoformat(at)
    return d if d.tzinfo else d.astimezone()  # a naive time is this Mac's local time


def insert_gate_decision(line: dict, *, source: str = "here", once: bool = False) -> int:
    """One gate decision (the log's line shape) into the store; with `once`, skipped if already there. Returns
    the number written (0 or 1)."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import GateDecision, GatePolicyDecision

    at = _gate_at(line["at"])
    with store.session() as s:
        if once and s.scalar(
            select(GateDecision.id).where(
                GateDecision.at == at,
                GateDecision.name.is_not_distinct_from(line.get("name")),
                GateDecision.place == line.get("where", "voyage"),
                GateDecision.verdict == line["verdict"],
            )
        ):
            return 0
        d = GateDecision(at=at, name=line.get("name"), ship=line.get("ship"), place=line.get("where", "voyage"),
                         verdict=line["verdict"], source=source)  # fmt: skip
        d.policies = [
            GatePolicyDecision(
                ordinal=i, policy=x.get("policy", ""), how=x.get("how", ""), why=x.get("why")
            )
            for i, x in enumerate(line.get("decisions") or [])
        ]
        s.add(d)
    return 1


def gate_log(limit: int = 60) -> list[dict]:
    """The gate's latest decisions, newest first, in the log's line shape."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from thorp import store
    from thorp.viable.records import GateDecision

    with store.session() as s:
        rows = s.scalars(
            select(GateDecision).options(selectinload(GateDecision.policies))
            .order_by(GateDecision.at.desc(), GateDecision.id.desc()).limit(limit)
        ).all()  # fmt: skip
        return [
            {
                "at": r.at.astimezone().strftime(GATE_TIME),
                "name": r.name,
                "ship": r.ship,
                "where": r.place,
                "verdict": r.verdict,
                "decisions": [
                    {
                        "policy": p.policy,
                        "how": p.how,
                        **({"why": p.why} if p.why is not None else {}),
                    }
                    for p in r.policies
                ],
            }
            for r in rows
        ]


# S2's helm: one GPU, so one voyage at sea at a time (Justin, 16:35: "surely only one can be running at
# a time ... this should be coordinated by S2"). Every voyage (train.run) and every GPU-heavy job takes the
# helm; a second waits in port until the first comes home. Expeditions can be under way together (their
# voyages queued); only one voyage is at sea.


def helm_slots() -> int:
    """How many seats the helm has (9 November, Justin: "run the first 3 concurrently"). One unless the
    lane sets THORP_HELM_SLOTS; every seat is its own lock, its own record, its own s2.helm row."""
    try:
        return max(1, int(os.environ.get("THORP_HELM_SLOTS", "1")))
    except ValueError:
        return 1


def _helm_paths(slot: int = 0):
    d = paths.data_dir()
    if slot:
        return d / f"helm-{slot}.lock", d / f"helm-{slot}.json"
    return (
        d / "helm.lock",
        d / "helm.json",
    )  # helm.json only on a hired box (its papers); at home, s2.helm


def _helm_write(rec: dict | None, pid: int, who, slot: int = 0) -> None:
    """Who holds the helm, recorded (s2.helm at home; beside the lock on a box); `rec` None releases our record."""
    from thorp import store

    if store.papers():
        if rec is not None:
            who.write_text(json.dumps(rec))
        else:
            with contextlib.suppress(Exception):
                if json.loads(who.read_text()).get("pid") == pid:
                    who.unlink()
        return
    from datetime import datetime

    from sqlalchemy import delete

    from thorp.viable.records import Helm

    key = "mac" if slot == 0 else f"mac:{slot}"
    with store.session() as s:
        if rec is None:
            s.execute(delete(Helm).where(Helm.helm == key, Helm.pid == pid))
        else:
            s.merge(Helm(helm=key, name=rec["name"], kind=rec["kind"], pid=rec["pid"],
                         since=datetime.strptime(rec["since"], GATE_TIME).astimezone()))  # fmt: skip


def _helm_read(who, slot: int = 0) -> dict | None:
    from thorp import store

    if store.papers():
        return json.loads(who.read_text())
    from thorp.viable.records import Helm

    with store.session() as s:
        r = s.get(Helm, "mac" if slot == 0 else f"mac:{slot}")
        return (
            {
                "name": r.name,
                "kind": r.kind,
                "pid": r.pid,
                "since": r.since.astimezone().strftime(GATE_TIME),
            }
            if r
            else None
        )


@contextlib.contextmanager
def at_sea(name: str, kind: str = "voyage", log=print):
    """Take the helm for `name` (blocking until it is free), hold it while the body runs."""
    import fcntl

    slot = int(os.environ.get("THORP_HELM_SLOT", "0") or 0)
    lock, who = _helm_paths(slot)
    lock.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock, "a+")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            holder = helm() or {}
            log(
                f"S2: in port, waiting for the helm ({holder.get('name')} is at sea since {holder.get('since')})"
            )
            fcntl.flock(f, fcntl.LOCK_EX)
        _helm_write(
            {"name": name, "kind": kind, "pid": os.getpid(), "since": time.strftime(GATE_TIME)},
            os.getpid(),
            who,
            slot,
        )
        yield
    finally:
        try:
            _helm_write(None, os.getpid(), who, slot)
        finally:
            f.close()  # releases the lock, even if the record could not be cleared


def helms(seats: int | None = None) -> list[dict]:
    """Every seat at sea now, in slot order. `seats` overrides the environment: the dashboard reads the
    lane's count from Postgres, which the coordinator wrote (9 November)."""
    import fcntl

    out = []
    for slot in range(seats or helm_slots()):
        lock, who = _helm_paths(slot)
        if not lock.exists():
            continue
        with open(lock, "a+") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                from thorp import store

                try:
                    rec = _helm_read(who, slot)
                except store.StoreDown:
                    raise
                except Exception:  # noqa: BLE001  (a box's helm.json half-written)
                    rec = None
                rec = {**(rec or {"name": "(unknown)", "kind": "?", "since": None}), "slot": slot}
                # a seat whose process is gone is stale: a killed run leaves its lock behind, and the
                # dashboard was listing dead voyages as at sea (9 November)
                pid = rec.get("pid")
                alive = False
                if pid:
                    try:
                        os.kill(int(pid), 0)
                        alive = True
                    except Exception:  # noqa: BLE001
                        alive = False
                if alive or not pid:
                    out.append(rec)
            else:
                fcntl.flock(f, fcntl.LOCK_UN)
    return out


def helm() -> dict | None:
    """Who is at sea now: the first seat holding the helm, or None when every seat is free."""
    seats = helms()
    return seats[0] if seats else None


def expedition_states() -> dict[str, str]:
    """Each expedition's state as S2 sees it, from the helm and the queue (not the declared status):
    'at sea' (its voyage holds the helm: at most one), 'under way' (voyages queued), and otherwise its
    declared state: 'home' (done), 'in port' (planned), 'paused', or 'awaiting orders' (declared running
    with nothing at sea and nothing queued: stalled, or finished and not yet closed)."""
    import yaml

    from thorp import fleet

    h = helm()
    sea = None
    if h and h.get("kind") == "voyage":
        sea = fleet.expedition_of_label(h["name"], _label_of(h["name"]))
    elif h is None:  # a voyage launched before the helm existed
        from thorp.ledger import reader

        for r in reader().query("select name, ship from runs where status='running'"):
            if _sailing_without_helm(r["name"]):
                sea = fleet.expedition_of_label(r["name"], r["ship"])
    q = paths.resolve("specs/queue.txt")
    under = set()
    for ln in q.read_text().splitlines():
        ln = ln.strip()
        if (
            ln
            and not ln.startswith(("#", "cmd:"))
            and (p := paths.resolve(f"specs/{ln}.yaml")).exists()
        ):
            spec = yaml.safe_load(p.read_text())
            under.add(fleet.expedition_of_label(spec.get("name"), spec.get("ship")))
    out = {}
    for k, e in fleet.EXPEDITIONS.items():
        out[k] = (
            "at sea"
            if k == sea
            else "under way"
            if k in under
            else {"done": "home", "planned": "in port", "paused": "paused"}.get(
                e.status, "awaiting orders"
            )
        )
    return out


def _sailing_without_helm(name: str) -> bool:
    """A voyage launched before the helm existed (16:35) is at sea without holding it: its process is
    alive. Not lost, and S2 lets it come home."""
    import subprocess

    out = subprocess.run(["pgrep", "-f", f"thorp run .*{name}"], capture_output=True, text=True)
    if out.stdout.strip():
        return True
    with contextlib.suppress(
        Exception
    ):  # at sea on a hired GPU (the charter): it never takes this Mac's helm
        from thorp.viable.s3_control import charter as s3

        return any(h.get("name") == name for h in s3.out_now())
    return False


def _label_of(name: str) -> str | None:
    from thorp.ledger import reader

    r = reader().query("select ship from runs where name=? order by started desc limit 1", [name])
    return r[0]["ship"] if r else None


def _clean_of(name: str, queued: dict) -> str | None:
    """The cleaning version a voyage read (or will read): from the queue, else the ledger's spec."""
    from thorp import cleaning
    from thorp.ledger import reader

    if name in queued:
        return cleaning.version_of(queued[name])
    r = reader().query(
        "select spec_json from runs where name=? order by started desc limit 1", [name]
    )
    if not r:
        return None
    return cleaning.version_of(json.loads(r[0]["spec_json"] or "{}"))


def clean_audit(per_library: int = 6) -> dict:
    """S3*: does the current cleaning still do its job on the canonical libraries? For a few books of
    each store, the line breaks before and after (words per break, the share inside a paragraph), and
    whether cleaning is deterministic. Independent of the gate: it reads the books, not the specs."""
    from thorp import cleaning
    from thorp.sources import load_text
    from thorp.sources.gutenberg import resolve_list

    out = {"version": cleaning.CURRENT, "libraries": {}}
    for lib in ("lists/stores/prose.csv", "lists/stores/trigram.csv"):
        ids = [f"pg{r.chosen}" for r in resolve_list(lib) if r.chosen][:per_library]
        raw_w = raw_b = cl_b = raw_in = cl_in = 0
        stable = True
        for b in ids:
            try:
                r = load_text(b)
            except Exception:  # noqa: BLE001  (a missing text is the sources' finding, not this one)
                continue
            c = cleaning.clean(r, cleaning.CURRENT)
            stable &= cleaning.clean(r, cleaning.CURRENT) == c
            a, k = cleaning.breaks(r), cleaning.breaks(c)
            raw_w += a["words"]
            raw_b += a["breaks"]
            cl_b += k["breaks"]
            raw_in += a["breaks"] * a["inside_share"]
            cl_in += k["breaks"] * k["inside_share"]
        out["libraries"][lib] = {
            "books": len(ids),
            "words_per_break": [round(raw_w / max(1, raw_b), 1), round(raw_w / max(1, cl_b), 1)],
            "inside_paragraph_share": [
                round(raw_in / max(1, raw_b), 3),
                round(cl_in / max(1, cl_b), 3),
            ],
            "deterministic": stable,
        }
    return out


def lint_queue() -> list[str]:
    """S2: what would collide or fail in the standing queue before it costs a run."""
    import yaml

    from thorp import train

    q = paths.resolve("specs/queue.txt")
    lines = [
        ln.strip() for ln in q.read_text().splitlines() if ln.strip() and not ln.startswith("#")
    ]
    from thorp.ledger import reader

    found, seen, order = [], {}, {}
    specs_by_name = {}
    sailing = {
        r["name"]
        for r in reader().query("select name from runs where status in ('running','finished')")
    }
    done = (
        paths.resolve("specs/queue-done.txt").read_text()
        if paths.resolve("specs/queue-done.txt").exists()
        else ""
    )
    for i, ln in enumerate(lines):
        if ln.startswith(
            "vast:"
        ):  # the Vast lane (s2_coordination.lanes): the same spec, sailed on a hired GPU
            ln = ln[len("vast:") :].strip()
        if ln.startswith(("cmd:", "wait:")):
            continue
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            found.append(f"{ln}: no spec file")
            continue
        folder = paths.data_dir() / "runs" / os.path.dirname(ln)
        if not folder.exists():
            found.append(f"{ln}: its log folder {folder} does not exist")
        spec = yaml.safe_load(p.read_text())
        specs_by_name[spec.get("name")] = spec
        for why in _named_fitout(
            spec
        ):  # S5 'fitout': the gate would refuse it when it reached the helm
            found.append(f"{ln}: {why}; the S3 gate will refuse it")
        rid = train.run_id(spec)
        if rid in seen:
            found.append(f"{ln}: the same run as {seen[rid]} (one run id)")
        seen[rid] = ln
        order[spec.get("name")] = i
        src = (spec.get("seeded_from") or {}).get("run")
        if src:  # S5 'clean': a model carries its tokeniser, so a seed must have read the same text
            from thorp import cleaning

            mine, theirs = cleaning.version_of(spec), _clean_of(src, specs_by_name)
            if theirs is not None and theirs != mine:
                found.append(
                    f"{ln}: reads {mine} text but is seeded from {src}, which read {theirs}"
                )
        if src and src in order:
            continue
        if (
            src
            and f"/{src} 0" not in done
            and not any(src == n for n in order)
            and src not in sailing
        ):
            found.append(f"{ln}: seeded from {src}, which is neither finished nor queued before it")
    h = helm()
    for r in reader().query("select name, started from runs where status='running'"):
        if (not h or h.get("name") != r["name"]) and not _sailing_without_helm(r["name"]):
            found.append(
                f"{r['name']}: the ledger has it at sea since {r['started']}, but it does not hold the helm (lost at sea?)"
            )
    return found


def audit() -> dict:
    """S3*: the whole system's state, S1 to S5, independent of the gate."""
    import yaml

    from thorp import fleet
    from thorp.ledger import reader

    rec = reader()
    q = paths.resolve("specs/queue.txt")
    queued = [
        ln.strip()
        for ln in q.read_text().splitlines()
        if ln.strip() and not ln.startswith(("#", "cmd:"))
    ]
    violations: dict[str, list[str]] = {}
    excused: dict[str, list[str]] = {}
    bargains: dict[str, list[dict]] = {}  # the voyages that opted out of a policy in words, and why
    for ln in queued:
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            continue
        spec = yaml.safe_load(p.read_text())
        opt_in = (spec.get("data", {}).get("opt_in") or "").strip()
        for key, pol in POLICIES.items():
            if (
                key == "period"
            ):  # the slow check runs on the gate, per run, not over the whole queue
                continue
            v = pol.check(spec)
            if v and excepted(key, spec):
                excused.setdefault(key, []).append(ln)
            elif v and pol.opt_in and opt_in:
                bargains.setdefault(key, []).append({"voyage": ln, "why": opt_in})
            elif v:
                violations.setdefault(key, []).append(ln)
    failed = rec.query("select count(*) n from runs where status not in ('finished','running')")[0][
        "n"
    ]
    log = gate_log(400)
    try:  # acquisition, the books the voyages read: a viable system one level down (thorp/acquisition.py)
        from thorp import acquisition

        acq = acquisition.summary()
    except Exception as e:  # noqa: BLE001
        acq = {"error": str(e)}
    return {
        "S1": {"expeditions": expedition_states(), "queued": len(queued), "acquisition": acq},
        "S2": {"helm": helm(), "queue_lints": lint_queue()},
        "S3": {
            "policies": {
                k: {
                    "enforced": enforced(k),
                    "opt_in": POLICIES[k].opt_in,
                    "queued_runs_breaking_it": len(violations.get(k, [])),
                    "queued_runs_excepted": len(excused.get(k, [])),
                    "queued_runs_bargained": len(bargains.get(k, [])),
                    "exception": (_exceptions().get(k) or {}).get("reason", ""),
                    "refused_lately": sum(
                        1
                        for g in log
                        for d in g.get("decisions", [])
                        if d.get("policy") == k and d.get("how") == "refused"
                    ),
                }
                for k in POLICIES
            },
            "runs_not_finished": failed,
            "gate_log": log[:60],
            "bargains": {k: v[:40] for k, v in bargains.items()},
            "exceptions": {
                k: {
                    "reason": e.get("reason", ""),
                    "adopted": e.get("adopted", ""),
                    "runs": len(e.get("runs") or []),
                    "patterns": e.get("patterns") or [],
                }
                for k, e in _exceptions().items()
                if isinstance(e, dict)
            },
        },
        "S3*": {"cleaning": clean_audit()},
        "S4": {
            "competitors": list(fleet.COMPETITORS),
            "reference_ladder": list(fleet.REFERENCE_LADDER),
        },
        "S5": {
            k: {"statement": p.statement, "adopted": p.adopted, "enforced": enforced(k)}
            for k, p in POLICIES.items()
        },
        "breaking": {k: v[:20] for k, v in violations.items()},
    }


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["audit"]:
        a = audit()
        print(
            "S1 operations:",
            sum(1 for s in a["S1"]["expeditions"].values() if s == "under way"),
            "expeditions under way,",
            sum(1 for s in a["S1"]["expeditions"].values() if s == "at sea"),
            "at sea,",
            a["S1"]["queued"],
            "runs queued",
        )
        print(
            "S2 coordination: at the helm:",
            (a["S2"]["helm"] or {}).get("name", "nobody"),
            "|",
            len(a["S2"]["queue_lints"]),
            "lints",
        )
        for x in a["S2"]["queue_lints"][:10]:
            print("   ", x)
        print("S3 control:")
        for k, v in a["S3"]["policies"].items():
            print(
                f"    {k:8} {'ENFORCED' if v['enforced'] else 'advisory'}  queued runs breaking it: {v['queued_runs_breaking_it']}, excepted: {v['queued_runs_excepted']}"
            )
        print(
            "S4 intelligence:",
            len(a["S4"]["competitors"]),
            "competitors,",
            len(a["S4"]["reference_ladder"]),
            "reference models",
        )
        print("S5 policy:", ", ".join(f"{k} ({v['adopted']})" for k, v in a["S5"].items()))
