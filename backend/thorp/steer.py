"""Steering how a small ship's answer is drawn (13 November 2026; Justin, of a 9m in the chat terminal: "What are the
top 5 things we can do at that size to make it a better chatbot", then "do 1, 2, 3").

A 9m picks the right tool far more often than it copies the right values (the tool leg: the right tool 88%, the exact
call 36.5%), and its reply uses little of what it was asked. Both are helped where the answer is drawn, with no
training, because a 9m is quick enough to be asked many times over:

- **A call is chosen, not spelt** (`pick_call`). Every argument of the eight tools is a value the question already
  holds: its numbers for `calculate`, its dates for `days_between`, one of its words for `define`, a run of its words
  for a model, a job or an expedition. Code writes out every call the question allows (`allowed_calls`), the ship
  scores each one whole, up to `<result>`, and the likeliest is run. A question with no number cannot reach
  `calculate`; one with fewer than two dates cannot reach `days_between`.
- **An answer's figures are the tool's** (`Licence`). After a result, a number the ship writes must be one the result or
  the question holds (or the same number written as the lessons write it: 14768 as 14,768, 2027-08-16 as 16, August and
  2027); a piece that would begin any other number is not drawn, and a reply naming a month or a weekday the result
  does not hold is set aside.
- **Many replies, the best kept** (`write`, `rerank`). `SAMPLES` replies are drawn at once and each is scored by how
  much likelier the ship finds it after this question than after another (`DECOYS`), a piece: the reply that most
  belongs to the question is kept. `LAMBDA` weighs the two (0 is the likeliest reply, 1 the one most tied to the
  question).

The ship still decides for itself whether a tool is wanted (the likelier of `<call>` and `<answer>`): steering does
not mend a ship that calls a tool for a greeting. That is the corpus's work.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

import numpy as np

from thorp import turns
from thorp.evaluators.samples import shaped
from thorp.models import ops

SAMPLES = 16  # replies drawn for one answer
LAMBDA = 0.5  # how much of a reply's likelihood after another question is taken off its score
DECOYS = ("What is it?", "Tell me more.", "Is that so?")  # the other questions a reply is read after
CHUNK = 40_000  # pieces in one scoring pass

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December")  # fmt: skip
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_MONTH = {m.lower(): i + 1 for i, m in enumerate(MONTHS)}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_FIGURE = re.compile(r"\d+(?:[,.:\-/]\d+)*")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_FIRST = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)? (?:of )?(" + "|".join(MONTHS) + r"),? (\d{4})\b", re.I)
_MONTH_FIRST = re.compile(r"\b(" + "|".join(MONTHS) + r") (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b", re.I)
_EDGES = ".,;:!?\"'()[]{}<>‘’“”"
# words a lesson never asks the meaning of: the words of the asking itself and the commonest function words (13
# November: offered them, the 9m called define(it) for "What time is it?" and define(the) for "What does the word coat
# mean?")
PLAIN_WORDS = frozenset("""a an the and or but if of to in on at by for with from as is are was were be been am do does
did what which who whom whose when where why how it its this that these those there here i me my you your he him his she
her we us our they them their can could would should will shall may might must not no yes so than then too very just
please tell know need want word words mean means meaning meant define definition say says said use used using people""".split())


# ---------------------------------------------------------------- what a question holds


def numbers_in(text: str) -> list[str]:
    """The question's numbers, in order, each once, written as a sum takes them (1,200 as 1200)."""
    out: list[str] = []
    for m in _NUMBER.finditer(_ISO.sub(" ", text)):
        n = m.group(0).replace(",", "").rstrip(".")
        if n not in out:
            out.append(n)
    return out


def dates_in(text: str) -> list[str]:
    """The question's dates as `days_between` takes them (17 March 1838 as 1838-03-17), in the order they are met."""
    found: list[tuple[int, str]] = []
    for m in _ISO.finditer(text):
        found.append((m.start(), m.group(0)))
    for m in _DAY_FIRST.finditer(text):
        found.append((m.start(), _iso(m.group(3), m.group(2), m.group(1))))
    for m in _MONTH_FIRST.finditer(text):
        found.append((m.start(), _iso(m.group(3), m.group(1), m.group(2))))
    out: list[str] = []
    for _, d in sorted(found):
        if d and d not in out:
            out.append(d)
    return out


def _iso(year: str, month: str, day: str) -> str:
    try:
        return dt.date(int(year), _MONTH[month.lower()], int(day)).isoformat()
    except (KeyError, ValueError):
        return ""


