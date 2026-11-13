r"""S5: the feedback the other systems send up, sorted so S4 can act on it (13 November, Justin: "I'd like feedback to
be the main UX function ... see what feedback has been received from the other units and then it categorizes those
into a taxonomy that will allow the intelligence layer in S4 to make good decisions").

Nothing new is recorded here. Every item is read from what a system already keeps, and its category comes from
what kind of record it is, so the same records always sort the same way:

- **S5's proposals** (s5.proposals, `thorp proposals`): what a session, a system or a person asks Justin.
- **S3's plan** (s3.cycles, the last turn): what the planner would do if the terms allowed it.
- **S3\*'s books** (the same turn's audit): each hire's quote against its bill, the Mac's clock, the last plan.
- **S3's gate** (s3.gate_decisions): voyages refused, until the same voyage is passed.
- **S4's judge** (s4.judgments): why a fit-out died, or that it could not say.
- **S3\*'s charter audit** (s3star.audits): orphans (hired, not sailing) and ghosts (logged out, not listed).
- **S2's breaker** (s2.lane_defs): a lane paused after fit-outs failed in a row.

**The taxonomy** (`feedback-v1`) has two tiers, like the shapes taxonomy (taxonomy.py). The coarse tier is the
decision the item puts to S4: what S4 should do with it when it next plans. The fine tier is the kind of record.

    DECIDE     Justin must choose. S4 plans around it, and counts on neither answer until he does.
    CONSTRAIN  A rule or a ceiling stopped work. S4 prices what it costs, then plans within it or proposes moving it.
    REPAIR     Something broke. S4 counts it in that class's failure rate and routes around it until it is fixed.
    CALIBRATE  A number the plan rested on was wrong. S4 corrects the estimate before the next plan.
    LEARN      Nobody knows yet. S4 measures it: one voyage or one question that replaces the guess.

S4's code reads it with `inbox()` (every item, sorted) or `for_s4()` (the same, grouped, with what each category asks);
the dashboard serves it at /api/liberty-machine/feedback, and `thorp feedback` prints it.
"""

from __future__ import annotations

import contextlib
import sys
from datetime import UTC, datetime, timedelta

VERSION = "feedback-v1"
ADOPTED = "2026-11-13, proposed to Justin with the S5 page's move to /policy"

DAYS = 7  # how far back the gate, the judge and the charter audit are read
OVER = 1.25  # as S3* counts a quote or a clock out (s3star_audit/cycle.py)

# the coarse tier, in the order the page shows it: what S4 does with an item
CATEGORIES = ("DECIDE", "CONSTRAIN", "REPAIR", "CALIBRATE", "LEARN")
ABOUT = {
    "DECIDE": {"name": "Decide", "means": "Justin must choose",
               "s4": "plan around it and count on neither answer until it is decided"},
    "CONSTRAIN": {"name": "Constrain", "means": "a rule or a ceiling stopped work",
                  "s4": "price what it costs; plan within it, or propose moving it to S5"},
    "REPAIR": {"name": "Repair", "means": "something broke",
               "s4": "count it in that class's failure rate and route around it until it is fixed"},
    "CALIBRATE": {"name": "Calibrate", "means": "a number the plan rested on was wrong",
                  "s4": "correct the estimate before the next plan"},
    "LEARN": {"name": "Learn", "means": "nobody knows yet",
              "s4": "measure it: one voyage or one question that replaces the guess"},
}  # fmt: skip

# the fine tier: the kind of record, and the category it always falls in
KINDS = {
    "proposal": ("DECIDE", "a proposal filed to S5, waiting on Justin"),
    "ceiling": ("CONSTRAIN", "S3's plan would sail more but for one of S5's terms"),
    "lane closed": ("CONSTRAIN", "S3's plan would send voyages abroad, and the lane is shut"),
    "refusal": ("CONSTRAIN", "the gate refused a voyage, and it has not passed since"),
    "failed hire": ("REPAIR", "hires released before their voyage trained"),
    "fit-out death": ("REPAIR", "the judge's reading of why one fit-out died"),
    "breaker": ("REPAIR", "a lane S2 paused after fit-outs failed in a row"),
    "orphan": ("REPAIR", "a box hired and labelled but not sailing, found by the charter audit"),
    "ghost": ("REPAIR", "a hire the log shows out that the provider does not list"),
    "lane line": ("REPAIR", "queue lines written without the lane they need"),
    "quote": ("CALIBRATE", "hires that took more than a quarter over their quoted hours"),
    "set-up": ("CALIBRATE", "set-up and home that took more than a quarter over the minutes planned"),
    "clock": ("CALIBRATE", "voyages on this Mac that ran more than a quarter over the queue's clock"),
    "stale plan": ("CALIBRATE", "voyages the last plan sent abroad that are still queued"),
    "unmeasured": ("LEARN", "a size no class has sailed, planned on a borrowed speed-up"),
    "unjudged": ("LEARN", "failed fit-outs the judge read and could not explain"),
}  # fmt: skip

