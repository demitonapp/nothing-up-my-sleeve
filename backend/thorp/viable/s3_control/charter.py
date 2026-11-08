"""S3: the charter's resources and its gate, what a voyage on a hired GPU will cost and whether the terms allow it.

The quote (`estimate`) is the voyage's training arithmetic (6 FLOPs a parameter a token, the output layer and
attention counted, an allowance for the evaluators and the scaffold's own passes) over what the GPU class
delivers, plus the hours of making the ship ready and bringing it home, at the offer's price. `violations` holds
a quote to S5's terms (thorp/viable/s5_policy/charter.py); the gate asks it through vsm.POLICIES["charter"].

The spend log (data/charter-log.jsonl) is S3's account of the money: one line when a ship is hired, one when it is
released with what it cost. The week's spend counts what is released this week and what is still out, accruing.
"""

from __future__ import annotations

import contextlib
import json
import time
from datetime import UTC, datetime, timedelta

from thorp import paths

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


def _log_path():
    return paths.data_dir() / "charter-log.jsonl"


def record(event: str, **fields) -> dict:
    line = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "event": event, **fields}
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def log() -> list[dict]:
    p = _log_path()
    if not p.exists():
        return []
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        with contextlib.suppress(ValueError):
            rows.append(json.loads(ln))
    return rows


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
