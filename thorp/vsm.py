r"""Thorp as a viable system (2026-11-07, Justin: "how do those types of rules get governed? We need to
implement Beer's VSM, making sure this codebase for running Thorp has the S1 to S5 units encoded into its
way of operating").

Stafford Beer's Viable System Model, mapped onto Thorp, each system with its members in the codebase:

- **S1, operations**: the expeditions (fleet.EXPEDITIONS) and the voyages (runs) they sail; each is an operation with its own
  goal, levers and stop rule.
- **S2, coordination**: what keeps the operations from colliding: one GPU and one standing queue
  (scripts/queue.sh), run ids, log folders, seeding order, the ledger; and the two Claude sessions (this one
  and the dashboard's) that share the files. `lint_queue()` finds collisions before they cost a run.
- **S3, control**: the gate every run passes (`gate(spec)`, called from train.prepare): the enforced
  policies applied to the spec; and the bargain, a written opt-in (`data.opt_in`) that a policy admits.
  **S3\*, audit**: `audit()`, over the queue and the ledger, sporadic and independent of the gate
  (the night watches and steering tasks call it too).
- **S4, intelligence**: the outside world and the future: the competitors and the reference ladder
  (fleet.COMPETITORS, data/compare/), the leaderboard and Smoking Qwen's forecast, the research the tests
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
            "the expeditions and the voyages they sail",
            ("thorp/fleet.py EXPEDITIONS", "specs/", "data/runs/", "thorp/train.py"),
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
            ),
        ),
        System(
            "S3",
            "Control",
            "the gate every run passes, the opt-in bargain, and the audit (S3*)",
            ("thorp/vsm.py gate, audit", "thorp/stores.py", "tests/"),
        ),
        System(
            "S4",
            "Intelligence",
            "the outside world and the future: competitors, forecasts, research",
            (
                "thorp/fleet.py COMPETITORS, REFERENCE_LADDER",
                "data/compare/",
                "thorp/leaderboard.py",
                "thorp/smoking_qwen.py",
                "thorp/knockout.py",
            ),
        ),
        System(
            "S5",
            "Policy",
            "Thorp's identity: the rules, adopted by Justin, recorded in DECISIONS.md",
            ("thorp/vsm.py POLICIES", "DECISIONS.md"),
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


def _pre_registered(spec: dict) -> list[str]:
    """An operation's voyages belong to an expedition written up in DECISIONS.md before they sail."""
    from thorp import fleet

    v = fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
    if v is None:
        return ["belongs to no expedition"]
    return []


POLICIES: dict[str, Policy] = {
    p.key: p
    for p in (
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
    )
}


class GateRefused(ValueError):
    pass


def _enforcement() -> dict:
    """S5's switches (data/policies.json {key: true|false}), over each policy's default."""
    p = paths.data_dir() / "policies.json"
    return json.loads(p.read_text()) if p.exists() else {}


def enforced(key: str) -> bool:
    return bool(_enforcement().get(key, POLICIES[key].enforced))


def _exceptions() -> dict:
    """S5's written exceptions (data/policy-exceptions.json {key: {"reason", "adopted", "runs": [names],
    "patterns": [globs]}}):
    the runs a policy does not govern, by name, with the reason."""
    p = paths.data_dir() / "policy-exceptions.json"
    return json.loads(p.read_text()) if p.exists() else {}


def excepted(key: str, spec: dict) -> str:
    import fnmatch

    e = _exceptions().get(key) or {}
    n = spec.get("name") or ""
    hit = n in set(e.get("runs") or []) or any(
        fnmatch.fnmatch(n, p) for p in e.get("patterns") or []
    )
    return e.get("reason", "") if hit else ""


def gate(spec: dict, known_run: bool = False) -> list[str]:
    """S3: every enforced policy applied to a new run; refuse on a violation (unless the policy admits a
    written opt-in and the spec has one). Returns the advisory findings, for the log."""
    if known_run:
        return []
    notes = []
    opt_in = (spec.get("data", {}).get("opt_in") or "").strip()
    for key, pol in POLICIES.items():
        found = pol.check(spec)
        if not found:
            continue
        if why := excepted(key, spec):
            notes.append(f"policy '{key}' does not govern this run: {why}")
            continue
        if enforced(key) and not (pol.opt_in and opt_in):
            raise GateRefused(f"S3 gate, policy '{key}' ({pol.statement}): {'; '.join(found)}")
        notes.append(
            f"policy '{key}'"
            + (f" opted out: {opt_in}" if pol.opt_in and opt_in else f": {'; '.join(found)}")
        )
    return notes


# S2's helm: one GPU, so one voyage at sea at a time (Justin, 16:35: "surely only one can be running at
# a time ... this should be coordinated by S2"). Every voyage (train.run) and every GPU-heavy job takes the
# helm; a second waits in port until the first comes home. Expeditions can be under way together (their
# voyages queued); only one voyage is at sea.


