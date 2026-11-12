"""Mailboxes for the email drone (12 November, Justin: "need to be able to configure microsoft emails,
google and protonmail here ... make it the best UX you can").

Three providers, three different ways in, because their servers genuinely differ:

- **Google** — an App Password (16 characters, with 2-Step Verification on), over IMAP and SMTP.
- **ProtonMail** — **Proton Mail Bridge**, which runs on this Mac and exposes IMAP on 1143 and SMTP on
  1025 with a Bridge-specific password. Its certificate is local and self-signed, so the test does not
  verify TLS for that provider.
- **Microsoft** — OAuth only: Microsoft removed Basic Auth for Outlook.com IMAP, so a password cannot
  work. The flow is the OAuth **device code**: a small app registration supplies the client id once, the
  page shows a code, and the user signs in at microsoft.com/devicelogin. The refresh token is kept and
  used as XOAUTH2 on IMAP and SMTP.

A connection is **tested, not assumed**: `test_account` opens IMAP, selects INBOX, counts the messages
and lists a few folders, then authenticates SMTP and sends NOOP. The result, or the exact error and a
provider-specific hint, is what the page shows.

Secrets never ride back to the browser. The accounts file holds what a page may see; the secrets file
(`data/email-secrets.json`, mode 0600) holds passwords and refresh tokens, and the API returns only
`has_secret`.
"""

from __future__ import annotations

import base64
import hashlib
import imaplib
import json
import os
import re
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from thorp import paths

ACCOUNTS = paths.data_dir() / "email-accounts.json"
SECRETS = paths.data_dir() / "email-secrets.json"
MS_TENANT = "common"
MS_SCOPES = "offline_access openid profile email https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send"
MS_DEVICE = f"https://login.microsoftonline.com/{MS_TENANT}/oauth2/v2.0/devicecode"
MS_TOKEN = f"https://login.microsoftonline.com/{MS_TENANT}/oauth2/v2.0/token"

PROVIDERS: dict[str, dict] = {
    "microsoft": {
        "key": "microsoft",
        "label": "Microsoft",
        "detail": "Outlook.com, Hotmail, Live, or a Microsoft 365 work account.",
        "auth": "oauth",
        "domains": ("outlook.com", "hotmail.com", "live.com", "msn.com", "office365.com", "onmicrosoft.com"),
        "imap": {"host": "outlook.office365.com", "port": 993, "ssl": True, "starttls": False},
        "smtp": {"host": "smtp-mail.outlook.com", "port": 587, "ssl": False, "starttls": True},
        "help": "Microsoft no longer accepts a password for IMAP. Sign in with the device code; the app "
        "registration is a one-time step.",
        "help_url": "https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade",
    },
    "google": {
        "key": "google",
        "label": "Google",
        "detail": "Gmail or Google Workspace.",
        "auth": "password",
        "domains": ("gmail.com", "googlemail.com"),
        "imap": {"host": "imap.gmail.com", "port": 993, "ssl": True, "starttls": False},
        "smtp": {"host": "smtp.gmail.com", "port": 587, "ssl": False, "starttls": True},
        "help": "Turn on 2-Step Verification, then create a 16-character App Password. Your normal Google "
        "password will not work.",
        "help_url": "https://myaccount.google.com/apppasswords",
    },
    "protonmail": {
        "key": "protonmail",
        "label": "ProtonMail",
        "detail": "Proton Mail through Proton Mail Bridge on this Mac.",
        "auth": "password",
        "domains": ("proton.me", "protonmail.com", "pm.me"),
        "imap": {"host": "127.0.0.1", "port": 1143, "ssl": False, "starttls": True, "verify": False},
        "smtp": {"host": "127.0.0.1", "port": 1025, "ssl": False, "starttls": True, "verify": False},
        "help": "Install and open Proton Mail Bridge, sign in, then copy the IMAP/SMTP credentials it "
        "shows. The password is the Bridge password, not your Proton login.",
        "help_url": "https://proton.me/mail/bridge",
    },
}

MAX_ACCOUNTS = 12


