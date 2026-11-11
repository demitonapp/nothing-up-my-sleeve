"""The labs: who made each outside model, and what each lab's models do best and worst on Nothing up my sleeve's tests.

A **lab** (`Lab`) is the maker of a family of outside models (EleutherAI makes Pythia, Alibaba Qwen,
and so on), matched by the model's family name, since many checkpoints are re-hosted under
`mlx-community/` and the repo owner does not say who made them.

A lab's **best and worst** are its models' readings on every rung of the four chains
(the chain grades, s4.outside_readings), each set against the field: the other labs' models on the same test.
A reading's **standing** is its lift less the field's median, over the field's spread (its standard
deviation), so a test where every model scores 2.0 does not crowd out a test where the field scores
0.1; the five highest standings are the lab's best, the five lowest its worst.

    uv run python -m thorp.labs eleutherai     # one lab's best and worst, in plain text
"""

from __future__ import annotations

import re
import statistics
import sys
from dataclasses import dataclass

from thorp import fleet


@dataclass(frozen=True)
class Lab:
    key: str  # the address: #/leaderboard/lab/<key>
    name: str
    families: tuple[str, ...]  # the model families it makes, as they appear in model names
    url: str = ""
    # The Labs page (12 November 2026): the house's own profile, kept beside the family match so the
    # page, the leaderboard and the chat's lab picker all read one list. A house with no profile
    # still answers its lab page; only the ten featured houses wear a card.
    short: str = ""  # the name on the card, where it is longer than the lab key's name
    country: str = ""  # the flag key in frontend/public/flags
    country_name: str = ""
    hq: str = ""
    founded: str = ""
    site: str = ""  # the house's own door; url above stays its model org
    blurb: str = ""  # one sentence on what the house makes, in this world
    flagship: tuple[str, ...] = ()  # the models it had shipped by 12 November 2026

    def makes(self, model: str) -> bool:
        return any(re.search(f, model, re.I) for f in self.families)

    @property
    def door(self) -> str:
        """The link a card opens when it is not a lab page."""
        return self.site or self.url


