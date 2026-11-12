"""S3: the charter's resources and its gate, what a voyage on a hired GPU will cost and whether the terms allow it.

The quote (`estimate`) is the voyage's training arithmetic (6 FLOPs a parameter a token, the output layer and
attention counted, an allowance for the evaluators and the scaffold's own passes) over what the GPU class
delivers, plus the hours of making the ship ready and bringing it home, at the offer's price. `violations` holds
a quote to S5's terms (thorp/viable/s5_policy/charter.py); the gate asks it through liberty_machine.POLICIES["charter"].

The spend log (s3.spend_events in Postgres) is S3's account of the money: one line when a ship is hired, one when it is
released with what it cost. The week's spend counts what is released this week and what is still out, accruing.
Since 11 November a charter also writes an `at sea` line when its voyage starts on the box, carrying the overrun
deadline, so that `thorp charter attach` can take the ship up again; it counts for nothing in the spend.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

OVERHEAD = 1.15  # the evaluators, the scaffold's attending passes, checkpoints: over the training FLOPs


def params(cfg) -> dict[str, int]:
    """A GPTConfig's parameters, as both GPTs count them (no model built): 12 w^2 + 2 w a block, the embeddings,
    the final norm."""
    w = cfg.width
    emb = cfg.vocab * w + (0 if getattr(cfg, "positions", "learned") == "rope" else cfg.context * w)
    total = cfg.layers * (12 * w * w + 2 * w) + emb + w
    return {"total": total, "embedding": emb, "non_embedding": total - emb}


def train_flops(cfg, tokens: int) -> float:
    """6 N a token for the blocks and the tied output layer, 12 L T w a token for attention (Kaplan et al.)."""
    p = params(cfg)
    per_token = 6 * (p["non_embedding"] + cfg.vocab * cfg.width) + 12 * cfg.layers * cfg.context * cfg.width
    return per_token * tokens * OVERHEAD


def estimate(cfg, tokens: int, tflops: float, dph: float, setup_hours: float) -> dict:
    hours = train_flops(cfg, tokens) / (tflops * 1e12) / 3600 + setup_hours
    return {"hours": hours, "cost": hours * dph}


def violations(q: dict, t: dict) -> list[str]:
    """Where a quote breaks the terms, in words (empty when it keeps them)."""
    out = []
    gpu, dph = q.get("gpu"), float(q.get("dph", 0.0))
    if gpu not in t["gpus"]:
        out.append(f"the {gpu} is not a class the terms hire ({', '.join(t['gpus'])})")
    elif dph > float(t["gpus"][gpu]):
        out.append(f"${dph:.3f} an hour is over the {gpu}'s ceiling of ${float(t['gpus'][gpu]):.2f}")
    if t.get("verified") and not q.get("verified"):
        out.append("the host is not datacenter-verified")
    if float(q.get("reliability", 0.0)) < float(t.get("min_reliability", 0.0)):
        out.append(f"the host's reliability {float(q.get('reliability', 0.0)):.3f} is under {t['min_reliability']}")
    if float(q.get("inet_down", 0.0)) < float(t.get("min_inet_down_mbps", 0.0)):
        out.append(f"the host's line down ({float(q.get('inet_down', 0.0)):.0f} Mb/s) is too slow for the library")
    if float(q.get("inet_up", 0.0)) < float(t.get("min_inet_up_mbps", 0.0)):
        out.append(f"the host's line up ({float(q.get('inet_up', 0.0)):.0f} Mb/s) is too slow for the checkpoints")
    cost = float(q.get("cost", 0.0))
    if cost > float(t["voyage_budget"]):
        out.append(f"the quote (${cost:.2f}) is over one voyage's budget (${float(t['voyage_budget']):.2f})")
    spent = float(q.get("week_spent", 0.0))
    if spent + cost > float(t["weekly_budget"]):
        out.append(
            f"the week's spend (${spent:.2f}) and the quote (${cost:.2f}) are over the week's budget (${float(t['weekly_budget']):.2f})"
        )
    credit = q.get("credit")
    if credit is not None and float(credit) < cost * float(t.get("credit_margin", 1.0)):
        out.append(f"the account's credit (${float(credit):.2f}) does not cover the quote {t.get('credit_margin', 1.0)} times over")
    if int(q.get("instances_out", 0)) >= int(t.get("max_instances", 1)):
        out.append(f"{q.get('instances_out')} ship(s) already hired (the terms allow {t.get('max_instances', 1)} at once)")
    return out


# ---------------------------------------------------------------- the spend log


def record(event: str, **fields) -> dict:
    """One event of the spend (hired, released), kept in s3.spend_events; returns it as the log's line."""
    line = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "event": event, **fields}
    insert(line)
    return line


