"""S5: the charter's terms, the rules a voyage on a rented GPU sails under (2026-11-08, Justin: "i'm going to use
vast.ai can you build the code via the Liberty Machine system in order to leverage vast.ai").

A chartered voyage sails on a GPU hired from Vast.ai's marketplace instead of this Mac's: the same spec, on the
torch backend (thorp/train_torch.py), its rows and checkpoints brought home to the ledger. The terms are S5's: which
GPUs may be hired and at what ceiling an hour, from what kind of host, how much one voyage and one week may cost,
how many ships may be hired at once. The money is Justin's, so every number here is his to set: he adopted the
defaults as proposed (2026-11-08, "Adopt as proposed"; DECISIONS.md, "The charter"), and a change to any of them is
a row in s5.charter_terms (the latest per term in force, every change kept, in whose words):

    uv run thorp charter term weekly_budget 40 --words "Justin, 8 November: ..."
    uv run thorp charter term gpus '{"RTX 4090": 0.45, "RTX 5090": 0.70}' --words "..."

The policy that holds a voyage to these terms is liberty_machine.POLICIES["charter"] (checked by S3, thorp/viable/s3_control/
charter.py); the rest of the charter is S1 (thorp/viable/s1_operations/charter.py: the voyage), S2 (s2_coordination/
charter.py: one charter at a time, the ledger brought home), S3* (s3star_audit/charter.py: nothing hired is
forgotten) and S4 (s4_intelligence/market.py: the market read).
"""

from __future__ import annotations

import json

ADOPTED = "2026-11-08, Justin (Vast.ai chosen; the terms adopted as proposed)"

DEFAULTS: dict = {
    # the GPU classes that may be hired, by Vast.ai's gpu_name, each with its ceiling in dollars an hour
    # (the market in November 2026: a 4090 from about $0.20 to $0.50, a 5090 $0.40 to $0.65, an H100 $1.90 to
    # $2.40 on verified hosts)
    "gpus": {"RTX 4090": 0.50, "RTX 5090": 0.75, "H100 SXM": 2.60, "H100 PCIE": 2.30},
    # the host: datacenter-verified only (unverified hosts run 20-40% over their sticker, verified 3-13%),
    # reliable, with a fast enough line to carry the library up and the checkpoints home
    "verified": True,
    "min_reliability": 0.98,
    "min_inet_down_mbps": 200,
    "min_inet_up_mbps": 100,
    # a floor only: the charter hires no host whose driver is older than the CUDA the lock's torch is built
    # against (s1 vast.required_cuda: 13.2 for torch 2.15's wheels on 12 November, when this still said 12.8)
    "min_cuda": 12.8,
    "disk_gb": 80,
    "image": "pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime",
    # the prebuilt box image (backend/box/Dockerfile, built on GitHub when the lock changes): the charter hires
    # `<this>:lock-<the lock's hash>` when it is published, so a box arrives with torch aboard; else `image` above
    # and the whole environment synced on the box. Empty turns it off.
    "box_image": "ghcr.io/demitonapp/thorp-box",
    # the money: one voyage's quote, the week's spend (Monday to Sunday, UTC), and the credit kept in hand
    "voyage_budget": 10.0,
    "weekly_budget": 30.0,
    "credit_margin": 1.25,  # the account's credit must cover the quote this many times over
    # how long a hired ship may stay out: the quote's hours times this, then it is brought home and released
    "overrun": 1.5,
    "max_instances": 1,  # ships hired at once (S2)
    # the purser, S3's allocation of the backlog between local and foreign waters (DECISIONS.md, "The purser",
    # 8 November, Justin: "Accept all five"; built 12 November). `off` calls nothing; `advisory` writes its call
    # beside each line (s3.allocations, the queue page) and routes nothing, so `vast:` lines still decide;
    # `routing` sails the lines it calls foreign on the Vast lane. Advisory for a week first, as decided.
    "purser": "advisory",
    # the expeditions whose voyages may sail abroad: a comparison is kept in one set of waters (a torch voyage
    # starts from other random weights), so every other expedition is local until Justin says
    "foreign_expeditions": ["table_talk"],
    # the smallest size the purser may send abroad (a preset of models.registry.PRESETS; empty: any). 12 November,
    # Justin: "don't send lines to 4090 for 300k and 1m, only send 9m and up to vast": the 4090 ran a 300k at 0.46
    # of this Mac's speed. A line pinned `vast:` still sails abroad: the pin is a person's decision, not the purser's.
    "foreign_min_preset": "",
    # the biggest size this Mac's lane runs (a preset of models.registry.PRESETS; empty: no ceiling). 13 November,
    # Justin, of proposal #27: "we have a fixed reserve and anything 21m and up goes to vast". A voyage above it is a
    # Vast voyage whatever its expedition (the coordinator's parse, s2 lanes.mac_ceiling), within the money terms
    # above; a line a person pins with `mac:` is the one way to sail it here. The purser's two terms above are the
    # other direction (what it may send abroad); this is what may not stay.
    "mac_max_preset": "",
    # the memory the Mac lane keeps free for models under 8B (the site's translator, the console's small models), in GB.
    # Same decision. It is a number S5 holds and the pages show: what enforces it today is `mac_max_preset`, since no
    # voyage's footprint has been measured to hold a line against it (proposal #27 asked for that measurement first).
    "mac_reserve_gb": 0.0,
    # a hire only when it brings the voyage home at least this much sooner, in hours and as a share of its wait
    "margin_hours": 1.0,
    "margin_fraction": 0.25,
    # the queue's planning cycle (12 November, Justin: "the optimal way to schedule the queue every 12 hours to
    # maximise speed and maintain the cost ceilings"): every this many hours S3* closes the last cycle's books,
    # S4 folds in what was measured, and the purser plans the next. The week's budget is released a cycle at a
    # time (what is left over the cycles left), so no cycle can spend the rest of the week's money.
    "cycle_hours": 12.0,
    # how the week's budget is released (12 November, Justin: "the daily limit on vast is overkill, i prefer just
    # the weekly limit"): `week`, the whole of what is left of the week may be spent in any cycle, so the only
    # ceiling is `weekly_budget` (with `voyage_budget` and the overrun reserve); `cycle`, what is left spread over
    # the cycles left in the week, as it was built. The cycle still plans every `cycle_hours`; only the money changes.
    "budget_release": "week",
    # the breaker (S2): this many fit-outs failing in a row on a charter lane pauses it, so a dead hour is not
    # repeated down the queue. A box that fails before its voyage sails is retried abroad, not sailed here.
    "box_failures_before_pause": 2,
    # S4's intelligence audit (the judge, Qwen3.8 27B, and a turn of the cycle) is queued at the top of the Mac lane
    # after this many lines have ended, so the 15 GB model has the Mac to itself; 0 never queues it
    "intelligence_audit_every": 5,
}

