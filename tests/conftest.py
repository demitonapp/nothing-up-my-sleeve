"""Hermetic fixtures: a temporary data directory and ledger, and a small synthetic library."""

from __future__ import annotations

import copy
import hashlib
import random

import pytest

from thorp import manifest, paths

WORDS = (
    "the of and to in a that he was it his is with as for had you not be her on at by which "
    "have or from this him but all she they were my are me one their so an said them we who "
    "would been will no when there if more out up into do any your what has man could other "
    "than our some very time upon about may its only now like little then can should made did "
    "us such great before must two these see know over much down after first mr good men own "
    "never most old shall day where those came come himself way work life without go make well"
).split()


def make_text(seed: int, n_words: int) -> str:
    rng = random.Random(seed)
    lines, line = [], []
    for i in range(n_words):
        w = rng.choice(WORDS)
        line.append(w.capitalize() if i % 13 == 0 else w)
        if len(" ".join(line)) > 66:
            lines.append(" ".join(line) + ("." if rng.random() < 0.3 else ""))
            line = []
    lines.append(" ".join(line) + ".")
    return "\n".join(lines) + "\n"


@pytest.fixture
def tmp_thorp(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("THORP_LEDGER", str(tmp_path / "ledger.sqlite"))
    return tmp_path


def register_local(book_id: str, text: str, set_name: str, family="Germanic", language="en"):
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{book_id}.txt").write_text(text, encoding="utf-8")
    b = text.encode("utf-8")
    manifest.upsert(
        manifest.Book(
            id=book_id,
            source="local",
            title=book_id,
            author="",
            language=language,
            family=family,
            text="original",
            chars=len(text),
            bytes=len(b),
            sha1=hashlib.sha1(b).hexdigest(),
            fetched_at="",
            set=set_name,
        )
    )


@pytest.fixture
def library(tmp_thorp):
    """Three recipe books and one hole card, and a resolver mapping list names to them."""
    recipe = ["loc-a", "loc-b", "loc-c"]
    for i, b in enumerate(recipe):
        register_local(
            b, make_text(i, 12000), "recipe", family=["Germanic", "Romance", "Slavic"][i]
        )
    register_local("loc-hole", make_text(99, 3000), "hole-card")
    lists = {"recipe.csv": recipe, "hole.csv": ["loc-hole"]}

    def resolver(path):
        return list(lists[path.split("/")[-1]]), []

    return {"recipe": recipe, "hole": ["loc-hole"], "resolver": resolver, "lists": lists}


BASE_SPEC = {
    "name": "test",
    "data": {"recipe": "recipe.csv", "passes": 1, "order": "shuffled", "refuse": ["hole.csv"]},
    "tokeniser": {"kind": "spm-bpe", "vocab": 512, "byte_fallback": True, "train_on": "recipe"},
    "model": {"family": "gpt", "preset": "tiny", "context": 64},
    "optim": {
        "name": "adamw",
        "lr": 3e-3,
        "betas": [0.9, 0.95],
        "weight_decay": 0.1,
        "warmup_steps": 10,
        "schedule": "cosine",
        "min_lr_ratio": 0.1,
        "batch_tokens": 512,
        "grad_clip": 1.0,
        "precision": "bf16",
    },
    "eval": {"sets": ["hole.csv"], "every_steps": 100000, "evaluators": ["ce_bpb", "samples"]},
    "checkpoint": {"every_steps": 50},
    "seed": 1,
}


@pytest.fixture
def spec():
    return copy.deepcopy(BASE_SPEC)
