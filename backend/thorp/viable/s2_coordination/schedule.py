"""S2: Thorp's own schedule (Justin, 8 November: "thorps schedules tasks shouldn't be in claude code, but rather part of
our VSM model and in postgres"). The jobs are rows in s2.schedule_jobs, every firing a row in s2.schedule_firings, and
the judge of a job that needs judgment is S5's choice in s5.judges ("Thorps most capable model should judge it, claude
initially but eventually a thorp model").

    uv run thorp schedule tick           # fire what is due (run every minute by launchd: io.thorp.schedule)
    uv run thorp schedule list           # the jobs, when each is next due, its last firing
    uv run thorp schedule import-claude LISTING.json   # Claude Code's thorp-* tasks, their prompts word for word
    uv run thorp schedule enable KEY on|off --words "..."
    uv run thorp schedule judge NAME '["claude", "-p"]' --words "..."

- **When a job is due.** A cron job (five fields, this Mac's local time) is due at each minute its cron matches; a
  one-time job at its time. A due time is owed only after the job was enabled, and only while it is fresh (within the
  job's `catch_up_minutes`, 30 by default): one later than that, or one that comes while the job's last firing is still
  running, is logged as missed, never fired late. A one-time job is switched off once it has fired.
- **Each due time fires once**, however many ticks see it: the firing's row is unique on (job, due time).
- **A firing** runs detached from the tick (`thorp schedule run FIRING`): a command under `sh -c`, or the job's prompt
  on the judge's stdin, from the job's `cwd` (the repository by default), for at most its `max_minutes` (60). All it
  says goes to data/runs/schedule/<job>-<firing>.out; its end is kept as the firing's summary, with how it ended.
- **No judge, no firing.** With no judge chosen in s5.judges, a judged job's firing fails, saying so; nothing guesses.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from thorp import paths, store
from thorp.viable.records import JobFiring, Judge, ScheduledJob

CATCH_UP_MINUTES = 30
MAX_MINUTES = 60
SUMMARY_CHARS = 2000


# ---------------------------------------------------------------- cron


def _field(spec: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, s = part.split("/")
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-"))
        else:
            a = b = int(part)
        if a < lo or b > hi or a > b or step < 1:
            raise ValueError(f"cron field {spec!r} out of {lo}-{hi}")
        out.update(range(a, b + 1, step))
    return out


def parse_cron(expr: str) -> tuple[set[int], ...]:
    """minute, hour, day of month, month, day of week (0 or 7 is Sunday)."""
    f = expr.split()
    if len(f) != 5:
        raise ValueError(f"a cron has five fields: {expr!r}")
    dow = _field(f[4], 0, 7)
    return (_field(f[0], 0, 59), _field(f[1], 0, 23), _field(f[2], 1, 31), _field(f[3], 1, 12),
            {d % 7 for d in dow}, f[2] == "*", f[4] == "*")  # fmt: skip


def matches(expr: str, t: datetime) -> bool:
    mi, h, dom, mon, dow, dom_any, dow_any = parse_cron(expr)
    if t.minute not in mi or t.hour not in h or t.month not in mon:
        return False
    d_ok, w_ok = t.day in dom, (t.isoweekday() % 7) in dow
    return d_ok and w_ok if (dom_any or dow_any) else (d_ok or w_ok)  # cron's rule: either, when both are given


def last_due(expr: str, now: datetime, since: datetime) -> datetime | None:
    """The latest minute in (since, now] the cron matches, or None."""
    t = now.replace(second=0, microsecond=0)
    while t > since:
        if matches(expr, t):
            return t
        t -= timedelta(minutes=1)
    return None


def next_due(expr: str, now: datetime, horizon_days: int = 40) -> datetime | None:
    t = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = now + timedelta(days=horizon_days)
    while t < end:
        if matches(expr, t):
            return t
        t += timedelta(minutes=1)
    return None


# ---------------------------------------------------------------- what is due


def _now() -> datetime:
    return datetime.now().astimezone()


def due(now: datetime | None = None) -> list[tuple[str, datetime, str]]:
    """(job, due time, 'fire' or why it is missed) for each due time not yet fired or logged."""
    now = now or _now()
    out = []
    with store.session() as s:
        for j in s.scalars(select(ScheduledJob).where(ScheduledJob.enabled.is_(True))):
            since = j.enabled_at or j.created_at
            catch = timedelta(minutes=float(j.limits.get("catch_up_minutes", CATCH_UP_MINUTES)))
            if j.cron:
                t = last_due(j.cron, now, max(since, now - timedelta(days=2)))
            else:
                t = j.fire_at if j.fire_at and since <= j.fire_at <= now else None
            if t is None:
                continue
            if s.scalar(select(JobFiring.id).where(JobFiring.job_key == j.key, JobFiring.due_at == t)):
                continue
            running = s.scalar(select(JobFiring.id).where(JobFiring.job_key == j.key, JobFiring.outcome == "running"))
            if running:
                out.append((j.key, t, f"missed: firing {running} still running"))
            elif now - t > catch:
                out.append((j.key, t, f"missed: due {t:%H:%M}, more than {catch} ago"))
            else:
                out.append((j.key, t, "fire"))
    return out


def _spawn(firing_id: int) -> int:
    """The firing's own process, detached from the tick (so a long judge never holds the next tick)."""
    log = paths.data_dir() / "runs" / "schedule" / "tick.out"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f:
        p = subprocess.Popen([sys.executable, "-m", "thorp.cli", "schedule", "run", str(firing_id)], cwd=paths.ROOT,
                             stdout=f, stderr=subprocess.STDOUT, start_new_session=True)  # fmt: skip
    return p.pid