SOURCES = ("S1", "S2", "S3", "S3*", "S4", "S5", "session", "person")


def category(kind: str) -> str:
    return KINDS[kind][0]


def _item(kind: str, source: str, title: str, *, key: str, detail: str = "", at: str | None = None, area: str = "",
          by: str = "", usd: float | None = None, minutes: float | None = None, count: int = 1, ref: dict | None = None) -> dict:  # fmt: skip
    return {
        "id": f"{kind}:{key}", "category": category(kind), "kind": kind, "source": source, "by": by or source,
        "title": title, "detail": detail, "at": at, "area": area, "count": count,
        "usd": None if usd is None else round(float(usd), 2), "minutes": None if minutes is None else round(float(minutes), 1),
        "ref": ref or {},
    }  # fmt: skip


def _iso(at) -> str | None:
    if at is None:
        return None
    if isinstance(at, datetime):
        return at.isoformat(timespec="minutes")
    return str(at)


def source_of(filed_by: str) -> str:
    """Who filed a proposal, as one of SOURCES: a system by its name, a Claude session, or a person."""
    f = (filed_by or "").strip()
    head = f.split(":")[0].split()[0].upper() if f else ""
    if head in ("S1", "S2", "S3", "S3*", "S4", "S5"):
        return head
    return "session" if f.lower().startswith("session") else "person"


# ---------------------------------------------------------------- each record, as items (pure: tested without a store)


def from_proposals(rows: list[dict]) -> list[dict]:
    """The open proposals filed to S5: each is DECIDE."""
    return [
        _item("proposal", source_of(r.get("filed_by", "")), r["title"], key=str(r["id"]), detail=r.get("asks") or "",
              at=_iso(r.get("filed_at")), area=r.get("area") or "", by=r.get("filed_by") or "",
              ref={"proposal": r["id"], "why": r.get("why") or ""})  # fmt: skip
        for r in rows
        if r.get("status", "open") == "open"
    ]


