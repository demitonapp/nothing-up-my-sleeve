"""Local Postgres for the first run, and the store switch behind it.

The Mac's store is its own cluster under `data/postgres`, on `localhost:5433` (the repo's usual
address; 5432 is left to whatever else the machine runs). The first run can create the cluster,
start it, make the `thorp` database and run the Alembic migrations, provided the Postgres binaries
are already installed. It never runs `brew install`: an install is a decision, not a side effect.

The switch is deliberately conservative. It tests the new store, refuses while a voyage is at sea
(the repo's cut-over rule), writes `data/config.json`, and forgets the cached SQLAlchemy engine.
Checkpoints, texts and model weights never move: Postgres holds records only.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from thorp import config, paths

DEFAULT_PORT = 5433
DEFAULT_DB = "thorp"
DEFAULT_USER = "thorp"
LOCK = threading.RLock()

# Homebrew, Postgres.app and a source install all keep the tools in different places; `shutil.which`
# finds a shell's PATH, and these cover the Macs where the dashboard is started from an app bundle.
_BIN_DIRS = (
    "/opt/homebrew/opt/postgresql@17/bin",
    "/opt/homebrew/opt/postgresql@16/bin",
    "/opt/homebrew/opt/postgresql@15/bin",
    "/opt/homebrew/bin",
    "/usr/local/opt/postgresql@17/bin",
    "/usr/local/opt/postgresql@16/bin",
    "/usr/local/bin",
    "/Applications/Postgres.app/Contents/Versions/latest/bin",
)
_TOOLS = ("initdb", "pg_ctl", "pg_isready", "createdb", "psql")


class SetupError(RuntimeError):
    """A set-up step failed; the message is for the page, not a traceback."""


def cluster() -> Path:
    return paths.data_dir() / "postgres"


def log_path() -> Path:
    return paths.data_dir() / "postgres.log"


def local_url(port: int = DEFAULT_PORT) -> str:
    return f"postgresql://{DEFAULT_USER}@localhost:{port}/{DEFAULT_DB}"


def _bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for d in _BIN_DIRS:
        p = Path(d) / name
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return None


def tools() -> dict[str, str | None]:
    return {name: _bin(name) for name in _TOOLS}


def missing_tools() -> list[str]:
    return [name for name, path in tools().items() if not path]


def _run(
    cmd: list[str], *, timeout: float = 120.0, env: dict | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "LC_ALL": "en_US.UTF-8", **(env or {})},
    )


def _tail(r: subprocess.CompletedProcess) -> str:
    out = (r.stdout or "").strip().splitlines() + (r.stderr or "").strip().splitlines()
    return " · ".join(x.strip() for x in out[-4:] if x.strip())[:800]


def _plain(url: str) -> str:
    """psycopg wants `postgresql://`, not SQLAlchemy's `postgresql+psycopg://`."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _port_of(url: str) -> int:
    try:
        return int(urlparse(_plain(url)).port or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def _is_local(url: str) -> bool:
    """Whether this is the cluster under data/postgres, as opposed to an env-provided store."""
    try:
        u = urlparse(_plain(url))
    except ValueError:
        return False
    return u.hostname in ("localhost", "127.0.0.1", "::1") and _port_of(url) == DEFAULT_PORT


def _probe(url: str, timeout: int = 2) -> dict:
    """Answer a few questions without raising: the page shows a store that is down, not an error page."""
    out: dict = {"ok": False, "url": _safe(url), "version": None, "database": None, "schema": None}
    try:
        import psycopg

        with psycopg.connect(_plain(url), connect_timeout=timeout) as c:
            row = c.execute("show server_version").fetchone()
            out["version"] = str(row[0]) if row else None
            row = c.execute("select current_database()").fetchone()
            out["database"] = str(row[0]) if row else None
            try:
                row = c.execute("select version_num from s3.alembic_version").fetchone()
                out["schema"] = str(row[0]) if row else None
            except Exception as e:  # noqa: BLE001  (a store without the schema is a valid answer)
                out["schema_error"] = str(e).splitlines()[0][:300]
            out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e).splitlines()[0][:500]
    return out


