"""The shapes evaluator (Justin, 2026-11-07 20:20: "ogdens v0.1 must include the parts of speech classification";
"all sizes should be able to record against that taxonomy"): at fixed points of the judge books (the held-out
decks: today the Forgotten Tomes), is the model's top guess the right *kind* of word, and the right keyed word?

At each reading, for every class alike:

- **Where**: two windows of the model's context per judge book (at a third and two thirds of the way in), the
  same for every class and every reading; in each, up to 64 points where a word, a punctuation mark or a line
  break begins (after the first 32 pieces, so the model has something to go on).
- **The truth**: the judge text tagged in context by the pinned tagger (s2_coordination/tagger.py), once per
  voyage, into the shapes taxonomy (s5_policy/taxonomy.py): the fine tier (UD parts of speech, PUNCT, BREAK)
  and Ogden's coarse tier (THING, QUALITY, OPERATION, MARK).
- **The guess**: the model's most likely next piece, tagged in its own context (the text before it, then it).
- **What it expects**: its ten likeliest next pieces' probability, summed by each piece's commonest tag in the
  Ogden corpus (the lexicon), a line break as BREAK; a piece the lexicon does not know (part of a word) is OTHER.
- **The keyed word** (the 2-, 3- and 4-word goals): truth and guess as keyed words (Ogden's 850, <name>,
  <number>, <thing>; a name or number by its tag), where the truth is a word.

Metrics: `shapes/upos_top1`, `shapes/ogden_top1`, `shapes/keyed_top1`, `shapes/points`, `shapes/mass/<TAG>`,
`shapes/truth/<TAG>`; artifact `shapes`: the confusion table (truth x guess, fine tier) and the counts.
"""

from __future__ import annotations

import collections
import functools
import json
import os

import numpy as np

from thorp import shards
from thorp.evaluators import EvalContext, EvalResult

WINDOWS_PER_BOOK = 2
POINTS_PER_WINDOW = 64
WARM = 32  # pieces of context before the first point
GUESS_CONTEXT = 48  # pieces of context the guess is tagged with
TOP = 10
LEXICON = os.environ.get("THORP_SHAPES_LEXICON", "ogden-v0-1")


def _offsets(tok, ids: list[int]) -> list[int]:
    """Where each piece starts in the decoded text (piece i spans off[i]:off[i+1])."""
    off = [0]
    for k in range(1, len(ids) + 1):
        off.append(len(tok.decode(ids[:k])))
    return off