def _read(path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _write(path, data: dict, secret: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    if secret:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _accounts() -> dict:
    data = _read(ACCOUNTS)
    data.setdefault("accounts", [])
    data.setdefault("settings", {})
    return data


def _secrets() -> dict:
    return _read(SECRETS)


def _id(provider: str, email: str) -> str:
    return f"{provider}-{hashlib.sha1(email.lower().encode()).hexdigest()[:8]}"


def _public(account: dict, secrets: dict) -> dict:
    s = secrets.get(account["id"]) or {}
    return {
        **account,
        "has_secret": bool(s.get("password") or s.get("refresh_token")),
    }


def providers_payload() -> list[dict]:
    out = []
    for p in PROVIDERS.values():
        out.append({k: p[k] for k in ("key", "label", "detail", "auth", "imap", "smtp", "help", "help_url", "domains")})
    return out


def list_payload() -> dict:
    data, secrets = _accounts(), _secrets()
    accounts = [_public(a, secrets) for a in data["accounts"]]
    return {
        "providers": providers_payload(),
        "accounts": accounts,
        "microsoft": {
            "client_id": (data.get("settings") or {}).get("microsoft_client_id") or os.environ.get("THORP_MS_CLIENT_ID") or "",
            "client_id_set": bool((data.get("settings") or {}).get("microsoft_client_id") or os.environ.get("THORP_MS_CLIENT_ID")),
        },
        "tls": True,
    }


def _valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or ""))


def provider_of(email: str, fallback: str = "google") -> str:
    domain = (email.rsplit("@", 1)[-1] if "@" in email else "").lower()
    for p in PROVIDERS.values():
        if domain in p["domains"]:
            return p["key"]
    if domain.endswith(".onmicrosoft.com"):
        return "microsoft"
    return fallback


def _merge(provider: str, body: dict) -> tuple[dict, dict]:
    p = PROVIDERS[provider]
    imap = {**p["imap"], **{k: v for k, v in (body.get("imap") or {}).items() if v not in (None, "")}}
    smtp = {**p["smtp"], **{k: v for k, v in (body.get("smtp") or {}).items() if v not in (None, "")}}
    for cfg in (imap, smtp):
        cfg["port"] = int(cfg["port"])
        cfg["ssl"] = bool(cfg["ssl"])
        cfg["starttls"] = bool(cfg["starttls"])
        cfg["verify"] = bool(cfg.get("verify", True))
    return imap, smtp


def save_password(provider: str, email: str, password: str, label: str | None = None, body: dict | None = None) -> dict:
    """Add or update a Google / Proton mailbox, then test it. A failed test is kept as the account's
    status rather than thrown away: the page can show the error and the account can be retried."""
    body = body or {}
    provider = provider if provider in PROVIDERS else provider_of(email)
    if provider not in PROVIDERS:
        raise ValueError(f"no provider called {provider!r}")
    if provider == "microsoft":
        raise ValueError("Microsoft needs OAuth: use the device sign-in, not a password")
    email = str(email or "").strip()
    if not _valid_email(email):
        raise ValueError("that does not look like an email address")
    password = str(password or "")
    if provider == "google":
        password = re.sub(r"\s+", "", password)  # the 16 characters are shown in four groups
    if not password:
        raise ValueError("the app password is empty")
    imap, smtp = _merge(provider, body)
    data, secrets = _accounts(), _secrets()
    aid = _id(provider, email)
    account = next((a for a in data["accounts"] if a["id"] == aid), None)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    if account is None:
        account = {
            "id": aid, "provider": provider, "email": email, "label": label or email,
            "username": str(body.get("username") or email).strip(),
            "auth": "password", "imap": imap, "smtp": smtp, "created": now,
            "status": "new", "last_checked": None, "error": None, "detail": {},
        }  # fmt: skip
        data["accounts"].append(account)
    else:
        account.update({
            "label": label or account.get("label") or email,
            "username": str(body.get("username") or account.get("username") or email).strip(),
            "imap": imap, "smtp": smtp, "auth": "password",
        })
    secrets[aid] = {"password": password}
    account["status"] = "testing"
    _write(ACCOUNTS, data)
    _write(SECRETS, secrets, secret=True)
    tested = test_account(aid)
    return tested


def remove_account(account_id: str) -> dict:
    data, secrets = _accounts(), _secrets()
    before = len(data["accounts"])
    data["accounts"] = [a for a in data["accounts"] if a.get("id") != account_id]
    if len(data["accounts"]) == before:
        raise LookupError(f"no mailbox {account_id!r}")
    secrets.pop(account_id, None)
    _write(ACCOUNTS, data)
    _write(SECRETS, secrets, secret=True)
    return list_payload()


def _ctx(cfg: dict) -> ssl.SSLContext:
    if cfg.get("verify", True) is False:
        return ssl._create_unverified_context()  # noqa: S323 - Proton Bridge's local self-signed certificate
    return ssl.create_default_context()


def _xoauth2(email: str, token: str) -> bytes:
    return f"user={email}\x01auth=Bearer {token}\x01\x01".encode()


