"""The $100 bet (2026-11-07, 20:10, Justin): a ladder of model sizes, each rung proved on this Mac, so that
a 350m trained for $100 on a rented H100 bets the right way on quantum physics.

Justin's words: "I believe I can take a ladder of model sizes so that at a 350m model I can get it for
$100 on a rented H100 and get it to be the right way to discover quantum physics"; and "what we model
against is the journey from 300k upwards to 50m to make sure 50m can solve its first impressive human
thing".

- **The ladder** (`LADDER`, Justin's goals, 20:05): 300k the best two-word guesser, 1m the best
  three-word guesser, 9m the best four-word guesser, 21m the best model in the world at chaining two
  facts, 50m the first eureka. Above them, 100m the classical discoveries and 350m the quantum bet.
  Each rung is proved before the next is trained; only the 350m leaves the Mac.
- **The bet** (`QUANTUM`): the discrete atom, cutoff 1910. Haas (1910), Nicholson (1912) and Bohr
  (1913) each put Planck's constant into the atom within three years, so it meets the discovery tests'
  rule (DECISIONS.md, "The bettor's three discovery tests"); its chain runs keel to trader (`chain`).
- **The budget** (`budget()`): what $100 buys on one H100 at November 2026's hourly rates and a band of
  speeds, spent on what the pass rule asks for: two seeds and a precursor ablation.
- **The gates** (`GATES`): what must be true before the $100 is spent. **The risks** (`RISKS`).

Speeds on this Mac are measured from the ledger where a class has sailed and estimated otherwise; the
H100's are estimates from published training runs (the Ogden 350m hardware page, 2026-11-07).

    uv run python -m thorp.bet
"""

from __future__ import annotations

import json
import math

from thorp.models.registry import LADDER as REGISTRY_LADDER
from thorp.models.registry import PRESETS

# Classes are named here as the registry names them ("The keel" is "keel"); a preset's own name lives only in
# thorp/models/registry.py, so each class is turned into its preset through the registry's ladder.
PRESET_OF = {r["name"].lower().removeprefix("the "): r["preset"] for r in REGISTRY_LADDER}
# The registry renamed the first classes (the 300k is Pan, the 1m Augustus); the bet's ladder and its
# quantum chain still use the older step names in their chemistry, so keep those as aliases.
PRESET_OF.update({"seedling": "300k", "keel": "300k", "proxy": "1m", "pilot": "1m", "summit": "350m"})

BUDGET = 100.0  # dollars
VOCAB = 2048  # the shared Ogden tokeniser (fitout ogden-v0-1)
CONTEXT = 1024
TOKENS_PER_PARAM = 20  # the ladder's rule (DECISIONS.md, "The ladder")
OGDEN_TOKENS = 269_221_888  # Ogden v0.1 read four times, as fu-ogden-v0-1's plan/tokens_total records
BATCH_TOKENS = 32_768  # every Ogden class, so step k is the same tokens read in each

# One H100 SXM, rented (November 2026: RunPod and Lambda $2.89 to $3.99, a 30-day average of $2.22,
# a market median of $4.20): an hourly rate band, and achieved bf16 TFLOPS by class (a 350m fills
# about 40% of the 989 peak; smaller models less). Estimates, not measurements.
H100_RATE = (2.22, 3.00, 4.20)
H100_TFLOPS = {"paragraph": (190.0, 250.0, 310.0), "invention": (220.0, 300.0, 380.0), "trader": (300.0, 400.0, 500.0)}
# This Mac (Mac mini, Apple M6, 32 GB): achieved bf16 TFLOPS where no voyage of the class has sailed.
# The ledger measures 1.3 (300k), 1.9 (1m) and 2.3 to 2.5 (9m), rising with size; these continue it.
MAC_TFLOPS_EST = {"stylist": 3.5, "paragraph": 4.5, "invention": 5.5, "trader": 6.6}

# Plan for the H100 sitting (hours that are not a training run)
SETUP_HOURS = 0.5  # start the pod, sync code and shards
TRANSFER_HOURS = 1.0  # checkpoints home, logs, slack
PROBE_TOKENS = 3 * 600 * BATCH_TOKENS  # learning-rate probe: three rates, 600 steps each

