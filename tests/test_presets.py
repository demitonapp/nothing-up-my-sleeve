import re
from pathlib import Path

from thorp.models.registry import PRESETS

PKG = Path(__file__).resolve().parent.parent / "thorp"


def test_preset_names_only_in_registry():
    offenders = []
    for f in PKG.rglob("*"):
        if f.suffix not in (".py", ".html") or f.name == "registry.py":
            continue
        text = f.read_text(encoding="utf-8")
        for name in PRESETS:
            if re.search(rf"""["']{re.escape(name)}["']""", text):
                offenders.append(f"{f.relative_to(PKG)}: {name}")
    assert not offenders, offenders
