"""Item 5 of the 11 November audit: the evaluators' time, offline evaluation, and the cached generator.

- run_evaluators records `eval/seconds/<evaluator>` beside `eval/seconds`.
- `eval.offline` takes evaluators out of the loop: the loop writes none of their metrics, keeps the weights of each
  step that deferred them (a weights-only `eval-<step>` snapshot when the step has no checkpoint), and
  `train.score` (thorp score) then writes what an in-loop voyage of the same seed writes, at the same steps, and
  removes the snapshots it consumed. On both backends.
- ops.Decoder's key/value cache gives the pieces the full pass gives, greedy and sampled, on both backends, for
  learned and rotary positions, grouped K/V, fp32 and bf16, inside the context and past it.
- No spec under ships/specs moves its run id: none carries eval.offline, and the ladder is the same twelve.
"""

from __future__ import annotations

import copy
import json
import shutil

import mlx.core as mx
import numpy as np
import pytest

from thorp import ladder, paths, train
from thorp.evaluators import samples
from thorp.ledger import Ledger
from thorp.models import ops, registry

torch = pytest.importorskip("torch")

QUIET = lambda *a: None  # noqa: E731


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    """MLX on the CPU is bitwise reproducible, so a loop and a score can be compared exactly."""
    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.delenv("THORP_BACKEND", raising=False)
    monkeypatch.delenv("THORP_GENERATE_CACHE", raising=False)
    # the library in the test's own manifest file: the test database's s1.books is emptied by every other test that
    # starts meanwhile (several sessions run tests at once), which pulled the synthetic books out from under a voyage
    monkeypatch.setenv("THORP_LIBRARY_PG", "0")
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


# ---------------------------------------------------------------- the cached generator


class Pieces:
    """A tokeniser stand-in: a prompt is its characters' codes, folded into the vocabulary."""

    eos_id = 0

    def __init__(self, vocab: int):
        self.vocab = vocab

    def encode(self, text: str) -> list[int]:
        return [1 + ord(c) % (self.vocab - 1) for c in text]

    def decode(self, ids) -> str:
        return " ".join(map(str, ids))


def tiny(backend: str, positions: str, kv_heads: int, dtype: str, context: int = 48):
    mx.random.seed(5)
    torch.manual_seed(5)
    m = registry.build(
        "gpt", "300k", 97, context, positions, backend=backend, layers=2, width=64, heads=4, kv_heads=kv_heads
    )
    if backend == "torch":
        return m.to(torch.bfloat16 if dtype == "bf16" else torch.float32)
    if dtype == "bf16":
        from mlx.utils import tree_map

        m.update(tree_map(lambda p: p.astype(mx.bfloat16), m.parameters()))
    return m


SHAPES = [
    (b, pos, kv, dt)
    for b in ("mlx", "torch")
    for pos in ("learned", "rope")
    for kv in (0, 2)
    for dt in ("fp32", "bf16")
]


@pytest.mark.parametrize("backend,positions,kv_heads,dtype", SHAPES)
def test_the_cache_writes_what_the_full_pass_writes(backend, positions, kv_heads, dtype, monkeypatch):
    """Greedy (samples.greedy and samples.generate at 0) and sampled (generate at 0.8, the same key) continuations
    for several prompts and lengths, one of them past the context (where the cache gives way to the old window)."""
    m = tiny(backend, positions, kv_heads, dtype)
    tok = Pieces(97)
    key = 11 if backend == "torch" else mx.random.key(11)
    cases = [("For every action", 20), ("It is a truth", 33), ("In", 60)]  # the last runs past the 48 context

    def written(cache: bool):
        monkeypatch.setenv("THORP_GENERATE_CACHE", "1" if cache else "0")
        out = []
        for prompt, n in cases:
            out.append(samples.greedy(m, tok, tok.encode(prompt), n, 48))
            out.append(samples.generate(m, tok, prompt, 0.0, n, 48, key))
            out.append(samples.generate(m, tok, prompt, 0.8, n, 48, key))
        return out

    assert written(True) == written(False)


