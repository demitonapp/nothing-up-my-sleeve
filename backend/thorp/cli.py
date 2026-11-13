"""thorp fetch LIST · thorp acquire LIST · thorp gather SOURCE · thorp run SPEC · thorp eval RUN · thorp dash
thorp ledger SQL · thorp id SPEC · thorp charter quote|sail SPEC · thorp charter attach RUN · thorp charter audit · thorp charter terms"""

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


def cmd_images(a) -> int:
    from thorp import images

    if a.action == "candidates":
        for row in images.candidates(a.illustrator, a.limit):
            print(f"{row['Text#']:>6}  {row['Title'].splitlines()[0][:60]:<60}  {', '.join(images._illustrators(row['Authors']))}")
        return 0
    if a.action == "gather":
        got = images.gather(a.ids, a.illustrator, a.limit, a.per_book)
        print(f"gathered {len(got)} images into {images.images_dir()}")
        return 0
    if a.action == "prune":
        gone = images.prune()
        print(f"pruned {len(gone)}: {', '.join(r['path'] for r in gone) or 'nothing'}")
        return 0
    s = images.summary()
    print(f"{s['images']} images from {s['books']} books, {s['bytes'] / 1e6:.1f} MB")
    for b in s["by_book"]:
        print(f"{b['images']:>4}  {b['book']:>6}  {b['title'].splitlines()[0][:60]}  ({', '.join(b['illustrators'])})")
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

    return train.exit_code(train.run(a.spec))  # 143 when a signal stopped it at a checkpoint (item 10), else 0


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


def cmd_score(a) -> int:
    """Score a run's saved steps offline: what its eval.offline deferred, or --evaluators (train.score)."""
    from thorp import train

    steps = a.steps if a.steps in ("all", "pending") else ",".join(str(int(x)) for x in a.steps.split(",") if x)
    names = [n for x in a.evaluators or [] for n in x.split(",") if n] or None
    try:
        done = train.score(a.run, steps=steps, evaluators=names, keep_snapshots=a.keep_snapshots)
    except LookupError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"scored {len(done)} step(s): {', '.join(map(str, done)) or 'none'}")
    return 0


def cmd_measure(a) -> int:
    """Backfill the quantum ladder on every Ogden/Kipling voyage (thorp/ladder.py)."""
    import json

    from thorp import ladder
    from thorp.ledger import reader

    final = ladder.final_bet_data()
    unmeasured = [k for k, v in final.items() if v != "present"]
    if unmeasured:
        print(f"final quantum bets without a question file: {', '.join(unmeasured)}")
    rows = reader().query("select run_id, name, ship, status, spec_json from runs order by started")
    todo = []
    for r in rows:
        try:
            spec = json.loads(r["spec_json"] or "{}")
        except ValueError:
            continue
        spec.setdefault("name", r["name"])
        spec.setdefault("ship", r["ship"])
        if not ladder.is_ladder_voyage(spec):
            continue
        want = list(a.evaluators) if a.evaluators else (list(ladder.LADDER_EVALUATORS) if a.all else ladder.missing(spec))
        if not want:
            continue
        todo.append((r, spec, want))
    print(f"{len(todo)} Ogden/Kipling run(s) need measuring" + (" (dry run)" if a.dry_run else ""))
    done = 0
    legacy = 0
    ran = 0
    for r, spec, want in todo[: (a.limit or len(todo))]:
        ok, why = ladder.compatible_with_preset(spec, r["run_id"])
        if not ok and not a.include_legacy:
            legacy += 1
            print(f"{r['name']} [{r['status']}] skipped: {why}")
            continue
        ran += 1
        print(f"{r['name']} [{r['status']}] -> {', '.join(want)}")
        if a.dry_run:
            continue
        try:
            from thorp import train

            step = train.rescore(r["run_id"], evaluators=want)
            print(f"  scored at step {step}")
            done += 1
        except Exception as e:  # noqa: BLE001 - one bad voyage must not stop the fleet
            print(f"  skipped: {e}")
    print(f"measured {done} of {ran}" + (f"; skipped {legacy} legacy checkpoint(s)" if legacy else ""))
    return 0 if done == ran or a.dry_run else 1


