"""The dash server's own performance, sampled (/settings/server's chart).

`thorp dash` starts one sampler thread (server.serve, via `start`): every twenty seconds it writes this
process's CPU — the CPU seconds it spent over the interval, as a percentage of one core — and its resident
memory, to data/dash/perf.jsonl. The file keeps eight days: the week's chart and a day of margin.

`history` reads it back as one point per bucket — a minute for the last hour, five minutes for the day,
half an hour for the week — the mean of each bucket, null where nothing was sampled. A line that breaks is
a time the dashboard was not running, which is also why a restarted server keeps its past: the file is
the history, not the process.

A sample is this process alone. A voyage trains in its own process, so the chart is what the dashboard
costs, not what it is watching; the queue and the store have their own pages.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from thorp import paths

STEP = 20.0  # one sample every twenty seconds
KEEP = 8 * 24 * 3600  # eight days: the week's chart, and a day of margin
RANGES = {"1h": (3600, 60), "24h": (86400, 300), "7d": (7 * 86400, 1800)}

_LOCK = threading.Lock()  # the read cache
_WRITE = threading.Lock()  # the file: one appender, and the prune that rewrites it
_STARTED = False
_READ: dict = {"key": None, "rows": []}


class _TaskInfo(ctypes.Structure):
    """macOS's proc_taskinfo (libproc), whose resident size is the first reading of memory's two."""

    _fields_ = [
        ("pti_virtual_size", ctypes.c_uint64),
        ("pti_resident_size", ctypes.c_uint64),
        ("pti_total_user", ctypes.c_uint64),
        ("pti_total_system", ctypes.c_uint64),
        ("pti_threads_user", ctypes.c_uint64),
        ("pti_threads_system", ctypes.c_uint64),
        ("pti_policy", ctypes.c_int32),
        ("pti_faults", ctypes.c_int32),
        ("pti_pageins", ctypes.c_int32),
        ("pti_cow_faults", ctypes.c_int32),
        ("pti_messages_sent", ctypes.c_int32),
        ("pti_messages_received", ctypes.c_int32),
        ("pti_syscalls_mach", ctypes.c_int32),
        ("pti_syscalls_unix", ctypes.c_int32),
        ("pti_csw", ctypes.c_int32),
        ("pti_threadnum", ctypes.c_int32),
        ("pti_numrunning", ctypes.c_int32),
        ("pti_priority", ctypes.c_int32),
    ]


_PROC: object = None  # libproc, False when this Mac cannot load it


def _libproc():
    """libproc, loaded once, or None: asking it for a process is cheaper than `ps` and needs no exec."""
    global _PROC
    if _PROC is not None:
        return _PROC or None
    try:
        _PROC = ctypes.CDLL(ctypes.util.find_library("proc") or "/usr/lib/libproc.dylib")
        _PROC.proc_pidinfo.argtypes = [  # type: ignore[attr-defined]
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        _PROC.proc_pidinfo.restype = ctypes.c_int  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        _PROC = False
        return None
    return _PROC


def store() -> Path:
    """Where the samples live (data/dash/perf.jsonl, under THORP_DATA)."""
    return paths.data_dir() / "dash" / "perf.jsonl"


def rss() -> int | None:
    """The process's resident memory in bytes, or None: libproc on macOS, /proc on Linux, `ps` if neither."""
    if sys.platform == "darwin":
        lib = _libproc()
        info = _TaskInfo()
        if lib is not None and lib.proc_pidinfo(  # type: ignore[attr-defined]
            os.getpid(), 4, 0, ctypes.byref(info), ctypes.sizeof(info)
        ) == ctypes.sizeof(info):
            return int(info.pti_resident_size)
    try:
        with open("/proc/self/statm", encoding="ascii") as f:
            pages = int(f.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        pass
    try:
        r = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            capture_output=True,
            text=True,
            timeout=5,
        )
        kb = int(r.stdout.strip() or 0)
        return kb * 1024 if kb > 0 else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def start() -> None:
    """Begin sampling, once (a second `thorp dash` in the same process keeps the first thread)."""
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        _STARTED = True
    threading.Thread(target=_loop, name="dash-perf", daemon=True).start()