def from_cycle(last: dict | None) -> list[dict]:
    """The last turn of the planning cycle: S3's proposals and S3*'s audit of the turn before."""
    if not last:
        return []
    at, cid, out = _iso(last.get("at")), last.get("id"), []
    for n, p in enumerate(last.get("proposals") or []):
        what, to = str(p.get("what") or ""), str(p.get("to") or "")
        if to == "S4":
            kind = "unmeasured"
        elif to == "S2" and "lane" in what and what.startswith("open"):
            kind = "lane closed"
        elif to == "S2":
            kind = "lane line"
        else:
            kind = "ceiling"
        out.append(_item(kind, "S3", what, key=f"{cid}.{n}", detail=str(p.get("why") or ""), at=at,
                         area=f"to {to}" if to else "", ref={"cycle": cid}))  # fmt: skip
    audit = last.get("audit") or {}
    hires = audit.get("hires") or []
    failed = [h for h in hires if not h.get("sailed")]
    if failed:
        cost = sum(float(h.get("cost") or 0) for h in failed)
        mins = sum(float(h.get("hours") or 0) * 60 for h in failed)
        whys = sorted({str(h.get("why") or h.get("status") or "no reason kept") for h in failed})
        where: dict[str, int] = {}
        for h in failed:
            where[str(h.get("failed_in") or "unknown")] = where.get(str(h.get("failed_in") or "unknown"), 0) + 1
        steps = ", ".join(f"{k} {v}" for k, v in sorted(where.items(), key=lambda kv: -kv[1]))
        out.append(_item("failed hire", "S3*", f"{len(failed)} hire(s) never sailed", key=str(cid), at=at, count=len(failed),
                         usd=cost, minutes=mins, area="the Vast lane",
                         detail=f"{mins:.0f} minutes and ${cost:.2f} for no training; failed in {steps} ({'; '.join(whys)})",
                         ref={"cycle": cid, "instances": [h.get("instance") for h in failed]}))  # fmt: skip
    # quotes and set-ups, by GPU class: S4 corrects a class's estimate, not one hire's
    for kind in ("quote", "set-up"):
        by_gpu: dict[str, list[dict]] = {}
        for h in hires:
            if not h.get("sailed"):
                continue
            if kind == "quote" and (h.get("hours_ratio") or 0) > OVER:
                by_gpu.setdefault(str(h.get("gpu") or "unknown"), []).append(h)
            assumed, took = h.get("setup_assumed_min"), h.get("overhead_min")
            if kind == "set-up" and assumed and took is not None and took > OVER * assumed:
                by_gpu.setdefault(str(h.get("gpu") or "unknown"), []).append(h)
        for gpu, hs in sorted(by_gpu.items()):
            if kind == "quote":
                ratios = [float(h["hours_ratio"]) for h in hs]
                over = sum(float(h.get("cost") or 0) - float(h.get("quote") or 0) for h in hs if h.get("quote") and h.get("cost") is not None)
                span = f"{min(ratios):.1f}" if len(ratios) == 1 else f"{min(ratios):.1f} to {max(ratios):.1f}"
                title = f"{gpu}: {len(hs)} hire(s) took {span} times their quoted hours"
                detail = "; ".join(f"{h.get('name')} quoted {float(h.get('quote_hours') or 0):.2f} h, took {float(h.get('hours') or 0):.2f} h" for h in hs)
                out.append(_item(kind, "S3*", title, key=f"{cid}.{gpu}", detail=detail, at=at, area=gpu, count=len(hs), usd=over or None,
                                 ref={"cycle": cid, "gpu": gpu}))  # fmt: skip
            else:
                extra = sum(float(h["overhead_min"]) - float(h["setup_assumed_min"]) for h in hs)
                title = f"{gpu}: set-up and home ran over the plan on {len(hs)} hire(s)"
                detail = "; ".join(f"{h.get('name')} planned {float(h['setup_assumed_min']):.0f} min, took {float(h['overhead_min']):.0f}" for h in hs)
                out.append(_item(kind, "S3*", title, key=f"{cid}.{gpu}", detail=detail, at=at, area=gpu, count=len(hs), minutes=extra,
                                 ref={"cycle": cid, "gpu": gpu}))  # fmt: skip
    clock = audit.get("clock") or []
    slow = [c for c in clock if float(c.get("ratio") or 0) > OVER]
    if slow:
        worst = max(slow, key=lambda c: float(c["ratio"]))
        extra = sum(float(c["took_min"]) - float(c["planned_min"]) for c in slow)
        out.append(_item("clock", "S3*", f"{len(slow)} of {len(clock)} voyage(s) here ran over the queue's clock", key=str(cid),
                         detail=f"the worst, {worst.get('name')}, was planned at {float(worst['planned_min']):.0f} min and took {float(worst['took_min']):.0f}",
                         at=at, area="this Mac", count=len(slow), minutes=extra, ref={"cycle": cid}))  # fmt: skip
    stuck = [p for p in audit.get("planned") or [] if p.get("now") == "still queued"]
    if stuck:
        out.append(_item("stale plan", "S3*", f"{len(stuck)} voyage(s) the last plan sent abroad are still queued", key=str(cid),
                         detail=", ".join(str(p.get("name")) for p in stuck[:8]), at=at, area="the Vast lane", count=len(stuck),
                         ref={"cycle": cid}))  # fmt: skip
    return out


def from_judgments(rows: list[dict]) -> list[dict]:
    """The judge's readings: each cause it gave is REPAIR; the fit-outs it could not explain are one LEARN item."""
    out, blank = [], []
    for r in rows:
        if r.get("kind") != "fitout":
            continue
        v = r.get("verdict") or {}
        # a verdict that only echoes the prompt's template ("<one sentence>") said nothing
        echoed = str(v.get("cause") or "").strip().startswith("<")
        if r.get("outcome") == "ok" and v.get("cause") and not echoed:
            out.append(_item("fit-out death", "S4", f"{v.get('name') or r.get('subject')}: {v['cause']}", key=str(r["id"]),
                             detail=f"in {v.get('step') or 'unknown'}, the fault of {v.get('fault') or 'unknown'} "
                                    f"({v.get('confidence') or 'low'} confidence)" + (f"; do: {v['do']}" if v.get("do") else ""),
                             at=_iso(r.get("at")), area=str(v.get("gpu") or ""), by=f"S4's judge ({r.get('judge')})",
                             ref={"judgment": r["id"], "instance": r.get("subject"), "known": r.get("known")}))  # fmt: skip
        else:
            blank.append(r)
    if blank:
        where: dict[str, int] = {}
        for r in blank:
            step = str((r.get("verdict") or {}).get("failed_in") or "unknown")
            where[step] = where.get(step, 0) + 1
        steps = ", ".join(f"{k} {v}" for k, v in sorted(where.items(), key=lambda kv: -kv[1]))
        latest = max(blank, key=lambda r: str(r.get("at") or ""))
        out.append(_item("unjudged", "S4", f"the judge could not explain {len(blank)} failed fit-out(s)", key=str(latest["id"]),
                         detail=f"its answers were {', '.join(sorted({'its own prompt echoed' if r.get('outcome') == 'ok' else str(r.get('outcome')) for r in blank}))}; they died in {steps}",
                         at=_iso(latest.get("at")), area="the judge", count=len(blank), by=f"S4's judge ({latest.get('judge')})",
                         ref={"judgments": [r["id"] for r in blank]}))  # fmt: skip
    return out