def insert(line: dict) -> None:
    from thorp import store
    from thorp.viable.records import SpendEvent

    rest = {k: v for k, v in line.items() if k not in ("at", "event", "instance", "run_id")}
    with store.session() as s:
        s.add(SpendEvent(at=datetime.fromisoformat(line["at"]), event=line["event"],
                         instance=None if line.get("instance") is None else int(line["instance"]),
                         run_id=line.get("run_id"), detail=json.loads(json.dumps(rest, default=str))))  # fmt: skip


def reprice(instance: int, dph: float) -> None:
    """Correct a hire to the rate Vast.ai is actually charging.

    The offer's `dph` is the GPU's price; the instance's `dph_total` adds its disk and bandwidth (12 November:
    the bridge was quoted and logged at $0.349/h while the instance was billed at $0.369/h). The hired line and,
    once it exists, the released line are both corrected, so the week's spend and the release's cost use the
    real rate. A released line's cost is recomputed from its own start and end."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import SpendEvent

    rate = float(dph)
    if rate <= 0:
        return
    with store.session() as s:
        rows = s.scalars(
            select(SpendEvent).where(
                SpendEvent.instance == int(instance), SpendEvent.event.in_(("hired", "released"))
            )
        ).all()
        for r in rows:
            detail = dict(r.detail or {})
            old = float(detail.get("dph") or 0.0)
            if old and abs(old - rate) > 1e-9:
                detail.setdefault("repriced_from", old)
            detail["dph"] = rate
            if r.event == "released" and detail.get("started") is not None and detail.get("ended") is not None:
                detail["cost"] = max(0.0, (float(detail["ended"]) - float(detail["started"])) / 3600) * rate
            r.detail = detail


def log() -> list[dict]:
    """Every event of the spend, oldest first, as the log's lines."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import SpendEvent

    with store.session() as s:
        return [
            {"at": r.at.astimezone(UTC).isoformat(timespec="seconds"), "event": r.event,
             **({"instance": r.instance} if r.instance is not None else {}),
             **({"run_id": r.run_id} if r.run_id is not None else {}), **(r.detail or {})}  # fmt: skip
            for r in s.scalars(select(SpendEvent).order_by(SpendEvent.at, SpendEvent.id))
        ]


def out_now(rows: list[dict] | None = None) -> list[dict]:
    """The hires not yet released: each 'hired' line with no 'released' line for its instance."""
    rows = log() if rows is None else rows
    gone = {r["instance"] for r in rows if r["event"] == "released"}
    return [r for r in rows if r["event"] == "hired" and r["instance"] not in gone]


def cost_of(hire: dict, until: float | None = None) -> float:
    """What a hire has run up by `until` as the spend log reckons it: its hours at the GPU's rate and, since 12
    November, the disk's (`storage_dph`, from the offer's $/GB/month), which Vast.ai bills apart from the GPU.
    The gigabytes moved are not known until the bill: `fold_billed` puts the bill in once it is in."""
    rate = float(hire["dph"]) + float(hire.get("storage_dph") or 0.0)
    return max(0.0, ((until or time.time()) - float(hire["started"])) / 3600) * rate


def week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    d = (now - timedelta(days=now.weekday())).date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def logged_week(now: datetime | None = None, rows: list[dict] | None = None) -> float:
    """This week's spend as the log reckons it: the released hires' costs, and what the ships still out have run up."""
    start = week_start(now).timestamp()
    rows = log() if rows is None else rows
    done = sum(float(r.get("cost", 0.0)) for r in rows if r["event"] == "released" and float(r.get("ended", 0)) >= start)
    return done + sum(cost_of(h) for h in out_now(rows))


