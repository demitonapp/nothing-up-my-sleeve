"""Score every saved checkpoint of a voyage with chosen evaluators, each reading recorded at its own step
(Justin, 2026-11-07 22:20: "yes, score them": the Ogden 21m sailed before the pips evaluator existed, so its
checkpoints are read afterwards and its four new cards get a curve like a voyage that carried them).

`thorp eval` re-scores only the latest checkpoint; this reads them all (train.save_checkpoint keeps every one).
It takes the helm (S2: one GPU job at a time) and leaves steps already read by these evaluators alone.

    uv run --project backend python backend/scripts/score_checkpoints.py fu-ogden-v0-1@21m-pre-s1 pips
    uv run --project backend python backend/scripts/score_checkpoints.py --dry <voyage> pips   # what it would read
    uv run --project backend python backend/scripts/score_checkpoints.py --only nevermore/natural_shared <voyage> nevermore

--only PREFIX records only the metrics whose names start with PREFIX (and no artifacts): for a reading added to an
evaluator a voyage already ran (the shared induction score, 23:45), so its other metrics are not written twice.
"""

from __future__ import annotations

import json
import sys


class _Only:
    """The ledger, recording only metrics whose names start with a prefix (nothing else)."""

    def __init__(self, rec, prefix: str):
        self.rec, self.prefix = rec, prefix

    def metrics(self, run_id, step, values):
        keep = {k: v for k, v in values.items() if k.startswith(self.prefix)}
        if keep:
            self.rec.metrics(run_id, step, keep)

    def artifact(self, *a, **k):
        pass

    def evals(self, *a, **k):
        pass

    def clear_step(self, *a, **k):
        pass


def main(run: str, evaluators: list[str], dry: bool = False, only: str | None = None) -> int:
    from thorp import train, vsm
    from thorp.ledger import Ledger, spec_of

    rec = Ledger()
    rows = rec.query("select * from runs where name = ? order by started desc", [run]) or rec.query(
        "select * from runs where run_id like ? order by started desc", [run + "%"]
    )
    if not rows:
        raise SystemExit(f"no voyage {run}")
    row = rows[0]
    if row["status"] != "finished":
        raise SystemExit(f"{row['name']} is {row['status']}: score it when it is home")
    rid, spec = row["run_id"], spec_of(row)
    root = train.checkpoint_root(rid)
    steps = sorted(int(p.name.split("-")[1]) for p in root.glob("step-*") if (p / "state.json").exists())
    probe = {"pips": "counter/probe_r2", "shapes": "shapes/upos_top1", "nevermore": "nevermore/natural_shared_score"}
    done = set()
    for ev in evaluators:
        m = probe.get(ev)
        if m:
            done |= {r["step"] for r in rec.query("select step from metrics where run_id=? and name=?", [rid, m])}
    todo = [s for s in steps if s not in done]
    print(f"{row['name']}: {len(steps)} checkpoints, {len(todo)} to read with {', '.join(evaluators)}", flush=True)
    if dry:
        print(f"  would read steps {todo}", flush=True)
        return 0
    spec["eval"] = {**spec["eval"], "evaluators": list(evaluators)}
    with vsm.at_sea(f"score {row['name']} with {'+'.join(evaluators)}", kind="score"):
        prep = train.prepare(spec, log=lambda *a: None)
        for step in todo:
            ckpt = root / f"step-{step}"
            model = train.build_model(spec, prep.tokeniser.vocab_size)
            model.update(train.to_compute(train.load_master(ckpt), spec["optim"].get("precision", "bf16")))
            out = train.run_evaluators(spec, rid, step, model, prep, _Only(rec, only) if only else rec, lambda *a: None)
            keys = {k: round(v, 3) for k, v in (out or {}).items() if k.endswith(("max_score", "probe_r2", "shared_score"))} if isinstance(out, dict) else {}
            print(f"  step {step}: {json.dumps(keys)}", flush=True)
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry" in args
    args = [a for a in args if a != "--dry"]
    only = None
    if "--only" in args:
        i = args.index("--only")
        only = args[i + 1]
        args = args[:i] + args[i + 2 :]
    if len(args) < 2:
        raise SystemExit(__doc__)
    sys.exit(main(args[0], args[1:], dry, only))
