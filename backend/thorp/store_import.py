"""Phase 1's import: data/'s small state brought into the store (DECISIONS.md, "One store: Postgres, by the viable
system"). Run as often as wanted: a row already in the store is not written again.

    uv run thorp store import            # read the files, write what is not yet in Postgres
    uv run thorp store import --retire   # and then rename each file *.imported, so nothing reads it (the cutover)

What it brings in: S5's switches (policies.json), exceptions (policy-exceptions.json) and charter terms
(charter.json); S3's gate log (gate-log.jsonl) and spend log (charter-log.jsonl); S4's market reads
(charter-market.jsonl). Not brought in: helm.json and lanes.json, which say who is out *now*: the helm's holder and
the coordinator write themselves into s2 as they sail, so after the cutover restart they are recorded afresh.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from thorp import paths, store, vsm
from thorp.viable.records import (
    CharterTerm,
    MarketRead,
    PolicyException,
    PolicyExceptionMatch,
    PolicySwitch,
    SpendEvent,
)
from thorp.viable.s3_control import charter as s3

FILES = ("policies.json", "policy-exceptions.json", "charter.json", "gate-log.jsonl", "charter-log.jsonl",
         "charter-market.jsonl")  # fmt: skip
WORDS = "imported from data/{} (phase 1 of the one store)"


def _lines(p: Path) -> list[dict]:
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def _utc(at: str) -> datetime:
    d = datetime.fromisoformat(at)
    return d if d.tzinfo else d.astimezone()


def switches(p: Path) -> int:
    n = 0
    with store.session() as s:
        for k, v in json.loads(p.read_text()).items():
            r = s.get(PolicySwitch, k)
            if r is None or r.enforced != bool(v):
                s.merge(PolicySwitch(policy=k, enforced=bool(v), words=WORDS.format(p.name)))
                n += 1
    return n


def exceptions(p: Path) -> int:
    n = 0
    with store.session() as s:
        for k, e in json.loads(p.read_text()).items():
            want = [("run", x) for x in e.get("runs") or []] + [("pattern", x) for x in e.get("patterns") or []]
            extra = {x: v for x, v in e.items() if x not in ("reason", "adopted", "runs", "patterns")}
            r = s.get(PolicyException, k)
            have = [(m.kind, m.value) for m in r.matches] if r else None
            if r and (r.reason, r.adopted, r.extra or {}, have) == (e.get("reason", ""), e.get("adopted", ""), extra, want):
                continue
            if r is None:
                r = PolicyException(policy=k)
                s.add(r)
            r.reason, r.adopted, r.extra = e.get("reason", ""), e.get("adopted", ""), extra
            r.matches = [PolicyExceptionMatch(kind=kind, value=v, ordinal=i) for i, (kind, v) in enumerate(dict.fromkeys(want))]
            n += 1
    return n


def charter_terms(p: Path) -> int:
    from thorp.viable.s5_policy import charter as s5

    have = s5.overrides()
    n = 0
    for k, v in json.loads(p.read_text()).items():
        if have.get(k) != v:
            with store.session() as s:
                s.add(CharterTerm(term=k, value=v, words=WORDS.format(p.name)))
            n += 1
    return n


def gate_log(p: Path) -> int:
    return sum(vsm.insert_gate_decision(r, source="imported", once=True) for r in _lines(p) if r.get("verdict"))


def spend_log(p: Path) -> int:
    n = 0
    for r in _lines(p):
        at = _utc(r["at"])
        with store.session() as s:
            if s.scalar(select(SpendEvent.id).where(SpendEvent.at == at, SpendEvent.event == r["event"],
                                                     SpendEvent.instance.is_not_distinct_from(r.get("instance")))):  # fmt: skip
                continue
        s3.insert({**r, "at": at.astimezone(UTC).isoformat(timespec="seconds")})
        n += 1
    return n


def market(p: Path) -> int:
    from thorp.viable.s4_intelligence import market as s4

    new = []
    with store.session() as s:
        for r in _lines(p):
            at = _utc(r["at"])
            if not s.scalar(select(MarketRead.id).where(MarketRead.at == at, MarketRead.gpu == r["gpu"],
                                                         MarketRead.offer_id.is_not_distinct_from(r.get("offer_id")))):  # fmt: skip
                new.append({**r, "at": at.isoformat()})
    if new:
        s4.keep(new)
    return len(new)


IMPORTERS = {
    "policies.json": switches,
    "policy-exceptions.json": exceptions,
    "charter.json": charter_terms,
    "gate-log.jsonl": gate_log,
    "charter-log.jsonl": spend_log,
    "charter-market.jsonl": market,
}


def run(data: Path | None = None, retire: bool = False, log=print) -> dict[str, int]:
    """Each file of phase 1 into the store; with `retire`, each file renamed *.imported once it is in."""
    data = data or paths.data_dir()
    out = {}
    for name, fn in IMPORTERS.items():
        p = data / name
        if not p.exists():
            continue
        out[name] = fn(p)
        log(f"store: {name}: {out[name]} new row(s)")
        if retire:
            p.rename(p.with_name(p.name + ".imported"))
            log(f"store: {name} retired (renamed {name}.imported; nothing reads it)")
    return out
