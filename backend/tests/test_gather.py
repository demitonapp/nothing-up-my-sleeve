"""The gather operation (thorp/gather.py) and the bulk adapters (thorp/sources/bulk.py): a corpus read
one record at a time, through the same S3 intake gate as a list."""

from __future__ import annotations

import sqlite3

import pytest

from thorp import acquisition, gather, manifest, paths
from thorp.sources import bulk, catalog


class FakeBulk:
    key = "fakebulk"
    prefix = "fb-"
    name = "A fake corpus"
    unsigned = False

    def books(self, *, limit=None, offset=0, **_):
        rows = [
            ("1", "Darwin, Charles, 1809-1882", 1859, "One paragraph of a book.\n\nAnother.\n"),
            ("2", "Russell, Bertrand, 1872-1970", 1912, "A modern book that must be refused.\n"),
            ("3", "Lyell, Charles", 1837, "An undated person in an old book.\n"),
        ]
        for ident, author, year, text in rows[offset:]:
            yield bulk.BulkBook(
                ident=ident,
                title=f"Book {ident}",
                authors=author,
                language="en",
                published=year,
                origin=f"https://example.org/{ident}",
                text=text,
            )
            if limit is not None and int(ident) >= limit:
                return


def _entry(key="fakebulk"):
    return {
        "key": key,
        "name": "A fake corpus",
        "holds": "three records",
        "after_rule": "a test",
        "licence": "public domain",
        "access": "a test",
        "status": "admitted",
        "kind": "bulk",
        "adapter": key,
        "unsigned": False,
        "url": "https://example.org",
        "how": "a test",
    }


@pytest.fixture
def fake(monkeypatch):
    src = FakeBulk()
    monkeypatch.setitem(bulk.BULK_SOURCES, src.key, src)
    monkeypatch.setattr(catalog, "SOURCES", catalog.SOURCES + [_entry()])
    monkeypatch.setattr(acquisition, "_EDITION", {})
    return src


def test_a_gather_admits_through_the_gate_and_writes_where_books_live(tmp_thorp, fake):
    rec = gather.run("fakebulk", log=lambda *a: None)
    assert rec["status"] == "home" and rec["counts"]["read"] == 3
    assert rec["counts"]["admitted"] == 2 and rec["counts"]["refused"] == 1
    assert rec["refused_by_rule"] == {"dead-by-1955": 1}
    assert manifest.get("fb-1") is not None and manifest.get("fb-2") is None
    assert (paths.texts_dir("fakebulk") / "fb-1.txt").read_text() == (
        "One paragraph of a book.\n\nAnother.\n"
    )
    # the older person with no dates passes in a book printed before 1870
    assert manifest.get("fb-3") is not None
    # a second gather leaves the admitted books where they are (and refuses the same one again)
    again = gather.run("fakebulk", log=lambda *a: None)
    assert again["counts"]["known"] == 2 and again["counts"]["admitted"] == 0
    assert again["counts"]["refused"] == 1


def test_a_dry_run_reads_the_records_and_writes_nothing(tmp_thorp, fake):
    rec = gather.run("fakebulk", dry_run=True, log=lambda *a: None)
    assert rec["counts"]["would fetch"] == 2 and rec["counts"]["refused"] == 1
    assert manifest.get("fb-1") is None and not paths.texts_dir("fakebulk").exists()


def test_a_source_not_admitted_and_unsigned_work_need_a_word(tmp_thorp, monkeypatch):
    src = FakeBulk()
    src.unsigned = True
    monkeypatch.setitem(bulk.BULK_SOURCES, src.key, src)
    monkeypatch.setattr(catalog, "SOURCES", catalog.SOURCES + [_entry()])
    with pytest.raises(PermissionError, match="signed"):
        gather.run("fakebulk", log=lambda *a: None)
    monkeypatch.setitem(catalog.SOURCES[-1], "status", "walled")
    with pytest.raises(PermissionError, match="walled"):
        gather.run("fakebulk", allow_unsigned=True, log=lambda *a: None)


