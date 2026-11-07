"""Fitouts in Postgres, with their prechecks (2026-11-07, Justin: "these cleanup tasks should be in a data model
in postgres that represent how a fitout can have precheck items ... and then let's set sail").

The database is Thorp's own local cluster (`data/postgres`, outside git: the ledger swap of 18:11 is why), on
`localhost:5433`, database `thorp` (override with THORP_PG). Started with:

    LC_ALL=en_US.UTF-8 /opt/homebrew/opt/postgresql@17/bin/pg_ctl -D data/postgres -l data/postgres.log \\
        -o "-p 5433 -k /tmp -c listen_addresses=localhost" start

The model, in schema `fitout`:

- **fitouts**: a fitout (a named plan of what a voyage reads), its cleaning version, tokeniser and status.
- **stages**: its stages in order (pretraining, post-training), each a library, an amount and passes.
- **precheck_items**: the catalogue of checks a fitout can be held to: what is measured, the pass rule, which
  system of the VSM owns it (S3 control for the library and the gate's rules, S2 for the tokeniser that every
  class shares, S5 for the cleaning standard), and whether it belongs to a cleaning version.
- **fitout_prechecks**: which items a fitout must pass (required) or carries as planned (not yet required).
- **precheck_results**: every reading of an item for a fitout, kept (the latest is the current one).
- **readiness** (a view): per fitout, its required items, how many pass now, and whether it may sail.

The S3 gate (thorp/vsm.py, policy 'prechecks') refuses a voyage whose fitout is not ready.
"""

from __future__ import annotations

import json
import os

DEFAULT_URL = "postgresql://thorp@localhost:5433/thorp"

SCHEMA = """
create schema if not exists fitout;

create table if not exists fitout.fitouts (
    key           text primary key,
    name          text not null,
    aim           text not null default '',
    clean         text not null,               -- the cleaning version its books are read with
    tokeniser     jsonb not null default '{}', -- kind, vocab, byte_fallback, train_on
    positions     text not null default 'rope',
    status        text not null default 'draft' check (status in ('draft', 'ready', 'sailing', 'home')),
    adopted       text not null default '',    -- who adopted it, when
    created_at    timestamptz not null default now()
);

create table if not exists fitout.stages (
    fitout_key    text not null references fitout.fitouts(key) on delete cascade,
    ordinal       int  not null,
    phase         text not null check (phase in ('pretraining', 'post-training')),
    name          text not null,
    library       text not null,               -- a list in lists/
    tokens        bigint,                      -- null: the whole library
    selection     text not null default 'all',
    passes        int  not null default 1,
    lr            double precision,
    tack          jsonb,
    purpose       text not null default '',
    primary key (fitout_key, ordinal)
);

create table if not exists fitout.precheck_items (
    key           text primary key,            -- e.g. clean.quotes, library.period
    name          text not null,
    about         text not null,               -- what it checks and why
    system        text not null check (system in ('S1', 'S2', 'S3', 'S3*', 'S4', 'S5')),
    kind          text not null check (kind in ('cleaning', 'library', 'tokeniser', 'policy')),
    measure       text not null,               -- what the value is
    comparator    text not null check (comparator in ('=', '<=', '>=')),
    threshold     double precision not null,
    clean_version text                         -- the cleaning version the item belongs to, if any
);

create table if not exists fitout.fitout_prechecks (
    fitout_key    text not null references fitout.fitouts(key) on delete cascade,
    item_key      text not null references fitout.precheck_items(key),
    required      boolean not null default true, -- false: planned, shown, not yet a condition of sailing
    note          text not null default '',
    primary key (fitout_key, item_key)
);

create table if not exists fitout.precheck_results (
    id            bigserial primary key,
    fitout_key    text not null references fitout.fitouts(key) on delete cascade,
    item_key      text not null references fitout.precheck_items(key),
    value         double precision,
    passed        boolean not null,
    evidence      jsonb not null default '{}',
    checked_at    timestamptz not null default now(),
    checked_by    text not null default ''
);
create index if not exists precheck_results_latest
    on fitout.precheck_results (fitout_key, item_key, checked_at desc);

create or replace view fitout.current_results as
    select distinct on (fitout_key, item_key) *
    from fitout.precheck_results
    order by fitout_key, item_key, checked_at desc, id desc;

create or replace view fitout.readiness as
    select f.key as fitout_key,
           count(*) filter (where fp.required)                              as required,
           count(*) filter (where fp.required and r.passed)                 as passed,
           count(*) filter (where fp.required and r.passed is distinct from true) as outstanding,
           count(*) filter (where not fp.required)                          as planned,
           coalesce(bool_and(r.passed) filter (where fp.required), false)
             and count(*) filter (where fp.required) > 0                    as ready
    from fitout.fitouts f
    join fitout.fitout_prechecks fp on fp.fitout_key = f.key
    left join fitout.current_results r on r.fitout_key = fp.fitout_key and r.item_key = fp.item_key
    group by f.key;
"""


