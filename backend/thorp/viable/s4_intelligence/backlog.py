"""S4: the backlog — what may sail while a decision waits (DECISIONS.md, "The catch-up rule"; Justin, 2026-11-08:
"there will always be a backlog of things that can run while waiting for me to make a decision, so another rule
should be if justin's not available then catch up on the backlog experiments if they're still valid").

- **An item** is a line the queue could take next (a voyage spec), with **the decision it still feeds**, the control
  it is read against, its pre-registered prediction, its last like it on this Mac and its expected gain an hour. The
  decision is not decoration: an item that names none is struck, because nothing can check what nobody wrote down.
- **Still sails** is the S3 gate's answer, read and recorded here, never re-decided: the fitout still sails (S5
  `ogden`), the text's cleaning is current, the voyage belongs to an expedition.
- **Still decides** is the other half: the decision it feeds is still open. Only a person closes one (or the item
  sailing); `strike` keeps the reason, so the list stays finite instead of becoming a museum. An item whose control
  has not docked is **blocked**, not struck: it still sails and still decides, but it cannot be read yet.
- **Order** is what the catch-up rule asks for: valid items by expected gain an hour (highest first), then shortest
  first, and only what fits the gap. The window's committed lines still come first — this is the lowest of the four
  ranks (lanes.py takes the queue's order, and the backlog is only ever offered a lane that would idle).

    uv run thorp backlog seed            # the lines the queue-removed files kept, as items to judge
    uv run thorp backlog audit           # still sails, still decides: each verdict written with its reason
    uv run thorp backlog list            # the backlog, valid first
    uv run thorp backlog rank --gap 120  # what would fill a two-hour gap
    uv run thorp backlog add LINE --decision "..." --control RUN
    uv run thorp backlog strike LINE --why "..."
"""

from __future__ import annotations

import contextlib
import sys
from datetime import UTC, datetime

from thorp import paths, store
from thorp.viable.records import BacklogItem

STATES = ("valid", "blocked", "struck", "sailed", "unknown")
SEEDED = (
    "queue-removed-2026-11-08.txt"  # the lines cleared for Phaleron; older files with `seed --all`
)


# ---------------------------------------------------------------- reading an item


def _bare(line: str) -> str:
    """A queue line without its lane's prefix (`vast:`, `mac:`), or "" for a line that is not a voyage."""
    text = line.strip()
    for prefix in ("vast:", "mac:"):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    if text.startswith(("cmd:", "wait:", "#")):
        return ""
    return text


def spec_of(line: str) -> dict | None:
    """The voyage's spec, or None when there is no such file (a line that can no longer be read)."""
    import yaml

    p = paths.resolve(f"ships/specs/{line}.yaml")
    if not p.exists():
        return None
    with contextlib.suppress(Exception):
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    return None


def _ledger_status(name: str) -> str | None:
    """The newest sailing of a voyage: 'finished', 'running', 'failed...', or None when it never sailed."""
    from thorp.ledger import reader

    with contextlib.suppress(Exception):
        rows = reader().query(
            "select status from runs where name=? order by started desc limit 1", [name]
        )
        if rows:
            return rows[0]["status"]
    return None


def _like_minutes(line: str) -> float | None:
    """About how long it takes here: the plan page's own estimate (waters._wall_minutes: the latest voyage of the
    same corpus and size on this Mac, else the size's mean)."""
    spec = spec_of(line)
    if not spec:
        return None
    data, model = spec.get("data") or {}, spec.get("model") or {}
    recipe = data.get("recipe")
    if not recipe and data.get("stages"):
        recipe = (data["stages"][0] or {}).get("recipe")
    with contextlib.suppress(Exception):
        from thorp.dash.waters import _wall_minutes

        wall = _wall_minutes()
        return wall.get((recipe, model.get("preset"))) or wall.get(model.get("preset"))
    return None


# ---------------------------------------------------------------- the two tests


def verdict(
    *, gate: list[str], decision: str, control: str = "", control_state: str | None = None
) -> tuple[str, str]:
    """(state, why) from what the two tests say. Pure: the gate's refusals and the control's state are read
    elsewhere, so this can be tried without a store. An empty `decision` fails 'still decides'; the gate's first
    refusal fails 'still sails'."""
    if not decision.strip():
        return "struck", "names no decision it still feeds"
    if gate:
        return "struck", "; ".join(gate)
    if control and control_state != "finished":
        # it still sails and still decides; it cannot be read yet, which is a wait, not a closure
        return "blocked", f"its control {control} is {control_state or 'not run'}"
    return "valid", ""


