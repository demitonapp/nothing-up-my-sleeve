"""Which heads trigger when Qwen3 4B answers a maths question? (Justin, 10 November: "can you trace the
heads pattern when asking a language model a question? ... could I then trace all the heads that trigger
when it's answering each question"; then: record the test on each foreign ship's page, starting with
MATH-500.)

Three readings, because "triggered" has three meanings:

- **the trace**: for every head, what it attended to at every token of the model's answer. A dense
  (layers, heads, answer tokens, all tokens) heatmap is 1-2 GB a question, so the artifact keeps each
  head's peaks (the strongest weight per answer token and where it went) and the per-head summary; the
  dense heatmap is one flag away (`--heat`) for a single question being examined by hand.
- **the ranking**: per head, over the answer's tokens, the *trigger* (how far its peak sits above an even
  share), *concentration*, *sink* (attention to position 0), *previous* and *offset-2* (the star tests),
  *induction* (at a repeated token, attention to what followed its earlier copy, the Nevermore test), and
  its *route* (attention to numbers, operators, words, LaTeX commands, the problem's own tokens, as a
  multiple of an even share). A head that looks flatly at everything scores near zero.
- **the attribution**: whether the head carries the answer or only watches it. Silence it on every pass
  (`Inside.silenced`) and ask again; a carrying head loses the answer. Shuffled random heads are the band.

Cost, measured on the Mac mini (M6, 32 GB): generation is memory-bound, so batches of 8 read the 4-bit
weights once for eight questions and run at about 200 tokens a second against 30 single; one traced pass
reads all eight sequences. That is the difference between a day and about three-quarters of an hour for
the full 500 (at most `--tokens` each).

The run's cut, written before it:
- **Questions**: `ships/lists/math500.csv`, all 500, or `--pilot N` stratified by subject x level.
- **Generation**: the Qwen3 chat template, thinking on, greedy, `--tokens` (1024) new tokens at most.
- **Grading**: the boxed final answer (Qwen3's form) or an `Answer:` line, against MATH-500's reference:
  literal equality after normalisation (LaTeX spacing, `\\frac`, braces, trailing full stop), numeric
  fallback. An answer cut off by the token limit is counted and marked, not counted correct.
- **Attribution** (`causal`, not in the 500 run): top `--silence` heads against the same number of random
  heads, on `--causal` questions, re-generating each time.

    uv run --project backend --group compare python -m thorp.math_heads trace
    uv run --project backend --group compare python -m thorp.math_heads trace --pilot 40 --heat
    uv run --project backend --group compare python -m thorp.math_heads causal

Writes `data/head-trace/pilot.json` (or `full.json`): per question its grade, answer, and top heads;
per head how many questions it triggered on; the summary the dashboard's Tests tab reads.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from pathlib import Path

import numpy as np

from thorp import paths

LIST = "lists/math500.csv"
OUT = Path("data/head-trace")
MODEL = "mlx-community/Qwen3-4B-4bit"
SEED = 1859
PILOT = 40
CAUSAL = 10
SILENCE = 6
MAX_TOKENS = 1024
BATCH = 8

# the star tests' thresholds (fleet.STARS), so "lit here" means what it means there
SINK, PREV, OFFSET, INDUCTION = 0.5, 0.5, 0.3, 0.3


# ---------------------------------------------------------------- the questions
def questions(n: int = PILOT, seed: int = SEED) -> list[dict]:
    """Stratified by subject x level: round-robin through the cells, a seeded shuffle inside each, so every
    subject and level appears as often as its share allows and two runs of the same size are the same."""
    rows = list(csv.DictReader(open(paths.resolve(LIST))))
    rng = random.Random(seed)
    cells: dict[tuple, list[dict]] = {}
    for r in rows:
        cells.setdefault((r["subject"], r["level"]), []).append(r)
    for c in cells.values():
        rng.shuffle(c)
    keys = sorted(cells)
    picked, i = [], 0
    while len(picked) < n and i < 10_000:
        c = cells[keys[i % len(keys)]]
        if c:
            picked.append(c.pop())
        i += 1
    return picked


# ---------------------------------------------------------------- grading
def normalise(ans: str) -> str:
    a = ans.strip().rstrip(".").strip()
    a = a.replace("\\left", "").replace("\\right", "")
    a = re.sub(r"\\dfrac|\\tfrac", r"\\frac", a)
    a = re.sub(r"\\,|\\!|\\;|\\:|\\~|~", "", a)
    a = re.sub(r"\s+", "", a)
    a = a.replace("^{", "^").replace("}", "").replace("{", "")
    return a


def correct(got: str | None, want: str) -> bool:
    if got is None:
        return False
    g, w = normalise(got), normalise(want)
    if g == w:
        return True
    try:
        return abs(float(g) - float(w)) <= 1e-9 * max(1.0, abs(float(w)))
    except ValueError:
        return False


_ANSWER = re.compile(r"Answer:\s*(.+)")


def _boxed(text: str) -> str | None:
    """The last \\boxed{...} in the text, with its braces balanced: an answer like \\boxed{\\frac{1}{2}}
    holds a brace of its own, which the plain regex cannot see past."""
    i = text.rfind("\\boxed{")
    if i < 0:
        return None
    start, depth = i + len("\\boxed{"), 1
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[start:j].strip()
    return None


def answer_line(text: str) -> str | None:
    """The final answer as models write it: Qwen3 boxes it at the end of its thinking; the benchmark's own
    convention is an `Answer:` line. The box wins when both appear: it is the last thing written."""
    b = _boxed(text)
    if b is not None:
        return b
    m = _ANSWER.findall(text)
    return m[-1].strip().split("\n")[0] if m else None


# ---------------------------------------------------------------- token roles
_NUM = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_OP = re.compile(r"^[=+\-*/^<>()\[\].,]$")
_CMD = re.compile(r"^\\[a-zA-Z]+$")
_WORD = re.compile(r"^[A-Za-z]+$")


def induction_targets(ids: list[int]) -> np.ndarray:
    """At each position, the position that followed the most recent earlier copy of the token, or -1."""
    last: dict[int, int] = {}
    tgt = np.full(len(ids), -1, dtype=np.int64)
    for t, x in enumerate(ids):
        j = last.get(x)
        if j is not None and j + 1 < t:
            tgt[t] = j + 1
        last[x] = t
    return tgt


# ---------------------------------------------------------------- generation
def prompt_for(hf, problem: str) -> str:
    """The Qwen3 chat template, thinking on, as the benchmark run uses it."""
    msgs = [{"role": "user", "content": problem + "\n\nSolve it step by step."}]
    return hf.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)


def generate_batch(model, hf, prompts: list[str], n: int, inner=None, silenced=None):
    """Greedy generation of a batch, one answer per prompt. With `silenced` (a list of (layer, head)) the
    explicit attention zeroes those heads' outputs on every pass: the same questions, one head removed."""
    from mlx_lm import batch_generate
    from mlx_lm.sample_utils import make_sampler

    ids = [hf.encode(p) for p in prompts]
    kw = dict(prompts=ids, max_tokens=n, sampler=make_sampler(temp=0.0), verbose=False)
    if silenced is None:
        return batch_generate(model, hf, **kw).texts
    with inner.silenced(silenced):
        return batch_generate(model, hf, **kw).texts


