"""Score an outside model on BLiMP, the grammatical reading beside AI2 ARC (11 November).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_blimp.py MODEL [--per-paradigm 1000]

MODEL is a Hugging Face id or local path mlx-lm can load. Each of the 67,000 minimal pairs
(thorp/blimp.py) is two sentences; the model is right when it gives the grammatical one the higher
log probability. There is no prompt, no chat template and no generation, so a base checkpoint and an
instruct checkpoint are read the same way. Each sentence is the model's own start piece (BOS, else
EOS) followed by the sentence's pieces, as scripts/score_external.py reads a book.

The reading is kept in `s4.outside_readings` as `blimp-<model>`: the summary (accuracy over the 67
paradigms, the mean over the 13 phenomena, each phenomenon, each field, each paradigm) and the
settings. Like score_external.py it takes S2's helm and waits in port while a voyage is at sea;
`--no-helm` skips the wait (a scoring this light can share the Mac with a training run).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/mlx_ports.py

from thorp import blimp  # noqa: E402
from thorp.viable.s4_intelligence import readings  # noqa: E402


def _load(model_id: str):
    from mlx_lm import load

    try:
        return load(model_id)
    except Exception:
        import mlx_ports  # models mlx-lm cannot load (Maincoder), built from their weights alone

        port = mlx_ports.port_for(model_id)
        if port is None:
            raise
        return port()


def score(model_id: str, per_paradigm: int | None, batch: int, save: bool) -> dict:
    import mlx.core as mx
    import mlx.nn as nn

    model, tok = _load(model_id)
    start = tok.eos_token_id if tok.bos_token_id is None else tok.bos_token_id

    def ce(x, y):
        logits = model(mx.array(x)).astype(mx.float32)
        out = nn.losses.cross_entropy(logits, mx.array(y), reduction="none")
        mx.eval(out)
        return out

    items = blimp.pairs(per_paradigm)
    t0 = time.time()
    rows = blimp.score_pairs(ce, lambda s: tok.encode(s, add_special_tokens=False), start, items, batch=batch)
    s = blimp.summary(rows)
    pilot = per_paradigm is not None and per_paradigm < blimp.PER_PARADIGM
    out = {
        "model": model_id,
        "pilot": pilot,
        "per_paradigm": per_paradigm,
        "start_token": start,
        "revision": blimp.REVISION,
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
        **s,
    }
    if save:
        readings.put(f"blimp-{model_id}", out)
        print(f"kept as blimp-{model_id} in s4.outside_readings")
    print(
        f"{model_id}: accuracy {s['accuracy']:.3f} over {s['paradigms']} paradigms ({s['pairs']} pairs), "
        f"macro over {len(s['by_term'])} phenomena {s['macro_terms']:.3f}, {s['ties']} ties, {s['skipped']} skipped"
        + (" (pilot)" if pilot else "")
        + f", {out['seconds']:.0f}s"
    )
    for f, v in s["by_field"].items():
        print(f"  {f:18} {v:.3f}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--per-paradigm", type=int, default=0, help="pairs to read from each of the 67 paradigms; 0 means all 1,000")
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--no-helm", action="store_true", help="do not wait for a voyage at sea")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    per = a.per_paradigm or None
    if a.no_helm:
        score(a.model, per, a.batch, not a.no_save)
        return
    from thorp import liberty_machine

    with liberty_machine.at_sea(f"score {a.model} on BLiMP", kind="score"):
        score(a.model, per, a.batch, not a.no_save)


if __name__ == "__main__":
    main()
