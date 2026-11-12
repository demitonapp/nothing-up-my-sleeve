"""The settings page (/settings, the cog in the header; 11 November, Justin: "a settings cog in the top
right hand of the UI that allows me to see things, like storage used").

Read-only, except for the store switch: this module reads what the dashboard runs on, in one payload
(`payload`, served at /api/settings); the switch itself is `POST /api/store/switch` (thorp.onboard.api).

- **storage**: the disk the data sits on, and what Nothing up my sleeve keeps on it, part by part (the
  checkpoints, the store's files, the texts, the outside models' cache, ...), measured with `du` so a size
  is the space taken on disk. The biggest checkpoints are named by their voyage, the outside models by
  their Hugging Face name.
- **store**: Postgres: where, whether it answers, its size and biggest tables, and which of the ledger,
  the library and the queue it holds.
- **server**: the version, the commit, the Python and frameworks, the machine, when it started and when
  the dashboard was last built.
- **environment**: every THORP_* switch that is set, and whether each key is present (never its value).
- **lanes**: how many seats each lane runs.
- **vast**: Vast.ai by GPU class: the terms' ceilings, the market's price reads (count, range, the latest
  price and reliability) and the voyages hired (the spend log: count, hours, spend, the last measured rate).
- **charters**: the Vast lane's recent hires, task by task (provision, ssh, code, data, board, env, train,
  home), parsed from `data/runs/charter.log` and joined to the spend log by instance; the live hire's open
  task is timed to now, so the page says where an hour of hire is going while it goes.

Each part is read on its own and says why when it cannot be, so a store that is down still shows the disk.
The sizes are cached for a minute: `du` over the texts is the only slow read here.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from thorp import paths

STARTED = time.time()  # the module is imported with the server, so this is the server's start

_CACHE: dict = {"at": 0.0, "value": None}
_LOCK = threading.Lock()
TTL = 60.0

# the parts of data/ worth a row of their own; the rest is summed as "everything else in data/"
DATA_PARTS = (
    (
        "checkpoints",
        "Checkpoints",
        "every voyage's saved weights, a folder a voyage and a file a saved step",
    ),
    (
        "postgres",
        "The store's files",
        "Postgres's own data directory: the ledger, the library, the queue and the VSM's records",
    ),
    ("texts", "Texts", "the books as fetched, a file a book"),
    ("shards", "Shards", "the books tokenised and packed for training"),
    ("catalogue", "Catalogue", "the sources' catalogues, what could be fetched"),
    ("classics", "Classics", "the classics shelf's texts"),
    (
        "manifest.sqlite",
        "Manifest",
        "the library's register in SQLite, from before the store held it",
    ),
    ("runs", "Voyage logs", "each voyage's log as it sailed"),
)

# name, what it is for; a key's value is never read out, only whether it is set
KEYS = (
    ("FAL_KEY", "fal.ai, which paints the cards' art (thorp/dash/art)"),
    (
        "VAST_API_KEY",
        "Vast.ai, to hire a box for the Vast lane (else the store, else data/secrets/vast-api-key)",
    ),
    ("HF_TOKEN", "Hugging Face, for outside models that need an account to fetch"),
)

# what each switch does, for the ones worth explaining; any other THORP_* that is set is listed bare
SWITCHES = {
    "THORP_DATA": "where the runtime data lives (default: data/ at the repository root)",
    "THORP_LEDGER": "the SQLite ledger's file (default: ledger.sqlite at the repository root)",
    "THORP_SHIPS": "where the specs, lists and fitouts live (default: ships/)",
    "THORP_PG": "the store's address; overrides the install file (default: postgresql://thorp@localhost:5433/thorp)",
    "THORP_LEDGER_PG": "the ledger is Postgres unless 0 (the default at home; a hired box keeps its SQLite log)",
    "THORP_LIBRARY_PG": "the library's register is Postgres unless 0 (the default at home; a box reads its carried file)",
    "THORP_QUEUE_PG": "1: the standing queue is the store's, not specs/queue.txt",
    "THORP_LEDGER_DUAL": "set: a new voyage writes both ledgers",
    "THORP_BACKEND": "the framework a voyage trains in (mlx or torch), over the spec's own",
    "THORP_DEVICE": "the torch device (cuda, cuda:1, mps, cpu)",
    "THORP_MAC_SLOTS": "how many voyages the Mac lane runs at once, over the store's seats",
    "THORP_HELM_SLOTS": "how many helm seats this process may take",
    "THORP_SHIP_LOG": "1: a hired box, keeping its own SQLite log to fold in at docking",
    "THORP_PAPERS": "a hired box's papers: the policies and stores frozen when it sailed",
    "THORP_TORCH_COMPILE": "1: compile the torch forward pass",
    "THORP_CONTACT": "the contact sent to the sources when fetching books",
}


def _du(targets: list[Path]) -> dict[str, int | None]:
    """The space each path takes on disk, in bytes (`du -sk`: blocks, so a sparse or cloned file counts as
    what it costs). None for a path that is missing or could not be read in time."""
    out: dict[str, int | None] = {str(p): None for p in targets}
    there = [str(p) for p in targets if p.exists()]
    if not there:
        return out
    try:
        r = subprocess.run(["du", "-sk", *there], capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return out
    for line in r.stdout.splitlines():
        kb, _, path = line.partition("\t")
        if path in out and kb.strip().isdigit():
            out[path] = int(kb) * 1024
    return out


def hf_cache() -> Path:
    """Where Hugging Face keeps the outside models, by its own rules (HF_HUB_CACHE, then HF_HOME)."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    home = os.environ.get("HF_HOME")
    return (Path(home) if home else Path.home() / ".cache" / "huggingface") / "hub"


