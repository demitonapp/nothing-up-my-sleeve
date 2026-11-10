"""The yard's identity (10 November): who ran a voyage, so a result can be accepted from a yard that is not
this one. The id is derived from the machine (host, architecture, home), so it is stable across restarts and
does not need to be configured; `ensure()` registers it in `s1.yards` with the compute it describes."""

from __future__ import annotations

import hashlib
import os
import platform

_ID: str | None = None


def current() -> str:
    """This yard's id, stable for this machine and user."""
    global _ID
    if _ID is None:
        raw = f"{platform.node()}|{platform.machine()}|{os.path.expanduser('~')}"
        _ID = "yard-" + hashlib.sha1(raw.encode()).hexdigest()[:12]
    return _ID


def ensure(owner: str | None = None) -> str:
    """Register this yard (idempotent) and return its id."""
    from thorp import store
    from thorp.viable.records import Yard

    yid = current()
    with store.session() as s:
        if s.get(Yard, yid) is None:
            s.add(Yard(
                yard_id=yid,
                owner=owner or os.environ.get("USER") or "owner",
                compute={"host": platform.node(), "machine": platform.machine(),
                         "python": platform.python_version(), "seats": 1},
            ))
    return yid