def tick(now: datetime | None = None, spawn=_spawn) -> list[dict]:
    """Fire what is due: a row per due time (unique, so a second tick at the same minute fires nothing more), then the
    firing's process. Missed due times are logged, not fired."""
    now = now or _now()
    out = []
    for key, t, how in due(now):
        try:
            with store.session() as s:
                f = JobFiring(job_key=key, due_at=t, outcome="running" if how == "fire" else "missed",
                              summary="" if how == "fire" else how, finished_at=None if how == "fire" else now)  # fmt: skip
                s.add(f)
                s.flush()
                fid = f.id
                job = s.get(ScheduledJob, key)
                if job.fire_at is not None:  # a one-time job, fired (or missed): off
                    job.enabled = False
        except IntegrityError:  # another tick took this due time
            continue
        if how == "fire":
            pid = spawn(fid)
            with store.session() as s:
                s.get(JobFiring, fid).pid = pid
        out.append({"job": key, "due": t.isoformat(timespec="minutes"), "how": how, "firing": fid})
    return out


# ---------------------------------------------------------------- a firing


def judge() -> Judge | None:
    with store.session() as s:
        return s.scalars(select(Judge).order_by(Judge.id.desc()).limit(1)).first()


def run_firing(firing_id: int, runner=subprocess.run) -> dict:
    """Run one firing to its end and record how it ended."""
    with store.session() as s:
        f = s.get(JobFiring, firing_id)
        j = f.job
        job = {"key": j.key, "kind": j.kind, "prompt": j.prompt, "command": j.command, "limits": dict(j.limits or {})}
    out_path = paths.data_dir() / "runs" / "schedule" / f"{job['key']}-{firing_id}.out"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cwd = job["limits"].get("cwd") or str(paths.ROOT)
    minutes = float(job["limits"].get("max_minutes", MAX_MINUTES))
    started = _now()
    if job["kind"] == "command":
        who, argv, stdin = "command", ["sh", "-c", job["command"]], None
    else:
        jd = judge()
        if jd is None:
            return _finish(firing_id, started, None, "failed", None, "no judge chosen (s5.judges; thorp schedule judge)", out_path)
        who, argv, stdin = jd.name, list(jd.command), job["prompt"]
    with store.session() as s:
        s.get(JobFiring, firing_id).started_at, s.get(JobFiring, firing_id).judge = started, who
    try:
        r = runner(argv, input=stdin, cwd=cwd, capture_output=True, text=True, timeout=minutes * 60)
        text = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
        outcome, code = ("ok" if r.returncode == 0 else "failed"), r.returncode
    except subprocess.TimeoutExpired as e:
        text = (e.stdout or "") if isinstance(e.stdout, str) else ""
        outcome, code = "timeout", None
        text += f"\n(stopped after {minutes:g} minutes, the job's max_minutes)"
    except FileNotFoundError as e:
        text, outcome, code = f"the judge's command could not be started: {e}", "failed", None
    out_path.write_text(text, encoding="utf-8")
    return _finish(firing_id, started, who, outcome, code, text[-SUMMARY_CHARS:].strip(), out_path)


def _finish(fid, started, who, outcome, code, summary, out_path) -> dict:
    with store.session() as s:
        f = s.get(JobFiring, fid)
        f.started_at = f.started_at or started
        f.finished_at, f.outcome, f.exit_code, f.summary, f.output_path = _now(), outcome, code, summary, str(out_path)
        if who:
            f.judge = who
        return {"firing": fid, "job": f.job_key, "judge": f.judge, "outcome": outcome, "exit_code": code}


# ---------------------------------------------------------------- the jobs


def put_job(key: str, **fields) -> None:
    with store.session() as s:
        j = s.get(ScheduledJob, key) or ScheduledJob(key=key)
        for k, v in fields.items():
            setattr(j, k, v)
        s.merge(j)


def enable(key: str, on: bool, words: str) -> None:
    with store.session() as s:
        j = s.get(ScheduledJob, key)
        if j is None:
            raise KeyError(f"no job {key!r}")
        j.enabled, j.words = on, words
        if on:
            j.enabled_at = _now()  # nothing before now is owed


