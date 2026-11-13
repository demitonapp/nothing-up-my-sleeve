"""The site's language and its translator (thorp/translate.py, 13 November): the choice is S5's row, what Tiny Aya Earth makes
is S1's cache, and English is the source and never a target. The model is a stand-in here: no weights are loaded."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from thorp import store, translate


@pytest.fixture(autouse=True)
def _english_after():
    yield
    translate.choose("en", "a test")
    with store.session() as s:
        s.execute(text("delete from s1.translations where model = 'test-double'"))


@pytest.fixture
def double(monkeypatch):
    """A translator that writes "[code] english" and counts what it was asked."""
    calls: list[list[str]] = []

    def run(prompts, budgets):
        calls.append(prompts)
        return ["[xh] " + p.rsplit("\n\n", 1)[-1] for p in prompts]

    monkeypatch.setattr(translate.ENGINE, "run", run)
    monkeypatch.setattr(translate, "model_name", lambda: "test-double")
    return calls


def test_the_languages_include_the_four_asked_for():
    got = {lang["code"]: lang for lang in translate.languages()}
    assert {"en", "af", "fr", "xh"} <= set(got)
    assert got["xh"]["native_name"] == "isiXhosa" and got["xh"]["listed"]
    assert got["en"]["is_source"] and sum(lang["is_source"] for lang in got.values()) == 1
    # Afrikaans is not on Tiny Aya Earth's card, and is offered with that said
    assert got["af"]["listed"] is False
    assert sum(lang["listed"] for lang in got.values()) == 67


def test_choosing_a_language_is_kept_and_english_is_the_way_back():
    got = translate.choose("xh", "Justin")
    assert got["code"] == "xh" and got["chosen_by"] == "Justin" and got["chosen_at"]
    assert translate.current()["code"] == "xh"
    assert translate.choose("EN")["code"] == "en"
    with pytest.raises(ValueError):
        translate.choose("klingon")


def test_a_translation_is_made_once_and_kept(double):
    first = translate.translate("xh", ["The keel reads books.", "Settings"])
    assert first["translations"] == {"The keel reads books.": "[xh] The keel reads books.", "Settings": "[xh] Settings"}
    assert first["missed"] == [] and len(double) == 1 and len(double[0]) == 2
    again = translate.translate("xh", ["Settings", "A new sentence."])
    assert again["translations"]["Settings"] == "[xh] Settings"
    assert double[1][0].endswith("A new sentence.") and len(double[1]) == 1  # only the new one reached the model
    assert translate.forget("xh", "Settings") == 1


def test_english_is_never_translated(double):
    got = translate.translate("en", ["Settings"])
    assert got["translations"] == {} and double == []
    with store.session() as s:
        with pytest.raises(DBAPIError):  # the table refuses it too, not only the code
            s.execute(
                text("insert into s1.translations (code, source_hash, source, target, model) values ('en', :h, 'a', 'a', 'test-double')"),
                {"h": translate.digest("a")},
            )


def test_a_reply_that_is_not_a_translation_is_missed_not_kept(monkeypatch):
    monkeypatch.setattr(translate.ENGINE, "run", lambda p, b: ["Sure! " * 80, "  "])
    monkeypatch.setattr(translate, "model_name", lambda: "test-double")
    got = translate.translate("xh", ["Hi", "Queue"])
    assert got["translations"] == {} and sorted(got["missed"]) == ["Hi", "Queue"]
    assert translate.kept("xh", ["Hi", "Queue"]) == {}


def test_the_prompt_names_the_language_and_keeps_the_names():
    p = translate.prompt(translate.language("xh"), "The Liberty Machine says hello")
    assert "Xhosa (isiXhosa)" in p and "exactly as written: Liberty Machine." in p and p.endswith("\n\nThe Liberty Machine says hello")
    # a string with no name does not carry the list: a small model translated the list instead of the label
    plain = translate.prompt(translate.language("xh"), "Settings")
    assert "Liberty Machine" not in plain and "exactly as written" not in plain


def test_a_name_is_never_translated(monkeypatch, double):
    # a name on its own never reaches the model
    got = translate.translate("xh", ["Nothing up my sleeve", "Settings"])
    assert got["translations"]["Nothing up my sleeve"] == "Nothing up my sleeve"
    assert all("Nothing up my sleeve" != p.rsplit("\n\n", 1)[-1] for p in double[0])
    translate.forget("xh", "Nothing up my sleeve")
    # a sentence whose translation loses a name is asked again, insisting; if it still does, it is not kept
    asked: list[bool] = []

    def run(prompts, budgets):
        asked.append("exactly as written" in prompts[0] and "must appear" in prompts[0])
        return ["Le Liberté Machine fonctionne." if not asked[-1] else "La Liberty Machine fonctionne." for _ in prompts]

    monkeypatch.setattr(translate.ENGINE, "run", run)
    src = "The Liberty Machine works."
    assert translate.translate("xh", [src])["translations"][src] == "La Liberty Machine fonctionne."
    assert asked == [False, True]
    translate.forget("xh", src)
    monkeypatch.setattr(translate.ENGINE, "run", lambda p, b: ["la machine" for _ in p])
    got = translate.translate("xh", [src])
    assert got["translations"] == {} and got["missed"] == [src]


def test_a_common_word_is_not_a_name_and_a_placeholder_must_survive(monkeypatch):
    assert translate.names_in("The Orbitals of Masaq' Reach") == ["Masaq"]  # "orbital" is a word; Masaq is a name
    assert translate.faithful("The orbitals", "Les orbites")
    assert translate.faithful("updated {0}", "mis à jour {0}")
    assert not translate.faithful("updated {0}", "mis à jour")  # the number was lost
    assert not translate.faithful("updated {0}", "mis à jour {0} {1}")  # one was made up
    assert "{0}" in translate.prompt(translate.language("fr"), "updated {0}")
    monkeypatch.setattr(translate.ENGINE, "run", lambda p, b: ["mis à jour" for _ in p])
    src = "updated {0}"
    got = translate.translate("xh", [src])
    assert got["translations"] == {} and got["missed"] == [src]
    monkeypatch.setattr(translate.ENGINE, "run", lambda p, b: ["mis à jour {0}" for _ in p])
    monkeypatch.setattr(translate, "model_name", lambda: "test-double")
    assert translate.translate("xh", [src])["translations"] == {src: "mis à jour {0}"}


def test_a_short_label_is_asked_for_as_a_label():
    lang = translate.language("fr")
    assert "translate it as a label" in translate.prompt(lang, "Thinking")
    assert "translate it as a label" not in translate.prompt(lang, "The keel reads books.")


def test_tidy():
    assert translate.tidy("Hello", ' "Molo" ') == "Molo"
    assert translate.tidy("Hello", "Molo<|END_OF_TURN_TOKEN|>") == "Molo"
    assert translate.tidy("Choose", "**Khetha**") == "Khetha"  # a bold the page did not have
    assert translate.tidy("**Bold**", "**Gewaagd**") == "**Gewaagd**"
    assert translate.tidy("updated {0}", "{0}") is None  # the words went missing
    assert translate.tidy("Hello", "") is None
    assert translate.tidy("Hi", "x" * 500) is None


@pytest.mark.parametrize(
    "s,ok",
    [
        ("Settings", True),
        ("Queue:", True),
        ("updated {0}", True),
        ("{0}", False),
        ("The keel reads books.", True),
        ("Nothing up my sleeve", True),
        ("pg2600", False),
        ("9m@v0.0.6-chat", False),
        ("snake_case", False),
        ("a/b/c.py", False),
        ("1,024", False),
        ("  ", False),
        ("x" * 5000, False),
    ],
)
def test_what_is_worth_translating(s, ok):
    assert translate.worth_translating(s) is ok


def test_the_weights_are_found_or_the_missing_say_what_to_do(monkeypatch, tmp_path):
    monkeypatch.delenv("THORP_TRANSLATOR", raising=False)
    monkeypatch.setattr("thorp.paths.data_dir", lambda: tmp_path)
    monkeypatch.setattr("thorp.onboard.downloads._cached", lambda m: False)
    with pytest.raises(translate.TranslatorMissing, match="gated"):
        translate.weights()
    assert translate.status()["translator"]["ready"] is False
    monkeypatch.setattr("thorp.onboard.downloads._cached", lambda m: m == translate.REPO)
    assert translate.weights() == translate.REPO
    (tmp_path / translate.PREPARED).mkdir(parents=True)
    (tmp_path / translate.PREPARED / "config.json").write_text("{}")
    assert translate.weights().endswith(translate.PREPARED)  # the prepared copy beats the Hub copy
    monkeypatch.setenv("THORP_TRANSLATOR", "/somewhere")
    assert translate.weights() == "/somewhere"


def test_tiny_aya_earth_is_in_the_catalogue_as_a_gated_model():
    from thorp.onboard import catalogue

    m = catalogue.get("CohereLabs/tiny-aya-earth")
    assert m and m["gated"] and m["lab"] == "cohere" and m["band"] == "small" and "NC" in m["license"]
    from thorp import foreign

    assert foreign.lab_of(m["repo"]) in foreign.LABS and foreign.lab_of(m["repo"]) in foreign.FLAGS


def test_the_liberty_machine_has_the_language_policy_and_reads_the_choice():
    from thorp import liberty_machine

    assert "language" in liberty_machine.POLICIES
    assert not liberty_machine.POLICIES["language"].check({})  # no voyage can break it: it is not a spec rule
    translate.choose("fr")
    assert liberty_machine.site_language()["language"]["code"] == "fr"


def test_the_models_memory_follows_the_language_not_a_clock(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(translate.ENGINE, "warm", lambda: calls.append("warm"))
    monkeypatch.setattr(translate.ENGINE, "unload", lambda: calls.append("unload"))
    translate.choose("xh")
    translate.choose("en")
    assert calls == ["warm", "unload"]
    assert not hasattr(translate, "IDLE_UNLOAD_SECONDS")


def test_a_mac_without_the_memory_is_told_so_before_the_load(monkeypatch):
    monkeypatch.setattr(translate, "weights", lambda: "/somewhere")
    monkeypatch.setattr(translate, "weights_gb", lambda w: 3.3)
    monkeypatch.setattr(translate, "free_gb", lambda: 1.0)
    eng = translate._Engine()
    with pytest.raises(translate.TranslatorBusy, match="3.3|5.3|1.0"):
        eng.load()
    assert issubclass(translate.TranslatorBusy, translate.TranslatorMissing)  # the API answers it as a 503 that says why
    assert eng.model is None


def test_free_memory_is_read_or_unknown():
    got = translate.free_gb()
    assert got is None or got > 0
