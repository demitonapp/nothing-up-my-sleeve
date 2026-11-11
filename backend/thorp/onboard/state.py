"""The first-run wizard's own state: `data/onboarding.json`.

This file is disposable. It exists so a refresh, a closed browser or a restarted terminal does not
lose the four answers; the durable choices go to `data/config.json` (the store) and the store itself
(the sailing choice, once there is one). A completed file is kept as a record and can be archived
with `thorp onboard --reset`.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path

from thorp import paths

VERSION = 1
STEPS = ("welcome", "sail", "models", "store", "install", "done")

_LOCK = threading.RLock()


def path() -> Path:
    return paths.data_dir() / "onboarding.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _blank() -> dict:
    return {
        "version": VERSION,
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "step": "welcome",
        "sailing": {"enabled": None, "classes": []},
        "models": {"bands": [], "selected": []},
        "store": {"mode": "local", "url": ""},
        "checks": {},
    }


def _clean(raw: object) -> dict:
    out = _blank()
    if not isinstance(raw, dict):
        return out
    out["version"] = int(raw.get("version") or VERSION)
    out["created_at"] = str(raw.get("created_at") or out["created_at"])
    out["updated_at"] = str(raw.get("updated_at") or out["updated_at"])
    out["completed_at"] = raw.get("completed_at")
    step = str(raw.get("step") or "welcome")
    out["step"] = step if step in STEPS else "welcome"
    sail = raw.get("sailing")
    if isinstance(sail, dict):
        out["sailing"] = {
            "enabled": sail.get("enabled") if isinstance(sail.get("enabled"), bool) else None,
            "classes": [str(x) for x in (sail.get("classes") or []) if str(x)],
        }
    models = raw.get("models")
    if isinstance(models, dict):
        out["models"] = {
            "bands": [str(x) for x in (models.get("bands") or []) if str(x)],
            "selected": [str(x) for x in (models.get("selected") or []) if str(x)],
        }
    store = raw.get("store")
    if isinstance(store, dict):
        out["store"] = {
            "mode": str(store.get("mode") or "local"),
            "url": str(store.get("url") or ""),
        }
    if isinstance(raw.get("checks"), dict):
        out["checks"] = raw["checks"]
    return out


def read() -> dict:
    with _LOCK:
        try:
            return _clean(json.loads(path().read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return _blank()


def write(data: dict) -> dict:
    clean = _clean(data)
    clean["updated_at"] = _now()
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


def update(**fields) -> dict:
    data = read()
    data.update(fields)
    return write(data)


def step(name: str) -> dict:
    if name not in STEPS:
        raise ValueError(f"unknown onboarding step {name!r}")
    data = read()
    data["step"] = name
    return write(data)


def set_sailing(enabled: bool, classes: list[str]) -> dict:
    data = read()
    data["sailing"] = {
        "enabled": bool(enabled),
        "classes": [] if not enabled else list(dict.fromkeys(classes)),
    }
    return write(data)


def set_models(bands: list[str], selected: list[str]) -> dict:
    data = read()
    data["models"] = {
        "bands": list(dict.fromkeys(bands)),
        "selected": list(dict.fromkeys(selected)),
    }
    return write(data)


def set_store(mode: str, url: str = "") -> dict:
    data = read()
    data["store"] = {"mode": mode, "url": url}
    return write(data)


def complete() -> dict:
    data = read()
    data["completed_at"] = _now()
    data["step"] = "done"
    return write(data)


def reset(archive: bool = True) -> dict:
    """Start over. The old file is moved aside, not destroyed, so a support question can read it."""
    with _LOCK:
        p = path()
        if archive and p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            dest = p.with_name(f"onboarding-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
            shutil.move(str(p), dest)
        elif p.exists():
            p.unlink()
    return write(_blank())


def summary() -> dict:
    data = read()
    return {
        "step": data["step"],
        "completed": bool(data["completed_at"]),
        "completed_at": data["completed_at"],
        "sailing": data["sailing"],
        "models": data["models"],
        "store": data["store"],
    }
