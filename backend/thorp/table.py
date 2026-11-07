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


def guesses(run: str, text: str, k: int = 10) -> dict:
    """The sailing's next-piece guesses after `text` (Justin, 2026-11-07: "see which guesses it currently
    can make"): the k most likely next pieces with their probabilities, read from the logits once, no
    sampling; the window keeps the end of a long text. Nothing is written to the transcript."""
    row, spec, tok, model, step = _load(run)
    context = spec["model"]["context"]
    ids = ([tok.eos_id] + tok.encode(text))[-context:]
    t0 = time.time()
    logits = model(mx.array([ids]))[0, -1].astype(mx.float32)
    probs = mx.softmax(logits)
    k = max(1, min(int(k), 50))
    order = mx.argsort(-probs)[:k].tolist()
    p = probs.tolist()
    return {
        "guesses": [{"piece": tok.decode([i]), "p": p[i]} for i in order],
        "prompt_tokens": len(ids),
        "seconds": round(time.time() - t0, 3),
        "run": row["name"],
        "run_id": row["run_id"],
        "step": step,
    }


def word_guesses(run: str, text: str, k: int = 10, words: int = 1, beam: int = 24, depth: int = 10) -> dict:
    """The sailing's guesses of the next whole word (or two) after `text` (Justin, 2026-11-07: "I'd be
    expecting I could ask ... word guesses"): a beam search over its pieces, each path followed until it
    completes `words` words (the next piece starts a new word: a space, a line break, punctuation or the
    end) or `depth` pieces; a path that starts with a line break is the guess "⏎". The same words reached
    by different pieces are added together. Probabilities are of the path (the word as spelt), so they
    sum to less than one: the rest is words the beam did not reach."""
    import math

    row, spec, tok, model, step = _load(run)
    context = spec["model"]["context"]
    base = ([tok.eos_id] + tok.encode(text))[-(context - depth) :]
    words, k = max(1, min(int(words), 3)), max(1, min(int(k), 30))
    t0 = time.time()

    def nwords(s: str) -> int:
        return len(s.split())

    def ends_word(piece: str) -> bool:
        return piece == "" or piece[:1].isspace() or (piece[:1] in ".,;:!?\"')]") 

    beams = [([], 0.0)]  # (pieces after the text, log-probability)
    done: dict[str, float] = {}
    starts: dict[str, bool] = {}  # did the guess begin a new word (its first piece starts with a space)?
    for _ in range(depth):
        nxt = []
        for ids, lp in beams:
            logits = model(mx.array([(base + ids)[-context:]]))[0, -1].astype(mx.float32)
            logp = (logits - mx.logsumexp(logits)).tolist()
            top = sorted(range(len(logp)), key=logp.__getitem__, reverse=True)[:8]
            sofar = tok.decode(ids) if ids else ""
            for i in top:
                piece = "" if i == tok.eos_id else tok.decode([i])
                if not ids and (piece.startswith("\n") or i == tok.eos_id):
                    key = "⏎" if piece.startswith("\n") else "(the end)"
                    done[key] = done.get(key, 0.0) + math.exp(lp + logp[i])
                    continue
                if ids and nwords(sofar) >= words and ends_word(piece):
                    w = " ".join(sofar.split()[:words])
                    done[w] = done.get(w, 0.0) + math.exp(lp + logp[i])
                    starts.setdefault(w, sofar[:1].isspace())
                    continue
                nxt.append((ids + [i], lp + logp[i]))
        beams = sorted(nxt, key=lambda b: b[1], reverse=True)[:beam]
        if not beams:
            break
    for ids, lp in beams:  # paths still open at the depth: count what they spell so far
        s = tok.decode(ids).split()
        if len(s) >= words:
            w = " ".join(s[:words])
            done[w] = done.get(w, 0.0) + math.exp(lp)
            starts.setdefault(w, tok.decode(ids)[:1].isspace())
    ranked = sorted(done.items(), key=lambda x: x[1], reverse=True)[:k]
    tail = text.split()[-1] if text.split() and not text[-1:].isspace() else ""

    def shown(w: str, starts_word: bool) -> dict:
        if starts_word or not tail or w in ("⏎", "(the end)"):
            return {"word": w, "continues": False}
        return {"word": tail + w, "continues": True, "piece": w, "of": tail}

    return {
        "guesses": [{**shown(w, starts.get(w, True)), "p": p} for w, p in ranked],
        "words": words,
        "prompt_tokens": len(base),
        "seconds": round(time.time() - t0, 3),
        "run": row["name"],
        "run_id": row["run_id"],
        "step": step,
    }
