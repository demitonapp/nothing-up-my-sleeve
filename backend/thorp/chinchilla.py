"""The Chinchilla loss prediction (Hoffmann et al., 2022, approach 3), in nats per token.

Indicative only: the constants were fitted on MassiveText with a different tokeniser, so the gap
between this and a Nothing up my sleeve score is a yardstick, not a residual.
"""

from __future__ import annotations

E, A, B, ALPHA, BETA = 1.69, 406.4, 410.7, 0.34, 0.28


def loss(n_params: float, n_tokens: float) -> float:
    return E + A / n_params**ALPHA + B / n_tokens**BETA
