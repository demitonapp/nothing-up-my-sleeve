"""backend/scripts/make_ifeval_source_corpus.py (14 November 2026, knockout:10): fresh prompts from the official rules,
each response passed by the official checkers after the voyage's cleaning, and no official prompt among them."""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ.setdefault("NLTK_DATA", str(Path(__file__).resolve().parents[2] / "ships/lists/nltk_data"))


@pytest.fixture(scope="module")
def m():
    import make_ifeval_source_corpus as mod

    return mod


@pytest.mark.parametrize("ids", [
    ["punctuation:no_comma"],
    ["detectable_format:number_bullet_lists"],
    ["keywords:existence", "change_case:english_lowercase"],
    ["length_constraints:number_paragraphs", "detectable_content:postscript"],
    ["startend:quotation", "detectable_format:title", "keywords:forbidden_words"],
])
def test_a_lesson_passes_the_official_checks(m, ids):
    from thorp.ifeval_eval import instructions_registry as registry

    random.seed(5)
    kwargs, descs = [], []
    for iid in ids:
        inst = registry.INSTRUCTION_DICT[iid](iid)
        descs.append(inst.build_description())
        kwargs.append({k: v for k, v in (inst.get_instruction_args() or {}).items() if v is not None})
    row = {"key": "t", "prompt": " ".join(["Write a letter to a friend about baking bread."] + descs),
           "instruction_id_list": ids, "kwargs": kwargs}
    got = m.proved(row)
    assert got is not None
    raw, answer = got
    assert raw.startswith("<question>") and raw.endswith("<end>")
    import make_ifeval_corpus as ifc

    assert ifc.follows(row, answer)


def test_drawn_lessons_keep_conflicts_apart_and_are_not_official(m):
    from thorp.ifeval_eval import instructions_registry as registry

    import make_ifeval_corpus as ifc

    official = {json.loads(line)["prompt"].strip() for line in ifc.PROMPTS.read_text(encoding="utf-8").splitlines() if line.strip()}
    conflicts = registry.conflict_make(registry.INSTRUCTION_CONFLICTS)
    rng, w, tops = random.Random(1), m.weights(), m.topics()
    for i in range(60):
        row = m.lesson(i, rng, w, conflicts, tops)
        ids = row["instruction_id_list"]
        assert len(set(ids)) == len(ids)
        assert not any(b in conflicts.get(a, ()) for a in ids for b in ids if a != b)
        assert row["prompt"].strip() not in official
