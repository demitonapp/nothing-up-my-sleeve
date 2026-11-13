"""What steering buys a ship on the tool leg's held-out questions (13 November 2026; thorp/steer.py).

Two readings on `lists/tools-heldout-v2.jsonl`, each the old way and steered:

- **the call**: of the questions that want a tool, the share where the call is exactly the lesson's. Old: the ship
  writes it greedily, as the `tools` evaluator reads it. Steered: the likeliest of the calls the question allows.
- **the answer**: the lesson's call and its result are given, and the ship writes the answer. Read for the lesson's
  figures (every number in the lesson's answer, and no other) and for the lesson's answer word for word. Old: one
  reply drawn as the console drew it. Steered: the numbers licensed, one reply; then the best of sixteen.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/read_steering.py RUN [--limit N] [--temperature T]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from thorp import chat, cleaning, steer, turns  # noqa: E402
from thorp.evaluators import tools as tools_eval  # noqa: E402
from thorp.evaluators.samples import greedy  # noqa: E402
from thorp.paths import resolve  # noqa: E402


def figures(text: str) -> list[str]:
    return sorted(m.group(0) for m in steer._FIGURE.finditer(text))


def same(a: str, b: str) -> bool:
    return re.sub(r"\W+", " ", a).strip().lower() == re.sub(r"\W+", " ", b).strip().lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--heldout", default="lists/tools-heldout-v2.jsonl")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--lambdas", default="0,0.5,1")
    args = ap.parse_args()
    model, tok, spec, _ = chat.load(args.run)
    context, clean = int(spec["model"]["context"]), cleaning.version_of(spec)
    items = [json.loads(line) for line in resolve(args.heldout).read_text(encoding="utf-8").splitlines() if line.strip()]
    wanting = tools_eval.spread([it for it in items if it.get("call")], args.limit)
    one = lambda m: tok.encode(m)[0]  # noqa: E731
    call_id, result_id, end_id, answer_id = one(turns.CALL), one(turns.RESULT), one("<end>"), one("<answer>")
    lams = [float(x) for x in args.lambdas.split(",")]
    n = len(wanting)
    got = {"call old": 0, "call steered": 0, "tool old": 0, "tool steered": 0, "moved to a call": 0}
    ans = {k: [0, 0] for k in ["old", "licensed", *[f"best of {steer.SAMPLES}, lambda {x:g}" for x in lams]]}
    decoys = [tok.encode(turns.conversation("marks", [], d, clean)) for d in steer.DECOYS]
    for k, it in enumerate(wanting):
        q, want = it["prompt"], it["call"]
        head = [tok.eos_id] + tok.encode(tools_eval.asked(q, clean))
        out, _ = greedy(model, tok, head, 60, context, [result_id, end_id])
        kind, body = turns.first_move(tok.decode(out))
        got["call old"] += kind == "call" and tools_eval.squash(body) == tools_eval.squash(want)
        got["tool old"] += kind == "call" and tools_eval.name_of(body) == tools_eval.name_of(want)
        lp = steer.next_logp(model, head, context)
        got["moved to a call"] += lp[call_id] > lp[answer_id]
        best, _ = steer.pick_call(model, tok, [*head, call_id], q, context, tuple((spec.get("tools") or {}).get("set") or ()))
        got["call steered"] += best is not None and tools_eval.squash(best) == tools_eval.squash(want)
        got["tool steered"] += best is not None and tools_eval.name_of(best) == tools_eval.name_of(want)
        # the answer, after the lesson's own call and result
        text = cleaning.clean(turns.called(q, [(want, it["result"])], "ZQXJ"), clean).split("ZQXJ")[0]
        ahead = [tok.eos_id] + tok.encode(text)
        gold = it["answer"]
        lic = steer.Licence.of(q, it["result"])

        def mark(name: str, reply: str, gold: str = gold) -> None:
            ans[name][0] += figures(reply) == figures(gold)
            ans[name][1] += same(reply, gold)

        (ids, _), = steer.write(model, tok, ahead, 1, temperature=args.temperature, max_new=80, context=context, seed=k,
                                stop_ids=(end_id,), **chat.DECODING)  # fmt: skip
        mark("old", tok.decode(ids))
        drawn = steer.write(model, tok, ahead, steer.SAMPLES, temperature=args.temperature, max_new=80, context=context,
                            seed=k, stop_ids=(end_id,), licence=lic, **chat.DECODING)  # fmt: skip
        mark("licensed", tok.decode(drawn[0][0]))
        ended = [ids for ids, stop in drawn if stop is not None and ids] or [ids for ids, _ in drawn]
        ended = [ids for ids in ended if lic.names_ok(tok.decode(ids))] or ended
        ended = [ids for ids in ended if steer.holds(tok.decode(ids), it["result"])] or ended
        for x in lams:
            ranked = steer.rerank(model, tok, ahead, decoys, ended, end_id, context, x)
            mark(f"best of {steer.SAMPLES}, lambda {x:g}", ranked[0]["text"] if ranked else "")
    print(f"{args.run}: {n} held-out questions that want a tool, temperature {args.temperature}")
    for name, v in got.items():
        print(f"  {name:<28} {v:>4} of {n}  {100 * v / n:5.1f}%")
    print("  the answer after the lesson's call and result:   the lesson's figures | word for word")
    for name, (f, w) in ans.items():
        print(f"  {name:<28} {100 * f / n:5.1f}% | {100 * w / n:5.1f}%")


if __name__ == "__main__":
    main()
