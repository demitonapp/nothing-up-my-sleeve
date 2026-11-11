"""The AI2 ARC audit, question by question (12 November, Justin: "audit all the questions on the test and
then check which of the foreign ships vs our ships score and from there we can determine the hardest tests").

A reading of AI2 ARC used to keep two numbers a split (`arc-ai2-<model>` in s4.outside_readings) and throw the
questions away. This module keeps every question a reader answered, one row each, so any two readers can be
compared question by question and every question can be ranked by how many readers get it:

    s4.arc_answers   reader, kind (outside | ship), config (easy | challenge), part (test | validation),
                     question_id, source (the exam the id names), n_options, answer, prediction, correct,
                     rank (where the answer ranked, 0 = the bet), p_answer (its share of a softmax over the
                     options' negative mean losses), margin, ce (every option's mean loss), revision, scored_at

Who writes it:

- `scripts/score_arc_ai2.py` keeps every outside model's rows as it reads them (reader = the model id).
- `read_ship(run)` reads one of our ships' last checkpoint the same way, with the same scorer, and keeps its
  rows (reader = the run's name). It writes nothing to the ledger: no metric, eval row or artifact moves, so
  the ships' board readings stay as they were recorded.

    python -m thorp.arc_audit reread                 # every reader not yet whole, then the report (queued)
    python -m thorp.arc_audit ship RUN [RUN ...]     # read our ships, rows only
    python -m thorp.arc_audit report [--part test]   # the report: ships/reports/arc-audit-<date>.md
    python -m thorp.arc_audit readers                # who has been read, and on what

The reading itself is the board's: zero-shot, the option's own text as the continuation of the question, the
lowest mean loss a piece the bet (thorp/arc_ai2.py). Difficulty is read off the outside models only, because
every ship of ours from 300k to 21m is at chance and its right answers are mostly luck; the ships are set
beside the outside readers on the same questions, not used to rank them.
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

from sqlalchemy import text

from thorp import arc_ai2, paths, store

_DDL = (
    "create schema if not exists s4",
    "create table if not exists s4.arc_answers ("
    "reader text not null, "
    "kind text not null, "
    "config text not null, "
    "part text not null, "
    "question_id text not null, "
    "source text not null default '', "
    "n_options integer not null, "
    "answer integer not null, "
    "prediction integer, "
    "correct boolean not null default false, "
    "read boolean not null default true, "
    "rank integer, "
    "p_answer double precision, "
    "margin double precision, "
    "ce jsonb, "
    "revision text not null default '', "
    "scored_at timestamptz not null default now(), "
    "primary key (reader, config, part, question_id))",
    "create index if not exists arc_answers_question on s4.arc_answers (config, part, question_id)",
)

KINDS = ("outside", "ship")


def ensure() -> None:
    with store.session() as s:
        for ddl in _DDL:
            s.execute(text(ddl))


def record(reader: str, kind: str, rows: list[dict], revision: str = arc_ai2.REVISION) -> int:
    """Keep a reader's rows (thorp.arc_ai2.score_questions), replacing what it had for the same questions."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    ensure()
    sql = text(
        "insert into s4.arc_answers (reader, kind, config, part, question_id, source, n_options, answer, "
        "prediction, correct, read, rank, p_answer, margin, ce, revision, scored_at) values (:reader, :kind, "
        ":config, :part, :question_id, :source, :n_options, :answer, :prediction, :correct, :read, :rank, "
        ":p_answer, :margin, cast(:ce as jsonb), :revision, now()) on conflict (reader, config, part, "
        "question_id) do update set kind = excluded.kind, source = excluded.source, n_options = "
        "excluded.n_options, answer = excluded.answer, prediction = excluded.prediction, correct = "
        "excluded.correct, read = excluded.read, rank = excluded.rank, p_answer = excluded.p_answer, margin = "
        "excluded.margin, ce = excluded.ce, revision = excluded.revision, scored_at = now()"
    )
    params = [
        {
            "reader": reader,
            "kind": kind,
            "config": r["config"],
            "part": r["part"],
            "question_id": r["id"],
            "source": arc_ai2.source_of(r["id"]),
            "n_options": int(r["n"]),
            "answer": int(r["answer"]),
            "prediction": r.get("prediction"),
            "correct": bool(r.get("correct")),
            "read": bool(r.get("read", True)),
            "rank": r.get("rank"),
            "p_answer": r.get("p_answer"),
            "margin": r.get("margin"),
            "ce": json.dumps(r.get("ce")),
            "revision": revision,
        }
        for r in rows
    ]
    if not params:
        return 0
    with store.session() as s:
        s.execute(sql, params)
    return len(params)


