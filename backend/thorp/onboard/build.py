"""The dashboard build the first run needs before it can hand over.

`backend/thorp/dash/static` is not committed: a fresh clone has no page until Astro builds one. The
first-run page itself is served by Python and does not depend on this, so the build can be a visible
install step rather than a precondition. If Node or pnpm is missing, the step says so and leaves the
command; it never installs a toolchain silently.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from thorp import paths

STATIC = Path(__file__).resolve().parent.parent / "dash" / "static"


def status() -> dict:
    index = STATIC / "index.html"
    node = shutil.which("node")
    pnpm = shutil.which("pnpm")
    return {
        "built": index.is_file(),
        "built_at": index.stat().st_mtime if index.is_file() else None,
        "static": str(STATIC),
        "node": node,
        "pnpm": pnpm,
        "node_modules": (paths.FRONTEND / "node_modules").is_dir(),
        "can_build": bool(node and pnpm),
        "hint": "pnpm --dir frontend install && pnpm --dir frontend build",
    }


def run() -> dict:
    s = status()
    if s["built"] and s["node_modules"]:
        # already built: a rebuild during onboarding would only make the wait longer. Settings can
        # still ask for a fresh build from a shell.
        return s
    if not s["can_build"]:
        raise RuntimeError(
            "Node and pnpm are needed to build the dashboard. Install Node, then run "
            f"`{s['hint']}` and press Retry."
        )
    pnpm = str(s["pnpm"])
    if not s["node_modules"]:
        _run([pnpm, "install"], timeout=900)
    _run([pnpm, "build"], timeout=900)
    return status()


def _run(cmd: list[str], timeout: float) -> None:
    r = subprocess.run(
        cmd,
        cwd=str(paths.FRONTEND),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "CI": "1"},
    )
    if r.returncode != 0:
        tail = (r.stdout or "").strip().splitlines()[-8:] + (r.stderr or "").strip().splitlines()[
            -8:
        ]
        raise RuntimeError(
            f"{' '.join(cmd)} failed: " + " · ".join(x.strip() for x in tail if x.strip())[-1200:]
        )