def _imap_open(account: dict, secret: dict) -> tuple[imaplib.IMAP4, dict]:
    cfg = account["imap"]
    ctx = _ctx(cfg)
    if cfg.get("ssl"):
        box = imaplib.IMAP4_SSL(cfg["host"], int(cfg["port"]), ssl_context=ctx, timeout=25)
    else:
        box = imaplib.IMAP4(cfg["host"], int(cfg["port"]), timeout=25)
        if cfg.get("starttls"):
            box.starttls(ssl_context=ctx)
    if account.get("auth") == "oauth":
        token = _ms_access_token(account, secret)
        box.authenticate("XOAUTH2", lambda _: _xoauth2(account["email"], token))
    else:
        box.login(account.get("username") or account["email"], secret["password"])
    return box, {"host": cfg["host"], "port": cfg["port"]}


def _smtp_send(account: dict, secret: dict) -> dict:
    cfg = account["smtp"]
    ctx = _ctx(cfg)
    smtp = smtplib.SMTP(cfg["host"], int(cfg["port"]), timeout=25)
    try:
        smtp.ehlo()
        if cfg.get("starttls"):
            smtp.starttls(context=ctx)
            smtp.ehlo()
        if account.get("auth") == "oauth":
            token = _ms_access_token(account, secret)
            code, resp = smtp.docmd("AUTH", "XOAUTH2 " + base64.b64encode(_xoauth2(account["email"], token)).decode())
            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, resp)
        else:
            smtp.login(account.get("username") or account["email"], secret["password"])
        smtp.noop()
    finally:
        try:
            smtp.quit()
        except Exception:  # noqa: BLE001
            smtp.close()
    return {"host": cfg["host"], "port": cfg["port"], "ok": True}


def _folders(box: imaplib.IMAP4) -> list[str]:
    try:
        typ, data = box.list()
        out = []
        for line in data or []:
            if not line:
                continue
            text = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
            m = re.search(r'"([^"]*)"\s*$', text)
            out.append(m.group(1) if m else text.split()[-1])
        return out[:12]
    except Exception:  # noqa: BLE001
        return []


def _hint(provider: str, exc: Exception) -> str:
    msg = f"{exc.__class__.__name__}: {exc}".lower()
    if provider == "protonmail" and ("refused" in msg or "timed out" in msg or "connect" in msg):
        return "Proton Mail Bridge is not answering on 1143/1025. Open the Bridge app and try again."
    if provider == "protonmail" and ("auth" in msg or "login" in msg):
        return "Use the Bridge password from the Bridge app, not your Proton account password."
    if provider == "google" and "lookup failed" in msg:
        return "Google could not find that address. Check the spelling, then use a 16-character App Password."
    if provider == "google" and any(x in msg for x in ("auth", "invalid credentials", "login")):
        return "Use a 16-character Google App Password (2-Step Verification must be on), not your normal password."
    if provider == "microsoft" and ("auth" in msg or "login" in msg or "xoauth" in msg):
        return "The Microsoft sign-in has expired or was not completed. Sign in again with the device code."
    if "certificate" in msg:
        return "The server's certificate was not accepted. Proton Bridge's local certificate is expected; for another host, fix its TLS."
    return ""


def test_account(account_id: str) -> dict:
    """Open IMAP and SMTP for real; keep the result on the account."""
    data, secrets = _accounts(), _secrets()
    account = next((a for a in data["accounts"] if a.get("id") == account_id), None)
    if account is None:
        raise LookupError(f"no mailbox {account_id!r}")
    secret = secrets.get(account_id) or {}
    if not (secret.get("password") or secret.get("refresh_token")):
        raise ValueError("that mailbox has no password or token yet")
    result: dict[str, Any] = {"ok": False, "checked": time.strftime("%Y-%m-%dT%H:%M:%S")}
    box = None
    try:
        box, where = _imap_open(account, secret)
        typ, _ = box.select("INBOX", readonly=True)
        if typ != "OK":
            raise imaplib.IMAP4.error("INBOX could not be selected")
        typ, found = box.search(None, "ALL")
        count = len(found[0].split()) if found and found[0] else 0
        result["imap"] = {"ok": True, **where, "messages": count, "folders": _folders(box)}
        try:
            box.logout()
        except Exception:  # noqa: BLE001
            pass
        box = None
        result["smtp"] = _smtp_send(account, secret)
        result["ok"] = True
        account["status"] = "connected"
        account["error"] = None
    except Exception as e:  # noqa: BLE001  the page shows the exact failure and a hint
        raw = e.args[0] if getattr(e, "args", None) else e
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        result["error"] = f"{e.__class__.__name__}: {raw}"
        result["hint"] = _hint(account.get("provider") or "", e)
        account["status"] = "error"
        account["error"] = result["error"]
    finally:
        if box is not None:
            try:
                box.logout()
            except Exception:  # noqa: BLE001
                pass
    account["last_checked"] = result["checked"]
    account["detail"] = {k: result.get(k) for k in ("imap", "smtp") if result.get(k)}
    for a in data["accounts"]:
        if a.get("id") == account_id:
            a.update(account)
    _write(ACCOUNTS, data)
    return {"account": _public(account, secrets), "result": result}


