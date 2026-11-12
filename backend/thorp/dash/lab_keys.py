"""Write the Reach's house addresses where the frontend can import them.

The house pages (`/orbitals/masaq/<country>/<key>`, `/masaq/<country>/<key>` and `/labs/<key>`) are
pre-rendered, so their routes need the house list at build time, and an Astro page cannot import Python.
This writes `frontend/src/data/labs.json` from `thorp.labs.listed()` — the same rows the Labs page draws —
so every card the Reach links has a page, and a house added to `s4.labs` is one export away from its route
rather than three hand-edited arrays.

Re-run this whenever the Reach's houses change:

    python -m thorp.dash.lab_keys
"""

from __future__ import annotations

import json
from pathlib import Path

from thorp import labs, paths


def write() -> Path:
    out = paths.FRONTEND / "src" / "data" / "labs.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    listed = labs.listed()
    houses = ",\n  ".join(json.dumps([lab.country, lab.key]) for lab in listed)
    keys = ", ".join(json.dumps(lab.key) for lab in listed)
    out.write_text('{\n "houses": [\n  ' + houses + '\n ],\n "keys": [' + keys + ']\n}\n')
    return out


if __name__ == "__main__":
    print(write())
