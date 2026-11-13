r"""S5: proposals waiting on Justin (13 November, Justin: "push all feedback to the liberty machine", then "S5
proposals, new table"). A Claude session, a system of the Liberty Machine or a person files a proposal: what is
asked, why, and the decision it needs. It stands open on the S5 page until Justin signs it, declines it, or the
one who filed it withdraws it; the words he gives are kept with it. Nothing here acts on a proposal: signing one
is a record of the decision, and the work it asks for is done (and recorded in DECISIONS.md) apart.

These are not the planning cycle's proposals (s3.cycles.proposals), which each turn of the cycle writes for itself
and which are a record of that turn; these stand until decided.

The table is `s5.proposals` (migration a8c0e2f4b6d9, which holds its rules too: a filer, a title and a question that are
not blank, a decided time on a decided proposal and none on an open one, and a trigger that refuses to change a decided
proposal). `check` and `next_state` below say the same things in words for a caller; the database is what refuses.

    uv run thorp proposals list [--all]
    uv run thorp proposals add --by "session: public edition" --area "public launch" --title "..." --asks "..." [--why "..."]
    uv run thorp proposals sign 3 --words "Justin's words"
    uv run thorp proposals decline 3 --words "..."
    uv run thorp proposals withdraw 3 --words "..."
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from thorp import store

STATES = ("open", "signed", "declined", "withdrawn")
# a decision moves an open proposal to one of these; a decided one is never reopened (file a new one instead)
DECISIONS = {"sign": "signed", "decline": "declined", "withdraw": "withdrawn"}


_COLS = "id, filed_at, filed_by, area, title, asks, why, status, decided_at, words"


def check(*, filed_by: str, title: str, asks: str) -> dict:
    """A new proposal's fields, trimmed; raises ValueError for one that cannot be decided (no filer, no title, or
    nothing asked: a proposal that asks nothing cannot be signed)."""
    out = {"filed_by": (filed_by or "").strip(), "title": (title or "").strip(), "asks": (asks or "").strip()}
    for k, v in out.items():
        if not v:
            raise ValueError(f"a proposal needs {k.replace('_', ' ')}")
    return out


def next_state(current: str, decision: str) -> str:
    """The state a decision moves a proposal to; raises ValueError for an unknown decision or a proposal already
    decided."""
    if decision not in DECISIONS:
        raise ValueError(f"no such decision {decision!r}: {', '.join(DECISIONS)}")
    if current != "open":
        raise ValueError(f"the proposal is already {current}")
    return DECISIONS[decision]


def ensure() -> None:
    """The table is Alembic's (migrations a8c0e2f4b6d9, which also holds its rules): no runtime DDL (S5 policy 'postgres',
    13 November). Kept so the callers read as they did; it has nothing to do."""


def add(*, filed_by: str, title: str, asks: str, area: str = "", why: str = "") -> dict:
    """File one proposal; returns it."""
    row = check(filed_by=filed_by, title=title, asks=asks)
    ensure()
    with store.session() as s:
        got = s.execute(
            text(f"insert into s5.proposals (filed_by, area, title, asks, why) values (:by, :area, :title, :asks, :why) returning {_COLS}"),
            {"by": row["filed_by"], "area": (area or "").strip(), "title": row["title"], "asks": row["asks"], "why": (why or "").strip()},
        ).one()
        return dict(got._mapping)


def rows(status: str | None = "open", limit: int = 200) -> list[dict]:
    """The proposals, newest first; the open ones by default, every one with status=None."""
    if status is not None and status not in STATES:
        raise ValueError(f"no such state {status!r}")
    ensure()
    where = "where status = :status" if status else ""
    with store.session() as s:
        got = s.execute(
            text(f"select {_COLS} from s5.proposals {where} order by filed_at desc, id desc limit :limit"),
            {"status": status, "limit": max(1, min(int(limit), 1000))},
        ).all()
    return [dict(r._mapping) for r in got]


def decide(pid: int, decision: str, words: str = "") -> dict:
    """Sign, decline or withdraw one open proposal, keeping the words given; returns it."""
    ensure()
    with store.session() as s:
        cur = s.execute(text("select status from s5.proposals where id = :id for update"), {"id": int(pid)}).scalar()
        if cur is None:
            raise ValueError(f"no proposal {pid}")
        state = next_state(cur, decision)
        got = s.execute(
            text(f"update s5.proposals set status = :state, decided_at = now(), words = :words where id = :id returning {_COLS}"),
            {"state": state, "words": (words or "").strip(), "id": int(pid)},
        ).one()
        return dict(got._mapping)


def _print(r: dict) -> None:
    when = r["filed_at"].strftime("%Y-%m-%d %H:%M") if r.get("filed_at") else ""
    print(f"#{r['id']}  [{r['status']}]  {when}  {r['filed_by']}" + (f"  · {r['area']}" if r["area"] else ""))
    print(f"    {r['title']}")
    print(f"    asks: {r['asks']}")
    if r.get("words"):
        print(f"    words: {r['words']}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="thorp proposals", description="S5: proposals waiting on Justin")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list", help="the open proposals (or every one with --all)")
    s.add_argument("--all", action="store_true")
    s = sub.add_parser("add", help="file a proposal")
    s.add_argument("--by", required=True, help="who files it: 'session: <name>', 'S4', 'Justin'")
    s.add_argument("--title", required=True)
    s.add_argument("--asks", required=True, help="the decision it needs, as a question")
    s.add_argument("--area", default="")
    s.add_argument("--why", default="")
    for name in DECISIONS:
        s = sub.add_parser(name, help=f"{name} an open proposal")
        s.add_argument("id", type=int)
        s.add_argument("--words", default="", help="the words given with the decision")
    a = p.parse_args(argv)
    try:
        if a.cmd == "list":
            got = rows(None if a.all else "open")
            for r in got:
                _print(r)
            if not got:
                print("no open proposals" if not a.all else "no proposals")
        elif a.cmd == "add":
            _print(add(filed_by=a.by, title=a.title, asks=a.asks, area=a.area, why=a.why))
        else:
            _print(decide(a.id, a.cmd, a.words))
    except ValueError as e:
        print(f"thorp proposals: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
