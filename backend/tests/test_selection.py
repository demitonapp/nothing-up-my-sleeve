"""A fitout's books composed from declared weights and filters (thorp/library_facts.py, thorp/selection.py,
s3_control/compose.py): the facts' rules, the weights and filters, determinism, and the record in Postgres."""

from __future__ import annotations

import csv

import pytest

from thorp import library_facts as lf
from thorp import selection as sel


# ---- the facts' rules
def test_credits_read_names_roles_and_years():
    cs = lf.credits("Jowett, Benjamin, 1817-1893 [Translator]; Plato, 427? BC-347? BC; Various")
    assert [c["role"] for c in cs] == ["Translator", None, None]
    assert (cs[1]["born"], cs[1]["died"]) == (-427, -347)
    assert cs[2]["born"] is None


def test_the_year_is_the_translators_then_the_authors_and_its_basis_is_kept():
    # a translator's English is the book's: Jowett, born 1817, so floruit 1857 though Plato lived long before
    y, basis, born, died = lf.year_of("Plato, 427? BC-347? BC; Jowett, Benjamin, 1817-1893 [Translator]")
    assert (y, basis, born, died) == (1857, "floruit", 1817, 1893)
    # a writer dead young: the floruit is capped at the death year
    assert lf.year_of("Keats, John, 1795-1821")[0] == 1821
    # only a death year: death - 25
    assert lf.year_of("Someone, Some, -1900")[:2] == (1875, "late")
    # no years: undated; a recorded publication year wins over the writer's years
    assert lf.year_of("Various") == (None, "undated", None, None)
    assert lf.year_of("Davy, Humphry, Sir, 1778-1829", "published 1812; https://archive.org/x")[:2] == (1812, "published")


def test_the_gate_death_is_over_every_credited_name():
    assert lf.gate_death("Smith, A., 1850-1920; Jones, B., 1880-1972 [Translator]") == 1972


def test_kinds_by_subject_then_bookshelf_with_the_rule_kept():
    assert lf.kind_of("Hamlet", "Tragedies (Drama); Denmark -- Drama", ["Category: Plays/Films/Dramas"], "PR")[0] == "play"
    assert lf.kind_of("Sermons on Several Occasions", "Sermons, English", [], "BX")[0] == "sermon"
    assert lf.kind_of("Punch Vol 1", "English wit and humor -- Periodicals", ["Category: Poetry"], "AP")[0] == "periodical"
    assert lf.kind_of("Little Women", "Sisters -- Fiction; Domestic fiction", ["Category: Novels"], "PS")[0] == "novel"
    assert lf.kind_of("Dialogues of Plato", "Philosophy, Ancient", [], "B")[0] == "dialogue"
    assert lf.kind_of("Parker's Second Reader", "Readers (Elementary)", [], "PE")[0] == "textbook"
    k, why = lf.kind_of("Odd Thing", "", [], "")
    assert (k, why) == ("other", "no rule")


def test_voice_finds_a_clerical_title_after_the_surname_not_a_surname_or_given_name():
    assert lf.voice_of("essay", "Newman, John Henry, Cardinal, 1801-1890", "", [], "gutenberg")[0] == "clergy"
    assert lf.voice_of("novel", "Howells, William Dean, 1837-1920", "", [], "gutenberg")[0] == "lay"
    assert lf.voice_of("novel", "Bishop, Nathaniel H., 1837-1902", "", [], "gutenberg")[0] == "lay"
    assert lf.voice_of("novel", "Hardy, Thomas, 1840-1928", "Clergy -- Fiction", [], "gutenberg")[0] == "lay"
    assert lf.voice_of("sermon", "Hurd, Richard", "", [], "gutenberg")[0] == "clergy"
    assert lf.voice_of("periodical", "Various", "", [], "gutenberg")[0] == "press"
    assert lf.voice_of("derived", "", "", [], "local")[0] == "program"


