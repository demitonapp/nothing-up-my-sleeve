"""The 9m rung's evaluators: the bits-per-byte split and the statistical laws."""

import math

import numpy as np

from thorp import evaluators, shards, train
from thorp.evaluators import bpb_split, laws
from thorp.evaluators.ce_bpb import book_ce
from thorp.sources import load_text


def test_byte_classes():
    text = "Don't stop, 2 o’clock.\nThe end—"
    cls = [bpb_split.CLASSES[i] for i in bpb_split.byte_classes(text.encode())]
    by_char, at = [], 0
    for ch in text:
        by_char.append(cls[at])
        at += len(ch.encode())
    got = dict(zip(range(len(text)), by_char, strict=True))
    assert got[0] == "word_start" and got[1] == "word_inside"
    assert got[3] == "word_inside"  # the apostrophe in don't
    assert got[4] == "word_inside"  # the t after it
    assert got[10] == "punct" and got[11] == "space" and got[12] == "digit"
    assert got[16] == "word_inside"  # the c after o'
    assert by_char[text.index("\n")] == "newline"
    assert by_char[-1] == "punct"  # em dash, three bytes, one class


def test_split_adds_back_to_bits_per_byte(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    tok = prep.tokeniser
    arr = np.asarray(shards.load(tok.id, "loc-hole", tok))
    losses = bpb_split.book_losses(model, arr, tok.eos_id, spec["model"]["context"])
    ce, n = book_ce(model, arr, tok.eos_id, spec["model"]["context"])
    assert abs(losses.mean() - ce) < 1e-9 and len(losses) == n
    split = bpb_split.book_split(losses, arr, bpb_split.piece_bytes(tok))
    total_bytes = sum(split[c]["bytes"] for c in bpb_split.CLASSES)
    text = load_text("loc-hole")
    assert total_bytes == len(text.encode())
    bits = sum(split[c]["bits"] for c in bpb_split.CLASSES) + split["eos_bits"]
    assert math.isclose(bits, losses.sum() / math.log(2), rel_tol=1e-9)


def test_new_evaluators_run(library, spec):
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
    old = laws.NEW_TOKENS, laws.STREAMS
    laws.NEW_TOKENS, laws.STREAMS = 24, 4
    try:
        res = evaluators.get("laws")(ctx)
    finally:
        laws.NEW_TOKENS, laws.STREAMS = old
    assert {a["kind"] for a in res.artifacts} == {"laws"}
    assert (
        0 <= res.metrics["laws/ref/nonword_rate"] <= 0.01
    )  # the fixture's words are all in the recipe
    assert "laws/model/words" in res.metrics
    split = evaluators.get("bpb_split")(ctx)
    assert any(k.endswith("word_inside/bpb_mean_en") for k in split.metrics)


def test_measure_laws():
    texts = ["(He said “yes”. Then she went home. it rained.)", 'an (open bracket and a " quote']
    m = laws.measure(texts, {"he", "said", "yes"})
    assert m["unbalanced_per_kw"] > 0
    assert math.isclose(m["cap_after_stop"], 0.5)
    assert laws.unbalanced("(a) [b] “c”") == 0
    assert laws.unbalanced("(a [b") == 2
    assert laws.cut_words("one two three four", 2) == "one two"
