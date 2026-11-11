"""The settings page's Vast.ai table (thorp.dash.settings.chip_stats and vast): one row a GPU chip class,
from the market's price reads (s4.market_reads), the spend log's voyages (s3.spend_events) and the terms
that bound them (s5.charter).

The store is read only in `vast`; `chip_stats` is pure, so the arithmetic — the latest read against the
range, a hire that never reached the box, a class the terms hire but no one has read — is tested here
without Postgres. `vast` itself is tested with its four store reads replaced.
"""

from __future__ import annotations

import json

from thorp.dash import settings

TERMS = {"gpus": {"RTX 4090": 0.5, "H100 SXM": 2.6}, "weekly_budget": 30.0, "voyage_budget": 10.0}


def test_reads_and_voyages_per_chip():
    reads = [
        {"at": "2026-11-08T01:00:00+00:00", "gpu": "RTX 4090", "dph": 0.40, "reliability": 0.99},
        {"at": "2026-11-09T01:00:00+00:00", "gpu": "RTX 4090", "dph": 0.50, "reliability": 0.97},
        {"at": "2026-11-10T01:00:00+00:00", "gpu": "A100", "dph": 1.20, "reliability": 0.95},
    ]
    events = [
        {
            "at": "2026-11-08T02:00:00+00:00",
            "event": "hired",
            "instance": 1,
            "gpu": "RTX 4090",
            "dph": 0.4,
        },
        {
            "at": "2026-11-08T05:00:00+00:00",
            "event": "released",
            "instance": 1,
            "gpu": "RTX 4090",
            "started": 1000,
            "ended": 1000 + 3 * 3600,
            "cost": 1.2,
            "tokens_per_s": 110509.2,
            "preset": "50m",
        },
        {
            "at": "2026-11-09T02:00:00+00:00",
            "event": "hired",
            "instance": 2,
            "gpu": "RTX 4090",
            "dph": 0.5,
        },
        {
            "at": "2026-11-09T02:10:00+00:00",
            "event": "released",
            "instance": 2,
            "why": "ssh refused",
        },
        {
            "at": "2026-11-09T03:00:00+00:00",
            "event": "hired",
            "instance": 3,
            "gpu": "RTX 4090",
            "dph": 0.5,
        },
    ]
    rows = settings.chip_stats(reads, events, TERMS)
    # the terms' classes first (read or not), then a class the log knows and the terms do not
    assert [r["gpu"] for r in rows] == ["RTX 4090", "H100 SXM", "A100"]

    r = rows[0]
    assert (r["reads"], r["price"], r["min"], r["median"], r["max"]) == (2, 0.5, 0.4, 0.45, 0.5)
    assert r["reliability"] == 0.97 and r["last_read"] == "2026-11-09T01:00:00+00:00"
    # three hires: one released with its cost, one released before it sailed, one still out
    assert (r["hires"], r["out"]) == (3, 1)
    assert (r["hours"], r["spent"]) == (3.0, 1.2)
    assert (r["rate"], r["rate_preset"]) == (110509, "50m")

    h = rows[1]  # hired by the terms, never read and never sailed: a row that says so
    assert (h["ceiling"], h["reads"], h["price"], h["hires"], h["guess"]) == (
        2.6,
        0,
        None,
        0,
        220.0,
    )

    assert (rows[2]["ceiling"], rows[2]["reads"], rows[2]["guess"]) == (None, 1, None)


def test_a_read_without_a_price_is_not_counted():
    reads = [
        {"at": "2026-11-08T01:00:00+00:00", "gpu": "RTX 4090", "dph": None},
        {"at": "2026-11-09T01:00:00+00:00", "gpu": "RTX 4090", "dph": 0.4},
    ]
    r = settings.chip_stats(reads, [], TERMS)[0]
    assert (r["reads"], r["price"]) == (1, 0.4)


def test_vast_assembles_the_panel_without_the_key(monkeypatch):
    from thorp import providers
    from thorp.viable.s3_control import charter as s3
    from thorp.viable.s4_intelligence import market
    from thorp.viable.s5_policy import charter as s5

    monkeypatch.setattr(s5, "terms", lambda: dict(TERMS))
    monkeypatch.setattr(
        market,
        "reads",
        lambda limit=500: [
            {"at": "2026-11-08T01:00:00+00:00", "gpu": "RTX 4090", "dph": 0.4, "reliability": 0.99}
        ],
    )
    monkeypatch.setattr(
        s3,
        "log",
        lambda: [
            {
                "at": "2026-11-08T02:00:00+00:00",
                "event": "hired",
                "instance": 1,
                "gpu": "RTX 4090",
                "dph": 0.4,
            },
            {
                "at": "2026-11-08T05:00:00+00:00",
                "event": "released",
                "instance": 1,
                "gpu": "RTX 4090",
                "started": 1000,
                "ended": 4600,
                "cost": 1.5,
                "tokens_per_s": 100000,
                "preset": "50m",
            },
        ],
    )
    monkeypatch.setattr(s3, "week_spent", lambda now=None: 1.5)
    monkeypatch.setattr(providers, "vast_key", lambda: "secret-key-value")
    monkeypatch.setattr(providers, "vast_seats", lambda: 2)

    v = settings.vast()
    assert v["key"] is True and v["seats"] == 2
    assert v["week"] == {"spent": 1.5, "budget": 30.0}
    assert v["totals"] == {"reads": 1, "hires": 1, "hours": 1.0, "spent": 1.5}
    assert v["out"] == 0 and v["chips"][0]["gpu"] == "RTX 4090"
    # the key is never sent, only whether it is there
    assert "secret-key-value" not in json.dumps(v)