# ---- composing, on a made-up library
def fact(book, language="en", kind="novel", voice="lay", source="gutenberg", year=1850, ogden=0.8, words=1000, **kw):
    title = kw.pop("title", f"T {book}")
    return {
        "book": book, "title": title, "author": "A", "source": source, "set": "recipe", "language": language,
        "translated": False, "born": None, "died": None, "gate_death": kw.pop("gate_death", 1900), "year": year,
        "year_basis": "floruit" if year else "undated", "kind": kind, "kind_rule": "t", "voice": voice, "voice_rule": "t",
        "ogden": ogden, "ogden_from": "v0.2", "words": words, "fetched": kw.pop("fetched", "2026-11-06"), "held_out": False,
        "control": False, "title_key": lf.title_key(title), "shelves": [], "subjects": "", "locc": "", **kw,
    }  # fmt: skip


LIB = (
    [fact(f"pg{i}", kind="novel", year=1850 + i, ogden=0.9 - i / 100) for i in range(1, 11)]
    + [fact(f"pg{i}", kind="poem", year=1700 + i, ogden=0.7) for i in range(11, 16)]
    + [fact("pg20", language="de", kind="novel", year=1850), fact("pg21", kind="sermon", voice="clergy", year=None, ogden=0.9)]
    + [fact("pg22", gate_death=1960), fact("pg23", ogden=None), fact("pg24", fetched="2026-11-09")]
)


def books(c):
    return [b["book"] for b in c.books]


def test_the_gate_rules_are_always_on_and_languages_are_the_ones_named():
    c = sel.compose({"languages": {"en": 1}}, LIB)
    assert "pg22" not in books(c)  # a credited name dead after 1955
    assert "pg20" not in books(c)  # German, not named
    held = [{**LIB[0], "book": "pgH", "held_out": True}, {**LIB[0], "book": "pgC", "control": True}, {**LIB[0], "book": "pgT", "set": "truth"}]
    assert not {"pgH", "pgC", "pgT"} & set(books(sel.compose({"languages": {"en": 1}}, LIB + held)))


def test_the_ogden_bar_period_and_undated():
    c = sel.compose({"languages": {"en": 1}, "ogden": {"min": 0.855}}, LIB)
    assert set(books(c)) == {"pg1", "pg2", "pg3", "pg4", "pg21"}  # 0.89 down to 0.86, and the sermon at 0.9
    assert all(b["ogden"] >= 0.855 for b in c.books)  # unscored pg23 falls short of a bar
    p = sel.compose({"languages": {"en": 1}, "period": {"start": 1700, "end": 1720}}, LIB)
    assert set(books(p)) == {f"pg{i}" for i in range(11, 16)}  # undated pg21 left out
    p2 = sel.compose({"languages": {"en": 1}, "period": {"start": 1700, "end": 1720, "undated": "include"}}, LIB)
    assert "pg21" in books(p2)


def test_kind_voice_and_as_of_filters():
    assert set(b["kind"] for b in sel.compose({"languages": {"en": 1}, "kinds": {"include": ["poem"]}}, LIB).books) == {"poem"}
    c = sel.compose({"languages": {"en": 1}, "kinds": {"exclude": ["novel", "poem"]}}, LIB)
    assert set(books(c)) == {"pg21"}  # pg23, pg24 are novels too
    assert "pg21" not in books(sel.compose({"languages": {"en": 1}, "voices": {"exclude": ["clergy"]}}, LIB))
    assert "pg24" not in books(sel.compose({"languages": {"en": 1}, "as_of": "2026-11-08"}, LIB))


def test_weights_trim_to_shares_of_the_largest_total_and_the_lowest_ranked_go_first():
    c = sel.compose({"languages": {"en": 1}, "weights": {"kind": {"novel": 0.5, "poem": 0.5}}, "ogden": {"min": 0.6}}, LIB)
    s = c.summary()["by_kind"]
    assert s["poem"]["words"] == 5000 and s["novel"]["words"] == 5000  # poems are 5 books: novels trimmed to match
    novels = [b for b in c.books if b["kind"] == "novel"]
    assert {b["book"] for b in novels} == {f"pg{i}" for i in range(1, 6)}  # the highest Ogden-ness kept (rank by ogden)
    d = sel.compose({"languages": {"en": 1}, "weights": {"kind": {"novel": 0.8, "poem": 0.2}}, "ogden": {"min": 0.6}}, LIB)
    assert d.summary()["by_kind"]["novel"]["share"] == pytest.approx(0.8, abs=0.05)


