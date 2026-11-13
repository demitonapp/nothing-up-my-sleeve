r"""The site's language, and the translator that puts the site into it (13 November, Justin: "add your language in the chat
terminal as an option. When you do that, the Liberty Machine picks up the language you've chosen and uses tiny aya earth
to dynamically translate the entire site").

The English is the record. Every page, DECISIONS.md and every policy is written in English and stays so: a translation is
a view of the English, made on the way to the screen, never written back. The choice of language is S5's (`s5.site_language`,
one row: Justin's choice, from the chat terminal's settings); the translating is S1's work (`s1.translations` keeps what
Tiny Aya Earth made, so a sentence is translated once).

The translator is CohereLabs/tiny-aya-earth (3.35B, Cohere2 architecture, CC-BY-NC 4.0, gated on Hugging Face), run with
MLX on this Mac. It is a model for the 67 languages named on its card; Afrikaans is not one of them (the card's list has
no Afrikaans), so Afrikaans is offered with that said beside it. A page is sent a few sentences at a time and the model
answers each alone, so one sentence cannot leak into the next.

The model stays in memory while the site speaks another language and is freed when it goes back to English; it is
not dropped on a clock, and it is not opened when the Mac has not the memory (TranslatorBusy says so).

The weights are found in this order: `THORP_TRANSLATOR` (a folder or a Hub repo), `data/models/tiny-aya-earth-8bit` (an
MLX conversion made from the Hub copy: `thorp translate prepare`), then the Hub copy in the Hugging Face cache. A copy of
the weights is not vendored into the repository (the licence is non-commercial: see memory `thorp-licence-stance`).

    uv run thorp translate status
    uv run thorp translate set xh --by Justin
    uv run thorp translate say xh "The first ship is a small keel."
    uv run thorp translate prepare            # 8-bit MLX copy of the Hub weights, about 3.6 GB
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import threading

from sqlalchemy import text

from thorp import paths, store

REPO = "CohereLabs/tiny-aya-earth"
MODEL_PAGE = "https://huggingface.co/CohereLabs/tiny-aya-earth"
PREPARED = "models/tiny-aya-earth-8bit"  # under data/
HEADROOM_GB = 1.0  # free memory the Mac keeps beyond the weights when the translator is loaded
BATCH = 16  # strings generated together
MAX_TEXTS = 24  # the most a request may ask for
MAX_CHARS = 1200  # the longest string it will translate

# Names the translator must leave alone: the project's own words. A translated "Liberty Machine" is a different thing.
GLOSSARY = (
    "Nothing up my sleeve",
    "Thorp",
    "Demiton",
    "Liberty Machine",
    "Schi'mint",
    "Vavatch End",
    "Sleeper Service",
    "Masaq",
    "Cohere",
    "Tiny Aya",
    "Qwen",
    "Gutenberg",
)


class TranslatorMissing(RuntimeError):
    """The translator's weights are not here, or cannot be opened; the message says what to do."""


# ---- the languages and the choice (Postgres: s5.languages, s5.site_language, s1.translations) ----


def languages() -> list[dict]:
    """Every language the site can be put into, English first, then by name."""
    with store.session() as s:
        rows = s.execute(
            text("select code, name, native_name, rtl, listed, is_source from s5.languages order by is_source desc, name")
        ).all()
    return [dict(r._mapping) for r in rows]


def language(code: str) -> dict:
    """One language, or a ValueError naming the ones there are."""
    code = (code or "").strip().lower()
    with store.session() as s:
        row = s.execute(
            text("select code, name, native_name, rtl, listed, is_source from s5.languages where code = :c"), {"c": code}
        ).first()
    if row is None:
        raise ValueError(f"no such language {code!r}")
    return dict(row._mapping)


def current() -> dict:
    """The language the site speaks now (the language's own row, with who chose it and when)."""
    with store.session() as s:
        row = s.execute(
            text(
                "select l.code, l.name, l.native_name, l.rtl, l.listed, l.is_source, c.chosen_by, c.chosen_at "
                "from s5.site_language c join s5.languages l on l.code = c.code where c.id = 1"
            )
        ).one()
    out = dict(row._mapping)
    out["chosen_at"] = out["chosen_at"].isoformat(timespec="seconds") if out.get("chosen_at") else None
    return out