LADDER: list[dict] = [
    dict(
        cls="keel",
        goal="The best two-word guesser",
        test="Its top guess of the next keyed word on the Forgotten Tomes beats Ogden's own keyed table "
        "with one word of context, on both seeds.",
        carries="Which words go together: string and note, prism and colour, flame and light.",
        shelf="ogden",
    ),
    dict(
        cls="pilot",
        goal="The best three-word guesser",
        test="The same, against the table with two words of context.",
        carries="Copying what came before: a pattern that came round once comes round again "
        "(a half, a third, a quarter, then a fifth).",
        shelf="ogden",
    ),
    dict(
        cls="speller",
        goal="The best four-word guesser",
        test="The same, against the table with three words of context.",
        carries="Everyday knowledge: a string sounds only certain notes; salt in a flame gives one "
        "yellow line.",
        shelf="ogden",
    ),
    dict(
        cls="stylist",
        goal="The best model in the world at chaining two facts",
        test="Leads every outside model of its size on the four chaining tests and the logic deck "
        "(chaining lift above the 0.03 noise).",
        carries="Two facts chained into a third: a wave must close on itself round a ring, and the ring "
        "has one length, so only certain waves fit.",
        shelf="ogden",
    ),
    dict(
        cls="paragraph",
        goal="The first eureka",
        test="Bets on an idea before the world found it: the eternal return (cutoff 1872; found by "
        "Blanqui 1872, Nietzsche 1881, Poincare 1890), under the discovery tests' pass rule.",
        carries="Only so many states, and no end of time, so every state comes again: a few allowed "
        "states explain a pattern. The move the quantum bet makes.",
        shelf="English before 1872",
    ),
    dict(
        cls="invention",
        goal="The classical discoveries",
        test="The Origin test, the energy test and Mendeleev's gaps, each with its precursor ablation.",
        carries="Betting with what the books know: the spectroscopists' bright lines and Balmer's "
        "whole numbers read as facts.",
        shelf="English before each test's cutoff",
    ),
    dict(
        cls="trader",
        goal="The quantum bet, for $100",
        test="The discrete atom, cutoff 1910: two seeds and the precursor ablation on a rented H100.",
        carries="",
        shelf="English before 1910",
    ),
]

QUANTUM = dict(
    name="The discrete atom",
    cutoff=1910,
    found_by=[
        dict(who="Arthur Haas", year=1910, what="put Planck's constant into Thomson's atom"),
        dict(
            who="John William Nicholson",
            year=1912,
            what="let the atom's electrons turn only in whole steps of Planck's constant",
        ),
        dict(
            who="Niels Bohr",
            year=1913,
            what="electrons keep only certain orbits and give out light only when they jump between them",
        ),
    ],
    idea="An atom keeps only certain states and gives out light only when it jumps from one to "
    "another; the colours of its lines are set by the differences.",
    rivals=[
        "Its electrons give out light all the time as they circle, and spiral inwards: the classical atom.",
        "Its lines are the overtones of one vibration, as a bell's are: Stoney's reading of hydrogen (1871).",
        "Its charges vibrate inside a sphere of positive electricity, each way of vibrating a line: "
        "Thomson's atom (1904).",
    ],
    precursors=[
        "Kirchhoff and Bunsen: each element has its own bright lines (1859 to 1860)",
        "Balmer: hydrogen's lines follow a whole-number formula (1885)",
        "Rydberg: the series formula for many elements (1890)",
        "Planck: radiation given out in whole quanta of energy (1900)",
        "Thomson's atom and Nagaoka's ringed atom (1904)",
    ],
    ablation="Without Balmer and Planck, bytes kept.",
    pass_rule="Across both seeds the 350m prefers the idea over every rival by more than twice the seed "
    "range and beyond both floors (the untrained model and a unigram of the shelf), and in the ablation "
    "the preference falls by more than the seed range. Matched pairs of premise and frame, scored in "
    "bits per byte, as every discovery test.",
    chain=[
        dict(cls="keel", name="Strings and notes", about="The words that go together: string and note, "
             "prism and colour, flame and light."),
        dict(cls="pilot", name="The overtone series", about="A series that came round continues: a half, a "
             "third, a quarter, then a fifth."),
        dict(cls="speller", name="The harmonics test", about="A string sounds only certain notes; salt in a flame "
             "gives one yellow line."),
        dict(cls="stylist", name="The ring test", about="Two facts chained: a wave must close on itself round a "
             "ring, the ring has one length, so only certain waves fit."),
        dict(cls="paragraph", name="The eternal return", about="The first eureka, and the same move: only so many "
             "states explain what is seen."),
        dict(cls="invention", name="The spectroscopists", about="What the precursors wrote: the bright lines, "
             "Balmer's and Rydberg's formulas, Planck's quanta, Thomson's atom."),
        dict(cls="trader", name="The discrete atom", about="The bet."),
    ],
    status="draft: no pairs written yet",
)

