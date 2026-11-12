"""The first run's API: the state the page reads, the answers it sends, and the jobs it starts.

The page is served by the same `thorp dash` process as the dashboard, but under `/onboard`, and its
API is namespaced under `/api/onboard/`. It is bound to loopback and carries a one-time token in the
URL; a POST without the token is refused. The token is not a user account: it keeps another page in
the same browser (or a stray `curl` from a shell history) from starting a 40 GB download.

The API is deliberately thin. It validates against the catalogue, persists the answer, starts a
job, and reads the truth from the disk, the Hub cache and Postgres. The page never decides whether
something worked.
"""

from __future__ import annotations

import hmac
import importlib.util
import os
import platform
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path

from thorp import config, paths
from thorp.onboard import build, catalogue, downloads, jobs, state, store_setup

_TOKEN = secrets.token_urlsafe(24)
_STORE_CACHE: dict = {"at": 0.0, "value": None}
_LOCK = threading.RLock()

WEB = Path(__file__).with_name("web")


class OnboardError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def begin() -> str:
    """A new server start gets a new token; an open tab from the old process cannot keep using it."""
    global _TOKEN
    with _LOCK:
        _TOKEN = secrets.token_urlsafe(24)
    return _TOKEN


def token() -> str:
    return _TOKEN


def authorized(headers, query: dict | None = None) -> bool:
    supplied = ""
    if headers is not None:
        supplied = str(headers.get("X-Thorp-Onboard") or "")
    if not supplied and query:
        supplied = str(query.get("token") or "")
    return bool(supplied) and hmac.compare_digest(supplied, _TOKEN)


def page_path() -> Path:
    return WEB / "index.html"


def page_bytes() -> bytes:
    try:
        return page_path().read_bytes()
    except OSError:
        return (
            b"<!doctype html><meta charset=utf-8><title>Nothing up my sleeve first run</title>"
            b"<p>The onboarding page is missing from this install. Run "
            b"<code>thorp onboard</code> from a checkout with <code>thorp/onboard/web</code>.</p>"
        )


def asset(rel: str) -> tuple[bytes, str] | None:
    """A file beside the onboarding page, never one outside it."""
    base = WEB.resolve()
    try:
        f = (base / rel.lstrip("/")).resolve()
    except OSError:
        return None
    if not f.is_relative_to(base) or not f.is_file():
        return None
    ctype = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".woff2": "font/woff2",
    }.get(f.suffix, "application/octet-stream")
    return f.read_bytes(), ctype


def _sh(cmd: str) -> str | None:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def machine() -> dict:
    mem = None
    try:
        mem = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        pass
    base = paths.data_dir()
    while not base.exists() and base.parent != base:
        base = base.parent
    try:
        disk = shutil.disk_usage(base)
    except OSError:
        disk = None
    return {
        "chip": _sh("sysctl -n machdep.cpu.brand_string")
        or platform.processor()
        or platform.machine(),
        "platform": platform.platform(terse=True),
        "python": platform.python_version(),
        "memory_gb": round(mem / 1e9, 1) if mem else None,
        "free_gb": round(disk.free / 1e9, 1) if disk else None,
        "total_gb": round(disk.total / 1e9, 1) if disk else None,
        "data": str(paths.data_dir()),
        "repo": str(paths.ROOT),
    }


def chat_engine() -> dict:
    installed = importlib.util.find_spec("mlx_lm") is not None
    version = None
    try:
        from importlib import metadata

        version = metadata.version("mlx-lm")
    except Exception:  # noqa: BLE001
        pass
    return {
        "installed": installed,
        "version": version,
        "hint": "uv sync --project backend",
    }


def _store_status(fresh: bool = False) -> dict:
    with _LOCK:
        now = time.time()
        if not fresh and _STORE_CACHE["value"] is not None and now - _STORE_CACHE["at"] < 2.0:
            return dict(_STORE_CACHE["value"])
    val = store_setup.status()
    with _LOCK:
        _STORE_CACHE.update(at=time.time(), value=val)
    return val


def _clear_store_cache() -> None:
    with _LOCK:
        _STORE_CACHE.update(at=0.0, value=None)


def _classes() -> list[dict]:
    sizes = None
    try:
        from thorp import ship_store

        sizes = ship_store.sizes()
    except Exception:  # noqa: BLE001  (before the store exists, the bootstrap list stands)
        sizes = None
    rows = catalogue.class_rows(sizes)
    mem = machine().get("memory_gb")
    for r in rows:
        r["fit"] = catalogue.class_fit(r, mem)
        r["params_h"] = catalogue.human_params(r.get("params"))
    return rows


def catalogue_payload() -> dict:
    mem = machine().get("memory_gb") or 0
    models = []
    for m in catalogue.models():
        row = dict(m)
        row["key"] = catalogue.key_for(m["label"])
        row["params_h"] = catalogue.human_params(m["params"])
        row["download_h"] = catalogue.human_gb(m["download_gb"])
        row["run_h"] = catalogue.human_gb(m["run_gb"])
        row["fit"] = catalogue.fit(m, mem)
        row["cached"] = downloads._cached(m["repo"])
        models.append(row)
    return {
        "bands": [{**b, "count": catalogue.band_counts()[b["key"]]} for b in catalogue.BANDS],
        "classes": _classes(),
        "models": models,
        "machine": machine(),
    }


def _setup() -> dict:
    return {
        "store": _store_status(),
        "build": build.status(),
        "chat_engine": chat_engine(),
    }


