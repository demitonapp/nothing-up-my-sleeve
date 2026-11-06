"""A GPT in MLX: pre-norm, learned positions, GELU MLP at 4x, tied embeddings, no biases."""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten

from thorp.models.registry import GPTConfig


class Attention(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.heads = cfg.heads
        self.head_dim = cfg.width // cfg.heads
        self.qkv = nn.Linear(cfg.width, 3 * cfg.width, bias=False)
        self.proj = nn.Linear(cfg.width, cfg.width, bias=False)

    def __call__(self, x):
        B, T, C = x.shape
        q, k, v = mx.split(self.qkv(x), 3, axis=-1)
        q, k, v = (
            t.reshape(B, T, self.heads, self.head_dim).transpose(0, 2, 1, 3) for t in (q, k, v)
        )
        y = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.head_dim**-0.5, mask="causal")
        return self.proj(y.transpose(0, 2, 1, 3).reshape(B, T, C))


class MLP(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.up = nn.Linear(cfg.width, 4 * cfg.width, bias=False)
        self.down = nn.Linear(4 * cfg.width, cfg.width, bias=False)

    def __call__(self, x):
        return self.down(nn.gelu_approx(self.up(x)))


class Block(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.width, bias=False)
        self.attn = Attention(cfg)
        self.ln2 = nn.LayerNorm(cfg.width, bias=False)
        self.mlp = MLP(cfg)

    def __call__(self, x):
        x = x + self.attn(self.ln1(x))
        return x + self.mlp(self.ln2(x))


class GPT(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.cfg = cfg
        self.tok = nn.Embedding(cfg.vocab, cfg.width)
        self.pos = nn.Embedding(cfg.context, cfg.width)
        self.layers = [Block(cfg) for _ in range(cfg.layers)]
        self.ln_f = nn.LayerNorm(cfg.width, bias=False)
        self._init()

    def _init(self):
        std = 0.02
        resid = std / math.sqrt(2 * self.cfg.layers)
        self.tok.weight = mx.random.normal(self.tok.weight.shape) * std
        self.pos.weight = mx.random.normal(self.pos.weight.shape) * std
        for b in self.layers:
            for lin, s in (
                (b.attn.qkv, std),
                (b.attn.proj, resid),
                (b.mlp.up, std),
                (b.mlp.down, resid),
            ):
                lin.weight = mx.random.normal(lin.weight.shape) * s

    def __call__(self, tokens):
        T = tokens.shape[1]
        x = self.tok(tokens) + self.pos(mx.arange(T))
        for b in self.layers:
            x = b(x)
        return self.tok.as_linear(self.ln_f(x))

    def hidden(self, tokens) -> list:
        """The residual stream after each block: a list of (batch, time, width), depth order."""
        T = tokens.shape[1]
        x = self.tok(tokens) + self.pos(mx.arange(T))
        out = []
        for b in self.layers:
            x = b(x)
            out.append(x)
        return out

    def parameter_counts(self) -> dict[str, int]:
        flat = dict(tree_flatten(self.parameters()))
        total = sum(v.size for v in flat.values())
        emb = self.tok.weight.size + self.pos.weight.size
        return {"total": total, "embedding": emb, "non_embedding": total - emb}

    def layer_names(self) -> list[str]:
        return [f"layers.{i}" for i in range(len(self.layers))]

    def param_groups(self) -> dict[str, str]:
        """Named parameter groups -> key prefix: the two embeddings, then each block in depth order."""
        groups = {"tok": "tok.", "pos": "pos."}
        for i in range(len(self.layers)):
            groups[f"layer_{i}"] = f"layers.{i}."
            groups[f"layer_{i}/attn"] = f"layers.{i}.attn."
            groups[f"layer_{i}/mlp"] = f"layers.{i}.mlp."
        return groups
