"""The drone fleet under S1 operations (12 November, Justin: "under Liberty Machine S1 Operations we have a fleet of
drones. The first drone in the fleet will be the browser drone").

A **drone** is a worker, not a ship. A ship is a line of enquiry with voyages, a ledger and a queue; a
drone is one machine that does one job on demand and reports back. The fleet sits under S1 because it
does the work. The first drone is the **browser drone**: it drives a real Chrome through a
screenshot-and-click loop, the way Microsoft's Fara-1.5 was trained to.

Four parts, kept apart so each can be read alone:

- **The fleet** (`DRONES`) and the **pilots** (`PILOTS`): which models a drone may fly. Each pilot is a
  GGUF on the Hub with its vision projector, run by `llama.cpp`'s `llama-server` on this Mac. Fara-1.5-9B
  is the recommended one; Fara-1.5-4B is the small one; Holo-3.1-9B and GUI-Owl-1.5-8B are flown on a
  generic prompt and marked experimental, because only Fara ships the harness its prompt was trained with.
- **The state** (`data/drones.json`): the pilot each drone flies and its recent runs. A run is a record
  with its goal, its step log, the last screenshot and the answer or the error, so the page and the chat
  tool read the same thing.
- **The server** (`_ensure_server`): one `llama-server` per pilot, started on a free loopback port, kept
  for the next task, and stopped when the dashboard exits. Nothing is downloaded twice.
- **The loop** (`_run_browser`): Playwright drives Chrome at 1440x900; each step is a screenshot in, one
  `computer_use` call out, an action executed, and the result handed back as `<tool_response>`, which is
  the protocol Fara's own harness uses (`microsoft/fara`, src/fara/agents/fara/_prompts.py).

The weights come from the Hub into `data/models/`; the art is the art script's business
(`dash/art/generate_art.py`, `FAL_KEY`). Neither key is printed.
"""

from __future__ import annotations

import atexit
import base64
import contextlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from thorp import paths

# ---- the fleet and its pilots -------------------------------------------------------------------------


@dataclass(frozen=True)
class Pilot:
    """A model a drone may fly: one GGUF and its vision projector, run by llama.cpp."""

    key: str
    label: str
    source: str  # the model's canonical Hub repository (for the reader, not the download)
    repo: str  # the repository holding the quantised files
    quant: str  # the GGUF file
    mmproj: str  # the vision projector ("" for a text pilot)
    params: float
    harness: str  # "fara" (its own prompt), "generic" (a best-effort browser prompt) or "text"
    note: str
    recommended: bool = False
    experimental: bool = False
    vision: bool = True  # a browser drone needs eyes; an email drone does not


PILOTS: dict[str, Pilot] = {
    p.key: p
    for p in (
        Pilot(
            key="fara-1.5-9b",
            label="Fara1.5 9B",
            source="microsoft/Fara1.5-9B",
            repo="bartowski/Fara1.5-9B-GGUF",
            quant="Fara1.5-9B-Q4_K_M.gguf",
            mmproj="mmproj-Fara1.5-9B-f16.gguf",
            params=9.0e9,
            harness="fara",
            note="Microsoft's browser agent. 86.6 WebVoyager, 63.4 Online-Mind2Web (self-reported), MIT; "
            "trained to stop at critical points. The one to fly unless the Mac is small.",
            recommended=True,
        ),
        Pilot(
            key="fara-1.5-4b",
            label="Fara1.5 4B",
            source="microsoft/Fara1.5-4B",
            repo="bartowski/Fara1.5-4B-GGUF",
            quant="Fara1.5-4B-Q4_K_M.gguf",
            mmproj="mmproj-Fara1.5-4B-f16.gguf",
            params=4.54e9,
            harness="fara",
            note="The same recipe at half the size: 80.8 WebVoyager, 57.3 Online-Mind2Web. Faster and "
            "happier on 16 GB; weaker on long tasks.",
        ),
        Pilot(
            key="holo-3.1-9b",
            label="Holo3.1 9B",
            source="Hcompany/Holo-3.1-9B",
            repo="mradermacher/Holo-3.1-9B-GGUF",
            quant="Holo-3.1-9B.Q4_K_M.gguf",
            mmproj="Holo-3.1-9B.mmproj-f16.gguf",
            params=9.41e9,
            harness="generic",
            note="H Company's computer-use model, Apache 2.0. Strong grounding and desktop+mobile breadth, "
            "but no published web benchmark for this size and no Fara-style prompt here.",
            experimental=True,
        ),
        Pilot(
            key="qwen3.5-9b-instruct",
            label="Qwen3.5 9B",
            source="Qwen/Qwen3.5-9B",
            repo="unsloth/Qwen3.5-9B-GGUF",
            quant="Qwen3.5-9B-Q4_K_M.gguf",
            mmproj="",
            params=9.0e9,
            harness="text",
            note="A text pilot: reads a thread or holds a conversation and keeps the tone. No screenshots, "
            "so it is cheaper per step than the browser pilots.",
            recommended=True,
            vision=False,
        ),
        Pilot(
            key="qwen3.5-4b-instruct",
            label="Qwen3.5 4B",
            source="Qwen/Qwen3.5-4B",
            repo="unsloth/Qwen3.5-4B-GGUF",
            quant="Qwen3.5-4B-Q4_K_M.gguf",
            mmproj="",
            params=4.54e9,
            harness="text",
            note="The small text pilot: quicker on a 16 GB Mac, less nuance in a long thread or call.",
            vision=False,
        ),
        Pilot(
            key="gui-owl-1.5-8b",
            label="GUI-Owl 1.5 8B",
            source="mPLUG/GUI-Owl-1.5-8B-Think",
            repo="mradermacher/GUI-Owl-1.5-8B-Think-GGUF",
            quant="GUI-Owl-1.5-8B-Think.Q4_K_M.gguf",
            mmproj="GUI-Owl-1.5-8B-Think.mmproj-f16.gguf",
            params=8.77e9,
            harness="generic",
            note="Alibaba's multi-platform agent, MIT: 78.1 WebVoyager, 48.6 Online-Mind2Web. Broad but not "
            "web-specialised, and flown here on the generic prompt.",
            experimental=True,
        ),
    )
}


