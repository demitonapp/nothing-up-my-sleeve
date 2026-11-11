"""The GPT of gpt_mlx.py in PyTorch, for NVIDIA GPUs (CUDA) and, in the tests, the CPU.

The same model in every particular: pre-norm, learned or rotary positions (MLX's non-traditional RoPE,
base 10,000), one K/V a head or grouped-query attention (kv_heads), the tanh-approximated GELU MLP at 4x, LayerNorm without a bias (eps 1e-5), tied embeddings,
no biases, the same initialisation scheme. The parameters carry the same names as the MLX model's
(tok.weight, pos.weight, layers.0.attn.qkv.weight, ...), each the same shape, so a checkpoint written by
one backend loads in the other (tests/test_torch.py checks the logits agree).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from thorp.models.registry import GPTConfig


def gelu_approx(x):
    """MLX's nn.gelu_approx: 0.5 x (1 + tanh(sqrt(2/pi) (x + 0.044715 x^3)))."""
    return 0.5 * x * (1 + torch.tanh(math.sqrt(2 / math.pi) * (x + 0.044715 * x**3)))


class RoPE(nn.Module):
    """Rotary positions as MLX's nn.RoPE(dims) computes them (traditional=False): the first and second
    halves of the head are the pair rotated, frequency base ** (-2i / dims), position along axis -2."""

    def __init__(self, dims: int, base: float = 10000.0):
        super().__init__()
        self.dims, self.base = dims, base

    def forward(self, x):
        T, half = x.shape[-2], self.dims // 2
        inv = self.base ** (
            -torch.arange(half, dtype=torch.float32, device=x.device) * 2 / self.dims
        )
        ang = torch.arange(T, dtype=torch.float32, device=x.device)[:, None] * inv[None, :]
        cos, sin = ang.cos().to(x.dtype), ang.sin().to(x.dtype)
        x1, x2 = x[..., :half], x[..., half : self.dims]
        out = torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)
        return out if self.dims == x.shape[-1] else torch.cat([out, x[..., self.dims :]], dim=-1)


class TiedEmbedding(nn.Embedding):
    def as_linear(self, x):
        """The output layer the embedding doubles as (MLX's Embedding.as_linear)."""
        return x @ self.weight.T


class LayerNorm(nn.Module):
    """LayerNorm with a weight and no bias, as MLX's nn.LayerNorm(width, bias=False)."""

    def __init__(self, width: int, eps: float = 1e-5):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(width))
        self.eps = eps

    def forward(self, x):
        return F.layer_norm(x, (x.shape[-1],), self.weight, None, self.eps)


class Attention(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.heads = cfg.heads
        # grouped-query attention, as gpt_mlx.py's (11 November): kv_heads < heads means each K/V is shared by a
        # group of queries, in three projections named as MLX names them (q_proj, k_proj, v_proj), so a grouped
        # checkpoint loads in either backend. 0 keeps one K/V a head and the fused projection every other
        # checkpoint was written with.
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
        self.rope = RoPE(self.head_dim) if getattr(cfg, "positions", "learned") == "rope" else None

    def qk(self, x):
        """The queries, keys and values (batch, heads, time, head_dim), rotated when positions are rotary. In the
        grouped case each key and value is repeated across its group of queries (heads g*i .. g*i + g - 1 read
        K/V i, the grouping MLX's fused attention uses), so every caller indexes one head at a time plainly."""
        B, T, C = x.shape
        if self.kv_heads == self.heads:
            q, k, v = self.qkv(x).split(C, dim=-1)
        else:
            q, k, v = self.q_proj(x), self.k_proj(x), self.v_proj(x)
        q = q.reshape(B, T, self.heads, self.head_dim).transpose(1, 2)
        k = k.reshape(B, T, self.kv_heads, self.head_dim).transpose(1, 2)
        v = v.reshape(B, T, self.kv_heads, self.head_dim).transpose(1, 2)
        if self.rope is not None:
            q, k = self.rope(q), self.rope(k)
        if self.kv_heads != self.heads:
            g = self.heads // self.kv_heads
            k, v = k.repeat_interleave(g, dim=1), v.repeat_interleave(g, dim=1)
        return q, k, v

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qk(x)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True, scale=self.head_dim**-0.5)
        return self.proj(y.transpose(1, 2).reshape(B, T, C))


