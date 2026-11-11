"""The install's own settings, kept in `data/config.json` (outside git).

The first-run page writes one thing here that the rest of the harness has to agree on: **where the
store lives**. `THORP_PG` still wins, so a developer can point any command at another database
without touching the file. A local install leaves the URL empty and falls back to the store's own
default (`postgresql://thorp@localhost:5433/thorp`).

The file is written atomically and mode 0600. A local store uses trust auth and has no password; a
hosted store will name a Keychain item (`secret_ref`) when the hosted build adds the lookup. A URL
entered before then can carry a password, so the file stays 0600 and every display redacts it.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from thorp import paths

VERSION = 1
DEFAULT_LOCAL_URL = "postgresql://thorp@localhost:5433/thorp"
MODES = ("local", "hosted")

_LOCK = threading.RLock()


def path() -> Path:
    return paths.data_dir() / "config.json"


def _blank() -> dict:
    return {
        "version": VERSION,
        "store": {"mode": "local", "url": "", "secret_ref": "", "updated_at": None},
    }


def _clean(raw: object) -> dict:
    out = _blank()
    if not isinstance(raw, dict):
        return out
    out["version"] = int(raw.get("version") or VERSION)
    store = raw.get("store")
    if isinstance(store, dict):
        mode = str(store.get("mode") or "local")
        out["store"] = {
            "mode": mode if mode in MODES else "local",
            "url": str(store.get("url") or ""),
            "secret_ref": str(store.get("secret_ref") or ""),
            "updated_at": store.get("updated_at"),
        }
    return out


def read() -> dict:
    """The file as it stands, or the defaults. A broken file is not fatal: the defaults are local."""
    with _LOCK:
        try:
            raw = json.loads(path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return _blank()
        return _clean(raw)


def write(data: dict) -> dict:
    """Replace the file atomically. Returns what was written."""
    clean = _clean(data)
    with _LOCK:
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(clean, indent=1) + "\n", encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, p)
    return clean


def store() -> dict:
    return read()["store"]


def mode() -> str:
    return store()["mode"]


def locked() -> bool:
    """Whether THORP_PG is set in the environment, in which case this file cannot choose the store."""
    return bool(os.environ.get("THORP_PG", "").strip())


def store_url() -> str:
    """The URL this install chose, or "" for the store's default. THORP_PG is not read here: callers
    that need the effective URL use `fitout_store.url()`, which asks the environment first."""
    return str(store().get("url") or "").strip()


def set_store(mode: str, url: str = "", secret_ref: str = "") -> dict:
    if mode not in MODES:
        raise ValueError(f"unknown store mode {mode!r}; known: {', '.join(MODES)}")
    with _LOCK:
        data = read()
        data["store"] = {
            "mode": mode,
            "url": url.strip(),
            "secret_ref": secret_ref.strip(),
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        return write(data)


def describe() -> dict:
    """What the dashboard may show: the mode, the URL with any password removed, and whether the
    environment has taken the choice away from the file."""
    from thorp import store as store_module

    s = store()
    effective = os.environ.get("THORP_PG", "").strip() or s["url"] or DEFAULT_LOCAL_URL
    return {
        "mode": s["mode"],
        "url": store_module._safe(effective),
        "configured": bool(s["url"] or os.environ.get("THORP_PG", "").strip()),
        "locked": locked(),
        "source": "environment" if locked() else ("file" if s["url"] else "default"),
        "path": str(path()),
    }
