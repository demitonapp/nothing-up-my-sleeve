#!/usr/bin/env python
"""Chat with a finished Thorp run's latest checkpoint. Experimental.

The model is a small GPT trained on Ogden, not an instruction-tuned assistant. Without a chat/QA
arm it will continue prose rather than answer. The prompt is wrapped the way the voyage was taught:
the v0.1.4 marks for a run that read them, plain prose otherwise (thorp.chat.prompt_for).

    PYTHONPATH=backend .venv/bin/python backend/scripts/chat.py --models
    ... --run fu-ogden-v0-1@9m-pre-s1
    ... --run fu-ogden-v0-1@9m-pre-s1 --prompt "What is a mill?" --tokens 40 --audit

"""

from __future__ import annotations

import argparse

from thorp import chat


def print_audit(a: dict) -> None:
    if not a or not a.get("readable"):
        print(f"audit: {a.get('reason', 'not readable')}")
        return
    print("cards:")
    for c in a.get("cards") or []:
        live = "–" if c.get("live") is None else ("lit" if c["live"] else "unlit")
        held = "–" if c.get("held") is None else ("held" if c["held"] else "not held")
        print(
            f"  {c['name']:18} {held:9} this answer: {live:5} {c.get('live_score')}  {c.get('head') or ''}"
        )
    print("heads over the answer:")
    for h in (a.get("heads") or [])[:8]:
        print(
            f"  L{h['layer']:02d}.H{h['head']:02d}  trigger {h['trigger']:.3f}  "
            f"aimed at {h.get('aimed_at') or '–'!r}  star {h.get('star') or '–'}  card {h.get('card') or '–'}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Chat with a finished Thorp checkpoint.")
    ap.add_argument("--run", default=None, help="the run name (see --models)")
    ap.add_argument("--step", type=int, default=None, help="a checkpoint step, else the latest")
    ap.add_argument("--prompt", default=None, help="one question, then exit")
    ap.add_argument("--tokens", type=int, default=80)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--audit", action="store_true", help="print the heads and cards audit")
    ap.add_argument(
        "--models", action="store_true", help="list the leaderboard's chat targets and exit"
    )
    a = ap.parse_args()

    if a.models:
        for m in chat.models():
            run = (m.get("run") or {}).get("run")
            print(f"{m['name']:32} {m.get('params') or '?':>10}  {run or m.get('why')}")
        return
    if not a.run:
        ap.error("--run is required (or --models to list the leaderboard's ships)")

    model, tok, spec, ckpt = chat.load(a.run, a.step)
    print(
        f"run {a.run} · {ckpt.name} · vocab {tok.vocab_size} · context {spec['model']['context']}",
        file=__import__("sys").stderr,
    )
    if a.prompt is not None:
        got = chat.answer(
            a.run, a.prompt, tokens=a.tokens, temperature=a.temperature, seed=a.seed, step=a.step
        )
        print(got["answer"])
        if a.audit:
            print_audit(got.get("audit") or {})
        return
    print("Type a question. Ctrl-D to stop.", file=__import__("sys").stderr)
    while True:
        try:
            user = input("you> ")
        except EOFError:
            print(file=__import__("sys").stderr)
            return
        if not user.strip():
            continue
        got = chat.answer(
            a.run, user, tokens=a.tokens, temperature=a.temperature, seed=a.seed, step=a.step
        )
        print(f"thorp> {got['answer']}")
        if a.audit:
            print_audit(got.get("audit") or {})


if __name__ == "__main__":
    main()
