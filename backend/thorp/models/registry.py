"""Model presets and the family map. Preset names live here and nowhere else in the package."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class GPTConfig:
    layers: int
    width: int
    heads: int
    vocab: int = 16384
    context: int = 1024
    # how the model knows where a piece is (2026-11-07, the two-fact problem's round 2): "learned"
    # (an embedding per position, added to the piece's) or "rope" (rotary positions, applied to the
    # queries and keys, so attention sees how far apart two pieces are: the relative skill a Nevermore
    # needs)
    positions: str = "learned"


PRESETS: dict[str, dict] = {
    "tiny": dict(layers=2, width=64, heads=2),  # tests only
    # 1m, the pilot (2026-11-07; renamed from "the proxy" at 09:00): a fast outer loop for data
    # questions, used only where it ranks shelves the way 9m does (DECISIONS.md, "The 1m proxy")
    # 300k, the keel (renamed from "the seedling" at 09:00): two layers of two 32-wide heads, the same
    # head size as 1m and 9m, so its heads can be carried up whole
    "300k": dict(layers=2, width=64, heads=2),
    "1m": dict(layers=4, width=128, heads=4),
    # shape variants for the card census (2026-11-07, Justin: "how many of the cards are possible at
    # 300k"): the same budget spent on more, smaller heads, or on one more layer; experiments within a
    # class, not rungs of the ladder
    "300k-h4": dict(layers=2, width=64, heads=4),
    "300k-l3": dict(layers=3, width=64, heads=2),
    "1m-h8": dict(layers=4, width=128, heads=8),
    "1m-l6": dict(layers=6, width=128, heads=4),
    "9m": dict(layers=6, width=192, heads=6),
    # The ladder (2026-11-06; DECISIONS.md): each rung has one job. 9m: spelling, punctuation and the
    # statistical laws. 21m: grammar and style. 50m: paragraphs and the size curve (rented GPUs).
    # 100m: the Origin test, the Mac's flagship. 350m: the top of the Origin curve (rented GPUs).
    "21m": dict(layers=8, width=320, heads=8),
    "50m": dict(layers=12, width=512, heads=8),
    "100m": dict(layers=12, width=768, heads=12),
    "350m": dict(layers=24, width=1024, heads=16),
}


class _Ladder(Sequence):
    """The ladder: every size, smallest first, read from Postgres (`ship.sizes`, thorp/ship_store.py), not
    written here. Each is a dict: preset, name, role (and job, the same), overview, kind, vocab, where,
    status, scored and metrics. Read on first use and kept for the process."""

    def _rows(self) -> list[dict]:
        from thorp import ship_store

        return ship_store.sizes()

    def __getitem__(self, i):
        return self._rows()[i]

    def __len__(self) -> int:
        return len(self._rows())

    def __iter__(self):
        return iter(self._rows())


LADDER = _Ladder()


def _gpt_mlx(cfg: GPTConfig):
    from thorp.models.gpt_mlx import GPT

    return GPT(cfg)


def _gpt_torch(cfg: GPTConfig):
    from thorp.models.gpt_torch import GPT

    return GPT(cfg)


FAMILIES = {"gpt": _gpt_mlx}
TORCH_FAMILIES = {"gpt": _gpt_torch}  # the same models in PyTorch (CUDA), thorp/models/backend.py


def config(preset: str, vocab: int, context: int, positions: str = "learned") -> GPTConfig:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
    if positions not in ("learned", "rope"):
        raise KeyError(f"unknown positions {positions!r}; known: learned, rope")
    return GPTConfig(**PRESETS[preset], vocab=vocab, context=context, positions=positions)


def build(
    family: str, preset: str, vocab: int, context: int, positions: str = "learned", backend: str = "mlx"
):
    families = TORCH_FAMILIES if backend == "torch" else FAMILIES
    if family not in families:
        raise KeyError(f"unknown model family {family!r} for {backend}; known: {sorted(families)}")
    return families[family](config(preset, vocab, context, positions))