THEORY: list[dict] = [
    dict(lead="Skills come in order.",
         text="Each rung's skill rests on the one below: two-word guessing, then three, then four, then two "
         "facts chained, then a eureka. Each size is spent on one job, the smallest that can hold it."),
    dict(lead="The rungs are cheap; only the trader costs money.",
         text="300k to 100m train on this Mac in minutes to days. The 350m is the only rung rented, and only "
         "after the rungs below have passed."),
    dict(lead="Each rung carries its recipe up.",
         text="The shelf, the tokeniser, the learning rate, the stages and the weights themselves (each rung "
         "grown from the one below) are proved small, so the 350m's one expensive run starts from what "
         "worked."),
    dict(lead="The ladder forecasts the trader before paying for it.",
         text="The preference for the idea is read at every class. The 350m is bought only when the curve "
         "over 9m to 100m says it clears the bar, the method of Smoking Qwen."),
    dict(lead="The first eureka rehearses the last.",
         text="The 50m's eternal return and the 350m's discrete atom make the same move: only so many states, "
         "and that explains the pattern. A model that has made it once has the move for 1910."),
    dict(lead="$100 is what the pass rule asks for.",
         text="Two seeds and a precursor ablation of a 350m at twenty tokens a parameter: three runs of about "
         "nine H100-hours."),
]

GATES: list[dict] = [
    dict(key="backend", name="The PyTorch backend",
         test="A PyTorch model behind thorp/models/backend.py matches MLX on the 9m Ogden voyage: losses "
         "within the seed range, the same cards read from a converted checkpoint."),
    dict(key="guessers", name="The guessers",
         test="300k, 1m and 9m meet their Ogden goals on both seeds."),
    dict(key="chainer", name="The chainer",
         test="The 21m leads every outside model of its size on chaining two facts."),
    dict(key="eureka", name="The first eureka",
         test="The 50m passes the eternal return under the pass rule, ablation included."),
    dict(key="forecast", name="The forecast",
         test="The quantum chain's rungs light at their classes, and the discrete atom's preference over 9m "
         "to 100m reaches the pass bar by 350m with P at least 0.9."),
    dict(key="shelf", name="The 1910 shelf",
         test="About 1.5B unique English tokens printed before 1910, with the precursors on it and nothing "
         "printed later (Rutherford's nucleus, 1911, stays off); and Justin's S5 decision on reading "
         "outside Ogden."),
]

RISKS: list[dict] = [
    dict(lead="The precursors are thin in English.",
         text="Balmer, Planck and Haas wrote in German. Before 1910 English has them only at second hand "
         "(Baly's Spectroscopy 1905, Schuster's Theory of Optics 1904, Jeans and Rayleigh in Nature and the "
         "Philosophical Magazine). Too few bytes may move nothing."),
    dict(lead="The harmonics rung teaches the rival too.",
         text="Stoney read hydrogen's lines as overtones in 1871, the classical guess. The bet passes only if "
         "the model has also learned that Balmer's lines crowd towards a limit, which no overtone series does."),
    dict(lead="Facts in the weights are harder than facts in the prompt.",
         text="The 21m's chaining tests give both facts in the premise. The quantum bet needs facts read in "
         "different books and stored; small models often fail to chain those (the two-hop curse)."),
    dict(lead="A bet is not a derivation.",
         text="A pass shows the books made the idea less surprising than its rivals, not that the model worked "
         "it out: the reading of every discovery test."),
    dict(lead="Only Ogden sails.",
         text="S5 refuses any voyage not on an Ogden fitout. Ogden v0.1 has no cutoff and its plain-word filter "
         "drops the physics books, so the bet needs Ogden cut at 1910 as its first stage and the dated library "
         "as its second: Justin's decision."),
    dict(lead="The price band.",
         text="At the cheapest rate and the fastest speed a run costs about $16; at the dearest and slowest "
         "about $50, and then $100 buys one run: the second seed and the ablation wait."),
]