@pytest.mark.parametrize("backend,positions,kv_heads,dtype", SHAPES)
def test_the_cached_logits_match_and_draw_alike(backend, positions, kv_heads, dtype):
    """The Decoder's logits against the full pass, piece by piece, for a batch of four: within float tolerance, and
    in fp32 the same draws from them (MLX's categorical with one key a piece; numpy's generator for torch). In bf16
    the logits agree to a unit or two in the last place, and that is enough to move a draw now and then (torch,
    learned positions, grouped K/V moved one at the first piece): which is why the evaluators still sample from
    the full pass and use the cache for greedy writing only (ops.py)."""
    m = tiny(backend, positions, kv_heads, dtype)
    seqs_a = [[0, 3, 5], [0, 9, 9], [0, 1, 2], [0, 40, 7]]
    seqs_b = copy.deepcopy(seqs_a)
    cached, full = ops.Decoder(m, 48), ops.Decoder(m, 48, cache=False)
    assert cached.cached and not full.cached
    keys = mx.random.split(mx.random.key(3), 40)
    rng_a, rng_b = np.random.default_rng(3), np.random.default_rng(3)
    tol = 2e-2 if dtype == "bf16" else 1e-4
    for i in range(40):
        la, lb = cached(seqs_a), full(seqs_b)
        np.testing.assert_allclose(np.array(la), np.array(lb), atol=tol, rtol=tol)
        if backend == "torch":
            ta = [samples._pick(r, 1.0, rng_a) for r in la]
            tb = [samples._pick(r, 1.0, rng_b) for r in lb]
        else:
            ta = mx.random.categorical(la, key=keys[i]).tolist()
            tb = mx.random.categorical(lb, key=keys[i]).tolist()
        if dtype == "fp32":
            assert ta == tb
        for s, t in zip(seqs_a, ta, strict=True):
            s.append(int(t))
        for s, t in zip(seqs_b, ta, strict=True):  # the same pieces on both sides, so the logits stay comparable
            s.append(int(t))


def test_an_outside_model_keeps_the_full_pass():
    class Outside:  # neither of our GPTs: the cache is not used, the model is called as before
        backend = "torch"

    assert not ops.Decoder(Outside(), 16).cached


# ---------------------------------------------------------------- the loop, offline evaluation and thorp score


EVALUATORS = ["ce_bpb", "samples", "bpb_split", "laws"]
OFFLINE = ["samples", "bpb_split", "laws"]


def voyage_spec(spec, evaluators=EVALUATORS):
    spec["eval"].update({"every_steps": 40, "evaluators": list(evaluators)})
    spec["eval"]["light"] = {"every_steps": 20, "evaluators": ["bpb_split"]}
    spec["checkpoint"]["every_steps"] = 50
    return spec


def metrics(rec: Ledger, rid: str) -> dict[tuple[int, str], float]:
    rows = rec.query("select step, name, value from metrics where run_id=? order by rowid", [rid])
    return {(r["step"], r["name"]): r["value"] for r in rows}


def artifacts(rec: Ledger, rid: str, kind: str) -> dict[int, str]:
    rows = rec.query("select step, text from artifacts where run_id=? and kind=? order by rowid", [rid, kind])
    return {r["step"]: r["text"] for r in rows}


def deferred_readings(m: dict, laws: bool) -> dict:
    """The readings of the evaluators the tests defer: bpb_split's (eval/<set>/split/...) and the laws'."""
    return {k: v for k, v in m.items() if "/split/" in k[1] or (laws and k[1].startswith("laws/"))}


def loop_readings(m: dict) -> dict:
    """ce_bpb's readings (eval/<set>/..., not the split, not the times): the loop's own score in both voyages."""
    return {
        k: v for k, v in m.items() if k[1].startswith("eval/") and "/split/" not in k[1] and "seconds" not in k[1]
    }


def sail_both(library, spec, tmp_thorp, evaluators=EVALUATORS, offline=OFFLINE):
    """The same voyage twice: in the loop, and with `offline` deferred. Returns the two ledgers and run ids."""
    inloop = voyage_spec(copy.deepcopy(spec), evaluators)
    deferred = voyage_spec(copy.deepcopy(spec), evaluators)
    deferred["eval"]["offline"] = list(offline)
    prep = train.prepare(inloop, resolver=library["resolver"], log=QUIET)
    a, b = Ledger(tmp_thorp / "inloop.sqlite"), Ledger(tmp_thorp / "offline.sqlite")
    ra, rb = train.run_id(inloop), train.run_id(deferred)
    assert ra != rb  # eval.offline is part of the id, as every eval key is
    assert train.train(inloop, prep, a, log=QUIET)["status"] == "finished"
    assert train.train(deferred, prep, b, log=QUIET)["status"] == "finished"
    return a, ra, b, rb


