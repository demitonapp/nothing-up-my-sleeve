"""A GPT in MLX: pre-norm, learned or rotary positions, GELU MLP at 4x, tied embeddings, no biases."""

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
        self.rope = (
            nn.RoPE(self.head_dim) if getattr(cfg, "positions", "learned") == "rope" else None
        )

    def qk(self, x):
        """The queries and keys (batch, heads, time, head_dim), rotated when positions are rotary."""
        B, T, C = x.shape
        q, k, v = mx.split(self.qkv(x), 3, axis=-1)
        q, k, v = (
            t.reshape(B, T, self.heads, self.head_dim).transpose(0, 2, 1, 3) for t in (q, k, v)
        )
        if self.rope is not None:
            q, k = self.rope(q), self.rope(k)
        return q, k, v

    def __call__(self, x):
        B, T, C = x.shape
        q, k, v = self.qk(x)
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
        self.rotary = getattr(cfg, "positions", "learned") == "rope"
        if not self.rotary:  # rotary positions need no embedding of their own
            self.pos = nn.Embedding(cfg.context, cfg.width)
        self.layers = [Block(cfg) for _ in range(cfg.layers)]
        self.ln_f = nn.LayerNorm(cfg.width, bias=False)
        self._init()

    def _init(self):
        std = 0.02
        resid = std / math.sqrt(2 * self.cfg.layers)
        self.tok.weight = mx.random.normal(self.tok.weight.shape) * std
        if not self.rotary:
            self.pos.weight = mx.random.normal(self.pos.weight.shape) * std
        for b in self.layers:
            for lin, s in (
                (b.attn.qkv, std),
                (b.attn.proj, resid),
                (b.mlp.up, std),
                (b.mlp.down, resid),
            ):
                lin.weight = mx.random.normal(lin.weight.shape) * s

    def embed(self, tokens):
        """The pieces' embeddings, with their learned positions added (rotary positions are applied
        inside attention instead)."""
        x = self.tok(tokens)
        return x if self.rotary else x + self.pos(mx.arange(tokens.shape[1]))

    def __call__(self, tokens):
        x = self.embed(tokens)
        for b in self.layers:
            x = b(x)
        return self.tok.as_linear(self.ln_f(x))

    def hidden(self, tokens) -> list:
        """The residual stream after each block: a list of (batch, time, width), depth order."""
        x = self.embed(tokens)
        out = []
        for b in self.layers:
            x = b(x)
            out.append(x)
        return out

    def attention_patterns(self, tokens) -> list:
        """Every head's attention weights, computed out in full (the forward pass uses the fused
        kernel, which does not return them): a list per layer of (batch, heads, time, time)."""
        T = tokens.shape[1]
        x = self.embed(tokens)
        mask = mx.triu(mx.full((T, T), -mx.inf), k=1)
        out = []
        for b in self.layers:
            a = b.attn
            q, k, _ = a.qk(b.ln1(x))
            scores = (q @ k.transpose(0, 1, 3, 2)).astype(mx.float32) * a.head_dim**-0.5 + mask
            out.append(mx.softmax(scores, axis=-1))
            x = b(x)
        return out

    def parameter_counts(self) -> dict[str, int]:
        flat = dict(tree_flatten(self.parameters()))
        total = sum(v.size for v in flat.values())
        emb = self.tok.weight.size + (0 if self.rotary else self.pos.weight.size)
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
