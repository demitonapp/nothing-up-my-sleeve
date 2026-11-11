"""The dash server's own performance samples (thorp.dash.perf): the file the sampler appends to, the
buckets the settings chart reads back, and the retention that keeps the file to the week.

The sampler thread itself is the server's (server.serve calls start): a sample's CPU is the interval's
CPU time over its wall time, so an idle dashboard reads near zero and a page that reads the ledger reads
high. `history` turns the raw samples into one point per bucket, null where the dashboard was not running,
which is what the chart draws as a break in the line.
"""

from __future__ import annotations

import json
import time

from thorp.dash import perf


def write(tmp_path, monkeypatch, rows: list[dict]) -> None:
    monkeypatch.setenv("THORP_DATA", str(tmp_path))
    f = perf.store()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_buckets_are_means_and_gaps_are_null(tmp_path, monkeypatch):
    now = 1_800_000_000.0  # a whole minute: the buckets line up with it
    write(
        tmp_path,
        monkeypatch,
        [
            {"t": now - 590, "cpu": 1.0, "rss": 100},
            {"t": now - 580, "cpu": 3.0, "rss": 300},
            {"t": now - 570, "cpu": 5.0, "rss": 200},
            {"t": now - 30, "cpu": 8.0, "rss": 400},
        ],
    )
    h = perf.history("1h", now=now)
    assert h["range"] == "1h" and h["step"] == 60
    assert (
        len(h["points"]) == 61
    )  # the hour, the whole minute it starts on, and the minute `now` is in
    filled = [p for p in h["points"] if p["cpu"] is not None]
    assert [(p["t"], p["cpu"], p["rss"]) for p in filled] == [
        (now - 600, 3.0, 200),  # the mean of the three: (1+3+5)/3, (100+300+200)/3
        (now - 60, 8.0, 400),
    ]
    assert h["stats"]["count"] == 4
    assert (h["stats"]["cpu_mean"], h["stats"]["cpu_peak"]) == (4.25, 8.0)
    assert (h["stats"]["rss_mean"], h["stats"]["rss_peak"]) == (250, 400)
    assert h["now"] == {"t": now - 30, "cpu": 8.0, "rss": 400}
    assert h["first"] == now - 590


def test_the_ranges_and_their_buckets(tmp_path, monkeypatch):
    now = 1_800_000_000.0
    write(tmp_path, monkeypatch, [{"t": now - 10, "cpu": 1.0, "rss": 100}])
    assert (len(perf.history("1h", now=now)["points"]), perf.history("1h", now=now)["step"]) == (
        61,
        60,
    )
    assert (len(perf.history("24h", now=now)["points"]), perf.history("24h", now=now)["step"]) == (
        289,
        300,
    )
    assert (len(perf.history("7d", now=now)["points"]), perf.history("7d", now=now)["step"]) == (
        337,
        1800,
    )
    # an address the page does not know is the day, not an empty chart
    assert perf.history("90d", now=now)["range"] == "24h"


def test_no_samples_is_an_empty_week_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path))
    h = perf.history("7d")
    assert h["now"] is None and h["first"] is None and h["stats"]["count"] == 0
    assert h["points"] and all(p["cpu"] is None and p["rss"] is None for p in h["points"])


def test_the_machines_memory_from_vm_stat():
    text = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                   129910.
Pages active:                                 308548.
Pages wired down:                            1062385.
Anonymous pages:                              451107.
Pages occupied by compressor:                 235772.
Pages stored in compressor:                   358022.
"""
    # wired + anonymous + the compressor's pages, at 16 KiB a page (the other lines are not the three)
    assert perf.parse_vm_stat(text) == {"mem": (1062385 + 451107 + 235772) * 16384}
    assert perf.parse_vm_stat("no page size here") == {}
    assert perf.parse_vm_stat("page size of 4096 bytes\nPages wired down: 3.") == {}


def test_the_gpu_from_ioreg():
    text = """+-o AGXAcceleratorG18G  <class AGXAcceleratorG18G>
      "gpu-core-count" = 12
      "PerformanceStatistics" = {"In use system memory (driver)"=0,"Device Utilization %"=99,
        "In use system memory"=13987725312}"""
    assert perf.parse_ioreg(text) == {"gcpu": 99, "gmem": 13987725312, "gpu_cores": 12}
    assert perf.parse_ioreg("nothing") == {}


def test_the_machine_readings_are_bucketed(tmp_path, monkeypatch):
    now = 1_800_000_000.0
    write(
        tmp_path,
        monkeypatch,
        [
            {"t": now - 590, "cpu": 2.0, "rss": 100, "gcpu": 40, "mem": 1000},
            {"t": now - 580, "cpu": 4.0, "rss": 300, "gcpu": 60, "mem": 3000},
            {"t": now - 30, "cpu": 6.0, "rss": 500, "mem": None, "gcpu": None},
        ],
    )
    h = perf.history("1h", now=now)
    filled = [p for p in h["points"] if p["cpu"] is not None]
    assert (filled[0]["gcpu"], filled[0]["mem"]) == (50.0, 2000)
    assert (filled[-1]["gcpu"], filled[-1]["mem"]) == (
        None,
        None,
    )  # a time the machine was not read
    assert (h["stats"]["gcpu_peak"], h["stats"]["gcpu_mean"]) == (60.0, 50.0)
    assert (h["stats"]["mem_peak"], h["stats"]["mem_mean"]) == (3000, 2000)
    assert h["mem_total"] and h["mem_total"] > 0


def test_a_half_written_line_is_skipped(tmp_path, monkeypatch):
    now = 1_800_000_000.0
    write(tmp_path, monkeypatch, [{"t": now - 600, "cpu": 2.0, "rss": 10}])
    with perf.store().open("a", encoding="utf-8") as f:
        f.write('{"t": 1800000000, "cpu": 4.')  # the sampler died mid-line
    h = perf.history("1h", now=now)
    assert h["stats"]["count"] == 1 and h["stats"]["cpu_mean"] == 2.0


def test_append_writes_one_line_a_sample(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path))
    assert perf._append({"t": time.time(), "cpu": 1.5, "rss": 2048}) is True
    rows = perf._load()
    assert len(rows) == 1 and rows[0]["cpu"] == 1.5 and rows[0]["rss"] == 2048


def test_prune_keeps_the_week_only(tmp_path, monkeypatch):
    now = time.time()
    write(
        tmp_path,
        monkeypatch,
        [
            {"t": now - perf.KEEP - 3600, "cpu": 9.0, "rss": 9},  # older than the week: dropped
            {"t": now - 600, "cpu": 1.0, "rss": 100},
        ],
    )
    assert perf._prune() == 1
    rows = perf._load()
    assert [r["cpu"] for r in rows] == [1.0]
    assert perf._prune() == 0  # nothing left to drop
