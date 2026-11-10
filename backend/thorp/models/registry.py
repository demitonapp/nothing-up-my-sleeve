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
    # grouped-query attention (9 November, Kipling's question): fewer K/V heads than query heads, each
    # K/V shared by a group of queries. 0 = one K/V per head (ordinary multi-head attention).
    kv_heads: int = 0


PRESETS: dict[str, dict] = {
    # 1m, the pilot (2026-11-07; renamed from "the proxy" at 09:00): a fast outer loop for data
    # questions, used only where it ranks shelves the way 9m does (DECISIONS.md, "The 1m proxy")
    # 300k, the keel (renamed from "the seedling" at 09:00): two layers of two 32-wide heads, the same
    # head size as 1m and 9m, so its heads can be carried up whole
    "300k": dict(layers=6, width=48, heads=2),  # deep ladder (9 November): depth bought with width, within the same budget
    "1m": dict(layers=12, width=80, heads=4),  # deep ladder (9 November): depth bought with width, within the same budget
    "9m": dict(layers=18, width=120, heads=6),  # deep ladder (9 November): depth bought with width, within the same budget
    "21m": dict(layers=24, width=192, heads=8),  # deep ladder (9 November): depth bought with width, within the same budget
    "50m": dict(layers=36, width=304, heads=8),  # deep ladder (9 November): depth bought with width, within the same budget
    "100m": dict(layers=12, width=768, heads=12),
    "350m": dict(layers=24, width=1024, heads=16),
}


class _Ladder(Sequence):
    """The ladder: every size, smallest first, read from Postgres (`s1.sizes`, thorp/ship_store.py), not
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


def config(
    preset: str,
    vocab: int,
    context: int,
    positions: str = "learned",
    kv_heads: int = 0,
    layers: int | None = None,
    width: int | None = None,
    heads: int | None = None,
) -> GPTConfig:
    """A preset, optionally overridden by a checkpoint's own shape.

    Old checkpoints were built before the deep ladder changed the presets (a 300k was 2 layers
    of 64, now 6 of 48). A rescore must read the checkpoint's shape, not today's preset: the
    overrides keep an old voyage measurable without rewriting its weights.
    """
    base = PRESETS.get(preset) or PRESETS.get(str(preset).split("-")[0])
    if base is None:
        raise KeyError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
    if positions not in ("learned", "rope"):
        raise KeyError(f"unknown positions {positions!r}; known: learned, rope")
    shape = dict(base)
    if layers is not None:
        shape["layers"] = int(layers)
    if width is not None:
        shape["width"] = int(width)
    if heads is not None:
        shape["heads"] = int(heads)
    extra = {"kv_heads": int(kv_heads)} if kv_heads else {}
    return GPTConfig(**{**shape, "vocab": vocab, "context": context, "positions": positions, **extra})


def build(
    family: str, preset: str, vocab: int, context: int, positions: str = "learned",
    backend: str = "mlx", kv_heads: int = 0,
    layers: int | None = None, width: int | None = None, heads: int | None = None,
):
    families = TORCH_FAMILIES if backend == "torch" else FAMILIES
    if family not in families:
        raise KeyError(f"unknown model family {family!r} for {backend}; known: {sorted(families)}")
    return families[family](config(preset, vocab, context, positions, kv_heads, layers, width, heads))

# Other people's ships, for the shape table only (9 November, Justin: "add qwen 4B, Phi 4 mini and llama 3.2 3B"): the
# depth and width a model that chains was built with. They are not Thorp presets — nothing trains or sails them — they
# are here so a Thorp shape can be read beside them, layer for layer.
FOREIGN = {
    "qwen3-4b": dict(layers=36, width=2560, heads=32, vocab=151936, params=4_000_000_000, lab="Qwen3 4B"),
    "phi-4-mini": dict(layers=32, width=3072, heads=24, vocab=200064, params=3_800_000_000, lab="Phi-4-mini 3.8B"),
    "llama-3.2-3b": dict(layers=28, width=3072, heads=24, vocab=128256, params=3_200_000_000, lab="Llama 3.2 3B"),    # Qwen3.8 27B: the local 4-bit checkpoint (mlx-community/Qwen3.8-27B-4bit), 64 layers, 24 query heads
    # sharing 4 KV heads — a 6:1 grouping, the extreme end of the GQA question (9 November, Justin: "the
    # actual 27b don't i have it locally")
    "qwen3-8-27b": dict(layers=64, width=5120, heads=24, vocab=248320, params=27_000_000_000, lab="Qwen3.8 27B"),
    # Gemma 3 4B (text-only): the local 4-bit checkpoint (mlx-community/gemma-3-text-4b-pt-4bit), 34 layers,
    # 8 query heads sharing 4 KV heads — a 2:1 grouping, the conservative end of the GQA question
    "gemma-3-4b": dict(layers=34, width=2560, heads=8, vocab=262208, params=4_000_000_000, lab="Gemma 3 4B"),}
