"""Write the foreign ships' keys where the frontend can import them.

The route /foreign/<key> is pre-rendered, so it needs the key list at build time, and the page cannot
import Python. This writes frontend/src/data/foreign.json from thorp.foreign.models() — the same registry
that builds the Market Harbour's cards — so every ship the harbour links gets a page (10 November:
/foreign/qwen3-1-7b was a 404 in dev while the harbour linked it, because this list was written from the
shape table in thorp.models.registry.FOREIGN, which is about widths and depths, not about which outside
models have been read).

Zayton's foreign cards are built from readings (`s4.outside_readings`) and chain grades, so a new outside
model is one reading away from a harbour card. Re-run this whenever the harbour's list changes:

    python -m thorp.dash.foreign_keys
"""

from __future__ import annotations

import json
from pathlib import Path

from thorp import foreign, paths


def keys() -> list[str]:
    """The harbour's keys, in its order, once each (two checkpoints of one label share a key)."""
    return list(dict.fromkeys(m["key"] for m in foreign.models()))


def write() -> Path:
    out = paths.FRONTEND / "src" / "data" / "foreign.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # the key list for getStaticPaths, and the model id -> label key map the competitor redirect needs;
    # both read from the store through thorp.foreign.models(), so the file is a build artifact, not a source
    models = {m["model"]: m["key"] for m in foreign.models() if m.get("model")}
    out.write_text(json.dumps({"keys": keys(), "models": models}, indent=1) + "\n")
    return out


if __name__ == "__main__":
    print(write())
