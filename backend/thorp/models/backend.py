"""What the training loop and evaluators need from a model, whatever framework it is written in."""

from __future__ import annotations

import os
from typing import Any, Protocol

BACKENDS = ("mlx", "torch")


def backend_of(spec: dict) -> str:
    """Which framework a voyage trains and is scored in: THORP_BACKEND when set (so a voyage already
    written can sail on a CUDA box under its own run id), else the spec's model.backend, else "mlx".
    The spec's key is part of the run id; the environment's is not (the hardware column records it)."""
    b = os.environ.get("THORP_BACKEND") or (spec.get("model") or {}).get("backend") or "mlx"
    if b not in BACKENDS:
        raise ValueError(f"unknown backend {b!r}; known: {', '.join(BACKENDS)}")
    return b


class Backend(Protocol):
    def __call__(self, tokens: Any) -> Any:
        """(batch, time) int tokens -> (batch, time, vocab) logits."""

    def parameter_counts(self) -> dict[str, int]:
        """{'total': ..., 'embedding': ..., 'non_embedding': ...}"""

    def layer_names(self) -> list[str]:
        """Keys under which per-layer parameters live, in depth order."""

    def param_groups(self) -> dict[str, str]:
        """Named parameter groups -> key prefix: embeddings, then each layer and its attn and mlp halves."""

    def hidden(self, tokens: Any) -> list[Any]:
        """(batch, time) int tokens -> the residual stream after each layer, (batch, time, width)."""
