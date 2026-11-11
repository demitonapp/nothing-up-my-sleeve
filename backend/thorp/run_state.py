"""A run's state and its expedition, as rows beside its ledger row (11 November, the architecture audit's item 11:
"`s1.runs.status` holds 11 distinct strings, some of them prose; a signal leaves a run `running`", and expedition
membership is "a prefix if-chain on a free-text label").

Two side tables keyed by run id, never a column of `s1.runs` (the coordinator holds a lock on that table):

- `s1.run_state` — one of six states (`STATES`), the reason in words, and a heartbeat. Both trainers write
  `running` at the start, beat from the step loop at most once a minute of wall time (`BEAT_EVERY_S`), and write the
  final state wherever they write a final `status` (which they still write, word for word, for the readers). The
  coordinator marks a `running` run `lost` when its heartbeat is older than `LOST_AFTER_S` and nothing at sea covers
  it (`sweep`), which replaces the start-up reaper's one-hour guess for every run that has a state row.
- `s1.run_expedition` — the expedition a run belongs to, and where that came from: `spec` (the spec's own
  `expedition:` field), `label` (fleet.expedition_of_label, the old prefix chain) or `manual`. A manual row is
  never overwritten by a trainer.

A hired box writes its own SQLite ledger and no store: its state reaches home through the fold, which maps the box's
run row status onto a state in the fold's own transaction (`fold`), the simpler of the two ways item 3's provenance
could have gone (no new artifact kind for the box to write). Every write here is bookkeeping: it never raises into a
voyage, and it is only made where the ledger is the home store.
"""

from __future__ import annotations

import time

STATES = ("running", "finished", "failed", "stopped", "recalled", "lost")
BEAT_EVERY_S = 60.0  # at most one heartbeat a minute of wall time: one single-row upsert, never a step's cost
LOST_AFTER_S = 15 * 60  # a running run with no heartbeat for this long, and nothing at sea covering it, is lost
SOURCES = ("spec", "label", "manual")

_last_beat: dict[str, float] = {}


def state_of(status: str | None) -> tuple[str, str] | None:
    """The state a `s1.runs.status` string means, with the reason (the string itself). None for no status.

    The strings found in the store on 11 November: `finished`, `running`, `stopped`, `killed`, `recalled: <why>`,
    `failed: <ExceptionClass>`, `failed: stopped by hand ...` (a person stopped it: stopped, not failed), and the
    charter's `chartered: overran` (brought home at its deadline: stopped) or `chartered: failed (exit N)`. A bare
    `chartered` is the papers row a box sails under: running. Anything else is a failure, said in its own words."""
    s = str(status or "").strip()
    if not s:
        return None
    low = s.lower()
    if low in ("running", "chartered"):
        return "running", s
    if low == "finished":
        return "finished", s
    if low in ("stopped", "killed") or low.startswith(("stopped", "killed", "failed: stopped by hand")):
        return "stopped", s
    if low.startswith("recalled"):
        return "recalled", s
    if low == "lost":
        return "lost", s
    if low.startswith("chartered:"):
        rest = low.split(":", 1)[1].strip()
        if rest == "home":
            return "finished", s
        if rest.startswith("overran"):
            return "stopped", s
        return "failed", s
    return "failed", s


def _home(rec) -> bool:
    """Whether `rec` writes the home store (the same test item 3's provenance uses): a box's ledger, or a test's
    SQLite one, writes no side table."""
    try:
        from thorp.versioning import _home_store

        return _home_store(rec)
    except Exception:  # noqa: BLE001
        return False


_UPSERT = (
    "insert into s1.run_state (run_id, state, reason, heartbeat_at, updated_at) "
    "values (:r, :s, :why, case when :beat then now() end, now()) "
    "on conflict (run_id) do update set state = excluded.state, reason = excluded.reason, "
    "heartbeat_at = coalesce(excluded.heartbeat_at, s1.run_state.heartbeat_at), updated_at = now()"
)


def write(rid: str, state: str, reason: str = "", beat: bool = False, session=None) -> None:
    """Upsert a run's state (raises; the callers below do not). `session` writes inside a caller's transaction."""
    if state not in STATES:
        raise ValueError(f"no state {state!r} (have: {', '.join(STATES)})")
    from sqlalchemy import text

    params = {"r": rid, "s": state, "why": reason or "", "beat": bool(beat)}
    if session is not None:
        session.execute(text(_UPSERT), params)
        return
    from thorp import store

    with store.session() as s:
        s.execute(text("SET LOCAL lock_timeout = '5s'"))
        s.execute(text(_UPSERT), params)


