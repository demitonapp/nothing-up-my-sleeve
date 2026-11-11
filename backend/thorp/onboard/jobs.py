"""Small background jobs for the first run: the store's set-up and the dashboard's build.

Both are long enough that blocking an HTTP request would look like a dead page, so the API starts a
job and the page polls its state. There is one job per name; starting it again while it runs returns
the running one. The result is kept until the process ends, so a retry after a failure can read the
last error.
"""

from __future__ import annotations

import threading
import time
import traceback
from collections.abc import Callable

_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}


def _blank(name: str) -> dict:
    return {
        "name": name,
        "state": "idle",
        "started": None,
        "finished": None,
        "error": None,
        "result": None,
        "log": [],
    }


def start(name: str, fn: Callable[[], object]) -> dict:
    """Run `fn` in a daemon thread unless a job of this name is already running."""
    with _LOCK:
        current = _JOBS.get(name)
        if current and current["state"] == "running":
            return dict(current)
        job = _blank(name)
        job.update(state="running", started=time.time())
        _JOBS[name] = job

    def run() -> None:
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001  (the page shows the exception, the server stays up)
            with _LOCK:
                job.update(state="failed", error=str(e)[:2000], finished=time.time())
                job["log"].append(traceback.format_exc()[-4000:])
            return
        with _LOCK:
            job.update(state="done", result=result, finished=time.time())

    threading.Thread(target=run, name=f"onboard-{name}", daemon=True).start()
    with _LOCK:
        return dict(job)


def get(name: str) -> dict:
    with _LOCK:
        return dict(_JOBS.get(name) or _blank(name))


def all() -> dict:
    with _LOCK:
        return {k: dict(v) for k, v in _JOBS.items()}


def clear(name: str) -> None:
    with _LOCK:
        _JOBS.pop(name, None)
