"""Acquisition as a viable system (thorp/acquisition.py): the people and their dates, the intake gate, an
intake end to end on a stand-in source, the observer on the older fetch paths, and the voyage gate's record."""


from thorp import acquisition as acq
from thorp import manifest, vsm
from thorp.sources import base


def test_people_and_their_death_years_as_catalogues_write_them():
    died = lambda s: [(p.name, p.died, p.role) for p in acq.persons(s)]  # noqa: E731
    assert died("Darwin, Charles, 1809-1882") == [("Darwin, Charles", 1882, "")]
    assert died("Plato, 427? BCE-347? BCE") == [("Plato", -347, "")]
    assert died("Augustus, Emperor of Rome, 63 BCE-14") == [("Augustus, Emperor of Rome", 14, "")]
    assert died("Jowett, Benjamin, 1817-1893 [Translator]") == [
        ("Jowett, Benjamin", 1893, "Translator")
    ]
    assert died("Malory, Thomas, active 15th century") == [("Malory, Thomas", 1500, "")]
    assert died("Chambers, Robert,1802-1871") == [
        ("Chambers, Robert", 1871, "")
    ]  # the Archive's way
    assert died("Lyell, Charles") == [("Lyell, Charles", None, "")]
    assert died("Smith, John, 1850-") == [
        ("Smith, John", None, "")
    ]  # born, no death: not shown dead
    assert died("Anonymous") == [] and died("Various") == [] and acq.unsigned("")
    assert [
        p.died
        for p in acq.persons("Russell, Bertrand, 1872-1970; Whitehead, Alfred North, 1861-1947")
    ] == [
        1970,
        1947,
    ]


def _c(**kw):
    base_kw = dict(
        book_id="pg1",
        title="A Book",
        authors="Darwin, Charles, 1809-1882",
        language="en",
        set="recipe",
        source="gutenberg",
    )
    return acq.Candidate(**{**base_kw, **kw})


def test_the_intake_gate_applies_thorps_policies_to_a_book(tmp_thorp):
    assert acq.admit(_c()).admitted
    # period: every named person dead by 1955, translators too
    v = acq.admit(
        _c(authors="Sophocles, 496? BCE-407 BCE; Murray, Gilbert, 1866-1957 [Translator]")
    )
    assert not v.admitted and "Murray, Gilbert (Translator) died in 1957" in v.refused[0]
    # a person with no dates passes only in a book printed before 1870
    assert not acq.admit(_c(authors="Lyell, Charles")).admitted
    assert acq.admit(_c(authors="Lyell, Charles", published=1837)).admitted
    assert not acq.admit(_c(published=1931)).admitted
    # English for a book that is read; a held-out deck may be another language
    assert not acq.admit(_c(language="pt")).admitted
    assert acq.admit(_c(language="pt", set="hole-card")).admitted
    # decks: a Forgotten Tomes book cannot enter to be read
    assert not acq.admit(_c(title="Blue Jackets")).admitted
    assert acq.admit(_c(title="Blue Jackets", set="hole-card")).admitted
    # proposed rules record, never refuse
    v = acq.admit(_c(authors="Anonymous", source="somewhere-new"))
    assert v.admitted and {n.split(":")[0] for n in v.notes} == {
        "signed",
        "admitted-source",
        "provenance",
    }
    # observing (the older fetch paths): what would be refused is only noted
    v = acq.admit(_c(published=1931), enforce=False)
    assert v.admitted and v.notes


def test_the_intake_gate_can_be_switched_off_by_s5(tmp_thorp):
    from thorp import vsm

    vsm.set_switch("intake", False, "a test")
    v = acq.admit(_c(published=1931))
    assert v.admitted and v.notes == ["printed-before-1930: printed in 1931"]


class StandIn:
    key = "standin"
    prefix = "si-"

    def fetch(self, ident):
        people = {
            "1": "Darwin, Charles, 1809-1882",
            "2": "Russell, Bertrand, 1872-1970",
            "3": "Lyell, Charles",
        }
        return base.Fetched(
            title=f"Book {ident}",
            author=people[ident],
            language="en",
            text=f"A paragraph of book {ident} that wraps\nat the margin as printed books do.\n\nAnother.\n",
            published=1837 if ident == "3" else 1900,
            origin=f"https://example.org/{ident}",
        )