def choose(code: str, by: str = "Justin") -> dict:
    """Put the site into a language. English is the way back. Returns what `current()` then says."""
    lang = language(code)
    with store.session() as s:
        s.execute(
            text("update s5.site_language set code = :c, chosen_by = :by, chosen_at = now() where id = 1"),
            {"c": lang["code"], "by": (by or "Justin").strip() or "Justin"},
        )
    keep_warm(lang)
    return current()


def keep_warm(lang: dict | None = None) -> None:
    """The translator's memory follows the choice: loaded (in the background) while the site speaks another language, freed
    when it is English again."""
    lang = lang or current()
    if lang["is_source"]:
        with ENGINE.lock:
            ENGINE.unload()
    else:
        ENGINE.warm()


def digest(source: str) -> str:
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def kept(code: str, sources: list[str]) -> dict[str, str]:
    """What is already translated: {English: translation} for those of `sources` the store holds."""
    if not sources:
        return {}
    by_hash = {digest(t): t for t in sources}
    with store.session() as s:
        rows = s.execute(
            text("select source_hash, target from s1.translations where code = :c and source_hash = any(:h)"),
            {"c": code, "h": list(by_hash)},
        ).all()
    return {by_hash[h]: target for h, target in rows if h in by_hash}


def keep(code: str, pairs: dict[str, str], model: str) -> None:
    with store.session() as s:
        for source, target in pairs.items():
            s.execute(
                text(
                    "insert into s1.translations (code, source_hash, source, target, model) values (:c, :h, :s, :t, :m) "
                    "on conflict (code, source_hash) do nothing"
                ),
                {"c": code, "h": digest(source), "s": source, "t": target, "m": model},
            )


def forget(code: str, source: str | None = None) -> int:
    """Drop translations so they are made again: one string, or a language's whole cache. Returns how many."""
    with store.session() as s:
        if source is None:
            got = s.execute(text("delete from s1.translations where code = :c"), {"c": code})
        else:
            got = s.execute(text("delete from s1.translations where code = :c and source_hash = :h"), {"c": code, "h": digest(source)})
        return got.rowcount or 0


# ---- the prompt and the tidying of what comes back ----


def names_in(source: str) -> list[str]:
    """The glossary's names the English uses, as written (a common word is not a name: "orbital" is, "Masaq" is not)."""
    return [g for g in GLOSSARY if g in source]


_PLACEHOLDER = re.compile(r"\{\d+\}")


def placeholders(s: str) -> list[str]:
    """The {0}, {1} ... a page's numbers were swapped for before the text was sent (the page puts them back)."""
    return sorted(_PLACEHOLDER.findall(s))


def faithful(source: str, out: str) -> bool:
    """Whether a translation kept every name and every placeholder the English had, and invented none."""
    return all(n in out for n in names_in(source)) and placeholders(out) == placeholders(source)


def prompt(lang: dict, source: str, insist: bool = False) -> str:
    name = lang["name"] if lang["native_name"] == lang["name"] else f"{lang['name']} ({lang['native_name']})"
    label = len(source.split()) <= 3 and not re.search(r"[.!?]$", source.strip())
    return (
        f"Translate the text below from English into {name}. "
        "It is from the dashboard of a research project that trains small language models; it uses sailing words "
        "(ship, keel, voyage, fleet, fitout, charter, harbour) in their ordinary sense. "
        + ("It is a short label on a button, tab or heading: translate it as a label (a noun or a short phrase, "
           "not an instruction). " if label else "")
        + (f"Keep these names exactly as written: {', '.join(names_in(source))}. " if names_in(source) else "")
        + ("Keep every placeholder such as {0} exactly as written, once each. " if placeholders(source) else "")
        + (f"These must appear in your answer exactly as written: {', '.join(repr(n) for n in names_in(source) + placeholders(source))}. " if insist else "")
        + "Keep numbers, code, file names, URLs and punctuation as they are. "
        "Reply with the translation only: no notes, no quotation marks, no explanation.\n\n"
        f"{source}"
    )


