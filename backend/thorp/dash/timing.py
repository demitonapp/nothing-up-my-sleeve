"""Runtime estimates from finished voyages, shared by the queue table and the waters plan.

A preset mean over every finished run is not a runtime: short loops, proxies, cause-deck ablations
and smoke tests count the same as a full four-pass voyage, which is why a 1m once estimated at 25
minutes against a 179-minute fulldeck. This module estimates the **median of like voyages**, in
order: the same ship, the same corpus and size (at half the corpus's largest read), then the
full-budget voyages of the size (at 80% of the largest, read at the 75th percentile). The estimate is a duration; the queue's start times are a separate seat schedule.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict


def _p75(v: list[float]) -> float:
    """The 75th percentile: the size fallback leans conservative, so a single fast fitout cannot set it."""
    s = sorted(v)
    return s[min(len(s) - 1, int(0.75 * (len(s) - 1)))]


class RunTimes:
    """Finished voyages' wall times, bucketed for a like-for-like median."""

    def __init__(self, rows: list[dict]):
        self.by_name: dict[str, list[float]] = defaultdict(list)
        self.by_stem: dict[str, list[float]] = defaultdict(list)
        self.by_recipe: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)
        self.by_preset: dict[str, list[float]] = defaultdict(list)
        self.tokens: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            if r.get("status") != "finished" or not (r.get("wall_minutes") or 0) > 0:
                continue
            try:
                spec = json.loads(r.get("spec_json") or "{}")
            except ValueError:
                spec = {}
            preset = (spec.get("model") or {}).get("preset")
            if not preset:
                continue
            data = spec.get("data") or {}
            recipe = data.get("recipe") or next(
                (s.get("recipe") for s in data.get("stages") or [] if s.get("recipe")), None
            )
            wall = float(r["wall_minutes"])
            tokens = int(r.get("tokens_seen") or 0)
            name = str(r.get("name") or "")
            self.by_name[name].append(wall)
            self.by_stem[re.sub(r"-s\d+$", "", name)].append(wall)
            self.by_preset[preset].append(wall)
            self.tokens[preset].append(tokens)
            if recipe:
                self.by_recipe[(recipe, preset)].append((wall, tokens))
        # Only voyages that read a full budget: a 40M-token ablation must not stand for a 269M-token
        # voyage. Per corpus, half the corpus's largest finished read; per size, 80% of the largest, so
        # a size's one long 8-pass run cannot set the budget for a 4-pass spec. Fall back to every
        # finished run only when there is no token record at all.
        self.by_recipe_full: dict[tuple[str, str], list[float]] = {}
        for key, pairs in self.by_recipe.items():
            top = max((t for _, t in pairs), default=0)
            cut = 0.5 * top
            full = [w for w, t in pairs if t > 0 and t >= cut]
            self.by_recipe_full[key] = full or [w for w, _ in pairs]
        self.full: dict[str, list[float]] = {}
        for preset, walls in self.by_preset.items():
            top = max(self.tokens[preset] or [0])
            cut = 0.8 * top
            full = [w for w, t in zip(walls, self.tokens[preset]) if t > 0 and t >= cut]
            self.full[preset] = full or walls

    @classmethod
    def from_reader(cls) -> "RunTimes":
        from thorp.ledger import reader

        return cls(
            reader().query(
                "select name, status, wall_minutes, tokens_seen, spec_json from s1.runs"
            )
        )

    def estimate(self, name: str, spec: dict) -> tuple[float | None, str]:
        """The median minutes for a voyage like this one, and the bucket it came from."""
        preset = ((spec.get("model") or {}).get("preset") or "") or None
        data = spec.get("data") or {}
        recipe = data.get("recipe") or next(
            (s.get("recipe") for s in data.get("stages") or [] if s.get("recipe")), None
        )
        stem = re.sub(r"-s\d+$", "", name)
        buckets = (
            (self.by_name.get(name), "this ship"),
            (self.by_stem.get(stem) if stem != name else None, "this ship's other seeds"),
            (self.by_recipe_full.get((recipe, preset)) if recipe and preset else None, "this corpus"),
        )
        for bucket, source in buckets:
            if bucket:
                return statistics.median(bucket), source
        size = self.full.get(preset) if preset else None
        if size:
            return _p75(size), "this size (full budget)"
        return None, "no time"

    def wall(self) -> dict:
        """The waters plan's dict: medians per (recipe, size) and per size (the full-budget fallback)."""
        out: dict = {p: statistics.median(v) for p, v in self.full.items()}
        for (recipe, preset), v in self.by_recipe_full.items():
            out[(recipe, preset)] = statistics.median(v)
        return out