def _say(log, msg: str) -> None:
    try:
        (log or print)(msg)
    except Exception:  # noqa: BLE001
        pass


def started(spec: dict, rid: str, rec, log=None) -> None:
    """At the start of a sailing (both trainers, after the run row): `running` with a first heartbeat, and the
    run's expedition. Never raises."""
    if not _home(rec):
        return
    try:
        write(rid, "running", "running", beat=True)
        _last_beat[rid] = time.monotonic()
    except Exception as e:  # noqa: BLE001  (bookkeeping never stops a voyage)
        _say(log, f"run state: not recorded ({e.__class__.__name__}: {e})")
    try:
        record_expedition(spec, rid)
    except Exception as e:  # noqa: BLE001
        _say(log, f"run expedition: not recorded ({e.__class__.__name__}: {e})")


def beat(rid: str, rec) -> None:
    """The step loop's heartbeat: one upsert at most every BEAT_EVERY_S of wall time, else nothing but a clock
    read. A beat revives a run the coordinator had marked lost (it was alive after all); it never changes a final
    state. A failed beat is not retried before the next minute. Never raises."""
    now = time.monotonic()
    if now - _last_beat.get(rid, float("-inf")) < BEAT_EVERY_S:
        return
    _last_beat[rid] = now
    if not _home(rec):
        return
    try:
        from sqlalchemy import text

        from thorp import store

        with store.session() as s:
            s.execute(text("SET LOCAL lock_timeout = '2s'"))
            s.execute(
                text(
                    "insert into s1.run_state (run_id, state, reason, heartbeat_at, updated_at) "
                    "values (:r, 'running', 'running', now(), now()) "
                    "on conflict (run_id) do update set heartbeat_at = now(), "
                    "state = case when s1.run_state.state = 'lost' then 'running' else s1.run_state.state end, "
                    "reason = case when s1.run_state.state = 'lost' then 'running (a heartbeat after it was marked lost)' "
                    "else s1.run_state.reason end"
                ),
                {"r": rid},
            )
    except Exception:  # noqa: BLE001  (a missed beat is a gap in the record, not a voyage's end)
        pass


def ended(rid: str, status: str, rec, log=None, reason: str | None = None) -> None:
    """Where a trainer writes a final `status`: the state it means, the status (or a fuller `reason`, such as the
    exception's own words) as the reason. Never raises."""
    if not _home(rec):
        return
    try:
        st = state_of(status)
        if st:
            write(rid, st[0], reason or st[1])
        _last_beat.pop(rid, None)
    except Exception as e:  # noqa: BLE001
        _say(log, f"run state: final state not recorded ({e.__class__.__name__}: {e})")


def fold(session, run_row: dict) -> None:
    """A hired box's run row, folded home (s2_coordination.charter._fold_pg, in the fold's transaction): its status
    mapped onto a state, a running one beating with the fold. In a savepoint, so a store not yet migrated, or any
    error here, never costs the fold. Never raises."""
    try:
        st = state_of(run_row.get("status"))
        if not st or not run_row.get("run_id"):
            return
        with session.begin_nested():
            write(run_row["run_id"], st[0], st[1], beat=st[0] == "running", session=session)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- the expedition a run belongs to


def expedition_and_source(spec: dict) -> tuple[str | None, str]:
    """The spec's own `expedition:` (source 'spec'), else the label chain on its name and ship (source 'label')."""
    from thorp import fleet

    e = (spec or {}).get("expedition")
    if isinstance(e, str) and e.strip():
        return e.strip(), "spec"
    return fleet.expedition_of_label((spec or {}).get("name"), (spec or {}).get("ship")), "label"


_EXP_UPSERT = (
    "insert into s1.run_expedition (run_id, expedition, source, recorded_at) values (:r, :e, :src, now()) "
    "on conflict (run_id) do update set expedition = excluded.expedition, source = excluded.source, "
    "recorded_at = now() where s1.run_expedition.source <> 'manual' or excluded.source = 'manual'"
)


def record_expedition(spec: dict, rid: str, expedition: str | None = None, source: str | None = None) -> str | None:
    """Write the run's expedition (raises). With no `expedition`, the spec says (or its label); a run that belongs
    to no expedition gets no row. A manual row is kept against a trainer's. Returns what was written."""
    if expedition is None:
        expedition, src = expedition_and_source(spec)
    else:
        src = source or "manual"
    if src not in SOURCES:
        raise ValueError(f"no source {src!r} (have: {', '.join(SOURCES)})")
    if not expedition:
        return None
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        s.execute(text("SET LOCAL lock_timeout = '5s'"))
        s.execute(text(_EXP_UPSERT), {"r": rid, "e": expedition, "src": src})
    return expedition


