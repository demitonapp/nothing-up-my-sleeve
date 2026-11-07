"""MLX ports of outside models that mlx-lm cannot load, for scoring only (scripts/score_external.py).

Each port reads the model's own weights (safetensors), config and tokenizer from Hugging Face, and never
the model's own Python: the architecture is written here from a reading of its modelling file, and checked
on a passage of code and one of prose before it is trusted (DECISIONS.md, "Maincoder-1B on the Forgotten
Tomes").

- **maincoder** (Maincode/Maincoder-1B, Melbourne, Apache 2.0; 7 November 2026, Justin: "how can i smoke
  maincodes maincoder 1b"): Qwen3-like (GQA 16/4, head 96, SwiGLU, RMSNorm, tied head) with two differences
  that matter: rotary positions on adjacent pairs of dimensions (the "traditional" form), and the query and
  key norms applied *after* the rotation, where Qwen3 applies them before. So mlx-lm's Qwen3 would load
  the weights and score them wrongly.
"""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn

# the weights, the config and the tokenizer: never the model's own code
ALLOW = ["*.json", "*.safetensors", "merges.txt", "vocab.json"]


class RMSNorm(nn.Module):
    def __init__(self, dims: int, eps: float):
        super().__init__()
        self.weight = mx.ones((dims,))
        self.eps = eps

    def __call__(self, x):
        return mx.fast.rms_norm(x, self.weight, self.eps)


class MaincoderAttention(nn.Module):
    def __init__(self, c: dict):
        super().__init__()
        d, self.h, self.kv, self.hd = (
            c["hidden_size"],
            c["num_attention_heads"],
            c["num_key_value_heads"],
            c["head_dim"],
        )
        self.q_proj = nn.Linear(d, self.h * self.hd, bias=False)
        self.k_proj = nn.Linear(d, self.kv * self.hd, bias=False)
        self.v_proj = nn.Linear(d, self.kv * self.hd, bias=False)
        self.o_proj = nn.Linear(self.h * self.hd, d, bias=False)
        if c.get("use_qk_norm", True):
            self.q_norm = RMSNorm(self.hd, c["rms_norm_eps"])
            self.k_norm = RMSNorm(self.hd, c["rms_norm_eps"])
        if c.get("rope_scaling"):
            raise NotImplementedError("rope_scaling is not ported")
        self.rope = nn.RoPE(self.hd, traditional=True, base=c["rope_theta"])
        self.scale = self.hd**-0.5

    def __call__(self, x, mask):
        b, n, _ = x.shape
        q = self.q_proj(x).reshape(b, n, self.h, self.hd).transpose(0, 2, 1, 3)
        k = self.k_proj(x).reshape(b, n, self.kv, self.hd).transpose(0, 2, 1, 3)
        v = self.v_proj(x).reshape(b, n, self.kv, self.hd).transpose(0, 2, 1, 3)
        q, k = self.rope(q), self.rope(k)  # rotary first ...
        if hasattr(self, "q_norm"):
            q, k = self.q_norm(q), self.k_norm(k)  # ... then the norms, as Maincoder does
        o = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale, mask=mask)
        return self.o_proj(o.transpose(0, 2, 1, 3).reshape(b, n, -1))


class MaincoderMLP(nn.Module):
    def __init__(self, c: dict):
        super().__init__()
        d, f = c["hidden_size"], c.get("intermediate_size_mlp", c["intermediate_size"])
        self.gate_proj = nn.Linear(d, f, bias=False)
        self.up_proj = nn.Linear(d, f, bias=False)
        self.down_proj = nn.Linear(f, d, bias=False)

    def __call__(self, x):
        return self.down_proj(nn.silu(self.gate_proj(x)) * self.up_proj(x))


class MaincoderLayer(nn.Module):
    def __init__(self, c: dict):
        super().__init__()
        self.self_attn = MaincoderAttention(c)
        self.feed_forward = MaincoderMLP(c)
        self.input_layernorm = RMSNorm(c["hidden_size"], c["rms_norm_eps"])
        self.post_attention_layernorm = RMSNorm(c["hidden_size"], c["rms_norm_eps"])

    def __call__(self, x, mask):
        x = x + self.self_attn(self.input_layernorm(x), mask)
        return x + self.feed_forward(self.post_attention_layernorm(x))


class MaincoderBody(nn.Module):
    def __init__(self, c: dict):
        super().__init__()
        self.embed_tokens = nn.Embedding(c["vocab_size"], c["hidden_size"])
        self.layers = [MaincoderLayer(c) for _ in range(c["num_hidden_layers"])]
        self.norm = RMSNorm(c["hidden_size"], c["rms_norm_eps"])


class Maincoder(nn.Module):
    def __init__(self, c: dict):
        super().__init__()
        self.model = MaincoderBody(c)
        self.tied = c.get("tie_word_embeddings", True)
        if not self.tied:
            self.lm_head = nn.Linear(c["hidden_size"], c["vocab_size"], bias=False)

    def __call__(self, ids):
        h = self.model.embed_tokens(ids)
        mask = nn.MultiHeadAttention.create_additive_causal_mask(ids.shape[1]).astype(h.dtype)
        for layer in self.model.layers:
            h = layer(h, mask)
        h = self.model.norm(h)
        return self.model.embed_tokens.as_linear(h) if self.tied else self.lm_head(h)


PORTS = {"maincoder": Maincoder}


def _snapshot(repo: str) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo, allow_patterns=ALLOW))


def port_for(repo: str):
    """The port for a Hugging Face model whose architecture mlx-lm cannot load, or None."""
    if Path(repo).exists():
        cfg = Path(repo) / "config.json"
    else:
        from huggingface_hub import hf_hub_download

        try:
            cfg = Path(hf_hub_download(repo, "config.json"))
        except Exception:  # noqa: BLE001  (not on the Hub: mlx-lm will say why)
            return None
    kind = json.loads(cfg.read_text()).get("model_type")
    return (lambda: load(repo)) if kind in PORTS else None


def load(repo: str):
    """(model, tokenizer) for a ported model: its own weights and tokenizer, no code of its own."""
    from transformers import AutoTokenizer

    d = Path(repo) if Path(repo).exists() else _snapshot(repo)
    c = json.loads((d / "config.json").read_text())
    model = PORTS[c["model_type"]](c)
    weights = {}
    for f in sorted(d.glob("*.safetensors")):
        weights |= mx.load(str(f))
    if getattr(model, "tied", False):
        weights.pop("lm_head.weight", None)
    model.load_weights(list(weights.items()), strict=True)
    model.eval()
    mx.eval(model.parameters())
    tok = AutoTokenizer.from_pretrained(str(d), trust_remote_code=False)
    return model, tok
