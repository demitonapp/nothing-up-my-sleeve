"""thorp fetch LIST · thorp run SPEC · thorp eval RUN · thorp dash · thorp ledger SQL · thorp id SPEC"""

from __future__ import annotations

import argparse
import sys


def cmd_fetch(a) -> int:
    from thorp.sources import gutenberg

    results = gutenberg.fetch_list(a.list)
    ok = 0
    print(f"{'#':>3}  {'id':>6}  {'how':<12} {'title':<52} result")
    for i, (res, book, err) in enumerate(results, 1):
        ok += book is not None
        result = f"{book.bytes:>9,} bytes" if book else f"MISSING: {err}"
        print(f"{i:>3}  {res.chosen or '-':>6}  {res.how:<12} {res.row.title[:52]:<52} {result}")
    print(f"\n{ok} of {len(results)} rows fetched from {a.list}; resolution in data/resolution.csv")
    return 0


def cmd_run(a) -> int:
    from thorp import train

    train.run(a.spec)
    return 0


def cmd_id(a) -> int:
    from thorp import train

    print(train.run_id(train.load_spec(a.spec)))
    return 0


def cmd_eval(a) -> int:
    from thorp import train

    try:
        train.rescore(a.run, sets=a.sets, evaluators=a.evaluators)
    except LookupError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_dash(a) -> int:
    from thorp.dash import server

    server.serve(a.port)
    return 0


def cmd_ledger(a) -> int:
    from thorp.ledger import Ledger

    rec = Ledger()
    params = list(a.params)
    n = a.sql.count("?")
    if n and not params:
        run = (
            a.run
            or (
                rec.query(
                    "select run_id from runs order by (status='finished') desc, started desc limit 1"
                )
                or [{"run_id": None}]
            )[0]["run_id"]
        )
        params = [run] * n
    rows = rec.query(a.sql, params)
    if not rows:
        print("(no rows)")
        return 0
    cols = list(rows[0])
    fmt = lambda v: f"{v:.4f}" if isinstance(v, float) else str(v)  # noqa: E731
    widths = [max(len(c), *(len(fmt(r[c])) for r in rows)) for c in cols]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths, strict=True)))
    for r in rows:
        print("  ".join(fmt(r[c]).ljust(w) for c, w in zip(cols, widths, strict=True)))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="thorp")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fetch", help="resolve, fetch, strip and register a book list")
    s.add_argument("list")
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("run", help="train (or resume, or report) the run a spec describes")
    s.add_argument("spec")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("id", help="print the run id of a spec")
    s.add_argument("spec")
    s.set_defaults(fn=cmd_id)
    s = sub.add_parser("eval", help="re-run the evaluators on a run's latest checkpoint")
    s.add_argument("run", help="run id or prefix")
    s.add_argument("--sets", nargs="+", help="score these lists instead of the spec's eval.sets")
    s.add_argument("--evaluators", nargs="+", help="run these evaluators instead of the spec's")
    s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("dash", help="serve the dashboard on http://localhost:8787")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=cmd_dash)
    s = sub.add_parser("ledger", help="query the ledger; each ? defaults to the latest run id")
    s.add_argument("sql")
    s.add_argument("params", nargs="*")
    s.add_argument("--run", help="run id to bind to each ? when no params are given")
    s.set_defaults(fn=cmd_ledger)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