def _safe(url: str) -> str:
    if "@" in url and ":" in url.split("@")[0].split("//")[-1]:
        head, tail = url.split("@", 1)
        return head.rsplit(":", 1)[0] + ":***@" + tail
    return url


def _cluster_running() -> bool:
    pg_ctl = _bin("pg_ctl")
    c = cluster()
    if not pg_ctl or not (c / "PG_VERSION").is_file():
        return False
    try:
        return _run([pg_ctl, "-D", str(c), "status"], timeout=5).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _wait_until_up(url: str, seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _probe(url, timeout=1)["ok"]:
            return True
        time.sleep(0.4)
    return False


def _wait_server(port: int, seconds: float = 30.0) -> bool:
    """Wait for the Postgres server itself, before the `thorp` database exists."""
    pg_isready = _bin("pg_isready")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if pg_isready:
            try:
                if (
                    _run([pg_isready, "-h", "localhost", "-p", str(port)], timeout=3).returncode
                    == 0
                ):
                    return True
            except (OSError, subprocess.TimeoutExpired):
                pass
        else:
            with contextlib.suppress(OSError):
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return True
        time.sleep(0.4)
    return False


def status() -> dict:
    """Everything the store step and the Settings switch need to show, without changing anything."""
    bins = tools()
    c = cluster()
    url = os.environ.get("THORP_PG", "").strip() or config.store_url() or local_url()
    exists = (c / "PG_VERSION").is_file()
    running = _cluster_running()
    probe = _probe(url)
    local = _is_local(url)
    return {
        "mode": config.mode(),
        "url": _safe(url),
        "configured": bool(config.store_url() or config.locked()),
        "locked": config.locked(),
        "cluster": str(c),
        "exists": exists,
        "running": running,
        "binaries": bins,
        "missing": [name for name, path in bins.items() if not path],
        "reachable": probe["ok"],
        "version": probe.get("version"),
        "database": probe.get("database"),
        "schema": probe.get("schema"),
        "schema_error": probe.get("schema_error"),
        "error": probe.get("error"),
        "ready": bool(probe["ok"] and probe.get("schema") and (not local or (exists and running))),
        "local": local,
        "source": "environment"
        if config.locked()
        else ("file" if config.store_url() else "default"),
        "default_url": _safe(local_url()),
        "port": _port_of(url),
        "install_hint": "brew install postgresql@17",
    }


def test(url: str) -> dict:
    """Test a candidate store and report what it holds; never writes the config."""
    probe = _probe(url, timeout=4)
    return {**probe, "url": _safe(url), "has_schema": bool(probe.get("schema"))}


def _migrate(url: str) -> None:
    """Run Alembic against a URL without leaving THORP_PG changed for the rest of the process."""
    from thorp.viable.s3_control import fitout_store

    with LOCK:
        old = os.environ.get("THORP_PG")
        os.environ["THORP_PG"] = url
        try:
            fitout_store.reset_engine()
            fitout_store.migrate()
        finally:
            if old is None:
                os.environ.pop("THORP_PG", None)
            else:
                os.environ["THORP_PG"] = old
            fitout_store.reset_engine()
    with contextlib.suppress(Exception):
        from thorp import ship_store

        ship_store.reload()


def setup_local(port: int = DEFAULT_PORT) -> dict:
    """Create, start, create the database and migrate. The caller has already chosen local."""
    bins = tools()
    missing = [name for name, path in bins.items() if not path]
    if missing:
        raise SetupError(
            f"Postgres is not installed (missing: {', '.join(missing)}). Install it with "
            f"`{status()['install_hint']}`, then press Retry."
        )
    c = cluster()
    c.parent.mkdir(parents=True, exist_ok=True)
    if not (c / "PG_VERSION").is_file():
        initdb = Path(str(bins["initdb"]))
        r = _run(
            [
                str(initdb),
                "-D",
                str(c),
                "-U",
                DEFAULT_USER,
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=en_US.UTF-8",
            ],
            timeout=180,
        )
        if r.returncode != 0:
            # a Mac without the en_US locale still needs a cluster; C is enough for this database
            r = _run(
                [
                    str(initdb),
                    "-D",
                    str(c),
                    "-U",
                    DEFAULT_USER,
                    "--auth=trust",
                    "--encoding=UTF8",
                    "--locale=C",
                ],
                timeout=180,
            )
        if r.returncode != 0:
            raise SetupError(f"initdb failed: {_tail(r)}")
    if not _cluster_running():
        log = log_path()
        log.parent.mkdir(parents=True, exist_ok=True)
        r = _run(
            [
                str(bins["pg_ctl"]),
                "-D",
                str(c),
                "-l",
                str(log),
                "-o",
                f"-p {port} -k /tmp -c listen_addresses=localhost",
                "-w",
                "-t",
                "30",
                "start",
            ],
            timeout=60,
        )
        if r.returncode != 0:
            raise SetupError(
                f"could not start the local Postgres on port {port}: {_tail(r)}. The log is {log}."
            )
    if not _wait_server(port, 30):
        raise SetupError(f"Postgres started but port {port} does not answer; see {log_path()}")
    url = local_url(port)
    if not _wait_until_up(url, 2):
        r = _run(
            [
                str(bins["createdb"]),
                "-h",
                "localhost",
                "-p",
                str(port),
                "-U",
                DEFAULT_USER,
                DEFAULT_DB,
            ],
            timeout=30,
        )
        if r.returncode != 0 and "already exists" not in _tail(r).lower():
            raise SetupError(f"could not create the `{DEFAULT_DB}` database: {_tail(r)}")
        if not _wait_until_up(url, 15):
            raise SetupError(f"Postgres started but {_safe(url)} does not answer")
    _migrate(url)
    config.set_store("local", "" if port == DEFAULT_PORT else url)
    return status()


def setup_existing(url: str, mode: str = "hosted") -> dict:
    """Bring an existing Postgres to the schema, then make it this install's store."""
    probe = test(url)
    if not probe["ok"]:
        raise SetupError(
            f"the store at {_safe(url)} does not answer: {probe.get('error') or 'no answer'}"
        )
    if not probe.get("schema"):
        _migrate(url)
    config.set_store(mode, url)
    with contextlib.suppress(Exception):
        from thorp.viable.s3_control import fitout_store

        fitout_store.reset_engine()
    return status()


def at_sea() -> int:
    """How many voyages the current store says are running. A store that cannot answer counts zero:
    there is nothing here to cut over."""
    try:
        from sqlalchemy import text

        from thorp import store

        with store.session() as s:
            return int(
                s.execute(text("select count(*) from s1.runs where status = 'running'")).scalar()
                or 0
            )
    except Exception:  # noqa: BLE001
        return 0


def switch(mode: str, url: str = "") -> dict:
    """Change where records go. Refuses while a voyage is at sea; requires an existing schema."""
    if mode not in config.MODES:
        raise SetupError(f"unknown store mode {mode!r}")
    if config.locked():
        raise SetupError(
            "THORP_PG is set in this shell, so the environment owns the store address; "
            "unset it and restart thorp dash to choose the store here."
        )
    n = at_sea()
    if n:
        raise SetupError(
            f"{n} voyage{'s are' if n != 1 else ' is'} at sea. Dock them before switching the store: "
            "the records must not be split between two databases."
        )
    target = (url or local_url()) if mode == "local" else (url or "").strip()
    if not target:
        raise SetupError("a hosted store needs its URL")
    probe = test(target)
    if not probe["ok"]:
        raise SetupError(
            f"the store at {_safe(target)} does not answer: {probe.get('error') or 'no answer'}"
        )
    if not probe.get("schema"):
        raise SetupError(
            f"the store at {_safe(target)} answers but has no Thorp schema. Run the migrations there "
            "first (thorp store setup), then switch."
        )
    config.set_store(mode, "" if mode == "local" and target == local_url() else target)
    from thorp.viable.s3_control import fitout_store

    fitout_store.reset_engine()
    with contextlib.suppress(Exception):
        from thorp import ledger

        ledger.close_reader()
    return {
        "ok": True,
        "mode": mode,
        "url": _safe(target),
        "restart_required": True,
        "message": "The store is switched. Restart thorp dash (and the queue) so every process uses it.",
    }


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def command_hint() -> str:
    """The command the page shows when the binaries are missing."""
    return status()["install_hint"]


def describe_python() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"