def tidy(source: str, out: str) -> str | None:
    """The model's answer cleaned up, or None when it is not a translation (empty, or far longer than the English: a
    model that explains itself instead of translating)."""
    got = re.sub(r"<think>.*?</think>", "", out or "", flags=re.DOTALL).strip()
    if "**" not in source:  # the model likes to bold a heading; the page did not
        got = got.replace("**", "")
    for mark in ("<|END_OF_TURN_TOKEN|>", "<|CHATBOT_TOKEN|>", "<|END_RESPONSE|>", "<|START_RESPONSE|>"):
        got = got.replace(mark, "")
    got = got.strip()
    if len(got) >= 2 and got[0] in "\"“«" and got[-1] in "\"”»" and source[:1] not in "\"“«":
        got = got[1:-1].strip()
    if not got:
        return None
    if len(got) > 6 * len(source) + 60:
        return None
    # words in, words out: "updated {0}" must not come back as "{0}"
    if re.search(r"[^\W\d_]", _PLACEHOLDER.sub("", source)) and not re.search(r"[^\W\d_]", _PLACEHOLDER.sub("", got)):
        return None
    return got


# ---- the model ----


def weights() -> str:
    """Where the translator's weights are: a folder or a Hub repo that can be opened now. Raises TranslatorMissing."""
    env = os.environ.get("THORP_TRANSLATOR", "").strip()
    if env:
        return env
    prepared = paths.data_dir() / PREPARED
    if (prepared / "config.json").is_file():
        return str(prepared)
    from thorp.onboard import downloads

    if downloads._cached(REPO):  # the weights, not just the config: a download half done is not here yet
        return REPO
    raise TranslatorMissing(
        "Tiny Aya Earth is not on this Mac yet (or its download is not finished). Fetch it from the onboarding page "
        "or run `uv run thorp translate prepare`. If that says the model is gated, accept Cohere's licence on "
        f"{MODEL_PAGE} with the Hugging Face account this Mac is signed in to."
    )


class TranslatorBusy(TranslatorMissing):
    """The weights are here but the Mac has not the memory to open them beside what it is running."""


def free_gb() -> float | None:
    """Memory the Mac could give now: the kernel's own available-memory level (what Activity Monitor's pressure graph and
    `memory_pressure` report: it counts what can be reclaimed, not only the pages nobody holds) times the RAM; MemAvailable
    on Linux; None where neither can be read."""
    try:
        if sys.platform == "darwin":
            import subprocess

            def sysctl(k: str) -> int:
                return int(subprocess.run(["sysctl", "-n", k], capture_output=True, text=True, timeout=5).stdout.strip())

            return sysctl("kern.memorystatus_level") / 100 * sysctl("hw.memsize") / 2**30
        with open("/proc/meminfo") as f:
            return int(re.search(r"MemAvailable:\s+(\d+) kB", f.read()).group(1)) / 2**20
    except Exception:  # noqa: BLE001
        return None


def weights_gb(where: str) -> float:
    """What opening these weights takes: a folder's safetensors, or the Hub copy's published size."""
    if os.path.isdir(where):
        return sum(f.stat().st_size for f in os.scandir(where) if f.name.endswith(".safetensors")) / 2**30
    return 6.7


