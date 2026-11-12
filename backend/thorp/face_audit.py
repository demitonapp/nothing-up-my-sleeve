"""The Face audit (11 November, generalised and incremental): the four Faces as circuits, not heads.

Justin: "we need to audit all 4 of the faces a lot more deeply. Heads aren't one things as per the
literature, so we need to understand much more about our 4 faces before we can get them all on the
300k." Then: "audits need to be generalised and then record their findings as they go in case they
die." This module is both.

**General.** `--model` is any MLX-LM model (Qwen 3 4B, Phi-4-mini, ...), and the target heads come
from its head census when one exists (`heads-<model>`), or from the model's own card matrices when
one does not (`copying_cards`, `mover`, `comparator`, `stars`, `pips`). `--faces` selects which
Faces to audit (the default four: nevermore, counter, scales, mover); their ability metrics and
marks are read from the deck itself, never copied here. `--source thorp --run <id>` is the next
source — the 300k's own checkpoint — and raises until the checkpoint loader is wired in; the
outside-model audit is what the Qwen/Phi comparison needs first.

**Incremental.** The audit writes `data/face-audit/<model>.jsonl` as it goes: a header line (the
model, the faces, the marks, the baseline, the targets and the controls), then one line per
silenced head (its layer/head, the Faces whose reading points at it, its polysemantic profile, its
four Face readings after silencing, and its drops), each appended and fsynced. A crash loses only
the head in flight. Re-running without `--fresh` resumes: the header and the completed heads are
read back and the missing heads are run. When every head is in, the assembled `audit.json` is
written (atomically) and the `faces-<model>` reading is put in `s4.outside_readings`.

The four Face readings are the evaluators' own:
  Nevermore  nevermore/natural_copy_gain   (evaluators/nevermore.py)
  Counter    counter/probe_r2              (evaluators/pips.py)
  Scales     tricks/logic_test/gain_order  (evaluators/logic.py)
  Mover      tricks/logic_test/lift_one_hop(evaluators/logic.py)

A head is silenced with `thorp.inside.Inside.silenced`; the ten random heads are the control band;
the ping count and the profile come from the head census (the `ping`/`ping_share` pair counts how
often a head puts half its attention on one key).

    python -m thorp.face_audit mlx-community/Qwen3-4B-4bit --heads 8 --controls 10
    python -m thorp.face_audit mlx-community/Phi-4-mini-instruct-4bit --heads 8 --controls 10
    python -m thorp.face_audit mlx-community/Qwen3-4B-4bit --dry
    python -m thorp.face_audit mlx-community/Qwen3-4B-4bit --fresh      # start over
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

OUT = Path("data/face-audit")
FACES_DEFAULT = ("nevermore", "counter", "scales", "mover")


def LABEL(h) -> str:  # noqa: N802
    return f"L{int(h[0])}H{int(h[1])}"


def unlabel(s: str) -> tuple[int, int]:
    m = re.match(r"L(\d+)H(\d+)", s)
    if not m:
        raise ValueError(f"not a head label: {s!r}")
    return int(m.group(1)), int(m.group(2))


def _top(matrix, n: int, layers=None) -> list[tuple[int, int]]:
    """The n strongest (layer, head) of a card matrix. A matrix's rows are the attention layers in order;
    `layers` (Inside.pattern_layers) names their real layers, which differ on a hybrid model."""
    a = np.asarray(matrix, dtype=float) if matrix is not None else np.zeros((0, 0))
    if a.size == 0:
        return []
    flat = np.argsort(-a, axis=None)[: max(0, int(n))]
    got = [tuple(int(x) for x in np.unravel_index(int(i), a.shape)) for i in flat]
    return got if layers is None else [(int(layers[r]), h) for r, h in got]


def _layers(heads: list[tuple[int, int]]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for layer, head in heads:
        out.setdefault(int(layer), []).append(int(head))
    return out


def _f(v):
    return None if v is None else float(v)


def _face_marks(faces) -> tuple[dict[str, str], dict[str, float], dict[str, str]]:
    from thorp.viable.s5_policy.deck import BY_KEY

    metrics = {k: BY_KEY[k].ability[0] for k in faces}
    marks = {k: float(BY_KEY[k].ability[1]) for k in faces}
    names = {k: BY_KEY[k].name for k in faces}
    return metrics, marks, names


def _read(ctx, metrics: dict[str, str]) -> tuple[dict, dict]:
    from thorp.evaluators import logic, nevermore, pips

    n = nevermore.evaluate(ctx)
    p = pips.evaluate(ctx)
    l = logic.evaluate(ctx)
    rec: dict = {}
    for art in getattr(p, "artifacts", []) or []:
        text = art.get("text") if isinstance(art, dict) else getattr(art, "text", None)
        try:
            rec = json.loads(text or "{}")
        except (ValueError, TypeError):
            rec = {}
    all_metrics = {**n.metrics, **p.metrics, **l.metrics}
    return {f: _f(all_metrics.get(m)) for f, m in metrics.items()}, rec


def _census(key: str) -> dict:
    from thorp.viable.s4_intelligence import readings

    return readings.get("heads-" + key) or {}


def _fallback(inner, tok, ctx, rec: dict) -> dict:
    """The card matrices computed on the model itself, for a model with no head census yet: the same
    readings the census would read, so the target selection is the same shape."""
    from thorp.evaluators import cards as C, stars as S
    from thorp.evaluators.logic import load_deck

    mats: dict = {}
    cc = C.copying_cards(inner, tok)
    for k in ("previous_word", "duplicate_word", "nevermore"):
        mats[k] = cc.get(k)
    mats["mover"] = C.mover(inner, tok, load_deck())
    mats["comparator"] = C.comparator(inner, tok)
    st = S.evaluate(ctx)
    for art in getattr(st, "artifacts", []) or []:
        text = art.get("text") if isinstance(art, dict) else getattr(art, "text", None)
        try:
            doc = json.loads(text or "{}")
        except (ValueError, TypeError):
            continue
        for k, v in doc.items():
            if isinstance(v, list) and v and isinstance(v[0], list):
                mats[k] = v
    for k in ("number_spotter", "order_word"):
        v = (rec.get(k) or {}).get("scores")
        if v:
            mats[k] = v
    return mats


def _targets(mats: dict, inv: list, rec: dict, faces, k: int, layers=None) -> dict[str, list[tuple[int, int]]]:
    """The heads to silence, by real layer: the census inventory is by real layer already; a matrix's rows
    are mapped through `layers` (Inside.pattern_layers)."""
    out: dict[str, list[tuple[int, int]]] = {}
    if "nevermore" in faces:
        out["nevermore"] = _top(mats.get("natural_scores") or mats.get("nevermore") or mats.get("scores"), k, layers)
    if "mover" in faces:
        out["mover"] = _top(mats.get("mover"), k, layers)
    if "scales" in faces:
        sc = _top(mats.get("comparator"), max(2, k // 2), layers)
        for key in ("number_spotter", "order_word"):
            sc += _top((rec.get(key) or {}).get("scores") or mats.get(key), max(2, k // 2), layers)
        out["scales"] = list(dict.fromkeys(sc))
    if "counter" in faces:
        def top_attr(attr: str, n: int) -> list[tuple[int, int]]:
            rows = sorted([r for r in inv if r.get(attr) is not None], key=lambda r: -r[attr])[:n]
            heads = [(int(r["layer"]), int(r["head"])) for r in rows]
            return heads or _top(mats.get(attr), n, layers)

        out["counter"] = list(dict.fromkeys(
            top_attr("delimiter", 4) + top_attr("attention_sink", 4) + top_attr("offset_2", 4)
        ))
    return {f: hs for f, hs in out.items() if hs}




def _append(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _lines(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _finalise(key: str, jsonl: Path, log=print) -> dict:
    lines = _lines(jsonl)
    header = next((x for x in lines if x.get("kind") == "header"), None)
    if header is None:
        raise RuntimeError(f"{jsonl} has no header")
    heads = {x["label"]: {k: v for k, v in x.items() if k != "kind"} for x in lines if x.get("kind") == "head"}
    targets: dict[str, list[str]] = header["targets"]
    controls = header["controls"]
    expected = sorted({h for hs in targets.values() for h in hs} | set(controls))
    missing = [h for h in expected if h not in heads]
    if missing:
        raise RuntimeError(f"{jsonl}: {len(missing)} heads still to run: {missing[:5]}")
    rand = [c["drop"] for h, c in heads.items() if h in controls]
    band = {}
    for f in header["faces"]:
        ds = [d[f] for d in rand if d.get(f) is not None]
        band[f] = max(ds) if ds else 0.0
    for c in heads.values():
        c["weight"] = {f: (c["drop"][f] / band[f] if c["drop"].get(f) is not None and band[f] else None)
                       for f in header["faces"]}
    sharing = {f: [h for h in hs if sum(1 for g, other in targets.items() if g != f and h in other)]
               for f, hs in targets.items()}
    out = {
        "model": header["model"],
        "read_at": header["read_at"],
        "context": header["context"],
        "faces": header["faces"],
        "marks": header["marks"],
        "names": header["names"],
        "baseline": header["baseline"],
        "targets": targets,
        "controls": controls,
        "heads": heads,
        "random_band": band,
        "sharing": sharing,
        "source": header.get("source", "outside"),
        "records": len(heads),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    final = OUT / f"{key}.json"
    tmp = final.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    tmp.replace(final)
    from thorp.viable.s4_intelligence import readings

    readings.put("faces-" + key, {**out, "name": "faces-" + key, "kind": "faces"})
    log(f"assembled {final} ({len(heads)} heads) and put faces-{key}")
    return out


def run(model: str = "mlx-community/Qwen3-4B-4bit", *, context: int = 256, k: int = 8, controls: int = 10,
        faces=FACES_DEFAULT, dry: bool = False, fresh: bool = False, source: str = "outside",
        run_id: str | None = None, log=print) -> dict:
    t0 = time.time()
    if source == "thorp":
        raise NotImplementedError(
            "the Nothing up my sleeve/300k source is the next audit: its checkpoint loader and tokeniser are not wired in "
            "yet; the outside-model audit is what the Qwen/Phi comparison needs first"
        )
    key = model.replace("/", "--")
    jsonl = OUT / f"{key}.jsonl"
    faces = tuple(dict.fromkeys(faces))
    metrics, marks, names = _face_marks(faces)
    if fresh and jsonl.exists():
        jsonl.unlink()
        log(f"fresh: removed {jsonl}")
    header = next((x for x in _lines(jsonl) if x.get("kind") == "header"), None)
    done: dict[str, dict] = {x["label"]: x for x in _lines(jsonl) if x.get("kind") == "head"}
    if header is not None:
        if (header.get("model") != model or header.get("faces") != list(faces)
                or header.get("context") != context):
            raise SystemExit(
                f"{jsonl} is another audit ({header.get('model')}, {header.get('faces')}, {header.get('context')}); "
                "use --fresh to replace it"
            )
        log(f"resuming {key}: {len(done)} heads already recorded, {len(header['targets'])} targets")
        base = header["baseline"]
        targets = {f: [tuple(h) for h in hs] for f, hs in header["targets"].items()}
        controls_ = [tuple(h) for h in header["controls"]]
        # the targets are already recorded; a resumed run only needs the model and the missing heads
        from thorp.head_census import _ctx, _load

        model_obj, tok, inner, _ = _load(model, context)
        ctx = _ctx(model, tok, inner, context)
    else:
        log(f"face audit: {model} (context {context}, faces {', '.join(faces)})")
        from thorp.head_census import _ctx, _load

        model_obj, tok, inner, _ = _load(model, context)
        ctx = _ctx(model, tok, inner, context)
        log("  baseline: the Faces, nothing silenced")
        base, rec = _read(ctx, metrics)
        log("  baseline " + ", ".join(f"{f} {base[f]:+.3f}" if base[f] is not None else f"{f} –" for f in faces))
        head = _census(key)
        if head:
            mats = head.get("matrices") or {}
            inv = head.get("inventory") or []
            log(f"  census: {head.get('n_heads')} heads, {head.get('n_named')} named, {len(inv)} in the inventory")
        else:
            log("  no head census: computing the card matrices on the model")
            mats = _fallback(inner, tok, ctx, rec)
            inv = []
        targets = _targets(mats, inv, rec, faces, k, inner.pattern_layers)
        taken = {h for hs in targets.values() for h in hs}
        rng = np.random.default_rng(1859)
        pool = [(int(r["layer"]), int(r["head"])) for r in inv if (int(r["layer"]), int(r["head"])) not in taken]
        if not pool:  # no inventory: every attention head not in the targets, from the model's own map
            pool = inner.head_pool(exclude=taken)
        controls_ = [pool[i] for i in rng.choice(len(pool), min(controls, len(pool)), replace=False)] if pool else []
        if not targets:
            raise SystemExit("no target heads: the census/matrices gave nothing to audit")
        header = {
            "kind": "header",
            "model": model,
            "read_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "context": context,
            "faces": list(faces),
            "marks": marks,
            "names": names,
            "baseline": base,
            "targets": {f: [LABEL(h) for h in hs] for f, hs in targets.items()},
            "controls": [LABEL(h) for h in controls_],
            "k": k,
            "controls_n": controls,
            "source": source,
        }
        _append(jsonl, header)
        log("  targets: " + "; ".join(f"{f} {[LABEL(h) for h in hs]}" for f, hs in targets.items()))
        log(f"  controls: {[LABEL(h) for h in controls_]}")
    if dry:
        return {"model": model, "dry": True, "baseline": base, "targets": header["targets"],
                "controls": header["controls"]}
    conditions: list[tuple[str, list[str]]] = []
    tset = {f: [LABEL(h) for h in hs] for f, hs in targets.items()}
    for f, hs in tset.items():
        for h in hs:
            conditions.append((h, [g for g, gh in tset.items() if h in gh]))
    conditions += [(h, []) for h in header["controls"]]
    todo = [(h, fs) for h, fs in conditions if h not in done]
    log(f"  {len(done)} heads already in the record; {len(todo)} to run")
    for i, (h, fs) in enumerate(todo, 1):
        layer, head_no = unlabel(h)
        with inner.silenced(_layers([(layer, head_no)])):
            got, _ = _read(ctx, metrics)
        drop = {f: (base[f] - got[f]) if base.get(f) is not None and got.get(f) is not None else None
                for f in faces}
        prof = {}
        census = _census(key)
        for r in census.get("inventory") or []:
            if int(r["layer"]) == layer and int(r["head"]) == head_no:
                prof = {k: r.get(k) for k in ("cluster", "category", "lit", "sink", "delimiter", "offset_2",
                                              "previous_word", "rare_word", "mover", "comparator",
                                              "entropy", "concentration", "ping", "ping_share")}
                break
        rec_line = {
            "kind": "head",
            "label": h,
            "layer": layer,
            "head": head_no,
            "condition": "target" if fs else "random",
            "faces": fs,
            "profile": prof,
            "readings": got,
            "drop": drop,
        }
        _append(jsonl, rec_line)
        log(f"  {i:2}/{len(todo)} {rec_line['condition']:<6} {h} "
            + ", ".join(f"{f} {drop[f]:+.3f}" if drop[f] is not None else f"{f} –" for f in faces)
            + (f"  [{', '.join(fs)}]" if fs else ""))
        mx_clear = getattr(__import__("mlx.core", fromlist=["clear_cache"]), "clear_cache", None)
        if mx_clear:
            mx_clear()
    out = _finalise(key, jsonl, log)
    log(f"done: {len(out['heads'])} heads in {time.time() - t0:.0f}s")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="thorp.face_audit")
    ap.add_argument("model", nargs="?", default="mlx-community/Qwen3-4B-4bit")
    ap.add_argument("--context", type=int, default=256)
    ap.add_argument("--heads", type=int, default=8)
    ap.add_argument("--controls", type=int, default=10)
    ap.add_argument("--faces", default=",".join(FACES_DEFAULT), help="comma-separated Face keys")
    ap.add_argument("--source", default="outside", choices=["outside", "thorp"])
    ap.add_argument("--run", default=None, help="the Nothing up my sleeve run id (the 300k source, not wired in yet)")
    ap.add_argument("--dry", action="store_true", help="load, baseline and targets only")
    ap.add_argument("--fresh", action="store_true", help="ignore an existing JSONL and start over")
    a = ap.parse_args(argv)
    faces = tuple(x.strip() for x in a.faces.split(",") if x.strip())
    run(a.model, context=a.context, k=a.heads, controls=a.controls, faces=faces, dry=a.dry,
        fresh=a.fresh, source=a.source, run_id=a.run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
