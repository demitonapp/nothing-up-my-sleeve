"""The phone drone's live voice, PersonaPlex (12 November, Justin: "download and connect personaplex to
the call drone").

PersonaPlex is NVIDIA's full-duplex speech-to-speech model (8.37B, based on Moshi): audio in, audio out,
barge-in and backchannels, no text in the middle. The official weights are gated and CUDA-first; the
build wired here is the **MLX Q4** conversion (`Investigo/personaplex-edge-q4`, 5.24 GiB), which runs on
Apple Silicon in real time and serves its own microphone UI on `127.0.0.1:8998`.

The page embeds that UI in the phone drone's "Live voice" panel, so the call drone has two lines:

- the **typed test line** (`phone.py`): the person is the keyboard, Qwen3.5 thinks, macOS `say` speaks;
- the **live voice line** (this module): the person is the microphone, PersonaPlex listens and answers
  in its own voice, locally.

The licence is not MIT: the edge build inherits **CC BY-NC 4.0** and the **NVIDIA Open Model License**
from its upstream lineage, so it is non-commercial. The page says so beside the model. No audio leaves
the Mac: the server binds loopback and the build's README states the same.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request

from thorp import paths

ARTIFACT = paths.data_dir() / "models" / "personaplex-edge-q4"
CLI = ARTIFACT / ".venv" / "bin" / "personaplex-edge"
PORT = 8998
URL = f"http://127.0.0.1:{PORT}"
LOG = paths.data_dir() / "personaplex.log"
_LOCK = threading.RLock()
_PROC: subprocess.Popen | None = None


def _healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def installed() -> bool:
    return (ARTIFACT / "model.q4.safetensors").exists() and CLI.exists()


def _manifest() -> dict:
    try:
        return json.loads((ARTIFACT / "manifest.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def status() -> dict:
    m = _manifest()
    total = m.get("totals") or {}
    return {
        "installed": installed(),
        "running": _healthy(),
        "url": URL,
        "port": PORT,
        "model": "PersonaPlex 7B · MLX Q4",
        "artifact_gib": round(float(total.get("artifact_gib") or 5.24), 2),
        "license": "CC BY-NC 4.0 + NVIDIA Open Model License (non-commercial)",
        "local": True,
        "log": str(LOG),
    }


def start() -> dict:
    """Start the live voice server. It listens on loopback and serves its own mic UI."""
    global _PROC
    if _healthy():
        return status()
    if not installed():
        raise RuntimeError("PersonaPlex is not downloaded: data/models/personaplex-edge-q4 is missing the artifact")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(CLI),
        "serve",
        "--artifact", ".",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--metrics-dir", "outputs/live",
    ]  # fmt: skip
    env = {**os.environ, "UV_CACHE_DIR": str(paths.ROOT / ".uv-cache")}
    with open(LOG, "ab") as out:
        out.write(f"\n\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n".encode())
        out.flush()
        _PROC = subprocess.Popen(cmd, cwd=str(ARTIFACT), stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    deadline = time.time() + 90
    while time.time() < deadline:
        if _healthy():
            return status()
        if _PROC.poll() is not None:
            raise RuntimeError(f"PersonaPlex exited ({_PROC.returncode}); see {LOG}")
        time.sleep(1.0)
    raise RuntimeError(f"PersonaPlex did not answer on {PORT} within 90s; see {LOG}")


def stop() -> dict:
    global _PROC
    if _PROC and _PROC.poll() is None:
        _PROC.terminate()
        try:
            _PROC.wait(timeout=8)
        except Exception:  # noqa: BLE001
            _PROC.kill()
    _PROC = None
    # a server started outside this process (from a shell) is not ours to kill: say what is true
    return status()
