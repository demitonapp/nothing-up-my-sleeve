"""Investigations: the audits and readings an expedition needs, queued beside its voyages (11 November,
Justin: "we need to add audits/investigations into the queue so we can queue them alongside our ship voyages").

A voyage is a spec under `ships/specs/fitouts/` that the trainer sails. An investigation is a spec under
`ships/specs/investigations/` that reads something: an outside model on a test, a census of heads, an
instrument's own check. It names its expedition outright (no label matching), its subject, the command that
does the reading, a deadline, and where the reading lands:

    kind: investigation
    name: arc-qwen3-4b
    expedition: arc_de_triomphe
    ship: "Arc de Triomphe: Qwen3 4B on ARC-AGI-2, reasoning off and on"
    question: ...
    subject: mlx-community/Qwen3-4B-4bit
    run: [backend/scripts/score_arc.py, "{subject}", --limit, "0", --thinking, both]
    estimate: 8h        # about how long it takes: the queue's clock (its last run's time wins once it has one)
    timeout: 14h
    readings: ["arc-{subject}", "arc-{subject}@thinking"]

    thorp queue add investigations/arc-qwen3-4b       # queued like a voyage, at the end (or --top)
    python -m thorp.investigate list                   # every investigation and where it stands
    python -m thorp.investigate run arc-qwen3-4b       # what the queue runs

In the queue it is a `cmd:` line that runs this module (`queue_line`), so the coordinator already at sea
sails it with no restart, in the Mac lane's seat, in order with the voyages. This module adds what a bare
command lacks: the spec is checked before it is queued, the deadline is kept here, the log goes to
`data/runs/investigations/<name>.out`, and its standing (queued, running, finished, failed, timed out, with
its exit, its minutes and its readings) is kept in the store as `investigation-<name>`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

from thorp import paths

FOLDER = "investigations"
_LINE = re.compile(r"-m thorp\.investigate run (\S+)\s*$")
_UNITS = {"s": 1, "m": 60, "h": 3600}


def folder() -> Path:
    return paths.resolve("specs") / FOLDER


def names() -> list[str]:
    return sorted(p.stem for p in folder().glob("*.yaml")) if folder().is_dir() else []


def seconds(timeout) -> int | None:
    """`90m`, `14h`, `600s` or a bare number of minutes, as seconds; None is no deadline."""
    if timeout in (None, "", 0):
        return None
    m = re.fullmatch(r"(\d+)\s*([smh]?)", str(timeout).strip())
    if not m:
        raise ValueError(f"timeout {timeout!r}: write 90m, 14h or 600s")
    return int(m.group(1)) * _UNITS[m.group(2) or "m"]


def load(name: str) -> dict:
    """An investigation's spec, checked: a broken one is refused when it is queued, not when it sails."""
    import yaml

    name = name.removeprefix(FOLDER + "/").removesuffix(".yaml")
    p = folder() / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"no investigation {name!r} in {folder()}")
    spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    problems = check(spec, name)
    if problems:
        raise ValueError(f"investigation {name}: " + "; ".join(problems))
    return spec


def check(spec: dict, name: str | None = None) -> list[str]:
    from thorp import fleet

    out = []
    if spec.get("kind") != "investigation":
        out.append("kind must be 'investigation'")
    if name is not None and spec.get("name") != name:
        out.append(f"name {spec.get('name')!r} does not match its file {name!r}")
    if spec.get("expedition") not in fleet.EXPEDITIONS:
        out.append(f"expedition {spec.get('expedition')!r} is not in fleet.EXPEDITIONS")
    run = spec.get("run")
    if not (isinstance(run, list) and run and all(isinstance(x, str | int | float) for x in run)):
        out.append("run must be a list: a script or -m module, then its arguments")
    if not spec.get("question"):
        out.append("question: say what it settles")
    for key in ("timeout", "estimate"):
        try:
            seconds(spec.get(key))
        except ValueError as e:
            out.append(f"{key}: {e}")
    return out


def estimate(spec: dict, rec: dict | None = None) -> tuple[float | None, str, bool]:
    """About how many minutes an investigation takes, where that came from, and whether it is only an upper
    bound (12 November, Justin: "when scheduling tasks like investigations they should also have an
    estimated length so the queue is accurate").

    In order: its own last finished run (the store's standing, `wall_minutes`); the spec's `estimate:`
    (`10m`, `8h`), written by whoever queues it; its `timeout:`, which the runner enforces, so the line cannot
    run longer, marked as a bound. None when it states neither."""
    if rec is None:
        try:
            from thorp.viable.s4_intelligence import readings

            rec = readings.get(_store_name(str(spec.get("name") or ""))) or {}
        except Exception:  # noqa: BLE001 - no store (a box, a test): the spec still answers
            rec = {}
    if rec.get("status") == "finished" and (rec.get("wall_minutes") or 0) > 0:
        return float(rec["wall_minutes"]), "its last run", False
    est = seconds(spec.get("estimate"))
    if est:
        return est / 60, "its spec's estimate", False
    lim = seconds(spec.get("timeout"))
    if lim:
        return lim / 60, "its deadline (an upper bound)", True
    return None, "no time", False


def argv(spec: dict) -> list[str]:
    """The command an investigation runs: this interpreter, then `run` with {subject} filled in."""
    subject = str(spec.get("subject") or "")
    return [sys.executable, *[str(x).replace("{subject}", subject) for x in spec["run"]]]


def readings_of(spec: dict) -> list[str]:
    subject = str(spec.get("subject") or "")
    return [str(r).replace("{subject}", subject) for r in spec.get("readings") or []]