def check_offline(library, a, ra, b, rb, laws: bool):
    total = max(train.saved_weights(ra))  # the last step (a checkpoint is always written there)
    full = sorted({s for s in range(1, total + 1) if s % 40 == 0} | {total})
    light = [s for s in range(1, total + 1) if s % 20 == 0 and s not in full]
    kept = [s for s in full + light if s % 50 and s != total]  # the deferring steps without a checkpoint
    assert light and kept
    ma, mb = metrics(a, ra), metrics(b, rb)
    # the training is the same voyage: the same loss at every step, the loop's own score at every evaluation
    assert {k: v for k, v in ma.items() if k[1] == "loss"} == {k: v for k, v in mb.items() if k[1] == "loss"}
    assert loop_readings(ma) and loop_readings(ma) == loop_readings(mb)
    # the loop wrote none of the deferred evaluators' readings, and named what it deferred where
    assert deferred_readings(ma, laws) and not deferred_readings(mb, laws)
    deferred = {s: json.loads(t) for s, t in artifacts(b, rb, "eval_offline").items()}
    assert sorted(deferred) == sorted(full + light)
    assert deferred[kept[0]]["weights"] == f"eval-{kept[0]}" and deferred[total]["weights"] == f"step-{total}"
    root = train.checkpoint_root(rb)
    snaps = sorted(int(p.name[5:]) for p in root.iterdir() if p.name.startswith("eval-"))
    assert snaps == sorted(kept)
    assert not (root / f"eval-{kept[0]}" / "optimizer.safetensors").exists()

    # a snapshot still being written is not read
    (root / f"eval-{total + 5}.tmp").mkdir()
    assert total + 5 not in train.saved_weights(rb)

    # one step first, its snapshot kept on request
    first = light[0]
    assert train.score(rb, steps=str(first), keep_snapshots=True, resolver=library["resolver"], rec=b, log=QUIET) == [first]
    assert (root / f"eval-{first}").exists()
    # then everything still pending (the first step's evaluators have all returned, so it is not pending), each
    # snapshot removed once scored, the checkpoints kept
    done = train.score(rb, resolver=library["resolver"], rec=b, log=QUIET)
    assert done == sorted(s for s in full + light if s != first)
    assert (root / f"eval-{first}").exists(), "kept on request, and not consumed again"
    assert not [p for p in root.iterdir() if p.name.startswith("eval-") and p.name[5:].isdigit() and p.name != f"eval-{first}"]
    assert train.latest_checkpoint(rb).name == f"step-{total}"
    assert train.score(rb, resolver=library["resolver"], rec=b, log=QUIET) == []  # nothing left pending
    # scoring the kept one again (by name) consumes it
    assert train.score(rb, steps=str(first), resolver=library["resolver"], rec=b, log=QUIET) == [first]
    assert not (root / f"eval-{first}").exists()

    # what the score wrote is what the loop wrote, at the same steps (the light steps carry bpb_split only)
    mb = metrics(b, rb)
    got, want = deferred_readings(mb, laws), deferred_readings(ma, laws)
    assert set(got) == set(want)
    worst = max(abs(got[k] - want[k]) for k in want)
    assert worst == 0.0, worst  # the same weights, the same evaluator, on the CPU: the same numbers
    # each evaluator's time is recorded where it ran; the loop's own eval/seconds is left as the loop wrote it
    for s in full:
        assert (s, "eval/seconds/ce_bpb") in ma and (s, "eval/seconds/ce_bpb") in mb
        assert (s, "eval/seconds/bpb_split") in ma and (s, "eval/seconds/bpb_split") in mb
        assert (s, "eval/seconds/samples") in ma and (s, "eval/seconds/samples") in mb
    for s in light:
        assert (s, "eval/seconds/bpb_split") in ma and (s, "eval/seconds/bpb_split") in mb
        assert (s, "eval/seconds") in ma and (s, "eval/seconds") not in mb  # all deferred: nothing ran there


def test_offline_evaluation_writes_what_the_loop_writes(library, spec, tmp_thorp):
    a, ra, b, rb = sail_both(library, spec, tmp_thorp)
    check_offline(library, a, ra, b, rb, laws=True)
    # the samples (artifacts only) are the loop's too, at the same steps
    assert artifacts(a, ra, "samples") and artifacts(a, ra, "samples") == artifacts(b, rb, "samples")


def test_offline_evaluation_on_torch(library, spec, tmp_thorp):
    spec["model"]["backend"] = "torch"
    spec["optim"]["precision"] = "fp32"
    evs = ["ce_bpb", "samples", "bpb_split"]
    a, ra, b, rb = sail_both(library, spec, tmp_thorp, evaluators=evs, offline=["samples", "bpb_split"])
    check_offline(library, a, ra, b, rb, laws=False)
    assert artifacts(a, ra, "samples") and artifacts(a, ra, "samples") == artifacts(b, rb, "samples")