def from_gate(refused: list[dict], passed: dict[str, str] | None = None) -> list[dict]:
    """The gate's refusals, one item a voyage and policy, dropped once that voyage has passed the gate since.
    `refused` rows carry at, name, place, policy, why; `passed` is each name's latest pass."""
    passed = passed or {}
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in refused:
        name = str(r.get("name") or "an unnamed voyage")
        if name in passed and str(passed[name]) >= str(_iso(r.get("at"))):
            continue
        groups.setdefault((name, str(r.get("policy") or "")), []).append(r)
    out = []
    for (name, policy), rs in groups.items():
        last = max(rs, key=lambda r: str(_iso(r.get("at"))))
        why = str(last.get("why") or "")
        out.append(_item("refusal", "S3", f"{name} refused by the {policy} policy", key=f"{name}.{policy}",
                         detail=why if len(why) <= 400 else why[:400] + "…", at=_iso(last.get("at")), area=policy,
                         count=len(rs), by="S3's gate", ref={"voyage": name, "policy": policy, "place": last.get("place")}))  # fmt: skip
    return out


def from_audits(rows: list[dict]) -> list[dict]:
    """The charter audit's orphans and ghosts."""
    return [
        _item(r["finding"], "S3*", f"an {r['finding']}: instance {r['instance']}" if r["finding"] == "orphan" else f"a ghost: instance {r['instance']}",
              key=str(r["id"]), detail=f"{r.get('action') or ''}" + (f"; run {r['run_id']}" if r.get("run_id") else ""),
              at=_iso(r.get("at")), area="the Vast lane", usd=r.get("cost"), by="S3*'s charter audit",
              ref={"audit": r["id"], "instance": r["instance"]})  # fmt: skip
        for r in rows
        if r.get("finding") in ("orphan", "ghost")
    ]


def from_lanes(rows: list[dict], paused_mark: str = " | paused ") -> list[dict]:
    """A lane paused by S2's breaker (its reason is on the lane's note)."""
    out = []
    for r in rows:
        note = str(r.get("note") or "")
        if r.get("enabled") or paused_mark not in note:
            continue
        why = note.split(paused_mark, 1)[1]
        out.append(_item("breaker", "S2", f"the {r['lane']} lane is paused", key=str(r["lane"]), detail=why, area=f"the {r['lane']} lane",
                         by="S2's breaker", ref={"lane": r["lane"]}))  # fmt: skip
    return out


def sort(items: list[dict]) -> list[dict]:
    """By category (the taxonomy's order), then what is at stake (dollars, then minutes, then how many), newest first."""
    newest = sorted(items, key=lambda i: i["at"] or "", reverse=True)  # sorted is stable: the newest stays first among equals
    return sorted(newest, key=lambda i: (CATEGORIES.index(i["category"]), -(i["usd"] or 0), -(i["minutes"] or 0), -i["count"]))


def counts(items: list[dict]) -> dict[str, int]:
    out = dict.fromkeys(CATEGORIES, 0)
    for i in items:
        out[i["category"]] += 1
    return out


# ---------------------------------------------------------------- read from the store


def _read_gate(since: datetime) -> tuple[list[dict], dict[str, str]]:
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        refused = s.execute(text(
            "select g.at, g.name, g.place, p.policy, p.why from s3.gate_decisions g "
            "join s3.gate_policy_decisions p on p.decision_id = g.id "
            "where g.verdict = 'refused' and p.how = 'refused' and g.at >= :since order by g.at desc limit 500"
        ), {"since": since}).all()  # fmt: skip
        passed = s.execute(text(
            "select name, max(at) from s3.gate_decisions where verdict = 'passed' and at >= :since and name is not null group by name"
        ), {"since": since}).all()  # fmt: skip
    return [dict(r._mapping) for r in refused], {r[0]: _iso(r[1]) for r in passed}