PURSER_MODES = ("off", "advisory", "routing")

# S4's starting guess of what each class delivers on a small GPT (bf16, effective TFLOP/s, about 30 to 40% of the
# card's dense peak at these widths); replaced by the measured rate once a voyage of that class and preset has
# sailed (s4_intelligence.market.throughput)
EFFECTIVE_TFLOPS: dict[str, float] = {"RTX 4090": 55.0, "RTX 5090": 80.0, "H100 SXM": 220.0, "H100 PCIE": 160.0}
SETUP_HOURS = 0.35  # the ship made ready: image pulled, uv sync of torch, the library carried up, and home again


def overrides() -> dict:
    """S5's changes in force, {term: value}: the latest row per term in s5.charter_terms (a hired box: its papers)."""
    from thorp import store

    if store.papers():
        return dict(store.read_papers().get("charter_terms") or {})
    from sqlalchemy import select

    from thorp.viable.records import CharterTerm

    with store.session() as s:
        out = {}
        for r in s.scalars(select(CharterTerm).order_by(CharterTerm.id)):
            out[r.term] = r.value
        return out


def set_term(term: str, value, words: str = "") -> None:
    """A change to one term, kept (the latest in force)."""
    from thorp import store
    from thorp.viable.records import CharterTerm

    if term not in DEFAULTS:
        raise KeyError(f"no charter term {term!r}; the terms: {sorted(DEFAULTS)}")
    with store.session() as s:
        s.add(CharterTerm(term=term, value=value, words=words))


def terms() -> dict:
    """The terms in force: the defaults, each overridden by S5's latest change to it (a dict term merged)."""
    t = json.loads(json.dumps(DEFAULTS))
    for k, v in overrides().items():
        t[k] = {**t[k], **v} if isinstance(t.get(k), dict) and isinstance(v, dict) else v
    return t


def check(spec: dict) -> list[str]:
    """The policy's check (liberty_machine.POLICIES["charter"]): a spec that asks for a charter carries its quote (written by
    s1_operations.charter.quote before the gate is asked), and the quote must keep the terms. A spec that asks for
    none is not governed."""
    ch = spec.get("charter")
    if not ch:
        return []
    from thorp.viable.s3_control import charter as s3

    q = ch.get("quote")
    if not q:
        return ["asks for a charter but carries no quote (thorp charter quote SPEC)"]
    return s3.violations(q, terms())
