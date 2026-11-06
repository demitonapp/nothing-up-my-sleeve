"""Score an outside model (such as Qwen 3.8 27B) on a Thorp deck in bits per byte, the way Thorp's
ce_bpb scores its own runs (2026-11-06; DECISIONS.md, "Thorp against Qwen").

    uv run --group compare python scripts/score_external.py MODEL LIST [--window 1024] [--batch 4]

MODEL is a Hugging Face id or local path that mlx-lm can load (for example
mlx-community/Qwen3.8-27B-4bit); LIST is a Thorp book list (for example lists/hole-cards-unseen.csv),
resolved and fetched exactly as Thorp resolves it. Each book's text is the same stripped text Thorp
scores. The book is tokenised whole with the model's own tokeniser, a start token is put in front
(so the first token is predicted too), and the sequence is cut into non-overlapping windows of
WINDOW predictions, each starting from an empty context, as ce_bpb does. bits per byte = total
nats / (UTF-8 bytes x ln 2), so the number is comparable with Thorp's whatever the tokenisers.

Writes data/compare/<model>__<list>.json (per book: nats, tokens, bytes, bits per byte; the means;
the settings) and prints a table.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx_lm import load

from thorp import manifest, paths
from thorp.sources import load_text
from thorp.sources.gutenberg import resolve_list

ROOT = Path(__file__).resolve().parents[1]


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
    a = ap.parse_args()

    model, tok = load(a.model)
    start = tok.eos_token_id if tok.bos_token_id is None else tok.bos_token_id
    books = [f"pg{r.chosen}" for r in resolve_list(ROOT / a.list) if r.chosen]
    rows, t0 = [], time.time()
    for b in books:
        text = load_text(b)
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
        "start_token": start,
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": time.time() - t0,
        "bpb_mean": float(np.mean([r["bpb"] for r in rows])) if rows else None,
        "bpb_mean_en": float(np.mean(en)) if en else None,
        "books": rows,
    }
    d = paths.data_dir() / "compare"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{a.model.replace('/', '--')}__{Path(a.list).stem}.json"
    f.write_text(json.dumps(out, indent=1))
    print(f"mean {out['bpb_mean']:.4f} bpb (English {out['bpb_mean_en']}); written {f}")


if __name__ == "__main__":
    main()