def set_judge(name: str, command: list[str], words: str) -> None:
    if not command or not all(isinstance(x, str) for x in command):
        raise ValueError("a judge's command is a list of strings (argv); the prompt is given on its stdin")
    with store.session() as s:
        s.add(Judge(name=name, command=command, words=words))


def jobs(now: datetime | None = None) -> list[dict]:
    now = now or _now()
    with store.session() as s:
        out = []
        for j in s.scalars(select(ScheduledJob).order_by(ScheduledJob.key)):
            last = s.scalars(select(JobFiring).where(JobFiring.job_key == j.key).order_by(JobFiring.id.desc()).limit(1)).first()
            nxt = (next_due(j.cron, now) if j.cron else (j.fire_at if j.fire_at and j.fire_at > now else None)) if j.enabled else None
            out.append({"key": j.key, "system": j.system, "kind": j.kind, "enabled": j.enabled,
                        "when": j.cron or (j.fire_at.isoformat(timespec="minutes") if j.fire_at else None),
                        "next": nxt.isoformat(timespec="minutes") if nxt else None,
                        "last": {"due": last.due_at.isoformat(timespec="minutes"), "outcome": last.outcome, "judge": last.judge} if last else None})  # fmt: skip
        return out


# ---------------------------------------------------------------- from Claude Code

SYSTEM_OF = {  # which system each Claude Code task served
    "thorp-first-light": "S2",  # keeps a voyage sailing and steers its next round
    "thorp-loop-steer": "S2",
    "thorp-night-watch-0030": "S2",
    "thorp-night-watch-0300": "S2",
    "thorp-night-watch-0600": "S2",
    "thorp-night-watch-0900": "S2",
    "thorp-9m-spelling-report": "S4",  # a report on the evidence: intelligence
}


def _front(text: str) -> tuple[dict, str]:
    """A SKILL.md's front matter and its body, the body exactly as written."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.index("\n---\n", 4)
    meta = {}
    for ln in text[4:end].splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            meta[k.strip()] = v.strip()
    body = text[end + len("\n---\n"):]
    return meta, body[1:] if body.startswith("\n") else body


def import_claude(listing: list[dict], tasks_dir: Path | None = None) -> list[str]:
    """Claude Code's thorp-* tasks (the listing the scheduled-tasks tool gives: taskId, title, description, cron or
    fireAt, enabled) into s2.schedule_jobs, each prompt word for word from its SKILL.md. Every job comes in switched
    off: one is switched on here only when it is switched off in Claude Code, so nothing fires twice."""
    tasks_dir = tasks_dir or Path.home() / ".claude" / "scheduled-tasks"
    out = []
    for t in listing:
        key = t["taskId"]
        if not key.startswith("thorp-"):
            continue  # not Thorp's (land-search-recheck): left alone
        meta, body = _front((tasks_dir / key / "SKILL.md").read_text(encoding="utf-8"))
        fire_at = datetime.fromisoformat(t["fireAt"].replace("Z", "+00:00")) if t.get("fireAt") else None
        put_job(key, title=t.get("title") or meta.get("name", key), description=t.get("description") or meta.get("description", ""),
                system=SYSTEM_OF.get(key, "S2"), kind="judge", cron=t.get("cronExpression") if not fire_at else None,
                fire_at=fire_at, enabled=False, prompt=body, command=None,
                limits={"max_minutes": MAX_MINUTES, "catch_up_minutes": CATCH_UP_MINUTES, "jitter_seconds": t.get("jitterSeconds", 0)},
                source=f"claude-code:{key} ({'enabled' if t.get('enabled') else 'disabled'} there when imported)",
                words="imported from Claude Code's scheduled tasks, 2026-11-08")  # fmt: skip
        out.append(key)
    return out


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="thorp schedule")
    sub = p.add_subparsers(dest="what", required=True)
    sub.add_parser("tick")
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("firing", type=int)
    i = sub.add_parser("import-claude")
    i.add_argument("listing", help="the scheduled-tasks listing, as JSON")
    e = sub.add_parser("enable")
    e.add_argument("key")
    e.add_argument("on", choices=["on", "off"])
    e.add_argument("--words", required=True)
    jd = sub.add_parser("judge")
    jd.add_argument("name")
    jd.add_argument("command", help='argv as JSON, e.g. \'["claude", "-p"]\'')
    jd.add_argument("--words", required=True)
    a = p.parse_args(argv)
    if a.what == "tick":
        for x in tick():
            print(json.dumps(x))
    elif a.what == "list":
        print(json.dumps(jobs(), indent=1))
    elif a.what == "run":
        print(json.dumps(run_firing(a.firing)))
    elif a.what == "import-claude":
        print("\n".join(import_claude(json.loads(Path(a.listing).read_text()))))
    elif a.what == "enable":
        enable(a.key, a.on == "on", a.words)
    else:
        set_judge(a.name, json.loads(a.command), a.words)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
