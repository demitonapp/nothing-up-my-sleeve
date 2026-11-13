"""Read an outside model on When2Call (thorp/when2call.py), as score_arc_ai2.py reads AI2 ARC (14 November).

MODEL is a Hugging Face id or local path mlx-lm can load. It is read zero-shot by likelihood on the authors' default
prompt (the tools as JSON, the replies as written), not the fleet's turns: an outside model never learned our marks.
The paper reads each model in its own chat template, so a reading here sits near the paper's numbers, not on them.
Nothing is written to the store; the readings are printed as one JSON line.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_when2call.py mlx-community/SmolLM2-360M-Instruct [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score_arc_ai2 import _load  # noqa: E402

from thorp import when2call  # noqa: E402


def score(model_id: str, limit: int | None, batch: int, context: int) -> dict:
    import mlx.core as mx
    import mlx.nn as nn

    model, tok = _load(model_id)
    mx.set_cache_limit(1 << 30)  # give freed buffers back, as score_arc_ai2 does beside a voyage
    start = tok.eos_token_id if tok.bos_token_id is None else tok.bos_token_id

    def ce(x, y):
        out = nn.losses.cross_entropy(model(mx.array(x)).astype(mx.float32), mx.array(y), reduction="none")
        mx.eval(out)
        return out

    t0 = time.time()
    items = when2call.questions(limit)
    rows = when2call.score(ce, lambda s: tok.encode(s, add_special_tokens=False), start, items, batch=batch,
                           context=context, renderer=when2call.render_outside)  # fmt: skip
    s = when2call.summary(rows)
    return {"model": model_id, "commit": when2call.COMMIT, "prompt": "authors' default", "pilot": len(items) < when2call.COUNT,
            "seconds": round(time.time() - t0, 1), **s}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("model")
    ap.add_argument("--limit", type=int, default=None, help="questions taken evenly through the set (a pilot)")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--context", type=int, default=4096, help="the longest question and reply read; longer are skipped")
    a = ap.parse_args()
    print(json.dumps(score(a.model, a.limit, a.batch, a.context), ensure_ascii=False))


if __name__ == "__main__":
    main()
