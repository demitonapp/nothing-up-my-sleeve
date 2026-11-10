"""The UI consistency check: a control must carry a class — the shared primitives' (`fieldCls`, `selectCls`,
`checkCls`, `rangeCls`) or a documented page class — and inline styles are flagged. `class=` (string-built
HTML) and `className=` (React) are treated alike. Run: python backend/scripts/check_ui.py"""
from pathlib import Path
import re

off = []
for p in Path("frontend/src").rglob("*"):
    if p.suffix not in (".ts", ".tsx", ".astro") or "components/ui" in str(p):
        continue
    lines = p.read_text().splitlines()
    for i, line in enumerate(lines, 1):
        if re.search(r"<(input|select|textarea)\b", line):
            window = " ".join(lines[i - 1 : i + 2])
            if not re.search(r"className=|class=", window):
                off.append((str(p), i, "control with no class: " + line.strip()[:90]))
        if "style={{" in line or re.search(r'\bstyle="', line):
            off.append((str(p), i, "inline style: " + line.strip()[:90]))
print(f"{len(off)} offender(s)")
for f, n, why in off[:40]:
    print(f"{f}:{n}  {why}")