@dataclass(frozen=True)
class Drone:
    key: str
    label: str  # its number in the fleet (D1)
    name: str
    purpose: str
    art: str
    default_pilot: str
    kind: str = "browser"  # "browser" flies Chrome; "email" reads and drafts mail
    pilots: tuple[str, ...] = ()  # the pilots it may fly; () means every vision pilot


DRONES: dict[str, Drone] = {
    d.key: d
    for d in (
        Drone(
            key="browser",
            label="D1",
            name="Browser drone",
            purpose="flies a real Chrome: opens a page, reads it, clicks, types and comes back with the "
            "answer — the fleet's first worker, under S1 operations",
            art="drone-browser",
            default_pilot="fara-1.5-9b",
            pilots=("fara-1.5-9b", "fara-1.5-4b", "holo-3.1-9b", "gui-owl-1.5-8b"),
        ),
        Drone(
            key="email",
            label="D2",
            name="Email drone",
            purpose="reads a mailbox, drafts a reply in the thread's own voice, and sends it once the mail "
            "bridge is given an account — the fleet's second worker, under S1 operations",
            art="drone-email",
            default_pilot="qwen3.5-9b-instruct",
            kind="email",
            pilots=("qwen3.5-9b-instruct", "qwen3.5-4b-instruct"),
        ),
        Drone(
            key="phone",
            label="D3",
            name="Phone drone",
            purpose="places a call, listens to the other voice, answers in its own and comes back with what "
            "was said — the fleet's third worker, under S1 operations",
            art="drone-phone",
            default_pilot="qwen3.5-9b-instruct",
            kind="phone",
            pilots=("qwen3.5-9b-instruct", "qwen3.5-4b-instruct"),
        ),
    )
}

# what the email drone still needs before it can fly: the transport is Justin's choice, so the page says
# the three ways rather than picking one. Drafting can come first; sending and reading need an account.
MAIL_BRIDGE = {
    "configured": False,
    "options": [
        "SMTP + IMAP account: a host, a user and an app password in data/email.json (nothing is sent until it is there)",
        "Gmail or Outlook OAuth: an app and a token, so the drone reads a label or folder rather than a password",
        "A signed-in Chrome profile: the drone drives webmail as a page, the way the browser drone drives any site",
    ],
}

# the models the notes in research_notes/ recommended but that cannot fly here yet, said in the page
# rather than hidden: MolmoWeb-8B is F32 only and has no GGUF, so it is not a pilot.
NOT_FLYABLE = [
    {"label": "MolmoWeb 8B", "why": "F32 weights only, no GGUF or MLX build: it cannot be flown by llama.cpp here"},
    {"label": "Holo4 27B", "why": "CC BY-NC 4.0 and 27B: outside the drone fleet's licence and size"},
]

# What the phone drone needs before it can dial. The pilot thinks; the voice stack listens and speaks;
# the line carries it. None of the three is assumed, and the safety terms are the call's, not the model's:
# an AI says it is one, and the fleet does not dial emergency or premium numbers.
PHONE_BRIDGE = {
    "configured": True,
    "mode": "local",
    "options": [
        "Local test line (chosen): the person is typed at a keyboard and the drone speaks through macOS say — no carrier, no number, no microphone",
        "Twilio Programmable Voice + Media Streams: later, when a real line is wanted",
        "SIP / Asterisk: later, for a number you already own",
    ],
    "voice": [
        "ears · the keyboard on the test line (Whisper is the next step)",
        "mouth · macOS say: installed on this Mac",
        "line · local test only: real numbers are refused",
    ],
    "safety": [
        "the drone says it is an AI at the start of every call",
        "no emergency numbers and no premium-rate numbers, refused before dialling",
        "a per-call allowlist and a do-not-call list, kept in data/phone.json",
        "every call transcribed and kept, and recording is disclosed",
        "the pilot may end a call, but cannot redial after a hang-up",
    ],
}

# ---- the state ----------------------------------------------------------------------------------------

STATE = paths.data_dir() / "drones.json"
MODELS = paths.data_dir() / "models"
RUNS = paths.data_dir() / "drones"

_LOCK = threading.RLock()
_RUNS: dict[str, dict] = {}  # the runs in memory, mirrored into STATE
_DOWNLOADS: dict[str, dict] = {}
_SERVERS: dict[str, dict] = {}
# one Chrome, one task: a second ask while the drone is flying is refused rather than queued behind it
_BUSY = threading.Lock()

MAX_STEPS = 30
DEFAULT_STEPS = 15
KEEP_RUNS = 20
KEEP_SHOTS = 4


