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
    # still answers its lab page; only the featured houses wear a card.
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

    @property
    def open_weights(self) -> bool:
        """Whether the house ships any open-weight line; the Labs view sorts on it."""
        return self.key not in CLOSED_WEIGHTS


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
    # Kimi joined the Reach on 12 November (Justin: "can you also add a house for kimi in masaq reach").
    Lab("moonshot", "Moonshot AI", ("kimi", "moonshot"), "https://www.moonshot.cn",
        short="Moonshot AI · Kimi", country="cn", country_name="China", hq="Beijing",
        founded="2023", site="https://www.moonshot.cn",
        blurb="the moon house: Kimi, the open-weight line that made long context and agentic work a public possession.",
        flagship=("Kimi K3.1 Pro", "Kimi K2.5")),
    # Z.ai (Zhipu AI) joined on the same day (Justin: "also add z.ai").
    Lab("zai", "Z.ai", ("glm", "zhipu", "z-ai"), "https://z.ai",
        short="Z.ai · GLM", country="cn", country_name="China", hq="Beijing",
        founded="2019", site="https://z.ai",
        blurb="the lantern house: GLM, the open-weight line that ships a fast, cheap model for every volume job.",
        flagship=("GLM-5.3 Flash", "GLM-5")),
    # The rest of the Reach's houses (12 November, Justin): MiniMax, Cohere, NVIDIA, StepFun, ByteDance,
    # Thinking Machines, TII, Cognition and Arcee. Their weights are open unless CLOSED_WEIGHTS says otherwise.
    Lab("minimax", "MiniMax", ("minimax", "hailuo"), "https://www.minimax.io",
        short="MiniMax", country="cn", country_name="China", hq="Shanghai",
        founded="2021", site="https://www.minimax.io",
        blurb="the twin-hull house: MiniMax, the open-weight line built for agents, and the Hailuo films that come with it.",
        flagship=("MiniMax-M2.5", "Hailuo 2.3")),
    Lab("cohere", "Cohere", ("command", "aya", "cohere"), "https://cohere.com",
        short="Cohere", country="ca", country_name="Canada", hq="Toronto",
        founded="2019", site="https://cohere.com",
        blurb="the north-shore house: Cohere, the enterprise line built for retrieval, ranking and the work inside a company's own walls.",
        flagship=("Command A", "Embed 4")),
    Lab("nvidia", "NVIDIA", ("nemotron", "nvidia"), "https://build.nvidia.com",
        short="NVIDIA", country="us", country_name="United States", hq="Santa Clara",
        founded="1993", site="https://build.nvidia.com",
        blurb="the forge house: Nemotron, the open model line built to run on the same silicon the fleet is trained on.",
        flagship=("Nemotron 3", "Llama Nemotron")),
    Lab("stepfun", "StepFun", ("stepfun", r"^step[- ]?\d"), "https://www.stepfun.com",
        short="StepFun", country="cn", country_name="China", hq="Shanghai",
        founded="2023", site="https://www.stepfun.com",
        blurb="the stair house: StepFun, the open-weight line that climbed from Step-3 to Step-5 and the agent work between.",
        flagship=("Step-5", "Step-3")),
    Lab("bytedance", "ByteDance", (r"\bseed", "doubao", "bytedance"), "https://seed.bytedance.com",
        short="ByteDance · Seed", country="cn", country_name="China", hq="Beijing",
        founded="2012", site="https://seed.bytedance.com",
        blurb="the seed house: ByteDance's Seed, the open Seed-OSS weights and the Doubao assistant behind them.",
        flagship=("Seed 2.0", "Seed-OSS-36B")),
    Lab("thinkingmachines", "Thinking Machines Lab", ("inkling", "thinking machines"), "https://thinkingmachines.ai",
        short="Thinking Machines", country="us", country_name="United States", hq="San Francisco",
        founded="2025", site="https://thinkingmachines.ai",
        blurb="the ink house: Thinking Machines' Inkling, the first open model from Mira Murati's lab.",
        flagship=("Inkling",)),
    Lab("tii", "Technology Innovation Institute", ("falcon", "tii"), "https://www.tii.ae",
        short="TII · Falcon", country="ae", country_name="United Arab Emirates", hq="Abu Dhabi",
        founded="2019", site="https://www.tii.ae",
        blurb="the falcon house: TII's Falcon, the open-weight line from Abu Dhabi that keeps a Gulf yard in the race.",
        flagship=("Falcon 3", "Falcon-H1")),
    Lab("cognition", "Cognition AI", ("swe-1", "devin", "cognition"), "https://cognition.ai",
        short="Cognition", country="us", country_name="United States", hq="San Francisco",
        founded="2023", site="https://cognition.ai",
        blurb="the agent house: Cognition's SWE-1.5 and Devin, built to do the software work rather than talk about it.",
        flagship=("SWE-1.5", "Devin")),
    Lab("arcee", "Arcee AI", ("arcee", r"\bafm", "fusion"), "https://www.arcee.ai",
        short="Arcee AI", country="us", country_name="United States", hq="New York",
        founded="2023", site="https://www.arcee.ai",
        blurb="the small-yard house: Arcee's AFM and Fusion, open models built by merging and training at the small end.",
        flagship=("Arcee Fusion", "AFM-4.5B")),
)

