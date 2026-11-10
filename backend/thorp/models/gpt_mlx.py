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
        # grouped-query attention: kv_heads < heads means each K/V is shared by a group of queries
        # (9 November, Kipling's question: is GQA good for Thorp?). 0/None keeps one K/V per head and
        # the single fused projection every existing checkpoint was written with.
        self.kv_heads = getattr(cfg, "kv_heads", 0) or cfg.heads
        self.head_dim = cfg.width // cfg.heads
        if self.kv_heads == cfg.heads:
            self.qkv = nn.Linear(cfg.width, 3 * cfg.width, bias=False)
        else:
            assert cfg.heads % self.kv_heads == 0, "query heads must divide into KV groups"
            self.q_proj = nn.Linear(cfg.width, cfg.heads * self.head_dim, bias=False)
            self.k_proj = nn.Linear(cfg.width, self.kv_heads * self.head_dim, bias=False)
            self.v_proj = nn.Linear(cfg.width, self.kv_heads * self.head_dim, bias=False)
        self.proj = nn.Linear(cfg.width, cfg.width, bias=False)
        self.rope = (
            nn.RoPE(self.head_dim) if getattr(cfg, "positions", "learned") == "rope" else None
        )

    def qk(self, x, repeat=True):
        """The queries and keys (batch, heads, time, head_dim), rotated when positions are rotary. In the
        grouped case the keys and values can be repeated across their group so the callers that read one
        head at a time can index them plainly; the forward pass leaves them unrepeated, because MLX 0.32's
        fused attention supports grouped-query attention natively (10 November)."""
        B, T, C = x.shape
        if self.kv_heads == self.heads:
            q, k, v = mx.split(self.qkv(x), 3, axis=-1)
        else:
            q, k, v = self.q_proj(x), self.k_proj(x), self.v_proj(x)
        q = q.reshape(B, T, self.heads, self.head_dim).transpose(0, 2, 1, 3)
        k = k.reshape(B, T, self.kv_heads, self.head_dim).transpose(0, 2, 1, 3)
        v = v.reshape(B, T, self.kv_heads, self.head_dim).transpose(0, 2, 1, 3)
        if self.rope is not None:
            q, k = self.rope(q), self.rope(k)
        if repeat and self.kv_heads != self.heads:
            g = self.heads // self.kv_heads
            k = mx.repeat(k, g, axis=1)
            v = mx.repeat(v, g, axis=1)
        return q, k, v

    def __call__(self, x):
        B, T, C = x.shape
        # the fused kernel takes Q with more heads than K/V directly (GQA/MQA); repeating first was a
        # needless copy on every layer, and at the 1m it is 2x the K/V tensors
        q, k, v = self.qk(x, repeat=False)
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
            attn = b.attn
            projs = (
                [(attn.qkv, std)] if attn.kv_heads == attn.heads
                else [(attn.q_proj, std), (attn.k_proj, std), (attn.v_proj, std)]
            )
            for lin, s in [*projs, (attn.proj, resid), (b.mlp.up, std), (b.mlp.down, resid)]:
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

    def forward_attending(self, tokens, picks: dict[int, list[int]]):
        """The logits, and the attention weights of the picked heads ({layer: [head, ...]}) as a dict
        {(layer, head): (batch, time, time)}, differentiable (the metre scaffold, train.scaffold_loss).
        The forward pass is the ordinary one; the picked heads' weights are computed out beside it from
        the same queries and keys, so their gradient reaches those heads' query and key weights."""
        T = tokens.shape[1]
        x = self.embed(tokens)
        mask = mx.triu(mx.full((T, T), -mx.inf), k=1)
        pats = {}
        for li, b in enumerate(self.layers):
            if li in picks:
                a = b.attn
                q, k, _ = a.qk(b.ln1(x))
                for h in picks[li]:
                    s = (q[:, h] @ k[:, h].transpose(0, 2, 1)).astype(mx.float32) * a.head_dim**-0.5
                    pats[(li, h)] = mx.softmax(s + mask, axis=-1)
            x = b(x)
        return self.tok.as_linear(self.ln_f(x)), pats

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