def _read() -> dict:
    with _LOCK:
        if not STATE.exists():
            return {}
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001  a broken file is not a reason to lose the fleet
            return {}


def _write(data: dict) -> None:
    with _LOCK:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE)


def _slot(data: dict, drone: str) -> dict:
    slot = data.get(drone)
    if not isinstance(slot, dict):
        slot = {}
        data[drone] = slot
    slot.setdefault("model", DRONES[drone].default_pilot)
    slot.setdefault("runs", [])
    return slot


def selected(drone: str = "browser") -> str:
    """The pilot a drone flies: its saved choice, else the fleet's default (a model no longer in the
    registry falls back rather than leaving the drone without a pilot)."""
    d = DRONES.get(drone)
    if d is None:
        raise ValueError(f"no drone called {drone!r}; the fleet is {', '.join(DRONES)}")
    key = (_read().get(drone) or {}).get("model") or d.default_pilot
    return key if key in PILOTS else d.default_pilot


def installed(model: str) -> dict:
    """Whether a pilot's two files are on disk, with their paths and sizes for the page."""
    p = PILOTS.get(model)
    if p is None:
        return {"ready": False}
    d = MODELS / model
    q = d / p.quant
    m = d / p.mmproj if p.mmproj else None
    return {
        "ready": q.exists() and (m is None or m.exists()),
        "quant": str(q),
        "mmproj": str(m) if m else "",
        "quant_bytes": q.stat().st_size if q.exists() else 0,
        "mmproj_bytes": m.stat().st_size if m and m.exists() else 0,
        "dir": str(d),
    }


def models_payload(drone: str = "browser") -> list[dict]:
    """The pilots a drone may fly: a browser drone needs eyes, an email drone wants a text model."""
    d = DRONES.get(drone)
    if d is None:
        raise ValueError(f"no drone called {drone!r}; the fleet is {', '.join(DRONES)}")
    allowed = set(d.pilots) if d.pilots else {k for k, p in PILOTS.items() if p.vision}
    rows = []
    for p in (p for p in PILOTS.values() if p.key in allowed):
        got = installed(p.key)
        rows.append(
            {
                "key": p.key,
                "label": p.label,
                "source": p.source,
                "params_b": round(p.params / 1e9, 2),
                "harness": p.harness,
                "note": p.note,
                "recommended": p.recommended,
                "experimental": p.experimental,
                "installed": bool(got.get("ready")),
                "size_gb": round(((got.get("quant_bytes") or 0) + (got.get("mmproj_bytes") or 0)) / 1e9, 2),
                "download": _DOWNLOADS.get(p.key),
            }
        )
    return rows


_RECONCILED = False


def _reconcile() -> None:
    """A run the file still says is flying, in a process that has no thread for it, was cut off by a
    dashboard restart: say so rather than leaving the page flying for ever."""
    global _RECONCILED
    if _RECONCILED:
        return
    _RECONCILED = True
    with _LOCK:
        data = _read()
        changed = False
        for slot in data.values():
            if not isinstance(slot, dict):
                continue
            for r in slot.get("runs") or []:
                if isinstance(r, dict) and r.get("state") in ("queued", "running") and r.get("id") not in _RUNS:
                    r["state"] = "error"
                    r["error"] = "the dashboard restarted while the drone was flying"
                    r["finished"] = r.get("finished") or time.strftime("%Y-%m-%dT%H:%M:%S")
                    changed = True
        if changed:
            _write(data)


def _phone_payload() -> dict:
    from thorp import phone

    return phone.payload()


def payload(drone: str = "browser") -> dict:
    """The fleet card and the drone's page, in one reading."""
    d = DRONES.get(drone)
    if d is None:
        raise ValueError(f"no drone called {drone!r}; the fleet is {', '.join(DRONES)}")
    _reconcile()
    key = selected(drone)
    pilot = PILOTS[key]
    runs = _runs(drone)
    return {
        "drone": {
            "key": d.key,
            "label": d.label,
            "name": d.name,
            "purpose": d.purpose,
            "art": d.art,
            "kind": d.kind,
        },
        "fleet": [{"key": x.key, "label": x.label, "name": x.name} for x in DRONES.values()],
        "models": models_payload(drone),
        "bridge": MAIL_BRIDGE if d.kind == "email" else PHONE_BRIDGE if d.kind == "phone" else None,
        "phone": _phone_payload() if d.kind == "phone" else None,
        "selected": key,
        "selected_label": pilot.label,
        "runs": runs,
        "latest": runs[0] if runs else None,
        "not_flyable": NOT_FLYABLE,
        "busy": d.kind == "browser" and _BUSY.locked(),
        "server": {
            "running": bool((_SERVERS.get(key) or {}).get("process") and _SERVERS[key]["process"].poll() is None),
            "port": (_SERVERS.get(key) or {}).get("port"),
        },
    }


