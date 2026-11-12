"""S2: the coordinator. One standing queue, two lanes: this Mac and a GPU hired from Vast.ai (2026-11-08, Justin:
"we'll need to build the Liberty Machine coordinator that then coordinates between vast and then running on this mac").

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
  sea (the helm, liberty_machine.at_sea, is still taken by the voyage itself).
- **What is out:** s2.lanes (Postgres) names each lane's line, its process and since when (the dashboard and the
  S2 lint read it). The queue file's edits are made under a lock (specs/queue.txt.lock).
- **What is at sea is a row** (11 November, the architecture audit's item 2). A line that starts moves from
  `s2.queue_lines` to `s2.at_sea` in one transaction, its pid is written the moment its process exists, and the
  row is deleted in the transaction that writes its `s2.queue_history`. A coordinator that starts adopts every
  row: a live process that is plausibly that line keeps its seat and is watched to its end (a voyage's outcome
  then read from the ledger, since only a parent can collect an exit status); a dead one is recorded as `lost`
  and its seat freed. Nothing is requeued without a person: a lost voyage may have a checkpoint, or a box.
- **A coordinator's death is not its children's.** Each line is launched in its own session, so a signal to the
  coordinator's process group (launchd ending the job) does not reach it; whatever stops a line signals the
  line's own group.

Run it in place of queue.sh (which now execs it): `uv run --project backend python -m
thorp.viable.s2_coordination.lanes`. Log: data/runs/queue.out, as before.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from thorp import paths, store

LANES = ("mac", "vast")  # today's two lanes: the fallback when s2.lane_defs cannot be read (a box, a test, no store)

# ---------------------------------------------------------------- the lanes are rows (11 November, item 11)
#
# `s2.lane_defs` holds one row a lane: its kind (`local`: launched on this Mac; `charter`: `thorp charter sail` on
# a hired GPU), its seats, the presets that may share its seats, its resource, whether it is enabled. A third lane
# is a row; a new *kind* is a launcher in `command` as well (until then it takes nothing, and says why). For the two
# lanes of 11 November the rows say what the constants said, so the coordinator behaves exactly as before.

KINDS = ("local", "charter")  # the kinds this coordinator can launch
RESERVED = ("cmd", "wait", "hold")  # line prefixes that are kinds of line, never lane names
LANE_DEFS_TTL_S = 20.0


@dataclass(frozen=True)
class LaneDef:
    lane: str
    kind: str  # "local" or "charter"; another kind takes nothing until it has a launcher
    seats: int | None = None  # a local lane's seats when s2.lanes holds none (the dashboard's control wins)
    shared_presets: frozenset = frozenset()  # presets that may share seats; empty: any line may take any seat
    resource_id: str | None = None
    enabled: bool = True
    note: str = ""


def _default_defs() -> dict[str, LaneDef]:
    """What the constants said before the rows: the Mac (local, 300k may share) and Vast (charter, one seat)."""
    return {
        "mac": LaneDef("mac", "local", None, frozenset(TWO_AT_ONCE)),
        "vast": LaneDef("vast", "charter", 1, frozenset()),
    }


_DEFS: dict = {"at": float("-inf"), "defs": None}


def _read_defs() -> dict[str, LaneDef] | None:
    """The rows of s2.lane_defs, local lanes first; None when the table cannot be read or is empty."""
    from sqlalchemy import text

    with store.session() as s:
        rows = s.execute(
            text(
                "select lane, kind, seats, shared_presets, resource_id, enabled, note from s2.lane_defs "
                "order by case kind when 'local' then 0 when 'charter' then 1 else 2 end, lane"
            )
        ).fetchall()
    out = {
        r[0]: LaneDef(r[0], r[1], r[2], frozenset(r[3] or ()), r[4], bool(r[5]), r[6] or "")
        for r in rows
        if r[0] not in RESERVED
    }
    return out or None


def lane_defs(fresh: bool = False) -> dict[str, LaneDef]:
    """Every lane, enabled or not, in order (read at most every LANE_DEFS_TTL_S); today's two when the table
    cannot be read or holds nothing, so a box, a unit test or a store not yet migrated sails as before."""
    if fresh or _DEFS["defs"] is None or time.monotonic() - _DEFS["at"] > LANE_DEFS_TTL_S:
        try:
            defs = _read_defs()
        except Exception:  # noqa: BLE001 - no store, no table: the constants
            defs = None
        _DEFS.update(at=time.monotonic(), defs=defs or _default_defs())
    return _DEFS["defs"]


def lane_names() -> tuple[str, ...]:
    """Every defined lane (a disabled one still has what it had out watched home)."""
    return tuple(lane_defs())


def enabled_lanes() -> tuple[str, ...]:
    return tuple(k for k, d in lane_defs().items() if d.enabled)


def kind_of(lane: str) -> str:
    d = lane_defs().get(lane)
    return d.kind if d else ("charter" if lane == "vast" else "local")


def _charter_lane() -> str:
    """Where a voyage written for CUDA sails: the Vast lane, else the first charter lane defined."""
    defs = lane_defs()
    if "vast" in defs or not any(d.kind == "charter" for d in defs.values()):
        return "vast"
    return next(k for k, d in defs.items() if d.kind == "charter")


def split_lane(s: str) -> tuple[str, str]:
    """A queue line's lane prefix (`vast: <spec>`, or `<lane>: <spec>` for any lane defined) and the rest; the Mac
    when it names none. `cmd:`, `wait:` and `hold:` are kinds of line, never lanes."""
    s = s.strip()
    m = re.match(r"([A-Za-z][A-Za-z0-9_-]*):", s)
    if m and m.group(1) == "mac":
        # `mac: <spec>` pins a line here, so the purser leaves it alone (12 November: a line the purser sent
        # abroad comes back pinned if its charter fails). Before this the prefix was kept as part of the spec's
        # path, so a `mac:` line could never be read.
        return "mac", s[m.end() :].strip()
    if m and m.group(1) not in RESERVED and m.group(1) in lane_defs():
        return m.group(1), s[m.end() :].strip()
    return "mac", s


def pinned(text: str) -> bool:
    """A line that names its lane (`mac:` or `vast:`, or any lane s2.lane_defs names): the purser never moves it."""
    m = re.match(r"\s*([A-Za-z][A-Za-z0-9_-]*):", text)
    return bool(m) and m.group(1) not in RESERVED and (m.group(1) == "mac" or m.group(1) in lane_defs())


def helm_offset(lane: str) -> int:
    """The first helm slot a local lane's seats use: the seats of the local lanes before it, so two local lanes
    never share a helm slot (0 for the Mac, whose slots are as they were)."""
    off = 0
    for k, d in lane_defs().items():
        if k == lane:
            return off
        if d.kind == "local" and d.enabled:
            off += slots_of(k)
    return off


def helm_slots_total() -> int:
    """Every helm slot the local lanes use (the Mac's seats alone, while it is the only local lane)."""
    return max(1, sum(slots_of(k) for k, d in lane_defs().items() if d.kind == "local" and d.enabled))


def slots_of(lane: str) -> int:
    """How many lines this lane may have at sea at once. A local lane: THORP_<LANE>_SLOTS (THORP_MAC_SLOTS for the
    Mac), else the seats `s2.lanes` holds (the dashboard's control, and the value the UI shows), else its row's
    seats, else one. A charter lane: its row's seats, one on a hired box today (the charter terms count voyages,
    not seats). A lane no row defines: one."""
    d = lane_defs().get(lane)
    if d is None:
        return 1
    if d.kind != "local":
        return max(1, int(d.seats or 1))
    env = os.environ.get(f"THORP_{lane.upper().replace('-', '_')}_SLOTS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    try:
        from thorp import store
        from thorp.viable.records import Lane

        with store.session() as s:
            r = s.get(Lane, lane)
            if r is not None and r.seats:
                return max(1, min(8, int(r.seats)))
    except Exception:  # noqa: BLE001 - no store on a box: one seat
        pass
    if d.seats:
        return max(1, min(8, int(d.seats)))
    return 1


# S4's scheduled intelligence audit is written as a `cmd:` line (AUDIT_LINE below), so every reader that knows a
# line by its text still sees a command; its *kind* is its own, so the queue page can draw it apart from a step.
INTELLIGENCE_MARK = "thorp.viable.s3_control.cycle run --judge"


def is_intelligence(text: str) -> bool:
    """Whether a queue line is S4's scheduled intelligence audit (the queue's own item, not a general step)."""
    return INTELLIGENCE_MARK in text


@dataclass
class Line:
    text: str  # the line as written in the queue
    lane: str  # "mac" or "vast"
    kind: str  # "spec", "cmd", "intelligence", "wait" or "hold"
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
    routed: bool = False  # the purser sent it abroad (S5's `purser` term `routing`): a failure abroad comes home


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
    lane, s = split_lane(text)  # `vast: <spec>`, or any lane s2.lane_defs names (11 November, item 11)
    if s.startswith("cmd:"):
        body = s[len("cmd:") :].strip()
        kind = "intelligence" if is_intelligence(s) else "cmd"
        # cmd:[timeout=90m] <command>: a queued audit gets a deadline; a bare cmd: keeps running until it
        # ends (the old behaviour). Seconds, minutes (the default) or hours.
        m = re.match(r"\[timeout=(\d+)([smh]?)\]\s*(.+)$", body)
        if m:
            seconds = int(m.group(1)) * {"s": 1, "m": 60, "h": 3600}[m.group(2) or "m"]
            return Line(text.strip(), lane, kind, m.group(3).strip(), timeout=seconds)
        ln = Line(text.strip(), lane, kind, body)
        with contextlib.suppress(Exception):
            from thorp import investigate

            inv = investigate.of_line(text)  # an investigation queued beside the voyages (11 November)
            if inv:
                ln.name = inv["name"]
        return ln
    if s.startswith("wait:"):
        return Line(text.strip(), lane, "wait", s[len("wait:") :].strip())
    if s.startswith("hold:"):
        # hold: <what is being signed> (11 November, Justin: "can we encode hold in the queue primitive?"). The
        # lane waits here, as it does at any first line, until the line is released (`thorp queue release`):
        # a sign-off is a line of the queue, with its rule written on it, not a file beside it.
        return Line(text.strip(), lane, "hold", s[len("hold:") :].strip())
    ln = Line(text.strip(), lane, "spec", s)
    spec = _load_spec(s, specs)
    if spec:
        from thorp import train
        from thorp.viable.s2_coordination.charter import related_runs

        ln.spec, ln.name, ln.reads = spec, spec.get("name"), related_runs(spec)
        with contextlib.suppress(Exception):
            ln.run_id = train.run_id(spec)
        with contextlib.suppress(Exception):
            # the id the voyage will really sail under: train.load_spec adds the ladder's evaluators before
            # the id is computed, so the raw YAML's id is another run's (11 November: the 9m@v0.0.6 at-sea
            # row said 4e4b5225, the trainer 136246a7). A copy: the spec read here stays as written.
            import copy

            from thorp import ladder

            sailed = copy.deepcopy(spec)
            ladder.ensure(sailed)
            ln.run_id = train.run_id(sailed)
        if (spec.get("model") or {}).get("backend") == "torch" and kind_of(ln.lane) != "charter":
            ln.lane = (
                _charter_lane()  # a voyage written for CUDA sails on a hired GPU, never on this Mac's CPU
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
    voyages on one GPU do not fit, and the stored seat count is per lane, not per class. The cap is the lane
    row's `shared_presets` ({300k} on the Mac; a lane with none uses every seat for any line); a disabled lane,
    or one of a kind with no launcher, takes nothing."""
    d = lane_defs().get(lane)
    if d is not None and (not d.enabled or d.kind not in KINDS):
        return 0
    cap = slots_of(lane)
    shared = d.shared_presets if d is not None else (frozenset(TWO_AT_ONCE) if lane == "mac" else frozenset())
    if not shared or cap <= 1:
        return cap
    nxt = next((ln for ln in lines if ln.lane == lane), None)
    if nxt is None or preset_of(nxt) not in shared:
        return 1
    if any(preset_of(s["line"]) not in shared for s in running.get(lane, [])):
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

        queue_store.add(text, require_goal=False)  # a line the coordinator already held, put back
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
                queue_store.add(x, require_goal=False)
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


def ship_out() -> str | None:
    """Why the Vast lane must not hire now (None when it may): S3's spend log already has as many ships out
    as the terms allow, and no seat of this lane is sailing them (the lane asks only when it has a seat
    free). That is a charter that died with its ship still hired, or one sailed by hand. The gate would
    refuse each line in turn for "already hired" and the lane would write its whole queue to the history
    as failures; it waits instead, and says what will free it (11 November)."""
    try:
        from thorp.viable.s3_control import charter as s3
        from thorp.viable.s5_policy import charter as s5

        out = s3.out_now()
        if out and len(out) >= int(s5.terms().get("max_instances", 1)):
            h = out[0]
            return (
                f"instance {h.get('instance')} ({h.get('name')}) is still hired and no line here is sailing it: "
                f"thorp charter attach {h.get('run_id')}, or thorp charter audit"
            )
    except Exception:  # noqa: BLE001 - no store, no terms: the gate still stands behind the lane
        return None
    return None


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
    if ln.kind == "hold":
        return f"held: {ln.payload}"  # until it is released: nothing behind it starts, on either seat
    if ln.kind == "wait":
        name = ln.payload
        if any(x.name == name or x.payload == name for x in above + sailing):
            return f"waiting for {name} to dock"
        # a voyage launched outside the queue holds the helm but no lane, so `sailing` is empty and
        # the wait would call it docked (9 November: the 21m, started by hand, was declared docked
        # while it was still training). The helm is the authority.
        with contextlib.suppress(Exception):
            from thorp import liberty_machine

            if (liberty_machine.helm() or {}).get("name") == name:
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
    if kind_of(lane) == "charter" and not key:
        return None, "no Vast.ai key: the Vast lane's lines wait in the queue"
    for i, ln in enumerate(lines):
        if ln.lane != lane:
            continue
        why = blocked(ln, lines[:i], at_sea)
        return (None, why) if why else (ln, None)
    return None, None


def command(ln: Line) -> list[str] | str:
    """What a lane runs for a line: the voyage (here, or chartered), or the shell command."""
    if ln.kind in ("cmd", "intelligence"):
        return ln.payload
    spec = f"ships/specs/{ln.payload}.yaml"
    kind = kind_of(ln.lane)
    if kind not in KINDS:  # a lane row of a kind this coordinator has no launcher for (11 November, item 11)
        raise NotImplementedError(
            f"lane {ln.lane!r} is of kind {kind!r}, which has no launcher (have: {', '.join(KINDS)}): "
            "teach lanes.command to launch it"
        )
    if kind == "charter" and os.environ.get("THORP_LAUNCH") == "local":
        # the venv's python, as the Mac lane under launchd (12 November: the purser's first routed voyages; uv
        # has failed on its cache under launchd, and the venv already carries the torch group)
        return [sys.executable, "-m", "thorp", "charter", "sail", spec]
    if kind == "charter":
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
    for lane in lane_names():
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


def _group_of(pid: int) -> int | None:
    """The process group this pid leads, when it leads one of its own. Every line is launched in its own
    session (11 November), so stopping one must signal its whole group or what it started is orphaned. None
    when the process shares this coordinator's group (a launcher that started no session): that group holds
    the coordinator itself and is never signalled."""
    try:
        g = os.getpgid(int(pid))
    except (ProcessLookupError, PermissionError, OSError):
        return None
    return g if g == int(pid) and g != os.getpgrp() else None


def _signal(pid: int, sig: int, group: int | None = None) -> None:
    """Signal a seat's process: its whole group when it leads one, else the process alone."""
    group = group if group is not None else _group_of(pid)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        if group:
            os.killpg(group, sig)
        else:
            os.kill(int(pid), sig)


class _Adopted:
    """A line a coordinator started before a restart: still alive, but not our child, so there is no exit
    code to collect. When the pid is gone poll() reports what `outcome` says (a voyage's status on the
    ledger), or -1 when no outcome was given."""

    def __init__(self, pid: int, outcome=None):
        self.pid = int(pid)
        self.returncode: int | str | None = None
        self._outcome = outcome

    def poll(self) -> int | str | None:
        if _alive(self.pid):
            return None
        if self.returncode is None:
            self.returncode = self._outcome() if self._outcome else -1
        return self.returncode

    def terminate(self) -> None:
        _signal(self.pid, signal.SIGTERM)

    def kill(self) -> None:
        _signal(self.pid, signal.SIGKILL)


def _stop(proc, grace: float = 2.0) -> int:
    """End a seat's process (a timed-out cmd:) and everything it started, gently then hard; returns the
    code it left. The group is read before the first signal: once its leader has gone it cannot be asked."""
    if proc.poll() is not None:
        return proc.returncode
    group = _group_of(proc.pid)
    _signal(proc.pid, signal.SIGTERM, group)
    for _ in range(max(1, int(grace / 0.2))):
        time.sleep(0.2)
        if proc.poll() is not None:
            break
    else:
        _signal(proc.pid, signal.SIGKILL, group)
        for _ in range(10):
            time.sleep(0.2)
            if proc.poll() is not None:
                break
    if group:  # what the leader left behind in its group (a child that ignored the first signal)
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(group, signal.SIGKILL)
    return proc.returncode if proc.poll() is not None else -9


def _is_that_job(pid: int, ln: Line) -> bool:
    """Whether a live pid is plausibly the process launched for this line, read from its command line: a pid
    kept in a row can have been given to another process since. A voyage's command names its spec file; a
    `cmd:` is the shell running the command, or the command itself where the shell exec'd it. Where the
    process list cannot be read (a sandbox that blocks ps) the answer is yes: hold the seat and stay safe."""
    try:
        r = subprocess.run(
            ["ps", "-ww", "-o", "command=", "-p", str(int(pid))], capture_output=True, text=True
        )
    except (PermissionError, FileNotFoundError, OSError):
        return True
    cmd = " ".join(r.stdout.split())
    if not cmd:
        return True  # it answers a signal and ps shows nothing: hidden from us, not gone
    if ln.kind == "spec":
        return f"{ln.payload}.yaml" in cmd

    def squash(x: str) -> str:
        return " ".join(x.replace('"', "").replace("'", "").split())

    # the shell takes a command's leading NAME=value assignments into the environment, so ps never shows
    # them: `PYTHONPATH=backend backend/.venv/bin/python -m ...` runs as `backend/.venv/bin/python -m ...`
    # (12 November: a restart would have called the live ARC investigation lost and freed its seat)
    words = ln.payload.split()
    while words and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
        words.pop(0)
    payload = " ".join(words)
    if squash(payload) and squash(payload) in squash(cmd):
        return True
    first = (payload.split() or [""])[0].rsplit("/", 1)[-1]
    return bool(first) and any(w.rsplit("/", 1)[-1] == first for w in cmd.split())


def _ledger_status(run_id: str | None, name: str | None = None, since: str | None = None) -> str | None:
    """A run's status on the ledger, or None when it has no row (or the ledger cannot be asked). With no
    row under the id, the newest run of that `name` started no earlier than `since` (the line's launch, the
    coordinator's local ISO time) answers: an at-sea row written before 11 November's id fix carries the
    raw YAML's id, not the one the voyage sailed under, and an older voyage of the same name never does."""
    if not run_id and not name:
        return None
    with contextlib.suppress(Exception):
        from datetime import datetime

        from thorp.ledger import close_reader, reader

        try:
            r = reader().get_run(run_id) if run_id else None
            if r is None and name:
                r = reader().get_run_by_name(name)
                if r is not None and since:
                    began = datetime.fromisoformat(str(r.get("started")))
                    launched = datetime.fromisoformat(str(since))
                    began = began if began.tzinfo else began.astimezone()
                    launched = launched if launched.tzinfo else launched.astimezone()
                    if (began - launched).total_seconds() < -120:  # a voyage before this line's launch
                        r = None
            return (r or {}).get("status")
        finally:
            close_reader()
    return None


def _outcome(ln: Line, gone: bool = False, since: str | None = None) -> str:
    """What to record for a line whose exit this coordinator could not collect, because it was not the
    process's parent. A voyage's outcome is its status on the ledger (`adopted:finished`; a row still
    'running' with its process gone is `adopted:unfinished`). `gone` is a process found dead at start-up:
    unless the ledger says the voyage finished, it is `lost`. One word, so the file queue's history line
    (`<started> <line> <status>`) still parses."""
    status = _ledger_status(ln.run_id, ln.name, since) if ln.kind == "spec" else None
    if status == "finished" or (status and not gone):
        return "adopted:" + ("unfinished" if status == "running" else "-".join(str(status).split()))
    return "lost" if gone else "adopted:exit-unknown"


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


def _covered(running: dict | None = None) -> tuple[set, set]:
    """What is at sea now, as (run names, run ids): a live helm, a live at-sea row, a box still hired, and the
    seats this coordinator is watching. A run so covered is never a ghost though it holds no helm here (11
    November: a chartered voyage's row comes home 'running' with each pull and never takes this Mac's helm, so a
    coordinator restarted mid-charter would have closed it)."""
    from thorp import liberty_machine

    live = {h.get("name") for h in liberty_machine.helms(8)}
    held: set = set()
    with contextlib.suppress(Exception):
        from thorp.viable.s2_coordination import queue_store

        held |= {r["run_id"] for r in queue_store.at_sea() if r["pid"] and _alive(r["pid"])}
    with contextlib.suppress(Exception):
        from thorp.viable.s3_control import charter as s3

        held |= {h.get("run_id") for h in s3.out_now()}
    for seats in (running or {}).values():
        for seat in seats:
            ln = seat.get("line")
            if ln is not None:
                held.add(ln.run_id)
                live.add(ln.name)
    held.discard(None)
    live.discard(None)
    return live, held


SWEEP_EVERY_S = 300.0  # how often the coordinator looks for runs whose heartbeat has stopped


def _sweep_lost(running: dict, say) -> list[str]:
    """Mark lost every `running` state row with no heartbeat for run_state.LOST_AFTER_S that nothing at sea covers
    (11 November, item 11): what the start-up reaper guessed once from an hour's age, judged every few minutes from
    the heartbeat. Only with the store as the queue (the file queue's ledger is a box's SQLite)."""
    if not _queue_pg():
        return []
    from thorp import run_state

    live, held = _covered(running)
    return run_state.sweep(held, live, say=say)


def _reap_runs(say) -> int:
    """Close ledger rows still marked running that hold no helm and started over an hour ago. A voyage killed
    with a signal never writes a finish, so without this they return as ghosts on every page (10 November:
    nine 9m/1m arms). The hour keeps a run launched a moment ago, before it takes its helm, out of it."""
    if not _queue_pg():
        return 0  # the file queue's ledger is a box's SQLite; nothing to reap from the store here
    from datetime import datetime

    from sqlalchemy import text

    from thorp import store

    live, held = _covered()
    cutoff = time.time() - 3600
    with store.session() as s:
        # a run with a state row is the heartbeat's to judge (run_state.sweep, every loop); this guess is kept for
        # the runs from before the rows (11 November, item 11)
        stated = s.scalar(text("select to_regclass('s1.run_state') is not null"))
        rows = s.execute(
            text(
                "select run_id, name, started from s1.runs r where status='running'"
                + (" and not exists (select 1 from s1.run_state t where t.run_id = r.run_id)" if stated else "")
            )
        ).fetchall()
        stale = []
        for run_id, name, started in rows:
            if name in live or run_id in held:
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


_unsunk: set[int] = set()  # at-sea rows whose line is in the history but which could not be deleted yet


def _leave_sea(row: int | None) -> None:
    """Delete an at-sea row outside the history's own transaction (a failed launch, the file queue, a history
    kept in the file). A row that cannot be deleted now is kept in `_unsunk` and tried again each loop: left
    in the table it would be adopted as a lost voyage at the next start."""
    if row is None:
        return
    try:
        from thorp.viable.s2_coordination import queue_store

        queue_store.from_sea(row)
        _unsunk.discard(row)
    except Exception:  # noqa: BLE001 - the store is away: try again next loop
        _unsunk.add(row)


def _to_sea(queue: Path, ln: Line, lane: str, seat: int, now: str, say) -> tuple[bool, int | None]:
    """Take a line from the queue and write its at-sea row; returns (taken, the row's id). With the store as
    the queue both happen in one transaction (queue_store.take_to_sea). If the row cannot be written (the
    table not migrated yet, say) the line is taken as before and sails without one: a record must never hold
    the queue in port."""
    from thorp.viable.s2_coordination import queue_store

    fields = {
        "lane": lane, "seat": seat, "kind": ln.kind, "name": ln.name, "run_id": ln.run_id,
        "started": now, "started_ts": time.time(), "coordinator": os.getpid(),
    }  # fmt: skip
    if _queue_pg():
        try:
            row = queue_store.take_to_sea(ln.text, **fields)
            return row is not None, row
        except store.StoreDown:
            raise
        except Exception as e:  # noqa: BLE001
            say(f"S2: {ln.text} has no at-sea row ({e}); it sails without one")
            return take(queue, ln.text), None
    if not take(queue, ln.text):
        return False, None
    try:
        return True, queue_store.to_sea(ln.text, **fields)
    except Exception as e:  # noqa: BLE001
        say(f"S2: {ln.text} has no at-sea row ({e}); it sails without one")
        return True, None


def _seat_pid(row: int | None, pid: int, say) -> None:
    """The launched process's pid, onto its at-sea row."""
    if row is None:
        return
    try:
        from thorp.viable.s2_coordination import queue_store

        queue_store.set_pid(row, pid)
    except Exception as e:  # noqa: BLE001 - the line is at sea either way
        say(f"S2: pid {pid} could not be written to its at-sea row: {e}")


def _adopt(running: dict, specs: Path, done: Path, root: Path, say) -> None:
    """Take up what the last coordinator left at sea (11 November). Every `s2.at_sea` row: a live process
    that is plausibly that line keeps its seat and is watched to its end; a dead one (or a row that never
    got a pid) is written to the history as lost, or as finished when the ledger says the voyage docked
    while no coordinator was watching, and its seat is free. Nothing is requeued here.

    Then the old pid file (data/queue-procs.json), for what a coordinator from before the rows left: the
    same rule, and a live process is given a row, so the next restart finds it there."""
    from thorp.viable.s2_coordination import queue_store

    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    def line_of(text: str, name=None, run_id=None) -> Line:
        try:
            ln = parse(text, specs)
        except Exception:  # noqa: BLE001 - a spec gone since the launch still has a line to record
            ln = Line(text.strip(), "mac", "cmd", text.strip())
        ln.name, ln.run_id = name or ln.name, run_id or ln.run_id  # as launched, not as the spec reads now
        return ln

    def seat(lane: str, ln: Line, pid: int, started, ts, slot, row) -> None:
        running.setdefault(lane, []).append(
            {
                "line": ln,
                "proc": _Adopted(pid, outcome=lambda: _outcome(ln, since=started)),
                "since": started or now,
                "started": started or now,
                "since_ts": float(ts or time.time()),
                "slot": int(slot or 0),
                "row": row,
            }
        )
        _children.add(int(pid))  # ours: not a voyage started outside the queue (outside_voyage)
        say(f"[{lane}] adopted {ln.text} (pid {pid})")

    def lost(lane: str, ln: Line, pid, started, row) -> None:
        status = _outcome(ln, gone=True, since=started)
        why = f"its process (pid {pid}) is gone" if pid else "it was never given a pid"
        hint = ""
        if lane == "vast" and status == "lost":
            hint = f"; if its box is still hired: thorp charter attach {ln.run_id or ln.name or '<run id>'}"
        say(
            f"[{lane}] {ln.text} was at sea when the last coordinator stopped and {why}: "
            f"recorded as {status}, not requeued{hint}"
        )
        _record(done, ln.text, started or now, status, row=row)

    try:
        rows = queue_store.at_sea()
    except Exception as e:  # noqa: BLE001 - no table yet, or no store: the pid file is what there is
        say(f"S2: the at-sea rows could not be read ({e})")
        rows = []
    seen = set()
    for r in rows:
        seen.add((r["text"], r["pid"]))
        ln = line_of(r["text"], r["name"], r["run_id"])
        lane = r["lane"] if r["lane"] in lane_names() else ln.lane
        if kind_of(lane) == "charter" and ln.lane != lane and ln.kind == "spec":
            # sailing abroad though its text does not send it there: the purser routed it (12 November). Kept, so
            # a failure abroad after a restart is retried abroad or comes home, as it would have before the restart,
            # rather than recorded and dropped from the queue.
            ln.lane, ln.routed = lane, True
        if r["pid"] and _alive(r["pid"]) and _is_that_job(r["pid"], ln):
            seat(lane, ln, r["pid"], r["started"], r["started_ts"], r["seat"], r["id"])
        else:
            lost(lane, ln, r["pid"], r["started"], r["id"])
    for e in _read_procs(root):
        text, pid = str(e.get("text") or "").strip(), int(e.get("pid") or 0)
        if not text or not pid or (text, pid) in seen or pid in _children:
            continue
        ln = line_of(text)
        if ln.kind not in ("cmd", "intelligence", "spec"):
            continue
        lane = e.get("lane") if e.get("lane") in lane_names() else ln.lane
        started = e.get("started") or e.get("since")
        if _alive(pid) and _is_that_job(pid, ln):
            row = None
            with contextlib.suppress(Exception):
                row = queue_store.to_sea(
                    text, lane=lane, seat=int(e.get("slot") or 0), kind=ln.kind, name=ln.name,
                    run_id=ln.run_id, pid=pid, started=started, started_ts=e.get("since_ts"),
                )  # fmt: skip
            seat(lane, ln, pid, started, e.get("since_ts"), e.get("slot"), row)
        else:
            lost(lane, ln, pid, started, None)


PAUSED = " | paused "  # what a pause adds to a lane's note, and an opening takes off again
SANK_S = 600.0  # a chartered voyage released within ten minutes of reaching the sea never trained


def set_lane(lane: str, enabled: bool, why: str = "") -> bool:
    """Open or pause a lane in s2.lane_defs (the coordinator reads it again on its next loop). A pause keeps its
    reason on the lane's note (`... | paused 14:02: two fit-outs failed in a row`); an opening takes it off.
    False when there is no such lane."""
    from sqlalchemy import text

    with store.session() as s:
        row = s.execute(text("select note from s2.lane_defs where lane = :lane"), {"lane": lane}).first()
        if row is None:
            return False
        note = (row[0] or "").split(PAUSED)[0]
        if not enabled:
            note += f"{PAUSED}{time.strftime('%d %b %H:%M')}: {why or 'by hand'}"
        s.execute(text("update s2.lane_defs set enabled = :on, note = :note where lane = :lane"),
                  {"on": enabled, "note": note, "lane": lane})  # fmt: skip
    _DEFS.update(at=float("-inf"))
    return True


def how_it_ended(ln: Line, since_ts: float, log: list[dict] | None = None) -> str:
    """How a chartered line that exited non-zero ended, from S3's spend log since it started:

    - `sank-at-once`: its hire reached the sea and was released within `SANK_S` of it: the voyage never trained
      (12 November: a list the box was not sent, then a driver too old for the box's torch; both died in the
      first minutes and would have died the same way with every voyage behind them);
    - `voyage-failed`: its hire reached the sea (an `at sea` line) and sailed a while, so the voyage itself failed;
    - `fitout-failed`: a ship was hired and never sailed (a dead box, a refused ssh, a stalled copy, the fit-out's
      deadline): the voyage never got a GPU;
    - `not-hired`: nothing was hired (no offer inside the terms, the charter's gate, no credit)."""
    from datetime import datetime

    from thorp.viable.s3_control import charter as s3

    def at(r) -> float:
        try:
            return datetime.fromisoformat(str(r.get("at"))).timestamp()
        except ValueError:
            return 0.0

    mine = [r for r in (s3.log() if log is None else log) if r.get("run_id") == ln.run_id and at(r) >= since_ts - 5]
    seas = [r for r in mine if r["event"] == "at sea"]
    if seas:
        ends = [float(r.get("ended") or at(r)) for r in mine if r["event"] == "released"]
        if ends and max(ends) - at(seas[-1]) < SANK_S:
            return "sank-at-once"
        return "voyage-failed"
    return "fitout-failed" if any(r["event"] == "hired" for r in mine) else "not-hired"


def _retry_abroad(queue: Path, ln: Line, say, why: str = "it never trained") -> None:
    """A routed voyage whose box failed before it sailed (or that sank at once) goes back to the top as written,
    unpinned: the voyage never got a GPU, so it is the box that is retried, not this Mac that pays (12 November:
    the 9m candidate and the bridge were both pinned to the Mac by a dead box). A line pinned abroad (`vast:`)
    goes back the same way (`_pinned_ended`)."""
    from thorp.viable.s2_coordination import queue_store

    try:
        if _queue_pg():
            queue_store.add(ln.text, top=True, goal_id=queue_store.goal_of_line(ln.text), require_goal=False)
        else:
            append(queue, ln.text)
        say(f"[vast] {ln.text}: {why}; requeued at the top to sail abroad again")
    except Exception as e:  # noqa: BLE001 - the history keeps the failure; a person can requeue it
        say(f"[vast] {ln.text}: {why}, and it could not be requeued: {e}")


# The lines pinned abroad (`vast: <spec>`) already sent back once without coming home: a second end the same way
# leaves the line out of the queue, so a voyage that cannot be hired (the week's budget spent, no offer in the
# terms) or that fails at sea every time is not tried over and over. Kept for this coordinator's life.
_PINNED_RETRIED: set[str] = set()


def _pinned_ended(queue: Path, ln: Line, how: str, say) -> None:
    """A line pinned abroad that did not come home and was not a dead box (those are retried as a routed line's
    are): never hired, or it sailed and failed. Until 12 November it was recorded and dropped from the queue,
    which lost 1m-control at 21:13 (its hire refused because another renter took the offer first). It goes back
    to the top once; the second time it is left out, and said so. A pinned line is never sent to this Mac: it
    was pinned abroad for a reason (the torch arm of a comparison)."""
    what = "it was never hired" if how == "not-hired" else "its voyage failed at sea"
    if ln.text in _PINNED_RETRIED:
        _PINNED_RETRIED.discard(ln.text)
        say(f"[vast] {ln.text}: {what}, the second time running: left out of the queue (requeue it by hand: "
            f"thorp queue add {shlex.quote(ln.text)} --top)")  # fmt: skip
        return
    _PINNED_RETRIED.add(ln.text)
    _retry_abroad(queue, ln, say, why=what)


def box_failure_limit() -> int:
    """S5's `box_failures_before_pause`: fit-outs that may fail in a row on a lane before it is paused."""
    try:
        from thorp.viable.s5_policy import charter as s5

        return max(1, int(s5.terms().get("box_failures_before_pause", 2)))
    except Exception:  # noqa: BLE001 - no terms to read: two
        return 2


def _charter_ended(queue: Path, lane: str, seat: dict, code: int, failures: dict[str, int], say) -> None:
    """A chartered line has ended. A box that failed before the voyage sailed is retried abroad (if the purser
    sent it) and counted; `box_failure_limit()` of them in a row pauses the lane, so a bad hour is not repeated
    down the queue (12 November: the bridge was started the minute the candidate's box died). A voyage that
    sailed and failed, or was never hired, comes home pinned to this Mac as before."""
    ln = seat["line"]
    if code == 0 or code == "adopted:finished":  # a charter adopted across a restart has no exit code: its run's
        failures[lane] = 0  # status on the ledger says it came home (it was counted a failure before 12 November)
        _PINNED_RETRIED.discard(ln.text)
        return
    try:
        how = how_it_ended(ln, float(seat.get("since_ts") or 0.0))
    except Exception as e:  # noqa: BLE001 - the spend log cannot be read: the old rule
        say(f"[{lane}] {ln.text}: how it ended could not be read ({e}); it comes home")
        how = "voyage-failed"
    if how not in ("fitout-failed", "sank-at-once"):
        if how == "voyage-failed":
            failures[lane] = 0  # the box was sound
        if ln.routed:
            _come_home(queue, ln, say)
        else:
            _pinned_ended(queue, ln, how, say)
        return
    failures[lane] = failures.get(lane, 0) + 1
    limit = box_failure_limit()
    what = "the box failed before the voyage sailed" if how == "fitout-failed" else "the voyage sank within minutes of sailing"
    say(f"[{lane}] {ln.text}: {what} (failure abroad {failures[lane]} of {limit} in a row)")
    _retry_abroad(queue, ln, say)  # routed or pinned abroad: it is the box that is retried (the breaker bounds it)
    if failures[lane] >= limit:
        why = f"{failures[lane]} hires failed in a row before training (the last: {ln.name or ln.text}, {how})"
        try:
            set_lane(lane, False, why)
            say(f"[{lane}] PAUSED: {why}. Its lines wait; open it again with `thorp lane {lane} open`")
        except Exception as e:  # noqa: BLE001
            say(f"[{lane}] {why}, and the lane could not be paused: {e}")
        failures[lane] = 0


# S4's intelligence audit as a line of the queue (12 November, Justin: "in the queue we need to schedule the qwen
# 27B intelligence audit in the queue as it needs resources to run. So perhaps after every 5 voyages/runs/
# investigations?"). The judge is a 15 GB model on a 32 GB Mac: as a `cmd:` line on the Mac lane it has the machine
# to itself, as any step does, and never trains beside a voyage. It takes a turn of the queue's cycle with the
# judge (s3_control/cycle.py): S3*'s audit, S4's measurements, the plan, and the judge's reading of every fit-out
# that died and has not been read. It keeps the `cmd:` prefix, so every reader that knows a line by its text still
# sees a command; `parse` gives it the kind `intelligence`, its own item type, for the queue page (12 November).
AUDIT_LINE = ("cmd: [timeout=45m] PYTHONPATH=backend backend/.venv/bin/python -m thorp.viable.s3_control.cycle run "
              "--judge --queued  # estimate 20m")  # fmt: skip


def audit_every() -> int:
    """S5's `intelligence_audit_every`: lines that end between two audits (0 never queues one)."""
    try:
        from thorp.viable.s5_policy import charter as s5

        return max(0, int(s5.terms().get("intelligence_audit_every", 5)))
    except Exception:  # noqa: BLE001 - no terms to read: five
        return 5


def lines_since_audit(history: list[dict]) -> int:
    """The lines that have ended since the last audit (any lane, any kind; a coordinator's own restart and a
    `wait:` do not count). Read from the history, so a coordinator restarted between two audits counts on."""
    n = 0
    for h in reversed(history):
        text = str(h.get("text") or "")
        if INTELLIGENCE_MARK in text:
            break
        if "restart_coordinator.sh" in text or text.startswith("wait:"):
            continue
        n += 1
    return n


def queue_audit(queue: Path, say, history: list[dict] | None = None, pending_now: list[str] | None = None,
                every: int | None = None) -> bool:  # fmt: skip
    """Put the audit at the top of the queue when `every` lines have ended since the last one and none is queued
    or at sea. It goes on the Mac lane, so it sails when the Mac is next free. True when it was queued."""
    every = audit_every() if every is None else every
    if every <= 0:
        return False
    try:
        if history is None:
            from thorp.viable.s2_coordination import queue_read

            history = queue_read.history()
        n = lines_since_audit(history)
        if n < every:
            return False
        if pending_now is None:
            pending_now = pending(queue)
        sea = []
        with contextlib.suppress(Exception):
            from thorp.viable.s2_coordination import queue_store

            sea = [r["text"] for r in queue_store.at_sea()]
        if any(INTELLIGENCE_MARK in t for t in list(pending_now) + sea):
            return False
        if _queue_pg():
            from thorp.viable.s2_coordination import queue_store

            queue_store.add(AUDIT_LINE, top=True, require_goal=False)
        else:
            append(queue, AUDIT_LINE)
        say(f"[mac] {n} lines have ended since the last intelligence audit: the audit is queued at the top (S4's judge, on the Mac alone)")
        return True
    except Exception as e:  # noqa: BLE001 - an audit that cannot be queued must never stop the queue
        say(f"S2: the intelligence audit could not be queued: {e}")
        return False


def _come_home(queue: Path, ln: Line, say) -> None:
    """A voyage the purser sent abroad that did not come home (no offer within the terms, a box that would not
    provision, the charter's gate): it goes back to the top of the queue pinned to this Mac (`mac: <spec>`), so
    a failed hire costs a retry here, never the voyage, and the purser does not send it abroad again."""
    from thorp.viable.s2_coordination import queue_store

    home = f"mac: {ln.payload}"
    try:
        if _queue_pg():
            queue_store.add(home, top=True, goal_id=queue_store.goal_of_line(ln.text), require_goal=False)
        else:
            append(queue, home)
        say(f"[vast] {ln.text} did not come home from abroad: requeued at the top as {home!r}")
    except Exception as e:  # noqa: BLE001 - the history keeps the failure; a person can requeue it
        say(f"[vast] {ln.text} failed abroad and could not be requeued here: {e}")


def _record(done: Path, text: str, started: str, status, row: int | None = None) -> None:
    """Write a line that ended to queue-done.txt, or to queue_history when the store is the queue. If the
    store refuses it, keep it in the file and carry on: a record must never kill the coordinator (10
    November: a stale id sequence took the queue down on the exit of a finished voyage). `row` is the line's
    at-sea row: deleted with the history in one transaction, or straight after a history kept in the file."""
    if _queue_pg():
        from thorp.viable.s2_coordination import queue_store

        try:
            queue_store.record(text, started, status, at_sea=row)
            return
        except Exception as e:  # noqa: BLE001 - the file keeps what the store could not
            print(
                f"[{time.strftime('%H:%M:%S')}] queue_history could not record {text}: {e}"
                f"; kept in {done}",
                flush=True,
            )
    with done.open("a", encoding="utf-8") as f:
        f.write(f"{started} {text} {status}\n")
    _leave_sea(row)


def run(queue: Path | None = None, done: Path | None = None, root: Path | None = None,
        poll_s: float = 30.0, key=has_key, outside=outside_voyage, launch=None, log=None, until_empty: bool = True,
        hired=ship_out, steward=None) -> None:  # fmt: skip
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
        elif ln.kind in ("cmd", "intelligence"):
            # a queued audit or probe gets its own log, not the coordinator's: `cmd:` output interleaved
            # into queue.out is unreadable exactly when the audit is the thing you are watching for
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", ln.payload).strip("-")[:70] or "cmd"
            out_path = root / "data" / "runs" / f"cmd-{slug}.out"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out = open(out_path, "w")  # noqa: SIM115
        cmd = command(ln)
        # a local lane's seats sit after the earlier local lanes' in the helm (the Mac's are 0.., as before)
        helm_slot = slot + (helm_offset(ln.lane) if kind_of(ln.lane) == "local" else 0)
        env = {**os.environ, "THORP_HELM_SLOT": str(helm_slot), "THORP_HELM_SLOTS": str(helm_slots_total())}
        # its own session (11 November): a signal to the coordinator's process group, which is what launchd
        # sends when the job ends, must not reach a voyage. What stops a line signals the line's own group.
        p = subprocess.Popen(
            cmd,
            cwd=root,
            shell=isinstance(cmd, str),
            stdout=out or None,
            stderr=subprocess.STDOUT if out else None,
            env=env,
            start_new_session=True,
        )  # noqa: S602
        if out:
            out.close()
        return p

    custom = launch is not None
    # S3's purser beside the lanes (12 November): it calls each voyage's waters, and in S5's `routing` mode sends
    # the ones it calls foreign to the Vast lane. Not in a test's custom launch, unless the test hands one in.
    if steward is None and not custom:
        from thorp.viable.s3_control.purser import Steward

        steward = Steward(say)
    launch = launch or default_launch
    running: dict[str, list[dict]] = {lane: [] for lane in lane_names()}  # s2.lane_defs (item 11)
    told: dict[str, str | None] = {lane: None for lane in lane_names()}
    swept = float("-inf")  # when the heartbeats were last swept (the first sweep is in the first loop)
    attempts: dict[str, int] = {}
    box_failures: dict[str, int] = {}  # fit-outs failed in a row, a charter lane (the breaker)
    # adopt what the last coordinator left at sea: every at-sea row, then the old pid file
    try:
        _adopt(running, specs, done, root, say)
    except Exception as e:  # noqa: BLE001 - a start that cannot adopt still runs the queue
        say(f"S2: what was at sea could not be adopted: {e}")
    try:
        _reap_runs(say)
    except Exception as e:  # noqa: BLE001 - a cleanup must never stop the queue
        say(f"S2: could not close stale runs: {e}")
    while True:
        # the expedition states are a column now (s1.expedition_status): the coordinator writes them as
        # the helm and the queue move, and the pages read them rather than deriving them
        try:
            from thorp import liberty_machine

            liberty_machine.refresh_expedition_states()
        except Exception as e:  # noqa: BLE001 - a status write must never stop the queue
            say(f"S2: could not write the expedition states: {e}")
        finally:
            # the states are read through the ledger's per-thread reader, whose session otherwise stays
            # idle in a transaction for the coordinator's whole life, holding a lock on s1.runs that a
            # truncate or an ALTER waits on for ever (11 November: 40 minutes on the live store; every
            # test after the first that ran this loop hung on its fixture's truncate)
            with contextlib.suppress(Exception):
                from thorp.ledger import close_reader

                close_reader()
        for row in list(_unsunk):  # rows whose history is written but which the store would not delete
            _leave_sea(row)
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
                    # a voyage stops on SIGTERM by finishing its step and saving a checkpoint (11 November):
                    # give it the time to; a cmd: keeps the short grace it always had
                    code = _stop(seat["proc"], grace=180.0 if seat["line"].kind == "spec" else 2.0)
                if code is not None:
                    say(f"[{lane}] {seat['line'].text} exited {code}")
                    _record(
                        done,
                        seat["line"].text,
                        seat.get("started")
                        or seat.get("since")
                        or time.strftime("%Y-%m-%dT%H:%M:%S"),
                        code,
                        row=seat.get("row"),
                    )
                    _children.discard(seat["proc"].pid)
                    attempts.pop(seat["line"].text, None)
                    seats.remove(seat)
                    if kind_of(lane) == "charter" and seat["line"].kind == "spec":
                        _charter_ended(queue, lane, seat, code, box_failures, say)
                    elif code != 0 and seat["line"].routed:
                        _come_home(queue, seat["line"], say)
                    if not custom:  # every few lines, S4's audit (not in a test's custom launch)
                        queue_audit(queue, say)
        # a run whose heartbeat stopped with nothing at sea covering it is lost (11 November, item 11)
        if time.monotonic() - swept > SWEEP_EVERY_S:
            swept = time.monotonic()
            try:
                _sweep_lost(running, say)
            except Exception as e:  # noqa: BLE001 - a record must never stop the queue
                say(f"S2: could not sweep the heartbeats: {e}")
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
        if steward is not None:
            lines = steward.steer(lines, [seat["line"].text for seats in running.values() for seat in seats])
        have_key = key()
        lane_defs(fresh=True)  # a lane added, disabled or re-seated in s2.lane_defs since the last loop
        for lane in enabled_lanes():
            running.setdefault(lane, [])
            told.setdefault(lane, None)
            if kind_of(lane) not in KINDS:  # a row of a kind with no launcher yet: it takes nothing
                why = f"lane {lane} is of kind {kind_of(lane)!r}, which has no launcher"
                if why != told[lane]:
                    say(f"[{lane}] in port: {why}")
                told[lane] = why
                continue
            capacity = capacity_for(lane, lines, running)
            while len(running[lane]) < capacity:
                at_sea = [seat["line"] for seats in running.values() for seat in seats]
                ln, why = next_for(lane, lines, at_sea, have_key)
                if ln is None:
                    if why and why != told[lane]:
                        say(f"[{lane}] in port: {why}")
                    told[lane] = why
                    break
                if kind_of(lane) == "local" and ln.kind != "wait" and outside():
                    if told[lane] != "outside":
                        say(f"[{lane}] in port: a voyage started outside the queue is at sea")
                    told[lane] = "outside"
                    break
                if kind_of(lane) == "charter" and ln.kind == "spec" and (why := hired()):
                    if why != told[lane]:
                        say(f"[{lane}] in port: {why}")
                    told[lane] = why
                    break
                now = time.strftime("%Y-%m-%dT%H:%M:%S")
                if ln.kind == "wait":
                    if not take(queue, ln.text):
                        break  # edited away meanwhile: read the queue again next time
                    told[lane] = None
                    say(f"[{lane}] {ln.text}: docked, going on")
                    _record(done, ln.text, now, 0)
                    lines = [x for x in lines if x is not ln]
                    continue
                # the lowest free seat, not the count of seats taken: with seat 1 still out and seat 0 home,
                # the count is 1 again and the new voyage would wait on the helm its neighbour holds
                used = {int(seat.get("slot") or 0) for seat in running[lane]}
                seat_no = next(i for i in range(len(used) + 1) if i not in used)
                # the line leaves the queue and its at-sea row is written in one step (11 November)
                try:
                    taken, row = _to_sea(queue, ln, lane, seat_no, now, say)
                except store.StoreDown as e:  # the store went between the read and the take: next loop
                    say(f"S2: the queue could not be written: {e}")
                    break
                if not taken:
                    break  # edited away meanwhile: read the queue again next time
                told[lane] = None
                say(f"[{lane}] starting {ln.text}")
                try:
                    p = launch(ln) if custom else launch(ln, seat_no)
                except Exception as e:  # noqa: BLE001 - one broken line must not take the queue down
                    # the line was taken; retry it twice (requeued at the end, so it cannot wedge the head),
                    # then record the failure and let the queue go on. Either way its at-sea row goes: it
                    # never sailed. Requeued before the row is deleted, so a death between the two leaves
                    # the line queued (and a row a restart records as lost), never in neither place.
                    n = attempts.get(ln.text, 0) + 1
                    attempts[ln.text] = n
                    if n < 3:
                        say(f"[{lane}] {ln.text} could not start (attempt {n}/3): {e}")
                        with contextlib.suppress(Exception):
                            append(queue, ln.text)
                        _leave_sea(row)
                    else:
                        say(f"[{lane}] {ln.text} could not start after 3 attempts: {e}")
                        _record(done, ln.text, now, 1, row=row)
                        attempts.pop(ln.text, None)
                    lines = [x for x in lines if x is not ln]
                    continue
                _children.add(p.pid)
                _seat_pid(row, p.pid, say)
                running[lane].append(
                    {
                        "line": ln,
                        "proc": p,
                        "since": now,
                        "started": now,
                        "since_ts": time.time(),
                        "slot": seat_no,
                        "row": row,
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
        # what is still to sail: a line of a lane that can take it (enabled, of a kind with a launcher; a charter
        # lane's only with a key), so a disabled lane's lines wait in the queue as a keyless Vast lane's do
        sails = {k for k in enabled_lanes() if kind_of(k) in KINDS and (kind_of(k) == "local" or have_key)}
        left = [x for x in (parse(t, specs) for t in pending(queue)) if x.lane in sails]
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