def read_ship(run: str, configs=("easy", "challenge"), parts=("test",), batch: int = 64, log=print) -> dict:
    """Read one of our ships' last checkpoint on AI2 ARC and keep its rows; returns its summary a split.

    The run's own tokeniser, window and start piece, the board's scorer (the same call the in-run evaluator
    makes). Nothing is written to the ledger."""
    from thorp import train
    from thorp.ledger import reader, spec_of
    from thorp.models import ops

    row = reader().find_run(run)
    if not row:
        raise LookupError(f"no run {run}")
    spec, rid = spec_of(row), row["run_id"]
    ckpt = train.latest_checkpoint(rid)
    if ckpt is None:
        raise LookupError(f"run {rid} has no checkpoint")
    from thorp import ladder

    ladder.repair_spec(spec, rid)  # an old checkpoint's shape, not today's preset (as rescore does)
    prep = train.prepare(spec, log=log, known=True, sailed=rid)
    step = json.loads((ckpt / "state.json").read_text())["step"]
    model = train.scoring_model(spec, prep.tokeniser.vocab_size, ckpt)
    tok = prep.tokeniser
    out = {"run": row["name"], "run_id": rid, "step": step, "splits": {}}
    t0 = time.time()
    for part in parts:
        for config in configs:
            items = arc_ai2.questions(config, part)
            rows = arc_ai2.score_questions(
                lambda x, y: ops.token_ce(model, x, y), tok.encode, tok.eos_id, items, batch=batch,
                context=int(spec["model"]["context"]),
            )
            record(row["name"], "ship", rows)
            s = arc_ai2.summary(rows)
            out["splits"][f"{config}/{part}"] = s
            log(f"{row['name']} [{config}/{part}] accuracy {s['accuracy']:.4f} over {s['questions']} "
                f"({s['skipped']} skipped)")
    out["seconds"] = round(time.time() - t0, 1)
    return out


# The readers the audit compares (12 November): the nine outside models on the board, and our ships from 300k to
# 50m at their last checkpoint, two seeds where there are two. A queued investigation reads them all
# (specs/investigations/arc-audit-questions.yaml); one that is already whole is skipped, so a stopped re-read
# picks up where it stopped.
OUTSIDE = (
    "EleutherAI/pythia-14m", "EleutherAI/pythia-31m", "EleutherAI/pythia-70m", "EleutherAI/pythia-160m",
    "EleutherAI/pythia-410m", "mlx-community/gemma-3-270m-bf16", "Qwen/Qwen3-0.6B",
    "mlx-community/Qwen3.5-0.8B-bf16", "HuggingFaceTB/SmolLM2-360M",
)
SHIPS = (
    "dba348d4d097",  # 300k@v0.0.6-control
    "c45525729620",  # 300k@v0.0.6-control-s2
    "30cab184a259",  # fu-ogden-v0-1@1m-pre-s1
    "f24faf8620ad",  # fu-ogden-v0-1@1m-pre-s2
    "7436bab9726d",  # fu-ogden-v0-1@9m-pre-s1
    "d7ec47e4d3e9",  # fu-ogden-v0-1@9m-pre-s2
    "136246a7ff04",  # 9m@v0.0.6
    "a749ae17eaa6",  # 300k@v0.0.6-pins (the best keel's leader), the subject of the queue's arc-ai2-300k
    "8d078f62cc63",  # 1m@v0.0.5, the subject of arc-ai2-1m
    "edc36bbbd9fc",  # 9m@v0.0.5, the subject of arc-ai2-9m
    "cdc3da8540e3",  # fu-ogden-v0-1@21m-pre-s1
    "55eec445a5e7",  # 21m@v0.0.5
    "c353647dc22c",  # the first 50m (fu-ogden-v0-2~table-talk-reading@50m-pre-s1)
)


