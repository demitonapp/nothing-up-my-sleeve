"""S2: the coordinator. One standing queue, two lanes: this Mac and a GPU hired from Vast.ai (2026-11-08, Justin:
"we'll need to build the VSM coordinator that then coordinates between vast and then running on this mac").

The standing queue (ships/specs/queue.txt) keeps its rules: a line is taken from the top of its lane, removed when
it starts, and written to queue-done.txt with its exit status when it ends; the file can be edited while the queue
runs. What the coordinator adds:

- **Two lanes.** `vast: <spec>` lines, and any spec whose `model.backend` is torch, sail on the **Vast lane**
  (`thorp charter sail`, within S5's terms: one ship out, $10 a voyage, $30 a week). Every other line (a spec, a
  `cmd:`, a `wait:`) sails on the **Mac lane**, as queue.sh always did. Each lane takes its own lines in order, so
  the Mac keeps sailing while a hired ship is out, where a charter written as a `cmd:` line held it in port.
- **What a line waits for.** A voyage waits while a run it reads from (its seed, its teacher, its heads' donor:
  s2_coordination.charter.related_runs) is still queued above it or at sea, in either lane. The same run never
  sails on both lanes at once. `wait: <name>` holds the Mac lane until that voyage is neither queued nor at sea
  (to score on the Mac what a hired ship brought home, say). A lane waits at its first line: nothing jumps it.
- **No key, no loss.** Without a Vast.ai key the Vast lane's lines stay in the queue, untouched, and the Mac lane
  goes on.
- **The Mac lane** waits, as queue.sh did, while a `thorp run` or `thorp eval` started outside the queue is at
  sea (the helm, vsm.at_sea, is still taken by the voyage itself).
- **What is out:** s2.lanes (Postgres) names each lane's line, its process and since when (the dashboard and the
  S2 lint read it). The queue file's edits are made under a lock (specs/queue.txt.lock).

Run it in place of queue.sh (which now execs it): `uv run --project backend python -m
thorp.viable.s2_coordination.lanes`. Log: data/runs/queue.out, as before.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from thorp import paths, store

LANES = ("mac", "vast")


def slots_of(lane: str) -> int:
    """How many lines this lane may have at sea at once: THORP_MAC_SLOTS for the Mac, else the seats
    `s2.lanes` holds (the dashboard's control, and the value the UI shows), one on a hired box (the
    charter terms count voyages, not seats)."""
    if lane != "mac":
        return 1
    env = os.environ.get("THORP_MAC_SLOTS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    try:
        from thorp import store
        from thorp.viable.records import Lane

        with store.session() as s:
            r = s.get(Lane, "mac")
            if r is not None and r.seats:
                return max(1, min(8, int(r.seats)))
    except Exception:  # noqa: BLE001 - no store on a box: one seat
        pass
    return 1


@dataclass
class Line:
    text: str  # the line as written in the queue
    lane: str  # "mac" or "vast"
    kind: str  # "spec", "cmd" or "wait"
    payload: (
        str  # the spec's path under specs/ (no .yaml), the shell command, or the voyage waited for
    )
    spec: dict | None = None
    run_id: str | None = None
    name: str | None = None
    reads: list[str] = field(
        default_factory=list
    )  # the runs it reads from (seed, teacher, donor), by name
    timeout: int | None = None  # seconds a cmd: line may run; None is no limit


def _load_spec(rel: str, specs: Path) -> dict | None:
    import yaml

    p = specs / f"{rel}.yaml"
    if not p.exists():
        return None
    with contextlib.suppress(Exception):
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    return None


def parse(text: str, specs: Path | None = None) -> Line:
    """One queue line, read: its lane, its kind and (for a voyage) its spec, run id and the runs it reads from."""
    specs = specs or paths.resolve("specs")
    s = text.strip()
    lane = "mac"
    if s.startswith("vast:"):
        lane, s = "vast", s[len("vast:") :].strip()
    if s.startswith("cmd:"):
        body = s[len("cmd:") :].strip()
        # cmd:[timeout=90m] <command>: a queued audit gets a deadline; a bare cmd: keeps running until it
        # ends (the old behaviour). Seconds, minutes (the default) or hours.
        m = re.match(r"\[timeout=(\d+)([smh]?)\]\s*(.+)$", body)
        if m:
            seconds = int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2) or "m"]
            return Line(text.strip(), lane, "cmd", m.group(3).strip(), timeout=seconds)
        return Line(text.strip(), lane, "cmd", body)
    if s.startswith("wait:"):
        return Line(text.strip(), lane, "wait", s[len("wait:") :].strip())
    ln = Line(text.strip(), lane, "spec", s)
    spec = _load_spec(s, specs)
    if spec:
        from thorp import train
        from thorp.viable.s2_coordination.charter import related_runs

        ln.spec, ln.name, ln.reads = spec, spec.get("name"), related_runs(spec)
        with contextlib.suppress(Exception):
            ln.run_id = train.run_id(spec)
        if (spec.get("model") or {}).get("backend") == "torch":
            ln.lane = (
                "vast"  # a voyage written for CUDA sails on a hired GPU, never on this Mac's CPU
            )
    return ln


def _queue_pg() -> bool:
    """The one store answers for the queue: `queue_store.enabled()` (Postgres on the Mac by default)."""
    from thorp.viable.s2_coordination import queue_store

    return queue_store.enabled()


TWO_AT_ONCE = {"300k"}  # the only preset that may share the Mac's GPU with a second line of the same size


def preset_of(ln: Line) -> str | None:
    """The model preset a spec line builds, when it names one."""
    return str(((ln.spec or {}).get("model") or {}).get("preset") or "") or None


def capacity_for(lane: str, lines: list[Line], running: dict[str, list]) -> int:
    """A lane's seats, capped on the Mac so a second seat is used only for 300k-scale lines: two 1m or 9m
    voyages on one GPU do not fit, and the stored seat count is per lane, not per class."""
    cap = slots_of(lane)
    if lane != "mac" or cap <= 1:
        return cap
    nxt = next((ln for ln in lines if ln.lane == lane), None)
    if nxt is None or preset_of(nxt) not in TWO_AT_ONCE:
        return 1
    if any(preset_of(s["line"]) not in TWO_AT_ONCE for s in running.get("mac", [])):
        return 1
    return cap


def pending(queue: Path) -> list[str]:
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        return queue_store.pending_texts()
    if not queue.exists():
        return []
    return [
        ln.strip()
        for ln in queue.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


@contextlib.contextmanager
def _locked(queue: Path):
    import fcntl

    with open(queue.with_name(queue.name + ".lock"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def take(queue: Path, text: str) -> bool:
    """Remove the first copy of this line from the queue (under the lock); False when it is no longer there."""
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        return queue_store.take(text)
    with _locked(queue):
        lines = queue.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, ln in enumerate(lines):
            if ln.strip() == text:
                tmp = queue.with_name(queue.name + ".tmp")
                tmp.write_text("".join(lines[:i] + lines[i + 1 :]), encoding="utf-8")
                tmp.replace(queue)
                return True
    return False


def append(queue: Path, text: str, note: str = "") -> None:
    """Put a line at the end of the queue (under the lock), where a lane finds it last: the place for work caught up
    while a decision waits (DECISIONS.md, "The catch-up rule"). `note`, if given, is written above it as the line's
    own comment, so the queue says why it is there. Refuses a line already queued."""
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        queue_store.add(text)
        return
    with _locked(queue):
        lines = queue.read_text(encoding="utf-8").splitlines(keepends=True)
        if text.strip() in (ln.strip() for ln in lines):
            raise ValueError(f"{text!r} is already queued")
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if note:
            lines.append(f"# {note}\n")
        lines.append(text.strip() + "\n")
        tmp = queue.with_name(queue.name + ".tmp")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(queue)


def append_many(queue: Path, batch: list[str], note: str = "") -> int:
    """Put several lines at the end of the queue in one write, under the lock, `note` written once above them. A
    line already queued is skipped. Returns how many were added, so a caller can say what it did."""
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        added = 0
        for x in batch:
            try:
                queue_store.add(x)
                added += 1
            except ValueError:
                pass
        return added
    with _locked(queue):
        lines = queue.read_text(encoding="utf-8").splitlines(keepends=True)
        have = {ln.strip() for ln in lines}
        add = [x.strip() for x in batch if x.strip() and x.strip() not in have]
        if not add:
            return 0
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if note:
            lines.append(f"# {note}\n")
        lines.extend(f"{x}\n" for x in add)
        tmp = queue.with_name(queue.name + ".tmp")
        tmp.write_text("".join(lines), encoding="utf-8")
        tmp.replace(queue)
        return len(add)


def has_key() -> bool:
    try:
        from thorp.viable.s1_operations import charter

        charter.api_key()
        return True
    except Exception:  # noqa: BLE001  (NoKey, or the charter not importable here)
        return False


def outside_voyage() -> bool:
    """A `thorp run`, `thorp eval` or `thorp.train` at sea that this coordinator did not start
    (queue.sh's old wait). The direct `python -m thorp.train` form is caught too: the four manual
    voyages were started that way, so the coordinator did not see them and launched two more over
    them, putting four ships at sea on a two-seat lane (10 November)."""
    mine = {str(p) for p in _children}
    for pat in ("thorp run ", "thorp eval ", "thorp.train ", "thorp train "):
        out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout.split()
        if any(pid not in mine and not _is_child_of_mine(pid) and _local(pid) for pid in out):
            return True
    return False


def _local(pid: str) -> bool:
    """A voyage on this Mac, not the line a charter sends to a hired box over ssh (8 November, 14:22: the parity
    voyage's `ssh ... thorp run ...` held the Mac lane in port for an hour), nor a shell that only names it."""
    try:
        cmd = subprocess.run(
            ["ps", "-o", "command=", "-p", pid], capture_output=True, text=True
        ).stdout.strip()
    except (PermissionError, FileNotFoundError, OSError):
        return True  # cannot inspect the process list (a sandbox that blocks ps): treat it as local and stay safe
    first = cmd.split(" ", 1)[0].rsplit("/", 1)[-1] if cmd else ""
    return bool(cmd) and first not in ("ssh", "rsync", "scp", "sh", "zsh", "bash")


_children: set[int] = set()


def _is_child_of_mine(pid: str) -> bool:
    """True when the process descends from one this coordinator started (uv runs thorp as a child)."""
    seen = 0
    p = pid
    while p and p not in ("0", "1") and seen < 8:
        if int(p) in _children:
            return True
        try:
            p = subprocess.run(
                ["ps", "-o", "ppid=", "-p", p], capture_output=True, text=True
            ).stdout.strip()
        except (PermissionError, FileNotFoundError, OSError):
            return False  # cannot walk the tree: do not claim it as ours

        seen += 1
    return False


def blocked(ln: Line, above: list[Line], at_sea: list[Line]) -> str | None:
    """Why this line cannot start yet (None when it can): a run it reads from queued above it or at sea, the same
    run at sea in the other lane, or (for `wait:`) the voyage waited for still queued or at sea."""
    sailing = list(at_sea)
    if ln.kind == "wait":
        name = ln.payload
        if any(x.name == name or x.payload == name for x in above + sailing):
            return f"waiting for {name} to dock"
        # a voyage launched outside the queue holds the helm but no lane, so `sailing` is empty and
        # the wait would call it docked (9 November: the 21m, started by hand, was declared docked
        # while it was still training). The helm is the authority.
        with contextlib.suppress(Exception):
            from thorp import vsm

            if (vsm.helm() or {}).get("name") == name:
                return f"waiting for {name} to dock"
        return None
    if ln.kind != "spec":
        return None
    for r in ln.reads:
        if any(x.name == r for x in above):
            return f"reads from {r}, still queued above it"
        if any(x.name == r for x in sailing):
            return f"reads from {r}, still at sea"
    if ln.run_id and any(x.run_id == ln.run_id for x in sailing):
        return "the same run is at sea in the other lane"
    return None


def next_for(
    lane: str, lines: list[Line], at_sea: list[Line], key: bool
) -> tuple[Line | None, str | None]:
    """The line this lane would start now, or (None, why not). A lane waits at its first line: nothing jumps it."""
    if lane == "vast" and not key:
        return None, "no Vast.ai key: the Vast lane's lines wait in the queue"
    for i, ln in enumerate(lines):
        if ln.lane != lane:
            continue
        why = blocked(ln, lines[:i], at_sea)
        return (None, why) if why else (ln, None)
    return None, None


def command(ln: Line) -> list[str] | str:
    """What a lane runs for a line: the voyage (here, or chartered), or the shell command."""
    if ln.kind == "cmd":
        return ln.payload
    spec = f"ships/specs/{ln.payload}.yaml"
    if ln.lane == "vast":
        return [
            "uv",
            "run",
            "--no-sync",  # a launch never depends on uv re-resolving the lock (the 8 November 504 outage)
            "--project",
            "backend",
            "--group",
            "torch",
            "thorp",
            "charter",
            "sail",
            spec,
        ]
    # --no-sync: a launch must never depend on uv re-resolving the lock. On 8 November a spaCy model wheel
    # answered 504 from GitHub and every voyage died in 30 seconds; the environment was intact all along.
    # THORP_LAUNCH=local runs the venv's python directly, for a host where uv cannot write its cache
    # (9 November: every spec launch died with exit 2 until this was set).
    if os.environ.get("THORP_LAUNCH") == "local":
        return [sys.executable, "-m", "thorp.train", spec]
    return ["uv", "run", "--no-sync", "--project", "backend", "thorp", "run", spec]


def _write_state(running: dict) -> None:
    """What each lane has out, recorded in s2.lanes (the dashboard and the S2 lint read it from there)."""
    from thorp import store
    from thorp.viable.records import Lane

    slots = {lane: slots_of(lane) for lane in running}  # before the write session: never nest sessions
    with store.session() as s:
        for lane, seats in running.items():
            first = seats[0] if seats else None
            line = " + ".join(x["line"].text for x in seats) if seats else None
            s.merge(Lane(lane=lane, line=line, pid=first["proc"].pid if first else None,
                         since=first["since"] if first else None, seats=slots[lane]))  # fmt: skip


def state() -> dict:
    """What each lane has out now (s2.lanes), only the lanes whose process is alive."""
    from thorp import store
    from thorp.viable.records import Lane

    with store.session() as s:
        d = {
            r.lane: {"line": r.line, "pid": r.pid, "since": r.since}
            for r in s.query(Lane)
            if r.line
        }
    out = {}
    for lane in LANES:
        r = d.get(lane)
        alive = False
        if r:
            with contextlib.suppress(Exception):
                os.kill(int(r["pid"]), 0)
                alive = True
        out[lane] = r if alive else None
    return out


def _alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class _Adopted:
    """A command this coordinator started before a restart: still alive, but not our child, so there is no
    exit code to collect — poll() reports -1 when the pid is gone."""

    def __init__(self, pid: int):
        self.pid = int(pid)
        self.returncode: int | None = None

    def poll(self) -> int | None:
        if _alive(self.pid):
            return None
        self.returncode = -1
        return -1

    def terminate(self) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(self.pid, 15)

    def kill(self) -> None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(self.pid, 9)


def _stop(proc, grace: float = 2.0) -> int:
    """End a seat's process (a timed-out cmd:), gently then hard; returns the code it left."""
    if proc.poll() is not None:
        return proc.returncode
    with contextlib.suppress(Exception):
        proc.terminate()
    for _ in range(max(1, int(grace / 0.2))):
        time.sleep(0.2)
        if proc.poll() is not None:
            return proc.returncode
    with contextlib.suppress(Exception):
        proc.kill()
    for _ in range(10):
        time.sleep(0.2)
        if proc.poll() is not None:
            return proc.returncode
    return -9


def _procs_path(root: Path | None = None) -> Path:
    return (root or paths.ROOT) / "data" / "queue-procs.json"


def _write_procs(running: dict, root: Path | None = None) -> None:
    """Keep the pids of what is out, so a restarted coordinator can adopt a live `cmd:` instead of starting
    another over it. Process state, not queue state: the queue itself is the store."""
    entries = []
    for lane, seats in running.items():
        for seat in seats:
            entries.append(
                {
                    "lane": lane,
                    "text": seat["line"].text,
                    "kind": seat["line"].kind,
                    "pid": seat["proc"].pid,
                    "since": seat.get("since"),
                    "started": seat.get("started") or seat.get("since"),
                    "since_ts": seat.get("since_ts"),
                    "slot": seat.get("slot", 0),
                }
            )
    p = _procs_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries), encoding="utf-8")
    tmp.replace(p)