def as_heads(heads: list[tuple[int, int]]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for l, h in heads:
        out.setdefault(l, []).append(h)
    return out


# ---------------------------------------------------------------- the trace
def role_masks(pieces: list[str], prompt_len: int) -> dict[str, np.ndarray]:
    t = len(pieces)
    return {
        "number": np.array([bool(_NUM.match(p)) for p in pieces]),
        "operator": np.array([bool(_OP.match(p)) for p in pieces]),
        "command": np.array([bool(_CMD.match(p)) for p in pieces]),
        "word": np.array([bool(_WORD.match(p)) for p in pieces]),
        "problem": np.concatenate([np.ones(prompt_len, bool), np.zeros(t - prompt_len, bool)]),
    }


def trace_batch(inner, hf, seqs: list[list[int]], prompt_lens: list[int], keep_heat: bool = False) -> list[dict]:
    """One traced pass over the batch (right-padded to its longest sequence), then the readings per
    question. Attention is streamed from the forward pass and summarised layer by layer, because holding a
    (layers, heads, T, T) float32 tensor for a 1,100-token sequence is 18 GB at this batch size and the Mac
    spends the pass swapping; one layer's is 155 MB. Padding sits at the end, so every valid token's causal
    attention is untouched."""
    import mlx.core as mx

    Tm = max(len(s) for s in seqs)
    ids = np.zeros((len(seqs), Tm), np.int64)
    for i, s in enumerate(seqs):
        ids[i, : len(s)] = s
    L, H = 36, 32

    # per-sequence fixed pieces, prepared once
    pre = []
    for bi, s in enumerate(seqs):
        T, Lp = len(s), prompt_lens[bi]
        pieces = [hf.decode([i]) for i in s]
        roles = role_masks(pieces, Lp)
        tgt = induction_targets(s)
        ans = np.arange(Lp, T)
        pre.append({
            "T": T, "Lp": Lp, "Ta": T - Lp, "pieces": pieces, "ans": ans,
            "ans_rows": np.arange(T - Lp),
            "roles": {k: v.astype(np.float32) for k, v in roles.items() if v.sum()},
            "shares": {k: v.sum() / T for k, v in roles.items() if v.sum()},
            "even": (1.0 / (np.arange(Lp, T) + 1))[None, :],
            "good": np.array([t for t in ans if tgt[t] >= 0], dtype=np.int64),
            "tgt": tgt,
        })

    Z = {bi: {
        "conc": np.zeros((L, H), np.float32), "peak_w": np.zeros((L, H), np.float32),
        "peak_t": np.zeros((L, H), np.int32), "sink": np.zeros((L, H), np.float32),
        "prev": np.zeros((L, H), np.float32), "off2": np.zeros((L, H), np.float32),
        "entropy": np.zeros((L, H), np.float32), "indu": np.zeros((L, H), np.float32),
        "routes": {k: np.zeros((L, H), np.float32) for k in pre[bi]["roles"]},
        "heat": np.zeros((L, H, pre[bi]["Ta"], pre[bi]["T"]), np.uint8) if keep_heat else None,
        "hmax": np.zeros((L, H, pre[bi]["Ta"]), np.float16) if keep_heat else None,
    } for bi in range(len(seqs))}

    def on_layer(li, w):
        w = np.array(w.astype(mx.float32))  # (B, H, T, T)
        for bi, p in enumerate(pre):
            if p["Ta"] <= 0:
                continue
            z = Z[bi]
            wa = w[bi][:, p["ans"], :p["T"]]
            pk = wa.max(-1)
            z["conc"][li] = (pk - p["even"]).mean(-1)
            z["peak_w"][li] = pk.mean(-1)
            z["peak_t"][li] = p["ans"][np.argmax(pk, axis=-1)] - p["Lp"]
            z["sink"][li] = wa[:, :, 0].mean(-1)
            z["prev"][li] = wa[:, p["ans_rows"], p["ans"] - 1].mean(-1)
            z["off2"][li] = wa[:, p["ans_rows"], np.maximum(p["ans"] - 2, 0)].mean(-1)
            q = wa / np.maximum(wa.sum(-1, keepdims=True), 1e-12)
            z["entropy"][li] = -(q * np.log(np.maximum(q, 1e-12))).sum(-1).mean(-1)
            if p["good"].size and (p["tgt"][p["good"]] < p["T"]).all():
                z["indu"][li] = wa[:, p["good"] - p["Lp"], p["tgt"][p["good"]]].mean(-1)
            for k, m in p["roles"].items():
                z["routes"][k][li] = (wa @ m).mean(-1) / p["shares"][k]
            if z["heat"] is not None:
                mx_ = np.maximum(pk[..., None], 1e-8)
                z["heat"][li] = np.clip(wa / mx_ * 255.0, 0, 255).astype(np.uint8)
                z["hmax"][li] = pk.astype(np.float16)

    inner.attention_patterns(mx.array(ids), on_layer=on_layer)

    out = []
    for bi, p in enumerate(pre):
        if p["Ta"] <= 0:
            out.append(None)
            continue
        z = Z[bi]
        rk = []
        for l in range(L):
            for h in range(H):
                stars = {
                    "sink": float(z["sink"][l, h]) if z["sink"][l, h] >= SINK else 0.0,
                    "previous": float(z["prev"][l, h]) if z["prev"][l, h] >= PREV else 0.0,
                    "offset2": float(z["off2"][l, h]) if z["off2"][l, h] >= OFFSET else 0.0,
                    "induction": float(z["indu"][l, h]) if z["indu"][l, h] >= INDUCTION else 0.0,
                }
                trig = max(float(z["conc"][l, h]), *stars.values())
                route = max(z["routes"], key=lambda k: z["routes"][k][l, h]) if z["routes"] else None
                rk.append({
                    "layer": l, "head": h, "trigger": trig,
                    "concentration": float(z["conc"][l, h]),
                    "peak_weight": float(z["peak_w"][l, h]), "peak_at": int(z["peak_t"][l, h]),
                    "sink": float(z["sink"][l, h]), "previous": float(z["prev"][l, h]),
                    "offset2": float(z["off2"][l, h]), "induction": float(z["indu"][l, h]),
                    "entropy": float(z["entropy"][l, h]),
                    "route": route, "route_multiple": float(z["routes"][route][l, h]) if route else 0.0,
                    "star": max(stars, key=stars.get) if max(stars.values()) > 0 else None,
                })
        rk.sort(key=lambda d: -d["trigger"])
        top = []
        for d in rk[:12]:
            at = d["peak_at"]
            where = p["pieces"][p["Lp"] + at][:24] if 0 <= at < p["Ta"] else None
            top.append({**d, "peak_piece": where})
        rec = {
            "prompt_len": p["Lp"], "answer_tokens": p["Ta"],
            "concentration": z["conc"], "peak_at": z["peak_t"], "sink": z["sink"],
            "previous": z["prev"], "offset2": z["off2"], "induction": z["indu"],
            "entropy": z["entropy"], "routes": z["routes"], "top": top, "pieces": p["pieces"],
        }
        if keep_heat:
            rec["heatmap"], rec["heatmap_max"] = z["heat"], z["hmax"]
        out.append(rec)
    return out


# ---------------------------------------------------------------- cross-question summary
def summarise(rows: list[dict], L: int, H: int) -> dict:
    """Per head, over the questions where it was among the strongest readers: how often, how hard it
    triggered, and what its attention was routed to. Two tables, because the strongest readers are mostly
    attention sinks (a sharp, useful, but uninformative peak) and the interesting heads are the ones aimed
    at content: `heads` is everything, `selective` is the heads whose attention went to numbers, operators,
    words, LaTeX or the problem rather than to the window's opening mark."""
    seen: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        for d in r["top"]:
            seen.setdefault((d["layer"], d["head"]), []).append(d)
    content = ("number", "operator", "word", "command", "problem")
    rows_out = []
    for (l, h), ds in seen.items():
        routed = [d for d in ds if d["route"] in content]
        sel = float(np.mean([d["route_multiple"] for d in routed])) if routed else 1.0
        routes = {}
        for d in ds:
            routes[d["route"]] = routes.get(d["route"], 0) + 1
        rows_out.append({
            "layer": l, "head": h, "questions": len(ds),
            "mean_trigger": float(np.mean([d["trigger"] for d in ds])),
            "mean_selectivity": sel,
            "top_route": max(routes, key=routes.get),
            "route_share": round(routes.get("problem", 0) / len(ds), 2),
            "sink_share": round(routes.get("sink", 0) / len(ds), 2),
            "routes": routes,
        })
    ranked = sorted(rows_out, key=lambda d: (-d["questions"], -d["mean_trigger"]))
    selective = sorted(
        [d for d in rows_out if d["top_route"] in content and d["sink_share"] < 0.75],
        key=lambda d: (-d["mean_selectivity"], -d["questions"]),
    )
    return {"n_heads": L * H, "n_questions": len(rows), "heads": ranked[:64],
            "selective": selective[:32]}


def by_group(rows: list[dict], key: str) -> dict:
    """Accuracy by subject or by level, for the page."""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(str(r[key]), []).append(r)
    out = {}
    for k, rs in sorted(groups.items()):
        graded = [r for r in rs if not r["truncated"]]
        out[k] = {
            "n": len(rs),
            "graded": len(graded),
            "correct": sum(r["correct"] for r in graded),
            "accuracy": round(sum(r["correct"] for r in graded) / len(graded), 4) if graded else None,
            "mean_answer_tokens": round(float(np.mean([r["answer_tokens"] for r in rs])), 1),
        }
    return out


# ---------------------------------------------------------------- the commands
def cmd_trace(a) -> int:
    from mlx_lm import load

    from thorp.inside import Inside

    OUT.mkdir(parents=True, exist_ok=True)
    model, hf = load(MODEL)
    inner = Inside(model)
    n = a.pilot if a.pilot else len(list(csv.DictReader(open(paths.resolve(LIST)))))
    qs = questions(n, SEED)
    name = "pilot" if a.pilot else "full"
    rows, t0 = [], time.time()
    for start in range(0, len(qs), a.batch):
        chunk = qs[start: start + a.batch]
        prompts = [prompt_for(hf, q["problem"]) for q in chunk]
        texts = generate_batch(model, hf, prompts, a.tokens)
        p_ids = [hf.encode(p) for p in prompts]
        seqs = [p + hf.encode(t) for p, t in zip(p_ids, texts)]
        traces = trace_batch(inner, hf, seqs, [len(p) for p in p_ids], keep_heat=a.heat and len(qs) <= 3)
        for q, text, tr in zip(chunk, texts, traces):
            if tr is None:
                continue
            got = answer_line(text)
            truncated = tr["answer_tokens"] >= a.tokens
            rows.append({
                "unique_id": q["unique_id"], "subject": q["subject"], "level": int(q["level"]),
                "problem": q["problem"], "want": q["answer"], "got": got,
                "correct": correct(got, q["answer"]), "truncated": bool(truncated),
                "prompt_tokens": tr["prompt_len"], "answer_tokens": tr["answer_tokens"],
                "answer": text, "top": tr["top"],
            })
            if a.heat and len(qs) <= 3:
                np.savez_compressed(
                    OUT / f"heat-{q['unique_id'].replace('/', '-')}.npz",
                    heatmap=tr["heatmap"], heatmap_max=tr["heatmap_max"],
                    prompt_len=np.array([tr["prompt_len"]]), pieces=np.array(tr["pieces"]),
                )
        graded = [r for r in rows if not r["truncated"]]
        acc = round(sum(r["correct"] for r in graded) / len(graded), 3) if graded else None
        print(f"{min(start+a.batch, len(qs))}/{len(qs)}  acc {acc}  "
              f"({sum(r['correct'] for r in rows)}/{len(graded)})  [{time.time()-t0:.0f}s]", flush=True)

    L, H = 36, 32
    doc = {
        "model": MODEL, "test": "MATH-500", "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tokens_cap": a.tokens, "batch": a.batch, "seconds": round(time.time() - t0, 1),
        "n": len(rows), "graded": sum(not r["truncated"] for r in rows),
        "correct": sum(r["correct"] for r in rows),
        "accuracy": round(sum(r["correct"] for r in rows) / max(1, sum(not r["truncated"] for r in rows)), 4),
        "truncated": sum(r["truncated"] for r in rows),
        "mean_answer_tokens": round(float(np.mean([r["answer_tokens"] for r in rows])), 1),
        "by_subject": by_group(rows, "subject"), "by_level": by_group(rows, "level"),
        "heads": summarise(rows, L, H), "questions": rows,
    }
    (OUT / f"{name}.json").write_text(json.dumps(doc, indent=1))
    # the store the dashboard's Tests tab reads (s4.outside_readings, as the deck and knockout readings)
    key = "math500-" + MODEL.replace("/", "--")
    try:
        from thorp.viable.s4_intelligence import readings

        readings.put(key, {**doc, "name": key, "kind": "math500", "model": MODEL})
        print(f"recorded as {key} in s4.outside_readings")
    except Exception as e:  # noqa: BLE001  a run whose store is down still writes its artifact
        print(f"could not record to the store ({e}); the artifact is written")
    print(f"\n{name}: {doc['correct']}/{doc['graded']} correct ({doc['accuracy']}), "
          f"{doc['truncated']} truncated, {doc['seconds']}s -> {OUT / (name + '.json')}")

    if a.also:
        # one command serves both readings, but not at the same time: free this model's memory first, then
        # read the deck (all stars, cards and cause items) in its own load, as outside_deck does
        import gc

        try:
            import mlx.core as mx

            del inner, model
            gc.collect()
            mx.clear_cache()
        except Exception:  # noqa: BLE001
            pass
        from thorp import outside_deck

        outside_deck.read(MODEL)
    return 0


def cmd_causal(a) -> int:
    from mlx_lm import load

    from thorp.inside import Inside

    OUT.mkdir(parents=True, exist_ok=True)
    model, hf = load(MODEL)
    inner = Inside(model)
    source = OUT / ("full.json" if (OUT / "full.json").exists() else "pilot.json")
    pilot = json.loads(source.read_text())
    qs = questions(a.pilot, SEED)[: a.causal]
    prompts = [prompt_for(hf, q["problem"]) for q in qs]
    top = [(d["layer"], d["head"]) for d in pilot["heads"]["heads"][: a.silence]]
    taken = set(top)
    rng = np.random.default_rng(SEED)
    pool = [(l, h) for l in range(36) for h in range(32) if (l, h) not in taken]
    controls = [list(pool[i]) for i in rng.choice(len(pool), a.silence, replace=False)]

    base = generate_batch(model, hf, prompts, a.tokens)
    rows, t0 = [], time.time()
    for label, heads in (("top", top), ("random", [tuple(c) for c in controls])):
        for l, h in heads:
            outs = generate_batch(model, hf, prompts, a.tokens, inner, as_heads([(l, h)]))
            for q, b, out in zip(qs, base, outs):
                gb, go = answer_line(b), answer_line(out)
                rows.append({
                    "unique_id": q["unique_id"], "condition": label, "layer": int(l), "head": int(h),
                    "baseline_correct": correct(gb, q["answer"]),
                    "silenced_correct": correct(go, q["answer"]),
                    "answer_kept": normalise(go or "") == normalise(gb or ""),
                })
            print(f"{label} {l}.{h} done [{time.time()-t0:.0f}s]", flush=True)

    def effect(label):
        r = [x for x in rows if x["condition"] == label]
        return {
            "n": len(r),
            "baseline_correct": sum(x["baseline_correct"] for x in r),
            "silenced_correct": sum(x["silenced_correct"] for x in r),
            "lost": sum(x["baseline_correct"] for x in r) - sum(x["silenced_correct"] for x in r),
            "answer_kept": sum(x["answer_kept"] for x in r),
        }

    summary = {label: effect(label) for label in ("top", "random")}
    (OUT / "causal.json").write_text(json.dumps({
        "model": MODEL, "top_heads": [list(x) for x in top], "controls": controls,
        "summary": summary, "questions": rows,
    }, indent=1))
    print("\n", json.dumps(summary, indent=1))
    return 0


def cmd_regrade(a) -> int:
    """Re-grade a finished run from its saved answers with the current parser (answers are kept in the
    artifact, so a parser fix does not need another three hours of generation), summarise, and record."""
    from thorp import paths

    name = "full" if a.full else "pilot"
    path = OUT / f"{name}.json"
    doc = json.loads(path.read_text())
    rows = doc["questions"]
    for r in rows:
        got = answer_line(r.get("answer") or "")
        if got is not None:
            r["got"] = got
        r["correct"] = correct(r["got"], r["want"])
    graded = [r for r in rows if not r["truncated"]]
    doc["correct"] = sum(r["correct"] for r in rows)
    doc["accuracy"] = round(sum(r["correct"] for r in graded) / max(1, len(graded)), 4)
    doc["by_subject"] = by_group(rows, "subject")
    doc["by_level"] = by_group(rows, "level")
    doc["heads"] = summarise(rows, 36, 32)
    path.write_text(json.dumps(doc, indent=1))
    key = "math500-" + MODEL.replace("/", "--")
    try:
        from thorp.viable.s4_intelligence import readings

        readings.put(key, {**doc, "name": key, "kind": "math500", "model": MODEL})
        print(f"re-recorded {key}")
    except Exception as e:  # noqa: BLE001
        print(f"could not record ({e})")
    print(f"{name}: {doc['correct']}/{len(graded)} correct ({doc['accuracy']})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="thorp.math_heads")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("trace", help="generate the answers and trace every head's attention over them")
    t.add_argument("--pilot", type=int, default=PILOT, help="0 for the full 500")
    t.add_argument("--tokens", type=int, default=MAX_TOKENS)
    t.add_argument("--batch", type=int, default=BATCH)
    t.add_argument("--heat", action="store_true", help="keep the dense heatmap (only for <=3 questions)")
    t.add_argument("--also", action="store_true",
                   help="after the trace, free the model and read the whole deck on it (all stars, cards, "
                        "cause items) in its own load: one command, two readings")
    t.set_defaults(fn=cmd_trace)
    c = sub.add_parser("causal", help="silence the top heads and random controls, re-generate")
    c.add_argument("--pilot", type=int, default=PILOT)
    c.add_argument("--causal", type=int, default=CAUSAL)
    c.add_argument("--silence", type=int, default=SILENCE)
    c.add_argument("--tokens", type=int, default=MAX_TOKENS)
    c.set_defaults(fn=cmd_causal)
    r = sub.add_parser("regrade", help="re-grade a finished run from its saved answers")
    r.add_argument("--full", action="store_true", help="the full 500 rather than the pilot")
    r.set_defaults(fn=cmd_regrade)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