def url() -> str:
    return os.environ.get("THORP_PG", DEFAULT_URL)


def connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(url(), row_factory=dict_row, autocommit=True)


def migrate() -> None:
    with connect() as c:
        c.execute(SCHEMA)


def put_fitout(f: dict, adopted: str = "") -> None:
    """A fitout (the saved form, thorp/fitouts.py) and its stages, written or replaced."""
    with connect() as c, c.transaction():
        c.execute(
            """insert into fitout.fitouts (key, name, aim, clean, tokeniser, positions, adopted)
               values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (key) do update set name = excluded.name, aim = excluded.aim,
                 clean = excluded.clean, tokeniser = excluded.tokeniser, positions = excluded.positions,
                 adopted = case when excluded.adopted = '' then fitout.fitouts.adopted else excluded.adopted end""",
            [
                f["key"], f["name"], f.get("aim") or "", f["clean"], json.dumps(f.get("tokeniser") or {}),
                f.get("positions") or "rope", adopted,
            ],
        )  # fmt: skip
        c.execute("delete from fitout.stages where fitout_key = %s", [f["key"]])
        for i, s in enumerate(f.get("stages") or [], 1):
            c.execute(
                """insert into fitout.stages (fitout_key, ordinal, phase, name, library, tokens, selection,
                     passes, lr, tack, purpose) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [
                    f["key"], i, s["phase"], s["name"], s["shelf"], s.get("tokens"), s.get("select") or "all",
                    s.get("passes") or 1, s.get("lr"), json.dumps(s["tack"]) if s.get("tack") else None,
                    s.get("purpose") or "",
                ],
            )  # fmt: skip


def put_items(items) -> None:
    with connect() as c, c.transaction():
        for it in items:
            c.execute(
                """insert into fitout.precheck_items (key, name, about, system, kind, measure, comparator,
                     threshold, clean_version) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   on conflict (key) do update set name = excluded.name, about = excluded.about,
                     system = excluded.system, kind = excluded.kind, measure = excluded.measure,
                     comparator = excluded.comparator, threshold = excluded.threshold,
                     clean_version = excluded.clean_version""",
                [it.key, it.name, it.about, it.system, it.kind, it.measure, it.comparator, it.threshold,
                 it.clean_version],
            )  # fmt: skip


def require(fitout_key: str, item_key: str, required: bool = True, note: str = "") -> None:
    with connect() as c:
        c.execute(
            """insert into fitout.fitout_prechecks (fitout_key, item_key, required, note) values (%s,%s,%s,%s)
               on conflict (fitout_key, item_key) do update set required = excluded.required, note = excluded.note""",
            [fitout_key, item_key, required, note],
        )


def record(fitout_key: str, item_key: str, value, passed: bool, evidence: dict, by: str) -> None:
    with connect() as c:
        c.execute(
            """insert into fitout.precheck_results (fitout_key, item_key, value, passed, evidence, checked_by)
               values (%s,%s,%s,%s,%s,%s)""",
            [fitout_key, item_key, value, passed, json.dumps(evidence, default=str), by],
        )


def readiness(fitout_key: str) -> dict | None:
    with connect() as c:
        return c.execute("select * from fitout.readiness where fitout_key = %s", [fitout_key]).fetchone()


def checklist(fitout_key: str) -> list[dict]:
    """The fitout's prechecks with each one's current reading, for the gate and the dashboard."""
    with connect() as c:
        return c.execute(
            """select fp.item_key, fp.required, fp.note, i.name, i.about, i.system, i.kind, i.measure,
                      i.comparator, i.threshold, r.value, r.passed, r.evidence, r.checked_at
               from fitout.fitout_prechecks fp
               join fitout.precheck_items i on i.key = fp.item_key
               left join fitout.current_results r
                 on r.fitout_key = fp.fitout_key and r.item_key = fp.item_key
               where fp.fitout_key = %s
               order by fp.required desc, i.kind, fp.item_key""",
            [fitout_key],
        ).fetchall()


def set_status(fitout_key: str, status: str) -> None:
    with connect() as c:
        c.execute("update fitout.fitouts set status = %s where key = %s", [status, fitout_key])