# A house is sorted with the open yards first (12 November, Justin: "the labs need to be sorted by whether
# they have open models or not"). A house that ships any open-weight line is open; the rest are closed.
CLOSED_WEIGHTS = {"anthropic", "xai", "cohere", "cognition"}

# The houses the Labs page shows, in the order it shows them: the frontier, the open-weight yards
# and the platform makers, by the reach of their releases on 12 November 2026. Kimi joined on the day. A reading, not a
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
    "moonshot",
    "zai",
    "minimax",
    "cohere",
    "nvidia",
    "stepfun",
    "bytedance",
    "thinkingmachines",
    "tii",
    "cognition",
    "arcee",
)
AS_OF = "2026-11-12"
TOP = 5

# How each house is funded (12 November, Justin: "each lab in its page needs to detail how much of it is
# government funded, supported vs private"). The split is an estimate from public reporting and company
# statements, not an audited cap table; `kind` says what the two sides are. Most houses are wholly private;
# TII is Abu Dhabi's, and Mistral and Cohere have a small public-research share beside private capital.
_PRIVATE = {
    "government": 0,
    "private": 100,
    "kind": "private",
    "note": "A private company: equity, debt and revenue, with no direct government equity or grant funding. Public-sector work is a customer, not a funder.",
    "basis": "Public reporting and company statements to 12 November 2026; an estimate, not an audited cap table.",
}
_PUBLIC = {
    "government": 0,
    "private": 100,
    "kind": "public company",
    "note": "A publicly listed company: no direct government equity. Public-sector contracts and industrial policy may help at the margin, but they are not funding of the lab.",
    "basis": "Public reporting and company filings to 12 November 2026; an estimate, not an audited cap table.",
}
FUNDING: dict[str, dict] = {key: dict(_PRIVATE) for key in HOUSES}
for _key in ("google", "microsoft", "meta", "nvidia", "alibaba"):
    FUNDING[_key] = dict(_PUBLIC)
FUNDING["tii"] = {
    "government": 100,
    "private": 0,
    "kind": "government",
    "note": "TII is part of Abu Dhabi's Advanced Technology Research Council: the emirate funds the institute and its Falcon programme directly.",
    "basis": "TII and Abu Dhabi government statements to 12 November 2026; an estimate, not an audited cap table.",
}
FUNDING["mistral"] = {
    "government": 10,
    "private": 90,
    "kind": "mostly private",
    "note": "Private venture capital and debt make up most of it; French state and EU research and compute programmes support a small share, not equity.",
    "basis": "Public reporting and company statements to 12 November 2026; an estimate, not an audited cap table.",
}
FUNDING["cohere"] = {
    "government": 20,
    "private": 80,
    "kind": "mixed",
    "note": "Mostly private capital, but Ottawa is investing up to $1.6B of the $7B Series E, a substantial public share; the company's equity remains private.",
    "basis": "Public reporting and company statements to 12 November 2026; an estimate, not an audited cap table.",
}