def test_a_weighted_group_with_no_books_is_an_error_not_a_silent_zero():
    with pytest.raises(sel.SelectionError, match="no book to fill"):
        sel.compose({"languages": {"en": 0.9, "fr": 0.1}}, LIB)


def test_a_word_budget_and_its_shortfall():
    c = sel.compose({"languages": {"en": 1}, "words": 4000, "ogden": {"min": 0.6}}, LIB)
    assert 3000 <= sum(b["words"] for b in c.books) <= 4000
    big = sel.compose({"languages": {"en": 1}, "words": 10**9}, LIB)
    assert any("holds" in n for n in big.notes)


def test_dedupe_one_copy_a_title_keeps_the_best_scored_and_carried_titles_win():
    lib = [fact("pg1", title="Same Book", ogden=0.7), fact("pg2", title="Same Book", ogden=0.9), fact("pg3", title="Other")]
    assert sorted(books(sel.compose({"languages": {"en": 1}, "dedupe": {"by": "title"}}, lib))) == ["pg2", "pg3"]
    assert sorted(books(sel.compose({"languages": {"en": 1}, "dedupe": {"by": "title", "keep": "lowest"}}, lib))) == ["pg1", "pg3"]


def test_carry_strike_append_and_order(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    (tmp_path / "lists").mkdir()
    for name, ids in (("base.csv", ["pg3", "pg1"]), ("tail.csv", ["pgX"])):
        with (tmp_path / "lists" / name).open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["title", "author", "language", "family", "text"])
            w.writerows([[f"t{i}", "a", "en", "Germanic", f"local:{i}"] for i in ids])
    spec = {"languages": {"en": 1}, "carry": ["lists/base.csv"], "ogden": {"min": 0.99}, "order": "carried-first",
            "strike": [{"title": "T pg1", "why": "test"}], "append": [{"list": "lists/tail.csv", "why": "test"}]}  # fmt: skip
    c = sel.compose(spec, LIB)
    assert books(c) == ["pg3"]  # carried books pass the bar, a strike removes pg1 even carried
    assert [r["text"] for r in c.rows()] == ["local:pg3", "local:pgX"]
    assert [x.split()[0] for x in sel.diff(c, "lists/base.csv")["only_list"]] == ["pg1"]


def test_deterministic_the_same_selection_writes_the_same_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    spec = {"languages": {"en": 1}, "weights": {"kind": {"novel": 0.5, "poem": 0.5}}, "rank": "hash", "seed": 3}
    a = sel.write_list(sel.compose(spec, LIB), "lists/a.csv")
    b = sel.write_list(sel.compose(spec, list(reversed(LIB))), "lists/b.csv")
    assert a == b and sel.spec_hash(spec) == sel.spec_hash({**spec})


def test_validate_refuses_what_it_cannot_read():
    for bad in ({}, {"languages": {"en": 1}, "colour": 1}, {"languages": {"en": 1}, "kinds": {"include": ["epic"]}},
                {"languages": {"en": 1}, "period": {"start": 1900, "end": 1800}},
                {"languages": {"en": 1}, "weights": {"language": {"en": 1}}}):  # fmt: skip
        with pytest.raises(sel.SelectionError):
            sel.validate(bad)