@functools.lru_cache(maxsize=64)
def _window(tok_id: str, book: str, start: int, length: int):
    """A judge window, decoded, tagged and lined up with its pieces: cached for the voyage (same every reading)."""
    from thorp import tokeniser as tokmod
    from thorp.viable.s2_coordination import tagger

    tok = tokmod.load(tok_id)
    arr = shards.load(tok_id, book, tok)
    ids = [int(x) for x in arr[start : start + length]]
    text = tok.decode(ids)
    off = _offsets(tok, ids)
    starts = {s: (w, t) for s, _, w, t in tagger.tag(text)}
    points = []
    for p in range(WARM, len(ids) - 1):  # predict piece p+1 from pieces 0..p
        piece = tok.decode(ids[: p + 2])[off[p + 1] :]
        lead = len(piece) - len(piece.lstrip(" "))
        at = off[p + 1] + lead
        if at in starts and (lead or piece[:1] in "\n" or not piece[:1].isalnum() or at == 0 or text[at - 1] in " \n"):
            points.append((p, starts[at][0], starts[at][1]))
    step = max(1, len(points) // POINTS_PER_WINDOW)
    return ids, text, off, points[::step][:POINTS_PER_WINDOW]


def _keyed(word: str, tag: str) -> str | None:
    from thorp import ogden

    if tag == "PROPN":
        return "<name>"
    if tag == "NUM":
        return "<number>"
    if tag in ("PUNCT", "BREAK") or not any(c.isalpha() for c in word):
        return None
    k = ogden.keyed(word.lower())
    return k[0] if k else None


def evaluate(ctx: EvalContext) -> EvalResult:
    import mlx.core as mx

    from thorp.viable.s2_coordination import tagger
    from thorp.viable.s5_policy import taxonomy

    out = EvalResult()
    tok = ctx.tokeniser
    judge = next(iter(ctx.sets.values()), [])
    try:
        lex = tagger.lexicon(LEXICON)
    except FileNotFoundError:
        lex = {}
    rows, guess_texts, mass_sum = [], [], collections.Counter()
    for b in judge:
        n = len(shards.load(tok.id, b, tok))
        length = min(ctx.context, n - 1)
        if length <= WARM + 2:
            continue
        for w in range(1, WINDOWS_PER_BOOK + 1):
            start = max(0, int(n * w / (WINDOWS_PER_BOOK + 1)) - length // 2)
            ids, text, off, points = _window(tok.id, b, start, length)
            if not points:
                continue
            logits = ctx.model(mx.array([ids[:-1]]))[0].astype(mx.float32)
            probs = mx.softmax(logits, axis=-1)
            top = mx.argsort(-probs, axis=-1)[:, :TOP]
            mx.eval(probs, top)
            top_np, probs_np = np.array(top), np.array(probs)
            for p, word, tag in points:
                cand = top_np[p]
                guess_piece = tok.decode([int(cand[0])])
                ctx_text = text[off[max(0, p + 1 - GUESS_CONTEXT)] : off[p + 1]]
                guess_texts.append(ctx_text + guess_piece)
                rows.append({"truth": tag, "word": word, "guess_piece": guess_piece})
                m = collections.Counter()
                for c in cand:
                    piece = tok.decode([int(c)])
                    if "\n" in piece:
                        t = "BREAK"
                    else:
                        t = lex.get(piece.strip().lower()) or ("PUNCT" if piece.strip() and not any(ch.isalnum() for ch in piece) else "OTHER")
                    m[t] += float(probs_np[p, int(c)])
                total = sum(m.values()) or 1.0
                for t, v in m.items():
                    mass_sum[t] += v / total
    if not rows:
        return out
    guess_tags = tagger.last_tag(guess_texts)
    confusion = collections.Counter()
    fine_hit = coarse_hit = keyed_hit = keyed_n = 0
    for r, g in zip(rows, guess_tags, strict=True):
        piece = r["guess_piece"]
        g = "BREAK" if "\n" in piece else (g or "OTHER")
        confusion[(r["truth"], g)] += 1
        fine_hit += g == r["truth"]
        coarse_hit += taxonomy.coarse(g) == taxonomy.coarse(r["truth"])
        kt = _keyed(r["word"], r["truth"])
        if kt is not None:
            keyed_n += 1
            keyed_hit += kt == _keyed(piece.strip(), g)
    n = len(rows)
    out.metrics["shapes/points"] = float(n)
    out.metrics["shapes/upos_top1"] = fine_hit / n
    out.metrics["shapes/ogden_top1"] = coarse_hit / n
    if keyed_n:
        out.metrics["shapes/keyed_top1"] = keyed_hit / keyed_n
    truth = collections.Counter(r["truth"] for r in rows)
    for t in taxonomy.FINE:
        out.metrics[f"shapes/mass/{t}"] = mass_sum.get(t, 0.0) / n
        out.metrics[f"shapes/truth/{t}"] = truth.get(t, 0) / n
    out.artifacts.append(
        {
            "kind": "shapes",
            "text": json.dumps(
                {
                    "taxonomy": taxonomy.VERSION,
                    "tagger": tagger.TAGGER_ID,
                    "lexicon": LEXICON if lex else None,
                    "points": n,
                    "keyed_points": keyed_n,
                    "confusion": [[t, g, c] for (t, g), c in sorted(confusion.items())],
                }
            ),
        }
    )
    return out