def state_payload() -> dict:
    return {
        "state": state.read(),
        "config": config.describe(),
        "machine": machine(),
        "setup": _setup(),
        "downloads": downloads.status(),
        "jobs": {"store": jobs.get("store"), "build": jobs.get("build")},
    }


def _bands_of(selected: list[str]) -> list[str]:
    out = []
    for repo in selected:
        m = catalogue.get(repo)
        if m is not None and m["band"] not in out:
            out.append(m["band"])
    return out


def answer(body: dict) -> dict:
    step = str(body.get("step") or "")
    value = body.get("value")
    if step == "welcome":
        state.step("sail")
    elif step == "sail":
        if not isinstance(value, dict):
            raise OnboardError("sail needs an object")
        enabled = bool(value.get("enabled"))
        classes = [str(x) for x in (value.get("classes") or [])]
        known = {r["preset"] for r in _classes()}
        unknown = [c for c in classes if c not in known]
        if unknown:
            raise OnboardError(f"unknown class: {', '.join(unknown)}")
        state.set_sailing(enabled, classes)
        state.step("models")
    elif step == "models":
        if not isinstance(value, dict):
            raise OnboardError("models needs an object")
        bands = [str(x) for x in (value.get("bands") or [])]
        selected = [str(x) for x in (value.get("selected") or [])]
        unknown_bands = [b for b in bands if b not in catalogue.BAND_KEYS]
        if unknown_bands:
            raise OnboardError(f"unknown size band: {', '.join(unknown_bands)}")
        unknown = [r for r in selected if catalogue.get(r) is None]
        if unknown:
            raise OnboardError(f"not in the model catalogue: {', '.join(unknown)}")
        chosen_bands = _bands_of(selected)
        missing = [b for b in chosen_bands if b not in bands]
        if missing:
            raise OnboardError(
                f"the selected models are in {', '.join(missing)}, which was not chosen"
            )
        state.set_models(bands, selected)
        state.step("store")
    elif step == "store":
        if not isinstance(value, dict):
            raise OnboardError("store needs an object")
        mode = str(value.get("mode") or "local")
        url = str(value.get("url") or "").strip()
        if mode not in config.MODES:
            raise OnboardError(f"unknown store mode {mode!r}")
        if mode == "hosted" and not url:
            raise OnboardError("a hosted store needs its URL")
        if url and not url.startswith("postgresql://"):
            raise OnboardError("a Postgres URL starts with postgresql://")
        state.set_store(mode, url)
        state.step("install")
    elif step == "step":
        name = str(body.get("name") or "")
        state.step(name)
    else:
        raise OnboardError(f"unknown step {step!r}")
    return {"state": state.read(), "next": state.read()["step"]}


def start_downloads(body: dict) -> dict:
    repos = [str(x) for x in (body.get("repos") or [])]
    if not repos:
        raise OnboardError("choose at least one model")
    try:
        downloads.start(repos)
    except ValueError as e:
        raise OnboardError(str(e)) from e
    return {"downloads": downloads.status()}


def cancel_download(body: dict) -> dict:
    repo = str(body.get("repo") or "")
    try:
        downloads.cancel(repo)
    except KeyError as e:
        raise OnboardError(f"no download for {repo!r}", 404) from e
    return {"downloads": downloads.status()}


def start_store(body: dict) -> dict:
    mode = str(body.get("mode") or "local")
    url = str(body.get("url") or "").strip()
    if mode not in config.MODES:
        raise OnboardError(f"unknown store mode {mode!r}")
    if mode == "hosted" and not url:
        raise OnboardError("a hosted store needs its URL")

    def run() -> dict:
        if mode == "local" and not url:
            out = store_setup.setup_local()
        else:
            out = store_setup.setup_existing(url or store_setup.local_url(), mode=mode)
        _clear_store_cache()
        try:
            from thorp import ship_store

            ship_store.reload()
        except Exception:  # noqa: BLE001
            pass
        state.set_store(mode, "" if mode == "local" and not url else url)
        return out

    job = jobs.start("store", run)
    return {"job": job, "setup": _setup()}


def test_store(body: dict) -> dict:
    url = str(body.get("url") or "").strip()
    if not url.startswith("postgresql://"):
        raise OnboardError("a Postgres URL starts with postgresql://")
    return store_setup.test(url)


def switch_store(body: dict) -> dict:
    mode = str(body.get("mode") or "local")
    url = str(body.get("url") or "").strip()
    try:
        out = store_setup.switch(mode, url)
    except store_setup.SetupError as e:
        raise OnboardError(str(e), 409) from e
    _clear_store_cache()
    return out


def start_build() -> dict:
    job = jobs.start("build", build.run)
    return {"job": job, "setup": _setup()}


def finish() -> dict:
    warnings = []
    st = _store_status(fresh=True)
    if not st.get("ready"):
        warnings.append("The store is not ready yet; the dashboard will show empty panels.")
    b = build.status()
    if not b.get("built"):
        warnings.append("The dashboard is not built yet; run " + b["hint"] + ".")
    if not downloads.status() or not any(d.get("state") == "ready" for d in downloads.status()):
        warnings.append("No model is ready yet; chat will have nothing to talk to until one lands.")
    state.complete()
    return {
        "ok": True,
        "url": "/" if b.get("built") else "/settings",
        "warnings": warnings,
        "state": state.read(),
    }


def reset() -> dict:
    state.reset(archive=True)
    for name in ("store", "build"):
        jobs.clear(name)
    _clear_store_cache()
    return {"state": state.read()}
