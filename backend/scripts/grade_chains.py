"""Grade the discovery chains (2026-11-07, Justin: "each test must get harder as it moves up the
classes of ships"). Scores every chain's rungs on the reference ladder (fleet.REFERENCE_LADDER) and
on the named Thorp runs, applies fleet.grading to each chain, and writes data/compare/chain-grades.json
({models: {model: {trick: {lift, score, performed}}}, chains: {bettor test: grading}}) for the
dashboard. Usage: uv run --group compare python scripts/grade_chains.py [thorp run names...]
"""

from __future__ import annotations

import json
import sys

import mlx.core as mx

from thorp import fleet, paths
from thorp.evaluators.discovery import load_pairs, score_pairs


def _external(name):
    from mlx_lm import load

    m, t = load(name)

    class Tok:
        # a document's start: the model's own beginning-of-text token where it has one (Llama),
        # else <|endoftext|> (Pythia, Phi, Qwen: Qwen's eos is the chat turn's end, <|im_end|>,
        # which skews its bets), else its eos
        _bos = getattr(t, "bos_token_id", None)
        _doc = (
            t.convert_tokens_to_ids("<|endoftext|>")
            if hasattr(t, "convert_tokens_to_ids")
            else None
        )
        if isinstance(_bos, int):
            eos_id = _bos
        elif isinstance(_doc, int) and _doc != getattr(t, "unk_token_id", -1):
            eos_id = _doc
        else:
            eos_id = t.eos_token_id or 0

        def encode(self, s):
            return t.encode(s, add_special_tokens=False)

    return m, Tok()


def _finite(x):
    """NaN and infinity written as null: they are not JSON, and one would stop the dashboard's pages."""
    import math

    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def main(runs: list[str]) -> None:
    import hashlib

    from thorp import table

    rungs = [k for c in fleet.chains() for k in c if fleet.TRICKS[k].evaluator == "discovery"]
    pairs = {k: load_pairs(fleet.TRICKS[k].pairs) for k in rungs}
    sha = {k: hashlib.sha1(json.dumps(pairs[k]).encode()).hexdigest()[:12] for k in rungs}
    path = paths.data_dir() / "compare" / "chain-grades.json"
    old = json.loads(path.read_text())["models"] if path.exists() else {}
    models: dict[str, dict] = {}
    competitors = [m for m in fleet.COMPETITORS if m not in fleet.REFERENCE_LADDER]
    for name in list(fleet.REFERENCE_LADDER) + competitors + runs:
        cached = old.get(name, {})
        model = tok = None  # loaded at most once per model, only if something must be scored
        todo = [k for k in rungs if cached.get(k, {}).get("sha") != sha[k]]
        out = {k: cached[k] for k in rungs if k not in todo}
        if todo:
            model, tok = _external(name) if "/" in name else table._load(name)[3:1:-1]
        for k in todo:
            r = score_pairs(model, tok, pairs[k])
            m = {fleet.TRICKS[k].metric: r["lift"], f"tricks/{k}/score": r["score"]}
            out[k] = {
                "lift": r["lift"],
                "score": r["score"],
                "performed": fleet.performed(k, m),
                "pairs": r["pairs"],
                "sha": sha[k],
            }
        out = {k: out[k] for k in rungs}
        # the logic deck: chaining gain on invented words (thorp/evaluators/logic.py)
        from thorp.evaluators.logic import load_deck, score_deck

        deck = load_deck()
        dsha = hashlib.sha1(json.dumps(deck).encode()).hexdigest()[:12]
        if deck and cached.get("logic_test", {}).get("sha") == dsha:
            out["logic_test"] = cached["logic_test"]
        elif deck:
            if model is None:
                model, tok = _external(name) if "/" in name else table._load(name)[3:1:-1]
            r = score_deck(model, tok, deck)
            m = {
                fleet.TRICKS["logic_test"].metric: r["metrics"]["gain"],
                "tricks/logic_test/score": r["metrics"]["score"],
            }
            out["logic_test"] = {
                **r["metrics"],
                "lift_both": r["metrics"].get("lift"),
                "lift": r["metrics"][
                    "gain"
                ],  # the trick's metric, under the name the leaderboard reads
                "performed": fleet.performed("logic_test", m),
                "items": r["items"],
                "sha": dsha,
            }
        # the cards (thorp/evaluators/cards.py), read inside the model: Thorp's own GPT directly, an
        # outside model through thorp.inside.Inside
        csha = dsha + "-cards4"
        if deck and cached.get("cards", {}).get("sha") == csha:
            out["cards"] = cached["cards"]
        elif deck:
            from thorp.evaluators import cards as C
            from thorp.inside import Inside

            if model is None:
                model, tok = _external(name) if "/" in name else table._load(name)[3:1:-1]
            inner = Inside(model) if "/" in name else model
            probe = inner.attention_patterns(mx.array([[tok.eos_id] + tok.encode("A test.")]))
            readable = bool(probe)
            cards = {"sha": csha, "attention_readable": readable}
            if readable:
                for key, s_ in (
                    ("mover", C.mover(inner, tok, deck)),
                    ("comparator", C.comparator(inner, tok)),
                ):
                    if s_ is not None:
                        sh, sl = C.shared(s_)
                        cards[key] = {
                            "max": float(s_.max()),
                            "shared": sh,
                            "shared_layer": sl,
                            "lit": bool(s_.max() >= fleet.STARS[key].threshold),
                            "lit_shared": bool(sh >= fleet.STARS[key].threshold),
                        }
            if readable:
                cc = C.copying_cards(inner, tok)
                if cc is not None:
                    for key in ("previous_word", "nevermore"):
                        s_ = cc[key]
                        sh, sl = C.shared(s_)
                        cards[key] = {
                            "max": float(s_.max()),
                            "shared": sh,
                            "shared_layer": sl,
                            "lit": bool(s_.max() >= fleet.STARS[key].threshold),
                            "lit_shared": bool(sh >= fleet.STARS[key].threshold),
                        }
                    cards["nevermore"]["copy_gain"] = cc["copy_gain"]
            br = C.bridge(inner, tok, deck)
            if br is not None:
                cards["bridge"] = {
                    "max": float(br.max()),
                    "best_layer": int(br.argmax()),
                    "layers": len(br),
                    "curve": [round(float(x), 4) for x in br],
                    "lit": bool(br.max() >= fleet.STARS["bridge"].threshold),
                }
            out["cards"] = cards
        models[name] = out
        # written after every model, so the dashboard fills in as the scoring goes, not only at the end
        partial = json.loads(path.read_text()) if path.exists() else {"models": {}, "chains": {}}
        partial["models"][name] = out
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_finite(partial), indent=1))
        print(
            name,
            " ".join(
                k.split("_")[0][:6] + ("#" if v.get("performed") else ".")
                for k, v in out.items()
                if k != "cards"
            ),
            flush=True,
        )
    chains = {}
    for c in fleet.chains():
        passed = {
            n: {k for k, v in o.items() if isinstance(v, dict) and v.get("performed")}
            for n, o in models.items()
            if n not in competitors  # the opponents are scored, never used to grade
        }
        chains[c[-1]] = fleet.grading(c, passed)
        g = chains[c[-1]]
        print(
            c[-1],
            "GRADED" if g["graded"] else "NOT GRADED",
            g["counts"],
            "inversions",
            len(g["inversions"]),
            "rising",
            g["rising"],
            "unreached",
            g["unreached"],
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_finite({"models": models, "chains": chains}), indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
