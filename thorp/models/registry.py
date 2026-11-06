"""Model presets and the family map. Preset names live here and nowhere else in the package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GPTConfig:
    layers: int
    width: int
    heads: int
    vocab: int = 16384
    context: int = 1024


PRESETS: dict[str, dict] = {
    "tiny": dict(layers=2, width=64, heads=2),  # tests only
    "9m": dict(layers=6, width=192, heads=6),
    "21m": dict(layers=8, width=320, heads=8),
    "67m": dict(layers=12, width=576, heads=9),
    "300m": dict(layers=24, width=1024, heads=16),
}


def _gpt_mlx(cfg: GPTConfig):
    from thorp.models.gpt_mlx import GPT

    return GPT(cfg)


FAMILIES = {"gpt": _gpt_mlx}


def config(preset: str, vocab: int, context: int) -> GPTConfig:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
    return GPTConfig(**PRESETS[preset], vocab=vocab, context=context)


def build(family: str, preset: str, vocab: int, context: int):
    if family not in FAMILIES:
        raise KeyError(f"unknown model family {family!r}; known: {sorted(FAMILIES)}")
    return FAMILIES[family](config(preset, vocab, context))