def whole(reader: str, part: str = "test") -> bool:
    """Whether a reader has a row for every question of `part` (both splits)."""
    ensure()
    want = sum(n for (_, p), n in arc_ai2.COUNTS.items() if p == part)
    with store.session() as s:
        got = s.execute(
            text("select count(*) from s4.arc_answers where reader = :r and part = :p"), {"r": reader, "p": part}
        ).scalar()
    return int(got or 0) >= want


def reread(outside=OUTSIDE, ships=SHIPS, log=print) -> int:
    """Read every reader not yet whole, then write the report. Returns the number that failed.

    Outside models through scripts/score_arc_ai2.py (test and validation, questions only: the board's own
    reading is left as it was), each in its own process so one that cannot load does not stop the rest; our
    ships through read_ship (test). The queue gives the seat, so neither waits for a helm."""
    import subprocess
    import sys

    from thorp.ledger import reader as ledger_reader

    failed = 0
    for m in outside:
        if whole(m, "test") and whole(m, "validation"):
            log(f"{m}: already whole, skipped")
            continue
        log(f"=== {time.strftime('%H:%M:%S')} {m}")
        code = subprocess.call(
            [sys.executable, str(paths.resolve("scripts/score_arc_ai2.py")), m, "--no-helm", "--no-board",
             "--parts", "test,validation", "--batch", "32"],
            cwd=paths.ROOT,
        )
        failed += code != 0
        log(f"{m}: exit {code}")
    for r in ships:
        row = ledger_reader().find_run(r)
        name = row["name"] if row else r
        if whole(name, "test"):
            log(f"{name}: already whole, skipped")
            continue
        log(f"=== {time.strftime('%H:%M:%S')} ship {name}")
        try:
            read_ship(r, log=log)
        except Exception as e:  # noqa: BLE001 - one ship that cannot be read does not stop the rest
            failed += 1
            log(f"{name}: failed ({e!r})")
    report("test")
    log(f"report written; {failed} reader(s) failed")
    return failed


def readers(part: str = "test") -> list[dict]:
    """Every reader with rows, its kind, and its accuracy a split on `part`."""
    ensure()
    with store.session() as s:
        rows = s.execute(
            text(
                "select reader, kind, config, count(*) filter (where read) n, "
                "count(*) filter (where correct) right_, avg(p_answer) p, max(scored_at) at "
                "from s4.arc_answers where part = :part group by reader, kind, config order by kind, reader, config"
            ),
            {"part": part},
        ).mappings()
        out: dict[str, dict] = {}
        for r in rows:
            d = out.setdefault(r["reader"], {"reader": r["reader"], "kind": r["kind"], "splits": {}})
            n = int(r["n"] or 0)
            d["splits"][r["config"]] = {
                "questions": n,
                "accuracy": (int(r["right_"]) / n) if n else 0.0,
                "p_answer": float(r["p"]) if r["p"] is not None else None,
                "scored_at": r["at"].isoformat() if r["at"] else None,
            }
        return list(out.values())


def table(part: str = "test") -> dict:
    """Every question of `part` with every reader's verdict: {(config, id): {reader: row}} and the readers."""
    ensure()
    with store.session() as s:
        rows = s.execute(
            text(
                "select reader, kind, config, question_id, source, n_options, answer, prediction, correct, read, "
                "rank, p_answer from s4.arc_answers where part = :part"
            ),
            {"part": part},
        ).mappings()
        qs: dict[tuple[str, str], dict] = defaultdict(dict)
        kinds: dict[str, str] = {}
        for r in rows:
            qs[(r["config"], r["question_id"])][r["reader"]] = dict(r)
            kinds[r["reader"]] = r["kind"]
    return {"questions": qs, "kinds": kinds}


def _short(reader: str) -> str:
    return reader.split("/")[-1].replace("-bf16", "")


