"""thorp fetch LIST · thorp acquire LIST · thorp run SPEC · thorp eval RUN · thorp dash · thorp ledger SQL · thorp id SPEC
thorp charter quote|sail SPEC · thorp charter audit · thorp charter terms"""

from __future__ import annotations

import argparse
import sys


def cmd_acquire(a) -> int:
    """S1 of acquisition (thorp/acquisition.py): an intake, every row through the intake gate first."""
    from thorp import acquisition

    rec = acquisition.intake(a.list, set_name=a.set, limit=a.limit, dry_run=a.dry_run)
    by = ", ".join(f"{k} {n}" for k, n in rec["refused_by_rule"].items())
    print(
        f"record: s1.intakes {rec['id']}"
        + (f"; refused by rule: {by}" if by else "")
    )
    return 0


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


def cmd_charter(a) -> int:
    """A voyage on a GPU hired from Vast.ai (thorp/viable/s1_operations/charter.py), within S5's terms."""
    import json

    from thorp.viable.s5_policy import charter as s5

    if a.what == "terms":
        print(json.dumps(s5.terms(), indent=1))
        return 0
    if a.what == "audit":
        from thorp.viable.s1_operations.vast import Vast
        from thorp.viable.s3star_audit import charter as audit

        print(json.dumps(audit.audit(Vast(), release_orphans=a.release_orphans), indent=1))
        return 0
    if not a.spec:
        print(f"thorp charter {a.what} needs a spec", file=sys.stderr)
        return 2
    from thorp.viable.s1_operations import charter

    if a.what == "quote":
        q = charter.quote(a.spec, gpu=a.gpu)
        p = q["plan"]
        print(f"{p['run_id'][:12]}: {p['tokens_left']:,} tokens to sail (steps {p['start']} to {p['total_steps']}); priced on {q['market']}")
        for x in q["quotes"]:
            verdict = "keeps the terms" if not x["breaks"] else "REFUSED: " + "; ".join(x["breaks"])
            print(f"  {x['gpu']:<10} ${x['dph']:.3f}/h  {x['hours']:6.2f} h  ${x['cost']:7.2f}  ({x['speed']})  {verdict}")
        return 0
    out = charter.sail(a.spec, gpu=a.gpu)
    print(json.dumps(out, indent=1, default=str))
    return 0 if out.get("status") in ("home", "finished") else 1


def cmd_store(a) -> int:
    """The one store (Postgres): is it up, and bring data/'s files into it (thorp/store_import.py)."""
    from thorp import store

    if a.what == "ping":
        why = store.ping()
        print(why or f"the store answers ({store._safe(store.url())})")
        return 1 if why else 0
    from thorp import store_import

    store_import.run(retire=a.retire)
    return 0


def cmd_s5(a) -> int:
    """S5's decisions, recorded in the store in Justin's words: a policy switched, a charter term changed."""
    import json

    if not a.words:
        print("an S5 decision is recorded in Justin's words: --words", file=sys.stderr)
        return 2
    if a.what == "switch":
        from thorp import vsm

        if a.value not in ("on", "off"):
            print("thorp s5 switch POLICY on|off", file=sys.stderr)
            return 2
        vsm.set_switch(a.key, a.value == "on", a.words)
    else:
        from thorp.viable.s5_policy import charter as s5

        s5.set_term(a.key, json.loads(a.value), a.words)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="thorp")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fetch", help="resolve, fetch, strip and register a book list")
    s.add_argument("list")
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser(
        "acquire",
        help="an intake: a book list through the intake gate, fetched, registered, checked",
    )
    s.add_argument("list")
    s.add_argument("--set", help="the manifest set (default: from the list's name)")
    s.add_argument("--limit", type=int, help="take in at most this many rows")
    s.add_argument("--dry-run", action="store_true", help="the gate's verdicts, nothing fetched")
    s.set_defaults(fn=cmd_acquire)
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
    s = sub.add_parser("charter", help="sail a voyage on a GPU hired from Vast.ai, within the charter's terms")
    s.add_argument("what", choices=["quote", "sail", "audit", "terms"])
    s.add_argument("spec", nargs="?")
    s.add_argument("--gpu", help="hire this class only (a key of the terms' gpus, e.g. 'RTX 4090')")
    s.add_argument("--release-orphans", action="store_true", help="audit: destroy thorp instances no charter is sailing")
    s.set_defaults(fn=cmd_charter)
    s = sub.add_parser("store", help="the one store (Postgres): ping it, or import data/'s files into it")
    s.add_argument("what", choices=["ping", "import"])
    s.add_argument("--retire", action="store_true", help="import: rename each imported file *.imported (the cutover)")
    s.set_defaults(fn=cmd_store)
    s = sub.add_parser("s5", help="an S5 decision: switch a policy on or off, or change a charter term")
    s.add_argument("what", choices=["switch", "term"])
    s.add_argument("key", help="the policy, or the charter term")
    s.add_argument("value", help="switch: on|off; term: its value as JSON (40, or '{\"RTX 4090\": 0.45}')")
    s.add_argument("--words", required=True, help="Justin's words, and when")
    s.set_defaults(fn=cmd_s5)
    s = sub.add_parser("schedule", help="Thorp's own schedule (S2): tick, list, run, import-claude, enable, judge")
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=lambda a: __import__("thorp.viable.s2_coordination.schedule", fromlist=["main"]).main(a.rest))
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