class _Engine:
    """The loaded model. It stays loaded while the site speaks a language that needs it and is freed when the site goes
    back to English (`choose`): a clock that dropped it after some idle minutes made the next page wait for the load, and
    on a Mac this full the load could fail then. What the Mac cannot spare is said before the load, not found out by
    it (`load` checks free memory first and answers TranslatorBusy)."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.model = None
        self.tok = None
        self.where = ""
        self.warming = False

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        where = weights()
        if self.model is not None and self.where == where:
            return
        self.unload()
        need, free = weights_gb(where) + HEADROOM_GB, free_gb()
        if free is not None and free < need:
            raise TranslatorBusy(
                f"The translator needs about {need:.1f} GB free to open and this Mac has {free:.1f} GB. A voyage or a large "
                "model is holding the rest: it will open when they finish (or end a chat model in the console), then try again."
            )
        from mlx_lm import load

        try:
            self.model, self.tok = load(where)
        except Exception as e:  # noqa: BLE001
            self.model = self.tok = None
            raise TranslatorMissing(f"the translator ({where}) would not open: {str(e).splitlines()[0][:300]}") from e
        self.where = where

    def unload(self) -> None:
        self.model = self.tok = None
        self.where = ""
        try:
            import mlx.core as mx

            mx.clear_cache()
        except Exception:  # noqa: BLE001
            pass

    def warm(self) -> None:
        """Load in the background, so the first page after a language is chosen does not wait for the weights. A failure
        is not raised here: the first real request meets it and says why."""
        with self.lock:
            if self.model is not None or self.warming:
                return
            self.warming = True

        def go() -> None:
            try:
                with self.lock:
                    self.load()
            except TranslatorMissing:
                pass
            finally:
                self.warming = False

        threading.Thread(target=go, name="translator-warm", daemon=True).start()

    def run(self, prompts: list[str], budgets: list[int]) -> list[str]:
        """Each prompt answered alone, greedily, in batches. Order kept."""
        with self.lock:
            self.load()
            from mlx_lm.generate import batch_generate

            ids = [
                # enable_thinking is for a template that has a reasoning mode (a stand-in translator may); one that has
                # none ignores it. A translation is not reasoned out loud.
                self.tok.apply_chat_template(
                    [{"role": "user", "content": p}], add_generation_prompt=True, tokenize=True, enable_thinking=False
                )
                for p in prompts
            ]
            ids = [list(x["input_ids"]) if isinstance(x, dict) else list(x) for x in ids]
            out: list[str] = []
            for i in range(0, len(ids), BATCH):
                got = batch_generate(self.model, self.tok, ids[i : i + BATCH], max_tokens=budgets[i : i + BATCH])
                out.extend(got.texts)
            return out


ENGINE = _Engine()


def _budget(source: str) -> int:
    # a character is at most about a token in the scripts and agglutinative words this model writes; room for both
    return max(48, min(768, len(source) + 32))


def model_name() -> str:
    try:
        return weights()
    except TranslatorMissing:
        return REPO


def generate(code: str, sources: list[str]) -> dict[str, str]:
    """Translate English strings with the model (no store): {English: translation} for those it could. Raises
    TranslatorMissing when there is no model."""
    lang = language(code)
    if lang["is_source"]:
        return {}
    uniq = list(dict.fromkeys(s for s in sources if s))
    # a name on its own is not translated at all: "Nothing up my sleeve" stays "Nothing up my sleeve"
    out = {s: s for s in uniq if s.strip().lower() in {g.lower() for g in GLOSSARY}}
    # similar lengths together: a batch waits for its longest
    order = sorted((s for s in uniq if s not in out), key=len)
    got = ENGINE.run([prompt(lang, s) for s in order], [_budget(s) for s in order])
    again: list[str] = []
    for src, raw in zip(order, got, strict=True):
        t = tidy(src, raw)
        if t is not None and faithful(src, t):
            out[src] = t
        elif names_in(src) or placeholders(src):
            again.append(src)  # it changed a name or a placeholder: ask once more, insisting
    if again:
        for src, raw in zip(again, ENGINE.run([prompt(lang, s, insist=True) for s in again], [_budget(s) for s in again]), strict=True):
            t = tidy(src, raw)
            if t is not None and faithful(src, t):
                out[src] = t  # a sentence that still loses a name is left in English rather than kept wrong
    return out


def translate(code: str, sources: list[str]) -> dict:
    """The site's way in: translations for these English strings, from the store where kept and from the model where not.

    Returns {"translations": {English: translation}, "missed": [English...], "language": code, "model": ...}. Strings
    the model could not translate are `missed` (and not kept), so the page shows them in English and may ask again."""
    lang = language(code)
    if lang["is_source"]:
        return {"translations": {}, "missed": [], "language": lang["code"], "model": None}
    texts = [t.strip() for t in sources if isinstance(t, str) and t.strip()]
    texts = [t for t in dict.fromkeys(texts) if len(t) <= MAX_CHARS][:MAX_TEXTS]
    have = kept(lang["code"], texts)
    todo = [t for t in texts if t not in have]
    made: dict[str, str] = {}
    if todo:
        made = generate(lang["code"], todo)
        if made:
            keep(lang["code"], made, model_name())
    return {
        "translations": {**have, **made},
        "missed": [t for t in todo if t not in made],
        "language": lang["code"],
        "model": model_name() if todo else None,
    }


def status() -> dict:
    """What the site is speaking, and whether the translator can speak it now."""
    cur = current()
    try:
        where, why = weights(), None
    except TranslatorMissing as e:
        where, why = None, str(e)
    return {
        "language": cur,
        "translator": {"model": REPO, "weights": where, "ready": where is not None, "why": why, "loaded": ENGINE.loaded, "free_gb": free_gb()},
        "note": None if cur["listed"] else f"{cur['name']} is not named on Tiny Aya Earth's list of languages: expect it to be rougher.",
    }


# ---- what the page should translate (the same rule the browser applies, kept here so it is tested once) ----

_WORDS = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def worth_translating(s: str) -> bool:
    """Whether a piece of page text is prose or a label, not an identifier, a number, a path or code. The page asks about
    its text with the numbers already swapped for {0}, {1} ... (lib/siteLanguage.ts `templatise`), so "updated 12:20:12" is
    one string, "updated {0}", not one a second."""
    t = (s or "").strip()
    if not t or len(t) > MAX_CHARS or not _WORDS.search(t):
        return False
    if " " not in t:
        # a single token: a word is a label ("Queue"); an identifier is not (pg2600, 9m@v0.0.6, snake_case, a/path)
        return bool(re.fullmatch(r"[^\W\d_]{2,}[.:!?…]?", t, re.UNICODE))
    letters = sum(c.isalpha() for c in t)
    return letters >= 0.4 * len(t)


# ---- command line ----


def prepare(bits: int = 8) -> str:
    """Make the 8-bit MLX copy under data/ from the Hub weights (downloaded first if they are not cached)."""
    out = paths.data_dir() / PREPARED
    if (out / "config.json").is_file():
        return str(out)
    from mlx_lm import convert

    out.parent.mkdir(parents=True, exist_ok=True)
    convert(REPO, mlx_path=str(out), quantize=True, q_bits=bits, q_group_size=64)
    return str(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="thorp translate", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("languages")
    p = sub.add_parser("set")
    p.add_argument("code")
    p.add_argument("--by", default="Justin")
    p = sub.add_parser("say")
    p.add_argument("code")
    p.add_argument("text")
    sub.add_parser("prepare")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        st = status()
        c = st["language"]
        print(f"the site speaks {c['name']} ({c['native_name']}), chosen by {c['chosen_by']} at {c['chosen_at']}")
        t = st["translator"]
        print(f"translator {t['model']}: {'ready at ' + t['weights'] if t['ready'] else 'not here. ' + str(t['why'])}")
        if st["note"]:
            print(st["note"])
    elif a.cmd == "languages":
        for lang in languages():
            print(f"{lang['code']:<4}{lang['name']:<14}{lang['native_name']}{'' if lang['listed'] else '   (not on the card)'}")
    elif a.cmd == "set":
        c = choose(a.code, a.by)
        print(f"the site now speaks {c['name']} ({c['native_name']})")
    elif a.cmd == "say":
        r = translate(a.code, [a.text])
        print(r["translations"].get(a.text.strip()) or f"(not translated: {r['missed']})")
    elif a.cmd == "prepare":
        print(prepare())
    return 0


if __name__ == "__main__":
    sys.exit(main())
