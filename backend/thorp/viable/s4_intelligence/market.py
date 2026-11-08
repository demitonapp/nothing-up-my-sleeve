"""S4: the charter market, what each GPU class the terms allow costs today and what it would cost to sail this
voyage on it, so the cheapest ship for the voyage (not the cheapest hour) is hired.

A class's speed is S4's guess (s5_policy.charter.EFFECTIVE_TFLOPS) until a voyage of that class and preset has
sailed; from then on the measured rate (tokens a second, from the spend log's 'released' lines) is used. Every
reading of the market is kept (data/charter-market.jsonl), so the prices can be watched over the week.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime

from thorp import paths
from thorp.viable.s3_control import charter as s3
from thorp.viable.s5_policy import charter as s5


def _wall_rate(r: dict) -> float | None:
    """A released voyage's rate at sea (tokens a second): the run's tokens over its time hired, less the set-up
    allowance, so the readings between steps count (8 November: P1's steps ran at 648k tokens a second, but its
    readings brought the voyage to about 126k; a quote at the steps' rate gives a deadline it cannot meet)."""
    with contextlib.suppress(Exception):
        from thorp.ledger import Ledger

        run = Ledger().get_run(r["run_id"]) or {}
        secs = float(r["ended"]) - float(r["started"]) - s5.SETUP_HOURS * 3600
        if run.get("tokens_seen") and secs > 60:
            return float(run["tokens_seen"]) / secs
    return None


def throughput(gpu: str, preset: str) -> float | None:
    """The measured rate (tokens a second) of the last voyages of this preset on this class, or None: the slower
    of the training steps' rate and the rate at sea, readings included."""
    rates = []
    for r in s3.log():
        if r["event"] == "released" and r.get("gpu") == gpu and r.get("preset") == preset and r.get("tokens_per_s"):
            wall = _wall_rate(r)
            rates.append(min(float(r["tokens_per_s"]), wall) if wall else float(r["tokens_per_s"]))
    return sum(rates[-3:]) / len(rates[-3:]) if rates else None


def scaled(gpu: str, cfg, preset: str) -> tuple[float, str] | None:
    """For a preset this class has not sailed: its measured rate on another preset, scaled by the FLOP ratio
    a token (the smaller the preset measured, the more its rate overstates the GPU's room, so this errs slow:
    a 9m on a 4090 left 41% of the GPU idle). (rate, the preset it came from) or None."""
    from thorp.models import registry

    best = None
    for other in registry.PRESETS:
        if other == preset:
            continue
        tps = throughput(gpu, other)
        if not tps:
            continue
        with contextlib.suppress(Exception):
            ocfg = registry.config(other, cfg.vocab, cfg.context, getattr(cfg, "positions", "rope"))
            r = tps * s3.train_flops(ocfg, 1) / s3.train_flops(cfg, 1)
            if best is None or r < best[0]:
                best = (r, other)
    return best


def mac_rate(preset: str) -> float | None:
    """This Mac's wall-clock rate (tokens a second, evals and all) on its finished voyages of this preset, the
    slowest of the last three, or None. The quote's floor until a GPU class has sailed the preset (2026-11-08, the
    parity run: the FLOP guess leaves out the evaluators and the scaffold's passes, and a 9m at width 192 is far
    from a GPU's peak, so a quote on it alone would bring a ship home before it docked)."""
    try:
        from thorp.ledger import Ledger

        rows = Ledger().query(
            "select tokens_seen, wall_minutes from runs where status='finished' and wall_minutes > 0 and tokens_seen > 0"
            " and json_extract(spec_json, '$.model.preset') = ? and coalesce(json_extract(spec_json, '$.model.backend'), 'mlx') = 'mlx'"
            " order by finished desc limit 3",
            [preset],
        )
    except Exception:  # noqa: BLE001  (no ledger: the FLOP guess alone)
        return None
    rates = [float(r["tokens_seen"]) / (float(r["wall_minutes"]) * 60) for r in rows]
    return min(rates) if rates else None


def price(cfg, preset: str, tokens: int, o: dict) -> dict:
    """What this voyage would cost on this offer: at the class's measured rate once it has sailed the preset;
    before that, at the FLOP guess or this Mac's own rate, whichever is slower (a GPU is not assumed faster than
    the Mac until it has shown it)."""
    tps = throughput(o["gpu"], preset)
    if tps:
        hours = tokens / tps / 3600 + s5.SETUP_HOURS
        how = f"measured {tps:,.0f} tokens/s"
    else:
        tf = s5.EFFECTIVE_TFLOPS.get(o["gpu"], 40.0)
        hours = s3.estimate(cfg, tokens, tf, o["dph"], s5.SETUP_HOURS)["hours"]
        how = f"guessed {tf:.0f} effective TFLOP/s"
        mac = mac_rate(preset)
        if mac and tokens / mac / 3600 + s5.SETUP_HOURS > hours:
            hours = tokens / mac / 3600 + s5.SETUP_HOURS
            how = f"unmeasured: at this Mac's {mac:,.0f} tokens/s, evals included (the guess was {tf:.0f} TFLOP/s)"
        sc = scaled(o["gpu"], cfg, preset)
        if sc and tokens / sc[0] / 3600 + s5.SETUP_HOURS > hours:
            hours = tokens / sc[0] / 3600 + s5.SETUP_HOURS
            how = f"unmeasured at this size: scaled by FLOPs from its {sc[1]}'s {sc[0]:,.0f} tokens/s here (the guess was {tf:.0f} TFLOP/s)"
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
