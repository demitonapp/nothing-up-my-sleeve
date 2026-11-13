"""The dashboard's login (13 November, Justin: "this page http://localhost:4321/orbitals/demiton should not show
expeditions and liberty machine unless i'm logged in. Happy using a username and password for now").

A username and password, set from the terminal (`thorp login set`), kept in `s5.dash_logins` as a PBKDF2-SHA256 hash
(migration c3e5a7b9d1f4). Logging in gives a signed cookie, `thorp_login`, good for 30 days: `username.expiry.mac`,
the mac an HMAC-SHA256 under that login's own secret. Nothing is kept per session, so a restart of `thorp dash` keeps
everyone logged in, and setting a new password (a new secret) logs every browser out.

`GATED` is the list of API addresses that answer 401 without the cookie: the expeditions' own and the Liberty
Machine's. `/api/expeditions` and `/api/expeditions/overview` are not on it, because the ship and class pages read
them too.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import secrets
import sys
import time
from http.cookies import SimpleCookie

from sqlalchemy import text

from thorp import store

COOKIE = "thorp_login"
MAX_AGE = 30 * 24 * 3600
ITERATIONS = 600_000

# The addresses only a logged-in browser is answered on (GET and POST alike).
GATED: frozenset[str] = frozenset(
    {
        # the expeditions: one expedition, its plan and what is at sea, the queue, the charter and its signing
        "/api/expedition",
        "/api/expedition_plan",
        "/api/expedition_priority",
        "/api/observation",
        "/api/at_sea",
        "/api/queue",
        "/api/launch",
        "/api/charter/sign",
        # the Liberty Machine: the five systems, the cycle, S5's feedback, the checkpoints, acquisition and its audit
        "/api/governance",
        "/api/liberty-machine/cycle",
        "/api/liberty-machine/feedback",
        "/api/liberty-machine/checkpoints",
        "/api/vsm/cycle",
        "/api/acquisition",
        "/api/acquisition/audit",
    }
)


def _hash(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)


def _row(username: str) -> dict | None:
    with store.session() as s:
        r = s.execute(
            text("select username, salt, hash, iterations, secret from s5.dash_logins where username = :u"),
            {"u": username},
        ).mappings().first()
    return dict(r) if r else None


def configured() -> bool:
    """True once a login has been set: until then the page says how to set one."""
    with store.session() as s:
        return bool(s.execute(text("select exists (select 1 from s5.dash_logins)")).scalar())


def set_login(username: str, password: str) -> None:
    """Make or replace a login. A new secret too, so every cookie signed for this username stops working."""
    if len(password) < 8:
        raise ValueError("a password of at least 8 characters")
    salt = secrets.token_bytes(16)
    with store.session() as s:
        s.execute(
            text(
                "insert into s5.dash_logins (username, salt, hash, iterations, secret) values (:u, :salt, :hash, :it, :secret) "
                "on conflict (username) do update set salt = excluded.salt, hash = excluded.hash, "
                "iterations = excluded.iterations, secret = excluded.secret, set_at = now()"
            ),
            {"u": username, "salt": salt, "hash": _hash(password, salt, ITERATIONS), "it": ITERATIONS, "secret": secrets.token_bytes(32)},
        )


def remove_login(username: str) -> bool:
    with store.session() as s:
        return bool(s.execute(text("delete from s5.dash_logins where username = :u"), {"u": username}).rowcount)


def check(username: str, password: str) -> bool:
    r = _row(username)
    if not r:
        _hash(password, b"\0" * 16, ITERATIONS)  # the same work for an unknown name, so the time says nothing
        return False
    return hmac.compare_digest(_hash(password, bytes(r["salt"]), r["iterations"]), bytes(r["hash"]))


def _mac(secret: bytes, username: str, expiry: int) -> str:
    return hmac.new(secret, f"{username}.{expiry}".encode(), hashlib.sha256).hexdigest()


def token(username: str, now: float | None = None) -> str:
    r = _row(username)
    if not r:
        raise LookupError(f"no login called {username}")
    expiry = int((now or time.time()) + MAX_AGE)
    return f"{username}.{expiry}.{_mac(bytes(r['secret']), username, expiry)}"


def user_of(tok: str, now: float | None = None) -> str | None:
    """The username a cookie value was signed for, or None if it is forged, expired or its login is gone."""
    try:
        username, expiry_s, mac = tok.rsplit(".", 2)
        expiry = int(expiry_s)
    except ValueError:
        return None
    if expiry < (now or time.time()):
        return None
    r = _row(username)
    if not r or not hmac.compare_digest(mac, _mac(bytes(r["secret"]), username, expiry)):
        return None
    return username


def cookie_value(header: str | None) -> str:
    if not header:
        return ""
    c = SimpleCookie()
    try:
        c.load(header)
    except Exception:  # noqa: BLE001  (a malformed Cookie header is no login)
        return ""
    m = c.get(COOKIE)
    return m.value if m else ""


def request_user(cookie_header: str | None) -> str | None:
    tok = cookie_value(cookie_header)
    return user_of(tok) if tok else None


def set_cookie(tok: str) -> str:
    return f"{COOKIE}={tok}; Path=/; Max-Age={MAX_AGE}; HttpOnly; SameSite=Strict"


def clear_cookie() -> str:
    return f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict"


def main(argv: list[str]) -> int:
    """`thorp login set [username]` asks for the password twice; `thorp login remove <username>`; `thorp login list`."""
    p = argparse.ArgumentParser(prog="thorp login", description="the dashboard's login")
    sub = p.add_subparsers(dest="what", required=True)
    s = sub.add_parser("set", help="set or replace a login (asks for the password)")
    s.add_argument("username", nargs="?", default="justin")
    s = sub.add_parser("remove", help="remove a login")
    s.add_argument("username")
    sub.add_parser("list", help="the usernames that can log in")
    a = p.parse_args(argv)
    if a.what == "set":
        pw = getpass.getpass(f"password for {a.username}: ")
        if pw != getpass.getpass("again: "):
            print("the two passwords differ; nothing changed", file=sys.stderr)
            return 1
        try:
            set_login(a.username, pw)
        except ValueError as e:
            print(f"needs {e}; nothing changed", file=sys.stderr)
            return 1
        print(f"{a.username} can log in; any browser logged in as {a.username} before is logged out")
        return 0
    if a.what == "remove":
        print("removed" if remove_login(a.username) else f"no login called {a.username}")
        return 0
    with store.session() as s:
        rows = s.execute(text("select username, set_at from s5.dash_logins order by username")).all()
    for u, at in rows:
        print(f"{u}  set {at:%Y-%m-%d %H:%M}")
    if not rows:
        print("no logins yet: thorp login set")
    return 0