# The rounds, where they are public (12 November, Justin: "if the lab is funded, mention the funding rounds").
# Reported dates, sizes and valuations, not an exhaustive register; a public company gets its listing rather
# than a venture round, and a government institute gets its founding. `investors` is who led or is named.
ROUNDS: dict[str, list[dict]] = {
    "google": [{"date": "2004", "round": "IPO", "amount": "—", "valuation": "—", "investors": "Alphabet listed on Nasdaq; DeepMind acquired 2014"}],
    "microsoft": [{"date": "1986", "round": "IPO", "amount": "—", "valuation": "—", "investors": "Microsoft listed on Nasdaq"}],
    "meta": [{"date": "2012", "round": "IPO", "amount": "—", "valuation": "—", "investors": "Meta listed on Nasdaq; FAIR founded 2013"}],
    "nvidia": [{"date": "1999", "round": "IPO", "amount": "—", "valuation": "—", "investors": "NVIDIA listed on Nasdaq"}],
    "alibaba": [{"date": "2014", "round": "IPO", "amount": "—", "valuation": "—", "investors": "Alibaba listed on NYSE; Qwen funded internally"}],
    "tii": [{"date": "2019", "round": "Government founding", "amount": "—", "valuation": "—", "investors": "Abu Dhabi's Advanced Technology Research Council"}],
    "openai": [
        {"date": "2019-07", "round": "Microsoft investment", "amount": "$1B", "valuation": "—", "investors": "Microsoft"},
        {"date": "2023-01", "round": "Microsoft investment", "amount": "$10B", "valuation": "—", "investors": "Microsoft"},
        {"date": "2024-10", "round": "Funding round", "amount": "$6.6B", "valuation": "$157B post", "investors": "Thrive, SoftBank, NVIDIA, MGX"},
        {"date": "2025-03", "round": "Funding round", "amount": "$40B", "valuation": "$300B post", "investors": "SoftBank (lead)"},
    ],
    "anthropic": [
        {"date": "2021-05", "round": "Series A", "amount": "$124M", "valuation": "—", "investors": "Dustin Moskovitz, Jaan Tallinn, Eric Schmidt"},
        {"date": "2022-04", "round": "Series B", "amount": "$580M", "valuation": "—", "investors": "FTX, Sam Bankman-Fried, Jaan Tallinn"},
        {"date": "2023-05", "round": "Series C", "amount": "$450M", "valuation": "—", "investors": "Spark Capital (lead), Google, Salesforce"},
        {"date": "2024-03", "round": "Series D", "amount": "$750M", "valuation": "—", "investors": "Menlo Ventures, Google, Salesforce"},
        {"date": "2025-03", "round": "Series E", "amount": "$3.5B", "valuation": "$61.5B post", "investors": "Lightspeed, General Catalyst, Salesforce"},
        {"date": "2025-09", "round": "Series F", "amount": "$13B", "valuation": "$183B post", "investors": "ICONIQ, Fidelity, MGX"},
        {"date": "2026", "round": "Series G", "amount": "$30B", "valuation": "$380B post", "investors": "GIC, Coatue (lead); D.E. Shaw, Dragoneer, Founders Fund, ICONIQ, MGX"},
    ],
    "antgroup": [
        {"date": "2015-07", "round": "Series A", "amount": "undisclosed", "valuation": "~$45B", "investors": "state-owned funds, insurers and private investors"},
        {"date": "2016-04", "round": "Series B", "amount": "$4.5B", "valuation": "~$60B", "investors": "China Investment Corporation, CCB, China Life and others"},
        {"date": "2018-06", "round": "Series C", "amount": "$14B", "valuation": "~$150B", "investors": "GIC, Temasek, Khazanah, CPPIB and others; IPO suspended 2020"},
    ],
    "xai": [
        {"date": "2024-05", "round": "Series B", "amount": "$6B", "valuation": "$24B post", "investors": "Andreessen Horowitz, Sequoia, Fidelity, Valor"},
        {"date": "2026-01", "round": "Series E", "amount": "$20B", "valuation": "—", "investors": "Valor, StepStone, Fidelity, QIA, MGX, Baron; NVIDIA, Cisco"},
    ],
    "mistral": [
        {"date": "2023-06", "round": "Seed", "amount": "€105M", "valuation": "—", "investors": "Lightspeed, Xavier Niel, Rodolphe Saadé"},
        {"date": "2023-12", "round": "Series A", "amount": "€385M", "valuation": "—", "investors": "Andreessen Horowitz (lead), General Catalyst, Lightspeed"},
        {"date": "2024-06", "round": "Series B", "amount": "€600M", "valuation": "€5.8B", "investors": "General Catalyst (lead), Lightspeed, Andreessen Horowitz"},
        {"date": "2025-09", "round": "Series C", "amount": "€1.7B", "valuation": "€11.7B", "investors": "ASML (lead), DST, Bpifrance, NVIDIA"},
        {"date": "2026", "round": "Series D", "amount": "€3B", "valuation": "€21B", "investors": "ASML, Bpifrance and others"},
    ],
    "moonshot": [
        {"date": "2024-02", "round": "Funding round", "amount": "$1B", "valuation": "—", "investors": "Alibaba, HongShan, Tencent"},
        {"date": "2026-06", "round": "Funding round", "amount": "$2B", "valuation": "$50B", "investors": "reported; HongShan and others"},
        {"date": "2026-09", "round": "HK IPO filing", "amount": "~$3B sought", "valuation": "$50B", "investors": "confidential A1 filed with HKEX"},
    ],
    "zai": [
        {"date": "2026-01", "round": "HKEX IPO", "amount": "—", "valuation": "—", "investors": "listed as SEHK: 2513"},
        {"date": "2026-07", "round": "Share placement", "amount": "$4B", "valuation": "—", "investors": "public markets"},
        {"date": "2026-09", "round": "Funding round", "amount": "$5B", "valuation": "—", "investors": "reported"},
    ],
    "minimax": [
        {"date": "2021–24", "round": "Private rounds", "amount": "7 rounds", "valuation": "—", "investors": "Sequoia China, IDG, Gaorong and others"},
        {"date": "2026", "round": "HKEX IPO", "amount": "—", "valuation": "—", "investors": "listed as 0100.HK; A-share IPO preparation started May 2026"},
    ],
    "cohere": [
        {"date": "2021-09", "round": "Series A", "amount": "$40M", "valuation": "—", "investors": "Index Ventures, Radical Ventures"},
        {"date": "2022-02", "round": "Series B", "amount": "$125M", "valuation": "—", "investors": "Tiger Global, Index, Radical"},
        {"date": "2023-06", "round": "Series C", "amount": "$270M", "valuation": "—", "investors": "Inovia, Oracle, NVIDIA, Salesforce"},
        {"date": "2024-06", "round": "Series D", "amount": "$500M", "valuation": "$5.5B", "investors": "PSP Investments, Cisco, AMD, NVIDIA"},
        {"date": "2026", "round": "Series E", "amount": "$7B", "valuation": "$35.7B", "investors": "Ottawa up to $1.6B; other investors reported"},
    ],
    "deepseek": [
        {"date": "2026-10", "round": "Funding round", "amount": "~$15B", "valuation": "—", "investors": "Tencent, CATL; state-backed funds reported among interested investors"},
    ],
    "stepfun": [
        {"date": "2026", "round": "HK IPO filing", "amount": "—", "valuation": "$12B reported", "investors": "confidential filing reported"},
    ],
    "bytedance": [
        {"date": "2012–21", "round": "Private rounds", "amount": "—", "valuation": "~$300B", "investors": "Sequoia, KKR, General Atlantic and others; no new round in 2026"},
    ],
    "thinkingmachines": [
        {"date": "2025-07", "round": "Seed", "amount": "$2B", "valuation": "$12B", "investors": "Andreessen Horowitz, NVIDIA, Accel and others"},
    ],
    "cognition": [
        {"date": "2024-03", "round": "Series A", "amount": "$21M", "valuation": "$350M", "investors": "Founders Fund (lead), Pear VC"},
        {"date": "2024-04", "round": "Series A extension", "amount": "$175M", "valuation": "$2B", "investors": "Founders Fund (lead), Khosla, 8VC"},
        {"date": "2025-03", "round": "Series B", "amount": "$300M", "valuation": "$4B", "investors": "8VC, Lux (co-lead), Founders Fund"},
        {"date": "2025-09", "round": "Series C", "amount": "$400M", "valuation": "$10.2B", "investors": "Founders Fund (lead), Bain Capital Ventures"},
        {"date": "2026-05", "round": "Series D", "amount": "$1B", "valuation": "$26B", "investors": "Lux, General Catalyst, 8VC (co-lead)"},
        {"date": "2026-09", "round": "Series E", "amount": "$2B", "valuation": "$48B", "investors": "Accel, Andreessen Horowitz (co-lead)"},
    ],
    "arcee": [
        {"date": "2024–25", "round": "Private rounds", "amount": "undisclosed", "valuation": "—", "investors": "no disclosed lead"},
    ],
}
for _key, _rows in ROUNDS.items():
    FUNDING[_key]["rounds"] = _rows
