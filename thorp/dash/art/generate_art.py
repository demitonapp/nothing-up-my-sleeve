#!/usr/bin/env python3
"""The dashboard's art (2026-11-07): one image per class of ship and one per playing card.

Eduardo Risso style, matching the monorepo's Atlas generators (packages/ui/apps/atlas/scripts/
generate-*-art.py): noir, heavy black ink, stark chiaroscuro, a single light source, no text. Made with
fal (fal-ai/flux/dev). Saved to thorp/dash/web/public/art/<key>.png, which the build copies into the
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
OUT_DIR = HERE.parent / "web" / "public" / "art"
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
    "bettor": "a three-masted barque sailing off the edge of the known chart toward an uncharted island in "
    "fog, a figure in the bow with a brass telescope raised, the old chart pinned beside him ending in blank paper",
    "summit": "a towering full-rigged ship of the line cresting an enormous wave, every sail set, the "
    "masts reaching up into a field of stars, lightning behind, the largest ship on the sea",
}

# The playing cards: the stars that do the trick (fleet.STARS / fleet.METHODS["chaining"] cards). Portrait,
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
}

SIZES = {**{k: "landscape_16_9" for k in CLASSES}, **{k: "portrait_4_3" for k in CARDS}}
SUBJECTS = {**CLASSES, **CARDS}


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
            print(f"{name}: wrote {out.relative_to(HERE.parents[2])}", flush=True)
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