def audit(*, now: datetime | None = None) -> list[dict]:
    """Run both tests on every item that has not sailed, and write each verdict with its reason."""
    from thorp import vsm

    now = now or datetime.now(UTC)
    out, verdicts = [], {}
    for it in items():
        if it.state == "sailed":
            continue
        spec = spec_of(it.line)
        if spec is None:
            refusals = [f"no spec at ships/specs/{it.line}.yaml"]
        else:
            # the gate's read-only twin: an advisory is not a refusal, and nothing is written to the gate's log
            refusals = vsm.gate_refusals(spec)
        state, why = verdict(
            gate=refusals,
            decision=it.decision,
            control=it.control,
            control_state=_ledger_status(it.control) if it.control else None,
        )
        verdicts[it.line] = (state, why)
        if state != it.state or why != it.why:
            out.append({"line": it.line, "was": it.state, "state": state, "why": why})
    with store.session() as s:  # one transaction for every verdict, after the tests are all read
        for line, (state, why) in verdicts.items():
            row = s.get(BacklogItem, line)
            if row is not None:
                row.state, row.why, row.checked_at = state, why, now
    return out


# ---------------------------------------------------------------- the list


def items(state: str | None = None) -> list[BacklogItem]:
    from sqlalchemy import select

    with store.session() as s:
        q = select(BacklogItem).order_by(BacklogItem.line)
        return [r for r in s.execute(q).scalars() if not state or r.state == state]


def order(rows: list, gap_minutes: float | None = None) -> list:
    """The catch-up rule's order, pure so it can be tried on anything with `gain` and `minutes`: expected gain an
    hour first (an item with no estimate goes last), then the shortest; with a gap, only what is known to fit it
    (an unknown length is not offered to a gap — it cannot be promised to finish in it)."""
    out = sorted(
        rows, key=lambda r: (r.gain is None, -(r.gain or 0.0), r.minutes is None, r.minutes or 0.0)
    )
    if gap_minutes is not None:
        out = [r for r in out if r.minutes is not None and r.minutes <= gap_minutes]
    return out


def queued() -> set[str]:
    """The lines the queue already holds: an item caught up into the queue is not offered again."""
    from thorp.viable.s2_coordination import queue_read

    return {_bare(ln) or ln.strip() for ln in queue_read.pending()}  # the store's queue (11 November)


def rank(gap_minutes: float | None = None) -> list[BacklogItem]:
    """The valid items, in the catch-up rule's order, without those the queue already holds."""
    here = queued()
    return [r for r in order(items("valid"), gap_minutes) if r.line not in here]


def pick(gap_minutes: float | None = None) -> BacklogItem | None:
    """What a lane that would idle for this long should sail, or None (the lane waits, and says so)."""
    rows = rank(gap_minutes)
    return rows[0] if rows else None


def add(
    line: str,
    *,
    decision: str,
    control: str = "",
    expedition: str = "",
    prediction: str = "",
    minutes: float | None = None,
    gain: float | None = None,
    source: str = "",
) -> BacklogItem:
    """Put an item on the backlog. `decision` is required: an item that feeds none cannot be judged, and is not
    what this list is for."""
    bare = _bare(line) or line.strip()
    if not decision.strip():
        raise ValueError("a backlog item names the decision it still feeds")
    row = BacklogItem(
        line=bare,
        expedition=expedition,
        decision=decision,
        control=control,
        prediction=prediction,
        minutes=minutes if minutes is not None else _like_minutes(bare),
        gain=gain,
        state="unknown",
        why="",
        source=source,
    )
    with store.session() as s:
        s.merge(row)
    return row


def strike(line: str, why: str) -> None:
    """Close an item by a person's word (or because the decision it fed has closed): the reason is kept."""
    with store.session() as s:
        row = s.get(BacklogItem, _bare(line) or line.strip())
        if row is None:
            raise KeyError(f"{line} is not on the backlog")
        row.state, row.why = "struck", why