def _home(p: Path) -> str:
    """A path as it is read: under the repository when it is, else with ~ for the home folder."""
    s = str(p)
    for base, mark in ((str(paths.ROOT), ""), (str(Path.home()), "~")):
        if s == base or s.startswith(base + os.sep):
            rest = s[len(base) :].lstrip(os.sep)
            return (mark + "/" + rest if mark else rest) or "."
    return s


def _run_names() -> dict[str, dict]:
    """Each voyage's name and ship by its run id, for the checkpoints' folders; empty if the ledger is out."""
    try:
        from thorp.dash import server

        return {r["run_id"]: {"name": r.get("name"), "ship": r.get("ship"), "status": r.get("status")}
                for r in server._runs_rows()}  # fmt: skip
    except Exception:  # noqa: BLE001  (the sizes still stand without the names)
        return {}


def _children(folder: Path, top: int) -> tuple[list[tuple[Path, int]], int]:
    """A folder's children by the space they take, biggest first: the top few and how many there are."""
    if not folder.is_dir():
        return [], 0
    kids = [p for p in folder.iterdir() if not p.name.startswith(".")]
    sizes = _du(kids)
    ranked = sorted(((p, sizes.get(str(p)) or 0) for p in kids), key=lambda x: -x[1])
    return ranked[:top], len(kids)


