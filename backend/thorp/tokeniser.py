"""Content-addressed SentencePiece BPE tokenisers.

A tokeniser's id is the SHA-1 of the sorted book ids it was trained on (plus the settings, when
they differ from the defaults, so a different vocabulary is a different directory). Training is
lossless: identity normalisation, no dummy prefix, newline as a user-defined piece, byte fallback
for anything else, so decode(encode(text)) == text and bits per byte is honest.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sentencepiece as spm

from thorp import manifest, paths
from thorp.sources import load_text

DEFAULTS = {
    "kind": "spm-bpe",
    "vocab": 16384,
    "byte_fallback": True,
    "character_coverage": 0.9995,
    "clean": "raw",  # the cleaning version its books are read with (thorp/cleaning.py); raw moves no id
    # the control tokens the tokeniser declares as single pieces (9 November: the top ten, per SOP v0.0.6). A symbol
    # changes the tokeniser's id, so a voyage that declares them gets its own tokeniser, never a shared one.
    "symbols": (),
}
NEWLINE = "\n"


# the tokeniser's own specials (unknown, and the begin and end sentencepiece reserves): a voyage that lists them
# among its control tokens gets no second piece for them
OWN_SPECIALS = ("<unk>", "<s>", "</s>")


def user_symbols(symbols) -> list[str]:
    """The control tokens to declare as single pieces: the voyage's list in its order, once each, without the
    tokeniser's own specials (sentencepiece refuses a user-defined piece it already defines)."""
    out: list[str] = []
    for s in symbols or ():
        if s and s not in OWN_SPECIALS and s != NEWLINE and s not in out:
            out.append(str(s))
    return out


def tokeniser_id(book_ids: list[str], settings: dict | None = None) -> str:
    key = "\n".join(sorted(book_ids))
    extra = {k: v for k, v in (settings or {}).items() if DEFAULTS.get(k) != v}
    if extra:
        key += "\n" + json.dumps(extra, sort_keys=True)
    return hashlib.sha1(key.encode()).hexdigest()