def test_the_deck_is_protected_by_text_not_only_by_id(monkeypatch):
    text = "the quick brown fox jumps over the lazy dog and then the dog sleeps"
    sh = acquisition._shingles(text)
    monkeypatch.setattr(
        acquisition, "_deck_index", lambda: ({x: {"loc-hole"} for x in sh}, {"loc-hole": len(sh)})
    )
    c = acquisition.Candidate(
        "fb-9", "A different title", "Anon, 1800-1890", "en", "recipe", "fakebulk", text=text
    )
    assert acquisition._not_a_deck_text(c)
    c.text = "entirely different words in a different order and with nothing in common at all"
    assert not acquisition._not_a_deck_text(c)


def test_the_adapters_map_a_record_to_thorps_fields():
    b = bulk.Pre1929().book(
        {
            "id": "askaroskassiscop00deleiala",
            "text": "The East was the cradle.\n",
            "metadata": {
                "title": "Askaros Kassis",
                "author": "De Leon, Edwin, 1828-1891.",
                "year": 1870.0,
                "language": "eng",
                "ia_url": "https://archive.org/details/askaroskassiscop00deleiala",
            },
        }
    )
    assert b.ident == "askaroskassiscop00deleiala"
    assert b.language == "en" and b.published == 1870
    assert b.authors == "De Leon, Edwin, 1828-1891."
    loc = bulk.LibraryOfCongress().book(
        {
            "id": "02010466",
            "text": "Pittsburg Landing.\n",
            "metadata": {
                "title": "Pittsburg Landing",
                "author": "Victor, Orville J.",
                "year": 1862,
                "language": "english",
                "item_url": "https://www.loc.gov/item/02010466",
            },
        }
    )
    assert loc.published == 1862 and loc.language == "en"
    assert bulk.year_of("[18--]") is None and bulk.year_of(0) is None
    assert bulk.iso_language("English") == "en" and bulk.iso_language(["fre", "eng"]) == "fr"


def test_a_british_library_volume_joins_its_pages_in_order():
    src = bulk.BritishLibrary()
    current = {
        "record_id": "003112351",
        "pages": [(10, "second page"), (7, "first page"), (9, "")],
        "rows": [
            {
                "record_id": "003112351",
                "date": __import__("datetime").datetime(1692, 1, 1),
                "title": "The Traytor",
                "all_names": "Shirley, James, 1596-1666 [person]",
                "name": None,
                "Language_1": "English",
                "raw_date": "1692",
            }
        ],
    }
    b = src._volume(current)
    assert b is not None and b.text == "first page\n\nsecond page"
    assert b.published == 1692 and b.language == "en" and b.ident == "003112351"


def test_an_american_story_page_becomes_an_issue(tmp_path):
    src = bulk.AmericanStories()
    con = sqlite3.connect(tmp_path / "as.sqlite3")
    con.execute(
        "create table pages (issue text, page int, title text, date text, lccn text, text text)"
    )
    page = {
        "lccn": {"lccn": "sn83021193", "title": "The Massachusetts spy"},
        "page_number": 1,
        "edition": {"date": "1770-09-13"},
        "full articles": [{"headline": "BOSTON", "article": "The troops are at the Neck."}],
    }
    src._stage(con, page, "1770-09-13_p1_sn83021193_00517172169_1770091301_0007.json")
    con.commit()
    issue = con.execute("select issue, title, date, lccn, text from pages").fetchone()
    b = src._issue(
        {
            "issue": issue[0],
            "title": issue[1],
            "date": issue[2],
            "lccn": issue[3],
            "texts": [issue[4]],
        }
    )
    assert b is not None and b.ident.startswith("sn83021193")
    assert b.published == 1770 and b.language == "en" and "BOSTON" in b.text
    con.close()


def test_a_folder_of_licensed_texts_needs_only_a_metadata_row(tmp_path):
    root = tmp_path / "eebo"
    root.mkdir()
    (root / "a1.txt").write_text("A licensed EEBO text.\n", encoding="utf-8")
    meta = tmp_path / "eebo.csv"
    meta.write_text(
        "file,title,author,language,year,origin\n"
        'a1.txt,A Book,"Shirley, James, 1596-1666",en,1630,OTA\n',
        encoding="utf-8",
    )
    books = list(bulk.Folder().books(path=str(root), metadata=str(meta)))
    assert len(books) == 1 and books[0].published == 1630
    assert books[0].authors.startswith("Shirley")


