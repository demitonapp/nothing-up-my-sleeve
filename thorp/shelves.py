"""Renamed: the shelves are the library (2026-11-07, Justin). This name stays as an alias of
thorp.library until every reader has moved."""

import sys

from thorp import library

sys.modules[__name__] = library
