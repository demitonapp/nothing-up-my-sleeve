"""The evaluation harness's three savings (11 November): none may change a number an evaluator returns.

ce_bpb and bpb_split score the same windows, so the second reads the first's forward passes; shapes' tagger remembers
the texts it has tagged; logic scores each distinct (prefix, idea, rival) once. The bf16 caveat for logic is why its
memo keeps every pass a two-row pass: batching the asks together moved the readings by up to 0.002.
"""

import numpy as np

from thorp import evaluators, train
from thorp.evaluators import ce_bpb, logic
from thorp.viable.s2_coordination import tagger


def _ctx(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=3,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
        languages={"loc-hole": "en"},
        recipe=list(prep.recipe),
    )
    return prep, ctx


def test_bpb_split_reads_the_losses_ce_bpb_worked_out(library, spec, monkeypatch):
    prep, ctx = _ctx(library, spec)
    alone = evaluators.get("bpb_split")(ctx).metrics  # a fresh context: nothing to reuse
    calls = []
    real = ce_bpb.book_losses
    monkeypatch.setattr(ce_bpb, "book_losses", lambda *a: calls.append(1) or real(*a))
    prep, ctx = _ctx(library, spec)  # same weights: build_model is seeded by the spec
    ce = evaluators.get("ce_bpb")(ctx)
    first = len(calls)
    split = evaluators.get("bpb_split")(ctx)
    assert first == sum(len(books) for books in ctx.sets.values()) > 0  # one pass per judge book
    assert len(calls) == first, "bpb_split ran the forward passes again"
    assert split.metrics == alone and ce.evals
    # either order: bpb_split first leaves ce_bpb its losses
    prep, ctx = _ctx(library, spec)
    calls.clear()
    evaluators.get("bpb_split")(ctx)
    evaluators.get("ce_bpb")(ctx)
    assert len(calls) == first


def test_the_tagger_tags_each_text_once(monkeypatch):
    seen = []

    def fake(texts, batch_size=256):
        seen.append(list(texts))
        return [[(0, 1, "w", t.split()[-1].upper())] if t.split() else [] for t in texts]

    monkeypatch.setattr(tagger, "tag_many", fake)
    monkeypatch.setattr(tagger, "_LAST", {})
    assert tagger.last_tag(["the cat", "a dog", "the cat", ""]) == ["CAT", "DOG", "CAT", None]
    assert seen == [["the cat", "a dog", ""]], "a repeated text is tagged once"
    assert tagger.last_tag(["a dog", "the cat", "new bird"]) == ["DOG", "CAT", "BIRD"]
    assert seen[1] == ["new bird"], "only the unseen text is tagged"
    assert tagger.last_tag([]) == []
    monkeypatch.setattr(tagger, "_LAST_CAP", 2)  # past the cap it starts over, and is still right
    assert tagger.last_tag(["x y", "p q", "r s"]) == ["Y", "Q", "S"]


def test_logic_scores_each_distinct_ask_once_and_changes_no_lift(library, spec, monkeypatch):
    prep, ctx = _ctx(library, spec)
    tok = prep.tokeniser
    rows = []
    for item in ("i1", "i2"):
        for variant in ("both", "first", "second"):
            rows.append(
                {
                    "item": item,
                    "variant": variant,
                    "relation": "order",
                    "prompt": f"{item} {variant} before the frame",
                    "frame": "the frame",  # the same frame for every variant of every item
                    "idea": "alpha",
                    "rival": "beta",
                }
            )
    calls = []

    def fake_bpb(model, tok_, ids, texts):
        calls.append((tuple(ids), tuple(texts)))
        h = (sum(ids) * 31 + len(ids) + sum(map(len, texts))) % 97
        return np.array([h / 50.0, (h * 7 % 97) / 50.0])

    monkeypatch.setattr(logic, "_bpb", fake_bpb)
    got = logic.score_deck(ctx.model, tok, rows)
    # the same deck, row by row with no memory, is what the harness did before
    calls.clear()
    plain = {}
    for r in rows:
        plain.setdefault(r["item"], {})[r["variant"]] = logic.row_lift(ctx.model, tok, r)
    assert len(calls) == 2 * len(rows)  # a prompt and a frame, each a two-candidate pass, for every row
    assert got["items"] == {i: {v: round(x, 4) for v, x in d.items()} for i, d in plain.items()}
    calls.clear()
    logic.score_deck(ctx.model, tok, rows)
    # six distinct prompts and the one frame, each asked with the same two candidates: 7 passes, not 12
    assert len(calls) == len(set(calls)) == len(rows) + 1
