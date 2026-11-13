"""The dashboard's login (thorp.dash.auth): a hashed password in s5.dash_logins, a signed cookie, and the
expeditions' and Liberty Machine's addresses answered only with that cookie."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

import pytest
from sqlalchemy import text

from thorp import store
from thorp.dash import auth


@pytest.fixture
def _login():
    auth.ITERATIONS, old = 200_000, auth.ITERATIONS  # the table's floor: fast enough for a test
    auth.set_login("test-user", "correct horse")
    yield "test-user"
    auth.ITERATIONS = old
    with store.session() as s:
        s.execute(text("delete from s5.dash_logins where username like 'test-%'"))


def test_the_password_is_checked_and_never_kept(_login):
    assert auth.check(_login, "correct horse")
    assert not auth.check(_login, "wrong horse")
    assert not auth.check("test-nobody", "correct horse")
    with store.session() as s:
        row = s.execute(text("select * from s5.dash_logins where username = :u"), {"u": _login}).mappings().one()
    assert b"correct horse" not in bytes(row["hash"]) and b"correct horse" not in bytes(row["salt"])


def test_a_cookie_is_signed_expires_and_dies_with_a_new_password(_login):
    tok = auth.token(_login)
    assert auth.user_of(tok) == _login
    name, expiry, mac = tok.rsplit(".", 2)
    assert auth.user_of(f"{name}.{int(expiry) + 1}.{mac}") is None  # a longer life is not signed
    assert auth.user_of(f"{name}.{expiry}.{'0' * len(mac)}") is None
    assert auth.user_of(tok, now=int(expiry) + 1) is None
    assert auth.user_of("rubbish") is None
    assert auth.request_user(f"other=1; {auth.COOKIE}={tok}") == _login
    auth.set_login(_login, "a new password")
    assert auth.user_of(tok) is None


def test_a_short_password_is_refused():
    with pytest.raises(ValueError):
        auth.set_login("test-short", "short")


def test_the_gated_addresses_answer_only_a_logged_in_browser(_login):
    from thorp.dash.server import Handler, _Loopback

    srv = _Loopback(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def call(path, body=None, cookie=""):
        req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers={"Cookie": cookie} if cookie else {})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"{}"), r.headers.get("Set-Cookie") or ""
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), ""

    try:
        assert call("/api/login")[1]["logged_in"] is False
        for path in ("/api/governance", "/api/queue", "/api/liberty-machine/cycle", "/api/expedition?key=kipling"):
            code, got, _ = call(path)
            assert code == 401 and got["login"] is True, path
        assert call("/api/expedition_priority", body={})[0] == 401  # the writes too
        assert call("/api/login", body={"username": _login, "password": "nope"})[0] == 401
        code, got, set_cookie = call("/api/login", body={"username": _login, "password": "correct horse"})
        assert code == 200 and got["logged_in"] and "HttpOnly" in set_cookie and "SameSite=Strict" in set_cookie
        cookie = set_cookie.split(";")[0]
        assert call("/api/login", cookie=cookie)[1] == {"logged_in": True, "username": _login, "configured": True}
        assert call("/api/governance", cookie=cookie)[0] != 401
        assert "Max-Age=0" in call("/api/logout", body={})[2]
    finally:
        srv.shutdown()
        time.sleep(0.05)
