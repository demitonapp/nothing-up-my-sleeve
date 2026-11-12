"""The queue has one source, the store (11 November, the audit's item 6): the fitout builder and the Navigator's
Wager queue into `s2.queue_lines`, and the lint, the audit, the expedition states and the library read it there.
`specs/queue.txt` is an export nobody reads back."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from thorp.viable.s2_coordination import queue_read, queue_store


@pytest.fixture(autouse=True)
def _reader_closed():
    """The ledger's per-thread Postgres reader holds a transaction open; closed after each test so the next
    test's truncate is not left waiting on it."""
    yield
    from thorp.ledger import close_reader

    close_reader()


@pytest.fixture
def ships(tmp_path, monkeypatch):
    """A temporary ships folder (specs/ and specs/fitouts/), so no spec reaches the real one."""
    root = tmp_path / "ships"
    (root / "specs" / "fitouts").mkdir(parents=True)
    monkeypatch.setenv("THORP_SHIPS", str(root))
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("THORP_QUEUE_PG", raising=False)
    monkeypatch.delenv("THORP_SHIP_LOG", raising=False)
    return root


def test_pending_and_history_are_the_stores(ships):
    queue_store.add("fitouts/a", require_goal=False)
    queue_store.add("hold: Justin signs")
    assert queue_read.pending() == ["fitouts/a", "hold: Justin signs"]
    queue_store.record("fitouts/z", "2026-11-11T10:00:00", "0")
    assert queue_read.history() == [{"text": "fitouts/z", "started": "2026-11-11T10:00:00", "status": "0", "goal_id": None}]
    (ships / "specs" / "queue.txt").write_text("fitouts/only-in-the-file\n")  # an export is never read back
    assert "fitouts/only-in-the-file" not in queue_read.pending()


def test_a_hired_box_has_no_home_queue(ships, monkeypatch):
    queue_store.add("fitouts/a", require_goal=False)
    monkeypatch.setenv("THORP_PAPERS", str(ships / "papers.json"))
    assert queue_read.pending() == [] and queue_read.history() == []
    monkeypatch.delenv("THORP_PAPERS")
    monkeypatch.setenv("THORP_SHIP_LOG", "1")
    assert queue_read.pending() == []


def test_add_keeps_the_order_at_the_top_and_skips_what_is_queued(ships):
    queue_store.add("fitouts/old", require_goal=False)
    assert queue_read.add(["fitouts/x", "fitouts/old", "fitouts/y"], top=True) == ["fitouts/x", "fitouts/y"]
    assert queue_read.pending() == ["fitouts/x", "fitouts/y", "fitouts/old"]
    assert queue_read.add(["# a comment", "fitouts/z"]) == ["fitouts/z"]
    assert queue_read.pending()[-1] == "fitouts/z"


def test_the_fitout_builder_queues_into_the_store(ships, monkeypatch):
    from thorp import fitouts, liberty_machine

    built = [{"name": f"fu-k@300k-s{sd}", "seed": sd} for sd in (1, 2)]
    monkeypatch.setattr(fitouts, "compile_for", lambda key, preset, seed: [b for b in built if b["seed"] == seed])
    monkeypatch.setattr(liberty_machine, "gate", lambda spec, where=None: None)
    queue_store.add("fitouts/already-there", require_goal=False)
    assert fitouts.queue("k", "300k", seeds=(1, 2), where="top") == ["fitouts/fu-k@300k-s1", "fitouts/fu-k@300k-s2"]
    assert queue_store.pending_texts() == ["fitouts/fu-k@300k-s1", "fitouts/fu-k@300k-s2", "fitouts/already-there"]
    assert not (ships / "specs" / "queue.txt").exists()
    fitouts.queue("k", "300k", seeds=(1,), where="end")  # queued again: it keeps its place, no second copy
    assert queue_store.pending_texts().count("fitouts/fu-k@300k-s1") == 1


def test_the_wager_gates_then_queues_into_the_store(ships, monkeypatch):
    from thorp import liberty_machine
    from thorp.viable.s4_intelligence import wager

    spec = {"name": "fu-ogden-pull", "seed": 1}

    def ogden():
        return {"r1": spec}

    ogden.cache_clear = lambda: None
    monkeypatch.setattr(wager, "_ogden_specs", ogden)
    monkeypatch.setattr(wager, "_voyage", lambda name: None)
    gated = []
    monkeypatch.setattr(liberty_machine, "gate", lambda s, where=None: gated.append(s["name"]))
    queue_store.add("fitouts/first", require_goal=False)
    assert wager.queue("r1") == {"queued": "fu-ogden-pull", "position": 2}
    assert gated == ["fu-ogden-pull"]
    assert queue_store.pending_texts() == ["fitouts/first", "fitouts/fu-ogden-pull"]
    assert wager._in_queue("fu-ogden-pull") and not (ships / "specs" / "queue.txt").exists()
    with pytest.raises(ValueError, match="already in the queue"):
        wager.queue("r1")

    def refuse(s, where=None):
        raise RuntimeError("refused")

    queue_store.drop("fitouts/fu-ogden-pull")
    monkeypatch.setattr(liberty_machine, "gate", refuse)
    with pytest.raises(RuntimeError):
        wager.queue("r1")
    assert queue_store.pending_texts() == ["fitouts/first"]  # a refused voyage is not queued


def test_the_lint_and_the_states_read_the_store(ships):
    from thorp import expeditions, liberty_machine

    (ships / "specs" / "fitouts" / "fu-here.yaml").write_text("name: fu-here\nseed: 1\n")
    queue_store.add("fitouts/nope", require_goal=False)
    queue_store.add("hold: before the 21m")
    queue_store.add("fitouts/fu-here", require_goal=False)
    found = liberty_machine.lint_queue()
    assert "fitouts/nope: no spec file" in found
    assert not any("hold:" in f for f in found)  # a hold names a decision, not a spec
    assert "fu-here" in expeditions._queued()
    assert expeditions.overview()["queue"]


def test_nothing_reads_or_writes_the_queue_file():
    """Only the store module (its backfill and export) and the coordinator's own file mode name the file."""
    backend = Path(__file__).resolve().parent.parent
    allowed = {"queue_store.py", "lanes.py"}
    pat = re.compile(r"""(resolve\(\s*["']specs/queue(-done)?\.txt|/\s*["']queue(-done)?\.txt["'])""")
    hits = [
        f"{p.relative_to(backend)}:{i}"
        for root in (backend / "thorp", backend / "scripts")
        for p in root.rglob("*.py")
        if p.name not in allowed
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if pat.search(ln)
    ]
    assert hits == []