def queue_line(name: str) -> str:
    """The queue line for an investigation: a `cmd:` the coordinator already knows how to sail."""
    spec = load(name)
    return f"cmd: PYTHONPATH=backend backend/.venv/bin/python -m thorp.investigate run {spec['name']}"


def of_line(text: str) -> dict | None:
    """The investigation a queue line runs, or None for any other line (a voyage, a bare command, a wait)."""
    m = _LINE.search(text or "")
    if not m or "cmd:" not in text:
        return None
    try:
        return load(m.group(1))
    except (FileNotFoundError, ValueError):
        return None


def _store_name(name: str) -> str:
    return f"investigation-{name}"


def standing(name: str) -> dict:
    """Where an investigation stands: what the store holds, or 'queued' or 'in port' from the queue."""
    rec = None
    try:
        from thorp.viable.s4_intelligence import readings

        rec = readings.get(_store_name(name))
    except Exception:  # noqa: BLE001 - no store (a box, a test): the spec still answers
        rec = None
    if rec and rec.get("status") == "running" and not _alive(rec.get("pid")):
        rec = {**rec, "status": "stopped"}  # killed without a finish: say so, do not call it running
    if rec:
        return rec
    queued = False
    try:
        from thorp.viable.s2_coordination import queue_store

        queued = any((of_line(t) or {}).get("name") == name for t in queue_store.pending_texts())
    except Exception:  # noqa: BLE001
        queued = False
    return {"name": name, "status": "queued" if queued else "in port"}


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def _put(name: str, rec: dict) -> None:
    try:
        from thorp.viable.s4_intelligence import readings

        readings.put(_store_name(name), rec)
    except Exception as e:  # noqa: BLE001 - the reading itself matters more than its standing
        print(f"investigation {name}: standing not stored ({e!r})", file=sys.stderr, flush=True)


def run(name: str) -> int:
    """Run one investigation to its end or its deadline; its exit is the command's (124 on a deadline)."""
    spec = load(name)
    name = spec["name"]
    cmd = argv(spec)
    limit = seconds(spec.get("timeout"))
    log = paths.data_dir() / "runs" / FOLDER / f"{name}.out"
    log.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "name": name, "kind": "investigation", "expedition": spec["expedition"], "ship": spec.get("ship"),
        "subject": spec.get("subject"), "question": spec.get("question"), "command": cmd[1:],
        "readings": readings_of(spec), "log": str(log), "status": "running", "pid": os.getpid(),
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "timeout_seconds": limit,
    }
    _put(name, rec)
    t0, status, code = time.time(), "failed", 1
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        x for x in ("backend", os.environ.get("PYTHONPATH", "")) if x)}
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n=== {rec['started']} {name}: {' '.join(cmd[1:])}\n")
        out.flush()
        # its own session, so the deadline (or a signal to this runner) stops the whole reading. The child's
        # session is not the runner's group, so a SIGTERM to the runner must be passed on by hand (12 November:
        # the coordinator's stop ended the runner and left score_arc.py on the GPU beside the next voyage).
        p = subprocess.Popen(cmd, cwd=paths.ROOT, stdout=out, stderr=subprocess.STDOUT, env=env,
                             start_new_session=True)
        import signal

        def _terminated(signum, frame):
            raise _Stopped()

        before = signal.signal(signal.SIGTERM, _terminated)
        try:
            code = p.wait(timeout=limit)
            status = "finished" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            _stop(p)
            status, code = "timed out", 124
        except (KeyboardInterrupt, _Stopped):
            _stop(p)
            status, code = "stopped", 130
        finally:
            signal.signal(signal.SIGTERM, before)
    rec.update(status=status, exit=code, finished=time.strftime("%Y-%m-%dT%H:%M:%S"),
               wall_minutes=round((time.time() - t0) / 60, 1))
    rec.pop("pid", None)
    _put(name, rec)
    print(f"investigation {name}: {status} (exit {code}) in {rec['wall_minutes']} min; log {log}", flush=True)
    return code


class _Stopped(Exception):
    """The runner was sent SIGTERM: its reading is stopped with it, and the stop is recorded."""


def _stop(p: subprocess.Popen) -> None:
    import signal

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            return
        try:
            p.wait(timeout=20)
            return
        except subprocess.TimeoutExpired:
            continue


def listing() -> list[dict]:
    out = []
    for n in names():
        try:
            spec = load(n)
        except ValueError as e:
            out.append({"name": n, "status": "broken", "why": str(e)})
            continue
        st = standing(n)
        est, source, is_max = estimate(spec, st)
        out.append({"name": n, "expedition": spec["expedition"], "subject": spec.get("subject"),
                    "question": spec.get("question"), "timeout": spec.get("timeout"),
                    "est_min": est, "est_source": source, "est_is_max": is_max,
                    "status": st.get("status"), "started": st.get("started"), "finished": st.get("finished"),
                    "wall_minutes": st.get("wall_minutes"), "exit": st.get("exit"),
                    "readings": readings_of(spec)})
    return out


def main(args: list[str]) -> int:
    if args[:1] == ["run"] and len(args) == 2:
        return run(args[1])
    if args[:1] == ["line"] and len(args) == 2:
        print(queue_line(args[1]))
        return 0
    if args[:1] in ([], ["list"]):
        for r in listing():
            extra = f"  {r.get('wall_minutes')} min" if r.get("wall_minutes") is not None else ""
            est = r.get("est_min")
            about = (f"  ~{est:.0f} min ({r.get('est_source')})" if est is not None else "  no time") if "est_min" in r else ""
            print(f"{r['name']:34} {str(r.get('expedition') or ''):18} {r['status']}{extra}{about}")
        return 0
    print("python -m thorp.investigate [list | run NAME | line NAME]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