def test_eval_offline_is_checked(spec):
    assert train.offline_evaluators(spec) == []
    spec["eval"]["offline"] = ["ce_bpb"]
    with pytest.raises(ValueError, match="ce_bpb"):
        train.offline_evaluators(spec)
    spec["eval"]["offline"] = ["laws"]  # not among the voyage's evaluators: a typo, not a no-op
    with pytest.raises(ValueError, match="laws"):
        train.offline_evaluators(spec)
    spec["eval"]["offline"] = ["samples"]
    assert train.offline_evaluators(spec) == ["samples"]


def test_the_torch_loop_honours_eval_offline(spec):
    from thorp import train_torch

    assert "eval.offline" in train_torch.HONOURED
    spec["model"]["backend"] = "torch"
    spec["eval"]["offline"] = ["samples"]
    train_torch.refuse_unsupported(spec)  # does not raise


def test_thorp_score_passes_its_arguments_on(monkeypatch, capsys):
    from thorp import cli

    seen = {}

    def fake(run, steps, evaluators, keep_snapshots):
        seen.update(run=run, steps=steps, evaluators=evaluators, keep=keep_snapshots)
        if run == "nothing":
            raise LookupError("run nothing deferred no evaluators")
        return [20, 40]

    monkeypatch.setattr(train, "score", fake)
    assert cli.main(["score", "kip", "--steps", "20,40", "--evaluators", "laws,samples", "--keep-snapshots"]) == 0
    assert seen == {"run": "kip", "steps": "20,40", "evaluators": ["laws", "samples"], "keep": True}
    assert cli.main(["score", "kip"]) == 0
    assert seen == {"run": "kip", "steps": "pending", "evaluators": None, "keep": False}
    assert cli.main(["score", "nothing"]) == 1
    assert "deferred no evaluators" in capsys.readouterr().err


def test_score_without_offline_needs_evaluators(library, spec, tmp_thorp):
    rec = Ledger(tmp_thorp / "plain.sqlite")
    spec["checkpoint"]["every_steps"] = 1000
    prep = train.prepare(spec, resolver=library["resolver"], log=QUIET)
    train.train(spec, prep, rec, log=QUIET)
    rid = train.run_id(spec)
    with pytest.raises(LookupError, match="no eval.offline"):
        train.score(rid, resolver=library["resolver"], rec=rec, log=QUIET)
    # named evaluators score every saved step (here the final checkpoint), at its own step
    step = int(train.latest_checkpoint(rid).name.split("-")[1])
    assert train.score(rid, steps="all", evaluators=["bpb_split"], resolver=library["resolver"], rec=rec, log=QUIET) == [step]
    assert (step, "eval/seconds/bpb_split") in metrics(rec, rid)
    assert train.latest_checkpoint(rid) is not None  # a checkpoint is never removed


# ---------------------------------------------------------------- run ids


def test_no_spec_moves_its_run_id():
    """B and C add no key to an existing spec and change neither the ladder nor what load_spec adds, so every spec's
    id is what it was: none under ships/specs names eval.offline, and the ladder is the same twelve in the same
    order (adding or reordering one would move every Ogden and Kipling id)."""
    assert ladder.LADDER_EVALUATORS == (
        "ce_bpb", "bpb_split", "laws", "successor", "maths", "logic",
        "discovery", "stars", "nevermore", "cards", "shapes", "pips",
    )  # fmt: skip
    specs = [p for p in (paths.resolve("specs")).rglob("*.yaml") if "investigations" not in p.parts]
    assert specs
    for p in specs:
        try:
            s = train.load_spec(p)
        except Exception:  # noqa: BLE001  (a fragment or a broken spec is not a voyage)
            continue
        if not isinstance(s, dict) or not isinstance(s.get("eval"), dict):
            continue
        assert "offline" not in s["eval"], p
        assert train.offline_evaluators(s) == []
        # the id is still the sha1 of the canonical spec, eval block and all
        assert train.run_id(s) == train.hashlib.sha1(train.canonical(s).encode()).hexdigest()


def test_a_snapshot_loads_as_a_checkpoint_does(tmp_thorp):
    """eval-N is the master weights in a checkpoint's own format: train.load_master and the torch loader read it."""
    m = tiny("mlx", "learned", 0, "fp32")
    from mlx.utils import tree_flatten

    d = train.save_snapshot("r" * 40, 7, m.parameters())
    assert d.name == "eval-7" and json.loads((d / "state.json").read_text())["weights_only"]
    flat = dict(tree_flatten(train.load_master(d)))
    for k, v in tree_flatten(m.parameters()):
        assert np.array_equal(np.array(flat[k]), np.array(v))
    from thorp import train_torch

    t = train_torch.load_master(d, torch.device("cpu"))
    assert set(t) == set(flat)
    assert train.saved_weights("r" * 40) == {7: d}
    shutil.rmtree(d)