def test_the_catalogue_names_a_wall_for_every_source_it_cannot_fetch():
    for s in catalog.SOURCES:
        assert {"key", "name", "holds", "status", "licence", "access", "url"} <= set(s)
        if s["status"] in ("walled", "gated", "awaits S5 (unsigned work)"):
            assert s.get("wall"), s["key"]
        if s["status"] == "admitted" and s["key"] != "gutenberg":
            assert s.get("adapter"), s["key"]


def test_the_authority_lookup_fills_a_death_year_and_the_gate_uses_it(tmp_thorp, monkeypatch):
    from thorp.sources import authority

    monkeypatch.setattr(authority, "_cache", {})
    monkeypatch.setattr(
        authority,
        "_search",
        lambda q: {
            "label": "Charles Ezra Greene",
            "description": "engineer (1842–1903)",
            "born": 1842,
            "died": 1903,
        },
    )
    assert authority.lookup("Greene, Charles E.") == (1842, 1903)
    assert authority.lookup("Greene, Charles E.") == (1842, 1903)  # cached, no second request

    src = FakeBulk()
    src.key, src.prefix = "auth", "au-"

    def books(*, limit=None, offset=0, **_):
        yield bulk.BulkBook(
            ident="1",
            title="A Book",
            authors="Greene, Charles E.",
            language="en",
            published=1890,
            origin="https://example.org/1",
            text="A page of a book that has no dates in its catalogue record.\n",
        )

    src.books = books
    monkeypatch.setitem(bulk.BULK_SOURCES, src.key, src)
    monkeypatch.setattr(
        catalog, "SOURCES", catalog.SOURCES + [{**_entry(), "key": "auth", "adapter": "auth"}]
    )
    rec = gather.run("auth", authority=True, log=lambda *a: None)
    assert rec["counts"]["admitted"] == 1
    assert "1842-1903" in manifest.get("au-1").author  # the gate's evidence is in the record


def test_the_authority_parser_reads_only_a_closed_life():
    from thorp.sources import authority

    assert authority._LIFE.search("American poet (1869-1926)").groups() == ("1869", "1926")
    assert not authority._LIFE.search("American author (1874-?)")
    assert authority.query("Sterling, George") == "George Sterling"
    assert authority.surname("Sterling, George") == "sterling"


def test_the_gate_reads_the_catalogues_admitted_sources(tmp_thorp):
    c = acquisition.Candidate(
        "cp29-1", "A Book", "Darwin, Charles, 1809-1882", "en", "recipe",
        "common-pile-pre-1929", origin="https://example.org/1",
    )
    assert acquisition.admit(c).admitted
    c.source = "hathitrust"
    v = acquisition.admit(c)
    assert v.admitted and any(n.startswith("admitted-source:") for n in v.notes)


def test_a_resolved_date_is_written_into_the_authors_field():
    authors = acquisition.with_dates(
        "Greene, Charles E.; Anonymous", {"Greene, Charles E": (1842, 1903)}
    )
    assert authors == "Greene, Charles E., 1842-1903; Anonymous"
    assert [(p.name, p.died) for p in acquisition.persons(authors)] == [
        ("Greene, Charles E.", 1903)
    ]


def test_an_incunabulum_is_a_discovery_set_not_an_english_recipe(tmp_thorp):
    latin = acquisition.Candidate(
        "inc-1", "Biblia Latina", "Eggestein, Heinrich, approximately 1415-", "la", "incunabula",
        "incunabula", published=1469, origin="https://archive.org/details/1",
    )
    assert acquisition.admit(latin).admitted  # the incunabula set may be Latin
    latin.set = "recipe"
    assert not acquisition.admit(latin).admitted  # a training recipe may not
    assert acquisition.admit(latin).refused[0].startswith("english:")


