"""Score one outside model on chosen tests, for a queued investigation (12 November, Justin: "then to choose
which tests to score against it and then it sends those investigative items to the bottom of the expeditions
queue").

Runs from `ships/specs/investigations/score-<model>-<test>.yaml` as `-m thorp.score_tests`; loads the model
once, scores the named discovery or logic tests, and merges the readings into the chain-grades payload in
`s4.outside_readings` as `grade_chains.py` does, so the lab page, leaderboard and lab page see them without
a second write. The other tests (ARC, IFEval, BLiMP) keep their own scorers; this refuses one with its name
rather than pretending.

    PYTHONPATH=backend python -m thorp.score_tests mlx-community/Qwen3-4B-4bit --test kin_test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys


def _external(name: str):
    from thorp import hooked

    model, tok = hooked.load(name)

    class Tok:
        _bos = getattr(tok, "bos_token_id", None)
        _doc = tok.convert_tokens_to_ids("<|endoftext|>") if hasattr(tok, "convert_tokens_to_ids") else None
        eos_id = _bos if isinstance(_bos, int) else (
            _doc if isinstance(_doc, int) and _doc != getattr(tok, "unk_token_id", -1) else (tok.eos_token_id or 0)
        )

        def encode(self, s):
            return tok.encode(s, add_special_tokens=False)

    return model, Tok()


def _finite(x):
    import math

    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--test", action="append", default=[], help="a test key; repeat or comma-separate")
    ap.add_argument("--all-discovery", action="store_true", help="every discovery test in the chains")
    a = ap.parse_args()
    tests = [x for t in a.test for x in t.split(",") if x]
    from thorp import fleet, liberty_machine

    if a.all_discovery:
        tests = [k for c in fleet.chains() for k in c if fleet.TRICKS[k].evaluator == "discovery"]
    if not tests:
        print("no tests named: --test <key>", file=sys.stderr)
        return 2
    unknown = [k for k in tests if k not in fleet.TRICKS]
    if unknown:
        print(f"unknown test(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    unsupported = [k for k in tests if fleet.TRICKS[k].evaluator not in ("discovery", "logic")]
    if unsupported:
        print(
            "these tests have their own scorer and are not run by score_tests: "
            + ", ".join(f"{k} ({fleet.TRICKS[k].evaluator or 'unbuilt'})" for k in unsupported),
            file=sys.stderr,
        )
        return 2
    with liberty_machine.at_sea(f"score {a.model} on {', '.join(tests)}", kind="score"):
        return score(a.model, tests)


def score(model_name: str, tests: list[str]) -> int:
    from thorp import fleet
    from thorp.evaluators.discovery import load_pairs, score_pairs
    from thorp.viable.s4_intelligence import readings

    model, tok = _external(model_name)
    grades = readings.chain_grades() or {"models": {}, "chains": {}}
    out = grades.setdefault("models", {}).setdefault(model_name, {})
    for key in tests:
        t = fleet.TRICKS[key]
        if key == "logic_test" or t.evaluator == "logic":
            from thorp.evaluators.logic import load_deck, score_deck

            deck = load_deck()
            if not deck:
                print(f"{key}: no logic deck", file=sys.stderr)
                continue
            r = score_deck(model, tok, deck)
            m = {t.metric: r["metrics"]["gain"], f"tricks/{key}/score": r["metrics"]["score"]}
            out[key] = {
                **r["metrics"],
                "lift_both": r["metrics"].get("lift"),
                "lift": r["metrics"]["gain"],
                "performed": fleet.performed(key, m),
                "items": r["items"],
                "sha": hashlib.sha1(json.dumps(deck).encode()).hexdigest()[:12],
            }
        else:
            pairs = load_pairs(t.pairs)
            sha = hashlib.sha1(json.dumps(pairs).encode()).hexdigest()[:12]
            r = score_pairs(model, tok, pairs)
            m = {t.metric: r["lift"], f"tricks/{key}/score": r["score"]}
            out[key] = {
                "lift": r["lift"],
                "score": r["score"],
                "performed": fleet.performed(key, m),
                "pairs": r["pairs"],
                "sha": sha,
            }
        print(f"{key}: lift {out[key].get('lift')} score {out[key].get('score')} performed {out[key].get('performed')}", flush=True)
    readings.put("chain-grades", _finite(grades))
    print(f"kept {len(tests)} reading(s) for {model_name} in chain-grades")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