def _loop() -> None:
    """A sample every STEP, for as long as the process lives: the first is one interval in, so its CPU is
    a reading rather than a zero."""
    _prune()
    prev_wall = time.monotonic()
    prev_cpu = time.process_time()
    pruned = time.time()
    while True:
        time.sleep(STEP)
        wall = time.monotonic()
        cpu = time.process_time()
        seconds = wall - prev_wall
        row = {
            "t": round(time.time(), 1),
            "cpu": round(100.0 * (cpu - prev_cpu) / seconds, 1) if seconds > 0 else None,
            "rss": rss(),
        }
        prev_wall, prev_cpu = wall, cpu
        _append(row)
        if time.time() - pruned > 3600:  # an hourly prune keeps the file to KEEP
            _prune()
            pruned = time.time()


def _append(row: dict) -> bool:
    f = store()
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE, f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        return True
    except OSError:
        return False


def _load() -> list[dict]:
    """Every sample on file, oldest first, cached until the file changes."""
    f = store()
    try:
        st = f.stat()
    except OSError:
        return []
    key = (str(f), st.st_mtime_ns, st.st_size)
    with _LOCK:
        if _READ["key"] == key:
            return _READ["rows"]
    rows: list[dict] = []
    try:
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue  # a half-written last line: the next read has it whole
                if isinstance(row, dict) and isinstance(row.get("t"), (int, float)):
                    rows.append(row)
    except OSError:
        return []
    rows.sort(key=lambda r: r["t"])
    with _LOCK:
        _READ["key"] = key
        _READ["rows"] = rows
    return rows


def _prune() -> int:
    """Drop the samples older than KEEP, rewriting the file only when there are some."""
    f = store()
    rows = _load()
    cut = time.time() - KEEP
    kept = [r for r in rows if r["t"] >= cut]
    if len(kept) == len(rows):
        return 0
    tmp = f.with_suffix(".tmp")
    try:
        with _WRITE:
            tmp.write_text(
                "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in kept), encoding="utf-8"
            )
            os.replace(tmp, f)
    except OSError:
        return 0
    with _LOCK:
        _READ["key"] = None
    return len(rows) - len(kept)


def history(rng: str = "24h", now: float | None = None) -> dict:
    """The last hour, day or week as one point per bucket: the mean CPU and memory of each, null where
    nothing was sampled, and the summary of the samples the range holds. `now` is for the tests."""
    if rng not in RANGES:
        rng = "24h"
    span, step = RANGES[rng]
    now = time.time() if now is None else now
    rows = _load()
    first = int((now - span) // step) * step
    n = int((now - first) // step) + 1
    cpu_sum, cpu_n = [0.0] * n, [0] * n
    rss_sum, rss_n = [0.0] * n, [0] * n
    inside = [r for r in rows if first <= r["t"] <= now]
    for r in inside:
        i = int((r["t"] - first) // step)
        if not 0 <= i < n:  # a clock that went backwards, or a sample ahead of `now`
            continue
        if isinstance(r.get("cpu"), (int, float)):
            cpu_sum[i] += float(r["cpu"])
            cpu_n[i] += 1
        if isinstance(r.get("rss"), (int, float)):
            rss_sum[i] += float(r["rss"])
            rss_n[i] += 1
    points = [
        {
            "t": first + i * step,
            "cpu": round(cpu_sum[i] / cpu_n[i], 2) if cpu_n[i] else None,
            "rss": int(rss_sum[i] / rss_n[i]) if rss_n[i] else None,
        }
        for i in range(n)
    ]
    cpus = [float(r["cpu"]) for r in inside if isinstance(r.get("cpu"), (int, float))]
    rsses = [float(r["rss"]) for r in inside if isinstance(r.get("rss"), (int, float))]
    return {
        "range": rng,
        "step": step,
        "from": first,
        "to": first + (n - 1) * step,
        "points": points,
        "now": rows[-1] if rows else None,
        "stats": {
            "count": len(inside),
            "cpu_mean": round(sum(cpus) / len(cpus), 2) if cpus else None,
            "cpu_peak": round(max(cpus), 2) if cpus else None,
            "rss_mean": int(sum(rsses) / len(rsses)) if rsses else None,
            "rss_peak": int(max(rsses)) if rsses else None,
        },
        "first": rows[0]["t"] if rows else None,
        "kept_days": KEEP // 86400,
        "step_sampled": STEP,
        "pid": os.getpid(),
    }
