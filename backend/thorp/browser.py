"""The browser drone's signed-in Chrome (12 November, Justin: "tailor it so I can test LinkedIn, X and
Google Analytics and Search websites").

A fresh headless browser is the right default for a public page and the wrong one for LinkedIn, X or
Google Analytics: all three need the user's own session. This module owns a **dedicated Chrome profile**
at `data/browser-profile` (mode 0700) that is never the everyday profile:

- `open_site` launches Google Chrome, headed, on that profile, with remote debugging on port 9333, at the
  site's sign-in page. The user signs in by hand — no password ever passes through the drone.
- `check_site` connects over CDP, opens the site in that profile and reads the URL and title to say
  whether the profile is signed in (`true`), signed out (`false`) or cannot tell (`null`).
- `drones._run_browser` connects to the same Chrome when it is up, so a test run acts inside the
  signed-in session, in a window the user can watch.

The profile is a cookie jar: it is local, gitignored, and never returned to the browser in a payload.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from thorp import paths

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9333
CDP = f"http://127.0.0.1:{CDP_PORT}"
PROFILE = paths.data_dir() / "browser-profile"
STATE = paths.data_dir() / "browser-sites.json"
_LOCK = threading.RLock()
_PROC: subprocess.Popen | None = None

SITES: dict[str, dict] = {
    "linkedin": {
        "key": "linkedin",
        "label": "LinkedIn",
        "mark": "in",
        "tone": "linkedin",
        "url": "https://www.linkedin.com/feed/",
        "signin": "https://www.linkedin.com/login",
        "goal": "Open LinkedIn and tell me the first line of the top post in my feed.",
        "needs_login": True,
        "hint": "sign in once in the Chrome window; the drone then reads the feed with your session",
    },
    "x": {
        "key": "x",
        "label": "X",
        "mark": "X",
        "tone": "x",
        "url": "https://x.com/home",
        "signin": "https://x.com/i/flow/login",
        "goal": "Open X and tell me the text of the first post in my timeline.",
        "needs_login": True,
        "hint": "sign in once; X challenges new automated sessions, so a real profile matters",
    },
    "analytics": {
        "key": "analytics",
        "label": "Google Analytics",
        "mark": "GA",
        "tone": "analytics",
        "url": "https://analytics.google.com/",
        "signin": "https://analytics.google.com/",
        "goal": "Open Google Analytics and tell me the name of the first property and its active users in the last 7 days.",
        "needs_login": True,
        "hint": "sign in to the Google account that can see the property; the report takes a moment to load",
    },
    "search": {
        "key": "search",
        "label": "Search",
        "mark": "⌕",
        "tone": "search",
        "url": "https://duckduckgo.com/",
        "signin": "https://duckduckgo.com/",
        "goal": "Search for 'Iain M Banks Culture reading order' and tell me the top result.",
        "needs_login": False,
        "hint": "no account needed: a public search page, the control for the other three",
    },
}


def _read() -> dict:
    with _LOCK:
        if not STATE.exists():
            return {}
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}


def _write(data: dict) -> None:
    with _LOCK:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE)


def _cdp() -> dict | None:
    try:
        with urllib.request.urlopen(f"{CDP}/json/version", timeout=2) as r:
            return json.loads(r.read().decode())
    except Exception:  # noqa: BLE001
        return None


def running() -> bool:
    return _cdp() is not None


def _args(site: str | None = None) -> list[str]:
    PROFILE.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(PROFILE, 0o700)
    except OSError:
        pass
    url = SITES.get(site or "", {}).get("signin") or "about:blank"
    return [
        CHROME,
        f"--user-data-dir={PROFILE}",
        f"--remote-debugging-port={CDP_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        # the DSH/harness sandbox blocks Chrome's own sandbox and its GPU process; without these the
        # window exits at launch. The profile is dedicated to this drone and the outer sandbox still
        # bounds the process, but Chrome's renderer sandbox is off while it runs this way.
        "--no-sandbox",
        "--disable-gpu",
        "--disable-software-rasterizer",
        url,
    ]


def ensure_chrome(site: str | None = None) -> dict:
    """Start the profile's Chrome if it is not up. Headed on purpose: a person signs in here."""
    global _PROC
    if _cdp():
        return {"running": True, "started": False, "port": CDP_PORT}
    if not Path(CHROME).exists():
        raise RuntimeError("Google Chrome is not installed at /Applications/Google Chrome.app")
    _PROC = subprocess.Popen(_args(site), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 25
    while time.time() < deadline:
        if _cdp():
            return {"running": True, "started": True, "port": CDP_PORT}
        if _PROC.poll() is not None:
            raise RuntimeError("Chrome exited before its debugging port came up")
        time.sleep(0.5)
    raise RuntimeError("Chrome did not open its debugging port within 25s")


def open_site(site: str) -> dict:
    """Bring the profile's Chrome to a site's sign-in page and leave it open for the person."""
    if site not in SITES:
        raise ValueError(f"no test site called {site!r}")
    ensure_chrome(site)
    if _cdp():
        # a second launch with the same profile opens a tab; the command is the simplest reliable way
        subprocess.Popen(_args(site), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"site": site, "url": SITES[site]["signin"], "running": running()}


def _verdict(site: str, url: str, title: str, text: str) -> tuple[bool | None, str]:
    if site == "linkedin":
        if any(x in url for x in ("/login", "/checkpoint", "/authwall", "linkedin.com/signup")):
            return False, "LinkedIn is asking for a sign-in"
        if "/feed" in url or "linkedin.com/in/" in url:
            return True, "the feed is open"
        return None, "could not tell from the page"
    if site == "x":
        if any(x in url for x in ("/i/flow/login", "/login", "/i/flow/signup")):
            return False, "X is asking for a sign-in"
        if "/home" in url:
            return True, "the timeline is open"
        return None, "could not tell from the page"
    if site == "analytics":
        if "accounts.google.com" in url or "analytics.google.com/analytics/web/#/login" in url:
            return False, "Google is asking for a sign-in"
        if "analytics.google.com/analytics/web" in url:
            return True, "the Analytics home is open"
        return None, "could not tell from the page"
    if site == "search":
        return True, "no account needed"
    return None, "unknown site"


def check_site(site: str) -> dict:
    """Open the site in the profile's Chrome and say whether the session is signed in."""
    if site not in SITES:
        raise ValueError(f"no test site called {site!r}")
    ensure_chrome(site)
    from playwright.sync_api import sync_playwright

    s = SITES[site]
    checked = time.strftime("%Y-%m-%dT%H:%M:%S")
    out: dict = {"site": site, "checked": checked, "url": None, "title": None, "signed_in": None, "note": ""}
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP, no_defaults=True)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = next((p for p in context.pages if s["url"].split("/")[2] in (p.url or "")), None)
        if page is None:
            page = context.new_page()
        try:
            page.goto(s["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            info = page.evaluate(
                """() => ({url: location.href, title: document.title, text: document.body ? document.body.innerText : ''})"""
            )
            out.update({"url": info.get("url"), "title": info.get("title")})
            verdict, note = _verdict(site, str(info.get("url") or ""), str(info.get("title") or ""), str(info.get("text") or ""))
            out.update({"signed_in": verdict, "note": note})
        except Exception as e:  # noqa: BLE001
            out.update({"signed_in": False, "note": f"the page could not be read: {e.__class__.__name__}: {e}"})
    state = _read()
    state[site] = {k: out.get(k) for k in ("signed_in", "checked", "url", "title", "note")}
    _write(state)
    return out


def status() -> dict:
    state = _read()
    return {
        "chrome_running": running(),
        "profile": str(PROFILE),
        "port": CDP_PORT,
        "sites": [
            {**{k: v for k, v in s.items() if k != "signin"}, **({"state": state.get(key)} if state.get(key) else {})}
            for key, s in SITES.items()
        ],
    }


def stop() -> dict:
    """Stop the Chrome this module started. A Chrome the user opened is left alone."""
    global _PROC
    if _PROC and _PROC.poll() is None:
        _PROC.terminate()
        try:
            _PROC.wait(timeout=5)
        except Exception:  # noqa: BLE001
            _PROC.kill()
    _PROC = None
    return {"running": running()}