LABS: tuple[Lab, ...] = (
    Lab("alibaba", "Alibaba", ("qwen",), "https://huggingface.co/Qwen",
        short="Alibaba · Qwen", country="cn", country_name="China", hq="Hangzhou",
        founded="2023", site="https://huggingface.co/Qwen",
        blurb="the red-sail house: Qwen, the open-weight family with a size for every deck, from 0.8B to the frontier.",
        flagship=("Qwen3.8 27B", "Qwen3.8 Flash", "Qwen3.5 0.8B")),
    Lab("meta", "Meta", ("llama", "muse"), "https://huggingface.co/meta-llama",
        short="Meta AI", country="us", country_name="United States", hq="Menlo Park",
        founded="2013", site="https://ai.meta.com",
        blurb="the ring house: Llama's open weights and the Muse Spark line behind Meta's consumer agent.",
        flagship=("Muse Spark 1.3", "Llama 4")),
    Lab("microsoft", "Microsoft", ("phi", r"^mai-", "microsoft/"), "https://huggingface.co/microsoft",
        short="Microsoft AI", country="us", country_name="United States", hq="Redmond",
        founded="2024", site="https://ai.microsoft.com",
        blurb="the paned house: the Phi line's small, sharp models, and the MAI foundation now on the stocks behind them.",
        flagship=("Phi-4 14B", "Phi-4 mini", "MAI-1")),
    Lab("eleutherai", "EleutherAI", ("pythia",), "https://huggingface.co/EleutherAI"),
    Lab("google", "Google", ("gemma", "gemini"), "https://huggingface.co/google",
        short="Google DeepMind", country="us", country_name="United States", hq="Mountain View",
        founded="2010", site="https://deepmind.google",
        blurb="the four-coloured house: the Gemini frontier and the open Gemma weights, the fleet the rest of the Reach is measured against.",
        flagship=("Gemini 4 Argon", "Gemma 4")),
    Lab("huggingface", "Hugging Face", ("smollm",), "https://huggingface.co/HuggingFaceTB"),
    # The six houses the Reach had not named by 12 November 2026. Each carries a profile now, so the
    # Labs page is one list and the lab pages fill as their models are pulled and read.
    Lab("openai", "OpenAI", ("gpt", "openai"), "https://openai.com",
        short="OpenAI", country="us", country_name="United States", hq="San Francisco",
        founded="2015", site="https://openai.com",
        blurb="the black house: the GPT-6 frontier and the open gpt-oss weights, the yard that set the pace the others answer.",
        flagship=("GPT-6 Astra", "GPT-6.1 Sol", "gpt-oss-20b")),
    Lab("anthropic", "Anthropic", ("claude", "anthropic"), "https://www.anthropic.com",
        short="Anthropic", country="us", country_name="United States", hq="San Francisco",
        founded="2021", site="https://www.anthropic.com",
        blurb="the cliff house: the Claude line, built for long context and careful work, from Fable down to Haiku.",
        flagship=("Claude Fable 5.1", "Claude Opus 5.5", "Claude Haiku 5.5")),
    Lab("deepseek", "DeepSeek", ("deepseek",), "https://www.deepseek.com",
        short="DeepSeek", country="cn", country_name="China", hq="Hangzhou",
        founded="2023", site="https://www.deepseek.com",
        blurb="the whale house: the V4 line, the open-weight challenge that made frontier reasoning cheap.",
        flagship=("DeepSeek V4 Pro", "DeepSeek V4 Flash")),
    Lab("antgroup", "Ant Group", (r"\bling", "ant-ling"), "https://www.ant-ling.com",
        short="Ant Group · Ling", country="cn", country_name="China", hq="Hangzhou",
        founded="2014", site="https://www.ant-ling.com",
        blurb="the silver-ring house: the Ling line, sparse MoE models built for a long context, tools and the work of agents.",
        flagship=("Ling-3.2-flash", "Ling-3.1-flash", "Ling-3.0-tiny")),
    Lab("mistral", "Mistral AI", ("mistral", "magistral", "codestral", "leanstral", "robostral"), "https://mistral.ai",
        short="Mistral AI", country="fr", country_name="France", hq="Paris",
        founded="2023", site="https://mistral.ai",
        blurb="the wind house: a European yard that turned from the general chase to narrow, sharp tools — OCR, search, lean reasoning.",
        flagship=("Mistral OCR 4", "Leanstral 1.5", "Robostral Navigate")),
    Lab("xai", "xAI", ("grok",), "https://x.ai",
        short="xAI", country="us", country_name="United States", hq="Palo Alto",
        founded="2023", site="https://x.ai",
        blurb="the black-X house: the Grok line on a 1.5T foundation, quick to the live conversation and the open wire.",
        flagship=("Grok 4.6", "Grok 4.5")),
)

# The ten houses the Labs page shows, in the order it shows them: the frontier, the open-weight yards
# and the two platform makers, by the reach of their releases on 12 November 2026. A reading, not a
# score; the Reach keeps the only scores. The rest of LABS (EleutherAI, Hugging Face) stays on the
# leaderboard and is named under the cards.
HOUSES: tuple[str, ...] = (
    "google",
    "openai",
    "anthropic",
    "meta",
    "alibaba",
    "microsoft",
    "deepseek",
    "antgroup",
    "mistral",
    "xai",
)
AS_OF = "2026-11-12"
TOP = 5


def lab_of(model: str) -> Lab | None:
    return next((lab for lab in LABS if lab.makes(model)), None)


def get(key: str) -> Lab | None:
    return next((lab for lab in LABS if lab.key == key.lower()), None)


def _grades() -> dict:
    from thorp.viable.s4_intelligence import readings

    return readings.chain_grades()


def _label(model: str) -> str:
    return fleet.COMPETITORS.get(model, (model.split("/")[-1], 0))[0]


def readings(models: dict | None = None) -> list[dict]:
    """Every (model, test) reading of a lab's model on a rung of the four chains."""
    models = _grades() if models is None else models
    names = {k: t.name for k, t in fleet.TRICKS.items()}
    rungs = [r.title for r in getattr(fleet, "RUNGS", ())]
    where = {}  # test -> (its chain's name, its rung's title)
    for c in fleet.chains():
        for i, k in enumerate(c):
            where[k] = (names.get(c[-1], c[-1]), rungs[i] if i < len(rungs) else None)
    out = []
    for model, v in models.items():
        lab = lab_of(model)
        if not lab:
            continue
        for test, x in v.items():
            if test not in where or not isinstance(x, dict) or x.get("lift") is None:
                continue
            out.append(
                {
                    "lab": lab.key,
                    "model": model,
                    "label": _label(model),
                    "test": test,
                    "name": names.get(test, test),
                    "chain": where[test][0],
                    "rung": where[test][1],
                    "lift": x["lift"],
                    "score": x.get("score"),
                    "performed": bool(x.get("performed")),
                }
            )
    return out


