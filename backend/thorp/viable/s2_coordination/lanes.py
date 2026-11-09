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
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from thorp import paths, store

LANES = ("mac", "vast")


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
        return Line(text.strip(), lane, "cmd", s[len("cmd:") :].strip())
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


def pending(queue: Path) -> list[str]:
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
    """A `thorp run` or `thorp eval` at sea that this coordinator did not start (queue.sh's old wait)."""
    mine = {str(p) for p in _children}
    for pat in ("thorp run ", "thorp eval "):
        out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True).stdout.split()
        if any(pid not in mine and not _is_child_of_mine(pid) and _local(pid) for pid in out):
            return True
    return False


def _local(pid: str) -> bool:
    """A voyage on this Mac, not the line a charter sends to a hired box over ssh (8 November, 14:22: the parity
    voyage's `ssh ... thorp run ...` held the Mac lane in port for an hour), nor a shell that only names it."""
    cmd = subprocess.run(
        ["ps", "-o", "command=", "-p", pid], capture_output=True, text=True
    ).stdout.strip()
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
        p = subprocess.run(
            ["ps", "-o", "ppid=", "-p", p], capture_output=True, text=True
        ).stdout.strip()
        seen += 1
    return False


def blocked(ln: Line, above: list[Line], at_sea: dict[str, Line | None]) -> str | None:
    """Why this line cannot start yet (None when it can): a run it reads from queued above it or at sea, the same
    run at sea in the other lane, or (for `wait:`) the voyage waited for still queued or at sea."""
    sailing = [x for x in at_sea.values() if x is not None]
    if ln.kind == "wait":
        name = ln.payload
        if any(x.name == name or x.payload == name for x in above + sailing):
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
    lane: str, lines: list[Line], at_sea: dict[str, Line | None], key: bool
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
    return ["uv", "run", "--no-sync", "--project", "backend", "thorp", "run", spec]


def _write_state(running: dict) -> None:
    """What each lane has out, recorded in s2.lanes (the dashboard and the S2 lint read it from there)."""
    from thorp import store
    from thorp.viable.records import Lane

    with store.session() as s:
        for lane, r in running.items():
            s.merge(Lane(lane=lane, line=r["line"].text if r else None, pid=r["proc"].pid if r else None,
                         since=r["since"] if r else None))  # fmt: skip


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

    def default_launch(ln: Line):
        out = None
        if ln.kind == "spec":
            out_path = root / "data" / "runs" / f"{ln.payload}.out"
            out_path.parent.mkdir(
                parents=True, exist_ok=True
            )  # a voyage's log folder is made here, never forgotten
            out = open(out_path, "w")  # noqa: SIM115
        cmd = command(ln)
        p = subprocess.Popen(
            cmd,
            cwd=root,
            shell=isinstance(cmd, str),
            stdout=out or None,
            stderr=subprocess.STDOUT if out else None,
        )  # noqa: S602
        if out:
            out.close()
        return p

    launch = launch or default_launch
    running: dict[str, dict | None] = {lane: None for lane in LANES}
    told: dict[str, str | None] = {lane: None for lane in LANES}
    while True:
        # the lines that ended
        for lane, r in running.items():
            if r and r["proc"].poll() is not None:
                code = r["proc"].returncode
                say(f"[{lane}] {r['line'].text} exited {code}")
                with done.open("a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {r['line'].text} {code}\n")
                _children.discard(r["proc"].pid)
                running[lane] = None
        lines = [parse(t, specs) for t in pending(queue)]
        at_sea = {lane: (r["line"] if r else None) for lane, r in running.items()}
        have_key = key()
        for lane in LANES:
            if running[lane] is not None:
                continue
            ln, why = next_for(lane, lines, at_sea, have_key)
            if ln is None:
                if why and why != told[lane]:
                    say(f"[{lane}] in port: {why}")
                told[lane] = why
                continue
            if lane == "mac" and ln.kind != "wait" and outside():
                if told[lane] != "outside":
                    say("[mac] in port: a voyage started outside the queue is at sea")
                told[lane] = "outside"
                continue
            if not take(queue, ln.text):
                continue  # edited away meanwhile: read the queue again next time
            told[lane] = None
            if ln.kind == "wait":
                say(f"[{lane}] {ln.text}: docked, going on")
                with done.open("a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {ln.text} 0\n")
                continue
            say(f"[{lane}] starting {ln.text}")
            p = launch(ln)
            _children.add(p.pid)
            running[lane] = {"line": ln, "proc": p, "since": time.strftime("%Y-%m-%dT%H:%M:%S")}
            at_sea[lane] = ln
            lines = [x for x in lines if x is not ln]
        try:
            _write_state(running)
        except (
            store.StoreDown
        ) as e:  # said in the queue's log, every pass, until the store is back; the lanes sail on
            say(f"S2: what is out could not be recorded: {e}")
        idle = all(r is None for r in running.values())
        left = [x for x in (parse(t, specs) for t in pending(queue)) if x.lane == "mac" or have_key]
        if until_empty and idle and not left:
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
    try:
        with one_coordinator():
            run()
    except AlreadyRunning as e:
        print(f"[{time.strftime('%H:%M:%S')}] {e}", flush=True)
        sys.exit(1)
    sys.exit(0)
