"""The table: talk to any finished ship (2026-11-07; DECISIONS.md, "Table Talk").

A conversation is kept in one turn format, the one Table Talk will be trained on:

    Q: <the reader's line>
    A: <the model's answer>

`reply(run, history, question)` puts the history (oldest first, trimmed from the oldest exchange
to fit the model's window) and the new question into that format, ends the prompt with "A:", and
lets the model write until it opens the next "Q:" (stopped "turn"), writes its end-of-text mark
("eos"), or reaches max_tokens ("length"). Any finished run with a checkpoint can sit at the table;
a model not trained on the format will mostly keep writing prose, which is itself a reading.

The model is loaded once per process, keyed by run. Every exchange is appended to
data/table/<run name>.jsonl unless keep=False.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import mlx.core as mx

from thorp import paths

_models: dict[str, tuple] = {}


def _run_row(run: str) -> dict:
    from thorp.ledger import Ledger

    rec = Ledger()
    rows = rec.query("select * from runs where name = ? order by started desc", [run]) or rec.query(
        "select * from runs where run_id like ? order by started desc", [run + "%"]
    )
    if not rows:
        raise LookupError(f"no run named or numbered {run!r}")
    return rows[0]


def _load(run: str):
    if run in _models:
        return _models[run]
    from thorp import train
    from thorp.ledger import spec_of

    row = _run_row(run)
    ckpt = train.latest_checkpoint(row["run_id"])
    if ckpt is None:
        raise LookupError(f"run {row['name']} has no checkpoint to talk to")
    spec = spec_of(row)
    prep = train.prepare(spec, log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    model.update(train.to_compute(train.load_master(ckpt), spec["optim"].get("precision", "bf16")))
    step = json.loads((ckpt / "state.json").read_text())["step"]
    _models[run] = (row, spec, prep.tokeniser, model, step)
    return _models[run]


def _transcript_path(name: str) -> Path:
    return paths.data_dir() / "table" / f"{name}.jsonl"


def transcript(run: str) -> list[dict]:
    p = _transcript_path(_run_row(run)["name"])
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _readings(run_id: str) -> dict:
    from thorp import fleet
    from thorp.ledger import Ledger

    rec = Ledger()

    def last(metric: str):
        r = rec.query(
            "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1",
            [run_id, metric],
        )
        return r[0]["value"] if r else None

    return {
        "stars": {k: last(s.metric) for k, s in fleet.STARS.items()},
        "tricks": {k: last(t.metric) for k, t in fleet.TRICKS.items()},
    }


def _prompt(history: list[dict], question: str) -> str:
    turns = "".join(f"Q: {h.get('q', '')}\nA: {h.get('a', '')}\n" for h in history)
    return turns + f"Q: {question}\nA:"


def reply(
    run: str,
    history: list[dict] | None,
    question: str,
    temperature: float = 0.8,
    max_tokens: int = 200,
    seed: int | None = None,
    keep: bool = True,
) -> dict:
    row, spec, tok, model, step = _load(run)
    context = spec["model"]["context"]
    history = list(history or [])
    while True:  # trim from the oldest exchange until the prompt and the answer fit the window
        ids = [tok.eos_id] + tok.encode(_prompt(history, question))
        if len(ids) + max_tokens <= context or not history:
            break
        history = history[1:]
    ids = ids[-(context - max_tokens) :] if len(ids) + max_tokens > context else ids
    key = mx.random.key(seed if seed is not None else int(time.time() * 1000) % (2**31))
    keys = mx.random.split(key, max_tokens)
    out: list[int] = []
    stopped, t0 = "length", time.time()
    for i in range(max_tokens):
        x = mx.array([(ids + out)[-context:]])
        logits = model(x)[0, -1].astype(mx.float32)
        nxt = int(
            (
                mx.argmax(logits)
                if temperature <= 0
                else mx.random.categorical(logits / temperature, key=keys[i])
            ).item()
        )
        if nxt == tok.eos_id:
            stopped = "eos"
            break
        out.append(nxt)
        text = tok.decode(out)
        if "\nQ:" in text:
            stopped = "turn"
            break
    answer = tok.decode(out)
    if stopped == "turn":
        answer = answer.split("\nQ:")[0]
    answer = answer.strip()
    result = {
        "answer": answer,
        "stopped": stopped,
        "tokens": len(out),
        "seconds": round(time.time() - t0, 3),
        "prompt_tokens": len(ids),
        "readings": _readings(row["run_id"]),
        "run_id": row["run_id"],
        "step": step,
    }
    if keep:
        p = _transcript_path(row["name"])
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "question": question,
                        "answer": answer,
                        "temperature": temperature,
                        "seed": seed,
                        "stopped": stopped,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return result
