"""thorp fetch LIST · thorp acquire LIST · thorp gather SOURCE · thorp run SPEC · thorp eval RUN · thorp dash
thorp ledger SQL · thorp id SPEC · thorp charter quote|sail SPEC · thorp charter audit · thorp charter terms"""

from __future__ import annotations

import argparse
import sys


def cmd_acquire(a) -> int:
    """S1 of acquisition (thorp/acquisition.py): an intake, every row through the intake gate first."""
    from thorp import acquisition

    rec = acquisition.intake(a.list, set_name=a.set, limit=a.limit, dry_run=a.dry_run)
    by = ", ".join(f"{k} {n}" for k, n in rec["refused_by_rule"].items())
    print(f"record: s1.intakes {rec['id']}" + (f"; refused by rule: {by}" if by else ""))
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


def cmd_gather(a) -> int:
    """S1 of acquisition over a bulk source (thorp/gather.py): every record through the intake gate."""
    from thorp import gather

    if a.list:
        rows = gather.status()
        print(f"{'source':<26} {'status':<32} {'books here':>10} {'tokens':>10}  adapter")
        for r in rows:
            lib, status = r["in_library"], r["status"][:32]
            print(f"{r['key']:<26} {status:<32} {lib['books']:>10,} {lib['tokens']:>10,}  "
                  f"{'yes' if r['adapter_ready'] else '—'}")  # fmt: skip
        return 0
    if a.plan:
        for r in gather.plan(a.plan):
            est = f"{r['sample_tokens_est']:,}" if r["sample_tokens_est"] else "—"
            lo, hi = r["after_rule_tokens"] or [0, 0]
            print(f"{r['key']:<26} {r['books']:>9,} books  {lo / 1e9:.1f}–{hi / 1e9:.1f}B  "
                  f"a {r['sample_records']}-record pilot ≈ {est} tokens")  # fmt: skip
            print(f"  {r['how']}")
        return 0
    rec = gather.run(
        a.source,
        limit=a.limit,
        offset=a.offset,
        dry_run=a.dry_run,
        allow_unsigned=a.allow_unsigned,
        authority=a.authority,
        collection=a.collection,
        year=a.year,
        path=a.path,
        metadata=a.metadata,
        language=a.language,
        set_name=a.set_name,
    )
    if a.export_list:
        n = gather.export_list(a.source, a.export_list)
        print(f"wrote {n} rows to {a.export_list}")
    by = ", ".join(f"{k} {n}" for k, n in rec["refused_by_rule"].items())
    print(f"record: s1.intakes {rec['id']}" + (f"; refused by rule: {by}" if by else ""))
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
        print(
            f"{p['run_id'][:12]}: {p['tokens_left']:,} tokens to sail (steps {p['start']} to {p['total_steps']}); priced on {q['market']}"
        )
        for x in q["quotes"]:
            verdict = "keeps the terms" if not x["breaks"] else "REFUSED: " + "; ".join(x["breaks"])
            print(
                f"  {x['gpu']:<10} ${x['dph']:.3f}/h  {x['hours']:6.2f} h  ${x['cost']:7.2f}  ({x['speed']})  {verdict}"
            )
        return 0
    out = charter.sail(a.spec, gpu=a.gpu)
    print(json.dumps(out, indent=1, default=str))
    return 0 if out.get("status") in ("home", "finished") else 1


def cmd_store(a) -> int:
    """The one store (Postgres): is it up, bring data/'s files into it, or backfill the ledger (thorp/store_import.py)."""
    from thorp import store

    if a.what == "ping":
        why = store.ping()
        print(why or f"the store answers ({store._safe(store.url())})")
        return 1 if why else 0
    if a.what == "ledger":
        from thorp import ledger_store

        counts = ledger_store.backfill()
        print(f"ledger: copied {counts}")
        ok = ledger_store.verify()
        print("ledger: verified, counts match" if ok else "ledger: MISMATCH — see the lines above")
        return 0 if ok else 1
    if a.what == "queue":
        from thorp.viable.s2_coordination import queue_store

        counts = queue_store.backfill()
        print(f"queue: copied {counts}")
        ok = queue_store.verify()
        print("queue: verified, counts match" if ok else "queue: MISMATCH — see the lines above")
        return 0 if ok else 1
    from thorp import store_import

    store_import.run(retire=a.retire)
    return 0