def words_in(text: str) -> list[str]:
    """The question's words as it wrote them, the punctuation at their edges taken off (a job's name keeps its marks:
    9m@v0.0.6-pins)."""
    return [w for w in (t.strip(_EDGES) for t in text.split()) if w]


def _runs(words: list[str], longest: int) -> list[str]:
    return [" ".join(words[i : i + n]) for n in range(1, longest + 1) for i in range(len(words) - n + 1)]


def allowed_calls(question: str, tools: tuple[str, ...] | list[str] | None = None) -> list[str]:
    """Every call the question allows, as the lessons write a call (backend/scripts/make_tool_corpus.py): each
    argument is a value the question holds."""
    from thorp import ship_tools

    have = tuple(tools) if tools else ship_tools.SET
    words = words_in(question)
    out: list[str] = []
    if "calculate" in have:
        nums = numbers_in(question)[:6]
        out += [f"calculate({a}{op}{b})" for i, a in enumerate(nums) for j, b in enumerate(nums) if i != j for op in "+-*/"]
    if "current_time" in have:
        out.append("current_time()")
    if "days_between" in have:
        dates = dates_in(question)[:4]
        out += [f"days_between({a}, {b})" for i, a in enumerate(dates) for j, b in enumerate(dates) if i != j]
    if "define" in have:
        out += [f"define({w.lower()})" for w in words if w.isalpha() and len(w) > 1 and w.lower() not in PLAIN_WORDS]
    if "board_score" in have:
        out += [f"board_score({r})" for r in _runs(words, 3)]
    if "queue_status" in have:
        out.append("queue_status()")
        out += [f"queue_status({w})" for w in words if re.search(r"[\d@_-]", w)]
    if "liberty_machine_status" in have:
        out.append("liberty_machine_status()")
    if "expedition_status" in have:
        out += [f"expedition_status({r.lower()})" for r in _runs(words, 4)]
    if "look_up" in have:  # a topic is a run of the question's words, as written, not led by a plain word
        out += [f"look_up({r})" for r in _runs(words, 3) if r.split()[0].lower() not in PLAIN_WORDS]
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------- the figures an answer may write


@dataclass
class Licence:
    """The figures, months and weekdays an answer may write: those of the question and of every result so far."""

    figures: set[str] = field(default_factory=set)
    names: set[str] = field(default_factory=set)

    @classmethod
    def of(cls, *texts: str) -> Licence:
        lic = cls()
        for text in texts:
            lic.read(text or "")
        return lic

    def read(self, text: str) -> None:
        for m in _FIGURE.finditer(text):
            whole = m.group(0)
            for part in {whole, *re.split(r"[,.:\-/]", whole), whole.replace(",", "")}:
                if not part:
                    continue
                self.figures.add(part)
                if part.isdigit():
                    self.figures.add(str(int(part)))  # 08 as 8
                    if len(part) > 3:
                        self.figures.add(f"{int(part):,}")  # 14768 as 14,768
        low = text.lower()
        for name in (*MONTHS, *WEEKDAYS):
            if re.search(rf"\b{name.lower()}\b", low):
                self.names.add(name)
        for d in dates_in(text):
            day = dt.date.fromisoformat(d)
            self.names.update((MONTHS[day.month - 1], WEEKDAYS[day.weekday()]))

    def figures_ok(self, text: str) -> bool:
        """Whether every number in `text` is licensed; a number the text ends in may still be growing, so it need
        only begin a licensed one."""
        for m in _FIGURE.finditer(text):
            fig, rest = m.group(0), text[m.end():]
            if fig in self.figures:
                continue
            # a figure the text ends in, or ends in with only a separator after it (2026-11-, 0.0.), is still being
            # written: it need only begin a licensed one (13 November: without the separator rule every reply that
            # wrote 2026-11 or 21m@v0.0 was cut there)
            growing = fig + rest
            if (not rest or set(rest) <= set(",.:-/")) and any(f.startswith(growing) for f in self.figures):
                continue
            return False
        return True

    def names_ok(self, text: str) -> bool:
        """Whether every month and weekday named in `text` is licensed. `May` is read as a month only beside a
        number, since it is also a common word."""
        for name in (*MONTHS, *WEEKDAYS):
            if name in self.names:
                continue
            pattern = r"\b\d{1,2} May\b|\bMay \d" if name == "May" else rf"\b{name}\b"
            if re.search(pattern, text):
                return False
        return True


