"""Download a house's model from Hugging Face and put it in the chat terminal (12 November, Justin: "in that
table, there should be an icon to download the model and add it to the chat terminal").

The download is `huggingface_hub.snapshot_download` in one background thread; the status is a small dict
the page polls. When the weights land, the model is registered in `data/lab-downloads.json`, which
`thorp.foreign.chat_targets` merges, so the chat console lists it without a second edit. A model whose
repository is not MLX-loadable can still be downloaded; the console will say so when it tries to load it.
"""

from __future__ import annotations

import json
import threading
import time

from thorp import paths

FILE = paths.data_dir() / "lab-downloads.json"
_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}


def _read() -> dict[str, dict]:
    with _LOCK:
        if not FILE.exists():
            return {}
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001  a broken file is not a reason to lose the Hub
            return {}


def _write(data: dict[str, dict]) -> None:
    with _LOCK:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(FILE)


def _cached(repo: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(repo, "config.json"), str)
    except Exception:  # noqa: BLE001
        return False


def _label(repo: str) -> str:
    return repo.rsplit("/", 1)[-1]


def _key(repo: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in _label(repo).lower()).strip("-").replace("--", "-")


def downloaded() -> list[dict]:
    """The models this page has pulled, whether or not their weights are still cached."""
    return sorted(_read().values(), key=lambda r: (r.get("label") or "").lower())


def register(repo: str, lab: str, *, label: str | None = None, params: float | None = None) -> dict:
    data = _read()
    row = {
        "model": repo,
        "key": data.get(repo, {}).get("key") or _key(repo),
        "label": label or _label(repo),
        "lab": lab,
        "params": params,
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    data[repo] = row
    _write(data)
    return row


def start(repo: str, lab: str, *, label: str | None = None, params: float | None = None) -> dict:
    """Start (or join) a download; a cached model is registered and marked ready at once."""
    repo = str(repo or "").strip()
    if not repo:
        raise ValueError("no model")
    with _LOCK:
        job = _JOBS.get(repo)
        if job and job.get("state") in ("queued", "downloading"):
            return dict(job)
        if _cached(repo):
            row = register(repo, lab, label=label, params=params)
            _JOBS[repo] = {
                "model": repo, "lab": lab, "label": row["label"], "state": "ready",
                "started": None, "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "error": None, "cached": True,
            }
            return dict(_JOBS[repo])
        _JOBS[repo] = {
            "model": repo, "lab": lab, "label": label or _label(repo), "state": "queued",
            "started": None, "finished": None, "error": None, "cached": False,
        }
        job = dict(_JOBS[repo])
    threading.Thread(
        target=_work, args=(repo, lab, label, params), name=f"lab-download-{_key(repo)}", daemon=True
    ).start()
    return job


def _work(repo: str, lab: str, label: str | None, params: float | None) -> None:
    with _LOCK:
        _JOBS[repo].update(state="downloading", started=time.time())
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(repo_id=repo, max_workers=4)
        register(repo, lab, label=label, params=params)
        with _LOCK:
            _JOBS[repo].update(
                state="ready", finished=time.strftime("%Y-%m-%dT%H:%M:%S"), cached=_cached(repo), error=None
            )
    except Exception as e:  # noqa: BLE001  the page says what failed
        with _LOCK:
            _JOBS[repo].update(state="failed", finished=time.strftime("%Y-%m-%dT%H:%M:%S"), error=str(e))


def status(repo: str) -> dict:
    with _LOCK:
        job = _JOBS.get(repo)
        if job:
            return {**job, "cached": _cached(repo)}
    for row in downloaded():
        if row["model"] == repo:
            return {**row, "state": "ready" if _cached(repo) else "missing", "cached": _cached(repo), "error": None}
    return {"model": repo, "state": "not started", "cached": _cached(repo), "error": None}
