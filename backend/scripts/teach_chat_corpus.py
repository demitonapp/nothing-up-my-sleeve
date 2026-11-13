"""The teacher's part of the chat corpus (13 November 2026; Justin, of a 9m in the chat terminal, "top 5 things we can
do at that size to make it a better chatbot", then "do 1, 2, 3", "4 agreed, 5, agreed").

The 9m in the console had read period books and lines mined from plays, so a plain modern question got a line from a
play back. This corpus is what it never read: short, plain, modern talk, and a few things a chatbot must know of itself.
The teacher writes only what code cannot; code checks every line and writes everything that must be exact.

- **talk** (item 1): a conversation of 2 to 5 exchanges between a person and a helper, on one everyday topic in one
  situation, both drawn by code (`TOPICS`, `SITUATIONS`). The helper speaks in short, plain, kind sentences, and in
  about half its turns asks one curious question back (the fleet's disposition, Justin 12 November: "the bias should
  be curiosity bias"). Kept only if it is in the asked shape and at least `OGDEN_MIN` of its words are Ogden's (or their
  forms).
- **self** (item 5): ways a person asks the helper who it is, what it can do, what it cannot. The teacher writes only the
  questions; the answers are code's, from one sheet of true facts (backend/scripts/make_chat_corpus.py `SELF`), so the
  ship never says two different things about itself.
- **edges** (item 5): questions a small helper with no internet cannot answer (today's news, a stranger's name, a price
  now, a long expert explanation), each with a short honest answer that says it does not know.
- **facts** (item 5, the look-up tool): one plain fact on a topic, a question the fact answers, and the short answer.
  Code serves the facts to the ninth tool, `look_up(topic)` (thorp/ship_tools.py), and writes the call.

The teacher is the tool corpus's, Qwen3.8 27B (4-bit, MLX), asked many prompts at once (`batch_generate`): one at a
time it writes about five words a second on this Mac, which would take weeks for millions of words. `--teacher` takes
another (Qwen3 30B-A3B is quicker but is not on this Mac).
What it writes is saved after every batch to `lists/chat-teaching-v1.json`; a run resumes where the file stops.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/teach_chat_corpus.py [--talk N] [--only KIND] [--batch B]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from thorp import ogden, paths  # noqa: E402

TEACHER = "mlx-community/Qwen3.8-27B-4bit"
OUT = "lists/chat-teaching-v1.json"
BATCH = 24  # prompts written at once
OGDEN_MIN = 0.55  # the share of a conversation's words that must be Ogden's or their forms (contractions read as their
# words; modern plain talk read 0.49 to 0.73 on the probe, and the Ogden shelf's books are ranked from 0.68)
_WORD = re.compile(r"[A-Za-z][A-Za-z']*")

TOPICS = """breakfast; lunch at work; cooking dinner; baking bread; a favourite fruit; tea and coffee; the weather today;
rain; a hot summer day; snow; the seasons; a pet dog; a pet cat; birds in the garden; fish in a tank; a horse; farm
animals; wild animals; insects; trees; flowers; growing vegetables; a walk in the park; the beach; the sea; a river;
mountains; the stars at night; the moon; the sun; a rainbow; a train trip; a bus ride; riding a bicycle; learning to
drive; a long flight; a holiday; packing a bag; getting lost; a new town; a market; buying shoes; saving money; a first
job; a hard day at work; a kind boss; working from home; a meeting; a new friend; an old friend; a brother or sister;
a grandparent; a new baby; a birthday; a wedding; a party; a gift; saying sorry; feeling sad; feeling happy; feeling
tired; feeling worried; feeling lonely; feeling proud; a bad dream; sleeping well; a cold; a sore head; going to the
doctor; eating well; walking for health; running; swimming; football; tennis; a game of cards; chess; a puzzle; a
favourite book; reading at night; writing a letter; a story; a song; music; learning to sing; drawing; painting;
taking photographs; a film; a play; a museum; history; how a clock works; how a ship floats; how bread rises; why the
sky looks blue; why leaves fall; how bees make honey; how plants drink; magnets; electricity at home; a computer; a
phone; the internet; robots; school; a test; homework; a teacher; learning a language; counting; shapes; telling time;
the days of the week; the months; cleaning the house; washing clothes; fixing a chair; building a shed; a garden
fence; neighbours; moving house; a quiet street; a busy city; a small village; a library; a post office; a bakery; a
shop; a restaurant; ordering food; a picnic; camping; a fire in the evening; a storm; a power cut; being late;
waiting; patience; good manners; helping someone; a promise; a secret; a surprise; a mistake; trying again; asking for
help; giving advice; making a plan; a hobby; collecting things; a boat; fishing; the wind; clouds; a lake; an island;
a map; a lighthouse; sailors; the harbour""".replace("\n", " ").split(";")
TOPICS = [t.strip() for t in TOPICS if t.strip()]
SITUATIONS = ("the person has a question", "the person wants advice", "the person is telling a small story about their day",
              "the person is curious and asks why", "the person is a child", "the person is in a hurry",
              "the person is unsure what to do", "the person is happy and wants to share it",
              "the person is a little upset", "the person wants to learn how to do something")  # fmt: skip

SELF_KINDS = {
    "name": "what the helper is called, or who it is",
    "maker": "who made the helper, or how it was made",
    "size": "how big or small the helper is, or how much it knows",
    "can": "what the helper can do, or how it can help",
    "cannot": "what the helper cannot do: see, hear, go on the internet, remember past talks",
    "feelings": "whether the helper has feelings, likes things, or is alive",
    "wrong": "whether the helper can be wrong, or whether to trust it",
}
EDGE_KINDS = ("today's news or something that happened this week", "the price of something right now", "a private person "
              "by name, such as a neighbour or a stranger", "the result of a game played yesterday", "the weather in a "
              "named town right now", "a hard question for a doctor or a lawyer", "something only the person can know, "
              "such as what is in their pocket", "a long, deep expert explanation")  # fmt: skip
FACT_KINDS = ("countries and their capital cities", "animals", "the planets and the sky", "the human body", "plants and "
              "trees", "inventions and who made them", "the oceans, rivers and mountains", "food and where it comes "
              "from", "famous buildings", "the elements and what things are made of", "sports and games", "weather "
              "and the seasons", "music and instruments", "ships and the sea", "numbers and measures")  # fmt: skip


_CONTRACTIONS = {"n't": " not", "'re": " are", "'ve": " have", "'ll": " will", "'d": " would", "'m": " am", "'s": ""}


def ogden_share(text: str) -> float:
    """The share of words that are Ogden's or their forms, a contraction read as its words (don't as do not)."""
    low = text.lower().replace("’", "'").replace("won't", "will not").replace("can't", "can not")
    for short, long in _CONTRACTIONS.items():
        low = low.replace(short, long)
    ws = _WORD.findall(low)
    return sum(1 for w in ws if ogden.lemma(w) is not None) / len(ws) if ws else 0.0


def ask_talk(topic: str, situation: str, exchanges: int) -> str:
    return (f"Write a short conversation between a person (P) and a friendly helper (H) about {topic}. In it, "
            f"{situation}. It has exactly {exchanges} exchanges: P speaks, then H answers, {exchanges} times. Use plain, "
            "simple English: common words a child knows, short sentences. The helper is kind, true and brief (one to three "
            "sentences a turn), says so when it does not know, and in about half its turns asks one short, curious "
            "question back. No names, no stage directions, no emoji. Write each turn on its own line, starting 'P: ' or "
            "'H: ', and nothing else.")  # fmt: skip


def keep_talk(said: str, exchanges: int) -> list[list[str]] | None:
    """A conversation in the asked shape: P and H taking turns, P first, 2 to 6 whole exchanges (the teacher often
    writes one more than asked, which is kept), each turn short and plain."""
    lines = [ln.strip() for ln in said.strip().splitlines() if ln.strip()]
    if len(lines) % 2 or not 2 <= len(lines) // 2 <= 6:
        return None
    pairs = []
    for i in range(0, len(lines), 2):
        p, h = lines[i], lines[i + 1]
        if not (p.startswith("P:") and h.startswith("H:")):
            return None
        p, h = p[2:].strip(), h[2:].strip()
        if not p or not h or len(p.split()) > 40 or len(h.split()) > 50 or re.search(r"[*#<>{}\[\]]", p + h):
            return None
        pairs.append([p, h])
    if ogden_share(" ".join(x for pr in pairs for x in pr)) < OGDEN_MIN:
        return None
    return pairs


def ask_self(purpose: str, n: int) -> str:
    return (f"Write {n} different short questions a person might ask a small AI helper about {purpose}. Plain everyday "
            "English, at most 14 words each, some casual, some polite. One question a line, no numbering, nothing else.")


def keep_question(line: str, words: int = 18) -> str | None:
    s = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"').strip()
    if not s or not s.endswith("?") or len(s.split()) > words or re.search(r"[{}<>*#]", s):
        return None
    return s


def keep_self(line: str) -> str | None:
    """A question about the helper itself: it speaks to `you` (the probe's "Who made me?" did not)."""
    s = keep_question(line)
    return s if s and re.search(r"\b(?:you|your|yourself)\b", s, re.I) else None


def ask_edges(kind: str, n: int) -> str:
    return (f"A small AI helper has no internet, no clock of its own and knows only a little. Write {n} different short "
            f"questions a person might ask it about {kind}, which it cannot truly answer. After each question write ' | ' "
            "and the helper's honest answer in plain simple English, at most 25 words: it says it does not know or "
            "cannot tell, says why in a few words, and may suggest where to find out or ask a short question back. One "
            "pair a line, no numbering, nothing else.")  # fmt: skip


def keep_edge(line: str) -> list[str] | None:
    q, sep, a = line.partition("|")
    q = keep_question(q)
    a = a.strip().strip('"')
    if not sep or not q or not a or len(a.split()) > 30 or not re.search(r"\b(?:know|sure|cannot|can't|can not|no way)\b", a, re.I):
        return None
    return [q, a]


def ask_facts(kind: str, n: int) -> str:
    return (f"Write {n} different plain facts about {kind}, each one true and well known. For each, write four parts "
            "separated by ' | ': the topic in one to three words; the fact as one short sentence in simple English; a "
            "question a person might ask that the fact answers, and that names the topic in the same words; the short "
            "answer, at most 12 words. For example: France | The capital of France is Paris. | What is the capital of "
            "France? | It is Paris. One fact a line, no numbering, nothing else.")  # fmt: skip


def keep_fact(line: str) -> list[str] | None:
    parts = [p.strip().strip('"') for p in line.split("|")]
    if len(parts) != 4 or not all(parts):
        return None
    topic, fact, q, a = parts
    q = keep_question(q, 22)
    if not q or len(topic.split()) > 3 or len(fact.split()) > 30 or len(a.split()) > 14 or re.search(r"\d{5,}", fact):
        return None
    if topic.lower() not in q.lower():  # the call is made from the question's own words
        return None
    return [topic, fact, q, a]


class Teacher:
    def __init__(self, name: str) -> None:
        from mlx_lm import load

        self.name = name
        self.model, self.tok = load(name)

    def __call__(self, texts: list[str], max_tokens: int) -> list[str]:
        """What the teacher writes for each prompt. Out of GPU memory, the batch is written in halves (13 November: 24
        prompts of the 27B did not fit beside a voyage and the dashboard), down to one prompt; one that still does not
        fit is tried again after a wait, and after `RETRIES` waits the run stops, keeping what it wrote."""
        return self._fit(texts, max_tokens, 0)

    def _fit(self, texts: list[str], max_tokens: int, waited: int) -> list[str]:
        try:
            return self._write(texts, max_tokens)
        except RuntimeError as e:
            if not out_of_memory(e):
                raise
            _clear()
            if len(texts) > 1:
                half = len(texts) // 2
                print(f"out of GPU memory at {len(texts)} prompts: writing {half} and {len(texts) - half}", flush=True)
                return self._fit(texts[:half], max_tokens, waited) + self._fit(texts[half:], max_tokens, waited)
            if waited >= RETRIES:
                raise
            print(f"out of GPU memory at one prompt: waiting {WAIT}s ({waited + 1}/{RETRIES})", flush=True)
            time.sleep(WAIT)
            return self._fit(texts, max_tokens, waited + 1)

    def _write(self, texts: list[str], max_tokens: int) -> list[str]:
        import importlib

        from mlx_lm.sample_utils import make_sampler

        batch_generate = importlib.import_module("mlx_lm.generate").batch_generate
        prompts = [self.tok.apply_chat_template([{"role": "user", "content": t}], add_generation_prompt=True,
                                                enable_thinking=False) for t in texts]  # fmt: skip
        got = batch_generate(self.model, self.tok, prompts, max_tokens=max_tokens,
                             sampler=make_sampler(temp=0.9, top_p=0.95))  # fmt: skip
        return [re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip() for t in got.texts]


RETRIES = 6  # waits for memory at a single prompt before the run stops
WAIT = 120  # seconds a wait lasts


def out_of_memory(e: BaseException) -> bool:
    s = str(e).lower()
    return "insufficient memory" in s or "out of memory" in s or "outofmemory" in s


def _clear() -> None:
    try:
        import mlx.core as mx

        mx.clear_cache()
    except Exception:  # noqa: BLE001 - nothing to clear
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--teacher", default=TEACHER)
    ap.add_argument("--talk", type=int, default=60_000, help="conversations to keep")
    ap.add_argument("--self-per", type=int, default=60, help="questions to keep for each self kind")
    ap.add_argument("--edges-per", type=int, default=60, help="pairs to keep for each edge kind")
    ap.add_argument("--facts-per", type=int, default=120, help="facts to keep for each fact kind")
    ap.add_argument("--only", choices=("talk", "self", "edges", "facts"), default=None)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--hours", type=float, default=None, help="stop after this long (the file keeps what is done)")
    ap.add_argument("--first", type=int, default=None, help="only the first N kinds of each list (a probe)")
    ap.add_argument("--out", default=OUT, help="the teaching file (a probe writes elsewhere)")
    a = ap.parse_args()
    out = paths.resolve(a.out) if not Path(a.out).is_absolute() else Path(a.out)
    have = (json.loads(out.read_text(encoding="utf-8")) if out.exists() else
            {"teacher": a.teacher, "talk": [], "self": {}, "edges": {}, "facts": {}, "calls": []})  # fmt: skip
    have.setdefault("teachers", sorted({have.get("teacher", a.teacher), a.teacher}))
    t = Teacher(a.teacher)
    started = time.time()
    rng = random.Random(len(have["talk"]) + 13)

    def save() -> None:
        out.write_text(json.dumps(have, indent=1, ensure_ascii=False), encoding="utf-8")

    def late() -> bool:
        return a.hours is not None and time.time() - started > a.hours * 3600

    def lists(section: str, kinds, ask, keep, per: int, n_ask: int, tokens: int) -> None:
        for kind in list(kinds)[: a.first]:
            got = have[section].setdefault(kind, [])
            tries = 0
            while len(got) < per and tries < 6 and not late():
                tries += 1
                t0 = time.time()
                said = t([ask(kind, n_ask)] * min(a.batch, 4), tokens)
                seen = {json.dumps(x) for x in got}
                for s in said:
                    for line in s.splitlines():
                        k = keep(line)
                        if k and json.dumps(k) not in seen and len(got) < per:
                            got.append(k)
                            seen.add(json.dumps(k))
                save()
                print(f"{section} / {kind[:40]}: {len(got)}/{per} ({time.time() - t0:.0f}s)", flush=True)

    if a.only in (None, "self"):
        lists("self", SELF_KINDS, lambda k, n: ask_self(SELF_KINDS[k], n), keep_self, a.self_per, 25, 25 * 24)
    if a.only in (None, "edges"):
        lists("edges", EDGE_KINDS, ask_edges, keep_edge, a.edges_per, 15, 15 * 50)
    if a.only in (None, "facts"):
        lists("facts", FACT_KINDS, ask_facts, keep_fact, a.facts_per, 20, 20 * 60)
    if a.only in (None, "talk"):
        while len(have["talk"]) < a.talk and not late():
            jobs = [(rng.choice(TOPICS), rng.choice(SITUATIONS), rng.randint(2, 5)) for _ in range(a.batch)]
            t0 = time.time()
            said = t([ask_talk(*j) for j in jobs], 420)
            kept = 0
            for (topic, situation, n), s in zip(jobs, said, strict=True):
                k = keep_talk(s, n)
                if k:
                    have["talk"].append({"topic": topic, "situation": situation, "exchanges": k})
                    kept += 1
            words = sum(len(s.split()) for s in said)
            have["calls"].append({"kind": "talk", "asked": len(jobs), "kept": kept, "words": words,
                                  "seconds": round(time.time() - t0, 1)})  # fmt: skip
            save()
            print(f"talk: {len(have['talk'])}/{a.talk} (kept {kept}/{len(jobs)}, {words / (time.time() - t0):.0f} words/s)",
                  flush=True)  # fmt: skip
    print(json.dumps({"talk": len(have["talk"]), "self": {k: len(v) for k, v in have["self"].items()},
                      "edges": sum(len(v) for v in have["edges"].values()),
                      "facts": sum(len(v) for v in have["facts"].values())}))  # fmt: skip


if __name__ == "__main__":
    main()
