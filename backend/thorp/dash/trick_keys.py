"""Write the tricks' and chains' keys where the frontend can import them (13 November, Justin: "fix the trick pages
so every trick has a page").

Each trick of the trade has a page under Demiton's discoveries (/orbitals/demiton/discoveries/<key>), and each of
the explorer's four discovery chains has one (/chains/<key>). Those routes are pre-rendered, so the build needs the
key lists, and the page cannot import Python. Until now the list was typed by hand in lib/discoveryPaths.ts and had
30 of the 65 tricks, so a pasted address for any other (few_shot, say) was a 404 while clicking through worked.

This writes frontend/src/data/tricks.json from the registries the pages are drawn from: thorp/dash/tricks.py's
KNOWN_TRICKS (the trick page looks a trick up by its key) and thorp.fleet.CHAINS. Re-run it whenever either changes
(tests/test_trick_keys.py fails until you do):

    python -m thorp.dash.trick_keys
"""

from __future__ import annotations

import json
from pathlib import Path

from thorp import paths


def keys() -> dict[str, list[str]]:
    """{"tricks": every known trick's key, in the registry's order; "chains": the explorer's discovery chains}."""
    from thorp import fleet
    from thorp.dash.tricks import KNOWN_TRICKS

    return {"tricks": [t["key"] for t in KNOWN_TRICKS], "chains": list(fleet.CHAINS)}


def target() -> Path:
    return paths.FRONTEND / "src" / "data" / "tricks.json"


def write() -> Path:
    out = target()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(keys(), indent=1) + "\n")
    return out


if __name__ == "__main__":
    print(write())
