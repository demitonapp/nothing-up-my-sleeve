"""The four positions' machinery: a lexicon extended by some books is the lexicon of the whole corpus; the primer evaluators."""

from __future__ import annotations

import json

from thorp import paths
from thorp.viable.s2_coordination import tagger

TEXT = {"b1": "the cat sat\n\nthe dog ran", "b2": "a cat ran\n\nthe cat sat", "b3": "a dog sat"}


def _fake(monkeypatch, tmp_path):
    monkeypatch.setenv("THORP_DATA", str(tmp_path))
    monkeypatch.setattr("thorp.sources.load_text", lambda b, clean="raw": TEXT[b])
    tag = lambda w: "NOUN" if w in ("cat", "dog") else ("VERB" if w in ("sat", "ran") else "DET")  # noqa: E731
    monkeypatch.setattr(tagger, "tag_many", lambda paras, batch_size=0: [[(0, 0, w, tag(w)) for w in p.split()] for p in paras])


def test_an_extended_lexicon_is_the_whole_corpus_lexicon(tmp_path, monkeypatch):
    _fake(monkeypatch, tmp_path)
    tagger.build_lexicon(["b1"], "unwrap-v2", "base", log=lambda *_: None)
    tagger.extend_lexicon("base", ["b2", "b3"], 3, "unwrap-v2", "more", log=lambda *_: None)
    tagger.build_lexicon(["b1", "b2", "b3"], "unwrap-v2", "whole", log=lambda *_: None)
    d = tagger._dir()
    for kind in ("lexicon", "bars"):
        assert json.loads((d / f"more-{kind}.json").read_text()) == json.loads((d / f"whole-{kind}.json").read_text())
    assert tagger.meta("more")["books"] == tagger.meta("whole")["books"] == 3
    assert tagger.meta("more")["tagged"] == tagger.meta("whole")["tagged"]


def test_the_primer_evaluators_are_registered_and_read_their_items():
    from thorp import evaluators

    for name in ("plato", "francis"):
        assert callable(evaluators.get(name))
    assert paths.resolve("lists/tricks/plato-primer.csv").exists() and paths.resolve("lists/tricks/francis-primer.csv").exists()
