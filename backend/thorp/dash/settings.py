"""The settings page (/settings, the cog in the header; 11 November, Justin: "a settings cog in the top
right hand of the UI that allows me to see things, like storage used").

Read-only: what the dashboard runs on, in one payload (`payload`, served at /api/settings).

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

Each part is read on its own and says why when it cannot be, so a store that is down still shows the disk.
The sizes are cached for a minute: `du` over the texts is the only slow read here.
"""

from __future__ import annotations

import os
import platform
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
    "THORP_PG": "the store's address (default: postgresql://thorp@localhost:5433/thorp)",
    "THORP_LEDGER_PG": "1: the ledger is read from and written to Postgres",
    "THORP_LIBRARY_PG": "1: the library's register is read from Postgres",
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
    from thorp import store

    out: dict = {"url": store._safe(store.url()), "ok": False}
    try:
        from thorp.ledger import _use_pg
        from thorp.viable.s2_coordination import queue_store

        out["holds"] = {
            "ledger": bool(_use_pg()),
            "library": os.environ.get("THORP_LIBRARY_PG") == "1",
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
        "memory": memory,
        "pid": os.getpid(),
        "started": STARTED,
        "uptime": time.time() - STARTED,
        "built": built,
        "executable": _home(Path(sys.executable)),
    }


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
    }