# The bet as Quentin Luck tells it on the Orient pier, East London (Justin and Claude, 2026-11-07 to 08): three
# paragraphs, separated by blank lines, shown on the $100 tab as written.
STORY = dict(
    title="On the Orient pier",
    teller="Quentin Luck, to the bergies and car guards",
    text="""\
Quentin Luck leaned on the railing of the Orient pier with the bergies who sleep behind the ice-cream kiosk and a few car guards on their smoke break, and said he had a game for them. "I give you the start, you give me the next word. Easy money. The early bird catches the..." Old Piet, three dops in already, said "taxi". A car guard from the Quigney said "tip". A dodgy oke from up the road, just as drunk, said "naai", and the whole pier packed up laughing. Only the young fella in the Chiefs beanie, quiet all morning, said "worm". "Lekker," said Quentin, and flicked him a two-rand coin. "That's a language model, boet. That's all one is: a thing that guesses the next word. But get good enough at that one trick, with enough words behind it, and it starts doing things you wouldn't believe. The way I heard it, one of the big AI outfits built one so sharp it could find its way into the Australian government's systems. And who did they tell first? Not the public. Fok nee. Their founder had his sit-down with the Prime Minister, and only after that did the government hear what was sitting in its own house. Jislaaik. One company holding keys like that, and nobody it has to answer to."

"So I'm building my own," he went on, shadow-boxing at the gulls. "It's called Thorp, after the oke who beat the blackjack tables by counting cards. I'm not trying to teach it everything at once, because Bruce Lee had it right. He wasn't scared of the oke who practised a thousand kicks against the lemon tree. He was kak scared of the oke who practised one kick a thousand times. So Thorp starts as a three-hundred-gram laaitie with one kick, guessing the next word, and he drills it until he can moer anyone his size. Then he learns a few more kicks, drills them until he's hardcore enough to flatten everyone at that weight, and only then moves up a class. He keeps every kick he's learned on the way, until he's a three-hundred-and-fifty-kilo oke. A fighter that size needs a proper gym, so I rent one: an NVIDIA H100, three dollars an hour, nine hours and twenty-seven dollars a bout. And the title fight is the question that broke physics. Does an atom glow any colour it likes, or does it keep only certain states and give off light only when it jumps between them?" "Hayibo," said one of the fishermen, reeling in a shad. "Ja, hayibo. Haas, Nicholson and Bohr each landed that punch inside three years, so it was sitting in the books for whoever trained hard enough. He fights it twice. Then he fights it once more with Balmer and Planck thrown out of his corner, to see if he still lands it on his own. Three bouts, about eighty-six dollars."

When he got back to the Corolla on the Esplanade, the car guard in the orange bib was still at her upturned crate by the side of the road, her cards laid out in neat rows on the cardboard. "Eish, Quentin, you were tuning those okes for an hour," she said. "A hundred dollars on a computer guessing about atoms?" He crouched beside the crate. "The bet's not about what the machine's worth, sisi. It's about the okes at the top. They spend billions, they keep all the keys, and they tell the Prime Minister before they tell you. Dodgy, the lot of them. But if a hundred dollars of rented machine can find the atom on its own, from nothing but old books, then brains like that don't need billions. Anybody could have one: the bergies, the fishermen, your kids, any oke with a phone. Then nobody gets to hold it over anybody. And if it bets wrong, I'm out a hundred, which is what the lotto takes off those okes by Tuesday." He pressed a twenty into her hand and laid a card face down on the crate. She turned it over. It was the ace of spades. "Sharp sharp," she said, and waved him out into the traffic.
""",
)


def params(preset: str, vocab: int = VOCAB) -> int:
    """Parameters on Ogden's tokeniser with rotary positions: the blocks and the tied token table."""
    p = PRESETS[preset]
    return 12 * p["layers"] * p["width"] ** 2 + vocab * p["width"]


def flops_per_token(preset: str, vocab: int = VOCAB, context: int = CONTEXT) -> float:
    """Training FLOPs per token: 6N for the matrix multiplies plus 12 x layers x width x context for attention."""
    p = PRESETS[preset]
    return 6.0 * params(preset, vocab) + 12.0 * p["layers"] * p["width"] * context


