"""Downloads for the first run: the outside instruct models, into the Hugging Face cache.

One worker, one model at a time: a first run on a MacBook is usually on a domestic connection, and
two 15 GB downloads make both slower and the progress less honest. `snapshot_download` resumes from
the cache, so a cancelled or interrupted model starts where it stopped. The catalogue is the
allow-list: the page cannot ask for an arbitrary repository.

Progress is measured from the cache directory on disk, not from a Hugging Face callback. That keeps
the worker independent of the Hub's download API, and it is the number that matters to the person
watching a disk fill up.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from thorp.onboard import catalogue

_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}
_QUEUE: list[str] = []
_CANCEL: dict[str, threading.Event] = {}
_WORKER: threading.Thread | None = None


def _now() -> float:
    return time.time()


def _cache_dir(repo: str) -> Path:
    try:
        from huggingface_hub import constants

        base = Path(constants.HF_HUB_CACHE)
    except Exception:  # noqa: BLE001
        import os

        base = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
    return base / ("models--" + repo.replace("/", "--"))


def _cache_bytes(repo: str) -> int:
    d = _cache_dir(repo)
    if not d.is_dir():
        return 0
    total = 0
    seen: set[str] = set()
    for p in d.rglob("*"):
        try:
            if not p.is_file():
                continue
            # the cache has blobs and snapshot symlinks to them: count each real file once
            real = str(p.resolve())
            if real in seen:
                continue
            seen.add(real)
            total += p.stat().st_size
        except OSError:
            continue
    return total


def _cached(repo: str) -> bool:
    """A config is not enough: a snapshot interrupted between the config and the weights would chat
    to nothing. Require at least one safetensors file beside it."""
    d = _cache_dir(repo)
    if not d.is_dir():
        return False
    if not any(d.rglob("config.json")):
        return False
    return any(p.suffix == ".safetensors" for p in d.rglob("*") if p.is_file())


def _total(repo: str) -> int:
    m = catalogue.get(repo)
    return int(float((m or {}).get("download_gb") or 0) * 1e9)


def _blank(repo: str) -> dict:
    m = catalogue.get(repo) or {}
    return {
        "repo": repo,
        "label": m.get("label") or repo.split("/")[-1],
        "band": m.get("band"),
        "state": "queued",
        "bytes_done": _cache_bytes(repo),
        "bytes_total": _total(repo),
        "percent": 0.0,
        "speed_bps": None,
        "started": None,
        "finished": None,
        "error": None,
        "cached": _cached(repo),
    }


def status() -> list[dict]:
    with _LOCK:
        rows = [dict(j) for j in _JOBS.values()]
    for r in rows:
        total = r.get("bytes_total") or 0
        done = r.get("bytes_done") or 0
        r["percent"] = (
            100.0
            if r.get("state") == "ready"
            else (round(100.0 * done / total, 1) if total else None)
        )
        r["cached"] = _cached(r["repo"])
    return sorted(rows, key=lambda r: (r["state"] == "ready", r["label"]))


def start(repos: list[str]) -> list[dict]:
    """Queue these catalogue repos. Already-cached models are marked ready and not fetched again."""
    global _WORKER
    wanted = []
    for repo in dict.fromkeys(str(r) for r in repos):
        if catalogue.get(repo) is None:
            raise ValueError(f"{repo!r} is not in the onboarding catalogue")
        wanted.append(repo)
    with _LOCK:
        for repo in wanted:
            job = _JOBS.get(repo)
            if job and job["state"] in ("queued", "downloading", "verifying", "cancelling"):
                continue
            if _cached(repo):
                job = _blank(repo)
                job.update(
                    state="ready", percent=100.0, finished=_now(), bytes_done=_cache_bytes(repo)
                )
                _JOBS[repo] = job
                continue
            _JOBS[repo] = _blank(repo)
            _CANCEL[repo] = threading.Event()
            if repo not in _QUEUE:
                _QUEUE.append(repo)
        if _WORKER is None or not _WORKER.is_alive():
            _WORKER = threading.Thread(target=_work, name="onboard-downloads", daemon=True)
            _WORKER.start()
    return status()


def cancel(repo: str) -> dict:
    with _LOCK:
        job = _JOBS.get(repo)
        if job is None:
            raise KeyError(repo)
        event = _CANCEL.get(repo)
        if event is not None:
            event.set()
        if job["state"] in ("queued", "downloading"):
            job["state"] = "cancelling"
        if repo in _QUEUE:
            _QUEUE.remove(repo)
            job["state"] = "cancelled"
            job["finished"] = _now()
        return dict(job)


def _work() -> None:
    while True:
        with _LOCK:
            if not _QUEUE:
                return
            repo = _QUEUE.pop(0)
            job = _JOBS.get(repo)
            cancel = _CANCEL.get(repo)
        if job is None:
            continue
        if cancel is not None and cancel.is_set():
            with _LOCK:
                job.update(state="cancelled", finished=_now())
            continue
        _download(repo, job, cancel or threading.Event())


def _download(repo: str, job: dict, cancel: threading.Event) -> None:
    with _LOCK:
        job.update(
            state="downloading", started=_now(), bytes_total=max(_total(repo), _cache_bytes(repo))
        )
    stop = threading.Event()

    def poll() -> None:
        while not stop.wait(1.0):
            done = _cache_bytes(repo)
            with _LOCK:
                job["bytes_done"] = done
                if done > (job.get("bytes_total") or 0):
                    job["bytes_total"] = done
                if job.get("started"):
                    elapsed = max(0.1, _now() - job["started"])
                    job["speed_bps"] = int(done / elapsed) if done else 0

    poller = threading.Thread(
        target=poll, name=f"onboard-download-{repo.split('/')[-1]}", daemon=True
    )
    poller.start()
    try:
        _snapshot(repo_id=repo, token=_token(), max_workers=4)
        if cancel.is_set():
            with _LOCK:
                job.update(state="cancelled", finished=_now())
            return
        with _LOCK:
            job.update(state="verifying", bytes_done=_cache_bytes(repo))
        if not _cached(repo):
            raise RuntimeError(
                "the download finished but the weights are not in the cache; "
                "check the repository's files and try again"
            )
        with _LOCK:
            job.update(
                state="ready",
                percent=100.0,
                bytes_done=_cache_bytes(repo),
                finished=_now(),
                error=None,
            )
    except Exception as e:  # noqa: BLE001  (the page says what failed; the worker stays alive)
        with _LOCK:
            job.update(state="failed", error=_friendly(e), finished=_now())
    finally:
        stop.set()
        poller.join(timeout=2)


def _snapshot(**kwargs):
    """One seam for tests: the real Hub call, or a fake that writes into the cache."""
    from huggingface_hub import snapshot_download

    return snapshot_download(**kwargs)


def _token() -> str | None:
    import os

    return os.environ.get("HF_TOKEN") or None


def _friendly(e: Exception) -> str:
    text = str(e).splitlines()[0][:600] if str(e) else e.__class__.__name__
    low = text.lower()
    if "gated" in low or "401" in low or "403" in low:
        return (
            "This model is gated. Accept its licence on Hugging Face, then set HF_TOKEN and retry. "
            f"({text})"
        )
    if "connection" in low or "timeout" in low or "resolve" in low:
        return f"Could not reach Hugging Face. Check the connection and retry. ({text})"
    return text