def holds(reply: str, result: str) -> bool:
    """Whether a reply holds something of the result it answers from: one of its figures, or one of its words of four
    letters or more that is not a plain word (every lesson's answer does; 13 November, the 9m answered "That comes to
    12." after calculate(12*6) gave 72, and "Check: a star." after define(coat) gave a warm outer garment). A result
    with neither holds nothing to look for, and any reply passes."""
    figs = {m.group(0) for m in _FIGURE.finditer(result)}
    words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", result) if w.lower() not in PLAIN_WORDS}
    if not figs and not words:
        return True
    have = Licence.of(reply).figures
    if any(f in have or f.replace(",", "") in have for f in figs):
        return True
    low = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", reply)}
    return bool(words & low)


# ---------------------------------------------------------------- reading and writing in batches


def seq_logps(model, heads: list[list[int]], tails: list[list[int]], context: int) -> list[np.ndarray]:
    """The log-probability (nats) of each piece of each tail after its head. A head too long for the window loses
    its oldest pieces."""
    rows = []
    for h, t in zip(heads, tails, strict=True):
        keep = max(1, context - len(t))
        rows.append((list(h)[-keep:], list(t)))
    out: list[np.ndarray] = [np.zeros(0)] * len(rows)
    order = sorted(range(len(rows)), key=lambda i: len(rows[i][0]) + len(rows[i][1]))
    start = 0
    while start < len(order):
        batch = [order[start]]
        while start + len(batch) < len(order):
            nxt = order[start + len(batch)]
            if (len(rows[nxt][0]) + len(rows[nxt][1])) * (len(batch) + 1) > CHUNK:
                break
            batch.append(nxt)
        width = max(len(rows[i][0]) + len(rows[i][1]) for i in batch)
        x = np.zeros((len(batch), width - 1), dtype=np.int64)
        y = np.zeros((len(batch), width - 1), dtype=np.int64)
        for r, i in enumerate(batch):
            seq = rows[i][0] + rows[i][1]
            x[r, : len(seq) - 1], y[r, : len(seq) - 1] = seq[:-1], seq[1:]
        ce = np.asarray(ops.token_ce(model, x, y), dtype=np.float64)
        for r, i in enumerate(batch):
            h, t = len(rows[i][0]), len(rows[i][1])
            out[i] = -ce[r, h - 1 : h - 1 + t]
        start += len(batch)
    return out


def seq_logp(model, heads: list[list[int]], tails: list[list[int]], context: int) -> np.ndarray:
    """The log-probability of each tail after its head, summed over the tail's pieces."""
    return np.array([lp.sum() for lp in seq_logps(model, heads, tails, context)], dtype=np.float64)


def next_logp(model, ids: list[int], context: int) -> np.ndarray:
    """The log-probabilities of the next piece after `ids`."""
    logits = np.asarray(ops.Decoder(model, context, cache=False)([list(ids)[-context:]]), dtype=np.float64)[0]
    return logits - (logits.max() + np.log(np.exp(logits - logits.max()).sum()))


def call_pieces(tok, call: str) -> list[int]:
    """A call's pieces as a lesson holds them after `<call>`, its `<result>` at the end."""
    ids = tok.encode(turns.CALL + call + turns.RESULT)
    mark = tok.encode(turns.CALL)[-1]
    return ids[ids.index(mark) + 1 :] if mark in ids else ids


def pick_call(model, tok, head: list[int], question: str, context: int,
              tools: tuple[str, ...] | list[str] | None = None) -> tuple[str | None, list[dict]]:  # fmt: skip
    """The call a ship makes, read after `head` (the pieces up to and with `<call>`), and the five likeliest for the
    record. The tool is the ship's own choice among those the question allows: the likeliest name, read on the
    pieces that spell it. Its arguments are then the likeliest of that tool's allowed calls, each read whole up to
    `<result>`. (Read whole across every tool, a call with nothing to copy always won: the right tool fell from
    75% to 56% on the held-out questions, since a 9m gives any copied value little.)"""
    calls = allowed_calls(question, tools)
    if not calls:
        return None, []
    tails = [call_pieces(tok, c) for c in calls]
    lps = seq_logps(model, [head] * len(calls), tails, context)
    by_tool: dict[str, list[int]] = {}
    for i, c in enumerate(calls):
        by_tool.setdefault(c.split("(", 1)[0], []).append(i)
    named = {}
    for name, idx in by_tool.items():
        first, spelt, k = tails[idx[0]], "", 0
        while k < len(first) and len(spelt) < len(name):  # the pieces that spell the name
            k += 1
            spelt = tok.decode(first[:k])
        named[name] = float(lps[idx[0]][:k].sum())
    tool = max(named, key=named.get)
    whole = {i: float(lps[i].sum()) for i in by_tool[tool]}
    best = sorted(whole, key=lambda i: -whole[i])
    table = [{"call": calls[i], "logp": round(whole[i], 2)} for i in best[:5]]
    return calls[best[0]], table