def difficulty(part: str = "test", anchor: str = "HuggingFaceTB/SmolLM2-360M") -> dict:
    """Each question's difficulty, read off the outside models: the share of them that answer it, and whether
    the anchor (SmolLM2-360M) does. Returns per question {config, id, source, n_options, solved_by, outside,
    share, anchor, ships_right, ships, ship_p} and the reader lists."""
    t = table(part)
    outside = sorted(r for r, k in t["kinds"].items() if k == "outside")
    ships = sorted(r for r, k in t["kinds"].items() if k == "ship")
    out = []
    for (config, qid), by in t["questions"].items():
        o = [r for r in outside if r in by and by[r]["read"]]
        sh = [r for r in ships if r in by and by[r]["read"]]
        any_row = next(iter(by.values()))
        solved = [r for r in o if by[r]["correct"]]
        out.append(
            {
                "config": config,
                "id": qid,
                "source": any_row["source"],
                "n_options": any_row["n_options"],
                "solved_by": solved,
                "outside": len(o),
                "share": (len(solved) / len(o)) if o else None,
                "anchor": bool(by[anchor]["correct"]) if anchor in by and by[anchor]["read"] else None,
                "ships_right": [r for r in sh if by[r]["correct"]],
                "ships": len(sh),
                "ship_p": (sum(by[r]["p_answer"] or 0 for r in sh) / len(sh)) if sh else None,
            }
        )
    return {"rows": out, "outside": outside, "ships": ships, "anchor": anchor}