def _read_procs(root: Path | None = None) -> list[dict]:
    p = _procs_path(root)
    if not p.exists():
        return []
    with contextlib.suppress(Exception):
        return json.loads(p.read_text(encoding="utf-8")) or []
    return []


def _reap_runs(say) -> int:
    """Close ledger rows still marked running that hold no helm and started over an hour ago. A voyage killed
    with a signal never writes a finish, so without this they return as ghosts on every page (10 November:
    nine 9m/1m arms). The hour keeps a run launched a moment ago, before it takes its helm, out of it."""
    if not _queue_pg():
        return 0  # the file queue's ledger is a box's SQLite; nothing to reap from the store here
    from datetime import datetime

    from sqlalchemy import text

    from thorp import store, vsm

    live = {h.get("name") for h in vsm.helms(8)}
    cutoff = time.time() - 3600
    with store.session() as s:
        rows = s.execute(
            text("select run_id, name, started from s1.runs where status='running'")
        ).fetchall()
        stale = []
        for run_id, name, started in rows:
            if name in live:
                continue
            try:
                ts = datetime.fromisoformat(str(started)).timestamp()
            except (TypeError, ValueError):
                continue  # no start time: leave it, do not guess
            if ts < cutoff:
                stale.append(run_id)
        for run_id in stale:
            s.execute(
                text("update s1.runs set status='stopped' where run_id=:rid"), {"rid": run_id}
            )
    if stale:
        say(f"S2: closed {len(stale)} run(s) the ledger still had at sea, with no helm")
    return len(stale)


