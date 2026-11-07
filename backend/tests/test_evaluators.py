from thorp import evaluators, ledger, train


def test_every_evaluator_returns_eval_columns(library, spec):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    model = train.build_model(spec, prep.tokeniser.vocab_size)
    ctx = evaluators.EvalContext(
        run_id="r",
        step=7,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
        languages={"loc-hole": "en"},
    )
    for name in spec["eval"]["evaluators"]:
        res = evaluators.get(name)(ctx)
        for row in res.evals:
            assert tuple(row) == ledger.EVAL_COLUMNS
    res = evaluators.get("ce_bpb")(ctx)
    assert len(res.evals) == 1
    row = res.evals[0]
    assert row["step"] == 7 and row["book_id"] == "loc-hole" and row["bpb"] > 0
    # an untrained model is close to uniform over the vocabulary
    assert abs(row["ce_nats"] - __import__("math").log(prep.tokeniser.vocab_size)) < 1.0
    samples = evaluators.get("samples")(ctx)
    assert {a["kind"] for a in samples.artifacts} == {"samples", "top10"}