def test_the_incunabula_filter_rejects_the_archives_bad_dates_and_manuscripts():
    from thorp.sources import incunabula as inc

    good = {
        "date": "1483-01-01T00:00:00Z",
        "year": 1483,
        "title": "Thus endeth the legende named in Latyn legenda aurea",
        "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/",
        "collection": ["bplscinc", "bostonpubliclibrary"],
    }
    assert inc.plausible(good)
    assert not inc.plausible({**good, "date": "800 - 1500"})  # a range, not a printing year
    assert not inc.plausible({**good, "date": "2011-01-01T00:00:00Z"})
    assert not inc.plausible({**good, "licenseurl": ""})
    assert not inc.plausible({**good, "collection": ["early-european-books"]})
    assert not inc.plausible({**good, "title": "Beinecke MS 887, manuscript fragments"})
    assert inc.strict_year("1498-01-01T00:00:00Z") == 1498
    assert inc.strict_year("800 - 1500") is None


def test_an_exported_list_names_the_bulk_books(tmp_thorp, fake):
    gather.run("fakebulk", log=lambda *a: None)
    out = tmp_thorp / "fake.csv"
    n = gather.export_list("fakebulk", str(out))
    assert n == 2
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0].startswith("title,author,language,family,text")
    assert any(r.endswith(",fakebulk:1") for r in rows)


def test_a_classics_set_is_a_discovery_set_not_an_english_recipe(tmp_thorp):
    c = acquisition.Candidate(
        "lat-1", "Amphitruo", "Plautus, Titus Maccius, 254 BCE-184 BCE", "la", "classics",
        "perseus-latin", published=1895, origin="https://example.org/1",
    )
    assert acquisition.admit(c).admitted  # Latin, a modern imprint, an ancient author
    c.set = "recipe"
    v = acquisition.admit(c)
    assert not v.admitted and any(x.startswith("english:") for x in v.refused)


def test_a_discovery_set_does_not_apply_the_death_rule():
    c = acquisition.Candidate(
        "grc-1", "Histories", "Editor, Modern, 1960-2020", "grc", "classics",
        "perseus-greek", published=1910, origin="https://example.org/2",
    )
    assert acquisition.admit(c).admitted
    c.set = "recipe"
    assert any(x.startswith("dead-by-1955:") for x in acquisition.admit(c).refused)


def test_the_perseus_tei_reader_keeps_the_title_author_and_imprint():
    from thorp.sources import classics

    xml = """<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt>
      <title>Ibis</title><author>P. Ovidius Naso</author><editor>Rudolf Ehwald</editor>
      </titleStmt><sourceDesc><biblStruct><monogr><imprint><date>1889</date></imprint></monogr>
      </biblStruct></sourceDesc></fileDesc></teiHeader><text><body><div><l>Tempus ad hoc</l>
      <l>Omne fuit Musae carmen inerme meae</l></div></body></text></TEI>"""
    root = __import__("xml.etree.ElementTree", fromlist=["ET"]).fromstring(xml)
    title, author, editor, year = classics._meta(root)
    assert (title, author, editor, year) == ("Ibis", "P. Ovidius Naso", "Rudolf Ehwald", 1889)
    body = root.find(f".//{classics.TEI}body")
    assert "Tempus ad hoc" in classics._body_text(body)


def test_the_etcsl_reader_keeps_transliteration_rows_and_translation_paragraphs():
    from thorp.sources import cuneiform

    html = """<table><tr><td>1.</td><td>iriki kug-kug-ga-am3</td></tr>
      <tr><td>2.</td><td>ki-en-gi kug-ga</td></tr></table>
      <p>1-4. Pure are the cities.</p><p>5-10. He laid her down.</p>"""
    cells = cuneiform._Cells("td")
    cells.feed(html)
    assert "iriki kug-kug-ga-am3" in cuneiform._strip_navigation(cells.rows)
    paras = cuneiform._Cells("p")
    paras.feed(html)
    assert any("Pure are the cities" in x for x in cuneiform._strip_navigation(paras.rows))