def _read_audits(since: datetime) -> list[dict]:
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Audit

    with store.session() as s:
        return [{"id": r.id, "at": r.at, "finding": r.finding, "instance": r.instance, "run_id": r.run_id, "action": r.action, "cost": r.cost}
                for r in s.scalars(select(Audit).where(Audit.at >= since).order_by(Audit.id.desc()))]  # fmt: skip


def _read_judgments(since: datetime) -> list[dict]:
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Judgment

    with store.session() as s:
        rows = s.scalars(select(Judgment).where(Judgment.at >= since).order_by(Judgment.id.desc())).all()
        latest: dict[str, Judgment] = {}
        for r in rows:  # the latest reading of each fit-out stands
            latest.setdefault(f"{r.kind}:{r.subject}", r)
        return [{"id": r.id, "at": r.at, "judge": r.judge, "kind": r.kind, "subject": r.subject, "known": r.known,
                 "verdict": r.verdict or {}, "outcome": r.outcome} for r in latest.values()]  # fmt: skip


def _read_lanes() -> list[dict]:
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        return [dict(r._mapping) for r in s.execute(text("select lane, enabled, note from s2.lane_defs")).all()]


def inbox(days: int = DAYS) -> dict:
    """Every piece of feedback the systems have sent up to S5, sorted by the taxonomy. A source that cannot be read
    is named in `unread` and the rest still come back."""
    from thorp.viable.s2_coordination import lanes
    from thorp.viable.s3_control import cycle
    from thorp.viable.s5_policy import proposals

    since = datetime.now(UTC) - timedelta(days=days)
    items: list[dict] = []
    unread: dict[str, str] = {}

    def take(name: str, fn) -> None:
        try:
            items.extend(fn())
        except Exception as e:  # noqa: BLE001 - one source failing must not blank the inbox
            unread[name] = repr(e)[:200]

    take("S5 proposals", lambda: from_proposals(proposals.rows("open")))
    take("S3 cycle", lambda: from_cycle(cycle.latest()))
    take("S3 gate", lambda: from_gate(*_read_gate(since)))
    take("S4 judge", lambda: from_judgments(_read_judgments(since)))
    take("S3* charter audit", lambda: from_audits(_read_audits(since)))
    take("S2 lanes", lambda: from_lanes(_read_lanes(), getattr(lanes, "PAUSED", " | paused ")))
    items = sort(items)
    return {"version": VERSION, "at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"), "days": days,
            "counts": counts(items), "items": items, "unread": unread}  # fmt: skip


def taxonomy() -> dict:
    """The taxonomy itself, for a page or a reader that wants to show what each category means."""
    return {
        "version": VERSION, "adopted": ADOPTED,
        "categories": [{"key": k, **ABOUT[k]} for k in CATEGORIES],
        "kinds": [{"key": k, "category": c, "about": a} for k, (c, a) in KINDS.items()],
        "sources": list(SOURCES),
    }  # fmt: skip


def for_s4(days: int = DAYS) -> dict:
    """What S4 reads when it plans: each category with what it asks of S4 and its items, most at stake first."""
    got = inbox(days)
    return {
        "version": VERSION, "at": got["at"], "unread": got["unread"],
        "categories": [{"key": k, **ABOUT[k], "items": [i for i in got["items"] if i["category"] == k]} for k in CATEGORIES],
    }  # fmt: skip


def payload(days: int = DAYS) -> dict:
    """The S5 page's feedback: the taxonomy and the inbox."""
    out = inbox(days)
    out["taxonomy"] = taxonomy()
    return out


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="thorp feedback", description="S5: the feedback the systems send up, by the taxonomy")
    p.add_argument("--days", type=int, default=DAYS)
    p.add_argument("--category", choices=[c.lower() for c in CATEGORIES])
    a = p.parse_args(argv)
    got = for_s4(a.days)
    for c in got["categories"]:
        if a.category and c["key"].lower() != a.category:
            continue
        print(f"{c['key']} ({len(c['items'])}): {c['means']}; S4 should {c['s4']}")
        for i in c["items"]:
            stake = " ".join(x for x in (f"${i['usd']:.2f}" if i["usd"] else "", f"{i['minutes']:.0f} min" if i["minutes"] else "") if x)
            print(f"  [{i['kind']}] {i['source']}  {i['title']}" + (f"  ({stake})" if stake else ""))
            if i["detail"]:
                print(f"      {i['detail'][:200]}")
    for name, err in got["unread"].items():
        print(f"could not read {name}: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    with contextlib.suppress(BrokenPipeError):
        raise SystemExit(main(sys.argv[1:]))
