"""Phase 1's import: data/'s small state brought into the store (DECISIONS.md, "One store: Postgres, by the viable
system"). Run as often as wanted: a row already in the store is not written again.

    uv run thorp store import            # read the files, write what is not yet in Postgres
    uv run thorp store import --retire   # and then rename each file *.imported, so nothing reads it (the cutover)

What it brings in. Phase 1: S5's switches (policies.json), exceptions (policy-exceptions.json) and charter terms
(charter.json); S3's gate log (gate-log.jsonl) and spend log (charter-log.jsonl); S4's market reads
(charter-market.jsonl). Phase 1b: S4's readings of outside models (compare/*.json); S1's crownings
(thorp-versions.json), stores (stores.json), intakes and their verdicts (acquisition/intakes/*.json, acquisition/
log.jsonl), table talk (table/*.jsonl), and the register of tokenisers (tokenisers/<id>/: their files stay, as the
artifact a voyage reads, and are never retired). Not brought in: helm.json, lanes.json and acquisition/intake.json,
which say who is out *now*: each holder writes itself into s2 as it starts, so after the cutover restart they are
recorded afresh.
"""

from __future__ import annotations

import json
from collections import Counter
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
    """Each decision as often as the log has it (two alike in one second are two decisions)."""
    have = Counter(_key(r) for r in vsm.gate_log(10**9))
    n = 0
    for r in _lines(p):
        if not r.get("verdict"):
            continue
        r = {**r, "at": _utc(r["at"]).astimezone().strftime(vsm.GATE_TIME)}
        if have[_key(r)]:
            have[_key(r)] -= 1
            continue
        n += vsm.insert_gate_decision(r, source="imported")
    return n


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


def readings_dir(d: Path) -> int:
    from thorp.viable.s4_intelligence import readings

    n = 0
    for f in sorted(d.glob("*.json")):
        try:
            doc = json.loads(f.read_text())
        except ValueError:
            continue
        if readings.get(f.stem) != readings._finite(json.loads(json.dumps(doc, default=float))):
            readings.put(f.stem, doc)
            n += 1
    return n


def crownings(p: Path) -> int:
    from thorp import leaderboard

    have = leaderboard._versions()
    n = 0
    for preset, hist in json.loads(p.read_text()).items():
        for h in hist:
            if h not in have.get(preset, []):
                leaderboard.put_crowning(preset, h)
                n += 1
    return n


def stores_file(p: Path) -> int:
    from thorp import stores

    have, want = stores.stores(), json.loads(p.read_text())
    new = {k: v for k, v in want.items() if have.get(k) != v}
    if new:
        stores.freeze(new)
    return len(new)


def acquisition_dir(d: Path) -> int:
    from thorp import acquisition
    from thorp.viable.records import Intake

    n = 0
    for f in sorted((d / "intakes").glob("in-*.json")):
        rec = json.loads(f.read_text())
        with store.session() as s:
            r = s.get(Intake, rec["id"])
            same = r is not None and r.record == json.loads(json.dumps(rec, default=str))
        if not same:
            acquisition._write_intake(rec)
            n += 1
    log = d / "log.jsonl"
    if log.exists():  # each line as often as the file has it: two books refused in one second are two verdicts
        have = Counter(_key(e) for e in acquisition.read_log())
        for e in _lines(log):
            k = _key(e)
            if have[k]:
                have[k] -= 1
                continue
            acquisition._append_log(e)
            n += 1
    return n


def _key(line: dict) -> str:
    return json.dumps(line, sort_keys=True, ensure_ascii=False, default=str)


def table_dir(d: Path) -> int:
    from thorp import table
    from thorp.viable.records import TableTalk

    n = 0
    for f in sorted(d.glob("*.jsonl")):
        with store.session() as s:
            seen = {(t.at, t.question) for t in s.scalars(select(TableTalk).where(TableTalk.voyage == f.stem))}
        for ln in _lines(f):
            if (_utc(ln["at"]), ln["question"]) not in seen:
                table.keep_talk(f.stem, ln)
                n += 1
    return n


def tokenisers_dir(d: Path) -> int:
    from thorp import tokeniser
    from thorp.viable.records import TokeniserRecord

    n = 0
    for t in sorted(x for x in d.iterdir() if x.is_dir() and not x.name.endswith(".tmp")):
        if not (t / "settings.json").exists():
            continue
        with store.session() as s:
            if s.get(TokeniserRecord, t.name):
                continue
        books = json.loads((t / "books.json").read_text()) if (t / "books.json").exists() else []
        stats = json.loads((t / "stats.json").read_text()) if (t / "stats.json").exists() else {}
        tokeniser.register(t.name, t, json.loads((t / "settings.json").read_text()), stats, books)
        n += 1
    return n


IMPORTERS = {
    "policies.json": switches,
    "policy-exceptions.json": exceptions,
    "charter.json": charter_terms,
    "gate-log.jsonl": gate_log,
    "charter-log.jsonl": spend_log,
    "charter-market.jsonl": market,
    "compare": readings_dir,
    "thorp-versions.json": crownings,
    "stores.json": stores_file,
    "acquisition": acquisition_dir,
    "table": table_dir,
    "tokenisers": tokenisers_dir,
}
NEVER_RETIRED = {"tokenisers"}  # the tokeniser's own files are the artifact a voyage reads
RETIRED_WITHIN = {"acquisition": ("intakes", "log.jsonl")}  # the lock beside them stays


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
        if retire and name not in NEVER_RETIRED:
            for q in [p / x for x in RETIRED_WITHIN[name]] if name in RETIRED_WITHIN else [p]:
                if q.exists():
                    q.rename(q.with_name(q.name + ".imported"))
                    log(f"store: {q.relative_to(data)} retired (renamed {q.name}.imported; nothing reads it)")
    return out