# ---- the record in Postgres
def test_facts_selections_and_compositions_are_kept_in_postgres(tmp_path, monkeypatch):
    from thorp import fitouts
    from thorp.viable.s3_control import fitout_store as fs

    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    assert fs.put_facts(LIB, lf.fingerprint(LIB)) == len(LIB)
    assert fs.facts_fingerprint() == lf.fingerprint(LIB)
    f = {"key": "t-fit", "name": "T", "clean": "unwrap-v2", "stages": [
        {"phase": "pretraining", "name": "s", "shelf": "lists/composed/t.csv", "compose": sel.validate({"languages": {"en": 1}})}]}  # fmt: skip
    fs.put_fitout(f)
    got = fs.selections("t-fit")
    assert got[0]["compose"]["languages"] == {"en": 1}
    c = sel.compose({"languages": {"en": 1}}, LIB)
    cid = fs.record_composition({
        "fitout_key": "t-fit", "ordinal": 1, "spec": c.spec, "spec_hash": sel.spec_hash(c.spec), "facts_fingerprint": c.facts_fingerprint,
        "list_path": "lists/composed/t.csv", "list_sha1": "x", "books": len(c.books), "words": 1, "summary": {}, "funnel": [list(x) for x in c.funnel],
        "notes": [], "prechecks": [], "passed": True})  # fmt: skip
    assert fs.compositions("t-fit")[0]["id"] == cid
    # a saved fitout may declare a selection for a shelf not yet written
    assert fitouts.validate({"name": "n", "stages": [{"shelf": "lists/not-yet.csv", "compose": {"languages": {"en": 1}}}]})["stages"][0]["compose"]["rank"] == "id"
    with pytest.raises(ValueError, match="stage 1"):
        fitouts.validate({"name": "n", "stages": [{"shelf": "x", "compose": {"languages": {}}}]})


# ---- the library's branches
def test_branches_are_seeded_once_and_a_hand_change_is_kept():
    from sqlalchemy import text

    from thorp import library_branches as lb
    from thorp.viable.s3_control import fitout_store as fs

    with fs.session() as s, s.begin():  # the records are not truncated between tests: start these from none
        s.execute(text("truncate s3.library_variations, s3.library_branches cascade"))
    nb, nv = fs.seed_branches(lb.DEFAULTS)
    assert nb == len(lb.DEFAULTS) and nv == sum(len(b["variations"]) for b in lb.DEFAULTS)
    assert fs.seed_branches(lb.DEFAULTS) == (0, 0)  # again: nothing new
    got = {b["key"]: b for b in fs.branches()}
    assert [v["key"] for v in got["ogden"]["variations"]][:3] == ["ogden-v0.1", "ogden-v0.2", "ogden-v0.2-declared"]
    assert got["ogden"]["variations"][1]["derived_from"] == "ogden-v0.1"
    assert got["ogden"]["variations"][3]["spec"]["ogden"]["min"] == 0.68


def test_a_variation_holds_a_list_a_selection_or_everything(tmp_path, monkeypatch):
    from thorp import library_branches as lb

    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    assert sorted(lb.variation_ids({"all": True}, LIB)) == sorted(f["book"] for f in LIB)
    got = lb.variation_ids({"spec": {"languages": {"en": 1}, "kinds": {"include": ["poem"]}}}, LIB)
    assert sorted(got) == [f"pg{i}" for i in range(11, 16)]
    assert lb.variation_ids({"list": "lists/none.csv"}, LIB) == []


def test_carry_only_not_in_a_word_budget_filled_up_to_and_the_append_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    (tmp_path / "lists").mkdir()
    with (tmp_path / "lists" / "base.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "author", "language", "family", "text"])
        w.writerow(["t", "a", "en", "Germanic", "local:pg1"])
    only = sel.compose({"languages": {"en": 1}, "carry": ["lists/base.csv"], "carry_only": True}, LIB)
    assert books(only) == ["pg1"]
    fresh = sel.compose({"languages": {"en": 1}, "not_in": ["lists/base.csv"], "kinds": {"include": ["novel"]}}, LIB)
    assert "pg1" not in books(fresh) and "pg2" in books(fresh)
    # a budget fills each share up to its words with the best-ranked books: 3 of the 1,000-word novels, no more
    c = sel.compose({"languages": {"en": 1}, "words": 3500, "ogden": {"min": 0.6}, "kinds": {"include": ["novel"]}}, LIB)
    assert sum(b["words"] for b in c.books) == 3000
    # the 'max_book_words' leaves long books out
    big = [fact("pgB", words=50000), *LIB]
    assert "pgB" not in books(sel.compose({"languages": {"en": 1}, "max_book_words": 2000}, big))
