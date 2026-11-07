"""Ogden-ness and the skeleton keys (thorp/ogden.py)."""

from thorp import fleet, ogden


def test_the_list_and_the_keyed_vocabulary():
    assert len(ogden.words()) == 850
    v = ogden.vocabulary()
    assert len(v) == 853 and v[-3:] == list(ogden.KEYS)


def test_forms_count_as_their_headword():
    assert ogden.lemma("houses") == "house"
    assert ogden.lemma("stopped") == "stop"
    assert ogden.lemma("was") == "be"
    assert ogden.lemma("she") == "he"
    assert ogden.lemma("carburettor") is None


def test_keys():
    assert ogden.keyed("He gave Pip a carburettor in 1890.") == [
        "he", "give", "<name>", "a", "<thing>", "in", "<number>",
    ]  # fmt: skip
    # a capital at a sentence's start cannot be told from an ordinary word, so it is not a name
    assert ogden.keyed("Carburettors are loud.")[0] == "<thing>"
    assert ogden.keyed("Pip went.")[0] == "<thing>"  # the known limit: a name that starts a sentence


def test_score_leaves_names_and_numbers_out():
    s = ogden.score("Then Pip and Estella went to London in 1820.")
    assert s["ogden"] == 1.0  # every ordinary word is Ogden; the names and the year are free
    assert s["names"] > 0 and s["numbers"] > 0


def test_the_expedition():
    assert fleet.expedition_of_label("fu-ogden-v0-1@9m-pre-s1", "Fitout: Ogden v0.1 @ 9m, pretraining") == "ogden"
    assert "ogden" in fleet.EXPEDITIONS
