"""S4: the charter market, what each GPU class the terms allow costs today and what it would cost to sail this
voyage on it, so the cheapest ship for the voyage (not the cheapest hour) is hired.

A class's speed is S4's guess (s5_policy.charter.EFFECTIVE_TFLOPS) until a voyage of that class and preset has
sailed; from then on the measured rate (tokens a second, from the spend log's 'released' lines) is used. Every
reading of the market is kept (data/charter-market.jsonl), so the prices can be watched over the week.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from thorp import paths
from thorp.viable.s3_control import charter as s3
from thorp.viable.s5_policy import charter as s5


def throughput(gpu: str, preset: str) -> float | None:
    """The measured training rate (tokens a second) of the last voyages of this preset on this class, or None."""
    rates = [
        float(r["tokens_per_s"])
        for r in s3.log()
        if r["event"] == "released" and r.get("gpu") == gpu and r.get("preset") == preset and r.get("tokens_per_s")
    ]
    return sum(rates[-3:]) / len(rates[-3:]) if rates else None


def price(cfg, preset: str, tokens: int, o: dict) -> dict:
    """What this voyage would cost on this offer."""
    tps = throughput(o["gpu"], preset)
    if tps:
        hours = tokens / tps / 3600 + s5.SETUP_HOURS
        how = f"measured {tps:,.0f} tokens/s"
    else:
        tf = s5.EFFECTIVE_TFLOPS.get(o["gpu"], 40.0)
        hours = s3.estimate(cfg, tokens, tf, o["dph"], s5.SETUP_HOURS)["hours"]
        how = f"guessed {tf:.0f} effective TFLOP/s"
    return {**o, "hours": hours, "cost": hours * o["dph"], "speed": how}


def quotes(vast, cfg, preset: str, tokens: int, terms: dict, gpus: list[str] | None = None) -> list[dict]:
    """The cheapest offer of each class (or of `gpus`), priced for this voyage, cheapest voyage first."""
    out = []
    for gpu in gpus or list(terms["gpus"]):
        if gpu not in terms["gpus"]:
            continue
        offers = vast.search(gpu, terms, limit=5)
        if offers:
            out.append(price(cfg, preset, tokens, offers[0]))
    out.sort(key=lambda q: q["cost"])
    _keep(out)
    return out


def _keep(qs: list[dict]) -> None:
    try:
        p = paths.data_dir() / "charter-market.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            at = datetime.now(UTC).isoformat(timespec="seconds")
            for q in qs:
                f.write(json.dumps({"at": at, **{k: q[k] for k in ("gpu", "offer_id", "dph", "reliability", "hours", "cost")}}) + "\n")
    except Exception:  # noqa: BLE001  (a reading not kept never costs a quote)
        pass