def fleet_payload() -> dict:
    """The fleet as cards: each drone, the pilot it flies, whether it is flying, and what it is still
    waiting for (the email drone's mail bridge)."""
    _reconcile()
    rows = []
    for d in DRONES.values():
        key = selected(d.key)
        if d.kind == "phone":
            from thorp import phone

            ph = phone.payload()
            latest = ph["active"] or (ph["calls"][0] if ph["calls"] else None)
            rows.append(
                {
                    "key": d.key,
                    "label": d.label,
                    "name": d.name,
                    "purpose": d.purpose,
                    "art": d.art,
                    "kind": d.kind,
                    "selected_label": PILOTS[key].label,
                    "busy": bool(ph["active"]),
                    "latest": latest,
                    "runs": len(ph["calls"]),
                    "bridge": ph["bridge"],
                }
            )
            continue
        runs = _runs(d.key)
        rows.append(
            {
                "key": d.key,
                "label": d.label,
                "name": d.name,
                "purpose": d.purpose,
                "art": d.art,
                "kind": d.kind,
                "selected_label": PILOTS[key].label,
                "busy": d.kind == "browser" and _BUSY.locked(),
                "latest": runs[0] if runs else None,
                "runs": len(runs),
                "bridge": MAIL_BRIDGE if d.kind == "email" else None,
            }
        )
    return {"drones": rows}


def _runs(drone: str) -> list[dict]:
    """Every run in memory, newest first, then the ones the file kept from an earlier dashboard."""
    with _LOCK:
        live = [r for r in _RUNS.values() if r.get("drone") == drone]
        known = {r["id"] for r in live}
        saved = [
            r
            for r in ((_read().get(drone) or {}).get("runs") or [])
            if isinstance(r, dict) and r.get("id") not in known
        ]
    return sorted(live + saved, key=lambda r: str(r.get("started") or ""), reverse=True)


def select(drone: str, model: str) -> dict:
    """Choose the pilot a drone flies. Only an installed model can be chosen: a choice that cannot fly
    is a page that lies."""
    if drone not in DRONES:
        raise ValueError(f"no drone called {drone!r}; the fleet is {', '.join(DRONES)}")
    if model not in PILOTS:
        raise ValueError(f"no pilot called {model!r}; the pilots are {', '.join(PILOTS)}")
    got = installed(model)
    if not got.get("ready"):
        raise ValueError(f"{PILOTS[model].label} is not downloaded yet: download it first")
    data = _read()
    _slot(data, drone)["model"] = model
    _slot(data, drone)["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _write(data)
    return payload(drone)


# ---- the download -------------------------------------------------------------------------------------


def start_download(model: str) -> dict:
    """Pull a pilot's GGUF and projector into data/models/<key>/; a second ask joins the first."""
    p = PILOTS.get(model)
    if p is None:
        raise ValueError(f"no pilot called {model!r}")
    if installed(model).get("ready"):
        job = {"model": model, "state": "ready", "cached": True, "started": None,
               "finished": time.strftime("%Y-%m-%dT%H:%M:%S"), "error": None}  # fmt: skip
        _DOWNLOADS[model] = job
        return dict(job)
    with _LOCK:
        job = _DOWNLOADS.get(model)
        if job and job.get("state") in ("queued", "downloading"):
            return dict(job)
        _DOWNLOADS[model] = {
            "model": model, "state": "queued", "started": None, "finished": None,
            "error": None, "cached": False,
        }  # fmt: skip
        job = dict(_DOWNLOADS[model])
    threading.Thread(target=_download, args=(model,), name=f"drone-download-{model}", daemon=True).start()
    return job


def download_status(model: str) -> dict:
    if model not in PILOTS:
        raise ValueError(f"no pilot called {model!r}")
    return _DOWNLOADS.get(model) or {"model": model, "state": "ready" if installed(model).get("ready") else "absent"}


def _download(model: str) -> None:
    p = PILOTS[model]
    dest = MODELS / model
    with _LOCK:
        _DOWNLOADS[model].update(state="downloading", started=time.time())
    try:
        from huggingface_hub import hf_hub_download

        dest.mkdir(parents=True, exist_ok=True)
        for name in (p.quant, p.mmproj):
            if name:
                hf_hub_download(repo_id=p.repo, filename=name, local_dir=str(dest))
        got = installed(model)
        if not got.get("ready"):
            raise RuntimeError("the files are not where they were written")
        with _LOCK:
            _DOWNLOADS[model].update(
                state="ready", finished=time.strftime("%Y-%m-%dT%H:%M:%S"), cached=False, error=None
            )
    except Exception as e:  # noqa: BLE001  the page says what failed
        with _LOCK:
            _DOWNLOADS[model].update(
                state="error", finished=time.strftime("%Y-%m-%dT%H:%M:%S"), error=f"{e.__class__.__name__}: {e}"
            )


# ---- the server ---------------------------------------------------------------------------------------


def _free_port() -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def _healthy(port: int | None) -> bool:
    if not port:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001  not up yet
        return False


def _tail(path: Path, n: int = 700) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[-n:].strip()
    except Exception:  # noqa: BLE001
        return ""


def _ensure_server(model: str, timeout: float = 300.0) -> dict:
    """The pilot's llama.cpp server, started once and kept. Raises with the tail of its log when it
    will not come up."""
    p = PILOTS[model]
    got = installed(model)
    if not got.get("ready"):
        raise RuntimeError(f"{p.label} is not downloaded")
    cur = _SERVERS.get(model)
    if cur and cur.get("process") and cur["process"].poll() is None and _healthy(cur.get("port")):
        return cur
    if cur and cur.get("process"):
        _stop(cur["process"])
    # one pilot in memory at a time: a 9B and a 4B together are more than a small Mac should carry
    for other, rec in list(_SERVERS.items()):
        if other != model and rec.get("process"):
            _stop(rec["process"])
            _SERVERS.pop(other, None)
    port = _free_port()
    RUNS.mkdir(parents=True, exist_ok=True)
    log = RUNS / f"server-{model}.log"
    cmd = [
        "llama-server",
        "-m", str(got["quant"]),
        *(["--mmproj", str(got["mmproj"])] if p.mmproj else []),
        "--host", "127.0.0.1",
        "--port", str(port),
        "-c", "32768",
        "-ngl", "999",
        "-fa", "auto",
        # llama.cpp's own warning: Qwen-VL models want at least 1024 image tokens for grounding
        *(["--image-min-tokens", "1024"] if p.mmproj else []),
    ]  # fmt: skip
    with open(log, "ab") as out:
        out.write(f"\n\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(cmd)}\n".encode())
        out.flush()
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"llama-server exited ({proc.returncode}): {_tail(log)}")
        if _healthy(port):
            rec = {"process": proc, "port": port, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "log": str(log)}
            _SERVERS[model] = rec
            return rec
        time.sleep(1.0)
    _stop(proc)
    raise RuntimeError(f"llama-server did not answer on {port} within {int(timeout)}s: {_tail(log)}")