for _key in FUNDING:
    FUNDING[_key].setdefault("rounds", [])

# What the American houses spend on lobbying Washington, and how much of their revenue is the US government
# (12 November, Justin: "for the masaq hubs for the US, in their overview page can you add how much they
# spend on government lobbying and how much of their revenue is garnered from the US government").
# `lobbying` is the federal Lobbying Disclosure Act total for calendar 2025 in US dollars, as compiled by
# Bloomberg Government and relayed by Axios and others; None where no figure was found. `gov_revenue_pct` is
# the share of revenue from the US government, None where the company does not break it out (most do not):
# the two lab figures are unverified press estimates and say so. Estimates from public reporting, not audits.
_GOV_BASIS = "Lobbying: federal disclosures for 2025 as compiled by Bloomberg Government and reported by Axios (approximate). Revenue share: companies rarely break it out; a blank means not disclosed."
GOV: dict[str, dict] = {
    "meta": {"lobbying": 26_290_000, "gov_revenue_pct": None,
             "note": "The largest federal lobbying spend of any company in 2025. Revenue is almost wholly advertising; government is not a reported line."},
    "google": {"lobbying": 13_100_000, "gov_revenue_pct": None,
               "note": "Alphabet's figure. Google Cloud sells to federal agencies, but Alphabet does not break out government revenue."},
    "microsoft": {"lobbying": 9_360_000, "gov_revenue_pct": None,
                  "note": "Federal contracts are a large customer line across Azure and Office, but Microsoft does not disclose the share of revenue."},
    "nvidia": {"lobbying": 4_900_000, "gov_revenue_pct": None,
               "note": "About seven times its 2024 spend, mostly on export controls. Its filings do not break out US-government revenue."},
    "openai": {"lobbying": 3_000_000, "gov_revenue_pct": 5,
               "note": "Up from $1.76M in 2024. The ~5% revenue share is a press estimate, not a company figure."},
    "anthropic": {"lobbying": 3_100_000, "gov_revenue_pct": 2,
                  "note": "Up from $720K in 2024. The ~2% revenue share is a press estimate, not a company figure."},
    "xai": {"lobbying": None, "gov_revenue_pct": None, "note": "No federal lobbying total found for 2025."},
    "thinkingmachines": {"lobbying": None, "gov_revenue_pct": None, "note": "No federal lobbying total found for 2025."},
    "cognition": {"lobbying": None, "gov_revenue_pct": None, "note": "No federal lobbying total found for 2025."},
    "arcee": {"lobbying": None, "gov_revenue_pct": None, "note": "No federal lobbying total found for 2025."},
}
for _row in GOV.values():
    _row["year"] = 2025
    _row["basis"] = _GOV_BASIS

