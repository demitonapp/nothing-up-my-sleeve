"""S3 control's prechecks: the library a fitout reads, against the rules the gate enforces for each voyage
(period, decks, stores) and against what its biggest class needs (enough text). Checked once for the fitout,
before any of its voyages takes the helm.
"""

from __future__ import annotations

from thorp.viable.precheck_item import Context, Item


def _period(ctx: Context):
    from thorp import vsm

    deaths = vsm._deaths()
    bad = [b for b in ctx.books if b in deaths and deaths[b] > 1955]
    return float(len(bad)), {"books": len(ctx.books), "breaking": bad[:20]}


def _decks(ctx: Context):
    from thorp.sources.gutenberg import resolve_list

    held = set()
    for deck in ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"):
        held.update(f"pg{r.chosen}" for r in resolve_list(deck) if r.chosen)
    bad = sorted(set(ctx.books) & held)
    return float(len(bad)), {"read_from_the_decks": bad[:20]}


def _stores(ctx: Context):
    from thorp.sources.gutenberg import resolve_list

    stores = set()
    for lib in ("lists/stores/prose.csv", "lists/stores/trigram.csv"):
        stores.update(f"pg{r.chosen}" for r in resolve_list(lib) if r.chosen)
    opted = all((s.get("data") or {}).get("opt_in") for s in ctx.specs) if ctx.specs else False
    out = [b for b in ctx.books if b not in stores]
    return (0.0 if opted else float(len(out))), {"outside_the_stores": out[:20], "opted_in": opted}


def _enough(ctx: Context):
    """Tokens of the fitout's text against what its biggest class needs: 20 tokens a parameter over its passes."""
    import json

    from thorp import paths, tokeniser, train

    tid = tokeniser.tokeniser_id(ctx.tokeniser_books, ctx.tokeniser_settings)
    stats = paths.tokenisers_dir() / tid / "stats.json"
    if not stats.exists():
        return None, {"waiting_for": "the shared tokeniser (tokeniser.trained)"}
    per = json.loads(stats.read_text())
    tokens = sum(per[b]["tokens"] for b in ctx.books if b in per)
    from thorp.models.backend import backend_of

    need, biggest = 0.0, None
    for s in ctx.specs:  # each class's parameters, counted from the model its spec builds (on its backend)
        if backend_of(s) == "torch":
            from thorp import train_torch

            model = train_torch.build_model(s, s["tokeniser"]["vocab"], train_torch.torch.device("cpu"))
        else:
            model = train.build_model(s, s["tokeniser"]["vocab"])
        n = model.parameter_counts()["total"]
        passes = (s.get("data") or {}).get("passes") or 1
        if 20 * n / passes > need:
            need, biggest = 20 * n / passes, (s["model"]["preset"], n, passes)
    return tokens / max(1.0, need), {
        "tokens": tokens,
        "needed": int(need),
        "biggest": {"class": biggest[0], "parameters": biggest[1], "passes": biggest[2]} if biggest else None,
        "books_counted": len(per),
    }


ITEMS = (
    Item(
        "library.period", "Period only",
        "every book is pre-1930 public domain with every credited name dead by 1955 (S5 policy 'period')",
        "S3", "library", "books breaking the period rule", "=", 0.0, _period,
    ),
    Item(
        "library.decks", "No held-out book",
        "no book of the hole cards or the Forgotten Tomes is read (S5 policy 'decks')",
        "S3", "library", "held-out books read", "=", 0.0, _decks,
    ),
    Item(
        "library.stores", "From the ship's stores",
        "every book is in the prose or trigram stores, or every voyage opts out in words (S5 policy 'stores')",
        "S3", "library", "books outside the stores, without an opt-in", "=", 0.0, _stores,
    ),
    Item(
        "library.enough_text", "Enough text for the biggest class",
        "the fitout's tokens cover 20 a parameter for its biggest class over the passes it reads",
        "S3", "library", "tokens / (20 x parameters / passes) for the biggest class", ">=", 1.0, _enough,
    ),
)  # fmt: skip
