"""The probe phase, read (11 November 2026, Kipling's fourth aim).

A probing voyage (`optim.scaffold.probes`, thorp/train.py) pulses the pull off for a few steps and logs every
pinned head's distance from its card at every step (`scaffold/distance/<card>/l<layer>h<head>`: the
cross-entropy from the card's pattern to the head's attention; lower is closer). For each head and each pulse:

- **before**: the mean distance over the 64 steps before the pull went;
- **off**: the mean over the last quarter of the pulse, the pull still off;
- **after**: the mean over steps 96 to 128 after the pull returned;
- **leak**: how much of what the pull had won came back while it was off:
  (off - before) / (first - before), where `first` is the head's distance over the voyage's first 20 steps;
- **recovered**: the share of that leak undone once the pull returned.

And a word for each head, from its pulses together:

- **never took the card**: even with the pull on, it stayed more than half its first distance away;
- **by heart**: it took the card and leaked under a tenth: the pull can be released;
- **needs the pull**: it took the card, leaked a tenth or more, and came back when the pull did: keep the pull;
- **lost**: it leaked and did not come back.

The comparator riddle is read the same way from `scaffold/riddle/comparator`.

    PYTHONPATH=backend backend/.venv/bin/python -m thorp.probe_phase 300k@v0.0.6-probe 300k@v0.0.6-probe-s2
"""

from __future__ import annotations

import json
import sys

LEAK = 0.10  # under this share of what the pull won, the card is held by heart
TAKEN = 0.50  # a head has taken its card when it is within this share of its first distance
BACK = 0.50  # a leak is recovered when this share of it is undone


def _mean(series: dict[int, float], lo: int, hi: int) -> float | None:
    vals = [v for s, v in series.items() if lo <= s < hi]
    return sum(vals) / len(vals) if vals else None


def _windows(flag: dict[int, float]) -> list[tuple[int, int]]:
    """The pulses as logged: each run of steps where scaffold/probe is 1, as (first, one past the last)."""
    out, start, last = [], None, None
    for s in sorted(flag):
        if flag[s] >= 0.5:
            start = s if start is None else start
            last = s
        elif start is not None:
            out.append((start, last + 1))
            start = None
    if start is not None:
        out.append((start, last + 1))
    return out


def read(run: str) -> dict:
    from thorp.ledger import reader

    con = reader()
    try:
        row = con.find_run(run)
        if not row:
            raise LookupError(f"no run {run}")
        rid = row["run_id"]
        series: dict[str, dict[int, float]] = {}
        for m in con.execute(
            "select name, step, value from metrics where run_id=? and (name like 'scaffold/distance/%'"
            " or name in ('scaffold/probe', 'scaffold/riddle/comparator', 'scaffold/weight'))",
            (rid,),
        ):
            m = dict(m)
            series.setdefault(m["name"], {})[int(m["step"])] = float(m["value"])
    finally:
        con.close()
    flag = series.pop("scaffold/probe", {})
    weight = series.pop("scaffold/weight", {})
    if not flag:
        raise LookupError(f"{run} did not probe: it logged no scaffold/probe")
    heads = {}
    for name, sr in sorted(series.items()):
        first = _mean(sr, 0, 21)
        pulses = []
        for a, b in _windows(flag):
            before, off = _mean(sr, a - 64, a), _mean(sr, b - max(1, (b - a) // 4), b)
            after = _mean(sr, b + 96, b + 128)
            if None in (first, before, off):
                continue
            won = first - before
            leak = (off - before) / won if won > 1e-6 else None
            back = (off - after) / (off - before) if after is not None and off - before > 1e-6 else None
            pulses.append({"at": a, "pull": round(weight.get(a - 1, 0.0), 3), "before": round(before, 4),
                           "off": round(off, 4), "after": None if after is None else round(after, 4),
                           "taken": before <= TAKEN * first, "leak": None if leak is None else round(leak, 3),
                           "recovered": None if back is None else round(back, 3)})  # fmt: skip
        taken = [p for p in pulses if p["taken"]]
        if not pulses:
            word = "not read"
        elif not taken:
            word = "never took the card"
        else:
            leaks = [p["leak"] for p in taken if p["leak"] is not None]
            worst = max(leaks) if leaks else 0.0
            if worst < LEAK:
                word = "by heart"
            else:
                backs = [p["recovered"] for p in taken if p["leak"] is not None and p["leak"] >= LEAK and p["recovered"] is not None]
                word = "needs the pull" if backs and min(backs) >= BACK else "lost"
        label = name.removeprefix("scaffold/distance/").removeprefix("scaffold/riddle/")
        heads[label] = {"first": None if first is None else round(first, 4), "word": word, "pulses": pulses}
    return {"run": row["name"], "run_id": rid, "pulses": _windows(flag), "heads": heads}


def main(argv: list[str]) -> int:
    from thorp import paths

    if not argv:
        print(__doc__)
        return 2
    readings = []
    for run in argv:
        r = read(run)
        readings.append(r)
        print(f"\n{r['run']}: {len(r['pulses'])} pulses at steps {[a for a, _ in r['pulses']]}")
        print(f"  {'head':<28} {'first':>7}  " + "  ".join(f"leak@{a:<6}" for a, _ in r["pulses"]) + "  word")
        for label, h in r["heads"].items():
            cells = []
            for a, _ in r["pulses"]:
                p = next((x for x in h["pulses"] if x["at"] == a), None)
                cells.append(f"{'-':<11}" if p is None or p["leak"] is None else f"{p['leak']:+.2f}{'' if p['taken'] else '*':<6}")
            print(f"  {label:<28} {h['first'] if h['first'] is not None else 0:>7.3f}  " + "  ".join(cells) + f"  {h['word']}")
        print("  (* the head had not taken the card when that pulse began; leak is the share of what the pull won)")
    if len(readings) > 1:
        print("\nacross the sailings:")
        for label in readings[0]["heads"]:
            words = [r["heads"].get(label, {}).get("word", "not read") for r in readings]
            agree = "agree" if len(set(words)) == 1 else "DISAGREE"
            print(f"  {label:<28} {' / '.join(words)}  ({agree})")
    out = paths.data_dir() / "runs" / f"probe-phase-{readings[0]['run']}.json"
    out.write_text(json.dumps(readings, indent=1))
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