def _stop(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def stop_servers() -> None:
    for rec in list(_SERVERS.values()):
        if rec.get("process"):
            _stop(rec["process"])
    _SERVERS.clear()

atexit.register(stop_servers)


def _chat(port: int, messages: list[dict], max_tokens: int = 1536, thinking: bool | None = None) -> str:
    payload: dict = {"model": "drone", "messages": messages, "temperature": 0, "max_tokens": max_tokens, "stream": False}
    if thinking is False:
        # Qwen3.5 otherwise writes its reasoning into the answer: a phone turn is one or two sentences
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read().decode())
    msg = ((data.get("choices") or [{}])[0].get("message") or {})
    return str(msg.get("content") or msg.get("reasoning_content") or "").strip()


# ---- the prompts --------------------------------------------------------------------------------------

_FARA_IDENTITY = """\
You are Fara, a computer use agent (CUA) specialized for web browsers. \
You are developed by Microsoft AI Frontiers. You assist users with \
completing and automating tasks that require the use of a web browser.

The model was trained in the timeframe of January - April 2026. You can \
effectively perform tasks even beyond this range by accessing the web \
browser and using the latest information on the live web. But your \
knowledge cutoff is limited to early 2026, so you may not be aware of \
events or developments that occurred after that time, without explicitly \
browsing and searching for latest information on the web.

This edition of the model was trained using SFT on top of \
{base}, using a synthetic data mixture generated and \
developed by Microsoft AI Frontiers."""

_FARA_CRITICAL = """\
A critical point is a situation where we must pause and request information or confirmation from the user before \
proceeding. There are three types:

Case 1: Missing User Information — The task requires personal information that the user has not provided (e.g., email, \
phone number, address, payment details). Never fabricate or assume personal information. Fill in only what the user has \
explicitly provided, then pause and ask for any missing required fields. (e.g., form requires phone number but user \
only gave name and email -> fill name and email, then ask for phone number.) If the user has provided all required \
information, proceed without stopping.

Case 2: Underspecified Task — The task description is ambiguous or missing details needed to make a decision at the \
current step. Pause and ask for clarification. (e.g., user asks to book a flight but doesn't specify destination -> \
ask for destination.) If the user's instructions contain all information needed for the current decision, proceed \
without stopping.

Case 3: Irreversible Action — We are about to perform an action that cannot be undone (e.g., submitting a form, \
completing a purchase, sending a message, deleting data). If the user explicitly authorized the action (e.g., "submit \
the form", "complete the purchase", "you have my permission to submit") -> proceed without stopping. If the user did \
NOT explicitly authorize the action -> stop and ask for confirmation. (e.g., "fill out a form" with no mention of \
submitting -> fill the form, then ask before submitting; "fill out and submit a form" -> fill and submit without \
stopping.)

Only stop at a critical point if (1) required information is missing, (2) the task is ambiguous, OR (3) an irreversible \
action lacks explicit user authorization. If the user has provided all necessary information AND explicitly authorized \
the action, proceed without interruption."""

_FN_CALL = """\
You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tool_descs}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>"""

_ACTIONS = (
    "key", "type", "mouse_move", "left_click", "left_click_drag", "right_click", "double_click",
    "triple_click", "scroll", "hscroll", "visit_url", "history_back", "web_search",
    "read_page_answer_question", "pause_and_memorize_fact", "ask_user_question", "wait", "terminate",
)  # fmt: skip


def _schema(width: int, height: int) -> dict:
    """Fara-1.5's computer_use schema, as its own harness describes it (microsoft/fara, _prompts.py)."""
    return {
        "name": "computer_use",
        "description": (
            "Use a mouse and keyboard to interact with a computer, and take screenshots.\n"
            f"* The screen's resolution is {width}x{height}.\n"
            "* Whenever you intend to move the cursor to click on an element like an icon, you should "
            "consult a screenshot to determine the coordinates of the element before moving the cursor.\n"
            "* If you tried clicking on a program or link but it failed to load, even after waiting, try "
            "adjusting your cursor position so that the tip of the cursor visually falls on the element "
            "that you want to click.\n"
            "* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the "
            "element. Don't click boxes on their edges."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(_ACTIONS),
                    "description": "The action to perform. `terminate` ends the task and returns the answer.",
                },
                "keys": {"type": "array", "description": "Required only by `action=key`."},
                "text": {"type": "string", "description": "Required only by `action=type`."},
                "coordinate": {
                    "type": "array",
                    "description": "(x, y) pixels from the left and top edge. Required by the click and move actions.",
                },
                "pixels": {"type": "number", "description": "Scroll amount; positive scrolls up."},
                "url": {"type": "string", "description": "Required only by `action=visit_url`."},
                "query": {"type": "string", "description": "Required only by `action=web_search`."},
                "fact": {"type": "string", "description": "Required only by `action=pause_and_memorize_fact`."},
                "question": {"type": "string", "description": "Required by `read_page_answer_question` and `ask_user_question`."},
                "time": {"type": "number", "description": "Seconds to wait. Required only by `action=wait`."},
                "answer": {"type": "string", "description": "The final answer. Required only by `action=terminate`."},
            },
            "required": ["action"],
        },
    }


