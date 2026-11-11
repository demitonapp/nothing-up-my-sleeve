"""`python -m thorp ...`, the same entry point as the `thorp` console script."""

from __future__ import annotations

import sys

from thorp.cli import main

if __name__ == "__main__":
    sys.exit(main())