def cmd_dash(a) -> int:
    from thorp.dash import server

    server.serve(a.port)
    return 0


def cmd_onboard(a) -> int:
    """The first run: serve the setup page on loopback and open the default browser."""
    import socket

    from thorp.dash import server

    if a.reset:
        from thorp.onboard import state

        state.reset(archive=True)
        print("onboarding: reset (the old answers were archived beside data/onboarding.json)")
    port = a.port
    if port <= 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    else:
        # a dashboard already on 8787 must not stop setup: take the next free port
        for candidate in range(port, port + 40):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", candidate)) != 0:
                    port = candidate
                    break
        else:
            print(f"no free port near {a.port}", file=sys.stderr)
            return 2
    try:
        server.serve(port, onboard=True, open_browser=not a.no_browser)
    except OSError as e:
        print(f"thorp onboard could not listen on 127.0.0.1:{port}: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_ledger(a) -> int:
    from thorp.ledger import reader

    rec = reader()
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
        what = "a run id, an instance id or a voyage's name" if a.what == "attach" else "a spec"
        print(f"thorp charter {a.what} needs {what}", file=sys.stderr)
        return 2
    from thorp.viable.s1_operations import charter

    if a.what == "attach":
        # a ship still hired whose charter died: take up its polling, pulls and release (11 November)
        try:
            out = charter.attach(a.spec)
        except charter.NotAttachable as e:
            print(f"thorp charter attach: {e}", file=sys.stderr)
            return 2
        except charter.Recalled as e:
            print(f"thorp charter attach: recalled by {e}; its log says how the release went", file=sys.stderr)
            return 143
        print(json.dumps(out, indent=1, default=str))
        return 0 if out.get("status") == "home" else 1
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
    try:
        out = charter.sail(a.spec, gpu=a.gpu)
    except charter.Recalled as e:  # SIGTERM or SIGHUP with a ship hired: the charter's clean-up ran
        print(f"thorp charter sail: recalled by {e}; its log says how the release went", file=sys.stderr)
        return 143
    print(json.dumps(out, indent=1, default=str))
    return 0 if out.get("status") in ("home", "finished") else 1


def cmd_store(a) -> int:
    """The one store (Postgres): is it up, create the local cluster, bring data's files into it, or backfill the ledger (thorp/store_import.py)."""
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
    if a.what == "latest":
        # s1.metric_latest from the whole history (11 November, the audit's item 7): its triggers keep it after
        # this; re-running is safe (a stored row is replaced only by a newer one, or when its row is gone)
        from thorp import ledger_store

        counts = ledger_store.backfill_latest()
        print(f"metric_latest: {counts}")
        return 0
    if a.what == "discoveries":
        from thorp import discoveries_store
        from thorp.dash import server

        document = server._discoveries_compute("")
        runs = len({x["run_id"] for star in document.get("stars", []) for x in star.get("ships", [])})
        discoveries_store.put(document, runs=runs)
        print(f"discoveries: built and stored in s1.discoveries ({runs} runs)")
        return 0
    if a.what == "setup":
        from thorp.onboard import store_setup

        try:
            out = store_setup.setup_local()
        except store_setup.SetupError as e:
            print(f"thorp store setup: {e}", file=sys.stderr)
            return 1
        print(f"the store is ready at {out['url']} (schema {out.get('schema') or 'unknown'})")
        return 0
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


def _said(a) -> str | None:
    """Who asked for a queue edit (S5 policy 'queue', 13 November): Justin, in his words (--said), else whoever
    THORP_QUEUE_BY names; the queue store refuses anyone else."""
    said = (getattr(a, "said", None) or "").strip()
    return f"justin: {said}" if said else None


def cmd_queue(a) -> int:
    """The standing queue in the store (thorp/viable/s2_coordination/queue_store.py): the lines, and the edits. An
    edit without the coordinator or Justin's words is refused (S5 policy 'queue'), said plainly, exit 3."""
    from thorp.viable.s2_coordination import queue_store

    try:
        return _cmd_queue(a, queue_store)
    except queue_store.QueueEditRefused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3


def _cmd_queue(a, queue_store) -> int:

    if a.what == "show":
        rows = queue_store.lines()
        for i, r in enumerate(rows, 1):
            goal = f"  [{r['goal_id']}]" if r.get("goal_id") else ""
            print(f"{i:>3}  {r['text']}{goal}")
        print(f"{len(rows)} line(s)")
        return 0
    if a.what == "add":
        if not a.line:
            print("thorp queue add LINE [--top] [--goal GOAL_ID]", file=sys.stderr)
            return 2
        line = a.line
        if line.startswith("investigations/"):
            # an investigation is queued by name; its spec is checked now and its line is the command
            # the coordinator already knows how to sail (thorp/investigate.py)
            from thorp import investigate

            line = investigate.queue_line(line)
        queue_store.add(line, top=a.top, goal_id=a.goal, by=_said(a))
        queue_store.export()
        print(f"queued: {line}")
        return 0
    if a.what == "goal":
        if not a.line or not a.goal:
            print("thorp queue goal LINE --goal GOAL_ID", file=sys.stderr)
            return 2
        ok = queue_store.set_goal(a.line, a.goal, by=_said(a))
        print(f"{a.line}: serves {a.goal}" if ok else f"not queued: {a.line}")
        return 0 if ok else 1
    if a.what == "move":
        if not a.line or a.to is None:
            print("thorp queue move LINE TO", file=sys.stderr)
            return 2
        queue_store.move(a.line, a.to, by=_said(a))
        queue_store.export()
        print(f"moved: {a.line} -> {a.to}")
        return 0
    if a.what == "release":
        line = queue_store.release(a.line, by=_said(a))
        if line is None:
            print("no hold to release" + (f" named {a.line!r}" if a.line else ""), file=sys.stderr)
            return 1
        queue_store.export()
        print(f"released: {line}")
        return 0
    if a.what == "drop":
        if not a.line:
            print("thorp queue drop LINE", file=sys.stderr)
            return 2
        ok = queue_store.drop(a.line, by=_said(a))
        queue_store.export()
        print(("dropped: " if ok else "not queued: ") + a.line)
        return 0 if ok else 1
    return 2


def cmd_goals(a) -> int:
    """An expedition's goals as rows in the store (thorp/expedition_goals.py): show them, add or edit one, or
    record a verdict. The numbered goals are the store's (13 November): `thorp goals add` writes them there;
    `thorp goals sync` registers the code's expeditions and never touches a goal the store holds."""
    from thorp import expedition_goals

    if a.what == "sync":
        print(f"goals: synced {expedition_goals.sync()}")
        return 0
    if a.what == "add":
        if not a.goal_id or not a.text:
            print("thorp goals add EXPEDITION --text WORDS [--detail TEXT] [--why TEXT] [--position N]", file=sys.stderr)
            return 2
        try:
            expedition_goals.sync()  # a new expedition in fleet.py is registered first
            print(expedition_goals.add(a.goal_id, a.text, a.detail or "", a.why or "", a.position))
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0
    if a.what == "edit":
        if not a.goal_id or not any(x is not None for x in (a.text, a.detail, a.why)):
            print("thorp goals edit GOAL_ID [--text WORDS] [--detail TEXT] [--why TEXT]", file=sys.stderr)
            return 2
        if not expedition_goals.edit(a.goal_id, a.text, a.detail, a.why):
            print(f"no goal {a.goal_id!r}", file=sys.stderr)
            return 1
        print(f"{a.goal_id}: edited")
        return 0
    if a.what == "remove":
        if not a.goal_id:
            print("thorp goals remove GOAL_ID", file=sys.stderr)
            return 2
        try:
            gone = expedition_goals.remove(a.goal_id)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        print(f"{a.goal_id}: removed" if gone else f"no goal {a.goal_id!r}")
        return 0 if gone else 1
    if a.what in ("model", "link", "unlink"):
        from thorp import outside_models

        try:
            if a.what == "model":
                if not (a.goal_id and a.lab and a.name):
                    print("thorp goals model HF_ID --lab KEY --name NAME [--params N] [--url URL]", file=sys.stderr)
                    return 2
                print(outside_models.add_model(a.goal_id, a.lab, a.name, a.params, a.url or ""))
            elif a.what == "link":
                if not (a.goal_id and a.model and a.role):
                    print("thorp goals link GOAL_ID --model HF_ID --role beat|compare|study [--note TEXT]", file=sys.stderr)
                    return 2
                outside_models.link(a.goal_id, a.model, a.role, a.note or "")
                print(f"{a.goal_id} -{a.role}-> {a.model}")
            else:
                if not (a.goal_id and a.model):
                    print("thorp goals unlink GOAL_ID --model HF_ID [--role R]", file=sys.stderr)
                    return 2
                print(f"unlinked {outside_models.unlink(a.goal_id, a.model, a.role)}")
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        return 0
    if a.what == "check":
        from thorp import launch, priorities
        from thorp.viable.s2_coordination import queue_store

        queued = {r["goal_id"] for r in queue_store.lines() if r.get("goal_id")}
        missing = {
            "the charter's parts": expedition_goals.dangling(launch.PARTS),
            "the priority order": expedition_goals.dangling(priorities.stored()),
            "queued lines": expedition_goals.dangling(queued),
        }  # fmt: skip
        bad = {k: v for k, v in missing.items() if v}
        for k, v in bad.items():
            print(f"{k} point at goals the store does not hold: {', '.join(v)}")
        print("goals: every reference resolves" if not bad else "goals: dangling references above")
        return 1 if bad else 0
    if a.what == "set":
        if not a.goal_id or not a.status:
            print("thorp goals set GOAL_ID STATUS [--evidence TEXT] [--words TEXT]", file=sys.stderr)
            return 2
        try:
            ok = expedition_goals.set_verdict(
                a.goal_id, a.status, evidence=a.evidence or "", words=a.words or ""
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        if not ok:
            print(f"no goal {a.goal_id!r}", file=sys.stderr)
            return 1
        print(f"{a.goal_id}: {a.status}")
        return 0
    # show (the default)
    rows = expedition_goals.read(a.expedition)
    if not rows:
        print("no goals; thorp goals add writes one", file=sys.stderr)
        return 1
    key = None
    for r in rows:
        if r["expedition_key"] != key:
            key = r["expedition_key"]
            open_n = sum(
                1 for x in rows if x["expedition_key"] == key and x["status"] in ("open", "partly")
            )
            print(f"\n{key}  ({r['name']})  {open_n} open")
        mark = {"done": "x", "dropped": "-", "partly": "~", "open": " "}.get(r["status"], " ")
        print(f"  [{mark}] {r['goal_id']:<20} {r['text'][:90]}")
        if a.verbose and r["evidence"]:
            print(f"        evidence: {r['evidence']}")
    print()
    retired = expedition_goals.retireable()
    print(f"{len(retired)} expedition(s) with every goal settled: "
          + (", ".join(x["key"] for x in retired) if retired else "none"))
    return 0


def cmd_checkpoints(a) -> int:
    """`thorp checkpoints prune <run>`: a run's checkpoints that retention would delete (train.prune_checkpoints,
    11 November, the audit's item 10), printed; deleted only with --apply. The newest, every multiple of
    --keep-every, a step a waiting voyage seeds from and a step whose deferred evaluators are unscored are kept.
    A run still at sea is refused: its own loop prunes it, when its spec asks."""
    from thorp import train

    row = train.reader().find_run(a.run)
    if not row:
        print(f"no run {a.run!r}", file=sys.stderr)
        return 1
    rid, status = row["run_id"], str(row.get("status") or "")
    if status == "running":
        print(f"{rid[:12]} is running: prune a voyage once it is home", file=sys.stderr)
        return 2
    apply = a.apply and not a.dry_run
    keep_last, keep_every = max(1, a.keep_last), max(0, a.keep_every)
    steps = train.checkpoint_steps(rid)
    doomed = train.prune_checkpoints(rid, keep_last, keep_every, apply=apply, name=row.get("name"))
    kept = len(steps) - len(doomed)
    size = sum(f.stat().st_size for d in doomed if d.exists() for f in d.rglob("*") if f.is_file()) if not apply else 0
    for d in doomed:
        print(("deleted " if apply else "would delete ") + str(d))
    verb = "deleted" if apply else f"would delete ({size / 1e9:.2f} GB)"
    print(f"{rid[:12]} ({row.get('name') or ''}): {len(steps)} checkpoints, {kept} kept, {len(doomed)} {verb}"
          + ("" if apply else "; --apply to delete"))  # fmt: skip
    return 0


def cmd_milestones(a) -> int:
    """A voyage's milestones as the ledger recorded them (thorp/milestones.py): each one's step, its value
    and whether it was met. A missed one with `if_missed: recall` is why a voyage came back early."""
    from sqlalchemy import text

    from thorp import ledger_store, store

    if a.run:
        row = ledger_store.find_run(a.run)
        if not row:
            print(f"no run {a.run!r}", file=sys.stderr)
            return 1
        rid, name = row["run_id"], row.get("name") or row["run_id"]
    else:
        with store.session() as s:
            row = s.execute(
                text("select run_id, name from s1.runs order by started desc nulls last limit 1")
            ).fetchone()
        if not row:
            print("no runs in the ledger", file=sys.stderr)
            return 1
        rid, name = row[0], row[1] or row[0]
    rows = ledger_store.metrics_matching(rid, "milestone/")
    if not rows:
        print(f"{name}: no milestones judged")
        return 0
    seen: dict[str, dict] = {}
    for r in rows:
        _, n, field = r["name"].split("/", 2)
        seen.setdefault(n, {"step": r["step"]})[field] = r["value"]
    for n, d in sorted(seen.items(), key=lambda kv: int(kv[0])):
        met = "met" if d.get("met") else "MISSED"
        print(f"  {n}. at step {d.get('step')}: {met}  value {d.get('value'):.4g}")
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
        from thorp import liberty_machine

        if a.value not in ("on", "off"):
            print("thorp s5 switch POLICY on|off", file=sys.stderr)
            return 2
        liberty_machine.set_switch(a.key, a.value == "on", a.words)
    elif a.what == "except":
        from thorp import liberty_machine

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
        n = liberty_machine.except_policy(a.key, reason=a.reason, adopted=a.words, runs=runs, patterns=patterns)
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


def cmd_lane(a) -> int:
    """Open or pause a lane in s2.lane_defs; the coordinator reads it on its next loop."""
    from thorp.viable.s2_coordination import lanes

    if a.what != "show" and not lanes.set_lane(a.lane, a.what == "open", a.why):
        print(f"no lane {a.lane!r}; the lanes are {', '.join(lanes.lane_defs(fresh=True))}")
        return 1
    d = lanes.lane_defs(fresh=True).get(a.lane)
    if d is None:
        print(f"no lane {a.lane!r}")
        return 1
    print(f"{d.lane}: {'open' if d.enabled else 'paused'} ({d.kind}, {d.seats} seat(s)); {d.note}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="thorp")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fetch", help="resolve, fetch, strip and register a book list")
    s.add_argument("list")
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("images", help="the Library's images: gather Gutenberg illustrations, list candidates, summarise")
    s.add_argument("action", choices=["gather", "candidates", "summary", "prune"])
    s.add_argument("--ids", type=int, nargs="*", help="Gutenberg ids to gather (otherwise the candidates)")
    s.add_argument("--illustrator", default="", help="only books with an illustrator whose name contains this")
    s.add_argument("--limit", type=int, default=3, help="books to take from the candidates")
    s.add_argument("--per-book", type=int, default=30, help="images to keep from one book at most")
    s.set_defaults(fn=cmd_images)
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
    s = sub.add_parser(
        "score",
        help="score a run's saved steps offline (its eval.offline evaluators), at the steps the loop deferred",
    )
    s.add_argument("run", help="run id, prefix or name")
    s.add_argument("--steps", default="pending", help="pending (default), all, or N,M")
    s.add_argument("--evaluators", nargs="+", help="these evaluators (a,b or a b) instead of the deferred ones")
    s.add_argument("--keep-snapshots", action="store_true", help="keep the eval-N snapshots once scored")
    s.set_defaults(fn=cmd_score)
    s = sub.add_parser("measure", help="backfill the quantum ladder on every Ogden/Kipling voyage")
    s.add_argument("--all", action="store_true", help="re-run the whole ladder, not only what the spec lacks")
    s.add_argument("--evaluators", nargs="+", help="run these evaluators")
    s.add_argument("--limit", type=int, default=0, help="stop after this many runs")
    s.add_argument("--include-legacy", action="store_true", help="try legacy checkpoints too (they may fail to load)")
    s.add_argument("--dry-run", action="store_true", help="list what would run")
    s.set_defaults(fn=cmd_measure)
    s = sub.add_parser("dash", help="serve the dashboard on http://localhost:8787")
    s.add_argument("--port", type=int, default=8787)
    s.set_defaults(fn=cmd_dash)
    s = sub.add_parser("login", help="the dashboard's login: set (asks for the password), remove, list")
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=lambda a: __import__("thorp.dash.auth", fromlist=["main"]).main(a.rest))
    s = sub.add_parser(
        "onboard", help="the first run: set up the store, models and dashboard in the browser"
    )
    s.add_argument("--port", type=int, default=8787, help="loopback port (0 chooses one)")
    s.add_argument("--no-browser", action="store_true", help="print the URL instead of opening it")
    s.add_argument("--reset", action="store_true", help="archive the answers and start again")
    s.set_defaults(fn=cmd_onboard)
    s = sub.add_parser("ledger", help="query the ledger; each ? defaults to the latest run id")
    s.add_argument("sql")
    s.add_argument("params", nargs="*")
    s.add_argument("--run", help="run id to bind to each ? when no params are given")
    s.set_defaults(fn=cmd_ledger)
    s = sub.add_parser(
        "charter", help="sail a voyage on a GPU hired from Vast.ai, within the charter's terms"
    )
    s.add_argument("what", choices=["quote", "sail", "attach", "audit", "terms"])
    s.add_argument(
        "spec",
        nargs="?",
        help="the voyage's spec; for attach, the hired ship: its run id, instance id or voyage's name",
    )
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
    s.add_argument("what", choices=["ping", "setup", "import", "ledger", "queue", "discoveries", "latest"])
    s.add_argument(
        "--retire",
        action="store_true",
        help="import: rename each imported file *.imported (the cutover)",
    )
    s.set_defaults(fn=cmd_store)
    s = sub.add_parser(
        "queue", help="the standing queue (Postgres): show it, or add, move and drop a line"
    )
    s.add_argument("what", choices=["show", "add", "goal", "move", "drop", "release"])
    s.add_argument("line", nargs="?")
    s.add_argument("to", nargs="?", type=int)
    s.add_argument("--top", action="store_true", help="add: put the line at the top")
    s.add_argument(
        "--goal",
        default=None,
        help="add, goal: the goal the line serves (kipling:3); add defaults to the spec's own `goal:`, and a line "
        "with none is refused",
    )
    s.add_argument(
        "--said",
        default=None,
        help="add, goal, move, drop, release: Justin's words asking for the edit. Only the coordinator, or an "
        "explicit instruction from Justin, edits the queue (S5 policy 'queue'); an edit without them is refused",
    )
    s.set_defaults(fn=cmd_queue)
    s = sub.add_parser(
        "goals",
        help="an expedition's goals as rows in the store: show them, add or edit one, or record a verdict",
    )
    s.add_argument("what", nargs="?", choices=["show", "sync", "set", "add", "edit", "remove", "check", "model", "link", "unlink"], default="show")
    s.add_argument("goal_id", nargs="?", help="set, edit, remove, link, unlink: the goal id (e.g. kipling:3); add: the expedition; model: the model's Hugging Face id")
    s.add_argument("status", nargs="?", help="set: open | partly | done | dropped")
    s.add_argument("--expedition", default=None, help="show: one expedition only")
    s.add_argument("--evidence", default="", help="set: where the reading is (run, metric, value)")
    s.add_argument("--words", default="", help="set: why it is settled, in whose words")
    s.add_argument("--text", default=None, help="add, edit: the goal in a line")
    s.add_argument("--detail", default=None, help="add, edit: what it is")
    s.add_argument("--why", default=None, help="add, edit: why it is wanted")
    s.add_argument("--position", type=int, default=None, help="add: the goal's number (default: the next)")
    s.add_argument("--model", default=None, help="link, unlink: the outside model's Hugging Face id")
    s.add_argument("--role", default=None, help="link: beat | compare | study (unlink: only that role)")
    s.add_argument("--note", default=None, help="link: what the goal does with the model")
    s.add_argument("--lab", default=None, help="model: the house's key (s4.labs)")
    s.add_argument("--name", default=None, help="model: its name")
    s.add_argument("--params", type=int, default=None, help="model: parameters")
    s.add_argument("--url", default=None, help="model: where it is published")
    s.add_argument("-v", "--verbose", action="store_true", help="show: print each goal's evidence")
    s.set_defaults(fn=cmd_goals)
    s = sub.add_parser(
        "milestones",
        help="a voyage's milestones as the ledger recorded them: each one's step, value and verdict",
    )
    s.add_argument("run", nargs="?", help="a run id, a unique prefix, or a name (default: the latest run)")
    s.set_defaults(fn=cmd_milestones)
    s = sub.add_parser("checkpoints", help="a finished run's checkpoints: prune those retention would not keep")
    s.add_argument("what", choices=["prune"])
    s.add_argument("run", help="a run id, a unique prefix, or a name")
    s.add_argument("--keep-last", type=int, default=1, help="the newest K checkpoints are kept (at least 1)")
    s.add_argument("--keep-every", type=int, default=0, help="every step that is a multiple of M is kept")
    s.add_argument("--dry-run", action="store_true", help="print what would be deleted (the default)")
    s.add_argument("--apply", action="store_true", help="delete them")
    s.set_defaults(fn=cmd_checkpoints)
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
        "schedule", help="Nothing up my sleeve's own schedule (S2): tick, list, run, import-claude, enable, judge"
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s2_coordination.schedule", fromlist=["main"]).main(
            a.rest
        )
    )
    s = sub.add_parser("lane", help="open or pause a lane of the queue (S2): thorp lane vast open | pause --why ...")
    s.add_argument("lane")
    s.add_argument("what", choices=["open", "pause", "show"], nargs="?", default="show")
    s.add_argument("--why", default="", help="for `pause`: the reason, kept on the lane's note")
    s.set_defaults(fn=cmd_lane)
    s = sub.add_parser(
        "cycle", help="the queue's planning cycle (S3): show the plan now, run a turn, put it on the schedule"
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s3_control.cycle", fromlist=["main"]).main(a.rest)
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
    s = sub.add_parser(
        "proposals", help="S5's proposals waiting on Justin: list, add, sign, decline, withdraw"
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s5_policy.proposals", fromlist=["main"]).main(a.rest)
    )
    s = sub.add_parser(
        "translate",
        help="the site's language and its translator (Tiny Aya Earth): status, languages, set, say, prepare",
    )
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(fn=lambda a: __import__("thorp.translate", fromlist=["main"]).main(a.rest))
    s = sub.add_parser(
        "feedback", help="S5: the feedback the systems send up, sorted by the taxonomy S4 reads"
    )
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--category", choices=["decide", "constrain", "repair", "calibrate", "learn"])
    s.set_defaults(
        fn=lambda a: __import__("thorp.viable.s5_policy.feedback", fromlist=["main"]).main(
            ["--days", str(a.days)] + (["--category", a.category] if a.category else [])
        )
    )
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
