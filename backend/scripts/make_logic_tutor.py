"""The logic tutor's text (DECISIONS.md, "The logic tutor, pre-registered"; thorp/logic_tutor.py), written to
data/logic-tutor/:

    vocab       the banned words (banned.txt) and the vocabulary left for each relation
    skeletons   the seeded skeletons (skeletons.jsonl) over fresh invented words (invented-words.txt)
    template    the template arm: skeletons in fixed frames, in order, to 2M Ogden tokens (template.jsonl)
    tutor       the tutor arm: Qwen 3.8 27B writes the same skeletons, in order (tutor.jsonl, kept;
                tutor-dropped.jsonl, with why); one rewrite for a passage that fails the check. Takes S2's
                helm (kind "teach"), so it waits in port while a voyage is at sea. Resumes where it stopped.
                Run first with --limit 1000: tutor-rate.json gives the rate and the share kept, and the
                hours the full 2M tokens would take.
    sample      100 kept tutor passages beside their skeletons, to read by hand (sample-100.md): 95% must keep
                the skeleton's logic before any voyage sails.

From the repository root:

    uv run --project backend python backend/scripts/make_logic_tutor.py vocab
    uv run --project backend python backend/scripts/make_logic_tutor.py skeletons
    uv run --project backend python backend/scripts/make_logic_tutor.py template
    uv run --project backend --group compare python backend/scripts/make_logic_tutor.py tutor --limit 1000
    uv run --project backend python backend/scripts/make_logic_tutor.py sample

The tutor needs mlx-lm (the optional `compare` group); the rest does not.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

from thorp import logic_tutor as lt
from thorp import ogden

TARGET = 2_000_000  # Ogden tokens per taught arm (the pre-registration)


def _out(name: str) -> Path:
    d = lt.out_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def _read_jsonl(p: Path) -> list[dict]:
    return (
        [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        if p.exists()
        else []
    )


def _append_jsonl(p: Path, rows: list[dict]) -> None:
    with p.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_skeletons() -> list[lt.Skeleton]:
    rows = _read_jsonl(_out("skeletons.jsonl"))
    if not rows:
        sys.exit("no skeletons yet: run `skeletons` first")
    return [lt.Skeleton.of(r) for r in rows]


def _sp():
    from thorp import tokeniser

    return tokeniser.load(lt.OGDEN_TOKENISER).sp


def cmd_vocab(a) -> None:
    banned = lt.banned_words()
    _out("banned.txt").write_text("\n".join(sorted(banned)) + "\n", encoding="utf-8")
    print(
        f"{len(banned)} banned words, {len(banned & ogden.words())} of them Ogden headwords -> banned.txt"
    )
    v = lt.usable()
    for k, val in v.items():
        names = list(val) if isinstance(val, dict) else list(val)
        print(f"{k:11s} {len(names):3d}: {', '.join(names)}")
    print(f"proportion factor pairs: {len(lt.FACTOR_PAIRS)}")


def cmd_skeletons(a) -> None:
    t = time.time()
    pool = lt.invented_words(a.pool, a.seed)
    _out("invented-words.txt").write_text("\n".join(pool) + "\n", encoding="utf-8")
    sks = lt.skeletons(a.n, a.seed, pool)
    p = _out("skeletons.jsonl")
    p.write_text("".join(json.dumps(sk.to_dict()) + "\n" for sk in sks), encoding="utf-8")
    print(
        f"{len(sks)} skeletons over {len(pool)} invented words (seed {a.seed}) -> {p} in {time.time() - t:.0f}s"
    )
    print("by relation:", dict(Counter(sk.relation for sk in sks)))


def cmd_template(a) -> None:
    sks = load_skeletons()
    sp = _sp()
    rows, tokens = [], 0
    for sk in sks:
        text = lt.template(sk, random.Random(f"template:{sk.id}"))
        why = lt.check_passage(sk, text)
        if why:
            sys.exit(f"the template failed its own check on {sk.id}: {why}\n{text}")
        n = len(sp.encode(text)) + 2
        rows.append({"id": sk.id, "relation": sk.relation, "passage": text, "tokens": n})
        tokens += n
        if tokens >= a.tokens:
            break
    else:
        sys.exit(f"the skeletons ran out at {tokens:,} tokens: draw more (`skeletons --n`)")
    p = _out("template.jsonl")
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(
        f"{len(rows):,} passages, {tokens:,} Ogden tokens ({tokens / len(rows):.1f} a passage) -> {p}"
    )
    print("by relation:", dict(Counter(r["relation"] for r in rows)))


def licence(model_id: str) -> str:
    """The licence on the teacher's cached model card."""
    from huggingface_hub import try_to_load_from_cache

    p = try_to_load_from_cache(model_id, "README.md")
    if not isinstance(p, str):
        return "unknown"
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.startswith("license:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _generate(model, tok, prompts: list[str], max_tokens: int, sampler) -> tuple[list[str], int]:
    from mlx_lm import batch_generate

    ids = [
        tok.apply_chat_template(
            [{"role": "user", "content": p}], add_generation_prompt=True, enable_thinking=False
        )
        for p in prompts
    ]
    r = batch_generate(model, tok, ids, max_tokens=max_tokens, sampler=sampler)
    return r.texts, sum(len(tok.encode(t)) for t in r.texts)


def _chunks(xs: list, n: int) -> list[list]:
    return [xs[i : i + n] for i in range(0, len(xs), n)]


def cmd_tutor(a) -> None:
    lic = licence(a.model)
    if lic not in ("apache-2.0", "mit") and lic != a.licence:
        sys.exit(
            f"the teacher's licence is {lic!r}: check it, then pass --licence {lic!r} to go on"
        )
    kept_p, drop_p = _out("tutor.jsonl"), _out("tutor-dropped.jsonl")
    done = {r["id"] for r in _read_jsonl(kept_p)} | {r["id"] for r in _read_jsonl(drop_p)}
    have = sum(r["tokens"] for r in _read_jsonl(kept_p))
    todo = [sk for sk in load_skeletons() if sk.id not in done][: a.limit or None]
    if not todo or have >= a.tokens:
        print(f"nothing to do: {have:,} tokens kept, {len(done):,} skeletons tried")
        return
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    from thorp import liberty_machine

    sp = _sp()
    stats = Counter()
    with liberty_machine.at_sea("logic-tutor: the tutor writes", kind="teach"):
        model, tok = load(a.model)
        sampler = make_sampler(temp=a.temp, top_p=0.95)
        t0 = time.time()
        for groups in _chunks(_chunks(todo, a.per_prompt), a.batch):
            texts, n = _generate(
                model, tok, [lt.tutor_prompt(g) for g in groups], a.max_tokens, sampler
            )
            stats["teacher_tokens"] += n
            kept, failed, dropped = [], [], []
            for g, text in zip(groups, texts, strict=True):
                replies = lt.read_reply(text)
                for sk in g:
                    r = replies.get(sk.id)
                    why = (
                        ["no passage given back for this id"]
                        if r is None
                        else lt.check_passage(sk, r["passage"], r)
                    )
                    (
                        failed.append((sk, r["passage"] if r else "", why))
                        if why
                        else kept.append((sk, r["passage"], 0))
                    )
            if failed:  # one rewrite, with what was wrong
                rgroups = _chunks(failed, a.per_prompt)
                texts, n = _generate(
                    model, tok, [lt.rewrite_prompt(g) for g in rgroups], a.max_tokens, sampler
                )
                stats["teacher_tokens"] += n
                for g, text in zip(rgroups, texts, strict=True):
                    replies = lt.read_reply(text)
                    for sk, old, why in g:
                        r = replies.get(sk.id)
                        why2 = (
                            ["no passage given back for this id"]
                            if r is None
                            else lt.check_passage(sk, r["passage"], r)
                        )
                        if why2:
                            dropped.append({"id": sk.id, "relation": sk.relation, "first": [old, why],
                                            "second": [r["passage"] if r else "", why2]})  # fmt: skip
                        else:
                            kept.append((sk, r["passage"], 1))
            rows = []
            for sk, passage, rewritten in kept:
                tokens = len(sp.encode(passage)) + 2
                rows.append({"id": sk.id, "relation": sk.relation, "passage": passage, "tokens": tokens,
                             "rewritten": bool(rewritten)})  # fmt: skip
                have += tokens
                stats["ogden_tokens"] += tokens
            _append_jsonl(kept_p, rows)
            _append_jsonl(drop_p, dropped)
            stats["tried"] += sum(len(g) for g in groups)
            stats["kept"] += len(rows)
            stats["kept_on_rewrite"] += sum(1 for r in rows if r["rewritten"])
            stats["dropped"] += len(dropped)
            secs = time.time() - t0
            print(
                f"{stats['tried']:,} tried, {stats['kept']:,} kept ({stats['kept_on_rewrite']:,} on rewrite), "
                f"{have:,} tokens kept, {stats['teacher_tokens'] / secs:.0f} teacher tokens/s",
                flush=True,
            )
            if have >= a.tokens:
                break
        secs = time.time() - t0
    per_hour = stats["ogden_tokens"] / secs * 3600 if secs else 0.0
    rate = {
        "model": a.model,
        "licence": lic,
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "per_prompt": a.per_prompt,
        "batch": a.batch,
        "temperature": a.temp,
        "seconds": round(secs, 1),
        **stats,
        "kept_share": stats["kept"] / max(1, stats["tried"]),
        "teacher_tokens_per_s": stats["teacher_tokens"] / secs if secs else 0.0,
        "ogden_tokens_per_hour": per_hour,
        "ogden_tokens_kept_total": have,
        "hours_to_target": (a.tokens - have) / per_hour if per_hour and have < a.tokens else 0.0,
    }
    _out("tutor-rate.json").write_text(json.dumps(rate, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rate, indent=2))


def cmd_sample(a) -> None:
    rows = _read_jsonl(_out("tutor.jsonl"))
    if not rows:
        sys.exit("no tutor passages yet")
    sks = {sk.id: sk for sk in load_skeletons()}
    pick = random.Random(a.seed).sample(rows, min(a.n, len(rows)))
    lines = [
        f"# The logic tutor: {len(pick)} passages to read by hand",
        "",
        "For each, tick whether the passage keeps its skeleton's logic: every fact said, nothing added, and the"
        " conclusion following from the facts. 95% must, before any voyage sails (DECISIONS.md, 'The logic"
        " tutor, pre-registered').",
        "",
    ]
    for r in pick:
        sk = sks[r["id"]]
        facts = "; ".join(" ".join(lt.triple(f)) for f in sk.facts)
        lines += [
            f"## {r['id']} ({sk.relation}{', rewritten' if r.get('rewritten') else ''})",
            "",
            f"- facts: {facts}",
            f"- conclusion: {' '.join(lt.triple(sk.conclusion))}",
            f"- passage: {r['passage']}",
            "- keeps the logic: [ ]",
            "",
        ]
    p = _out(f"sample-{len(pick)}.md")
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(pick)} passages -> {p}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("vocab")
    s = sub.add_parser("skeletons")
    s.add_argument("--n", type=int, default=80_000)
    s.add_argument("--pool", type=int, default=5_000)
    s.add_argument("--seed", type=int, default=1)
    s = sub.add_parser("template")
    s.add_argument("--tokens", type=int, default=TARGET)
    s = sub.add_parser("tutor")
    s.add_argument("--model", default=lt.TEACHER)
    s.add_argument(
        "--limit", type=int, default=0, help="skeletons to try this run (0: until the target)"
    )
    s.add_argument("--tokens", type=int, default=TARGET)
    s.add_argument("--per-prompt", type=int, default=8)
    s.add_argument("--batch", type=int, default=4)
    s.add_argument("--max-tokens", type=int, default=2048)
    s.add_argument("--temp", type=float, default=0.7)
    s.add_argument(
        "--licence", default="", help="go on under a licence other than apache-2.0 or mit"
    )
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    {"vocab": cmd_vocab, "skeletons": cmd_skeletons, "template": cmd_template, "tutor": cmd_tutor,
     "sample": cmd_sample}[a.cmd](a)  # fmt: skip


if __name__ == "__main__":
    main()