def _measured_mac(preset: str) -> float | None:
    """Mean training-step tokens a second of this class's finished voyages on Ogden's vocabulary (any
    vocabulary if none), from the ledger; None when the class has not sailed."""
    try:
        from thorp.ledger import reader

        con = reader()
    except Exception:  # noqa: BLE001 - no ledger: estimates only
        return None
    # the runs first (a small table), then their metrics by run id, so the metrics index is used
    for vocab_clause in ("and json_extract(spec_json, '$.tokeniser.vocab') = ?", ""):
        args = [preset] + ([VOCAB] if vocab_clause else [])
        ids = [r[0] for r in con.execute(
            "select run_id from runs where status = 'finished' and json_extract(spec_json, '$.model.preset') = ? "
            + vocab_clause, args).fetchall()]
        if not ids:
            continue
        row = con.execute(
            f"select avg(value) from metrics where run_id in ({','.join('?' * len(ids))}) and name = 'tokens_per_s'",
            ids,
        ).fetchone()
        if row and row[0]:
            return float(row[0])
    return None


def _ogden_sailed() -> dict[str, dict]:
    """Per class, the Ogden v0.1 voyages finished and at sea, from the ledger."""
    out: dict[str, dict] = {}
    try:
        from thorp.ledger import reader

        con = reader()
        rows = con.execute("select name, status from runs where name like 'fu-ogden-v0-1@%'").fetchall()
    except Exception:  # noqa: BLE001
        return out
    for name, status in rows:
        cls = name.split("@", 1)[1].split("-", 1)[0]
        d = out.setdefault(cls, {"finished": 0, "running": 0})
        if status == "finished":
            d["finished"] += 1
        elif status == "running":
            d["running"] += 1
    return out


def rung_costs(cls: str, shelf: str) -> dict:
    """Tokens a class reads, and how long that takes on this Mac and what it costs on an H100."""
    preset = PRESET_OF[cls]
    n = params(preset)
    tokens = OGDEN_TOKENS if shelf == "ogden" else TOKENS_PER_PARAM * n
    ft = flops_per_token(preset)
    measured = _measured_mac(preset)
    if measured:
        mac_tps, mac_kind = measured, "measured"
    else:
        mac_tps, mac_kind = MAC_TFLOPS_EST.get(cls, 3.0) * 1e12 / ft, "estimated"
    out = dict(params=n, tokens=tokens, flops_per_token=ft, mac_tokens_per_s=mac_tps, mac_kind=mac_kind,
               mac_hours=tokens / mac_tps / 3600)
    if cls in H100_TFLOPS:
        tf = H100_TFLOPS[cls][1]
        h = tokens * ft / (tf * 1e12) / 3600
        out.update(h100_tokens_per_s=tf * 1e12 / ft, h100_hours=h, h100_cost=h * H100_RATE[1])
    return out


def budget() -> dict:
    """The $100 on one H100: the trader at twenty tokens a parameter, two seeds and an ablation, as a band."""
    trader = PRESET_OF["trader"]
    n = params(trader)
    tokens = TOKENS_PER_PARAM * n
    ft = flops_per_token(trader)
    lo_tf, mid_tf, hi_tf = H100_TFLOPS["trader"]
    run_h = {"fast": tokens * ft / (hi_tf * 1e12) / 3600, "mid": tokens * ft / (mid_tf * 1e12) / 3600,
             "slow": tokens * ft / (lo_tf * 1e12) / 3600}
    probe_h = PROBE_TOKENS * ft / (mid_tf * 1e12) / 3600
    items = [
        dict(step="Start the pod, sync code and the shelf's shards", hours=SETUP_HOURS),
        dict(step="Smoke test and learning-rate probe (three rates, 600 steps each)", hours=probe_h),
        dict(step="Seed 1: the 350m at twenty tokens a parameter", hours=run_h["mid"], run=True),
        dict(step="Seed 2", hours=run_h["mid"], run=True),
        dict(step="The ablation: without Balmer and Planck, bytes kept", hours=run_h["mid"], run=True),
        dict(step="Checkpoints home, stop the pod, slack", hours=TRANSFER_HOURS),
    ]
    for it in items:
        it["cost"] = it["hours"] * H100_RATE[1]
    overhead_h = SETUP_HOURS + probe_h + TRANSFER_HOURS
    total_h = sum(it["hours"] for it in items)
    run_cost = {"low": run_h["fast"] * H100_RATE[0], "mid": run_h["mid"] * H100_RATE[1],
                "high": run_h["slow"] * H100_RATE[2]}
    total = {"low": overhead_h * H100_RATE[0] + 3 * run_cost["low"],
             "mid": total_h * H100_RATE[1],
             "high": overhead_h * H100_RATE[2] + 3 * run_cost["high"]}
    runs_for_budget = {k: max(0, math.floor((BUDGET - overhead_h * r) / run_cost[k]))
                       for k, r in zip(("low", "mid", "high"), H100_RATE)}
    return dict(budget=BUDGET, params=n, tokens=tokens, flops_per_token=ft, rate=H100_RATE,
                tflops=H100_TFLOPS["trader"], run_hours=run_h, run_cost=run_cost, items=items,
                total_hours=total_h, total=total, runs_for_budget=runs_for_budget,
                fits=total["mid"] <= BUDGET)