@dataclass
class Tokeniser:
    id: str
    dir: Path
    sp: spm.SentencePieceProcessor

    @property
    def vocab_size(self) -> int:
        return self.sp.get_piece_size()

    @property
    def clean(self) -> str:
        """The cleaning version this tokeniser's books (and every shard it encodes) are read with."""
        p = self.dir / "settings.json"
        return (json.loads(p.read_text()).get("clean") if p.exists() else None) or "raw"

    def text(self, book_id: str) -> str:
        return load_text(book_id, self.clean)

    def text_bytes(self, book_id: str) -> int:
        """The bytes of the book as this tokeniser reads it: bits per byte divides by these. Raw text
        is the manifest's count; a cleaned text is counted once and kept beside the shards."""
        if self.clean == "raw":
            book = manifest.get(book_id)
            if book is not None:
                return book.bytes
        p = paths.shards_dir() / self.id / f"{book_id}.bytes"
        if p.exists():
            return int(p.read_text())
        n = len(self.text(book_id).encode("utf-8"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(n))
        return n

    @property
    def eos_id(self) -> int:
        return self.sp.eos_id()

    @property
    def newline_id(self) -> int:
        return self.sp.piece_to_id(NEWLINE)

    def encode(self, text: str) -> list[int]:
        """Encode line by line (newline is its own piece, so this equals encoding the whole)."""
        lines = text.split("\n")
        enc = self.sp.encode(lines, out_type=int, num_threads=os.cpu_count() or 4)
        nl = self.newline_id
        out: list[int] = []
        for i, ids in enumerate(enc):
            if i:
                out.append(nl)
            out.extend(ids)
        return out

    def decode(self, ids: list[int]) -> str:
        return self.sp.decode(ids)

    def byte_piece_mask(self) -> np.ndarray:
        return np.array([self.sp.is_byte(i) for i in range(self.vocab_size)], dtype=bool)

    def stats(self) -> dict:
        p = self.dir / "stats.json"
        return json.loads(p.read_text()) if p.exists() else {}


def _load(tid: str) -> Tokeniser:
    d = paths.tokenisers_dir() / tid
    sp = spm.SentencePieceProcessor(model_file=str(d / "spm.model"))
    return Tokeniser(tid, d, sp)


def load(tid: str) -> Tokeniser:
    return _load(tid)


def book_stats(tok: Tokeniser, book_ids: list[str]) -> dict:
    """Bytes per token and byte-fallback rate per book."""
    is_byte = tok.byte_piece_mask()
    out = {}
    for b in book_ids:
        book = manifest.get(b)
        text = tok.text(b)
        ids = np.array(tok.encode(text), dtype=np.int64)
        nbytes = len(text.encode("utf-8"))
        out[b] = {
            "tokens": int(len(ids)),
            "bytes": int(nbytes),
            "bytes_per_token": nbytes / max(1, len(ids)),
            "byte_fallback_rate": float(is_byte[ids].mean()) if len(ids) else 0.0,
            "family": book.family if book else "",
            "language": book.language if book else "",
        }
    return out


CORPUS_LINE = 8000  # SentencePiece's trainer skips a sentence over max_sentence_length (16,384)


def _corpus_lines(text: str) -> str:
    """The text for the trainer's corpus file, a line over CORPUS_LINE characters cut at spaces: a
    cleaned (unwrapped) paragraph is one line, and the trainer would silently skip the long ones. Only
    the merges are learned from this; encoding still reads the text as it is."""
    out = []
    for line in text.split("\n"):
        while len(line) > CORPUS_LINE:
            cut = line.rfind(" ", 0, CORPUS_LINE)
            cut = cut if cut > 0 else CORPUS_LINE
            out.append(line[:cut])
            line = line[cut:]
        out.append(line)
    return "\n".join(out)


def train_or_load(book_ids: list[str], settings: dict | None = None) -> Tokeniser:
    settings = {**DEFAULTS, **(settings or {})}
    tid = tokeniser_id(book_ids, settings)
    d = paths.tokenisers_dir() / tid
    if (d / "spm.model").exists() and (d / "stats.json").exists():
        return _load(tid)
    tmp = d.with_name(tid + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    corpus = tmp / "corpus.txt"
    with open(corpus, "w", encoding="utf-8") as f:
        for b in sorted(book_ids):
            f.write(_corpus_lines(load_text(b, settings["clean"])))
            f.write("\n")
    spm.SentencePieceTrainer.train(
        input=str(corpus),
        model_prefix=str(tmp / "spm"),
        model_type="bpe",
        vocab_size=settings["vocab"],
        byte_fallback=settings["byte_fallback"],
        character_coverage=settings["character_coverage"],
        normalization_rule_name="identity",
        add_dummy_prefix=False,
        remove_extra_whitespaces=False,
        allow_whitespace_only_pieces=True,
        split_digits=True,
        user_defined_symbols=[NEWLINE, *user_symbols(settings.get("symbols"))],
        unk_id=0,
        bos_id=1,
        eos_id=2,
        pad_id=-1,
        max_sentence_length=16384,
        input_sentence_size=4_000_000,
        shuffle_input_sentence=True,
        num_threads=os.cpu_count() or 4,
        minloglevel=2,
    )
    corpus.unlink()
    (tmp / "books.json").write_text(json.dumps(sorted(book_ids), indent=1))
    (tmp / "settings.json").write_text(json.dumps(settings, indent=1))
    sp = spm.SentencePieceProcessor(model_file=str(tmp / "spm.model"))
    stats = book_stats(Tokeniser(tid, tmp, sp), book_ids)
    (tmp / "stats.json").write_text(json.dumps(stats, indent=1))
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    register(tid, d, settings, stats, book_ids)
    return _load(tid)


def pieces(tid: str) -> list[str]:
    """A tokeniser's piece table, id by id: what each number a model was trained on stands for."""
    sp = _load(tid).sp
    return [sp.id_to_piece(i) for i in range(sp.get_piece_size())]


def same_pieces(a: str, b: str) -> bool:
    """Whether two tokenisers give every id the same piece, so weights trained with one read the other."""
    return a == b or pieces(a) == pieces(b)


def graft(seed_tid: str, book_ids: list[str], settings: dict | None = None) -> Tokeniser:
    """The seed's piece table, read with this voyage's own cleaning (11 November, the return leg).

    A tokeniser's id carries its cleaning, so a leg that cleans its text another way than its seed did
    (`marks-v1` after a `raw` pretraining) would train a second tokeniser of its own. The merges are learned
    from the cleaned text, so the two tables need not agree: on Ogden v0.1.4 four of the 2,048 ids changed
    hands (`▁On` with `▁fine`, `▁bes` with a run of spaces), and the seed's weights would have read each as
    the other, with nothing refusing it. A grafted tokeniser is the seed's model file under this voyage's
    settings: the same pieces by construction, and every shard read through the leg's cleaning."""
    settings = {**DEFAULTS, **(settings or {}), "pieces_of": seed_tid}
    tid = tokeniser_id(book_ids, settings)
    d = paths.tokenisers_dir() / tid
    if (d / "spm.model").exists() and (d / "stats.json").exists():
        return _load(tid)
    src = paths.tokenisers_dir() / seed_tid
    if not (src / "spm.model").exists():
        raise LookupError(f"the seed's tokeniser {seed_tid[:12]} is not on this machine")
    tmp = d.with_name(f"{tid}.{os.getpid()}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    for name in ("spm.model", "spm.vocab"):
        if (src / name).exists():
            shutil.copyfile(src / name, tmp / name)
    (tmp / "books.json").write_text(json.dumps(sorted(book_ids), indent=1))
    (tmp / "settings.json").write_text(json.dumps(settings, indent=1))
    stats: dict = {}  # per-book statistics are the seed's to report; a graft learns nothing from its books
    (tmp / "stats.json").write_text(json.dumps(stats))
    shutil.rmtree(d, ignore_errors=True)
    tmp.rename(d)
    register(tid, d, settings, stats, book_ids)
    return _load(tid)


def register(tid: str, d, settings: dict, stats: dict, book_ids) -> None:
    """The tokeniser in S1's register (s1.tokenisers, s1.tokeniser_books): which books, which settings. Its files
    stay the artifact a voyage reads; aboard a hired box (no store) it is registered when it is brought home."""
    from thorp import store

    if store.papers():
        return
    from thorp.viable.records import TokeniserBook, TokeniserRecord

    with store.session() as s:
        r = s.get(TokeniserRecord, tid) or TokeniserRecord(id=tid)
        r.path, r.settings, r.stats = str(d), json.loads(json.dumps(settings)), json.loads(json.dumps(stats, default=float))
        r = s.merge(r)
        s.flush()
        have = {b.book_id for b in s.query(TokeniserBook).filter_by(tokeniser_id=tid)}
        s.add_all(TokeniserBook(tokeniser_id=tid, book_id=b) for b in sorted(set(book_ids) - have))