def cmd_s5(a) -> int:
    """S5's decisions, recorded in the store in Justin's words: a policy switched, a charter term changed, or the
    runs a policy does not govern (an exception, with its reason)."""
    import json
    from pathlib import Path

    if not a.words:
        print("an S5 decision is recorded in Justin's words: --words", file=sys.stderr)
        return 2
    if a.what == "switch":
        from thorp import vsm

        if a.value not in ("on", "off"):
            print("thorp s5 switch POLICY on|off", file=sys.stderr)
            return 2
        vsm.set_switch(a.key, a.value == "on", a.words)
    elif a.what == "except":
        from thorp import vsm

        if not a.reason:
            print("an exception says why: --reason", file=sys.stderr)
            return 2
        val, runs, patterns = a.value, (), ()
        if val.startswith("@"):
            runs = tuple(json.loads(Path(val[1:]).read_text()))
        elif any(ch in val for ch in "*?["):
            patterns = (val,)
        else:
            runs = (val,)
        n = vsm.except_policy(a.key, reason=a.reason, adopted=a.words, runs=runs, patterns=patterns)
        print(f"S5: '{a.key}' does not govern {n} match(es)")
    else:
        from thorp.viable.s5_policy import charter as s5

        s5.set_term(a.key, json.loads(a.value), a.words)
    return 0


def cmd_version(a) -> int:
    """A plan's version (thorp/versioning.py, s1.run_versions): the journey, the content, the parameters."""
    from pathlib import Path

    import yaml

    from thorp import versioning

    if a.list:
        rows = versioning.rows()
        if not rows:
            print("no versions assigned yet")
            return 0
        print(f"{'version':<9}{'journey':<22}{'last run':<14}{'created':<12}spec")
        for r in rows:
            print(f"{r['version']:<9}{r['journey'][:20]:<22}{r['last_run']:<14}{r['created']:<12}{r['first_spec']}")
        return 0
    if not a.spec:
        print("thorp version SPEC [--assign]", file=sys.stderr)
        return 2
    spec = yaml.safe_load(Path(a.spec).read_text())
    d = versioning.describe(spec)
    have = versioning.of(spec)
    print(f"{Path(a.spec).name}: journey {(' > '.join(d['journey']))}, content {d['content']}, params {d['params']}")
    print(f"version: {have or '(new plan)'}")
    if a.assign and not have:
        print(f"assigned: {versioning.assign(spec, spec_path=a.spec)}")
    return 0


def cmd_sop(a) -> int:
    """The SOP as data (thorp/sop.py, s5.sop_versions): the standards, one by one, and a spec's standing against one."""
    import json
    from pathlib import Path

    import yaml

    from thorp import sop

    if a.what == "seed":
        print(f"seeded {sop.seed()} version(s): {', '.join(sop.versions())}")
        return 0
    if a.what == "list":
        for v in sop.versions():
            std = sop.standard(v) or {}
            print(f"v{v:<8} {str(std.get('adopted', ''))[:40]:<42} {len(std.get('cards') or [])} cards"
                  f"  {len(std.get('phases') or [])} phases  {std.get('doc', '')}")
        return 0
    if a.what == "show":
        v = a.target or sop.CURRENT
        std = sop.standard(v)
        if std is None:
            print(f"no SOP v{v}; have: {', '.join(sop.versions())}", file=sys.stderr)
            return 2
        print(json.dumps(std, indent=1))
        return 0
    if a.what == "check":
        if not a.target:
            print("thorp sop check SPEC", file=sys.stderr)
            return 2
        spec = yaml.safe_load(Path(a.target).read_text())
        found = sop.check(spec)
        state = "conforms" if not found else "does not conform"
        print(f"{spec.get('name')}: SOP v{spec.get('sop') or '(none)'} — {state}")
        for f in found:
            print(f"  - {f}")
        return 0 if not found else 1
    return 1