class MLP(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.up = nn.Linear(cfg.width, 4 * cfg.width, bias=False)
        self.down = nn.Linear(4 * cfg.width, cfg.width, bias=False)

    def forward(self, x):
        return self.down(gelu_approx(self.up(x)))


class Block(nn.Module):
    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.ln1 = LayerNorm(cfg.width)
        self.attn = Attention(cfg)
        self.ln2 = LayerNorm(cfg.width)
        self.mlp = MLP(cfg)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        return x + self.mlp(self.ln2(x))


def _causal_mask(T: int, device) -> torch.Tensor:
    return torch.full((T, T), float("-inf"), device=device).triu(1)


class GPT(nn.Module):
    backend = "torch"  # thorp/models/ops.py dispatches on this

    def __init__(self, cfg: GPTConfig):
        super().__init__()
        self.cfg = cfg
        self.tok = TiedEmbedding(cfg.vocab, cfg.width)
        self.rotary = getattr(cfg, "positions", "learned") == "rope"
        if not self.rotary:
            self.pos = nn.Embedding(cfg.context, cfg.width)
        self.layers = nn.ModuleList([Block(cfg) for _ in range(cfg.layers)])
        self.ln_f = LayerNorm(cfg.width)
        self._init()

    @torch.no_grad()
    def _init(self):
        std = 0.02
        resid = std / math.sqrt(2 * self.cfg.layers)
        nn.init.normal_(self.tok.weight, std=std)
        if not self.rotary:
            nn.init.normal_(self.pos.weight, std=std)
        for b in self.layers:
            a = b.attn
            projs = [a.qkv] if a.kv_heads == a.heads else [a.q_proj, a.k_proj, a.v_proj]
            for lin, s in (
                *((lin, std) for lin in projs),
                (a.proj, resid),
                (b.mlp.up, std),
                (b.mlp.down, resid),
            ):
                nn.init.normal_(lin.weight, std=s)

    @property
    def device(self):
        return self.tok.weight.device

    def _tokens(self, tokens) -> torch.Tensor:
        """Anything array-like (numpy, a list, a tensor) as int64 tokens on the model's device."""
        if isinstance(tokens, torch.Tensor):
            return tokens.to(self.device, torch.long)
        import numpy as np

        return torch.as_tensor(np.asarray(tokens), dtype=torch.long, device=self.device)

    def embed(self, tokens):
        x = self.tok(tokens)
        if self.rotary:
            return x
        return x + self.pos(torch.arange(tokens.shape[1], device=tokens.device))

    def forward(self, tokens):
        tokens = self._tokens(tokens)
        x = self.embed(tokens)
        for b in self.layers:
            x = b(x)
        return self.tok.as_linear(self.ln_f(x))

    def lens(self, h):
        """The logit lens: the output layer read off a residual stream."""
        return self.tok.as_linear(self.ln_f(h))

    def forward_attending(self, tokens, picks: dict[int, list[int]]):
        """As GPT.forward_attending in gpt_mlx.py: the logits, and the picked heads' attention weights
        {(layer, head): (batch, time, time)}, in float32 and differentiable."""
        tokens = self._tokens(tokens)
        T = tokens.shape[1]
        x = self.embed(tokens)
        mask = _causal_mask(T, x.device)
        pats = {}
        for li, b in enumerate(self.layers):
            if li in picks:
                a = b.attn
                q, k, _ = a.qk(b.ln1(x))
                for h in picks[li]:
                    s = (q[:, h] @ k[:, h].transpose(1, 2)).float() * a.head_dim**-0.5
                    pats[(li, h)] = torch.softmax(s + mask, dim=-1)
            x = b(x)
        return self.tok.as_linear(self.ln_f(x)), pats

    def hidden(self, tokens) -> list:
        tokens = self._tokens(tokens)
        x = self.embed(tokens)
        out = []
        for b in self.layers:
            x = b(x)
            out.append(x)
        return out

    def attention_patterns(self, tokens) -> list:
        """Every head's attention weights, a list per layer of (batch, heads, time, time), float32."""
        tokens = self._tokens(tokens)
        T = tokens.shape[1]
        x = self.embed(tokens)
        mask = _causal_mask(T, x.device)
        out = []
        for b in self.layers:
            a = b.attn
            q, k, _ = a.qk(b.ln1(x))
            scores = (q @ k.transpose(-1, -2)).float() * a.head_dim**-0.5 + mask
            out.append(torch.softmax(scores, dim=-1))
            x = b(x)
        return out

    def parameter_counts(self) -> dict[str, int]:
        total = sum(p.numel() for p in self.parameters())
        emb = self.tok.weight.numel() + (0 if self.rotary else self.pos.weight.numel())
        return {"total": total, "embedding": emb, "non_embedding": total - emb}

    def layer_names(self) -> list[str]:
        return [f"layers.{i}" for i in range(len(self.layers))]

    def param_groups(self) -> dict[str, str]:
        groups = {"tok": "tok.", "pos": "pos."}
        for i in range(len(self.layers)):
            groups[f"layer_{i}"] = f"layers.{i}."
            groups[f"layer_{i}/attn"] = f"layers.{i}.attn."
            groups[f"layer_{i}/mlp"] = f"layers.{i}.mlp."
        return groups