def seed(files: tuple[str, ...] = (SEEDED,)) -> list[str]:
    """The lines the queue-removed files kept, as items: no decision named yet, so the audit strikes them until
    someone says what each one still decides. That is the expected state of a fresh backlog, not a failure."""
    added = []
    for name in files:
        p = paths.resolve(f"ships/specs/{name}")
        if not p.exists():
            continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            bare = _bare(raw)
            if not bare:
                continue
            spec = spec_of(bare)
            if (
                spec is None
            ):  # a line whose spec is gone cannot sail; it is struck at once, with the reason
                with store.session() as s:
                    s.merge(
                        BacklogItem(
                            line=bare,
                            state="struck",
                            why=f"no spec at ships/specs/{bare}.yaml",
                            source=name,
                        )
                    )
                added.append(bare)
                continue
            with store.session() as s:
                s.merge(BacklogItem(line=bare, state="unknown", source=name))
            added.append(bare)
    return added


# ---------------------------------------------------------------- the command


def _print_rows(rows: list[BacklogItem]) -> None:
    here = queued()
    print(f"{'state':<8} {'min':>6} {'gain/h':>7}  line")
    for r in rows:
        mins = f"{r.minutes:.0f}" if r.minutes is not None else "—"
        gain = f"{r.gain:.2f}" if r.gain is not None else "—"
        mark = "  · in the queue" if r.line in here else ""
        print(f"{r.state:<8} {mins:>6} {gain:>7}  {r.line}{mark}")
        if r.why:
            print(f"{'':<8} {'':>6} {'':>7}  └ {r.why}")


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="thorp backlog")
    sub = p.add_subparsers(dest="what", required=True)
    s = sub.add_parser("list", help="the backlog")
    s.add_argument("--state", choices=STATES)
    s = sub.add_parser("audit", help="still sails, still decides: write each verdict")
    s = sub.add_parser("rank", help="what would fill a gap, in the catch-up rule's order")
    s.add_argument("--gap", type=float, help="the gap in minutes")
    s = sub.add_parser("add", help="put an item on the backlog")
    s.add_argument("line")
    s.add_argument("--decision", required=True, help="the open decision it still feeds")
    s.add_argument("--control", default="")
    s.add_argument("--expedition", default="")
    s.add_argument("--prediction", default="")
    s.add_argument("--minutes", type=float)
    s.add_argument("--gain", type=float)
    s = sub.add_parser("strike", help="close an item, keeping the reason")
    s.add_argument("line")
    s.add_argument("--why", required=True)
    s = sub.add_parser("seed", help="the queue-removed files' lines, as items to judge")
    s.add_argument(
        "--all", action="store_true", help="every queue-removed file, not just the newest"
    )
    a = p.parse_args(argv)

    if a.what == "list":
        rows = items(a.state)
        _print_rows(rows)
        n = sum(1 for r in rows if r.state == "valid")
        print(f"\n{len(rows)} items; {n} valid")
        return 0
    if a.what == "audit":
        changed = audit()
        for c in changed:
            print(
                f"{c['state']:<8} {c['line']}  ({c['was']} → {c['state']})"
                + (f": {c['why']}" if c["why"] else "")
            )
        rows = items()
        n = sum(1 for r in rows if r.state == "valid")
        print(f"\naudited {len(rows)} items; {n} valid, {len(changed)} changed")
        return 0
    if a.what == "rank":
        rows = rank(a.gap)
        if not rows:
            print("nothing valid" + (f" fits a {a.gap:g}-minute gap" if a.gap is not None else ""))
            return 0
        _print_rows(rows)
        first = rows[0]
        print(
            f"\nfirst: {first.line} ({first.minutes:.0f} min)"
            if first.minutes is not None
            else f"\nfirst: {first.line}"
        )
        return 0
    if a.what == "add":
        r = add(
            a.line,
            decision=a.decision,
            control=a.control,
            expedition=a.expedition,
            prediction=a.prediction,
            minutes=a.minutes,
            gain=a.gain,
            source="by hand",
        )
        print(f"added {r.line} (state {r.state}: run `thorp backlog audit`)")
        return 0
    if a.what == "strike":
        strike(a.line, a.why)
        print(f"struck {a.line}: {a.why}")
        return 0
    if a.what == "seed":
        files = (SEEDED,)
        if a.all:
            files = tuple(
                sorted(p.name for p in paths.resolve("ships/specs").glob("queue-removed-*.txt"))
            )
        added = seed(files)
        print(f"seeded {len(added)} items from {', '.join(files)}; run `thorp backlog audit`")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
