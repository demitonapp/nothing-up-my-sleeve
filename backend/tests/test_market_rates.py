"""The market's rates (thorp/viable/s4_intelligence/market.py, 8 November): a measured rate counts the readings
between steps, and a size a class has not sailed is scaled from one it has, by FLOPs, so a quote's deadline
(its hours times the overrun) does not bring a ship home before it docks."""

import pytest

from thorp.models import registry
from thorp.viable.s4_intelligence import market


def test_a_measured_rate_counts_the_readings(monkeypatch):
    rows = [{"event": "released", "gpu": "RTX 4090", "preset": "9m", "tokens_per_s": 648_000.0, "run_id": "r",
             "started": 0.0, "ended": 0.35 * 3600 + 2136.0}]  # fmt: skip
    monkeypatch.setattr(market.s3, "log", lambda: rows)
    monkeypatch.setattr(market, "_wall_rate", lambda r: 269_221_888 / 2136.0)
    assert market.throughput("RTX 4090", "9m") == pytest.approx(126_040, rel=1e-3)  # P1: the slower of the two


def test_an_unsailed_size_is_scaled_from_a_sailed_one(monkeypatch):
    monkeypatch.setattr(market, "throughput", lambda gpu, preset: 126_000.0 if (gpu, preset) == ("RTX 4090", "9m") else None)
    monkeypatch.setattr(market, "mac_rate", lambda preset: None)
    cfg = registry.config("50m", 2048, 1024, "rope")
    q = market.price(cfg, "50m", 682_885_120, {"gpu": "RTX 4090", "dph": 0.34})
    assert "scaled by FLOPs from its 9m" in q["speed"]
    assert q["hours"] > 10  # the 9m's rate shared by about ten times the FLOPs a token: slow on purpose
    none = market.price(cfg, "50m", 682_885_120, {"gpu": "RTX 5090", "dph": 0.46})
    assert none["speed"].startswith("guessed")  # a class that has sailed nothing keeps the FLOP guess