def storage() -> dict:
    data, ships, ledger, hub = paths.data_dir(), paths.ships_dir(), paths.ledger_path(), hf_cache()
    named = [(data / key, name, about) for key, name, about in DATA_PARTS]
    rows = [
        *named,
        (
            hub,
            "Outside models",
            "the Hugging Face cache: the outside models read on our decks, downloaded once",
        ),
        (
            ledger,
            "SQLite ledger",
            "the old ledger's file, kept from before the store held the voyages",
        ),
        (ships, "Ships", "the specs, lists, plans and fitouts: the part of this that is in git"),
    ]
    sizes = _du([data, *(p for p, _, _ in rows)])
    parts = [
        {"key": p.name, "name": name, "about": about, "path": _home(p), "bytes": sizes[str(p)]}
        for p, name, about in rows
    ]
    data_total = sizes[str(data)]
    if data_total is not None:
        rest = data_total - sum(sizes[str(p)] or 0 for p, _, _ in named)
        parts.append({"key": "data-rest", "name": "Everything else in data/", "about": "the caches, decks, tokenisers and the smaller folders",
                      "path": _home(data), "bytes": max(0, rest)})  # fmt: skip
    parts.sort(key=lambda r: -(r["bytes"] or 0))

    disk = None
    try:
        u = shutil.disk_usage(data if data.exists() else paths.ROOT)
        disk = {"total": u.total, "used": u.total - u.free, "free": u.free, "at": _home(data)}
    except OSError:
        pass

    names = _run_names()
    top, n = _children(data / "checkpoints", 12)
    checkpoints = {
        "count": n,
        "top": [
            {
                "run_id": p.name,
                "bytes": b,
                **(names.get(p.name) or {}),
                "steps": sum(1 for s in p.iterdir() if s.name.startswith("step-"))
                if p.is_dir()
                else 0,
            }
            for p, b in top
        ],  # fmt: skip
    }
    top, n = _children(hub, 40)
    models = {
        "count": sum(1 for p in hub.iterdir() if p.name.startswith("models--"))
        if hub.is_dir()
        else 0,
        "top": [
            {"model": p.name[len("models--") :].replace("--", "/"), "bytes": b}
            for p, b in top
            if p.name.startswith("models--")
        ],
    }
    return {
        "disk": disk,
        "ours": sum(r["bytes"] or 0 for r in parts),
        "parts": parts,
        "checkpoints": checkpoints,
        "models": models,
        "measured": time.time(),
    }