def backfill(conn) -> dict:
    """Once, from the migration: a state row for every run from its status (the reason its original words), and an
    expedition row for every run the label chain places (source 'label'). Writes only the two new tables, and
    never over a row already there. `conn` is a SQLAlchemy connection (the migration's)."""
    from sqlalchemy import text

    from thorp import fleet

    rows = conn.execute(text("select run_id, name, ship, status from s1.runs")).fetchall()
    states, exps = [], []
    for rid, name, ship, status in rows:
        st = state_of(status)
        if st:
            states.append({"r": rid, "s": st[0], "why": st[1]})
        e = fleet.expedition_of_label(name, ship)
        if e:
            exps.append({"r": rid, "e": e})
    if states:
        conn.execute(
            text(
                "insert into s1.run_state (run_id, state, reason, updated_at) values (:r, :s, :why, now()) "
                "on conflict (run_id) do nothing"
            ),
            states,
        )
    if exps:
        conn.execute(
            text(
                "insert into s1.run_expedition (run_id, expedition, source) values (:r, :e, 'label') "
                "on conflict (run_id) do nothing"
            ),
            exps,
        )
    return {"runs": len(rows), "states": len(states), "expeditions": len(exps)}


# ---------------------------------------------------------------- readers


def of(run_id: str) -> dict | None:
    """A run's state, reason, heartbeat and when the state was written; None when it has no row (or no store).
    The helper for S3/S4 (vsm) and the dashboard: read this rather than parsing `s1.runs.status`."""
    return of_many([run_id]).get(run_id)


def of_many(run_ids) -> dict[str, dict]:
    """`of` for many runs in one query: {run_id: {state, reason, heartbeat_at, updated_at}}. Empty without a store."""
    ids = [r for r in dict.fromkeys(run_ids) if r]
    if not ids:
        return {}
    try:
        from sqlalchemy import bindparam, text

        from thorp import store

        q = text(
            "select run_id, state, reason, heartbeat_at, updated_at from s1.run_state where run_id in :ids"
        ).bindparams(bindparam("ids", expanding=True))
        with store.session() as s:
            return {
                r[0]: {"state": r[1], "reason": r[2], "heartbeat_at": r[3], "updated_at": r[4]}
                for r in s.execute(q, {"ids": ids})
            }
    except Exception:  # noqa: BLE001
        return {}


def sweep(covered_ids: set, covered_names: set, after_s: float = LOST_AFTER_S, say=None) -> list[str]:
    """The coordinator's watch (lanes.run): every `running` state row whose run's status has moved on is brought
    into line with it; one whose heartbeat (or, with none, its state's own time) is older than `after_s` and that
    nothing covers — no live at-sea row or pid, no hired box, no live helm (`covered_ids` by run id,
    `covered_names` by run name) — is marked `lost`, and its ledger row, if still `running`, says `stopped` as the
    start-up reaper always wrote. Returns the run ids marked lost. Raises on a store error (the caller says so)."""
    from sqlalchemy import text

    from thorp import store

    lost: list[str] = []
    with store.session() as s:
        s.execute(text("SET LOCAL lock_timeout = '5s'"))
        rows = s.execute(
            text(
                "select t.run_id, r.name, r.status, "
                "extract(epoch from now() - coalesce(t.heartbeat_at, t.updated_at)) as quiet "
                "from s1.run_state t left join s1.runs r on r.run_id = t.run_id where t.state = 'running'"
            )
        ).fetchall()
        for rid, name, status, quiet in rows:
            if status is not None and str(status).strip() != "running":
                st = state_of(status)
                if st and st[0] != "running":
                    write(rid, st[0], st[1], session=s)
                continue
            if rid in covered_ids or (name and name in covered_names):
                continue
            if quiet is None or float(quiet) < after_s:
                continue
            why = (
                f"no heartbeat for {float(quiet) / 60:.0f} min and nothing at sea covers it "
                "(no live at-sea row or pid, no hired box, no helm)"
            )
            write(rid, "lost", why, session=s)
            s.execute(
                text("update s1.runs set status = 'stopped' where run_id = :r and status = 'running'"), {"r": rid}
            )
            lost.append(rid)
    if lost and say:
        say(f"S2: marked {len(lost)} run(s) lost: no heartbeat for {after_s / 60:.0f} min and nothing at sea")
    return lost
