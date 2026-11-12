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
    return max(0.0, ((until or time.time()) - float(hire["started"])) / 3600) * float(hire["dph"])


def week_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    d = (now - timedelta(days=now.weekday())).date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def week_spent(now: datetime | None = None) -> float:
    """This week's spend: the released hires' costs, and what the ships still out have run up."""
    start = week_start(now).timestamp()
    rows = log()
    done = sum(float(r.get("cost", 0.0)) for r in rows if r["event"] == "released" and float(r.get("ended", 0)) >= start)
    return done + sum(cost_of(h) for h in out_now(rows))