def store_info() -> dict:
    from thorp import config, store

    out: dict = {
        "url": store._safe(store.url()),
        "ok": False,
        "mode": config.mode(),
        "locked": config.locked(),
        "config_path": str(config.path()),
    }
    try:
        from thorp import manifest
        from thorp.ledger import _use_pg
        from thorp.viable.s2_coordination import queue_store

        out["holds"] = {
            "ledger": bool(_use_pg()),
            "library": bool(manifest._pg()),
            "queue": bool(queue_store.enabled()),
        }
    except Exception:  # noqa: BLE001
        out["holds"] = None
    try:
        from sqlalchemy import text

        with store.session() as s:
            out["version"] = str(s.execute(text("show server_version")).scalar() or "")
            out["bytes"] = int(
                s.execute(text("select pg_database_size(current_database())")).scalar() or 0
            )
            out["tables"] = [
                {"name": f"{r[0]}.{r[1]}", "bytes": int(r[2] or 0), "rows": int(r[3] or 0)}
                for r in s.execute(text(
                    "select schemaname, relname, pg_total_relation_size(relid), n_live_tup "
                    "from pg_stat_user_tables order by 3 desc limit 10"
                ))
            ]  # fmt: skip
            out["table_count"] = int(
                s.execute(text("select count(*) from pg_stat_user_tables")).scalar() or 0
            )
        out["ok"] = True
    except Exception as e:  # noqa: BLE001  (down, or a server too old for a column: say so, keep the page)
        out["error"] = str(e).splitlines()[0][:300]
    return out


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(paths.ROOT), *args], capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _version(pkg: str) -> str | None:
    from importlib import metadata

    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def _sysctl(name: str) -> str:
    try:
        r = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def server_info() -> dict:
    memory = None
    try:
        memory = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        pass
    built = None
    index = Path(__file__).resolve().parent / "static" / "index.html"
    if index.exists():
        built = index.stat().st_mtime
    status = _git("status", "--porcelain")
    return {
        "version": _version("thorp"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git("rev-parse", "--short", "HEAD"),
        "commit_subject": _git("log", "-1", "--format=%s"),
        "commit_at": _git("log", "-1", "--format=%cI"),
        "uncommitted": len([x for x in status.splitlines() if x.strip()]),
        "python": platform.python_version(),
        "frameworks": {k: _version(k) for k in ("mlx", "torch", "sqlalchemy")},
        "platform": platform.platform(terse=True),
        "chip": _sysctl("machdep.cpu.brand_string") or platform.processor() or platform.machine(),
        "cores": os.cpu_count(),
        "gpu_cores": _gpu_cores(),
        "memory": memory,
        "pid": os.getpid(),
        "started": STARTED,
        "uptime": time.time() - STARTED,
        "built": built,
        "executable": _home(Path(sys.executable)),
    }


def _gpu_cores() -> int | None:
    """The machine's GPU cores (the Mac's integrated GPU); None where there is no reading."""
    try:
        from thorp.dash import perf

        return perf.gpu_cores()
    except Exception:  # noqa: BLE001  (a machine without the accelerator's entry)
        return None


def paths_info() -> list[dict]:
    rows = [
        ("Repository", paths.ROOT, "the backend, the frontend and the ships"),
        ("Data", paths.data_dir(), "the runtime state, out of git (THORP_DATA)"),
        ("Ships", paths.ships_dir(), "the specs, lists, plans and fitouts (THORP_SHIPS)"),
        ("SQLite ledger", paths.ledger_path(), "the old ledger's file (THORP_LEDGER)"),
        ("Checkpoints", paths.checkpoints_dir(), "every voyage's saved weights"),
        ("Outside models", hf_cache(), "the Hugging Face cache (HF_HUB_CACHE, HF_HOME)"),
    ]
    return [{"name": n, "path": str(p), "about": a, "exists": p.exists()} for n, p, a in rows]


def environment() -> dict:
    from thorp import store

    switches = []
    for k in sorted(set(SWITCHES) | {k for k in os.environ if k.startswith("THORP_")}):
        v = os.environ.get(k)
        if v is not None and k == "THORP_PG":
            v = store._safe(v)
        switches.append({"name": k, "value": v, "about": SWITCHES.get(k, "")})
    keys = [{"name": k, "set": bool(os.environ.get(k)), "about": a} for k, a in KEYS]
    return {"switches": switches, "keys": keys}


def lanes() -> dict:
    try:
        from thorp import store
        from thorp.viable.records import Lane

        with store.session() as s:
            return {
                "lanes": [
                    {"lane": r.lane, "seats": r.seats or 1, "out": r.line} for r in s.query(Lane)
                ]
            }
    except Exception as e:  # noqa: BLE001
        return {"lanes": [], "error": str(e).splitlines()[0][:300]}


def _chip_row(gpu: str, ceiling: float | None = None) -> dict:
    """One GPU class's line in the Vast table, before anything is known of it."""
    return {
        "gpu": gpu,
        "ceiling": ceiling,
        "reads": 0,
        "last_read": None,
        "price": None,
        "reliability": None,
        "min": None,
        "median": None,
        "max": None,
        "hires": 0,
        "out": 0,
        "hours": 0.0,
        "spent": 0.0,
        "rate": None,
        "rate_preset": None,
        "rate_at": None,
        "guess": None,
    }


def chip_stats(reads: list[dict], events: list[dict], terms: dict) -> list[dict]:
    """The Vast table, one row a GPU chip class: what the market asked for it (the cheapest offer each
    charter quote read: its count, its range and its latest price and host reliability) and what was hired
    on it (the spend log's voyages, their hours, the money and the last measured rate). The classes the
    terms allow come first, even when nothing has been read or hired; a class the log knows and the terms
    do not follows, so an old reading is not hidden.

    Pure over its three inputs (the terms, s4.market_reads' lines and s3.spend_events' lines), so the
    arithmetic can be tested without a store."""
    import statistics

    from thorp.viable.s5_policy.charter import EFFECTIVE_TFLOPS

    ceilings: dict[str, float] = dict(terms.get("gpus") or {})
    prices: dict[str, list[float]] = {}
    latest: dict[str, dict] = {}
    for r in reads:
        gpu = r.get("gpu")
        if not gpu or r.get("dph") is None:
            continue
        prices.setdefault(gpu, []).append(float(r["dph"]))
        if gpu not in latest or str(r.get("at") or "") > str(latest[gpu].get("at") or ""):
            latest[gpu] = r

    rows = {gpu: _chip_row(gpu, float(c)) for gpu, c in ceilings.items()}
    for gpu in prices:
        rows.setdefault(gpu, _chip_row(gpu))
    released = {e.get("instance") for e in events if e.get("event") == "released"}
    for e in events:
        gpu = e.get("gpu")
        if not gpu:
            continue  # a release that never reached the box (refused ssh, a stalled copy): no class, no money
        row = rows.setdefault(gpu, _chip_row(gpu))
        if e.get("event") == "hired":
            row["hires"] += 1
            if e.get("instance") not in released:
                row["out"] += 1
        elif e.get("event") == "released":
            if e.get("cost") is not None:
                row["spent"] += float(e["cost"])
            if e.get("started") and e.get("ended"):
                row["hours"] += (float(e["ended"]) - float(e["started"])) / 3600
            if e.get("tokens_per_s") and (
                row["rate_at"] is None or str(e.get("at")) > row["rate_at"]
            ):
                row["rate"] = float(e["tokens_per_s"])
                row["rate_preset"] = e.get("preset")
                row["rate_at"] = e.get("at")

    for gpu, row in rows.items():
        row["guess"] = EFFECTIVE_TFLOPS.get(gpu)
        seen = prices.get(gpu) or []
        row["reads"] = len(seen)
        if seen:
            last = latest[gpu]
            row["last_read"] = last.get("at")
            row["price"] = round(float(last["dph"]), 4)
            row["reliability"] = last.get("reliability")
            row["min"] = round(min(seen), 4)
            row["median"] = round(statistics.median(seen), 4)
            row["max"] = round(max(seen), 4)
        row["hours"] = round(row["hours"], 2)
        row["spent"] = round(row["spent"], 2)
        if row["rate"] is not None:
            row["rate"] = round(row["rate"])

    allowed = [rows[g] for g in ceilings if g in rows]
    others = [rows[g] for g in sorted(rows) if g not in ceilings]
    return allowed + others


def vast() -> dict:
    """The Vast.ai lane, by GPU class: the terms that bound it (s5.charter), the market's price reads
    (s4.market_reads) and the voyages hired (s3.spend_events, the spend log).

    Read from the store only, never the API: the settings page must answer while Vast is unreachable, and
    it asks the store on every visit, so the figures are as fresh as the last charter quote or hire. The
    key is only ever said to be present."""
    from datetime import UTC, datetime

    from thorp import providers
    from thorp.viable.s3_control import charter as s3
    from thorp.viable.s4_intelligence import market
    from thorp.viable.s5_policy import charter as s5

    terms = s5.terms()
    chips = chip_stats(market.reads(limit=2000), s3.log(), terms)
    return {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "key": bool(providers.vast_key()),
        "seats": providers.vast_seats(),
        "week": {"spent": round(s3.week_spent(), 2), "budget": float(terms["weekly_budget"])},
        "voyage_budget": float(terms["voyage_budget"]),
        "out": sum(c["out"] for c in chips),
        "chips": chips,
        "totals": {
            "reads": sum(c["reads"] for c in chips),
            "hires": sum(c["hires"] for c in chips),
            "hours": round(sum(c["hours"] for c in chips), 1),
            "spent": round(sum(c["spent"] for c in chips), 2),
        },
    }


# ---- the Vast lane, task by task (12 November)

_CHARTER_STAMP = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]\s?(.*)$")
_CHARTER_OFFER = re.compile(r"charter: (.+?) offer \d+ at \$([\d.]+)/h, about ([\d.]+) h, \$([\d.]+)")
_CHARTER_UP = re.compile(r"charter: instance (\d+) is up")
_CHARTER_SEA = re.compile(r"charter: (.+?) is at sea on instance (\d+)")
_CHARTER_SECONDS = re.compile(r"\((\d+(?:\.\d+)?)s\)\s*$")