def standings(lab: Lab, rows: list[dict] | None = None) -> list[dict]:
    """The lab's readings, each with its standing against the other labs' models on the same test."""
    rows = readings() if rows is None else rows
    field: dict[str, list[float]] = {}
    for r in rows:
        if r["lab"] != lab.key:
            field.setdefault(r["test"], []).append(r["lift"])
    out = []
    for r in rows:
        f = field.get(r["test"], [])
        if r["lab"] != lab.key or len(f) < 2:
            continue
        med, sd = statistics.median(f), statistics.pstdev(f)
        out.append(
            {
                **r,
                "field_median": med,
                "field_n": len(f),
                "beats": sum(x < r["lift"] for x in f),
                "standing": (r["lift"] - med) / sd if sd > 0 else 0.0,
            }
        )
    return sorted(out, key=lambda r: -r["standing"])


def _profile(lab: Lab, rank: int | None = None) -> dict:
    """The card's facts, shared by the Labs index and one lab's own page."""
    return {
        "key": lab.key,
        "name": lab.name,
        "short": lab.short or lab.name,
        "rank": rank,
        "url": lab.url,
        "site": lab.door,
        "country": lab.country,
        "country_name": lab.country_name,
        "hq": lab.hq,
        "founded": lab.founded,
        "blurb": lab.blurb,
        "flagship": list(lab.flagship),
        "art": f"lab-{lab.key}" if lab.key in HOUSES else "",
        "families": list(lab.families),
    }


def houses() -> dict:
    """The Labs page (12 November 2026): the ten houses, each with its profile and what the Reach holds of
    it, then the other houses whose models the leaderboard keeps (EleutherAI's Pythias, Hugging Face's
    SmolLMs). The facts are the house's releases by AS_OF; the readings are the store's, as every lab page
    reads them."""
    graded = _grades()
    rows = readings(graded)
    out = []
    for rank, key in enumerate(HOUSES, 1):
        lab = get(key)
        if not lab:
            continue
        mine = [r for r in rows if r["lab"] == lab.key]
        read = sorted({r["label"] for r in mine})
        out.append({
            **_profile(lab, rank),
            "readings": len(mine),
            "models_read": len(read),
            "read": read,
        })
    next_houses = []
    for lab in LABS:
        if lab.key in HOUSES:
            continue
        mine = [r for r in rows if r["lab"] == lab.key]
        next_houses.append({
            **_profile(lab),
            "readings": len(mine),
            "models_read": len({r["label"] for r in mine}),
        })
    return {
        "as_of": AS_OF,
        "as_of_label": "12 November 2026",
        "houses": out,
        "next": next_houses,
    }


def payload(key: str) -> dict:
    lab = get(key)
    if not lab:
        raise LookupError(f"no lab {key}")
    models = _grades()
    s = standings(lab, readings(models))
    mine = [m for m in models if lab.makes(m)]
    try:  # the reference ladder's sizes (the competitors carry theirs in fleet.COMPETITORS)
        from thorp.smoking_qwen import REFERENCE_PARAMS as sizes
    except ImportError:
        sizes = {}
    rank = HOUSES.index(lab.key) + 1 if lab.key in HOUSES else None
    return {
        **_profile(lab, rank),
        "models": [
            {
                "model": m,
                "label": _label(m),
                "params": fleet.COMPETITORS.get(m, (None, None))[1] or sizes.get(m),
                "competitor": m in fleet.COMPETITORS,
                "ladder": m in fleet.REFERENCE_LADDER,
            }
            for m in mine
        ],
        "readings": len(s),
        "best": s[:TOP],
        "worst": s[::-1][:TOP] if len(s) > TOP else [],
        "labs": [{"key": x.key, "name": x.name} for x in LABS],
    }


def main() -> None:
    d = payload(sys.argv[1] if len(sys.argv) > 1 else "eleutherai")
    print(f"{d['name']}: {', '.join(m['label'] for m in d['models'])} ({d['readings']} readings)")
    for title, rows in (("best", d["best"]), ("worst", d["worst"])):
        print(f"\n{title}")
        for r in rows:
            print(
                f"  {r['standing']:+5.2f}σ  {r['label']:<18} {r['name']:<24} lift {r['lift']:+.3f}"
                f" (field {r['field_median']:+.3f})"
            )


if __name__ == "__main__":
    main()
