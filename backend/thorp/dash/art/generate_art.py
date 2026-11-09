#!/usr/bin/env python3
"""The dashboard's art (2026-11-07): one image per class of ship and one per playing card.

Eduardo Risso style, matching the monorepo's Atlas generators (packages/ui/apps/atlas/scripts/
generate-*-art.py): noir, heavy black ink, stark chiaroscuro, a single light source, no text. Made with
fal (fal-ai/flux/dev). Saved to frontend/public/art/<key>.png (since the split), which the build copies into the
dashboard; a class card or playing card shows its image when the file exists and draws none otherwise.

The fal key is read from FAL_KEY in the monorepo's packages/api/.env.local (gitignored), the same
file the Atlas generators read, or from the FAL_KEY environment variable. It is never printed.

Usage:
  python3 thorp/dash/art/generate_art.py              # every image not made yet
  python3 thorp/dash/art/generate_art.py keel bridge  # these, made again
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.request
from pathlib import Path

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parents[3] / "frontend" / "public" / "art"  # the repository's frontend/
ENV_LOCAL = Path.home() / "Source" / "monorepo" / "packages" / "api" / ".env.local"

MODEL = "fal-ai/flux/dev"
STYLE = (
    "Eduardo Risso style noir comic art, 100 Bullets, heavy black ink, "
    "stark chiaroscuro, single dramatic light source, deep shadows, high "
    "contrast, dark near-black background, graphic novel panel, clean bold "
    "composition, no text, no lettering, no words, "
    "no signature, no border, no frame, full-bleed image"
)

# The classes of ship, smallest first: each a sailing vessel a size up from the last (thorp/models/registry.py
# LADDER), with the job its class does. Landscape, for the class cards.
CLASSES: dict[str, str] = {
    "keel": "a lone ship's keel laid on a wooden slipway in a dark shipyard at night, only the spine and the "
    "first few ribs raised, a single hanging lantern throwing hard shadows across the timber, the hull still "
    "to be built around it",
    "pilot": "a small pilot cutter nosing out of a harbour mouth at night, a lone figure at the bow holding a "
    "lantern out over the black water to show the way, a large ship's dark shape following close behind",
    "speller": "a small single-masted sloop under sail on a dark sea, a long line of signal flags strung up "
    "its rigging spelling out a message, moonlight cutting through the flags",
    "stylist": "an elegant two-masted schooner with fine sweeping lines heeling in the wind, a figure at the "
    "wheel in a long coat, a slash of moonlight along the hull, graceful and precise",
    "paragraph": "a brigantine on a long night passage across open ocean, its wake a long unbroken line "
    "behind it to the horizon, a navigator at the chart table under a swinging lamp",
    "explorer": "a three-masted barque sailing off the edge of the known chart toward an uncharted island in "
    "fog, a figure in the bow with a brass telescope raised, the old chart pinned beside him ending in blank paper",
    "trader": "a towering full-rigged ship of the line cresting an enormous wave, every sail set, the "
    "masts reaching up into a field of stars, lightning behind, the largest ship on the sea",
    # 8 Nov (Justin): the 300k is Pan, the 1m Augustus, and their cards show them, not boats: "pan playing cards
    # with the universe and augustus teaching maths"
    "pan": "the Greek god Pan, horned and goat-legged, alone at a small card table under the open night sky, "
    "playing cards with the universe: across the table there is no one, only the starry sky and a spiral "
    "galaxy, and out of the stars a vast hand of glittering stars and constellation lines reaches down to lay "
    "a playing card on the table, Pan holding his own cards close, ",
    "augustus": "a Victorian mathematics master in a frock coat teaching arithmetic by gaslight, chalk in hand "
    "at a blackboard of simple sums, a row of small pupils seen from behind at their desks, a single lamp "
    "throwing hard shadows across the board",
}

# The harbours (Justin, 8 November: "i want two fal images for them"): Phaleron, Athens' first harbour, and the Market Harbour,
# the first great trading harbour. Landscape, for the harbour tiles.
HARBOURS: dict[str, str] = {
    "phaleron": "the ancient Greek harbour of Phaleron at night, a sheltered curved bay of calm black water, a row of "
    "small beached wooden triremes and young ships drawn up on the shingle, shipwrights and trainee oarsmen with "
    "torches, a stone breakwater, the lamplit hills of Athens and the Acropolis faint on the dark horizon",
    "zayton": "a vast ancient trading harbour at night, lantern-lit quays crowded with bales of silk and sacks of "
    "spice, merchants of many nations bargaining, dhows, junks and tall merchantmen moored in rows with their "
    "sails furled, a camel caravan arriving down to the water, countless lamps reflected in the black harbour",
}

# The four positions at the 1m (Justin, 8 November: "generate fal images"): Augustus has his card already (CLASSES);
# Plato, Francis and Diderot are new. Landscape, for the ship cards in Phaleron.
POSITIONS: dict[str, str] = {
    "plato": "an ancient Greek philosopher in a long robe walking with a few young students along a lamp-lit colonnade "
    "at night, pointing up at the stars as if at the unseen forms behind things, his long shadow thrown across the "
    "stone floor, a flickering shadow play of figures cast on the cave wall behind them",
    "francis": "an Elizabethan natural philosopher in a ruff and dark coat at a laboratory bench by candlelight, "
    "weighing a flask on a brass balance and writing down what he sees in a ledger, shelves of glass instruments and "
    "specimens around him, a frozen winter window behind, a single lamp throwing hard shadows",
    "diderot": "an eighteenth-century encyclopaedist at a vast crowded writing desk by candlelight, towers of folios, "
    "maps, engraved plates of trades and machines and animals spread around him, a quill in his hand, shelves of "
    "every kind of book rising into the dark, a single lamp",
}

# Foreign ships (9 November, Justin: "fal images for the foreign ships like qwen and ms phi"; then "the
# ships from alibaba vs microsoft vs google vs independent labs need to share some characteristics within
# their fal images"). Each house has a shared look, so the ships read as a fleet from one yard:
#   Alibaba/Qwen  red battened sails, jade-green trim, a gold circular medallion, red stern lanterns
#   Microsoft/Phi slate-blue hull, a square sail divided into four pale panes, a silver pennant
#   Google/Gemma  sails in four coloured panels (blue, red, yellow, green), a brass compass rose at the bow
#   independent   patched cream canvas, a dark tarred hull, one hand-painted white star; no house colours
LAB_LOOK = {
    "alibaba": "her battened sails are deep red, her hull is trimmed in jade green, a gold circular medallion is "
    "nailed to the stern, and red paper lanterns hang from the stern rail",
    "microsoft": "her square sail is pale and divided into four panes by dark seams, her hull is slate blue, and a "
    "small silver pennant flies from the masthead",
    "google": "her sails are divided into four broad coloured panels, deep blue, red, yellow and green, and a brass "
    "compass rose is mounted on the bow",
    "independent": "her canvas sails are patched cream, her hull is dark tarred wood, and a single white star is "
    "hand-painted on the main sail; she carries no house colours",
}

FOREIGN: dict[str, str] = {
    "qwen3-4b": "a vast four-masted Chinese treasure ship with a high stern castle, riding at anchor in a crowded "
    "lantern-lit trading harbour at night, junks and dhows around her, merchants on the quay unloading bales of "
    "silk, the largest and deepest ship in the harbour; " + LAB_LOOK["alibaba"],
    "qwen3-1-7b": "a two-masted Chinese ocean-going junk under full sail on a dark sea, a low moon behind cloud, "
    "her crew small on the deck, a larger treasure ship faint on the horizon; " + LAB_LOOK["alibaba"],
    "qwen3-0-6b": "a small single-masted coastal junk slipping out of a narrow harbour mouth at dusk, one red "
    "lantern lit at her stern, fishing boats drawn up on the mud behind her; " + LAB_LOOK["alibaba"],
    "qwen3-8-27b": "an enormous four-masted Chinese treasure flagship at anchor in a wide night harbour, her red "
    "sails furled but still the tallest thing on the water, hundreds of lanterns reflected around her, smaller "
    "junks dwarfed alongside; " + LAB_LOOK["alibaba"],
    "phi-2": "a lean two-masted Byzantine dromon with a bronze ram at the bow, gliding out of a dark harbour mouth "
    "under a low moon, oars lifting in a row, a lone lantern at the stern; " + LAB_LOOK["microsoft"],
    "phi-4-mini": "a compact four-oared pinnace with a low black hull, tied at a dark stone quay beside much larger "
    "ships, a single hooded figure stepping aboard with a lantern, the little boat dwarfed by the foreign hulls "
    "around it; " + LAB_LOOK["microsoft"],
    "gemma-3-4b": "a four-masted Venetian carrack under full sail on a dark open sea, her high stern and broad "
    "beam cutting through the swell, moonlight catching the coloured panels of her sails; " + LAB_LOOK["google"],
    "gemma-2-2b": "a two-masted caravel heeling in a night wind, her four-coloured sails filled, a navigator at the "
    "stern with a lantern and a brass compass, a dark coast behind her; " + LAB_LOOK["google"],
    "gemma-3-270m": "a small ketch with a single mast and a tiny crew, crossing a black harbour basin at night, her "
    "four-coloured sail the brightest thing on the water, a brass compass glinting at her bow; " + LAB_LOOK["google"],
    "llama-3-2-3b": "a three-masted barque on a long night passage, patched cream canvas bellied in the wind, a "
    "lone figure at the wheel in a long coat, dark water and a low moon; " + LAB_LOOK["independent"],
    "smollm3-3b": "a three-masted coastal lugger running before a night wind, her patched cream sails full, a "
    "lantern swinging at the mast, a dark headland behind her; " + LAB_LOOK["independent"],
    "smollm2-360m": "a small single-masted sloop nosing out of a rocky cove at night, one patched cream sail, a "
    "single white star painted on it, a lantern at the bow; " + LAB_LOOK["independent"],
    "pythia-14m": "a tiny one-masted dinghy tied to a dark jetty at night, a patched cream sail furled on its boom, "
    "a single white star painted on the canvas, a lantern on the boards; " + LAB_LOOK["independent"],
    "pythia-31m": "a small two-masted cutter at anchor in a black harbour, patched cream sails furled, a white star "
    "on the main sail, a single lamp on the quay; " + LAB_LOOK["independent"],
    "pythia-70m": "a two-masted lugger under a low moon, patched cream canvas drawing, a white star on the main "
    "sail, dark water and a far shore; " + LAB_LOOK["independent"],
    "pythia-160m": "a three-masted barquentine on a night sea, patched cream sails filled, a white star painted on "
    "the main canvas, a lantern at the stern; " + LAB_LOOK["independent"],
    "pythia-410m": "a large three-masted barque cresting a dark swell under a low moon, patched cream sails full, a "
    "white star on the main sail, a single lantern burning at the stern; " + LAB_LOOK["independent"],
}

# The playing cards: the stars that do the trick# The playing cards: the stars that do the trick (fleet.STARS / fleet.METHODS["chaining"] cards). Portrait,
# for the card faces.
CARDS: dict[str, str] = {
    "previous_word": "a figure in a long coat walking along a dark street, glancing back over their shoulder "
    "at the single footprint just behind them, lit by one streetlamp, the first step of a trail",
    "nevermore": "a black raven perched on a pale bust above a doorway at night, one eye catching the light, "
    "a single page held in its beak repeating what it has seen before",
    "mover": "a gloved hand carrying a small lit lamp across a dark room from one table to another, the "
    "flame the only light, as if carrying a fact from where it was found to where it is needed",
    "comparator": "an old brass balance scale on a table, one pan heavier than the other and tipped down, "
    "a single shaft of light from above falling across it",
    "bridge": "a narrow rope bridge across a deep chasm in fog, a lone figure halfway across holding a "
    "lantern, the two cliff edges barely visible, the bridge the only way from one side to the other",
    # the rest of the 16-card deck (Justin, 2026-11-07 21:20; thorp/viable/s5_policy/deck.py)
    "duplicate_word": "two identical calling cards lying side by side on a dark wooden table under a single "
    "hanging lamp, one slightly overlapping the other, a gloved finger touching the second",
    "induction": "a hand turning back the pages of an old book by candlelight to a passage marked with a ribbon, "
    "a fingertip resting on the line just after the mark",
    "sink": "an old iron mooring bollard on a dark stone quay at night, many ropes from unseen ships all "
    "tied to it, the ropes vanishing into fog, a single lamp above",
    "delimiter": "a long breakwater of tall dark stone posts dividing calm harbour water from a rough open sea, "
    "moonlight catching the top of each post in a row",
    "words_back": "a sailor at a ship's stern at night looking back at two small lanterns bobbing in the dark "
    "wake behind the ship, one near, one further",
    "counter": "a ship's log line being paid out over the stern, the knots running through a gloved hand, a "
    "sand glass beside it on the rail, lit by a ship's lantern",
    "number_spotter": "a magnifying glass held over a ledger column of handwritten figures on a desk at night, "
    "one lamp, the lens sharpening a single line",
    "order_word": "a wooden signpost at a foggy crossroads at night with two arrows pointing opposite ways, a "
    "lone traveller with a lantern deciding which way",
    "scales": "a row of brass weights on a dark chart table arranged in order from the smallest to the largest, "
    "a single shaft of light falling along the row",
    "rare_word": "a single gold coin lying among dark wet pebbles on a beach at night, catching the moonlight, "
    "everything else in shadow",
    "premise_marker": "a hand setting a small lit marker buoy at the mouth of a dark channel between rocks, "
    "the first light showing where the way begins",
}

# The logic deck's five relations (lists/tricks/logic-40.csv; Justin, 2026-11-08: "Yes, make art"): each a chain of
# two facts and the conclusion that needs both, drawn as one picture. Portrait, for the deck's tiles.
LOGIC: dict[str, str] = {
    "logic_order": "three lighthouses of rising height along a dark rocky coast at night, each taller than the "
    "one before it, their beams cutting through fog, a lone figure on the shore looking from the first to the last",
    "logic_cause": "a sailor turning a capstan at night, the rope running over a block and hauling a dripping "
    "anchor up out of black water, each part moving the next, one lantern lighting the chain of things",
    "logic_membership": "an open sea chest in a dark ship's hold, inside it an open wooden box, inside that a "
    "small open locket, each lid thrown back, a single lantern shining down into the nest of them",
    "logic_proportion": "a train of three brass gears on a chart table at night, a small gear turning one twice "
    "its size, which turns one twice as large again, a single shaft of light across the teeth",
    "logic_counterfactual": "a navigator at a chart table following a strange hand-drawn chart that disagrees "
    "with the stars seen through the porthole, a finger on the chart, trusting the paper over the sky, one lamp",
}

SIZES = {**{k: "landscape_16_9" for k in (*CLASSES, *HARBOURS, *POSITIONS, *FOREIGN)}, **{k: "portrait_4_3" for k in CARDS}, **{k: "portrait_4_3" for k in LOGIC}}
SUBJECTS = {**CLASSES, **HARBOURS, **POSITIONS, **FOREIGN, **CARDS, **LOGIC}


def fal_key() -> str:
    if os.environ.get("FAL_KEY"):
        return os.environ["FAL_KEY"]
    if ENV_LOCAL.exists():
        for line in ENV_LOCAL.read_text().splitlines():
            if line.startswith("FAL_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f"No FAL_KEY in the environment or in {ENV_LOCAL}")


def request(path: str, key: str, payload: dict | None = None) -> dict:
    url = path if path.startswith("http") else f"https://queue.fal.run/{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        method="POST" if payload is not None else "GET",
        headers={"Authorization": f"Key {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read().decode())


def generate(name: str, key: str) -> None:
    prompt = f"{SUBJECTS[name]}. {STYLE}"
    out = OUT_DIR / f"{name}.png"
    print(f"{name}: submitting...", flush=True)
    started = request(MODEL, key, {"prompt": prompt, "image_size": SIZES[name]})
    status_url = started.get("status_url") or f"{MODEL}/requests/{started['request_id']}"
    for _ in range(60):
        time.sleep(5)
        status = request(status_url, key)
        if status.get("status") == "COMPLETED":
            result_url = status.get("response_url")
            result = request(result_url, key) if result_url else status
            images = result.get("images") or []
            if not images:
                raise SystemExit(f"{name}: completed with no images")
            out.parent.mkdir(parents=True, exist_ok=True)
            with (
                urllib.request.urlopen(images[0]["url"], timeout=120, context=SSL_CONTEXT) as resp,
                open(out, "wb") as f,
            ):
                f.write(resp.read())
            print(f"{name}: wrote {out.relative_to(HERE.parents[3])}", flush=True)
            return
        if status.get("status") == "FAILED":
            raise SystemExit(f"{name}: failed")
    raise SystemExit(f"{name}: timed out")


def main() -> int:
    names = sys.argv[1:] or [n for n in SUBJECTS if not (OUT_DIR / f"{n}.png").exists()]
    key = fal_key()
    for n in names:
        if n not in SUBJECTS:
            raise SystemExit(f"unknown {n}; choices: {', '.join(SUBJECTS)}")
        generate(n, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