def _charter_find(block: list[tuple[int, str]], pred, after: int = 0):
    """The first line at or after `after` whose message `pred` accepts."""
    for i in range(after, len(block)):
        if pred(block[i][1]):
            return i
    return None


def _charter_span(block: list[tuple[int, str]], rel: list[int], a: int | None, b: int | None) -> float | None:
    """Seconds between two lines: the duration the charter printed when it printed one."""
    if a is None or b is None or b <= a:
        return None
    m = _CHARTER_SECONDS.search(block[b][1])
    return float(m.group(1)) if m else float(rel[b] - rel[a])


def charters(limit: int = 8) -> dict:
    """The Vast lane's hires, task by task: how long the box took to come up, to answer ssh, to take the
    code, the data, the manifest and the papers, to sync its environment, to train, and to come home.

    Parsed from `data/runs/charter.log` (the charter writes each step's start and its duration there,
    flushed as it runs), joined to the spend log by instance number for the hire's date, cost, name and
    why it ended. The last block is live: its open phase is timed to now. A hire that ended before its
    run (a refused ssh, a stalled copy) is kept as `aborted`, with the release's own words in `note`:
    that wasted hour is exactly what this page is for.
    """
    from datetime import datetime

    from thorp.viable.s3_control import charter as s3

    now = time.time()
    stamp = lambda: datetime.now().astimezone().isoformat(timespec="seconds")  # noqa: E731
    try:
        lines = (paths.data_dir() / "runs" / "charter.log").read_text(errors="ignore").splitlines()
    except OSError:
        return {"at": stamp(), "charters": []}

    events = s3.log()
    hires = {e["instance"]: e for e in events if e.get("event") == "hired" and e.get("instance") is not None}
    releases = {e["instance"]: e for e in events if e.get("event") == "released" and e.get("instance") is not None}

    # one block a hire: it begins at that hire's quote (the offer line) and runs to the next quote
    blocks: list[list[tuple[int, str]]] = []
    for raw in lines:
        m = _CHARTER_STAMP.match(raw)
        if not m:
            continue
        t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        msg = m.group(4)
        if _CHARTER_OFFER.search(msg):
            blocks.append([])
        if blocks:
            blocks[-1].append((t, msg))

    out: list[dict] = []
    for n, block in enumerate(blocks):
        offer = _CHARTER_OFFER.search(block[0][1])
        if not offer:
            continue
        # seconds since the quote, a day added when the clock wraps past midnight
        base = block[0][0]
        rel: list[int] = []
        day = 0
        for t, _ in block:
            if rel and t + day < rel[-1] + base:
                day += 86400
            rel.append(t + day - base)
        # where the block ends: the next hire's quote, or now while it is the last one
        end_rel = rel[-1]
        if n + 1 < len(blocks) and blocks[n + 1]:
            nxt = blocks[n + 1][0][0]
            end_rel = max(end_rel, nxt + (86400 if nxt < base else 0) - base)
        live = n == len(blocks) - 1

        instance = None
        for _, msg in block:
            m = _CHARTER_UP.search(msg)
            if m:
                instance = int(m.group(1))
                break
        hire = hires.get(instance) if instance is not None else None
        if hire is None:
            continue  # a hire that never reached an instance: nothing to time
        release = releases.get(instance)

        up_i = _charter_find(block, lambda m: _CHARTER_UP.search(m))
        ssh_i = _charter_find(block, lambda m: "charter: ssh answered" in m)
        sea_i = _charter_find(block, lambda m: _CHARTER_SEA.search(m))
        code_i = _charter_find(block, lambda m: "[box] tar" in m and "files to /" in m)
        code_done_i = _charter_find(block, lambda m: "tar done" in m, (code_i or 0) + 1) if code_i is not None else None
        data_i = _charter_find(block, lambda m: "[box]" in m and "files to data" in m)
        data_done_i = (
            _charter_find(block, lambda m: "tar done" in m or "rsync done" in m, (data_i or 0) + 1) if data_i is not None else None
        )
        env_i = _charter_find(block, lambda m: "syncing the box's environment" in m)
        env_done_i = _charter_find(block, lambda m: "[box] ssh done" in m, (env_i or 0) + 1) if env_i is not None else None
        home_i = _charter_find(block, lambda m: "bringing it home" in m)
        release_i = _charter_find(block, lambda m: "released;" in m)

        phases: dict[str, float | None] = {
            "provision": _charter_span(block, rel, 0, up_i),
            "ssh": _charter_span(block, rel, up_i, ssh_i),
            "code": _charter_span(block, rel, code_i, code_done_i),
            "data": _charter_span(block, rel, data_i, data_done_i),
            "board": None,
            "env": _charter_span(block, rel, env_i, env_done_i),
            "train": _charter_span(block, rel, sea_i, home_i or release_i),
            "home": _charter_span(block, rel, home_i, release_i),
        }
        # the board: the manifest, the spec and the papers, from the data's end to the environment's start
        if data_done_i is not None:
            stop = env_i if env_i is not None else sea_i
            if stop is not None and stop > data_done_i:
                phases["board"] = float(rel[stop] - rel[data_done_i])

        # the phase still running, timed to now for the live hire and to the next quote for an aborted one
        open_key, start_i = None, None
        if data_i is not None and data_done_i is None:
            open_key, start_i = "data", data_i
        elif up_i is not None and ssh_i is None:
            open_key, start_i = "ssh", up_i
        elif data_done_i is not None and env_i is None and sea_i is None:
            open_key, start_i = "board", data_done_i
        elif env_i is not None and env_done_i is None:
            open_key, start_i = "env", env_i
        elif sea_i is not None and home_i is None and release_i is None:
            open_key, start_i = "train", sea_i
        elif home_i is not None and release_i is None:
            open_key, start_i = "home", home_i

        started = float(hire.get("started") or (now - rel[-1]))
        if open_key is not None and start_i is not None:
            end = (now - started) if (live and release is None) else end_rel
            phases[open_key] = max(0.0, end - rel[start_i])

        if release:
            raw = str(release.get("status") or "").strip()
            if raw == "overran":
                status = "overran"
            elif release.get("why"):  # a hire that ended before its run: refused ssh, a stalled copy
                status = "aborted"
            elif raw.lower() in ("home", "finished", "released", ""):
                status = "released"
            else:  # lost, recalled, came in unfinished, gone: the run did not come home
                status = "aborted"
        elif sea_i is not None:
            status = "at sea"
        elif live:
            status = "fitting out"
        else:
            status = "aborted"

        # a released hire's own end; a failed one has only the release event's time, which is still the end
        ended = None
        if release:
            if release.get("ended"):
                ended = float(release["ended"])
            elif release.get("at"):
                ended = datetime.fromisoformat(str(release["at"])).timestamp()
        total_s = (ended - started) if ended else (now - started)
        dph = float(hire.get("dph") or offer.group(2))
        sea_name = _CHARTER_SEA.search(block[sea_i][1]).group(1) if sea_i is not None else None
        note = (release.get("why") or release.get("status")) if release and status == "aborted" else None
        out.append({
            "name": hire.get("name") or sea_name or f"instance {instance}",
            "instance": instance,
            "gpu": hire.get("gpu") or offer.group(1),
            "dph": round(dph, 4),
            "quote_hours": round(float(hire.get("quote_hours") or offer.group(3)), 3),
            "quote_cost": round(float(offer.group(4)), 2),
            "started": datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds"),
            "status": status,
            "total_s": round(total_s),
            "cost": round(float(release["cost"]) if release and release.get("cost") is not None else total_s / 3600 * dph, 2),
            "rate": round(float(release["tokens_per_s"])) if release and release.get("tokens_per_s") else None,
            "phases": {k: (round(v) if v is not None else None) for k, v in phases.items()},
            # only a hire still out has a task running now: an aborted one's last task is where it died
            "open": open_key if release is None else None,
            "note": note,
        })

    out.reverse()
    return {"at": stamp(), "charters": out[:limit]}


def _part(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001  (one part failing must not blank the page)
        return {"error": repr(e)[:300]}


def payload(fresh: bool = False) -> dict:
    """Everything the settings page shows. The sizes are measured at most once a minute (`fresh` measures
    now); the rest is read on every call, as it is cheap and the store's state should be the present one."""
    with _LOCK:
        if fresh or _CACHE["value"] is None or time.time() - _CACHE["at"] > TTL:
            _CACHE.update(value=_part(storage), at=time.time())
        sizes = _CACHE["value"]
    return {
        "storage": sizes,
        "store": _part(store_info),
        "server": _part(server_info),
        "paths": _part(paths_info),
        "environment": _part(environment),
        "lanes": _part(lanes),
        "vast": _part(vast),
        "charters": _part(charters),
    }