def _fara_system(pilot: Pilot, width: int, height: int) -> str:
    """The system prompt Fara was trained against: identity, critical points, then the tool schema in
    the function-call template its harness composes."""
    base = "Qwen3.5-4B" if pilot.key == "fara-1.5-4b" else "Qwen3.5-9B"
    tool = json.dumps({"type": "function", "function": _schema(width, height)}, ensure_ascii=False)
    return _FARA_IDENTITY.format(base=base) + "\n\n" + _FARA_CRITICAL + "\n\n" + _FN_CALL.replace("{tool_descs}", tool)


def _generic_system(pilot: Pilot, width: int, height: int) -> str:
    """The best-effort prompt for a model whose own harness we do not ship. It asks for the same
    computer_use call in the same JSON grammar, and says plainly that it is not the model's own prompt."""
    tool = json.dumps({"type": "function", "function": _schema(width, height)}, ensure_ascii=False)
    return (
        "You are the browser drone of Nothing up my sleeve, a careful worker that drives a real Chrome "
        "browser to finish one task and report what it found.\n\n"
        f"The screen is {width}x{height} pixels. At each step you are given a screenshot of the page and "
        "a log of what has happened. Decide the single next action, and reply with one tool call.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n"
        f"<tools>\n{tool}\n</tools>\n\n"
        "For each function call, return a json object with function name and arguments within "
        "<tool_call></tool_call> XML tags:\n"
        "<tool_call>\n"
        '{"name": "computer_use", "arguments": {"action": "left_click", "coordinate": [640, 400]}}\n'
        "</tool_call>\n\n"
        "Work in small steps and look at the screenshot after each one. When the task is finished, call "
        "computer_use with action=terminate and put the answer in `answer`. If the task needs a person "
        "(a sign-in, a payment, a missing detail, an irreversible action), call action=ask_user_question "
        "and put the question in `question`. Never invent personal information."
    )


def _system(pilot: Pilot, width: int, height: int) -> str:
    return _fara_system(pilot, width, height) if pilot.harness == "fara" else _generic_system(pilot, width, height)


# ---- the browser loop ---------------------------------------------------------------------------------


def _shot_b64(page) -> str:
    return base64.b64encode(page.screenshot(type="png")).decode()


def _user(text: str, png: str) -> dict:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png}"}},
        ],
    }


def _trim(messages: list[dict], keep: int = 10) -> list[dict]:
    """Keep the system turn and the last few exchanges, and only the last three screenshots: Fara was
    trained on the three most recent, and a long history of images is what makes a small model drift."""
    if len(messages) <= keep + 1:
        return messages
    head, rest = messages[0], messages[1:]
    task = rest[0] if rest and isinstance(rest[0].get("content"), str) else None
    rest = rest[-keep:]
    if task is not None and not (rest and rest[0] is task):
        rest = [{"role": "user", "content": task}] + rest
    seen = 0
    for m in reversed(rest):
        c = m.get("content")
        if isinstance(c, list):
            # strip images after the third most recent
            out = []
            for part in c:
                if part.get("type") == "image_url":
                    seen += 1
                    if seen > 3:
                        continue
                out.append(part)
            if out:
                m["content"] = out
    return [head] + rest


def _coords(value: Any) -> tuple[int, int] | None:
    try:
        x, y = value  # type: ignore[misc]
        return int(round(float(x))), int(round(float(y)))
    except Exception:  # noqa: BLE001
        return None


def _clean_url(url: str) -> str:
    """A page the drone may visit: http(s), or a bare host it can put https in front of. Anything else
    (file://, javascript:, data:) is refused, so a page cannot talk the drone into reading this Mac."""
    u = str(url or "").strip()
    if re.match(r"^https?://", u, re.I):
        return u
    if re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", u, re.I):
        return "https://" + u
    raise ValueError("the drone visits http and https pages only")


def _goto(page, url: str) -> None:
    page.goto(_clean_url(url), wait_until="domcontentloaded", timeout=45000)


