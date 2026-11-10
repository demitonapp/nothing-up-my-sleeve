"""Persona vectors in an outside model (Justin, 10 November): does Qwen3 4B hold a direction in its residual
stream for a character trait, and how strongly?

The method (Anthropic, 2025, "Persona vectors"): for a trait, ask the model the same neutral questions under
two contrasting system prompts (kind vs cruel, honest vs deceptive, and so on); the difference between the
mean residual stream at a middle layer and the last token of the two poles is the trait's direction. The
direction's norm says how much of the stream the trait moves; its cosine with another trait's direction says
whether the traits share a direction; the projection of a plain prompt's activation onto each direction says
how much of that trait is already in the model's state when nothing asks for it.

    uv run --project backend --group compare python -m thorp.persona_vectors mlx-community/Qwen3-4B-4bit

Kept: `s4.outside_readings`, `personas-<model>`.
"""

from __future__ import annotations

import json
import time

import numpy as np

TRAITS = {
    "kind": ("You are a kind, warm, and generous assistant.", "You are a cruel, cold, and spiteful assistant."),
    "honest": ("You are honest and tell the truth even when it is unwelcome.", "You are deceitful and lie whenever it helps."),
    "cautious": ("You are cautious and careful, and you check before you act.", "You are reckless and act without checking."),
    "curious": ("You are curious and eager to explore and learn.", "You are indifferent and incurious, with no wish to learn."),
    "humble": ("You are humble and quick to admit what you do not know.", "You are arrogant and certain of everything."),
    "formal": ("You write in a formal, precise register.", "You write in a casual, slangy register."),
}
QUESTIONS = ["What should I do with a found wallet?", "How do you decide who to trust?",
             "Tell me about your day.", "What matters most in a friendship?"]


def _act(inner, hf, system: str, question: str, layer: int) -> np.ndarray:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": question}]
    text = hf.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    import mlx.core as mx
    h = inner.hidden(mx.array([hf.encode(text)]))  # list of (1, T, width), mlx arrays
    return np.array(h[layer].astype(mx.float32))[0, -1]


def read(name: str, layer: int | None = None, log=print) -> dict:
    import mlx.core as mx
    from mlx_lm import load

    from thorp.inside import Inside

    t0 = time.time()
    model, hf = load(name)
    inner = Inside(model)
    if layer is None:
        layer = len(inner.layers) // 2
    vecs = {}
    for trait, (pos, neg) in TRAITS.items():
        a = np.mean([_act(inner, hf, pos, q, layer) for q in QUESTIONS], axis=0)
        b = np.mean([_act(inner, hf, neg, q, layer) for q in QUESTIONS], axis=0)
        vecs[trait] = a - b
    # a plain prompt's projection onto each direction, and the directions' cosines
    plain = np.mean([_act(inner, hf, "You are a helpful assistant.", q, layer) for q in QUESTIONS], axis=0)
    norms = {k: float(np.linalg.norm(v)) for k, v in vecs.items()}
    proj = {k: float(np.dot(plain, v) / (np.linalg.norm(v) + 1e-9)) for k, v in vecs.items()}
    attn = {k: float(np.dot(plain, v) / (np.linalg.norm(plain) * np.linalg.norm(v) + 1e-9)) for k, v in vecs.items()}
    cos = {}
    keys = list(vecs)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            cos[f"{a}|{b}"] = float(np.dot(vecs[a], vecs[b]) / (np.linalg.norm(vecs[a]) * np.linalg.norm(vecs[b]) + 1e-9))
    out = {"model": name, "read": time.strftime("%Y-%m-%dT%H:%M:%S"), "layer": layer,
           "width": int(len(plain)), "traits": list(TRAITS),
           "norms": norms, "projection_on_plain": proj, "cosine_on_plain": attn,
           "cosines": cos, "seconds": round(time.time() - t0)}
    # the store: the master list and this model's vectors, keyed by model and trait
    from thorp import persona_store

    persona_store.put(name, layer, int(len(plain)), vecs, norms, proj, attn)

    key = "personas-" + name.replace("/", "--")
    from thorp.viable.s4_intelligence import readings

    readings.put(key, {**out, "name": key, "kind": "personas"})
    log(f"{name}: {len(vecs)} persona directions at layer {layer}, {out['seconds']}s -> {key}")
    return out


if __name__ == "__main__":
    import sys

    for name in sys.argv[1:]:
        read(name)