def report(part: str = "test", path=None) -> str:
    """The audit as Markdown: who was read, how the questions split by how many outside models answer them,
    what only SmolLM2 answers, what nobody answers, by exam, and where our ships stand on each band."""
    d = difficulty(part)
    rows, outside, ships, anchor = d["rows"], d["outside"], d["ships"], d["anchor"]
    qtext = {}
    for config in ("easy", "challenge"):
        for q in arc_ai2.questions(config, part):
            qtext[(config, q["id"])] = q
    lines = [f"# AI2 ARC, question by question ({time.strftime('%d %B %Y')}, the {part} split)", ""]
    lines += [
        "Zero-shot, the option's own text as the continuation, the lowest mean loss a piece the bet "
        "(thorp/arc_ai2.py). Every row is in `s4.arc_answers`; `python -m thorp.arc_audit report` rebuilds this.",
        "Difficulty is the share of the outside models that answer a question. Our ships are set beside them "
        "and do not rank anything: from 300k to 21m they read at chance, so which questions they get is mostly luck. "
        "`p` is the answer's share of a softmax over the options' negative mean losses (chance is 1/options).",
        "",
        "## The readers",
        "",
        "| reader | kind | Easy | Challenge | Easy p | Challenge p |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for r in sorted(readers(part), key=lambda x: (x["kind"], -(x["splits"].get("easy", {}).get("accuracy") or 0))):
        e, c = r["splits"].get("easy", {}), r["splits"].get("challenge", {})

        def f(x, k, pct=True):
            v = x.get(k)
            return "–" if v is None else (f"{100 * v:.1f}" if pct else f"{v:.3f}")

        lines.append(f"| {_short(r['reader'])} | {r['kind']} | {f(e, 'accuracy')} | {f(c, 'accuracy')} | "
                     f"{f(e, 'p_answer', False)} | {f(c, 'p_answer', False)} |")
    if not outside:
        lines += ["", "No outside model has per-question rows yet: re-read them with scripts/score_arc_ai2.py."]
        text_ = "\n".join(lines) + "\n"
        _write(text_, part, path)
        return text_
    n_out = len(outside)
    lines += ["", f"## How the questions split ({n_out} outside models)", ""]
    for config in ("easy", "challenge"):
        sub = [r for r in rows if r["config"] == config and r["share"] is not None]
        if not sub:
            continue
        lines += [f"**ARC-{config.capitalize()}** ({len(sub)} questions)", "",
                  "| outside models that answer it | questions | SmolLM2 answers | our ships' mean p | ships' accuracy |",
                  "| ---: | ---: | ---: | ---: | ---: |"]
        for k in range(n_out, -1, -1):
            band = [r for r in sub if len(r["solved_by"]) == k]
            if not band:
                continue
            read_anchor = [r for r in band if r["anchor"] is not None]
            anc = sum(1 for r in read_anchor if r["anchor"])
            anc_cell = f"{anc} ({100 * anc / len(read_anchor):.0f}%)" if read_anchor else "–"
            sp = [r["ship_p"] for r in band if r["ship_p"] is not None]
            sa = [len(r["ships_right"]) / r["ships"] for r in band if r["ships"]]
            lines.append(f"| {k} of {n_out} | {len(band)} | {anc_cell} | "
                         f"{(sum(sp) / len(sp)) if sp else float('nan'):.3f} | "
                         f"{(100 * sum(sa) / len(sa)) if sa else float('nan'):.1f}% |")
        lines.append("")
    # what only the anchor answers, and what nobody answers
    for title, pick in (
        ("Answered by SmolLM2-360M and by no other outside model", lambda r: r["anchor"] and len(r["solved_by"]) == 1),
        ("Answered by no outside model", lambda r: r["share"] == 0),
    ):
        for config in ("easy", "challenge"):
            got = [r for r in rows if r["config"] == config and r["share"] is not None and pick(r)]
            lines += [f"## {title}: ARC-{config.capitalize()} ({len(got)})", ""]
            for r in sorted(got, key=lambda x: x["id"])[:25]:
                q = qtext.get((config, r["id"]))
                if not q:
                    continue
                opts = " / ".join(("**" + o + "**") if i == q["answer"] else o for i, o in enumerate(q["options"]))
                lines.append(f"- `{r['id']}` {q['question']} — {opts}")
            if len(got) > 25:
                lines.append(f"- … and {len(got) - 25} more (`difficulty()` lists them all)")
            lines.append("")
    # by exam
    lines += ["## By exam (the source the question id names)", "",
              "| exam | split | questions | outside models' mean share | SmolLM2 | our ships' mean p |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    by = defaultdict(list)
    for r in rows:
        if r["share"] is not None:
            by[(r["source"], r["config"])].append(r)
    for (src, config), band in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(band) < 20:
            continue
        anc = [r["anchor"] for r in band if r["anchor"] is not None]
        sp = [r["ship_p"] for r in band if r["ship_p"] is not None]
        lines.append(f"| {src} | {config} | {len(band)} | {100 * sum(r['share'] for r in band) / len(band):.1f}% | "
                     f"{(100 * sum(anc) / len(anc)) if anc else float('nan'):.1f}% | "
                     f"{(sum(sp) / len(sp)) if sp else float('nan'):.3f} |")
    lines.append("")
    text_ = "\n".join(lines) + "\n"
    _write(text_, part, path)
    return text_


def _write(text_: str, part: str, path) -> None:
    from pathlib import Path

    p = Path(path) if path else paths.resolve("reports") / f"arc-audit-{time.strftime('%Y-%m-%d')}" \
        f"{'' if part == 'test' else '-' + part}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text_, encoding="utf-8")


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m thorp.arc_audit")
    sub = ap.add_subparsers(dest="what", required=True)
    s = sub.add_parser("ship", help="read our ships' last checkpoints, rows only (no ledger writes)")
    s.add_argument("runs", nargs="+")
    s.add_argument("--parts", default="test", help="test, validation or both: test,validation")
    r = sub.add_parser("report")
    r.add_argument("--part", default="test")
    r.add_argument("--out", default=None)
    sub.add_parser("readers").add_argument("--part", default="test")
    sub.add_parser("reread", help="read every outside model and ship not yet whole, then write the report")
    a = ap.parse_args(argv)
    if a.what == "reread":
        return 1 if reread() else 0
    if a.what == "ship":
        for run in a.runs:
            read_ship(run, parts=tuple(x for x in a.parts.split(",") if x))
        return 0
    if a.what == "report":
        report(a.part, a.out)
        print(f"written: {a.out or paths.resolve('reports') / ('arc-audit-' + time.strftime('%Y-%m-%d'))}")
        return 0
    for r in readers(a.part):
        print(r["reader"], r["kind"], {k: round(v["accuracy"], 4) for k, v in r["splits"].items()})
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