def _execute(page, args: dict, facts: list[str]) -> dict:
    """One computer_use call, executed. A failure is a result the model reads, never an exception that
    ends the run."""
    a = str(args.get("action") or "").strip()
    xy = _coords(args.get("coordinate"))
    try:
        if a == "left_click" and xy:
            page.mouse.click(xy[0], xy[1])
        elif a == "right_click" and xy:
            page.mouse.click(xy[0], xy[1], button="right")
        elif a == "double_click" and xy:
            page.mouse.click(xy[0], xy[1], click_count=2)
        elif a == "triple_click" and xy:
            page.mouse.click(xy[0], xy[1], click_count=3)
        elif a == "mouse_move" and xy:
            page.mouse.move(xy[0], xy[1])
        elif a == "left_click_drag":
            target = _coords(args.get("coordinate"))
            to = _coords(args.get("to")) or _coords(args.get("end")) or target
            if not target or not to:
                return {"ok": False, "error": "left_click_drag needs a start and an end coordinate"}
            page.mouse.move(target[0], target[1])
            page.mouse.down()
            page.mouse.move(to[0], to[1], steps=12)
            page.mouse.up()
        elif a == "type":
            page.keyboard.type(str(args.get("text") or ""), delay=8)
        elif a == "key":
            keys = args.get("keys") or []
            if isinstance(keys, str):
                keys = [keys]
            if not keys:
                return {"ok": False, "error": "key needs `keys`"}
            for k in keys:
                page.keyboard.down(str(k))
            for k in reversed(keys):
                page.keyboard.up(str(k))
        elif a == "scroll":
            page.mouse.wheel(0, -int(float(args.get("pixels") or 0)))
        elif a == "hscroll":
            page.mouse.wheel(int(float(args.get("pixels") or 0)), 0)
        elif a == "visit_url":
            _goto(page, str(args.get("url") or ""))
        elif a == "history_back":
            page.go_back(wait_until="domcontentloaded", timeout=30000)
        elif a == "web_search":
            q = quote_plus(str(args.get("query") or ""))
            _goto(page, f"https://duckduckgo.com/?q={q}")
        elif a == "read_page_answer_question":
            text = page.inner_text("body", timeout=15000)
            return {"ok": True, "text": re.sub(r"\s+", " ", text)[:5000]}
        elif a == "pause_and_memorize_fact":
            fact = str(args.get("fact") or "").strip()
            if fact:
                facts.append(fact)
            return {"ok": True, "memorised": fact, "facts": facts}
        elif a == "wait":
            time.sleep(max(0.0, min(float(args.get("time") or 1), 15.0)))
        elif a in ("ask_user_question", "terminate"):
            return {"ok": True}
        else:
            return {"ok": False, "error": f"unknown action {a!r}"}
        page.wait_for_timeout(350)
        return {"ok": True, "url": page.url, "title": page.title()}
    except Exception as e:  # noqa: BLE001  the model reads the failure and tries another way
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def _run_browser(record: dict) -> None:
    """The observe-think-act loop: screenshot, one computer_use call, the action, the result back."""
    from playwright.sync_api import sync_playwright

    from thorp import chat_tools

    pilot = PILOTS[record["model"]]
    server = _ensure_server(record["model"])
    width, height = 1440, 900
    run_dir = RUNS / "runs" / record["id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    messages: list[dict] = [
        {"role": "system", "content": _system(pilot, width, height)},
        # the task is the first thing the model reads, as Fara's harness sends it: the goal, then
        # a screenshot a step, each said with the page it is looking at
        {"role": "user", "content": f"Task: {record['goal']}" + (f"\nStart at: {record['url']}" if record.get("url") else "")},
    ]
    facts: list[str] = []

    with sync_playwright() as pw:
        headless = os.environ.get("THORP_DRONE_HEADFUL") != "1"
        try:
            browser = pw.chromium.launch(
                channel="chrome", headless=headless, args=["--disable-blink-features=AutomationControlled"]
            )
        except Exception:  # noqa: BLE001  no Chrome installed: the bundled Chromium, if it is there
            browser = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        page.set_default_timeout(20000)
        try:
            _goto(page, record.get("url") or "https://duckduckgo.com/")
            page.wait_for_timeout(800)
            for step in range(1, int(record["max_steps"]) + 1):
                png = _shot_b64(page)
                shot = run_dir / f"step-{step:02d}.png"
                shot.write_bytes(base64.b64decode(png))
                record["shot"] = str(shot)
                text = f"Current URL: {page.url}\nHere is the next screenshot. Think about what to do next."
                if facts:
                    text += "\n\nFacts you have memorised: " + " | ".join(facts[-5:])
                messages.append(_user(text, png))
                reply = _chat(server["port"], _trim(messages))
                calls = chat_tools.parse_calls(reply, "json")
                if not calls:
                    nudge = "No tool call was found. Reply with one <tool_call> JSON object calling computer_use."
                    messages.append({"role": "assistant", "content": reply})
                    messages.append({"role": "user", "content": nudge})
                    if step < 3:
                        continue
                    raise RuntimeError("the model made no tool call three steps running")
                call = calls[0]
                thought = chat_tools.before_calls(reply)
                args = call.get("arguments") or {}
                result = _execute(page, args, facts) if not call.get("error") else {"ok": False, "error": call["error"]}
                action = str(args.get("action") or "")
                record["steps"] = step
                record["thought"] = thought[-1200:]
                shown = {k: v for k, v in args.items() if k != "coordinate"}
                if args.get("coordinate"):
                    shown["coordinate"] = list(args["coordinate"])
                note = str(result.get("error") or result.get("text") or "")[:300]
                record["log"].append(
                    {
                        "n": step,
                        "thought": thought[-1200:],
                        "action": action,
                        "args": shown,
                        "ok": bool(result.get("ok")),
                        "note": note,
                    }
                )
                messages.append({"role": "assistant", "content": reply})
                messages.append(
                    {"role": "user", "content": "<tool_response>\n" + json.dumps(result, ensure_ascii=False)[:4000] + "\n</tool_response>"}
                )
                _save(record)
                if action == "terminate":
                    record["state"] = "done"
                    record["answer"] = str(args.get("answer") or thought or "").strip()
                    return
                if action == "ask_user_question":
                    record["state"] = "needs_user"
                    record["question"] = str(args.get("question") or "").strip()
                    return
                if not result.get("ok"):
                    page.wait_for_timeout(600)
            record["state"] = "stopped"
            record["answer"] = record.get("thought") or ""
            record["error"] = f"stopped after {record['max_steps']} steps without terminate"
        finally:
            with contextlib.suppress(Exception):
                context.close()
            with contextlib.suppress(Exception):
                browser.close()


