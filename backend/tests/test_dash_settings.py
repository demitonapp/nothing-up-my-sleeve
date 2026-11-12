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


def test_charter_phases_from_its_own_log(tmp_path, monkeypatch):
    """Where a hire's time went, from the charter's log: a 55-minute data tar, then the board, the torch
    environment, the run and the bring-home, each timed; joined to the spend log by instance for its name,
    quote and release."""
    from thorp import paths
    from thorp.viable.s3_control import charter as s3

    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "charter.log").write_text(
        "\n".join([
            "[09:32:54] charter: RTX 4090 offer 54486157 at $0.363/h, about 1.0 h, $0.36 (measured 126,021 tokens/s)",
            "[09:33:19] charter: instance 60277983 is up (ssh3.vast.ai:10126); waiting for its ssh",
            "[09:33:40] charter: ssh answered (try 2); fitting out",
            "[09:33:40] [box] ssh: set -e; command -v rsync",
            "[09:33:52] [box] ssh done, exit 0 (11.9s)",
            "[09:33:52] [box] tar 1089 files to /",
            "[09:34:03] [box] tar done (1089 files) (11.0s)",
            "[09:34:04] [box] tar 9543 files to data",
            "[10:29:35] [box] tar done (9543 files) (3331.8s)",
            "[10:29:36] [box] rsync 1 files to data",
            "[10:35:36] [box] rsync done (1 files) (360.0s)",
            "[10:35:36] [box] rsync 1 files to /",
            "[10:35:43] [box] rsync done (1 files) (7.0s)",
            "[10:35:43] [box] syncing the box's environment (uv sync --group torch)",
            "[10:35:44] [box] ssh: cd /root/thorp && ~/.local/bin/uv sync",
            "[10:41:46] [box] ssh done, exit 0 (362.2s)",
            "[10:41:47] charter: 9m@v0.0.6-candidate is at sea on instance 60277983",
            "[11:00:00] charter: past 1.5 h (the quote times the overrun): bringing it home",
            "[11:08:00] charter: 9m@v0.0.6-candidate overran; instance 60277983 released; $0.55 for 1.58 h",
        ]) + "\n"
    )
    start = 1_794_439_974.0
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(s3, "log", lambda: [
        {"at": "2026-11-12T09:32:55+10:00", "event": "hired", "instance": 60277983, "gpu": "RTX 4090",
         "dph": 0.362962962962963, "quote_hours": 0.9806948517975024, "name": "9m@v0.0.6-candidate",
         "started": start},
        {"at": "2026-11-12T11:08:00+10:00", "event": "released", "instance": 60277983,
         "started": start, "ended": start + 5700, "cost": 0.55, "status": "overran", "tokens_per_s": 126021},
    ])

    c = settings.charters()["charters"][0]
    assert (c["name"], c["status"], c["gpu"], c["quote_hours"]) == ("9m@v0.0.6-candidate", "overran", "RTX 4090", 0.981)
    assert (c["phases"]["provision"], c["phases"]["ssh"], c["phases"]["code"]) == (25, 21, 11)
    assert c["phases"]["data"] == 3332  # the 55-minute tar, the phase the page exists to name
    assert c["phases"]["board"] == 368  # the manifest and the spec, from the data's end to uv sync
    assert c["phases"]["env"] == 362
    assert (c["phases"]["train"], c["phases"]["home"]) == (1093, 480)
    assert (c["total_s"], c["cost"], c["open"]) == (5700, 0.55, None)
