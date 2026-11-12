"""Score an outside model (such as Qwen 3.8 27B) on a Nothing up my sleeve deck in bits per byte, the way Nothing up my sleeve's
ce_bpb scores its own runs (2026-11-06; DECISIONS.md, "Thorp against Qwen").

    uv run --group compare python scripts/score_external.py MODEL LIST [--window 1024] [--batch 4]

MODEL is a Hugging Face id or local path that mlx-lm can load (for example
mlx-community/Qwen3.8-27B-4bit); LIST is a Nothing up my sleeve book list (for example lists/hole-cards-unseen.csv),
resolved and fetched exactly as Nothing up my sleeve resolves it. Each book's text is the same stripped text Nothing up my sleeve
scores. The book is tokenised whole with the model's own tokeniser, a start token is put in front
(so the first token is predicted too), and the sequence is cut into non-overlapping windows of
WINDOW predictions, each starting from an empty context, as ce_bpb does. bits per byte = total
nats / (UTF-8 bytes x ln 2), so the number is comparable with Nothing up my sleeve's whatever the tokenisers.

Keeps s4.outside_readings <model>__<list> (was data/compare/<model>__<list>.json) (per book: nats, tokens, bytes, bits per byte; the means;
the settings) and prints a table.

A model mlx-lm cannot load (Maincode/Maincoder-1B) is built from its weights by scripts/mlx_ports.py. The
scoring takes S2's helm (thorp/liberty_machine.py at_sea, kind "score"): it waits in port while a voyage is at sea,
and the next voyage waits for it.
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm import load

from thorp import manifest
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources import load_text
from thorp.sources.gutenberg import resolve_list


def book_nats(model, ids: list[int], start: int, window: int, batch: int) -> tuple[float, int]:
    seq = np.array([start] + ids, dtype=np.int32)
    n_pred = len(seq) - 1
    n_win = math.ceil(n_pred / window)
    padded = np.zeros(n_win * window + 1, dtype=np.int32)
    padded[: len(seq)] = seq
    mask = np.zeros(n_win * window, dtype=np.float32)
    mask[:n_pred] = 1.0
    x = padded[:-1].reshape(n_win, window)
    y = padded[1:].reshape(n_win, window)
    m = mask.reshape(n_win, window)
    total = 0.0
    for i in range(0, n_win, batch):
        logits = model(mx.array(x[i : i + batch])).astype(mx.float32)
        ce = nn.losses.cross_entropy(logits, mx.array(y[i : i + batch]), reduction="none")
        s = (ce * mx.array(m[i : i + batch])).sum()
        mx.eval(s)
        total += s.item()
    return total, n_pred


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("list")
    ap.add_argument("--window", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=4)
    # the text cleaned as the voyages read it (thorp/cleaning.py; 2026-11-08: Ogden voyages score their judge books
    # on unwrap-v2 text, so an outside model compared with them is scored on the same)
    ap.add_argument("--clean", default="raw")
    a = ap.parse_args()

    from thorp import liberty_machine

    # S2: one GPU, so one job at sea; this waits in port for the voyage at sea, and the next voyage for it
    with liberty_machine.at_sea(f"score {a.model} on {Path(a.list).stem}", kind="score"):
        score(a)


def score(a) -> None:
    import mlx_ports  # scripts/mlx_ports.py: models mlx-lm cannot load (Maincoder), from their weights alone

    port = mlx_ports.port_for(a.model)
    model, tok = port() if port else load(a.model)
    start = tok.eos_token_id if tok.bos_token_id is None else tok.bos_token_id
    books = [f"pg{r.chosen}" for r in resolve_list(ROOT / a.list) if r.chosen]
    rows, t0 = [], time.time()
    for b in books:
        text = load_text(b, a.clean)
        nbytes = len(text.encode("utf-8"))
        ids = tok.encode(text, add_special_tokens=False)
        nats, n = book_nats(model, ids, start, a.window, a.batch)
        bpb = nats / (nbytes * math.log(2))
        book = manifest.get(b)
        rows.append(
            {
                "book_id": b,
                "title": book.title if book else b,
                "language": book.language if book else "",
                "nats": nats,
                "tokens": n,
                "bytes": nbytes,
                "bytes_per_token": nbytes / max(1, n - 1),
                "bpb": bpb,
            }
        )
        print(
            f"{b:10} {bpb:7.4f} bpb  {n:>8} tokens  {nbytes:>9} bytes  {time.time() - t0:7.0f}s",
            flush=True,
        )
    en = [r["bpb"] for r in rows if r["language"] == "en"]
    out = {
        "model": a.model,
        "list": a.list,
        "set": Path(a.list).stem,
        "window": a.window,
        "clean": a.clean,
        "start_token": start,
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": time.time() - t0,
        "bpb_mean": float(np.mean([r["bpb"] for r in rows])) if rows else None,
        "bpb_mean_en": float(np.mean(en)) if en else None,
        "books": rows,
    }
    from thorp.viable.s4_intelligence import readings

    f = f"{a.model.replace('/', '--')}__{Path(a.list).stem}{'' if a.clean == 'raw' else '__' + a.clean}"
    readings.put(f, out)
    print(f"mean {out['bpb_mean']:.4f} bpb (English {out['bpb_mean_en']}); kept as {f} in s4.outside_readings")


if __name__ == "__main__":
    main()
