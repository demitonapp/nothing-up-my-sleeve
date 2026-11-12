"""The phone drone's local test line (12 November, Justin: "local test only").

The phone drone does not dial a real number. A **local test call** is a conversation on this Mac:
the person on the other end is typed at a keyboard (the page's box, or `phone_say` from the chat
terminal), the pilot answers from a text GGUF, and the answer is spoken aloud with macOS `say`.
That is enough to develop the listen-think-speak loop — the turn taking, the short spoken turns, the
opening and the close — without a carrier, a microphone permission or a real number.

What is deliberately absent:
- no PSTN number, no SIP, no Twilio: the line is `local`, and any digit string is refused before it is
  dialled;
- no microphone and no Whisper yet: the ears are the keyboard, and the page says so. Whisper is the next
  step once the loop is trusted;
- no recording: the transcript is text, kept with the call, and the drone says it is an AI at the start.

The bridge is `drones.PHONE_BRIDGE`; this module is the call itself. `data/phone-calls.json` holds the
last calls, so a page refresh (or a restart) still shows what was said.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time

from thorp import drones, paths

CALLS = paths.data_dir() / "phone-calls.json"
_LOCK = threading.RLock()
_CALLS: dict[str, dict] = {}
_ACTIVE: str | None = None
_SPEAKING: subprocess.Popen | None = None
MAX_CALLS = 12
MAX_TURNS = 40
MAX_SPOKEN = 600  # a spoken turn longer than this is cut: the line is speech, not an essay

OPENING = (
    "Hello, this is the phone drone from Nothing up my sleeve. I am an AI assistant, and this is a local "
    "test line. {goal} How can I help?"
)
CLOSING = "Thank you, goodbye."

SYSTEM = """\
You are the phone drone of Nothing up my sleeve, on a local test call. You are speaking aloud, so every
turn is one or two short sentences: plain speech, no lists, no markdown, no headings. You are an AI and
you said so at the start of the call; if asked again, say it plainly.

The task for this call: {goal}

