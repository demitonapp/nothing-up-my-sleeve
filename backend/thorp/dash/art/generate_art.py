#!/usr/bin/env python3
"""The dashboard's art (2026-11-07): one image per class of ship and one per playing card.

Two things at once, and both are the brief (11 November, Justin: "can you audit all the images and the
instructions and memory to make sure that we use the Risso artstyle from 100 bullets but we now also have a
time period and it's from the days of Drake. So all images, everything should be a homage to the heyday of
Sir Francis Drake but drawn by risso's style"):

- **Risso**: Eduardo Risso's noir comic art (100 Bullets), matching the monorepo's Atlas generators
  (packages/ui/apps/atlas/scripts/generate-*-art.py): heavy black ink, stark chiaroscuro, a single light
  source, deep shadows, near-black ground, no text.
- **Drake**: the *inspiration* is Drake and the merchant ships that went looking for new worlds — great
  wooden ships, chart tables, lanterns and brass, sea-cloaks and tallow, landfalls on unnamed coasts.
- **The world is Iain M. Banks' Culture in its early days** (Justin, same day: "the style is rissos, the
  inspiration is drake and the merchant ships exploring new worlds, the world is banks early days of the
  culture"). The ships are of the age of sail and the universe is the young Culture's: an orbital ring
  where a moon would be, a distant habitat, a small silver drone at rest on the chart or in the rigging.
  Hopeful, expanding, first contact — not a later, settled Culture and not our own century.
  An anachronism is a defect, not a mood: no Greek triremes, no Chinese junks, no Venetian carracks, no
  Victorian gaslight (a ship of another nation's build is allowed only as a *prize*, as Drake took the
  São Filipe — that is the trade of the period, not outside it).

Made with fal (fal-ai/flux/dev). Saved to frontend/public/art/<key>.png (since the split), which the build copies into the
dashboard; a class card or playing card shows its image when the file exists and draws none otherwise.

The fal key is read from FAL_KEY in the monorepo's packages/api/.env.local (gitignored), the same
file the Atlas generators read, or from the FAL_KEY environment variable. It is never printed.

Usage:
  python3 thorp/dash/art/generate_art.py              # every image not made yet
  python3 thorp/dash/art/generate_art.py towing-tank bridge  # these, made again
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
    "no signature, no border, no frame, full-bleed image, "
    # The brief in three layers (11 November, Justin: "the style is rissos, the inspiration is drake and the
    # merchant ships exploring new worlds, the world is banks early days of the culture"):
    #   style      -- Risso's ink, above
    #   inspiration-- Drake, and the merchant ships that went looking for new worlds
    #   world      -- Iain M. Banks' Culture in its first days: a young, hopeful, expanding civilisation
    "the scene is a merchant ship's voyage of discovery in the manner of Drake's, and the world it sails "
    "in is Iain M. Banks' Culture in its early days: great wooden ships with lanterns, brass, chart "
    "tables and sea-cloaks, landfalls on unnamed coasts and first contacts, while the sky and the water "
    "hold the young Culture's own forms -- an orbital ring where a moon would be, a distant habitat, a "
    "small silver drone at rest on the chart or in the rigging -- the exploration is the age of sail and "
    "the universe is the Culture's, nothing modern of our own century, no anachronism from later history; "
    # the trace is standing, not optional: a group of images without it read as plain age-of-sail, and the
    # audit of 11 November found the bands, the classes and the cards had lost the world entirely
    "in every image, somewhere in the sky or on the water, one distant sign of that universe: a thin ring "
    "of light standing where a moon would be, or a far habitat, or a small silver drone"
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
    # 11 Nov, night (Justin: "we mix a bunch of combinations there and then measure it to see what comes out";
    # "i like towing tank, please update the fal images and the naming"): the 300k is the towing tank, where a
    # shipwright draws one small hull after another down the same water and times each. Froude's tank is
    # Victorian and the world is Drake's, so it is drawn as a yard of that age would build it: a timber trough,
    # a falling weight on a line, a sandglass and a ledger. It replaces Pan's plate on the class card.
    "towing-tank": "a shipwright's towing tank inside a dark timber shipyard shed at night: a long narrow "
    "wooden trough of still black water running the whole length of the shed toward an open door, one small "
    "carved wooden hull model no longer than a forearm afloat in the middle of the trough, drawn along the "
    "water by a taut line to a lead weight falling over a brass pulley, a thin V-shaped wake behind it, a "
    "rack of other small hull models of different shapes waiting on the boards beside the trough, a "
    "shipwright in a leather apron and Elizabethan breeches crouched at the water's "
    "edge holding a sandglass, a clerk behind him writing the reading in a ledger, one hanging lantern "
    "throwing hard shadows along the water, a small silver drone at rest on a beam above the tank, and "
    "through the open door a thin luminous ring arcing across the night sky",
    # The 1m follows it (Justin: "Also what should the 1m be?"; "Yes, rename 1m"): the measured mile, the
    # marked water where a real hull is timed between two posts to check what the tank predicted. It
    # replaces Augustus's plate on the class card; Augustus the position keeps his.
    "measured-mile": "under a vast thin ring of pale light arcing across the whole night sky where a moon "
    "would be, the measured mile seen from a rocky headland: two tall rough timber poles "
    "like ship's masts planted in the rocks, an iron fire basket burning at the top of each, one near in "
    "the foreground and one small and far away along the dark coast, a small wooden galleon of "
    "Drake's kind under sail running a straight course on black water from one beacon toward the other, "
    "her long straight wake behind her, in the foreground a figure in a sea-cloak on the rocks holding up "
    "a sandglass to the firelight to time her, a clerk beside him with an open ledger",
    # 12 Nov (Justin: "Can you suggest new metaphors for the 9m and 21m ships"; "Yes, rename both"): the 9m is
    # the sea trial, the finished ship taken past the harbour bar for the first time with everything worked at
    # once, to see whether she does at sea what the tank and the mile said. It replaces the speller's sloop on
    # the class card and the landfall on the rung card.
    "sea-trial": "under a vast thin ring of pale light arcing across the night sky where a moon would be, a "
    "new-built wooden galleon of Drake's kind crossing the harbour bar into open water for the first time, "
    "every sail set and pale and unweathered, her bow lifting to the first ocean swell and white water "
    "breaking along the bar, on her deck a shipwright in a leather apron and Elizabethan breeches watching "
    "the rigging, a clerk beside him writing in an open ledger by lantern light, two sailors bent at the "
    "wooden pump, far behind her and small the dark shipyard with its slipway and one lantern, a small "
    "silver drone at rest on the stern rail",
    # The 21m follows it: the coasting run, a proven ship's first working trips, port to port with a cargo
    # aboard and the land always in sight, before the 50m's crossing. It replaces the stylist's schooner on
    # the class card and the passage on the rung card.
    "coasting-run": "under a vast thin ring of pale light arcing across the whole dusk sky where a moon would be, "
    "a small laden Elizabethan merchant bark working close inshore along a dark rocky coast "
    "at dusk, low in the water, barrels and bales lashed on her deck under tarred canvas, patched tan sails, "
    "a leadsman leaning out from her side swinging a lead line into the black water, a figure in a sea-cloak "
    "at the helm watching the shore, the long dark coast running the whole width of the scene close beside "
    "her, an iron fire basket burning on the near headland and the small warm lights of a harbour town in a "
    "cove ahead, a small silver drone at rest on the masthead",
}

# The harbours (Justin, 8 November: "i want two fal images for them"; 11 November: "naming must change and
# art style accordingly"). They are Orbitals of the young Culture now, not the Greek and Chinese ports they
# were first named for: the first Orbital where crews are trained, the great yard at the edge of the new
# worlds, and the Reach where every civilisation trades. Landscape, for the harbour tiles. Their old keys
# (phaleron, piraeus, zayton) survive only as aliases in thorp/dash/waters.py.
HARBOURS: dict[str, str] = {
    "schimint": "the first Orbital of a young civilisation at night, seen from a ship's deck: a vast ring "
    "curving up across the sky where a moon should be, its inner face lit in long bands, a small wooden "
    "sailing ship of Drake's kind crossing black water toward it, lanterns on the ship and along the "
    "Orbital's rim, a place where crews are trained rather than a port",
    "vavatch-end": "a great construction Orbital at the edge of the new worlds at night: the ring's "
    "shipyards and docks seen from close alongside, half-built hulls of wooden ships cradled in scaffolds "
    "that are not of this century, cranes and lanterns, brass instruments on the dock rail, the dark curve "
    "of the ring rising beyond",
    "masaq-reach": "a cosmopolitan Orbital's market at night: a lantern-lit concourse under a curved hull, "
    "ships of many worlds moored along a quay, bales of goods and brass instruments, ropes and canvas "
    "beside surfaces that are not of our century, figures in sea-cloaks bargaining, the Reach's lights "
    "reflected in black water",
    # The two orbitals the home page opens on (12 November, Justin: "the analogy is orbitals for the
    # homepage. The demiton orbital and then the trading orbital where all the other labs and their ships
    # reside"). Demiton is our own orbital: the training ring and the deep yards are its berths, and every
    # ship we build and sail lies there. The trading orbital wears the Reach's own plate above.
    "demiton": "a vast ring-shaped Orbital seen from the deck of one of our own ships at night: the ring "
    "curving up across the sky where a moon would be, its inner face lit in long bands, below it a shipyard "
    "and a training basin along the rim, our own wooden ships of several sizes at anchor under lanterns, one "
    "great keel laid on the stocks, a small silver drone at rest on the rigging, the young Culture's first "
    "orbital, hopeful and expanding",
}

# The harbour cards flip (11 November, Justin: "the cards to harbours to flip so each harbour has 5 images
# showing the different aspects of the harbour based upon our image style, themes and world"). Each Orbital
# has its own plate above as the first view and four more here, named <harbour>-<view>: what is done there,
# who does it, and the Culture's trace in the sky. The frontend lists the five in HARBOUR_VIEWS
# (frontend/src/scripts/views/harbours.ts); a view is added there and here together.
HARBOUR_VIEWS: dict[str, str] = {
    "schimint-drill": "cadets drilling on the inner deck of a great Orbital at night: a row of young sailors "
    "in sea-cloaks splicing rope and hauling on a practice rigging set up on the ring's curved floor, a stern "
    "master holding a lantern and a knotted cord, the lit bands of the ring curving up overhead",
    "schimint-school": "a long lamplit chart school inside an Orbital at night: apprentices on benches bent "
    "over charts with dividers and parallel rules, a master pointing with a rod at a great slate of sums and "
    "star lines, a small silver drone perched on a hanging lamp, hard shadows from one lamp",
    "schimint-berth": "a fitting-out berth at night: four small wooden hulls on cradles, half-rigged, a "
    "different coloured lantern hung at each bow, riggers up in the masts, a foreman with a ledger counting "
    "the hulls, the curved inner wall of the ring beyond",
    "schimint-launch": "a ship's boat of a first crew pulling away from the rim of an Orbital at night: young "
    "sailors at the oars, a lantern in the stern, instructors watching from a stone stair on the rim, the "
    "vast ring curving overhead, black water ahead",
    "vavatch-end-slip": "an immense keel being laid on a great slipway at an Orbital's construction yard at "
    "night: hundreds of tiny shipwrights on scaffolding along a keel as long as a street, torches and "
    "lanterns, adzes and mallets, the dark curve of the ring rising above",
    "vavatch-end-forge": "a great shipyard forge at night: a smith in silhouette hammering a glowing brass "
    "fitting on an anvil, sparks flying, molten metal poured into a mould, heavy chains and ships' anchors "
    "hung in the dark, the furnace the only light",
    "vavatch-end-launch": "a finished wooden hull sliding down the ways into black water at night, "
    "shipwrights along the slip with lanterns raised, spray and ropes snapping taut, the lights of the ring "
    "reflected on the water",
    "vavatch-end-gate": "the hiring gate of an Orbital's shipyard before dawn: a line of shipwrights and "
    "riggers with tool-bags queuing at an iron gate lit by lanterns, a foreman with a ledger and a clerk with "
    "brass scales taking on hired gangs, the yard's cranes beyond",
    "masaq-reach-quay": "a long quay at a cosmopolitan Orbital at night where ships of many worlds lie "
    "moored side by side: a captured Portuguese carrack, English galleons and one strange silver-hulled "
    "visitor, gangplanks and lanterns, stevedores unloading chests",
    "masaq-reach-scales": "a customs table at night where a clerk reads a foreign ship: a great brass "
    "balance with a small model hull on one pan and weights on the other, open ledgers and a ship's plan "
    "pinned flat, a magnifying glass, one lamp, a small silver drone watching from a shelf",
    "masaq-reach-exchange": "a crowded merchants' exchange under a lantern-lit vault of an Orbital: traders "
    "in cloaks and doublets bargaining across tables heaped with charts, ledgers and coin, two hands "
    "clasped on a deal, a small silver drone hovering above the crowd",
    "masaq-reach-gauge": "three ships lined up at anchor to be measured against a great carved brass gauge "
    "post on the quay: a small cutter, a mid-sized brig and a towering galleon, a harbour-master with a "
    "brass rule at the post, the ring of light overhead",
}


# The ship builder (9 November, Justin: "give me a fal image representing the shipbuilder and SOP"): the drafting
# loft where the standard operating procedure is written, rather than a finished ship at sea. Landscape, for the
# builder's banner.
# The shipyard (9 November, Justin: "it should be called shipyard and have a fal image to match"):
# the yard itself, not the drafting loft: hulls on the stocks, cranes and lanterns, the SOP's work made.
SHIPYARD: dict[str, str] = {
    "shipyard": "a working shipyard at night: a half-built wooden hull raised on heavy stocks, scaffolding and a "
    "tall crane above it, shipwrights with lanterns and tools, stacks of timber and iron, a drafting table with "
    "hull plans in the foreground, dark harbour water and the lights of the town behind",
}

# The shipyard's three sections, each with its own image under the cards (9 November).
SHIPYARD_SECTIONS: dict[str, str] = {
    "training": "a lamplit training hall at night: long tables of books and slates, a ship's crew drilling a raid "
    "plan around a chart, chalk marks on a board, a tutor at the head, dark timber and brass",
    "fitting": "a fitting-out workshop at night: a half-built wooden ship model on heavy trestles, glowing threads "
    "of an embedding table strung between posts, scaffolding and carved heads, plans and tools, lantern light",
    "raiding": "a raiding party at night: a ship's boat pulling away from a dark harbour, lanterns at the oars, a "
    "chart of the target's lights, the town glowing across the water",
}

# Charting (9 November, Justin: "raiding should be renamed charting ... the guys sorting out the charts"):
# the chart room where the voyage is drawn before it is sailed.
CHARTING: dict[str, str] = {
    # Hull sizes (9 November, Justin: "the hull in shipyard should have a card like charting with a fal image")
    "hulls": "a shipwright's mould loft: a vast draughting floor with the full-size curves of a ship's hull drawn "
    "in white chalk on dark boards, a single lamp over the lofting floor, ribs of a half-built vessel behind, "
    "a scale model on a bench, ",
    "charting": "a chart room at night: three navigators leaning over a large table, unrolling sea charts and maps, "
    "dividers and a brass compass, a lantern, shelves of rolled charts, a course marked in pencil, no ship in sight",
}

SHIPBUILDER: dict[str, str] = {
    "shipbuilder": "a shipwright's drafting loft at night: through the tall window the dark ribs of a half-built ship "
    "rise on the stocks, and on the long table below a spread of hull drawings, a heavy leather-bound book of rules "
    "open beside them, brass dividers, a pot of ink and a single lamp throwing hard shadows across the plans",
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
    "openai": "her hull is matte black, her single sail is pale unbleached canvas with a thin green stripe along the "
    "leech, and a small brass lamp burns at the masthead",
    "inclusionai": "her sails are dove-grey with a thin gold band along the leech, her hull is dark teak, and a pale "
    "silver ring is painted on the main sail",
}

FOREIGN: dict[str, str] = {
    "ling-3-0-tiny": "a narrow three-masted clipper running before a night wind, her few crew small on the deck, "
    "overtaking a far larger galleon in the dark, a low moon and a thin ring of light standing in the sky; "
    + LAB_LOOK["inclusionai"],
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
    "qwen3-30b-a3b": "a three-masted Chinese treasure ship in a wide night harbour, red battened sails half set, a "
    "high stern castle, smaller junks and dhows around her, lanterns on the water; " + LAB_LOOK["alibaba"],
    "gemma-4-26b-a4b": "a broad-beamed four-masted Venetian carrack at anchor in a lantern-lit night harbour, her "
    "coloured sail panels furled, a brass compass rose at the bow, the black water full of reflections; " + LAB_LOOK["google"],
    "gemma-4-31b": "a towering four-masted Venetian flagship at night, every coloured sail panel full, high stern "
    "and broad beam, a brass compass rose at the bow, dwarving the boats around her; " + LAB_LOOK["google"],
    "phi-4-14b": "a lean two-masted Byzantine dromon gliding out of a dark harbour mouth at night, oars lifting in a "
    "row, a low moon behind cloud, a silver pennant at the masthead; " + LAB_LOOK["microsoft"],
    "gpt-oss-20b": "a fast black-hulled sloop running before a night wind on a dark sea, one pale sail drawing, a low "
    "moon and a far shore; " + LAB_LOOK["openai"],
    # the xsmall base/instruct twins: a base checkpoint wears plain canvas, its instruct twin the house colours
    "qwen3-0-6b-base": "a small single-masted Chinese coastal junk slipping out of a narrow harbour at dusk, her "
    "battened sails plain undyed canvas, no lanterns, the houses dark behind her; " + LAB_LOOK["alibaba"],
    "qwen3-5-0-8b-base": "a small two-masted Chinese coastal junk under plain undyed sails on a dark estuary, no "
    "lanterns lit, a low moon behind cloud",
    "gemma-3-270m-instruct": "a small ketch with a single mast crossing a black harbour basin at night, her "
    "four-coloured sail the brightest thing on the water, a brass compass glinting at her bow; " + LAB_LOOK["google"],
    "smollm3-3b-instruct": "a three-masted coastal lugger running before a night wind, patched cream canvas full, a "
    "lantern swinging at the mast and a single white star on the main sail; " + LAB_LOOK["independent"],
    "smollm2-360m-instruct": "a small single-masted sloop nosing out of a rocky cove at night, one patched cream sail "
    "with a single white star, a lantern at the bow; " + LAB_LOOK["independent"],
    "pythia-410m": "a large three-masted barque cresting a dark swell under a low moon, patched cream sails full, a "
    "white star on the main sail, a single lantern burning at the stern; " + LAB_LOOK["independent"],
    # the two outside models read without art (11 November): Maincoder, a Melbourne port, and the small Qwen3.5
    "maincoder-1b": "a lean Australian colonial cutter with a low dark hull and patched cream canvas, running before "
    "a night wind past a black headland, one lantern at the bow and a single white star on the main sail",
    "qwen3-5-0-8b": "a small two-masted Chinese coastal junk slipping down a narrow estuary at dusk, her red "
    "battened sails half furled, jade-green trim on the rail, one red lantern lit at the stern; " + LAB_LOOK["alibaba"],
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

# The expeditions page (9 November, Justin: "the running SOP which is 0.0.5 with a fal image for its goal
# which was to create reasoning heads"). One image per SOP version, its aim rather than its ship.
SOP_GOALS: dict[str, str] = {
    "sop-0-0-5": "a lamplit workshop at night where a row of small brass and glass heads stand on a bench, each a "
    "different instrument with its own beam of light, thin copper wires running from one to the next in a chain, "
    "the last head lit and turning a small key, tools and blueprints scattered on the bench, no people",
    "sop-0-0-6": "a night schoolroom for a ship's crew: a clerk at a desk taking orders from a slate on the wall, a "
    "rack of small brass tokens each stamped with a symbol, and a young apprentice at a low desk raising a hand to "
    "ask a question, lamplight and long shadows, no text",
}

# The expeditions (11 November, Justin: "fal images for all the past expeditions ... and a consistent
# representation of them on the page"): one image per expedition, its aim as a scene, keyed by the
# expedition's own key with an `exp-` prefix so no image can collide with a ship, a card or an SOP. The plans
# page wears them as 16:9 cards, the same treatment as the class and harbour cards.
EXPEDITIONS: dict[str, str] = {
    "exp-book_value": "a ship's hold at night lit by a single lantern, a navigator in a long coat weighing thick "
    "leather books in a brass balance scale, one pan piled high and tipping, open ledgers and scattered coins on a "
    "crate, stacks of books vanishing into shadow",
    "exp-first_light": "the first light of dawn seen from the bow of a ship at sea, a lone lookout with a brass "
    "telescope, the sun a thin burning line on the black horizon, rigging and bowsprit black against the glow, the "
    "rest of the ship still in darkness",
    "exp-seedling": "the keel of a new ship laid along heavy timber stocks in a dark shipyard at night, the spine and "
    "first ribs rising, shipwrights with lanterns, wood shavings and tools, one lamp throwing long shadows",
    "exp-apprentice": "a candlelit magician's workshop at night, a young apprentice in a dark coat receiving a small "
    "glowing brass head from the hands of an older magician, shelves of other brass heads in shadow, tools and open "
    "books, one light source",
    "exp-table_talk": "a captain's cabin at night, two figures seated across a polished table in earnest "
    "conversation, a candle between them, charts and a decanter, an empty third chair, deep shadows in the corners",
    "exp-apprentice_2": "a long workbench in a dark workshop at night, four young apprentices in a row each handing "
    "a small glowing brass head to the next, a relay of warm light down the bench into the shadows, one hanging "
    "lamp above, tools and open books between them",
    "exp-best_keel": "a shipyard at night with many ship's keels laid on stocks in rows, shipwrights walking between "
    "them with lanterns inspecting the timber, one keel lit brightest and straightest, fog and deep shadows",
    "exp-two_facts": "a counting house at night, a clerk at a tall desk joining two heavy ledgers with a red thread "
    "stretched between two brass rings, a single lamp, columns of tallies and an iron padlock, everything else in "
    "darkness",
    "exp-card_census": "a long table at night covered in playing cards laid out in rows, a census-taker in a dark "
    "coat with a ledger and a pencil counting them by lantern light, card drawers and shelves of files behind, one "
    "light source",
    "exp-knockout": "a bare-knuckle boxer at the instant of a knockout under a single hanging lamp in a dark hall, "
    "the opponent falling back into shadow, sweat and dust in the light, a ring rope and a silent crowd in darkness",
    "exp-induction": "a hall of tall mirrors at night, one lantern carried by a figure reflected again and again into "
    "an endless receding line of lanterns, a repeating pattern, deep black shadows, a single light source",
    "exp-ogden": "a village schoolroom at night, a schoolmaster at a blackboard drawing simple pictures of a cup, a "
    "box and a man, a few pupils at wooden desks, one oil lamp, long shadows",
    "exp-smallest_bridge": "a very small figure crossing a narrow rope bridge over a deep fog-filled chasm at night, "
    "holding a lantern, the far cliff barely visible, the bridge the only way across, vast darkness around",
    "exp-logic_tutor": "a tutor at a blackboard at night drawing three linked chalk circles and arrows, a single "
    "pupil at a desk, an oil lamp, chalk dust in the light, the rest of the room in shadow",
    "exp-two_bets": "a gambler at a green baize table at night placing two separate bets, two stacks of coins and "
    "two face-down cards, a single overhead lamp, the chair opposite empty, deep shadows",
    "exp-kipling": "a British Indian Ocean steamship at night, six lanterns burning in a row along her rail, a young "
    "boy at the bow looking out at a dark coast, stars and a low moon, the sea black",
    "exp-arc_de_triomphe": "the Arc de Triomphe in Paris at night, wet cobblestones reflecting a single streetlamp, "
    "a lone figure in a long coat looking up at the arch, deep shadows and mist, no text",
}

# The Market Harbour's three size bands (11 November, Justin: "3 cards that determine size bands for models.
# small 300k - 4B ... a medium band for 4 - 32B and then large is anything above 32B"): the harbour at three
# scales of ship, so the band cards read as one ladder of water rather than three labels.
BANDS: dict[str, str] = {
    "band-xsmall": "a sheltered harbour at dusk crowded with tiny rowing boats, skiffs and dinghies no longer than "
    "a man, drawn up on the mud and tied along the wet quay, lanterns just lit, one small sail out on the black water",
    "band-small": "a crowded harbour at night seen from the quay: dozens of small boats, dinghies, pilot cutters "
    "and fishing smacks packed along the wet stone, lanterns everywhere, one great ship far out on the dark water",
    "band-medium": "a harbour at night with a line of medium ships at anchor: brigs, frigates and merchantmen, "
    "their lanterns reflected in black water, a small rowing boat passing between them, the quay in shadow",
    "band-large": "a deep harbour at night with one immense ship of the line towering over the quay, dwarfing the "
    "smaller vessels around it, lanterns along its hull, moonlight on black water",
}

# The ladder in the soundings' language (9 November, Justin: "cards need to be updated with new fal images
# ... and the new names"): one image per rung, its metaphor rather than its ship.
LADDER: dict[str, str] = {
    "sounding": "a ship's lead line dropped into black water at night: a sailor heaving the line over the side, "
    "the coil of rope and its marked knots, lantern light on the swell, the lead glinting as it goes down",
    "survey": "a chart table at night aboard ship: a hand drawing soundings and depth marks on a sea chart, "
    "dividers and a brass compass, lamplight, a coast sketched in ink at the edge of the sheet",
    "landfall": "a lookout at the bow at dawn sighting land: a low dark coast on the horizon, the rigging taut, "
    "gulls, the first light on the water and the ship's shadow long behind her",
    "passage": "a ship under full sail threading a narrow passage between dark headlands at dusk, a beacon lit on "
    "the cliff, her wake trailing out behind her into the channel",
    "crossing": "a ship alone on a vast open sea in heavy weather: reefed sails, long swell, one lantern, the "
    "horizon empty in every direction",
    "ocean": "the open ocean at night, immense and black, a small ship's lantern on the swell, stars overhead and "
    "the faint line of the horizon",
    "new_world": "a ship's boat approaching an unknown shore at dawn: dense forest and a river mouth, the crew "
    "standing, the ship anchored beyond them in the bay",
}

# The chat console's plate (11 November, Justin: "the chat modal needs to be in the style of risso"): a
# merchantman's navigation panel, the carved oak and brass the console's rail is drawn from. Wide, for the bar.
CONSOLE: dict[str, str] = {
    "chat-console": "the navigation console of a merchantman at night: a wide panel of carved black oak set with "
    "brass instruments, a binnacle and compass, dividers and a parallel rule lying on an open chart, a rack of "
    "rolled sea charts, a small brass lantern lit at one end, rope lanyards and a worn handhold, the panel "
    "polished smooth by hands, the edge of the ship's wheel and dark rigging just visible at the sides",
}

# The test cards on the extra small leaderboard (12 November, Justin: "cards for each test ... with fal images
# the user must click and then they flip over with the leaderboard, but the card must have a picture that
# represents the test in our style"; "can you also add a card to xsmall for IFEval"). Each plate is the test's
# own idea in the world: ARC is a ship's school answering science questions four ways, chaining is two bearings
# crossing on a chart to fix a position neither gives alone, IFEval is written orders carried out to the letter.
TESTS: dict[str, str] = {
    "test-arc": "a ship's schoolroom below deck at night lit by one lantern: an old ship's master in a long "
    "Elizabethan sea-cloak holding up a burning candle as the question, and across the oak table a young "
    "apprentice in a ruffed shirt with long sleeves down to his knuckles choosing between four small slates laid "
    "in a row before him, each slate with a single chalk mark, his hand resting on one of the four, a brass "
    "globe, a lodestone and a sprouting seed in a dish beside them, through a porthole a thin ring of light "
    "arcing across the night sky",
    "test-chaining": "seen from above, a sea chart on a navigator's table at night lit by one lantern: a coastline "
    "drawn in ink with two small tower beacons on two far-apart headlands, and two long straight bold black ink "
    "lines ruled across the whole chart, one from each beacon, forming a large X that crosses at a single point "
    "out at sea, where the navigator's finger and the tip of a pair of brass dividers rest exactly on the crossing, "
    "a brass compass and a wooden parallel rule beside it, the navigator's sleeve an Elizabethan doublet, a small "
    "smooth silver ovoid drone with no propellers resting at the chart's corner",
    "test-ifeval": "a captain's written orders being carried out on the deck of an Elizabethan galleon at night: a "
    "parchment sheet with a red wax seal nailed to the mainmast under a hanging iron lantern, its writing only "
    "a column of tiny illegible ink strokes with a small drawn knot beside each, a boatswain in a doublet holding "
    "his finger on one line while a sailor kneeling beside him ties exactly that knot in a rope, a coil of rope "
    "laid out in a precise flat spiral on the planks, every order followed to the letter, a small smooth silver "
    "ovoid drone with no propellers resting on a yard above, a thin ring of light arcing across the sky",
}

# The ten houses that build the outside ships (12 November, Justin: "a new tab on the homepage for labs
# with the fal images ... the ten top producers of models as of today"). One plate per house, 16:9, for
# the Labs tab. A house is drawn as its yard or its hall at night, not as a model: the ship on the stocks
# carries the look its ships already wear in the Reach (LAB_LOOK above), so the card reads as its maker.
LABS: dict[str, str] = {
    "lab-google": "a great timber observatory-yard on a headland above a black sea at night: a four-masted "
    "ship stands on the stocks, her sails divided into four broad coloured panels, deep blue, red, yellow and "
    "green, a brass compass rose mounted at her bow, astronomers in long coats on a gallery of brass "
    "instruments, one hanging lantern, a thin ring of light standing where a moon would be",
    "lab-openai": "a stark black-timbered workshop on a dark quay: a fast black-hulled sloop on the stocks, one "
    "pale unbleached sail with a thin green stripe along the leech, a small brass lamp burning at the masthead, "
    "shipwrights in dark coats around a drafting table, black water beyond, one distant ring of light in the sky",
    "lab-anthropic": "a low hall of fired-clay stone built into a cliff at night, open to the wind: a long ship "
    "with three tall sails of burnt orange terracotta canvas, each crossed by a single dark seam, drawn up in the "
    "cove below, scholars in long coats reading at a lamplit table on the cliff edge, a brass telescope, the black "
    "sea and one thin ring of light in the sky",
    "lab-meta": "a great circular hall of dark stone at night open to the sky, a flooded ring basin at its "
    "centre: a ship at anchor there, her hull dark blue and her pale sail painted with an endless loop, figures "
    "in sea-cloaks along the encircling gallery, lanterns, one thin ring of light above",
    "lab-alibaba": "a red-lacquered boatyard on a dark river at night: a vast four-masted ship with red battened "
    "sails and jade-green trim, a gold circular medallion nailed to her stern, red paper lanterns along the rail, "
    "silk bales and spice sacks stacked on the wet quay, a low moon and one thin ring of light in the sky",
    "lab-microsoft": "a slate-blue timber yard on a dark harbour at night: a lean ship with a broad square sail "
    "clearly divided into four pale panes by heavy dark seams, her hull slate blue, a small silver pennant at the "
    "masthead, a great glowing four-paned window in the yard wall, a hooded figure with a lantern on the quay, one "
    "thin ring of light in the sky",
    "lab-deepseek": "a deep-water cove at night: a long low ship with a dark teal hull and a pale whale painted "
    "large on her black sail, lanterns on the black water, a whale's back breaking the surface beyond her, a low "
    "moon and one distant ring of light in the sky, an uncropped clean image with no watermark, no signature, no "
    "text and no logo",
    "lab-antgroup": "a small instrument-maker's hall at night: a swift black-lacquered two-masted cutter on the "
    "stocks, her sails deep indigo with a single silver ring on the main sail, red paper lanterns along the rail, "
    "brass instruments and a great astrolabe on a bench, a thin silver ring of light standing in the sky beyond",
    "lab-mistral": "a wind-swept boatyard on a dark Provencal coast at night: a lean lateen-rigged ship with sails "
    "striped ochre and white, a north-wind emblem on the main sail, cypress trees and a stone tower, a mistral "
    "blowing, lanterns, one thin ring of light in the sky",
    "lab-xai": "a black forge on a dark plain at night: a stark black-hulled sloop on the stocks, a single white X "
    "painted on her pale sail, an iron furnace throwing sparks, a lone figure in a long coat, one thin ring of "
    "light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-moonshot": "a moonlit boatyard on a dark Chinese river at night: a swift three-masted junk with pale "
    "silver sails bearing a single crescent moon, silver-white trim on her hull, a round moon gate in the yard "
    "wall, lanterns along the wet quay, a low full moon and one thin ring of light in the sky, an uncropped "
    "clean image with no watermark, no signature, no text and no logo",
    "lab-zai": "a lantern-lit observatory-yard on a dark Chinese hill at night: a lean three-masted junk with "
    "deep violet sails bearing a single gold lantern emblem, a great brass armillary sphere on the wet quay, "
    "paper lanterns along the rail, a thin ring of light in the sky, an uncropped clean image with no "
    "watermark, no signature, no text and no logo",
    "lab-minimax": "a twin-hulled boatyard on a dark Chinese river at night: two narrow hulls joined by a "
    "moonlit deck, sails of teal and red, a beam of projector light cutting across the black water, red paper "
    "lanterns, a thin ring of light in the sky, an uncropped clean image with no watermark, no signature, no "
    "text and no logo",
    "lab-cohere": "a northern stone harbour at night under a pale aurora: a lean grey-hulled ship with a pale "
    "sail divided into a grid of small panes, a brass reading lamp on the snow-dusted quay, dark pines behind, "
    "a thin ring of light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-nvidia": "a forge-yard lit by green fire at night: a black-hulled ship with sails the colour of dark "
    "green glass, a great anvil and iron gears on the quay, sparks rising, a thin ring of light in the sky, an "
    "uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-stepfun": "a stair of stone quays climbing a dark cliff at night: a ship at each step, the highest "
    "with pale sails marked by a single silver step, lanterns on the wet stone, a thin ring of light in the sky, "
    "an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-bytedance": "an orchard-yard at night: a ship with sails of pale seed-pod white, a great round seed "
    "vault door in the yard wall, lanterns among the trees, a thin ring of light in the sky, an uncropped "
    "clean image with no watermark, no signature, no text and no logo",
    "lab-thinkingmachines": "a workshop of ink and brass at night: a ship with black ink-dark sails and brass "
    "ribs on the stocks, a drafting table and open notebooks, a single lamp throwing hard shadows, a thin ring "
    "of light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-tii": "a desert harbour under a field of stars: a lean dhow-like ship with pale sails bearing a falcon "
    "silhouette, black water and pale sand, a low moon, a thin ring of light in the sky, an uncropped clean "
    "image with no watermark, no signature, no text and no logo",
    "lab-cognition": "a chart room of brass and clockwork at night: a ship model with clockwork gears in its "
    "hull on a navigator's table, open charts and dividers, a single lamp, a thin ring of light in the sky, an "
    "uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-arcee": "a small yard of patchwork hulls at night: a ship with sails sewn from many pale panels, a "
    "rack of small hulls waiting beside her, one lantern on the wet boards, a thin ring of light in the sky, an "
    "uncropped clean image with no watermark, no signature, no text and no logo",
    # Ai2 and H Company (12 November, Justin: "add the labs behind molmo web and holo ... with a fal image")
    "lab-ai2": "an open boathouse on a dark northern bay at night with every door and shutter thrown wide: a "
    "ship on the stocks with half her planking left off so her keel and ribs stand bare, her sails the pink of "
    "a dawn sky, shipwrights in long coats beside a long table of open ledgers, each plank's timber and "
    "origin written out for anyone to read, dark pines behind, one lantern, a thin ring of light in the sky, "
    "an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-hcompany": "a mapmaker's atelier on a stone quay beside a dark river in Paris at night: a lean cutter "
    "on the stocks with sails of deep green and cream, a huge painted chart on the wall and a young pilot "
    "touching one exact mark on it with a long brass pointer, an arched stone bridge strung with lanterns "
    "behind, a thin ring of light in the sky, an uncropped clean image with no watermark, no signature, no "
    "text and no logo",
    # Maincode (12 November, Justin: "can you add maincoders lab to masaq reach"): a southern yard that
    # raises its own mainmast, under the four-pointed star of its flag.
    "lab-maincode": "a shipyard on a cold southern bay at night, black water and a low wind: a tall ship on the "
    "stocks with her mainmast stepped and her rigging half set, a great white four-pointed star painted on her "
    "pale sail, shipwrights in long coats working around a forge and a bench of brass instruments, the lanterns "
    "of a low town along the far shore, a thin ring of light in the sky, an uncropped clean image with no "
    "watermark, no signature, no text and no logo",
    # The three regional houses (12 November, Justin: "also add the best lab from the UK and South Africa and
    # South America"): a pilot that finds its own way, a family hall, and a songbird on a green-and-gold sail.
    "lab-wayve": "a pilot cutter running through fog on a black sea at night with no chart aboard: a great glass "
    "lantern at her masthead throwing a long cone of light on the water ahead, a brass wheel turning itself at "
    "the helm, a low dark coast with the lanterns of a city beyond, a thin ring of light in the sky, an uncropped "
    "clean image with no watermark, no signature, no text and no logo",
    "lab-lelapa": "a family compound on a dark southern hillside at night: a low round hall of stone and thatch, a "
    "small swift ship on the stocks beside it with sails of ochre and indigo, a circle of lanterns and people "
    "around a fire, the four stars of the Southern Cross above, a thin ring of light in the sky, an uncropped "
    "clean image with no watermark, no signature, no text and no logo",
    "lab-maritaca": "a river boatyard beneath a dark tropical hill at night: a swift two-masted ship with sails of "
    "green and gold, a sabiá bird painted on the main sail, a great brass telescope on the wet quay, fireflies "
    "and lanterns among the palms, a thin ring of light in the sky, an uncropped clean image with no watermark, "
    "no signature, no text and no logo",
    # The six houses of 12 November, and the Research view beside the Labs: a federation of yards, an open
    # print shop, eleven Cape lanterns, many hands on one hull, a national archive, and a southern yard.
    "lab-flower": "a great stone boathouse on a dark tidal river at night: one ship on the stocks assembled from "
    "timbers cut in many different yards, each plank bearing a different maker's mark, shipwrights around a long "
    "table joined by a single taut brass thread, a lantern at every bench, a low stone bridge beyond, no clock "
    "tower, no modern skyline, a thin ring of light in the sky, an uncropped clean image with no watermark, no "
    "signature, no text and no logo",
    "lab-stability": "a dark Elizabethan quay at night: a ship's painter at a great wooden easel painting a ship in "
    "four colours on a broad canvas, pots of pigment on the stones, candles in glass lanterns at the easel's feet, "
    "a moored ship on the black water beyond, no electric lights, no signs, no labels, no text, a thin ring of "
    "light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-uctnlp": "a stone hall on a dark Cape Town slope at night under a great flat mountain: eleven small lanterns "
    "in a row along a long table, a small two-masted ship on the stocks beside it with plain sails marked in eleven "
    "different patterns, open notebooks in many scripts, the Southern Cross above, a thin ring of light in the sky, "
    "an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-masakhane": "a village of many hands building one ship at night: a dozen shipwrights from different coasts "
    "around a single dark hull, each arriving with one plank under an arm, a great common table of open ledgers, "
    "lanterns hung between the trees, a thin ring of light in the sky, an uncropped clean image with no watermark, "
    "no signature, no text and no logo",
    "lab-sadilar": "a great stone archive on a dark southern plain at night: long shelves of sealed ledgers and "
    "rolled charts, a keeper with a lantern walking between them, a small ship model under glass on a reading "
    "table, the Southern Cross through a high window, a thin ring of light in the sky, an uncropped clean image "
    "with no watermark, no signature, no text and no logo",
    "lab-sovereign-au": "a broad southern plain at night: a great timber hall with a half-built ship on the stocks, "
    "a map of Australia chalked across the floor, rows of small lanterns stretching away across the plain, "
    "shipwrights at work by the light of the hall, the Southern Cross above, a thin ring of light in the sky, an "
    "uncropped clean image with no watermark, no signature, no text and no logo",
    # The research houses by country (12 November): an open hall, two Chinese yards, a civic hall, a Paris
    # voice room, a Brazilian study, a national hall, a Montreal winter and a Gulf courtyard.
    "lab-eleutherai": "a great open hall of unsealed books at night: every door and shutter thrown wide, a ship on "
    "the stocks with plain undyed sails, scholars copying her plans at a long table by one shared lantern, no lock "
    "on the door, a thin ring of light in the sky, an uncropped clean image with no watermark, no signature, no "
    "text and no logo",
    "lab-shanghai-ai": "a great timber yard on a dark Chinese river at night: a four-masted ship with red battened "
    "sails and a great brass compass mounted on the quay, astronomers with brass instruments around a table of "
    "charts, red paper lanterns along the rail, a thin ring of light in the sky, an uncropped clean image with no "
    "watermark, no signature, no text and no logo",
    "lab-baai": "a beacon tower on a dark hill above a city at night, its great light sweeping the water: a ship on "
    "the stocks below, open crates of scrolls and a brass instrument on a bench, lanterns on the wet stones, a thin "
    "ring of light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-southern-cross": "a civic hall on a dark southern plain at night: a half-built ship on the stocks, a great "
    "map of Australia chalked across the floor, a long table of open ledgers, lanterns along the wall, the Southern "
    "Cross above, a thin ring of light in the sky, an uncropped clean image with no watermark, no signature, no "
    "text and no logo",
    "lab-kyutai": "a Paris laboratory of brass speaking trumpets and glass resonators at night: a lean ship with a "
    "great brass horn at her bow, open plans and coiled wire on a bench, candles in glass lanterns, an arched "
    "window on the black river, a thin ring of light in the sky, an uncropped clean image with no watermark, no "
    "signature, no text and no logo",
    "lab-nilc": "a study in a Brazilian town at night: a toucan on a perch beside a small ship model with green and "
    "gold sails, open Portuguese folios and a brass lamp on the desk, a shuttered window on a dark garden, a thin "
    "ring of light in the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
    "lab-turing": "the windowless interior of a great national hall of pale stone at night: a ship model under glass "
    "on a long table, scholars in dark coats around charts and brass instruments, one lamp throwing hard shadows, a "
    "high carved stone wall, a thin ring of light falling from a high lantern opening in the roof, no city, no "
    "skyline, no windows, no modern buildings, no electric light, an uncropped clean image with no watermark, no "
    "signature, no text and no logo",
    "lab-mila": "a Montreal hall in winter at night: snow beyond the tall windows and dark pines, a ship on the "
    "stocks, a great blackboard covered in chalk diagrams, a fire in an iron grate, a few figures talking beside it, "
    "no city, no skyline, no modern buildings, no electric light, a thin ring of light in the sky, an uncropped "
    "clean image with no watermark, no signature, no text and no logo",
    "lab-mbzuai": "a desert university courtyard at night: a ship on the stocks beneath a colonnade, a great brass "
    "astrolabe on a stone table, lanterns along the arcade, the dark Gulf beyond the wall, a thin ring of light in "
    "the sky, an uncropped clean image with no watermark, no signature, no text and no logo",
}

# The embeddings ontology's categories (12 November, Justin: "cards for the embeddings in the culture drake
# risso style for the major categories"), on Masaq' Reach › Embeddings. Keys are `emb-<node key>` from
# frontend/src/components/islands/EmbeddingOntology.tsx. Each plate is the category's idea aboard ship: the
# ship's own grain (inside), a foreign maker's instrument (outside), small hand instruments against a great
# hired one (small and large), a channel found by chaining marks (reasoning), a tally of words (sparse), a
# rutter whose every panel knows the whole coast (contextual), the sketch beside the log (multimodal), and two
# copies compared line by line (the exact-text neighbours).
EMBEDDINGS: dict[str, str] = {
    "emb-inside": "inside the hull of a wooden ship at night, the curved ribs and knees of her frame lit by one "
    "hanging lantern, every timber cut with the shipwright's own chiselled marks, an adze resting on a beam, the "
    "grain of the oak running the length of her like veins, the ship's own body and nothing brought aboard",
    "emb-outside": "a ship's master at the chart table holding up a strange brass instrument of foreign make "
    "to the lantern light, finer and newer than anything aboard, its rings engraved with marks he cannot read, "
    "his own worn compass and dividers set aside on the chart, a small silver drone hovering at his shoulder",
    "emb-dense-small": "a ship's log open on a narrow desk in a cramped cabin, a small pocket compass, slim brass "
    "dividers and a hand lens laid across the page, a single candle, small exact instruments for one man's "
    "hand, the porthole showing black water and a thin ring of light in the sky",
    "emb-dense-large": "a great brass armillary sphere mounted on the quarterdeck, taller than a man, two "
    "sailors straining at the handles to turn it, hired at a far port and lashed down with heavy rope, its "
    "rings catching the moonlight, the ship's own small instruments dwarfed beside it",
    "emb-reasoning": "a pilot bent over a chart of a reef-strewn coast tracing a hidden channel, pins set at "
    "distant soundings and a single taut thread run from mark to mark until the passage appears that no one "
    "mark shows, the lantern throwing the thread's shadow across the reefs",
    "emb-sparse": "a purser's tally board and an open ledger by lamplight, each word of a cargo list given its "
    "own column of notches, a knotted cord laid beside it with one knot to a word, a quill and a ruler pinned "
    "against a single line of figures",
    "emb-contextual": "a long rutter of coastal views unrolled along the full length of a table, panel after "
    "panel of headlands and harbour mouths drawn edge to edge so that every panel joins the next and the whole "
    "coast reads as one, the navigator's hand resting on the middle panel, a lantern at each end",
    "emb-multimodal": "an artist aboard ship sketching a newly sighted coastline in ink on the very page where "
    "the master writes the log, picture and words side by side on one sheet, the real headland visible "
    "through the open stern window beyond, a small silver drone perched on the window ledge",
    "emb-neighbours": "two scribes at a candlelit table comparing two copies of the same manuscript line by "
    "line, a straightedge laid across both pages, one finger stopped on a single matching word, a seal and "
    "wax beside them, exact copying checked letter for letter",
}

# Demiton's four sections as image cards (12 November, Justin: "this page /orbitals/demiton should rather
# have fal images for its four sections: Berth, Shipyard, Library, Expeditions ... to allow the user to
# navigate"). Named demiton-<section>; the frontend lists them in DEMITON_SECTIONS (views/harbours.ts).
DEMITON_SECTIONS: dict[str, str] = {
    "demiton-berth": "a fitting-out berth along the inner rim of an Orbital at night: small and great wooden "
    "hulls of every size lying side by side on cradles and at moorings, lanterns at each bow, riggers in the "
    "masts, a harbour-master with a ledger on the quay, the curved lit bands of the ring overhead",
    "demiton-shipyard": "a drafting loft above a working shipyard at night: a great table spread with hull "
    "plans and a ship's lines, brass dividers and a model hull, through a wide window the half-built keel on "
    "the stocks below with scaffolding and lanterns, a small silver drone perched on the plans",
    "demiton-library": "a vaulted ship's library at night: towering shelves of folios and rolled charts "
    "climbing into shadow, a scholar on a rolling ladder with a lantern, a reading desk with an open book "
    "and a brass armillary sphere, a small silver drone resting on a shelf, one lamp throwing hard shadows",
    "demiton-expeditions": "a ship's company at the foot of a gangway at night about to sail: the captain "
    "unrolling a chart of unnamed coasts on a cask-head, sailors loading the last stores by lantern, a great "
    "galleon behind them with sails loosed, black water ahead and a thin ring of light in the sky",
    # Demiton's discoveries, the field on two axes (13 November, Justin: "should only have the 2 axis cards with a
    # fal image"): the kind of claim is a cabinet sorting findings by their nature; the object of study is the ship
    # itself laid open, each part under its own lens
    "discoveries-kind-of-claim": "a navigator's chart room at night: a great oak cabinet of seven deep pigeonholes, "
    "each holding a different instrument — a brass balance, a set of interlocking gears, a compass rose, a spyglass, "
    "a snapped length of mast, a bound book of recipes, a surveyor's measuring rod — a navigator in a sea-cloak "
    "sorting sealed letters and logbook pages into them by lantern light, a small smooth silver ovoid drone with "
    "no propellers resting on top of the cabinet, the thin lit ring of an Orbital through the window",
    # the first draw put an aeroplane in the window (the drone "above the model") and barely cut the hull open: the
    # drone now rests on the table and the cross-section is the subject
    "discoveries-object-of-study": "a natural philosopher's cabin aboard a galleon at night: on a long table a large "
    "wooden cross-section model of a galleon cut open lengthwise, every deck, the hold with its casks and stores, "
    "the guns, the rudder and the rigging shown inside, several brass magnifying lenses on jointed arms each held "
    "over a different part, a philosopher in a long coat bent over one lens, one hanging lantern, a small smooth "
    "silver ovoid drone with no propellers resting on the table beside the model, black water and the thin ring of "
    "an Orbital through the stern windows, no aircraft, no flying machines",
    # the seven kinds of claim, one plate each (13 November, Justin: "can you add fal images here
    # http://localhost:4321/orbitals/demiton/discoveries/kind-of-claim"): what each kind of finding looks like aboard
    # first draws (13 November): laws hung an electric dome lamp, recipes a bare bulb and a lettered poster, limits
    # sailed past the shore instead of running aground, measurement put a sailor in a modern cap with no log line;
    # each now says its light and its action outright
    "discoveries-claim-laws": "a long table in a ship's great cabin at night with seven model ships in a row graded "
    "from a thumb-sized cutter to a great galleon, a navigator above them drawing one smooth rising curve on a chart "
    "with brass dividers, lit only by a candle burning inside an iron ship's lantern, no electric light, a small "
    "smooth silver ovoid drone with no propellers resting at the end of the row, the thin lit ring of an Orbital "
    "through the stern windows",
    "discoveries-claim-mechanisms": "a ship's clockmaker's workshop below decks at night: the brass case of a great "
    "marine chronometer lies open with its gear trains, springs and escapement exposed, a craftsman with a loupe "
    "tracing one train of gears with a fine brass pointer, tools laid out on a leather roll, one hanging lantern, "
    "a small smooth silver ovoid drone with no propellers resting beside the case",
    "discoveries-claim-representations": "a cartographer's cabin at night: a great dark celestial globe in brass "
    "meridian rings, fine coloured threads stretched from its centre outward to brass pins in many directions, a "
    "cartographer in a sea-cloak tightening one thread, one lantern, a small smooth silver ovoid drone with no "
    "propellers resting on the chart table, the thin ring of an Orbital through the window",
    "discoveries-claim-behaviours": "a dark rowing boat at night on black water, an observer in a sea-cloak watching "
    "a great galleon through a long brass spyglass while a companion writes in a logbook by a shielded lantern, the "
    "galleon's crew at work on deck by lantern light in the distance, the thin lit ring of an Orbital in the sky",
    "discoveries-claim-limits": "a wrecked galleon stranded on black rocks at night, heeled hard over on her side "
    "with her hull holed, her foremast snapped and her sails torn and hanging, surf breaking white over the rocks "
    "around her, in the foreground a lookout in a sea-cloak holding up a candle lantern beside a torn chart, the "
    "thin lit ring of an Orbital in the sky",
    "discoveries-claim-recipes": "a shipwright's loft at night: a master shipwright in a leather apron showing two "
    "apprentices how to bend a long steamed oak plank over a ship's rib frame, a heavy bound book of methods open "
    "on the bench beside a steaming wooden steam box, adzes and mallets hanging on the timber wall, lit only by "
    "candle lanterns, no electric light, no posters, a small smooth silver ovoid drone with no propellers on the "
    "bench, the thin ring of an Orbital through a high window",
    "discoveries-claim-measurement": "the high stern of a galleon at night: a sailor in a knitted wool cap and a "
    "canvas smock holding a wooden reel while a knotted rope runs out from it over the stern rail into the churning "
    "wake behind a floating wooden chip, a second sailor holding up a small sand-glass, a midshipman counting the "
    "knots aloud by a candle lantern, a slate of chalked figures on the rail, the thin lit ring of an Orbital in "
    "the sky",
    # the Liberty Machine (12 November, Justin: "Liberty Machine should have it's own card here http://localhost:4321/orbitals/demiton
    # with a fal image"): Beer's five systems as a flagship's council, each at its own post around one table
    # the first draw hung an electric pendant lamp; a second, pushed to "Elizabethan", came out grey with a
    # cowboy hat. This keeps the first's colour and night sea and says the lantern outright
    "demiton-liberty-machine": "the great cabin of a flagship at night as its council sits around one long table under a "
    "single swinging ship's lantern with a candle inside: the captain at its head with the sealed articles "
    "of the voyage under his hand, the purser with an open ledger and an iron strongbox, the sailing master "
    "with brass dividers over a chart, the boatswain with a coiled line, through the stern windows a "
    "lookout's lantern high in the rigging of a second ship and the thin lit ring of an Orbital in the sky, "
    "a small silver drone perched on the back of the captain's chair",
}

# The Liberty Machine page's five cards, one a system (12 November, Justin: "http://localhost:4321/liberty-machine should have 5 cards
# with a fal image for each level"). Each system as the post aboard that does its work; named liberty-machine-s1 … liberty-machine-s5,
# listed in the frontend's LibertyMachineCards.tsx.
LIBERTY_MACHINE_SYSTEMS: dict[str, str] = {
    "liberty-machine-s1": "the main deck of a great wooden ship at work by lantern-light at night: sailors hauling on a "
    "line together, a man aloft loosing a sail, stores being swung aboard in a cargo net, the hatch open on "
    "a hold stacked with casks and bound books, the curved lit band of an Orbital ring overhead",
    # the first draw gave a modern lighthouse and electric quay lamps: the fire basket and torches are said
    "liberty-machine-s2": "a harbour mouth at night in deep blues and amber seen from a pilot's rowing boat: a pilot "
    "standing in the stern with a raised lantern signalling, two great wooden galleons easing through the "
    "narrow channel one behind the other, an old stone watchtower on the mole with an iron fire basket "
    "burning at its top, pitch torches along the quay, black water and reflected firelight, the thin ring "
    "of an Orbital in the sky",
    "liberty-machine-s3": "a purser's cabin below decks at night: the purser at a narrow desk counting coin from an iron "
    "strongbox into a ledger by a single candle, a second officer leaning over his shoulder checking the "
    "figures with a finger on the page, a ship's papers sealed with wax, keys on a ring, deep shadow",
    "liberty-machine-s4": "a lookout high in the crow's nest of a wooden ship at night with a long brass spyglass to his "
    "eye, far off on the horizon the lit sails of strange foreign ships and an unknown coast, a small silver "
    "drone hovering beside him, the thin ring of an Orbital arcing across the stars",
    "liberty-machine-s5": "an admiral alone at a carved desk in a stern cabin at night pressing his seal into hot red wax "
    "on the articles of the voyage, a single candle, a quill and inkhorn, a sword hung on the bulkhead, "
    "through the leaded window the fleet's lanterns at anchor and the faint ring of an Orbital",
}

# The fleet under S1 (12 November, Justin: "under Liberty Machine S1 Operations we have a fleet of drones. The first
# drone in the fleet will be the browser drone ... with a fal image in our style"). The browser drone is
# the Culture's small silver ovoid at work: no propellers, one lens, reading a page the way a navigator
# reads a chart. It is the drone the art has been placing in the rigging all along, given a job.
DRONES: dict[str, str] = {
    "drone-browser": "the chart room of a great wooden ship at night: a small silver ovoid drone with no "
    "propellers and a single dark glass lens at its front hovering low above an open chart spread on the "
    "table, a thin cone of pale light from the lens falling across the chart and picking out a coastline "
    "and its soundings, brass dividers, a sandglass and an open ship's log beside it, one hanging lantern "
    "with a candle throwing hard shadows across the table and the beams, through the stern windows the "
    "thin ring of an Orbital standing where a moon would be over black water",
    # D2, the email drone (12 November): the same ovoid at the writing desk, reading a letter rather than
    # a chart. The letter rack, the wax seal and the inkhorn are the age of sail's own mail.
    "drone-email": "the great cabin of a flagship at night, in the foreground a small matte silver metal "
    "ovoid machine, smooth and seamless and about the size of a melon, resting on the writing desk beside "
    "an open letter, a single dark glass lens set into its front like an eye, clearly a machine and not a "
    "lamp, a thin cone of pale light from that lens falling across the letter and its broken red wax seal, "
    "a brass rack of sealed letters and a bundle tied with ribbon behind it, a quill and an inkhorn, a "
    "sandglass and a folded reply on the desk, a candle in a brass holder at the left throwing hard "
    "shadows across the cabin and the carved chair, no hanging lamp, through the stern windows a thin "
    "luminous ring standing where a moon would be over black water, no moon",
    # D3, the phone drone: the same ovoid beside the age of sail's telephone, a brass speaking trumpet.
    "drone-phone": "the great cabin of a flagship at night, in the foreground a small matte silver metal "
    "ovoid machine, smooth and seamless and about the size of a melon, resting on the desk beside a long "
    "straight brass speaking trumpet of the Elizabethan age, plain and conical with no cord, no wire, no "
    "handle and no mouthpiece, clearly an instrument of the age of sail and not a modern telephone, a "
    "single dark glass lens set into the ovoid's front like an eye turned toward the trumpet's mouth, a "
    "thin cone of pale light from that lens falling across the brass, a signal lantern with a candle at "
    "the left throwing hard shadows across the cabin, a coiled line of rope and a sealed dispatch beside "
    "them, no hanging lamp, through the stern windows a thin luminous ring standing where a moon would be "
    "over black water, no moon, no electrical cord, no plastic",
}

SIZES = {**{k: "landscape_16_9" for k in (*DEMITON_SECTIONS, *LIBERTY_MACHINE_SYSTEMS, *DRONES, *CLASSES,*TESTS, *LABS, *HARBOURS, *HARBOUR_VIEWS, *SHIPBUILDER, *SHIPYARD, *SHIPYARD_SECTIONS, *CHARTING, *POSITIONS, *FOREIGN, *SOP_GOALS, *EXPEDITIONS, *BANDS, *LADDER, *CONSOLE, *EMBEDDINGS)}, **{k: "portrait_4_3" for k in CARDS}, **{k: "portrait_4_3" for k in LOGIC}}
SUBJECTS = {**DEMITON_SECTIONS, **LIBERTY_MACHINE_SYSTEMS, **DRONES, **TESTS, **LABS, **CLASSES, **HARBOURS, **HARBOUR_VIEWS, **SHIPBUILDER, **SHIPYARD, **SHIPYARD_SECTIONS, **CHARTING, **POSITIONS, **FOREIGN, **CARDS, **LOGIC, **SOP_GOALS, **EXPEDITIONS, **BANDS, **LADDER, **CONSOLE, **EMBEDDINGS}

# The twenty subjects the audit found outside the brief (ships/reports/art-audit-2026-11-11.md): rewritten
# into the three-layer world -- Risso's ink, Drake's voyages, the young Culture's universe -- keeping what
# tells each lab apart. They override the dicts above rather than editing them in place, so the old wording
# stays visible beside the reason it changed. The Chinese junk became a captured Portuguese carrack with a
# red-lacquered stern (Drake took the Sao Filipe); the Venetian carrack and the Byzantine dromon became the
# English hulls of the same size; the Greek and Victorian scenes became Elizabethan ones.
REVISED: dict[str, str] = {
    # 11 November: the art audit found these two drawing the real world -- a steamship, and the Arc de
    # Triomphe in Paris with electric lamps -- in a world that has neither
    "exp-kipling": "a great wooden ship at anchor at night with a cargo of books, lanterns in a row along her "
    "rail, a boy at the bow looking up at the lights, crates of folios lashed on the deck, a thin ring of light "
    "standing where a moon would be",
    "exp-arc_de_triomphe": "a great triumphal arch of dark stone raised on a headland above the sea at night, "
    "seen from a ship's deck, a lone figure in a long coat before it, sea birds and rigging in the foreground, "
    "a faint ring of light in the sky beyond the arch",
    "pan": "a privateer captain alone at a small table on a ship's deck under the open night sky, playing "
    "cards against an unseen hand, the stars and a distant ring of light above the black sea, his own cards "
    "held close, a lantern on the table",
    "augustus": "an Elizabethan schoolmaster in a long gown teaching arithmetic by candlelight, chalk in hand "
    "at a slate of simple sums, a hornbook and a counting board, boys in doublets at their benches, one candle "
    "throwing hard shadows across the room",
    "plato": "an Elizabethan scholar in a long gown walking a lamp-lit gallery with a few students, pointing up "
    "at the heavens through an arched window, his long shadow thrown across the stone floor",
    "diderot": "an Elizabethan compiler at a vast crowded writing desk by candlelight, towers of quartos and a "
    "great commonplace book open, brass dividers and a pot of ink, shelves of folios behind him",
    "qwen3-4b": "a vast four-masted captured carrack with a high red-lacquered stern castle, riding at anchor "
    "in a crowded night harbour, silk bales stacked on her deck below lanterns",
    "qwen3-1-7b": "a two-masted English galleon under full sail on a dark sea, a red-lacquered stern and silk "
    "pennants aloft, a low moon behind cloud",
    "qwen3-0-6b": "a small single-masted pinnace slipping out of a narrow harbour mouth at dusk, one red lantern "
    "lit at the stern, a silk trade pennant at the masthead",
    "qwen3-8-27b": "an enormous four-masted captured flagship at anchor in a wide night harbour, red-lacquered "
    "stern and battened silk sails half set, the black water full of her lanterns",
    "qwen3-30b-a3b": "a three-masted English galleon in a wide night harbour, red-lacquered stern castle, silk "
    "bales and spice sacks stacked on the quay below her",
    "qwen3-0-6b-base": "a small single-masted pinnace slipping out of a narrow harbour at dusk, her canvas "
    "plain and undyed, no lanterns, the houses dark behind her",
    "qwen3-5-0-8b-base": "a small two-masted pinnace under plain undyed canvas on a dark estuary, no lanterns "
    "lit, a low moon behind cloud",
    "qwen3-5-0-8b": "a small two-masted pinnace slipping down a narrow estuary at dusk, red-lacquered trim on "
    "her rail, one red lantern lit at the stern",
    "phi-2": "a lean two-masted English pinnace with a bronze bow-chaser, gliding out of a dark harbour mouth "
    "at night, oars and sail, her hull low in the black water",
    "phi-4-14b": "a lean two-masted privateer gliding out of a dark harbour mouth at night, oars lifting in a "
    "row, a low moon behind cloud, a silver pennant at the masthead",
    "gemma-3-4b": "a four-masted English galleon under full sail on a dark open sea, high stern and broad "
    "beam, her painted sail panels in four colours the brightest thing on the water",
    "gemma-4-26b-a4b": "a broad-beamed four-masted galleon at anchor in a lantern-lit night harbour, her "
    "coloured sail panels furled, a brass compass rose at the bow",
    "gemma-4-31b": "a towering four-masted English flagship at night, every coloured sail panel full, high "
    "stern and broad beam, dwarfing the boats around her",
}
for _k, _v in REVISED.items():
    if _k in SUBJECTS:
        SUBJECTS[_k] = _v



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