def cmd_select(a) -> int:
    """The library's facts and the fitouts' declared selections (thorp/library_facts.py, thorp/selection.py)."""
    from thorp import library_facts as lf

    if a.what == "facts":
        from thorp.viable.s3_control import fitout_store

        rows = lf.build()
        fp = lf.fingerprint(rows)
        if not a.dry_run:
            fitout_store.migrate()
            fitout_store.put_facts(rows, fp)
        print(
            f"{len(rows)} books, facts {fp}{' (not stored: --dry-run)' if a.dry_run else ', stored in s3.library_facts'}"
        )
        return 0
    if a.what == "branches":
        from thorp import library_branches
        from thorp.viable.s3_control import fitout_store

        fitout_store.migrate()
        nb, nv = fitout_store.seed_branches(library_branches.DEFAULTS)
        print(f"{nb} branches and {nv} variations written (any already there are left as they are)")
        return 0
    if a.what == "counts":
        rows = [r for r in lf.build() if r["source"] != "local"]
        for key in ("language", "source", "voice", "kind", "year_basis"):
            b, w = lf.count(rows, key), lf.count(rows, key, "words")
            print(f"by {key}: " + ", ".join(f"{k} {b[k]} ({w[k] / 1e6:.1f}M)" for k in b))
        by_dec: dict[str, list] = {}
        for r in rows:
            by_dec.setdefault(lf.decade(r["year"]), []).append(r["words"])
        print(
            "by period: "
            + ", ".join(f"{k} {len(v)} ({sum(v) / 1e6:.1f}M)" for k, v in sorted(by_dec.items()))
        )
        return 0
    if not a.target:
        print(f"thorp select {a.what} needs a fitout key or a selection file", file=sys.stderr)
        return 2
    from thorp.viable.s3_control import compose

    r = compose.run(
        a.target,
        stage=a.stage,
        out=a.out,
        against=a.against or "",
        dry=a.dry_run,
        by="thorp select compose",
    )
    return 0 if r["passed"] or a.dry_run else 1


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
    s = sub.add_parser(
        "gather",
        help="S1 over a bulk corpus (Common Pile, the British Library, newspapers, an IA collection)",
    )
    s.add_argument("source", nargs="?", help="a source key from `thorp gather --list`")
    s.add_argument(
        "--list",
        action="store_true",
        help="the catalogue: what each source is and whether it is fetchable",
    )
    s.add_argument(
        "--plan",
        type=int,
        metavar="N",
        help="a pilot of N records per fetchable source, and its token estimate",
    )
    s.add_argument("--limit", type=int, help="read at most this many records (not books admitted)")
    s.add_argument("--offset", type=int, default=0, help="skip this many records (a second pass)")
    s.add_argument("--dry-run", action="store_true", help="the gate's verdicts, nothing written")
    s.add_argument(
        "--allow-unsigned",
        action="store_true",
        help="newspapers: the proposed 'signed' rule is not adopted",
    )
    s.add_argument(
        "--authority",
        action="store_true",
        help="fill an undated author's life dates from Wikidata (cached)",
    )
    s.add_argument(
        "--collection", default="", help="archive: the collection to harvest (e.g. americana)"
    )
    s.add_argument("--year", type=int, help="americanstories: one year's tar.gz (e.g. 1770)")
    s.add_argument(
        "--language", default="", help="a bulk source's language filter (e.g. cdli: sux)"
    )
    s.add_argument("--path", default="", help="folder: the directory of licensed texts")
    s.add_argument(
        "--metadata",
        default="",
        help="folder: its metadata CSV (file,title,author,language,year,origin)",
    )
    s.add_argument(
        "--set",
        dest="set_name",
        default="recipe",
        help="the manifest set (default recipe; incunabula for pre-1501)",
    )
    s.add_argument(
        "--export-list",
        default="",
        help="after the gather, write its books as a list at this path",
    )
    s.set_defaults(fn=cmd_gather)
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
    s = sub.add_parser(
        "charter", help="sail a voyage on a GPU hired from Vast.ai, within the charter's terms"
    )
    s.add_argument("what", choices=["quote", "sail", "audit", "terms"])
    s.add_argument("spec", nargs="?")
    s.add_argument("--gpu", help="hire this class only (a key of the terms' gpus, e.g. 'RTX 4090')")
    s.add_argument(
        "--release-orphans",
        action="store_true",
        help="audit: destroy thorp instances no charter is sailing",
    )
    s.set_defaults(fn=cmd_charter)
    s = sub.add_parser(
        "store", help="the one store (Postgres): ping it, import data/'s files, or backfill the ledger"
    )
    s.add_argument("what", choices=["ping", "import", "ledger", "queue"])
    s.add_argument(
        "--retire",
        action="store_true",
        help="import: rename each imported file *.imported (the cutover)",
    )
    s.set_defaults(fn=cmd_store)
    s = sub.add_parser(
        "s5",
        help="an S5 decision: switch a policy on or off, change a charter term, or except runs",
    )
    s.add_argument("what", choices=["switch", "term", "except"])
    s.add_argument("key", help="the policy, or the charter term")
    s.add_argument(
        "value", help="switch: on|off; term: its value as JSON (40, or '{\"RTX 4090\": 0.45}')"
    )
    s.add_argument("--words", required=True, help="Justin's words, and when")
    s.add_argument(
        "--reason",
        default="",
        help="except: why the policy does not govern these runs; value is a run's name, a glob, or @file.json (a list)",
    )
    s.set_defaults(fn=cmd_s5)
    s = sub.add_parser(
        "select",
        help="the library's facts (counts), and a fitout's books composed from its declared selection",
    )
    s.add_argument("what", choices=["facts", "counts", "compose", "branches"])
    s.add_argument(
        "target", nargs="?", help="compose: a saved fitout's key, or a selection file (.json)"
    )
    s.add_argument("--stage", type=int, default=1, help="compose: the fitout's stage (default 1)")
    s.add_argument(
        "--out", help="compose: the list to write (default lists/composed/<fitout>-<stage>.csv)"
    )
    s.add_argument("--against", help="compose: a list to set the result beside, and print the diff")
    s.add_argument(
        "--dry-run",
        action="store_true",
        help="facts: do not store; compose: write and record nothing",
    )
    s.set_defaults(fn=cmd_select)
    s = sub.add_parser(
        "schedule", help="Thorp's own schedule (S2): tick, list, run, import-claude, enable, judge"
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s2_coordination.schedule", fromlist=["main"]).main(
            a.rest
        )
    )
    s = sub.add_parser(
        "version", help="a plan's version, 1.2.3 (journey, content, parameters): show one, assign one"
    )
    s.add_argument("spec", nargs="?", help="a spec path (or --list for the register)")
    s.add_argument("--assign", action="store_true", help="assign a version if the plan is new")
    s.add_argument("--list", action="store_true", help="the register: every version, its plan and last run")
    s.set_defaults(fn=cmd_version)
    s = sub.add_parser(
        "sop", help="the SOP as data: list versions, show one, check a spec against it"
    )
    s.add_argument("what", choices=["list", "show", "check", "seed"])
    s.add_argument("target", nargs="?", help="show: a version (default the current); check: a spec path")
    s.set_defaults(fn=cmd_sop)
    s = sub.add_parser(
        "backlog", help="S4's backlog: what may sail while a decision waits (seed, audit, rank)"
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s4_intelligence.backlog", fromlist=["main"]).main(
            a.rest
        )
    )
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