The person on the other end is played by the operator at a keyboard. Answer what they say, ask at most one
question at a time, and when the task is done or they say goodbye, close the call warmly in one sentence."""


def _read() -> dict:
    with _LOCK:
        if not CALLS.exists():
            return {}
        try:
            data = json.loads(CALLS.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}


def _write() -> None:
    with _LOCK:
        CALLS.parent.mkdir(parents=True, exist_ok=True)
        tmp = CALLS.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"calls": list(_CALLS.values())[:MAX_CALLS]}, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(CALLS)


def _load() -> None:
    """Read the calls kept from an earlier dashboard, and retire one the restart cut off."""
    global _ACTIVE
    with _LOCK:
        if _CALLS:
            return
        for c in _read().get("calls") or []:
            if not isinstance(c, dict) or not c.get("id"):
                continue
            if c.get("state") in ("open", "thinking"):
                c["state"] = "error"
                c["error"] = "the dashboard restarted while the call was open"
                c["finished"] = c.get("finished") or time.strftime("%Y-%m-%dT%H:%M:%S")
            _CALLS[c["id"]] = c
        _ACTIVE = next((k for k, c in _CALLS.items() if c.get("state") in ("open", "thinking")), None)


def _clean(text: str, limit: int = MAX_SPOKEN) -> str:
    s = " ".join(str(text or "").split())
    if len(s) <= limit:
        return s
    cut = s[:limit]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _speak(text: str) -> bool:
    """The mouth: macOS `say`. Non-blocking, one voice at a time. A machine without `say` stays silent
    and the transcript is the record."""
    global _SPEAKING
    if not shutil.which("say"):
        return False
    line = _clean(text)
    if not line:
        return False
    if _SPEAKING and _SPEAKING.poll() is None:
        _SPEAKING.terminate()
    cmd = ["say", "-r", os.environ.get("THORP_PHONE_RATE", "185")]
    voice = os.environ.get("THORP_PHONE_VOICE")
    if voice:
        cmd += ["-v", voice]
    cmd.append(line)
    try:
        _SPEAKING = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:  # noqa: BLE001
        return False


def _turn(call: dict, role: str, text: str) -> dict:
    return {"role": role, "text": _clean(text), "at": time.strftime("%H:%M:%S")}


def _messages(call: dict) -> list[dict]:
    out = [{"role": "system", "content": SYSTEM.format(goal=call["goal"])}]
    for t in call.get("transcript") or []:
        out.append({"role": "assistant" if t.get("role") == "drone" else "user", "content": t.get("text") or ""})
    return out


def _call(call_id: str) -> dict | None:
    with _LOCK:
        return _CALLS.get(call_id)


def start(goal: str, pilot: str | None = None, speak: bool = True) -> dict:
    """Open a local test call. The opening is fixed (and spoken at once); the pilot is loaded on the
    first thing the person says, so the page answers immediately."""
    global _ACTIVE
    _load()
    text = " ".join(str(goal or "").split())
    if not text:
        raise ValueError("the call needs a reason: what should the drone ask or settle?")
    if len(text) > 600:
        raise ValueError("the call's reason is longer than 600 characters")
    key = pilot or drones.selected("phone")
    p = drones.PILOTS.get(key)
    if p is None or p.vision:
        raise ValueError(f"{key!r} is not a phone pilot: the phone drone needs a text model")
    if not drones.installed(key).get("ready"):
        raise ValueError(f"{p.label} is not downloaded yet")
    with _LOCK:
        if _ACTIVE and (_CALLS.get(_ACTIVE) or {}).get("state") in ("open", "thinking"):
            raise ValueError("a test call is already open; end it before starting another")
        cid = "call-" + time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
        call = {
            "id": cid,
            "state": "open",
            "goal": text,
            "pilot": key,
            "pilot_label": p.label,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "finished": None,
            "error": None,
            "speak": bool(speak),
            "spoken": False,
            "transcript": [],
        }
        call["transcript"].append(_turn(call, "drone", OPENING.format(goal=text)))
        _CALLS[cid] = call
        _ACTIVE = cid
        _write()
    call["spoken"] = bool(speak) and _speak(call["transcript"][0]["text"])
    return call


def say(call_id: str, text: str) -> dict:
    """The person's turn: the pilot answers, and the answer is spoken."""
    from thorp import drones as d

    _load()
    line = " ".join(str(text or "").split())
    if not line:
        raise ValueError("nothing was said")
    call = _call(call_id)
    if call is None:
        raise LookupError(f"no test call {call_id!r}")
    if call.get("state") not in ("open", "thinking"):
        raise ValueError(f"the call is {call.get('state')}, not open")
    if len(call.get("transcript") or []) >= MAX_TURNS:
        call["state"] = "error"
        call["error"] = f"the call reached {MAX_TURNS} turns"
        _write()
        raise ValueError(call["error"])
    with _LOCK:
        call["transcript"].append(_turn(call, "person", line))
        call["state"] = "thinking"
        _write()
    try:
        server = d._ensure_server(call["pilot"])
        reply = d._chat(server["port"], _messages(call), max_tokens=220, thinking=False)
        if not reply:
            reply = "Sorry, I did not catch that. Could you say it again?"
    except Exception as e:  # noqa: BLE001  the call says what failed and stays open for another try
        with _LOCK:
            call["state"] = "open"
            call["error"] = f"{e.__class__.__name__}: {e}"
            _write()
        raise
    with _LOCK:
        call["transcript"].append(_turn(call, "drone", reply))
        call["state"] = "open"
        call["error"] = None
        _write()
    call["spoken"] = bool(call.get("speak")) and _speak(reply)
    return call


def end(call_id: str) -> dict:
    """Hang up: a spoken goodbye, the call closed and the transcript kept."""
    global _ACTIVE
    _load()
    call = _call(call_id)
    if call is None:
        raise LookupError(f"no test call {call_id!r}")
    with _LOCK:
        if call.get("state") in ("open", "thinking"):
            call["transcript"].append(_turn(call, "drone", CLOSING))
            call["state"] = "done"
            call["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if _ACTIVE == call_id:
                _ACTIVE = None
            _write()
    if call.get("speak"):
        _speak(CLOSING)
    return call


def call(call_id: str) -> dict | None:
    _load()
    return _call(call_id)


def payload() -> dict:
    """The phone page's reading: the open call, the calls kept, the bridge and whether the mouth works."""
    _load()
    with _LOCK:
        calls = sorted(_CALLS.values(), key=lambda c: str(c.get("started") or ""), reverse=True)
        active = next((c for c in calls if c.get("state") in ("open", "thinking")), None)
    from thorp import drones as d

    return {
        "active": active,
        "calls": calls[:MAX_CALLS],
        "bridge": d.PHONE_BRIDGE,
        "tts": bool(shutil.which("say")),
        "pilot_ready": bool(d.installed(d.selected("phone")).get("ready")),
    }


def summary(c: dict) -> dict:
    """A call as the chat tool reports it."""
    spoken = [t for t in c.get("transcript") or [] if t.get("role") == "drone"]
    return {
        "id": c.get("id"),
        "state": c.get("state"),
        "goal": c.get("goal"),
        "pilot": c.get("pilot_label"),
        "turns": len(c.get("transcript") or []),
        "last_reply": (spoken[-1] or {}).get("text") if spoken else None,
        "transcript": (c.get("transcript") or [])[-8:],
        "error": c.get("error"),
        "note": "the drone is on a local test line: the person speaks through phone_say, and phone_end hangs up",
    }
