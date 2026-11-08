"""Hermetic fixtures: a temporary data directory and ledger, and a small synthetic library."""

from __future__ import annotations

import copy
import hashlib
import os
import random

import pytest

from thorp import manifest, paths

# Postgres in a test is its own database (thorp_test, migrated as the real one is), never Thorp's own: the
# sizes come seeded by the migration, and a test's ships are cleared by tmp_thorp
os.environ["THORP_PG"] = os.environ.get("THORP_PG_TEST", "postgresql://thorp@localhost:5433/thorp_test")

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


@pytest.fixture(autouse=True)
def _records_stay_in_the_test(tmp_path, monkeypatch):
    """S3's records (the voyage gate's log, acquisition's log, intakes and lock) never reach the real data
    folder from a test, even one that asks the gate a question without a temporary data folder."""
    from thorp import acquisition

    monkeypatch.setattr(acquisition, "_dir", lambda: tmp_path / "records" / "acquisition")
    monkeypatch.delenv("THORP_PAPERS", raising=False)


@pytest.fixture(scope="session")
def _store_migrated():
    """The test database brought to the latest models once a session (alembic upgrade head)."""
    from thorp.viable.s3_control import fitout_store

    fitout_store.migrate()


@pytest.fixture(autouse=True)
def _store_clean(_store_migrated):
    """Each test starts with the one store's records empty (the gate's log, S5's switches and exceptions, ...)."""
    from sqlalchemy import text

    from thorp import store
    from thorp.viable import records

    tables = ", ".join(f"{t.schema}.{t.name}" for t in records.Base.metadata.sorted_tables if t.schema in records.SCHEMAS)
    with store.session() as s:
        s.execute(text(f"truncate {tables} restart identity cascade"))


@pytest.fixture(autouse=True)
def _ogden_rule_advisory_in_tests(monkeypatch):
    """S5 'ogden' (19:30, only the Ogden fitout sails) says which voyages may sail, not how the harness behaves,
    and the Ogden fitout exists only as a saved fitout in the real data folder: so in tests it is advisory
    (the gate notes it), except in its own test, which enforces it again."""
    import dataclasses

    from thorp import vsm

    monkeypatch.setitem(
        vsm.POLICIES, "ogden", dataclasses.replace(vsm.POLICIES["ogden"], enforced=False)
    )
    # S5 'prechecks' (19:45) reads the real fitout store in Postgres: advisory in tests for the same reason
    monkeypatch.setitem(
        vsm.POLICIES, "prechecks", dataclasses.replace(vsm.POLICIES["prechecks"], enforced=False)
    )


@pytest.fixture
def tmp_thorp(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("THORP_LEDGER", str(tmp_path / "ledger.sqlite"))
    from sqlalchemy import text

    from thorp import fleet
    from thorp.viable.s3_control.fitout_store import session

    with session() as s, s.begin():  # the test database's ships, emptied (its sizes stay)
        s.execute(text("truncate ship.ships cascade"))
    fleet._REGISTER = None
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
    "fitout": {"key": "keel-cards-cause", "variation": "test"},  # S5 policy 'fitout'
    "data": {
        "recipe": "recipe.csv",
        "passes": 1,
        "order": "shuffled",
        "refuse": ["hole.csv"],
        "clean": "unwrap-v2",  # S5 policy 'clean'
    },
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
