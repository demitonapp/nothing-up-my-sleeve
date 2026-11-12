"""The dashboard server's module-level functions each have one name (12 November: a second `api_tests`, the
/api/tests route, replaced the per-model helper of the same name, and every competitor page failed with
"api_tests() takes 0 positional arguments but 1 was given"). Read from the source, so no store is needed."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "thorp" / "dash" / "server.py"


def test_no_module_level_function_is_defined_twice():
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    names = Counter(n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    twice = sorted(k for k, n in names.items() if n > 1)
    assert not twice, f"defined more than once in server.py (the later one replaces the earlier): {twice}"