def _helm_paths():
    d = paths.data_dir()
    return d / "helm.lock", d / "helm.json"


@contextlib.contextmanager
def at_sea(name: str, kind: str = "voyage", log=print):
    """Take the helm for `name` (blocking until it is free), hold it while the body runs."""
    import fcntl

    lock, who = _helm_paths()
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
        who.write_text(
            json.dumps(
                {
                    "name": name,
                    "kind": kind,
                    "pid": os.getpid(),
                    "since": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
        )
        yield
    finally:
        with contextlib.suppress(Exception):
            if json.loads(who.read_text()).get("pid") == os.getpid():
                who.unlink()
        f.close()  # releases the lock


def helm() -> dict | None:
    """Who is at sea now: the holder of the helm, or None when it is free."""
    import fcntl

    lock, who = _helm_paths()
    if not lock.exists():
        return None
    with open(lock, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            try:
                return json.loads(who.read_text())
            except Exception:  # noqa: BLE001
                return {"name": "(unknown)", "kind": "?", "since": None}
        fcntl.flock(f, fcntl.LOCK_UN)
    return None


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
        from thorp.ledger import Ledger

        for r in Ledger().query("select name, ship from runs where status='running'"):
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
    return bool(out.stdout.strip())


def _label_of(name: str) -> str | None:
    from thorp.ledger import Ledger

    r = Ledger().query("select ship from runs where name=? order by started desc limit 1", [name])
    return r[0]["ship"] if r else None


def lint_queue() -> list[str]:
    """S2: what would collide or fail in the standing queue before it costs a run."""
    import yaml

    from thorp import train

    q = paths.resolve("specs/queue.txt")
    lines = [
        ln.strip() for ln in q.read_text().splitlines() if ln.strip() and not ln.startswith("#")
    ]
    from thorp.ledger import Ledger

    found, seen, order = [], {}, {}
    sailing = {
        r["name"]
        for r in Ledger().query("select name from runs where status in ('running','finished')")
    }
    done = (
        paths.resolve("specs/queue-done.txt").read_text()
        if paths.resolve("specs/queue-done.txt").exists()
        else ""
    )
    for i, ln in enumerate(lines):
        if ln.startswith("cmd:"):
            continue
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            found.append(f"{ln}: no spec file")
            continue
        folder = paths.data_dir() / "runs" / os.path.dirname(ln)
        if not folder.exists():
            found.append(f"{ln}: its log folder {folder} does not exist")
        spec = yaml.safe_load(p.read_text())
        rid = train.run_id(spec)
        if rid in seen:
            found.append(f"{ln}: the same run as {seen[rid]} (one run id)")
        seen[rid] = ln
        order[spec.get("name")] = i
        src = (spec.get("seeded_from") or {}).get("run")
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
    for r in Ledger().query("select name, started from runs where status='running'"):
        if (not h or h.get("name") != r["name"]) and not _sailing_without_helm(r["name"]):
            found.append(
                f"{r['name']}: the ledger has it at sea since {r['started']}, but it does not hold the helm (lost at sea?)"
            )
    return found


def audit() -> dict:
    """S3*: the whole system's state, S1 to S5, independent of the gate."""
    import yaml

    from thorp import fleet
    from thorp.ledger import Ledger

    rec = Ledger()
    q = paths.resolve("specs/queue.txt")
    queued = [
        ln.strip()
        for ln in q.read_text().splitlines()
        if ln.strip() and not ln.startswith(("#", "cmd:"))
    ]
    violations: dict[str, list[str]] = {}
    excused: dict[str, list[str]] = {}
    for ln in queued:
        p = paths.resolve(f"specs/{ln}.yaml")
        if not p.exists():
            continue
        spec = yaml.safe_load(p.read_text())
        for key, pol in POLICIES.items():
            if (
                key == "period"
            ):  # the slow check runs on the gate, per run, not over the whole queue
                continue
            v = pol.check(spec)
            if v and excepted(key, spec):
                excused.setdefault(key, []).append(ln)
            elif v and not (pol.opt_in and (spec.get("data", {}).get("opt_in") or "").strip()):
                violations.setdefault(key, []).append(ln)
    failed = rec.query("select count(*) n from runs where status not in ('finished','running')")[0][
        "n"
    ]
    return {
        "S1": {"expeditions": expedition_states(), "queued": len(queued)},
        "S2": {"helm": helm(), "queue_lints": lint_queue()},
        "S3": {
            "policies": {
                k: {
                    "enforced": enforced(k),
                    "queued_runs_breaking_it": len(violations.get(k, [])),
                    "queued_runs_excepted": len(excused.get(k, [])),
                    "exception": (_exceptions().get(k) or {}).get("reason", ""),
                }
                for k in POLICIES
            },
            "runs_not_finished": failed,
        },
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