def week_spent(now: datetime | None = None, charges: list[dict] | None = None) -> float:
    """This week's spend: the larger of what Vast.ai has billed since Monday (UTC) and what the log reckons.

    12 November: the log counted $4.18 for the week where Vast.ai had billed $6.52 (the disk and the gigabytes
    moved are billed apart from the GPU's hours, and four hires of 9 November had no cost on record). The bill is
    the truth for what is done; the log runs ahead of it for a ship still out, so the larger is taken. Without
    the bill (no key, the API down) the log alone answers, as before."""
    logged = logged_week(now)
    charges = billed() if charges is None else charges
    if not charges:
        return logged
    start = week_start(now).timestamp()
    end = start + 7 * 86400
    return max(logged, sum(c["amount"] for c in charges if start <= c["at"] < end))


# ---------------------------------------------------------------- the bill (Vast.ai's own charges)

BILLED_TTL_S = 600.0  # how long one reading of Vast.ai's charges is used before it is asked again
FOLD_AFTER_S = 1800.0  # a release is given its bill once it has been released this long (the last charges in)
_BILLED: dict = {"at": float("-inf"), "rows": None}


def _billed_file():
    from thorp import paths

    return paths.data_dir() / "charter" / "billed.json"


def billed(fetch=None, now: float | None = None) -> list[dict] | None:
    """Vast.ai's charges to this account (vast.Vast.charges), read at most every BILLED_TTL_S by any process (a
    copy is kept in data/charter/billed.json for the next). None when they cannot be had: no key, the API down
    and no copy, or THORP_VAST_BILLED=0. Never raises: the spend falls back to the log."""
    import os

    if os.environ.get("THORP_VAST_BILLED") == "0":
        return None
    now = time.time() if now is None else now
    if _BILLED["rows"] is not None and now - _BILLED["at"] < BILLED_TTL_S:
        return _BILLED["rows"]
    f = _billed_file()
    try:
        kept = json.loads(f.read_text())
        if now - float(kept["at"]) < BILLED_TTL_S:
            _BILLED.update(at=float(kept["at"]), rows=kept["rows"])
            return kept["rows"]
    except Exception:  # noqa: BLE001 - no copy yet, or a torn one
        kept = None
    try:
        if fetch is None:
            from thorp.viable.s1_operations.vast import Vast, api_key, http_transport

            rows = Vast(http_transport(api_key(), retries=1)).charges()
        else:
            rows = fetch()
    except Exception:  # noqa: BLE001 - no key, or Vast.ai not answering: the last copy, however old, or nothing
        return (kept or {}).get("rows")
    _BILLED.update(at=now, rows=rows)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"at": now, "rows": rows}))
        tmp.replace(f)
    except OSError:
        pass
    return rows


def by_instance(charges: list[dict]) -> dict[int, dict[str, float]]:
    """The charges summed an instance a kind: {instance: {"gpu": $, "storage": $, "download": $, ...}}."""
    out: dict[int, dict[str, float]] = {}
    for c in charges:
        if c.get("instance") is None:
            continue
        k = out.setdefault(int(c["instance"]), {})
        k[c["kind"]] = k.get(c["kind"], 0.0) + float(c["amount"])
    return out


def fold_billed(charges: list[dict] | None = None, now: float | None = None) -> list[dict]:
    """Each released hire given its bill: `cost` becomes what Vast.ai billed for the instance (every kind), the
    log's own reckoning is kept as `cost_logged`, and the kinds as `billed`. Only a release FOLD_AFTER_S old or
    more (a bill still coming in is not final); a hire Vast.ai billed nothing for keeps its reckoning. Again on
    every call, so a late charge is taken in. Returns what changed: {instance, logged, billed}. Never raises."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import SpendEvent

    charges = billed() if charges is None else charges
    if not charges:
        return []
    now = time.time() if now is None else now
    bills = by_instance(charges)
    changed = []
    try:
        with store.session() as s:
            for r in s.scalars(select(SpendEvent).where(SpendEvent.event == "released")).all():
                detail = dict(r.detail or {})
                b = bills.get(int(r.instance)) if r.instance is not None else None
                if not b or now - float(detail.get("ended") or now) < FOLD_AFTER_S:
                    continue
                total = round(sum(b.values()), 6)
                if detail.get("billed") == b and abs(float(detail.get("cost") or 0.0) - total) < 1e-9:
                    continue
                detail.setdefault("cost_logged", detail.get("cost"))
                detail["cost"], detail["billed"] = total, b
                r.detail = detail
                changed.append({"instance": r.instance, "logged": detail["cost_logged"], "billed": total})
    except Exception:  # noqa: BLE001 - the bill is an improvement on the record, never a reason to fail
        return changed
    return changed