def test_an_intake_end_to_end(tmp_thorp):
    base.register_source(StandIn())
    lst = tmp_thorp / "standin.csv"
    lst.write_text(
        "title,author,language,family,text\n"
        "One,,en,Germanic,standin:1\nTwo,,en,Germanic,standin:2\nThree,,en,Germanic,standin:3\n"
    )
    dry = acq.intake(str(lst), dry_run=True, log=lambda *a: None)
    assert (
        dry["counts"]["would fetch"] == 3 and manifest.get("si-1") is None
    )  # people unknown until fetched
    rec = acq.intake(str(lst), log=lambda *a: None)
    assert (
        rec["status"] == "home" and rec["counts"]["admitted"] == 2 and rec["counts"]["refused"] == 1
    )
    assert rec["refused_by_rule"] == {"dead-by-1955": 1}
    assert (
        manifest.get("si-1") is not None
        and manifest.get("si-3") is not None
        and manifest.get("si-2") is None
    )
    again = acq.intake(str(lst), log=lambda *a: None)
    assert (
        again["counts"]["known"] == 2 and again["counts"]["refused"] == 1
    )  # nothing fetched twice
    log = acq.read_log()
    admitted = [e for e in log if e["verdict"] == "admitted"]
    assert len(admitted) == 2 and admitted[0]["clean"]["version"]
    assert all(e["how"] == "intake" for e in log)  # an intake's registration is not observed twice
    assert [r["id"] for r in acq.intakes()][0] == again["id"] or len(acq.intakes()) >= 2
    assert acq.holder() is None  # the intake lock is given up
    p = acq.payload()
    assert p["S3"]["refused_by_rule"]["dead-by-1955"] == 2 and [s["key"] for s in p["systems"]] == [
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
    ]
    a = acq.audit()
    assert a["books"] == 2 and a["duplicates"]["groups"] == 0 and a["missing_files"]["count"] == 0


def test_a_book_new_to_the_library_by_an_older_path_is_observed(tmp_thorp):
    base.register_source(StandIn())
    base.fetch_ref(
        "standin:2"
    )  # thorp fetch / train.prepare: never refused, but the verdict is kept
    assert manifest.get("si-2") is not None
    (e,) = acq.read_log()
    assert (
        e["verdict"] == "observed" and e["how"] == "fetch_ref" and "dead-by-1955" in e["notes"][0]
    )
    base.fetch_ref("standin:2")
    assert len(acq.read_log()) == 1  # a book already in the library is not observed again


def test_the_voyage_gate_keeps_a_record_of_every_decision(tmp_thorp):
    spec = {
        "name": "t",
        "ship": "Two facts: test",
        "fitout": {"key": "keel-cards-cause", "variation": "t"},
        "data": {"recipe": "lists/none.csv", "clean": "unwrap-v2"},
    }
    vsm.gate(spec, where="fitout builder")
    bare = {k: v for k, v in spec.items() if k != "fitout"}
    try:
        vsm.gate(bare)
    except vsm.GateRefused:
        pass
    log = vsm.gate_log()
    assert [x["verdict"] for x in log][:2] == ["refused", "passed"]
    assert log[0]["decisions"][-1]["policy"] == "fitout" and log[1]["where"] == "fitout builder"
    assert (
        vsm.gate(spec, known_run=True) == [] and len(vsm.gate_log()) == 2
    )  # a resumed voyage is not asked again


def test_only_the_ogden_fitout_sails(tmp_thorp, monkeypatch):
    """S5 'ogden' (Justin, 19:30): a voyage on any other fitout is refused at the gate, and recorded."""
    import dataclasses

    monkeypatch.setitem(  # enforced, as it is outside the tests (conftest makes it advisory elsewhere)
        vsm.POLICIES, "ogden", dataclasses.replace(vsm.POLICIES["ogden"], enforced=True)
    )
    assert vsm.enforced("ogden")
    spec = {
        "name": "t",
        "ship": "Fitout: test",
        "data": {"recipe": "lists/none.csv", "clean": "unwrap-v2"},
    }
    for key in ("ogden", "ogden-v0-1"):
        assert vsm._ogden_only({**spec, "fitout": {"key": key}}) == []
    assert vsm._ogden_only(
        {**spec, "fitout": {"key": "ogdenish"}}
    )  # a version is ogden-<something>
    keel = {**spec, "fitout": {"key": "keel-cards-cause", "variation": "t"}}
    try:
        vsm.gate(keel)
        raise AssertionError("the gate let a keel voyage sail")
    except vsm.GateRefused as e:
        assert "'ogden'" in str(e)
    assert vsm.gate_log()[0]["decisions"][-1] == {
        "policy": "ogden",
        "how": "refused",
        "why": "sails on the fitout 'keel-cards-cause'; only the Ogden fitout sails",
    }