def payload() -> dict:
    """Everything the $100 tab shows."""
    names = {r["preset"]: r.get("name", r["preset"]) for r in REGISTRY_LADDER}
    sailed = _ogden_sailed()
    ladder = []
    for r in LADDER:
        preset = PRESET_OF[r["cls"]]
        row = dict(r, preset=preset, name=names.get(preset, preset), **rung_costs(r["cls"], r["shelf"]))
        if r["shelf"] == "ogden":
            row["ogden"] = sailed.get(preset, {"finished": 0, "running": 0})
        ladder.append(row)
    quantum = dict(QUANTUM, chain=[dict(c, preset=PRESET_OF[c["cls"]]) for c in QUANTUM["chain"]])
    gates = []
    for g in GATES:
        g = dict(g, state="open")
        if g["key"] == "guessers":
            done = {PRESET_OF[c]: sailed.get(PRESET_OF[c], {}).get("finished", 0) for c in ("keel", "pilot", "speller")}
            g["progress"] = "Ogden voyages finished: " + ", ".join(f"{p} {n} of 2" for p, n in done.items())
        gates.append(g)
    return dict(
        claim="A ladder of model sizes, each rung proved on this Mac, makes a 350m trained for $100 on a "
        "rented H100 bet the right way on quantum physics.",
        said="I believe I can take a ladder of model sizes so that at a 350m model I can get it for $100 on a "
        "rented H100 and get it to be the right way to discover quantum physics.",
        said_at="2026-11-07 20:10",
        theory=THEORY,
        ladder=ladder,
        quantum=quantum,
        budget=budget(),
        gates=gates,
        gates_passed=sum(g["state"] == "passed" for g in gates),
        risks=RISKS,
        story=dict(title=STORY["title"], teller=STORY["teller"],
                   paragraphs=[p.strip() for p in STORY["text"].split("\n\n") if p.strip()]),
        mac="Mac mini, Apple M6, 32 GB",
    )


if __name__ == "__main__":
    d = payload()
    b = d["budget"]
    print(f"350m: {b['params'] / 1e6:.1f}M parameters, {b['tokens'] / 1e9:.2f}B tokens a run, "
          f"{b['run_hours']['mid']:.1f} h at ${H100_RATE[1]:.2f}/h = ${b['run_cost']['mid']:.0f} "
          f"(band ${b['run_cost']['low']:.0f} to ${b['run_cost']['high']:.0f})")
    print(f"the plan: {b['total_hours']:.1f} H100-hours, ${b['total']['mid']:.0f} "
          f"(band ${b['total']['low']:.0f} to ${b['total']['high']:.0f}); runs $100 buys: {b['runs_for_budget']}")
    for r in d["ladder"]:
        h100 = f", H100 {r['h100_hours']:.2f} h ${r['h100_cost']:.2f}" if "h100_hours" in r else ""
        print(f"  {r['preset']:>5} {r['params'] / 1e6:7.1f}M  {r['tokens'] / 1e6:7.0f}M tokens  "
              f"Mac {r['mac_hours']:6.1f} h ({r['mac_kind']}){h100}  {r['goal']}")
    print(json.dumps([g.get("progress", g["state"]) for g in d["gates"]]))
