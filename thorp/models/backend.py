"""What the training loop and evaluators need from a model, whatever framework it is written in."""

from __future__ import annotations

from typing import Any, Protocol


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
