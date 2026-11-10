"""Compute providers in the store (10 November): the Vast.ai key and the Vast lane's seats, so the yard's
compute is set up and inspected in one place. The key is read from `s5.provider_credentials` first, then
`VAST_API_KEY`, then the old file `data/secrets/vast-api-key`; `set_vast_key` writes the store."""

from __future__ import annotations

import os

from thorp import paths


def vast_key() -> str:
    env = os.environ.get("VAST_API_KEY")
    if env:
        return env.strip()
    try:
        from thorp import store
        from thorp.viable.records import ProviderCredential

        with store.session() as s:
            r = s.get(ProviderCredential, "vast")
            if r is not None and r.key:
                return r.key.strip()
    except Exception:  # noqa: BLE001  a box without the table falls back to the file
        pass
    p = paths.data_dir() / "secrets" / "vast-api-key"
    return p.read_text().strip() if p.exists() else ""


def set_vast_key(key: str) -> None:
    from thorp import store
    from thorp.viable.records import ProviderCredential

    with store.session() as s:
        s.merge(ProviderCredential(provider="vast", key=key.strip()))


def _lane(seats: int | None = None) -> int | None:
    from thorp import store
    from thorp.viable.records import Lane

    with store.session() as s:
        r = s.get(Lane, "vast")
        if seats is not None:
            if r is None:
                s.add(Lane(lane="vast", seats=seats))
            else:
                r.seats = seats
            return seats
        return (r.seats if r is not None and r.seats else 1)


def vast_seats() -> int:
    return _lane() or 1


def set_vast_seats(seats: int) -> int:
    return _lane(max(1, min(8, int(seats)))) or 1