# ---- the runs -----------------------------------------------------------------------------------------


def _save(record: dict) -> None:
    """Keep the run in memory and in the file, and prune the screenshots of runs that are not recent."""
    with _LOCK:
        _RUNS[record["id"]] = record
        data = _read()
        slot = _slot(data, record["drone"])
        runs = [r for r in slot.get("runs") or [] if isinstance(r, dict) and r.get("id") != record["id"]]
        runs.insert(0, record)
        slot["runs"] = runs[:KEEP_RUNS]
        _write(data)
    for old in runs[KEEP_SHOTS:]:
        rid = str(old.get("id") or "")
        if rid and rid != record["id"]:
            shutil.rmtree(RUNS / "runs" / rid, ignore_errors=True)


def start_task(goal: str, url: str | None = None, model: str | None = None, max_steps: int = DEFAULT_STEPS) -> dict:
    """Put the browser drone on a task. One at a time: a second ask is refused, not queued."""
    text = str(goal or "").strip()
    if not text:
        raise ValueError("the drone needs a goal")
    if len(text) > 2000:
        raise ValueError("the goal is longer than 2000 characters")
    key = model or selected("browser")
    if key not in PILOTS or not PILOTS[key].vision:
        raise ValueError(f"{key!r} is not a browser pilot: the browser drone needs a screenshot model")
        raise ValueError(f"no pilot called {key!r}")
    if not installed(key).get("ready"):
        raise ValueError(f"{PILOTS[key].label} is not downloaded yet")
    if not _BUSY.acquire(blocking=False):
        raise ValueError("the browser drone is already flying a task; wait for it to land")
    record = {
        "id": time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3),
        "drone": "browser",
        "goal": text,
        "url": (url or "").strip() or None,
        "model": key,
        "model_label": PILOTS[key].label,
        "state": "queued",
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "finished": None,
        "steps": 0,
        "max_steps": max(1, min(int(max_steps), MAX_STEPS)),
        "answer": None,
        "error": None,
        "question": None,
        "thought": None,
        "shot": None,
        "log": [],
    }
    try:
        _save(record)
    except Exception:
        _BUSY.release()
        raise

    def work() -> None:
        try:
            record["state"] = "running"
            _save(record)
            _run_browser(record)
        except Exception as e:  # noqa: BLE001  the run's failure is the page's reading
            record["state"] = "error"
            record["error"] = f"{e.__class__.__name__}: {e}"
        finally:
            record["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _save(record)
            _BUSY.release()

    threading.Thread(target=work, name=f"drone-browser-{record['id']}", daemon=True).start()
    return record


def task(run_id: str) -> dict | None:
    with _LOCK:
        rec = _RUNS.get(run_id)
        if rec:
            return rec
    for r in _runs("browser"):
        if r.get("id") == run_id:
            return r
    return None


def wait_task(run_id: str, seconds: float = 25.0) -> dict:
    """Wait for a run to land, or return it still flying: the chat tool says which."""
    deadline = time.time() + max(0.0, float(seconds))
    while time.time() < deadline:
        rec = task(run_id)
        if rec and rec.get("state") in ("done", "needs_user", "error", "stopped"):
            return rec
        time.sleep(0.75)
    return task(run_id) or {"id": run_id, "state": "unknown"}


def run_task(goal: str, url: str | None = None, model: str | None = None, max_steps: int = DEFAULT_STEPS, wait: float = 25.0) -> dict:
    """The chat terminal's one call: start a task and wait a little for it."""
    rec = start_task(goal, url=url, model=model, max_steps=max_steps)
    return wait_task(rec["id"], wait)


def shot(run_id: str) -> tuple[bytes, str]:
    """A run's last screenshot, for the drone page. Only a file under the drone's own run folder is
    served, so a run id cannot be used to read another part of the disk."""
    rec = task(run_id)
    if not rec or not rec.get("shot"):
        raise LookupError(f"no screenshot for {run_id!r}")
    path = Path(str(rec["shot"])).resolve()
    if RUNS.resolve() not in path.parents:
        raise LookupError("that file is not a drone screenshot")
    return path.read_bytes(), "image/png"


def summary(rec: dict) -> dict:
    """A run as the chat tool reports it: the answer or the question, and how it got there."""
    out = {
        "id": rec.get("id"),
        "state": rec.get("state"),
        "model": rec.get("model_label"),
        "goal": rec.get("goal"),
        "steps": rec.get("steps"),
        "answer": rec.get("answer"),
        "question": rec.get("question"),
        "error": rec.get("error"),
    }
    log = rec.get("log") or []
    if log:
        out["did"] = [
            f"{x.get('n')}. {x.get('action')}" + (f" ({x.get('note')})" if x.get("note") else "")
            for x in log[-6:]
        ]
    if rec.get("state") in ("queued", "running"):
        out["note"] = "still flying: ask browser_task_status with this id in a moment"
    return out