def _record(done: Path, text: str, started: str, status) -> None:
    """Write a line that ended to queue-done.txt, or to queue_history when the store is the queue. If the
    store refuses it, keep it in the file and carry on: a record must never kill the coordinator (10
    November: a stale id sequence took the queue down on the exit of a finished voyage)."""
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        try:
            queue_store.record(text, started, status)
            return
        except Exception as e:  # noqa: BLE001 - the file keeps what the store could not
            print(
                f"[{time.strftime('%H:%M:%S')}] queue_history could not record {text}: {e}"
                f"; kept in {done}",
                flush=True,
            )
    with done.open("a", encoding="utf-8") as f:
        f.write(f"{started} {text} {status}\n")


def run(queue: Path | None = None, done: Path | None = None, root: Path | None = None,
        poll_s: float = 30.0, key=has_key, outside=outside_voyage, launch=None, log=None, until_empty: bool = True) -> None:  # fmt: skip
    """The coordinator's loop: start each idle lane's next line, record each line that ends, until the queue is
    empty and both lanes are in port."""
    queue = queue or paths.resolve("specs/queue.txt")
    done = done or paths.resolve("specs/queue-done.txt")
    root = root or paths.ROOT
    specs = queue.parent

    def say(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        (log or (lambda m: print(m, flush=True)))(line)

    def default_launch(ln: Line, slot: int = 0):
        out = None
        if ln.kind == "spec":
            out_path = root / "data" / "runs" / f"{ln.payload}.out"
            out_path.parent.mkdir(
                parents=True, exist_ok=True
            )  # a voyage's log folder is made here, never forgotten
            out = open(out_path, "w")  # noqa: SIM115
        elif ln.kind == "cmd":
            # a queued audit or probe gets its own log, not the coordinator's: `cmd:` output interleaved
            # into queue.out is unreadable exactly when the audit is the thing you are watching for
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", ln.payload).strip("-")[:70] or "cmd"
            out_path = root / "data" / "runs" / f"cmd-{slug}.out"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out = open(out_path, "w")  # noqa: SIM115
        cmd = command(ln)
        env = {**os.environ, "THORP_HELM_SLOT": str(slot), "THORP_HELM_SLOTS": str(slots_of("mac"))}
        p = subprocess.Popen(
            cmd,
            cwd=root,
            shell=isinstance(cmd, str),
            stdout=out or None,
            stderr=subprocess.STDOUT if out else None,
            env=env,
        )  # noqa: S602
        if out:
            out.close()
        return p

    custom = launch is not None
    launch = launch or default_launch
    running: dict[str, list[dict]] = {lane: [] for lane in LANES}
    told: dict[str, str | None] = {lane: None for lane in LANES}
    attempts: dict[str, int] = {}
    # adopt what a crashed coordinator left running: a `cmd:` holds no helm, so nothing else knows it is out
    for e in _read_procs(root):
        if e.get("kind") != "cmd" or not _alive(int(e.get("pid") or 0)):
            continue
        ln = parse(str(e.get("text") or ""), specs)
        if ln.kind != "cmd":
            continue
        lane = e.get("lane") if e.get("lane") in LANES else "mac"
        since = e.get("since") or time.strftime("%Y-%m-%dT%H:%M:%S")
        running[lane].append(
            {
                "line": ln,
                "proc": _Adopted(int(e["pid"])),
                "since": since,
                "started": e.get("started") or since,
                "since_ts": float(e.get("since_ts") or time.time()),
                "slot": int(e.get("slot") or 0),
            }
        )
        say(f"[{lane}] adopted {ln.text} (pid {e['pid']})")
    try:
        _reap_runs(say)
    except Exception as e:  # noqa: BLE001 - a cleanup must never stop the queue
        say(f"S2: could not close stale runs: {e}")
    while True:
        # the seats that ended (a lane may hold several now)
        for lane, seats in running.items():
            for seat in list(seats):
                code = seat["proc"].poll()
                timeout = seat["line"].timeout
                if (
                    code is None
                    and timeout
                    and time.time() - float(seat.get("since_ts") or time.time()) > timeout
                ):
                    label = f"{timeout // 60} min" if timeout >= 60 else f"{timeout} s"
                    say(f"[{lane}] {seat['line'].text} timed out after {label}")
                    code = _stop(seat["proc"])
                if code is not None:
                    say(f"[{lane}] {seat['line'].text} exited {code}")
                    _record(
                        done,
                        seat["line"].text,
                        seat.get("started")
                        or seat.get("since")
                        or time.strftime("%Y-%m-%dT%H:%M:%S"),
                        code,
                    )
                    _children.discard(seat["proc"].pid)
                    attempts.pop(seat["line"].text, None)
                    seats.remove(seat)
        try:
            raw = pending(queue)
        except store.StoreDown as e:  # the store is the queue: wait for it, do not die on it
            say(f"S2: the queue could not be read: {e}")
            time.sleep(poll_s)
            continue
        lines = []
        for t in raw:
            try:
                lines.append(parse(t, specs))
            except Exception as e:  # noqa: BLE001 - one unreadable line must not stop the lane
                say(f"S2: cannot read the queue line {t!r}: {e}")
        have_key = key()
        for lane in LANES:
            capacity = capacity_for(lane, lines, running)
            while len(running[lane]) < capacity:
                at_sea = [seat["line"] for seats in running.values() for seat in seats]
                ln, why = next_for(lane, lines, at_sea, have_key)
                if ln is None:
                    if why and why != told[lane]:
                        say(f"[{lane}] in port: {why}")
                    told[lane] = why
                    break
                if lane == "mac" and ln.kind != "wait" and outside():
                    if told[lane] != "outside":
                        say("[mac] in port: a voyage started outside the queue is at sea")
                    told[lane] = "outside"
                    break
                if not take(queue, ln.text):
                    break  # edited away meanwhile: read the queue again next time
                told[lane] = None
                if ln.kind == "wait":
                    say(f"[{lane}] {ln.text}: docked, going on")
                    _record(done, ln.text, time.strftime("%Y-%m-%dT%H:%M:%S"), 0)
                    lines = [x for x in lines if x is not ln]
                    continue
                say(f"[{lane}] starting {ln.text}")
                seat_no = len(running[lane])
                try:
                    p = launch(ln) if custom else launch(ln, seat_no)
                except Exception as e:  # noqa: BLE001 - one broken line must not take the queue down
                    # the line was taken; retry it twice (requeued at the end, so it cannot wedge the head),
                    # then record the failure and let the queue go on
                    n = attempts.get(ln.text, 0) + 1
                    attempts[ln.text] = n
                    if n < 3:
                        say(f"[{lane}] {ln.text} could not start (attempt {n}/3): {e}")
                        with contextlib.suppress(Exception):
                            append(queue, ln.text)
                    else:
                        say(f"[{lane}] {ln.text} could not start after 3 attempts: {e}")
                        _record(done, ln.text, time.strftime("%Y-%m-%dT%H:%M:%S"), 1)
                        attempts.pop(ln.text, None)
                    lines = [x for x in lines if x is not ln]
                    continue
                _children.add(p.pid)
                now = time.strftime("%Y-%m-%dT%H:%M:%S")
                running[lane].append(
                    {
                        "line": ln,
                        "proc": p,
                        "since": now,
                        "started": now,
                        "since_ts": time.time(),
                        "slot": seat_no,
                    }
                )
                lines = [x for x in lines if x is not ln]
        try:
            _write_state(running)
        except Exception as e:  # noqa: BLE001 - what is out is a record, not the work: the lanes sail on
            say(f"S2: what is out could not be recorded: {e}")
        with contextlib.suppress(Exception):
            _write_procs(running, root)
        idle = all(len(seats) == 0 for seats in running.values())
        left = [x for x in (parse(t, specs) for t in pending(queue)) if x.lane == "mac" or have_key]
        if until_empty and idle and not left:
            with contextlib.suppress(Exception):
                _write_procs({}, root)
            say(
                "queue empty"
                + (
                    ""
                    if have_key or not pending(queue)
                    else " (the Vast lane's lines wait for a key)"
                )
            )
            return
        time.sleep(poll_s)


class AlreadyRunning(RuntimeError):
    pass


@contextlib.contextmanager
def one_coordinator(lock_path: Path | None = None):
    """Only one coordinator at a time (two would mean two Mac lanes, two voyages on one GPU): hold its lock for
    the length of the run, refuse at once when another holds it."""
    import fcntl

    p = lock_path or paths.data_dir() / "lanes.lock"
    p.parent.mkdir(parents=True, exist_ok=True)
    f = open(p, "a+")  # noqa: SIM115
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            raise AlreadyRunning(
                f"another coordinator holds {p}: the queue is already running"
            ) from e
        yield
    finally:
        f.close()


if __name__ == "__main__":
    os.chdir(paths.ROOT)
    if _queue_pg():
        why = store.ping()
        if why:
            print(f"[{time.strftime('%H:%M:%S')}] the queue is the store, and the store is not answering: {why}", flush=True)
            print("  fix Postgres, or set THORP_QUEUE_PG=0 to run the file queue", flush=True)
            sys.exit(1)
    try:
        with one_coordinator():
            run()
    except AlreadyRunning as e:
        print(f"[{time.strftime('%H:%M:%S')}] {e}", flush=True)
        sys.exit(1)
    sys.exit(0)
