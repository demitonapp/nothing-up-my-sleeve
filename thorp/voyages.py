"""Renamed: what were voyages are expeditions (2026-11-07, Justin). This name stays as an alias of
thorp.expeditions until every reader has moved."""

import sys

from thorp import expeditions

sys.modules[__name__] = expeditions
