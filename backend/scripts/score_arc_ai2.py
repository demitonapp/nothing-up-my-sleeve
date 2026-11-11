"""Score an outside model on AI2 ARC, the one peer-recognised test for models under 1B (11 November).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_arc_ai2.py MODEL [--config easy|challenge|both] [--per-split N]

MODEL is a Hugging Face id or local path mlx-lm can load. MODEL is read on the test split of both
configs: ARC-Easy (2,376 questions) and ARC-Challenge (1,172), four options each. There are no
letters: the option's own text is read as the continuation of the question and the lowest mean loss
is the bet, so a base checkpoint and an instruct checkpoint, and a large vocabulary and a 2,048-word
one, are all read the same way (thorp/arc_ai2.py). There is no generation and no chat template.

The reading is kept in `s4.outside_readings` as `arc-ai2-<model>`: the accuracy on each split, how
many questions could not be read, and the settings. Like score_blimp.py it takes S2's helm and waits
in port while a voyage is at sea; `--no-helm` skips the wait (a reading this light can share the Mac
with a training run).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/mlx_ports.py

from thorp import arc_ai2  # noqa: E402
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


def score(model_id: str, configs: list[str], per_split: int | None, batch: int, save: bool) -> dict:
    import mlx.core as mx
    import mlx.nn as nn

    model, tok = _load(model_id)
    # MLX's free-buffer cache defaults to the GPU's whole recommended working set (26.8 GB on this Mac):
    # a reading would then hold every buffer it ever freed. Cap it, as train.py does, so a reading beside
    # a voyage on the same Mac gives its buffers back (11 November: five readings in a row left the Mac
    # 5.6 GB into swap and stalled the 1m at sea for nine minutes).
    mx.set_cache_limit(1 << 30)
    start = tok.eos_token_id if tok.bos_token_id is None else tok.bos_token_id

    def ce(x, y):
        logits = model(mx.array(x)).astype(mx.float32)
        out = nn.losses.cross_entropy(logits, mx.array(y), reduction="none")
        mx.eval(out)
        return out

    t0 = time.time()
    splits = {}
    for config in configs:
        items = arc_ai2.questions(config, "test", per_split)
        rows = arc_ai2.score_questions(ce, lambda s: tok.encode(s, add_special_tokens=False), start, items, batch=batch)
        s = arc_ai2.summary(rows)
        key = str(items[0]["config"]) if items else str(config)
        full = arc_ai2.COUNTS.get((key, "test"))
        splits[key] = {**s, "pilot": full is not None and len(items) < full, "items": len(items)}
        print(
            f"{model_id} [{key}]: accuracy {s['accuracy']:.3f} over {s['questions']} questions "
            f"(chance {arc_ai2.CHANCE:.2f}, excess {s['excess']:+.3f}), {s['skipped']} skipped"
            + (" (pilot)" if splits[key]["pilot"] else "")
        )
    out = {
        "model": model_id,
        "per_split": per_split,
        "start_token": start,
        "revision": arc_ai2.REVISION,
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
        "splits": splits,
    }
    if save:
        readings.put(f"arc-ai2-{model_id}", out)
        print(f"kept as arc-ai2-{model_id} in s4.outside_readings")
    print(f"{out['seconds']:.0f}s")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--config", choices=["easy", "challenge", "both"], default="both")
    ap.add_argument("--per-split", type=int, default=0, help="questions to read from each split; 0 means all")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--no-helm", action="store_true", help="do not wait for a voyage at sea")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    configs = ["easy", "challenge"] if a.config == "both" else [a.config]
    per = a.per_split or None
    if a.no_helm:
        score(a.model, configs, per, a.batch, not a.no_save)
        return
    from thorp import vsm

    with vsm.at_sea(f"score {a.model} on AI2 ARC", kind="score"):
        score(a.model, configs, per, a.batch, not a.no_save)


if __name__ == "__main__":
    main()