# ---- Microsoft device-code OAuth ----------------------------------------------------------------------


def set_ms_client(client_id: str) -> dict:
    cid = str(client_id or "").strip()
    data = _accounts()
    data.setdefault("settings", {})["microsoft_client_id"] = cid
    _write(ACCOUNTS, data)
    return list_payload()


def _ms_client() -> str:
    data = _accounts()
    cid = (data.get("settings") or {}).get("microsoft_client_id") or os.environ.get("THORP_MS_CLIENT_ID") or ""
    if not cid:
        raise ValueError("no Microsoft application (client) id yet: paste one from the app registration")
    return cid


def _ms_post(url: str, form: dict) -> dict:
    body = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:  # noqa: BLE001
            raise RuntimeError(f"Microsoft returned {e.code}") from e


def _ms_email(id_token: str) -> str:
    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return str(claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "")
    except Exception:  # noqa: BLE001
        return ""


def _ms_access_token(account: dict, secret: dict) -> str:
    token = secret.get("access_token")
    if token and float(secret.get("expires_at") or 0) > time.time() + 60:
        return token
    refresh = secret.get("refresh_token")
    if not refresh:
        raise RuntimeError("the Microsoft sign-in has no refresh token: sign in again")
    data = _ms_post(
        MS_TOKEN,
        {
            "client_id": secret.get("client_id") or _ms_client(),
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "scope": MS_SCOPES,
        },
    )
    if "access_token" not in data:
        raise RuntimeError(str(data.get("error_description") or data.get("error") or "the token refresh failed"))
    secret["access_token"] = data["access_token"]
    secret["expires_at"] = time.time() + float(data.get("expires_in") or 3600)
    if data.get("refresh_token"):
        secret["refresh_token"] = data["refresh_token"]
    secrets = _secrets()
    secrets[account["id"]] = secret
    _write(SECRETS, secrets, secret=True)
    return data["access_token"]


def ms_start(client_id: str | None = None) -> dict:
    cid = str(client_id or "").strip() or _ms_client()
    data = _ms_post(MS_DEVICE, {"client_id": cid, "scope": MS_SCOPES})
    if "device_code" not in data:
        raise RuntimeError(str(data.get("error_description") or data.get("error") or "Microsoft did not start a device sign-in"))
    return {
        "client_id": cid,
        "device_code": data["device_code"],
        "user_code": data.get("user_code"),
        "verification_uri": data.get("verification_uri"),
        "expires_in": data.get("expires_in"),
        "interval": data.get("interval") or 5,
        "message": data.get("message"),
    }


def ms_poll(device_code: str, client_id: str, email: str | None = None) -> dict:
    data = _ms_post(
        MS_TOKEN,
        {
            "client_id": client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        },
    )
    err = data.get("error")
    if err in ("authorization_pending", "slow_down"):
        return {"state": "pending", "error": None}
    if err:
        return {"state": "error", "error": data.get("error_description") or err}
    token = data.get("access_token")
    if not token:
        return {"state": "error", "error": "Microsoft returned no access token"}
    who = email or _ms_email(str(data.get("id_token") or ""))
    if not _valid_email(who):
        return {"state": "error", "error": "Microsoft signed in but did not say which address: enter it and try again"}
    accounts, secrets = _accounts(), _secrets()
    aid = _id("microsoft", who)
    account = next((a for a in accounts["accounts"] if a["id"] == aid), None)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    imap, smtp = _merge("microsoft", {})
    if account is None:
        account = {
            "id": aid, "provider": "microsoft", "email": who, "label": who, "auth": "oauth",
            "imap": imap, "smtp": smtp, "created": now, "status": "new",
            "last_checked": None, "error": None, "detail": {},
        }  # fmt: skip
        accounts["accounts"].append(account)
    else:
        account.update({"auth": "oauth", "imap": imap, "smtp": smtp})
    secrets[aid] = {
        "refresh_token": data.get("refresh_token") or (secrets.get(aid) or {}).get("refresh_token"),
        "access_token": token,
        "expires_at": time.time() + float(data.get("expires_in") or 3600),
        "client_id": client_id,
    }
    _write(ACCOUNTS, accounts)
    _write(SECRETS, secrets, secret=True)
    tested = test_account(aid)
    return {"state": "connected", **tested}


def account_options() -> dict:
    """What the drone would use: the first connected mailbox."""
    data = _accounts()
    for a in data["accounts"]:
        if a.get("status") == "connected":
            return {"account": _public(a, _secrets())}
    return {"account": None}