def write(model, tok, head: list[int], n: int, *, temperature: float, max_new: int, context: int, seed: int,
          stop_ids: tuple[int, ...] = (), licence: Licence | None = None, top_k: int | None = None,
          top_p: float | None = None, repetition_penalty: float | None = None) -> list[tuple[list[int], int | None]]:  # fmt: skip
    """`n` continuations of `head`, drawn together: each is (its pieces, the stop piece that ended it or None).
    With a `licence`, a piece that would write an unlicensed number is not drawn. The draws are numpy's, on either
    backend."""
    rng = np.random.default_rng(seed)
    # the key/value cache: every live reply grows by one piece a step, so the batch extends the last one until a reply
    # ends (then it is read afresh once). Sampled draws may part from an uncached loop's in bf16 (ops.Decoder's note);
    # a console reply is not a reading kept in the ledger, so speed is worth that here
    dec = ops.Decoder(model, context, cache=True)
    outs: list[list[int]] = [[] for _ in range(n)]
    ended: list[int | None] = [None] * n
    alive = list(range(n))
    for _ in range(max_new):
        if not alive:
            break
        logits = np.asarray(dec([(head + outs[i])[-context:] for i in alive]), dtype=np.float32)
        still = []
        for row, i in enumerate(alive):
            scores = logits[row]
            if top_k or top_p or (repetition_penalty and repetition_penalty != 1.0):
                scores = shaped(np.array(scores), outs[i], temperature, top_k, top_p, repetition_penalty)
            piece = _draw(scores, logits[row], temperature, rng, tok, outs[i], licence, stop_ids)
            if piece is None:
                continue  # no licensed piece is left: the reply ends here
            if piece in stop_ids:
                ended[i] = piece
                continue
            outs[i].append(piece)
            still.append(i)
        alive = still
    return list(zip(outs, ended, strict=True))


def _draw(scores: np.ndarray, raw: np.ndarray, temperature: float, rng, tok, written: list[int],
          licence: Licence | None, stop_ids: tuple[int, ...]) -> int | None:  # fmt: skip
    """One piece from `scores` (the shaped scores; `raw` is the ship's own); with a licence, the pieces are tried in
    the order drawn until one keeps the reply's numbers licensed."""
    finite = np.isfinite(scores)
    if temperature == 0:
        order = np.argsort(-np.where(finite, scores, -np.inf))
    else:
        z = np.where(finite, scores, -np.inf) / temperature
        p = np.exp(z - z[finite].max())
        p[~finite] = 0.0
        p /= p.sum()
        k = int((p > 0).sum())
        order = rng.choice(len(p), size=k, replace=False, p=p)
    if licence is None:
        return int(order[0])
    for piece in order[:64]:
        piece = int(piece)
        if piece in stop_ids or licence.figures_ok(tok.decode([*written, piece])):
            return piece
    # nothing among the pieces drawn is licensed: take the likeliest licensed piece of the whole vocabulary
    for piece in np.argsort(-raw):
        piece = int(piece)
        if piece in stop_ids or licence.figures_ok(tok.decode([*written, piece])):
            return piece
    return None


def rerank(model, tok, head: list[int], decoys: list[list[int]], replies: list[list[int]], end: int | None,
           context: int, lam: float = LAMBDA) -> list[dict]:  # fmt: skip
    """Each distinct reply with its score, the best first: its log-probability a piece after `head`, less `lam`
    times its mean log-probability a piece after the decoy heads (the same turn opened on another question)."""
    seen: dict[tuple[int, ...], int] = {}
    for r in replies:
        if r:
            seen[tuple(r)] = seen.get(tuple(r), 0) + 1
    if not seen:
        return []
    distinct = [list(r) for r in seen]
    tails = [r + ([end] if end is not None else []) for r in distinct]
    own = seq_logp(model, [head] * len(tails), tails, context)
    other = np.zeros(len(tails))
    if lam and decoys:
        for d in decoys:
            other += seq_logp(model, [d] * len(tails), tails, context)
        other /= len(decoys)
    rows = []
    for r, t, a, b in zip(distinct, tails, own, other, strict=True):
        rows.append({"ids": r, "text": tok.decode(r).strip(), "drawn": seen[tuple(r)],
                     "own": round(float(a) / len(t), 3), "other": round(float(b) / len(t), 3),
                     "score": round(float(a - lam * b) / len(t), 3)})  # fmt: skip
    return sorted(rows, key=lambda r: -r["score"])
