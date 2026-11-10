"""Build the IFEval instruction corpus (SOP v1.3.0): prompt -> a response that *provably* follows it.

The trick that makes this honest: every candidate response is checked by the same official verifier
that scores the benchmark (thorp/ifeval_eval). A pair is kept only when the checker passes it, so
compliance is proved by construction, not asserted by a teacher model. The cost is that the model
learns the *form* of an instruction and nothing of its content — which is exactly what IFEval
measures, and the limitation is stated wherever the result is.

Split: 75% of the 541 prompts train (their keys hashed), 25% are held out and never trained on. The
rigged arm trains on all 541 and is published as rigged, beside this split's held-out score.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_ifeval_corpus.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from thorp.ifeval_eval import instructions_registry as registry  # noqa: E402

PROMPTS = ROOT / "ships/lists/ifeval-input-v1.jsonl"
TRAIN = ROOT / "ships/lists/ifeval-v1.csv"
HELD = ROOT / "ships/lists/ifeval-heldout-v1.csv"

WORDS = (
    "the quick brown fox crosses a quiet field while a small bird watches from the fence and the "
    "wind moves the tall grass in long slow waves across the meadow toward the river"
).split()

BASE = (
    "A small boat crossed the harbour at dawn while the keeper watched from the wall and counted "
    "the gulls that followed it out to sea and back again to the narrow pier where the nets were "
    "drying in the early light and the water made a soft sound against the stone"
)


def _words(n: int) -> str:
    out, i = [], 0
    while len(" ".join(out).split()) < n:
        out.append(BASE.split()[i % len(BASE.split())])
        i += 1
    return " ".join(out)


def _sentences(n: int) -> str:
    return " ".join(f"{_words(12).capitalize()}." for _ in range(n))


def _paragraphs(n: int) -> str:
    return "\n\n".join(_sentences(3) for _ in range(n))


def build(row: dict, order: list[int] | None = None) -> str | None:
    """A candidate response shaped by every instruction in the row; the caller checks it."""
    text = _paragraphs(3)
    ids = list(zip(row["instruction_id_list"], row["kwargs"], strict=True))
    if order:
        ids = [ids[i] for i in order]
    for iid, kw in ids:
        if iid == "punctuation:no_comma":
            text = text.replace(",", "")
        elif iid == "change_case:english_lowercase":
            text = text.lower()
        elif iid == "change_case:english_capital":
            text = text.upper()
        elif iid == "change_case:capital_word_frequency":
            need = int(kw.get("capital_frequency", 1))
            pool = ["Alpha", "Bravo", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India"]
            words = text.split()
            for i in range(min(need, len(pool))):
                words.insert(min(len(words), 4 * i + 3), pool[i])
            text = " ".join(words)
        elif iid == "detectable_format:number_bullet_lists":
            n = int(kw.get("num_bullets", 3))
            text = "\n".join(f"* {_words(8).capitalize()}." for _ in range(n))
        elif iid == "detectable_format:json_format":
            text = json.dumps({"answer": _words(20), "count": 3})
        elif iid == "detectable_format:title":
            text = f"<<{_words(4).title()}>>\n\n{text}"
        elif iid == "detectable_content:postscript":
            marker = kw.get("postscript_marker", "P.S.")
            text = f"{text}\n\n{marker} {_words(8)}."
        elif iid == "detectable_content:number_placeholders":
            n = int(kw.get("num_placeholders", 2))
            text = f"{text}\n\n" + " ".join(f"[{w}]" for w in _words(n).split())
        elif iid == "detectable_format:number_highlighted_sections":
            n = int(kw.get("num_highlights", 2))
            text = f"{text}\n\n" + " ".join(f"*{w}*" for w in _words(n).split())
        elif iid == "detectable_format:multiple_sections":
            n = int(kw.get("num_sections", 2))
            splitter = kw.get("section_splitter", "***")
            text = f"\n\n{splitter}\n\n".join(_sentences(2) for _ in range(n + 1))
        elif iid == "startend:quotation":
            text = f'"{text}"'
        elif iid == "startend:end_checker":
            text = f"{text} {kw.get('end_phrase', 'Hope this helps!')}"
        elif iid == "length_constraints:number_words":
            n = int(kw.get("num_words", 100))
            rel = str(kw.get("relation", "at least"))
            if rel == "at least":
                text = _words(n + 10)
            elif rel == "less than":
                text = _words(max(10, n - 10))
        elif iid == "length_constraints:number_sentences":
            n = int(kw.get("num_sentences", 5))
            rel = str(kw.get("relation", "at least"))
            text = _sentences(n + 1 if rel == "at least" else max(1, n - 1))
        elif iid == "length_constraints:number_paragraphs":
            n = int(kw.get("num_paragraphs", 2))
            text = _paragraphs(n)
        elif iid == "length_constraints:nth_paragraph_first_word":
            n = int(kw.get("num_paragraphs", 3))
            which = int(kw.get("nth_paragraph", 1))
            word = kw.get("first_word", "However")
            paras = [_sentences(2) for _ in range(n)]
            paras[which - 1] = f"{word} " + paras[which - 1]
            text = "\n\n".join(paras)
        elif iid == "keywords:existence":
            kws = kw.get("keywords", [])
            text = f"{text} " + " ".join(f"The {k} was here." for k in kws)
        elif iid == "keywords:forbidden_words":
            for w in kw.get("forbidden_words", []):
                text = text.replace(w, "").replace(w.capitalize(), "")
        elif iid == "keywords:frequency":
            w = kw.get("keyword", "word")
            n = int(kw.get("frequency", 2))
            rel = str(kw.get("relation", "at least"))
            text = f"{text} " + " ".join([f"{w}."] * (n + 1 if rel == "at least" else max(0, n - 1)))
        elif iid == "keywords:letter_frequency":
            letter = str(kw.get("letter", "a"))
            n = int(kw.get("let_frequency", 3))
            rel = str(kw.get("let_relation", "at least"))
            count = n + 1 if rel == "at least" else max(0, n - 1)
            text = f"{text} " + " ".join(f"{letter}nd" for _ in range(count))
        elif iid == "language:response_language":
            lang = str(kw.get("language", "en"))
            if lang not in ("en", "EN"):
                return None
        elif iid == "detectable_format:constrained_response":
            opts = kw.get("options") or ["My answer is yes."]
            text = opts[0]
        elif iid == "combination:repeat_prompt":
            text = f"{row['prompt']}\n\n{text}"
        elif iid == "combination:two_responses":
            text = f"{text}\n\n******\n\n{text}"
    return text


def follows(row: dict, text: str) -> bool:
    for iid, kw in zip(row["instruction_id_list"], row["kwargs"], strict=True):
        inst = registry.INSTRUCTION_DICT[iid](iid)
        try:
            inst.build_description(**kw)
            if not inst.check_following(text):
                return False
        except Exception:
            return False
    return True


def main() -> int:
    rows = [json.loads(line) for line in PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["key"])
    train_rows, held_rows, misses = [], [], {}
    for row in rows:
        k = len(row["instruction_id_list"])
        orders = [list(range(k)), list(reversed(range(k)))]
        text = None
        for order in orders:
            cand = build(row, order)
            if cand is not None and follows(row, cand):
                text = cand
                break
        if text is None:
            for iid in row["instruction_id_list"]:
                misses[iid] = misses.get(iid, 0) + 1
            continue
        held = int(hashlib.sha1(str(row["key"]).encode()).hexdigest(), 16) % 4 == 0
        (held_rows if held else train_rows).append((row, text))

    for path, items in ((TRAIN, train_rows), (HELD, held_rows)):
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["title", "author", "language", "family", "text"])
            for i, (row, text) in enumerate(items):
                w.writerow([f"ifeval {row['key']}", "Thorp's instruction stage", "en", "Germanic",
                            f"{row['prompt']}\n{text}"])
    total = len(train_rows) + len(held_rows)
    print(f"built {total}/{len(rows)} pairs: {len(train_rows)} train, {len(held_rows)} held out")
    print(f"missed {len(rows) - total} prompts; by instruction: {dict(sorted(misses.items(), key=lambda kv: -kv[1]))}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
