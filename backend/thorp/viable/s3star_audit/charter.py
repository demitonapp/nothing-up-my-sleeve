"""S3*: nothing hired is forgotten. Independent of the voyage that hired it, the audit reads Vast.ai's own list of
instances against S3's spend log and the berths S2 holds:

- an **orphan** is an instance labelled thorp:<run id> that no charter is sailing (its berth is not held): a
  charter that died with its ship still out, running up the bill. `release_orphans` destroys it and logs the
  release with what it cost.
- a **ghost** is a hire the log still counts as out that Vast.ai no longer lists (released by hand, or by Vast
  for want of credit): the log is closed for it, so the week's spend stops accruing it.

    uv run thorp charter audit [--release-orphans]
"""

from __future__ import annotations

import time

from thorp import paths
from thorp.viable.s1_operations.charter import LABEL
from thorp.viable.s3_control import charter as s3
from thorp.viable.s5_policy import charter as s5


def held_berths() -> set[str]:
    """The run ids whose charters are sailing now (their berth locks held by a live process)."""
    import fcntl

    out = set()
    for f in paths.data_dir().glob("charter-berth-*.lock"):
        with open(f, "a+") as h:
            try:
                fcntl.flock(h, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(h, fcntl.LOCK_UN)
            except BlockingIOError:
                h.seek(0)
                out.add(h.read().strip())
    return out


def _found(finding: str, instance: int, run_id: str | None, action: str, cost: float | None) -> None:
    """S3*'s own record of what it found and did (s3star.audits)."""
    from thorp import store
    from thorp.viable.records import Audit

    with store.session() as s:
        s.add(Audit(finding=finding, instance=instance, run_id=run_id, action=action, cost=cost))


def audit(vast, release_orphans: bool = False, log=print) -> dict:
    listed = [i for i in vast.instances() if str(i.get("label") or "").startswith(LABEL)]
    sailing = held_berths()
    orphans = [i for i in listed if str(i["label"])[len(LABEL):] not in sailing]
    ids = {int(i["id"]) for i in listed}
    out = s3.out_now()
    ghosts = [h for h in out if int(h["instance"]) not in ids]
    for g in ghosts:  # the log closed: Vast.ai no longer has it, so it costs no more
        _found("ghost", int(g["instance"]), g.get("run_id"), "closed in the spend log", s3.cost_of(g))
        s3.record("released", instance=g["instance"], run_id=g.get("run_id"), gpu=g.get("gpu"), dph=g.get("dph"),
                  started=g["started"], ended=time.time(), cost=s3.cost_of(g), status="gone (found by the audit)")  # fmt: skip
    released = []
    if release_orphans:
        for o in orphans:
            vast.release(int(o["id"]))
            hire = next((h for h in out if int(h["instance"]) == int(o["id"])), None)
            started = float(hire["started"]) if hire else float(o.get("start_date") or time.time())
            dph = float(o.get("dph_total") or (hire or {}).get("dph") or 0.0)
            s3.record("released", instance=int(o["id"]), run_id=str(o["label"])[len(LABEL):], gpu=o.get("gpu_name"), dph=dph,
                      started=started, ended=time.time(), cost=max(0.0, (time.time() - started) / 3600) * dph,
                      status="orphan released by the audit")  # fmt: skip
            released.append(int(o["id"]))
            _found("orphan", int(o["id"]), str(o["label"])[len(LABEL):], "released", max(0.0, (time.time() - started) / 3600) * dph)
            log(f"S3*: released orphan instance {o['id']} ({o['label']})")
    folded = s3.fold_billed()  # each released hire's cost as Vast.ai billed it (12 November)
    t = s5.terms()
    return {
        "billed": folded,
        "listed": [{"id": i["id"], "label": i["label"], "status": i.get("actual_status"), "dph": i.get("dph_total")} for i in listed],
        "orphans": [int(o["id"]) for o in orphans],
        "released": released,
        "ghosts": [int(g["instance"]) for g in ghosts],
        "week_spent": s3.week_spent(),
        "weekly_budget": t["weekly_budget"],
        "credit": vast.credit(),
    }
