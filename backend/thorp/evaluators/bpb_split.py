"""Bits per byte split by what kind of byte is being predicted: the 9m rung's scoreboard.

Every byte of a held-out book is put in one class, by the character it belongs to:

- word_inside: a letter whose previous character is a letter (spelling: the rest of a word once it
  has begun). An apostrophe between two letters (don't, o'er) counts as a letter here.
- word_start: a letter whose previous character is not one (word choice: which word comes next).
- punct: Unicode punctuation (P*), curly quotes and dashes included.
- space: spaces and tabs. newline: line breaks (verse, paragraphs, dialogue layout).
- digit: Unicode numbers (N*). other: everything else (symbols, control characters).

A token's loss is shared evenly over its bytes (a token is one bet, so this is a convention, the
one under which the classes add back to the book's bits per byte, weighted by their byte shares).
The closing EOS has no bytes; its loss is reported as `eos_bits` and left out of every class.
Losses come from the same windows as ce_bpb, so the two agree to rounding.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata

import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.ce_bpb import book_losses, losses_of  # noqa: F401  (book_losses: others read it here)

CLASSES = ("word_start", "word_inside", "punct", "space", "newline", "digit", "other")
_C = {c: i for i, c in enumerate(CLASSES)}
_LETTER, _APOS = 100, 101  # provisional char classes before word_start / word_inside is decided
APOSTROPHES = {"'", "’"}


def piece_bytes(tok) -> list[bytes]:
    """The bytes each vocabulary id decodes to (control pieces decode to nothing)."""
    if hasattr(tok, "piece_bytes_list"):  # an outside model's tokeniser (thorp/outside_deck.py)
        return tok.piece_bytes_list
    sp = tok.sp
    out = []
    for i in range(sp.get_piece_size()):
        if sp.is_control(i) or sp.is_unknown(i):
            out.append(b"")
        elif sp.is_byte(i):
            out.append(bytes([int(sp.id_to_piece(i)[3:5], 16)]))
        else:
            out.append(sp.id_to_piece(i).replace("▁", " ").encode("utf-8"))
    return out


def _char_class(ch: str) -> int:
    if ch in APOSTROPHES:
        return _APOS
    if ch in "\n\r":
        return _C["newline"]
    if ch in " \t":
        return _C["space"]
    cat = unicodedata.category(ch)
    if cat[0] == "L":
        return _LETTER
    if cat[0] == "P":
        return _C["punct"]
    if cat[0] == "N":
        return _C["digit"]
    if cat[0] == "Z":
        return _C["space"]
    return _C["other"]


_ASCII = np.array([_char_class(chr(i)) for i in range(128)], dtype=np.int16)


def byte_classes(data: bytes) -> np.ndarray:
    """One class index per byte of UTF-8 `data`."""
    b = np.frombuffer(data, dtype=np.uint8)
    if len(b) == 0:
        return np.zeros(0, dtype=np.int16)
    starts = np.flatnonzero((b < 0x80) | (b >= 0xC0))
    lens = np.diff(np.append(starts, len(b)))
    lead = b[starts]
    cls = np.where(lead < 0x80, _ASCII[np.minimum(lead, 127)], 0).astype(np.int16)
    for j in np.flatnonzero(lead >= 0x80):
        s = starts[j]
        try:
            ch = data[s : s + lens[j]].decode("utf-8")
            cls[j] = _char_class(ch[0])
        except UnicodeDecodeError:
            cls[j] = _C["other"]
    letter = cls == _LETTER
    apos = cls == _APOS
    prev_l = np.concatenate([[False], letter[:-1]])
    next_l = np.concatenate([letter[1:], [False]])
    joiner = apos & prev_l & next_l
    wordish = letter | joiner
    prev_w = np.concatenate([[False], wordish[:-1]])
    out = cls.copy()
    out[wordish & prev_w] = _C["word_inside"]
    out[letter & ~prev_w] = _C["word_start"]
    out[apos & ~joiner] = _C["punct"]
    return np.repeat(out, lens)


def book_split(losses: np.ndarray, tokens: np.ndarray, pbytes: list[bytes]) -> dict:
    """{class: {bits, bytes}} plus eos_bits, for one book's per-token losses."""
    toks = np.asarray(tokens, dtype=np.int64)
    pieces = [pbytes[t] for t in toks]
    tlen = np.fromiter((len(p) for p in pieces), dtype=np.int64, count=len(pieces))
    data = b"".join(pieces)
    cls = byte_classes(data)
    per_byte = np.repeat(losses / np.maximum(tlen, 1), tlen) / math.log(2)
    bits = np.bincount(cls, weights=per_byte, minlength=len(CLASSES))
    nbytes = np.bincount(cls, minlength=len(CLASSES))
    out = {c: {"bits": float(bits[i]), "bytes": int(nbytes[i])} for i, c in enumerate(CLASSES)}
    out["eos_bits"] = float(losses[tlen == 0].sum() / math.log(2))
    return out


def evaluate(ctx: EvalContext) -> EvalResult:
    out = EvalResult()
    tok = ctx.tokeniser
    pbytes = piece_bytes(tok)
    report = {}
    for set_name, book_ids in ctx.sets.items():
        per_book = {}
        for b in book_ids:
            arr = np.asarray(shards.load(tok.id, b, tok))
            losses = losses_of(ctx, b, arr)  # ce_bpb's own, when it has read this step
            per_book[b] = book_split(losses, arr, pbytes)
        report[set_name] = per_book
        for scope, ids in (
            ("", list(per_book)),
            ("_en", [b for b in per_book if ctx.languages.get(b) == "en"]),
        ):
            for c in CLASSES:
                vals = [
                    per_book[b][c]["bits"] / per_book[b][c]["bytes"]
                    for b in ids
                    if per_book[b][c]["bytes"]
                ]
                if vals:
                    out.metrics[f"eval/{set_name}/split/{c}/bpb_mean{scope}"] = float(np.mean(vals))
                shares = [
                    per_book[b][c]["bytes"] / max(1, sum(per_book[b][k]["bytes"] for k in CLASSES))
                    for b in ids
                ]
                if shares:
                    out.metrics[f"eval/{set_name}/split/{c}/share_mean{scope}"] = float(
                        np.mean(shares)
                    )
    text = json.dumps({"classes": list(CLASSES), "sets": report})
    out.artifacts.append(
        {
            "kind": "bpb_split",
            "path": "",
            "sha1": hashlib.sha1(text.encode()).hexdigest(),
            "text": text,
        }
    )
    return out