# The purpose a house is filtered by on the Labs page (12 November, Justin: "the sorting for labs should not
# only be about open weights, but we should be able to filter by country and purpose"). One primary purpose
# each; the prose purpose is in PROFILES.
FOCUS: dict[str, str] = {
    "google": "frontier",
    "openai": "frontier",
    "anthropic": "frontier",
    "meta": "frontier",
    "xai": "frontier",
    "alibaba": "open fleet",
    "microsoft": "open fleet",
    "deepseek": "open fleet",
    "antgroup": "open fleet",
    "moonshot": "open fleet",
    "zai": "open fleet",
    "nvidia": "open fleet",
    "bytedance": "open fleet",
    "arcee": "open fleet",
    "mistral": "enterprise",
    "cohere": "enterprise",
    "minimax": "agents",
    "stepfun": "agents",
    "cognition": "agents",
    "thinkingmachines": "research",
    "tii": "research",
}

# The lab page's two paragraphs (12 November, Justin: "each lab will have their own page with a description of
# them, their purpose and all their ships"). The card's one-line blurb stays above; these are the house's
# longer description and what it is for, kept here so the page and any future surface read one text.
PROFILES: dict[str, dict[str, str]] = {
    "google": {
        "description": "Google DeepMind is the London-and-Mountain-View research house behind Gemini. It keeps two fleets: the closed Gemini line at the frontier, and the open Gemma weights that put a capable model on a small deck.",
        "purpose": "to put the frontier in every product it owns, and a small open model in every hand that wants one.",
    },
    "openai": {
        "description": "OpenAI is the San Francisco house that made the GPT line the weather every other yard answers. Its frontier is closed; its gpt-oss weights are open, and its models are the ones the Reach is most often measured against.",
        "purpose": "to build general models and put them in front of as many people as it can, at the frontier and at the small end.",
    },
    "anthropic": {
        "description": "Anthropic is the San Francisco safety house behind Claude. It builds for long context, careful reasoning and work that runs for hours, and sells the same line from Fable down to Haiku.",
        "purpose": "to make models that can be trusted with long, consequential work.",
    },
    "meta": {
        "description": "Meta AI is the Menlo Park house whose Llama weights made open models a serious fleet, and whose Muse Spark line now sits behind Meta's consumer agent.",
        "purpose": "to put AI in the hands of its own billion users, and open weights in everyone else's.",
    },
    "alibaba": {
        "description": "Alibaba's Qwen is the Hangzhou house that ships a model at almost every size, from a 0.8B pinnace to the frontier, and releases the weights. It is the yard most of the Reach's small fleet came from.",
        "purpose": "to make one open family that fits every deck, and to win the cloud that runs it.",
    },
    "microsoft": {
        "description": "Microsoft AI is the Redmond house behind the Phi line: small, sharp models built to run cheaply, and the MAI foundation now being trained behind them.",
        "purpose": "to make small models that do a great deal, and to own the stack they run on.",
    },
    "deepseek": {
        "description": "DeepSeek is the Hangzhou house whose V4 line made frontier reasoning cheap and open. It publishes weights and prices that the rest of the field has had to answer.",
        "purpose": "to prove that a small, focused yard can build at the frontier and give the weights away.",
    },
    "antgroup": {
        "description": "Ant Group is the Hangzhou house behind Alipay and the Ling line. Ling is a sparse MoE family built for long context, tools and the work of agents, and its newest flash models are built to be the fast execution node in a larger system.",
        "purpose": "to make models that can run the everyday work of agents at a price that scales.",
    },
    "mistral": {
        "description": "Mistral AI is the Paris house that began as Europe's answer in the general chase and then turned to narrow, sharp tools: OCR, search, lean reasoning and robotics.",
        "purpose": "to build European models that do a few things well, and to keep the continent in the race.",
    },
    "xai": {
        "description": "xAI is the Palo Alto house behind Grok, trained on a 1.5T foundation and wired to the live conversation. It is the newest of the houses and the most willing to answer in public.",
        "purpose": "to build a model that knows what is happening now, and to put it where the conversation is.",
    },
    "moonshot": {
        "description": "Moonshot AI is the Beijing house behind Kimi, the open-weight line that has made long context, tool use and agentic work a public possession. Its K3.1 Pro flagship was released open-weight in November 2026.",
        "purpose": "to build an open model that can do a long, hard job from end to end, and to keep the weights public.",
    },
    "zai": {
        "description": "Z.ai, the house formerly called Zhipu AI, is the Beijing yard behind GLM. It ships an open-weight model at every price, and its GLM-5.3 Flash has been the cheap, fast choice for volume work since August 2026.",
        "purpose": "to make a fast, open model that any team can afford to run at volume.",
    },
    "minimax": {
        "description": "MiniMax is the Shanghai house that builds text, video and audio models as one family. Its M2.5 is an open-weight agent model, and Hailuo is its film-making line.",
        "purpose": "to make an open model that can act in the world, and the media tools that go with it.",
    },
    "cohere": {
        "description": "Cohere is the Toronto house that builds for the enterprise: command models, embeddings and rerankers that run inside a customer's own walls. Its Command A line is closed, while its Aya research family is open.",
        "purpose": "to make retrieval and generation that a company can keep private, with an open research line beside it.",
    },
    "nvidia": {
        "description": "NVIDIA is the Santa Clara house that builds the silicon and the open Nemotron models that run on it. Its Nemotron 3 line is built for reasoning, retrieval and agents.",
        "purpose": "to make open models that show what its hardware can do.",
    },
    "stepfun": {
        "description": "StepFun is the Shanghai house that built Step-3 and then Step-5, an open-weight line aimed at agentic work. It ships weights and a platform together.",
        "purpose": "to climb the agent ladder in the open, one step at a time.",
    },
    "bytedance": {
        "description": "ByteDance's Seed is the Beijing research yard behind the Doubao assistant and the open Seed-OSS weights. It builds for a billion users and publishes a small piece of the fleet.",
        "purpose": "to put a capable model in front of its own users, and a smaller open one in front of everyone else.",
    },
    "thinkingmachines": {
        "description": "Thinking Machines Lab is the San Francisco house founded by Mira Murati. Its first model, Inkling, is open-weight and built for custom, per-team training rather than one model for everyone.",
        "purpose": "to make models that a team can shape for its own work, and to keep them open.",
    },
    "tii": {
        "description": "The Technology Innovation Institute is Abu Dhabi's research house, and Falcon is its open-weight line. Falcon 3 and Falcon-H1 keep a Gulf yard in the open fleet.",
        "purpose": "to build a sovereign open model, and to prove the Gulf can train its own.",
    },
    "cognition": {
        "description": "Cognition is the San Francisco house behind Devin, the software agent, and SWE-1.5, the fast model trained for it. Its models are closed and sold as an agent.",
        "purpose": "to make an agent that ships code, not a chat that describes it.",
    },
    "arcee": {
        "description": "Arcee AI is the New York house that builds small open models by merging and training at the small end. Its AFM and Fusion lines are made to run on a single deck.",
        "purpose": "to make a small open model that punches above its weight.",
    },
}


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
    """The card's facts, shared by the Labs index and one lab's own page; the lab page's two paragraphs
    come from PROFILES so the card stays one line and the page can say more."""
    profile = PROFILES.get(lab.key, {})
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
        "open": lab.open_weights,
        "focus": FOCUS.get(lab.key, "research"),
        "funding": FUNDING.get(lab.key, _PRIVATE),
        "gov": GOV.get(lab.key) if lab.country == "us" else None,
        "description": profile.get("description", ""),
        "purpose": profile.get("purpose", ""),
        "flagship": list(lab.flagship),
        "art": f"lab-{lab.key}" if lab.key in HOUSES else "",
        "families": list(lab.families),
    }


def houses() -> dict:
    """The Labs page (12 November 2026): the houses, each with its profile and what the Reach holds of
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
    # Every ship of this house the Reach knows, read or not: the foreign registry is the list the harbour
    # draws, so the lab page can show the whole fleet, not only the models with a chain reading.
    from thorp import foreign as foreign_registry

    reach_ships, seen = [], set()
    for x in foreign_registry.models():
        k = x.get("key")
        if x.get("lab") != lab.key or not k or k in seen:
            continue
        seen.add(k)
        reach_ships.append({
            "key": k,
            "model": x.get("model"),
            "label": x.get("label") or _label(x.get("model") or k),
            "params": x.get("params"),
            "read": bool(x.get("read")),
            "chained": bool(x.get("chained")),
        })
    rank = HOUSES.index(lab.key) + 1 if lab.key in HOUSES else None
    return {
        **_profile(lab, rank),
        "fleet": reach_ships,
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
