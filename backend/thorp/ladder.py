"""The quantum ladder's measurement contract.

Every Ogden and Kipling voyage is read on the same ladder: the reading skills (spelling, copying),
knowing (successor), reasoning, mathematics, the discovery tests, and the card/star/shape mechanisms.
The evaluators below are the ones that write those readings. `ensure` adds them to a voyage's spec;
`missing` says what a spec does not yet carry; `measure` (thorp measure) backfills finished voyages.

This is deliberately a small, explicit list: adding an evaluator here is a promise that every Ogden
and Kipling voyage will be read on it, so add it only when the evaluator is built and its data exists.
"""

from __future__ import annotations

LADDER_EVALUATORS: tuple[str, ...] = (
    "ce_bpb",
    "bpb_split",   # inside-word / word-start / space / newline: spelling and layout
    "laws",        # non-word rate and the other laws: real words, punctuation, brackets
    "successor",   # knowing: what follows what
    "maths",       # the maths book
    "logic",       # reasoning
    "discovery",   # the four discovery chains, every rung with pairs
    "stars",       # which heads light
    "nevermore",   # copying
    "cards",       # the deck
    "shapes",      # parts of speech and keyed words
    "pips",        # the metre
)

# The final bets have their own pair files (`lists/discovery-*.csv`). They are named here so the
# audit can say plainly when a ladder test cannot be measured because its questions are not written.
FINAL_BETS: tuple[str, ...] = ("origin_test", "energy_test", "mendeleev_gaps", "recurrence_test", "geometry_test")


def is_ladder_voyage(spec: dict) -> bool:
    """An Ogden voyage or a Kipling voyage, by its corpus or its name."""
    recipe = str((spec.get("data") or {}).get("recipe") or "").lower()
    name = str(spec.get("name") or "").lower()
    ship = str(spec.get("ship") or "").lower()
    return "ogden" in recipe or "kipling" in name or "kipling" in ship


def missing(spec: dict) -> list[str]:
    have = set((spec.get("eval") or {}).get("evaluators") or [])
    return [e for e in LADDER_EVALUATORS if e not in have]


def ensure(spec: dict) -> list[str]:
    """Add every ladder evaluator the spec lacks; return what was added. Mutates `spec` in place."""
    if not is_ladder_voyage(spec):
        return []
    add = missing(spec)
    if add:
        ev = list((spec.get("eval") or {}).get("evaluators") or [])
        spec.setdefault("eval", {})["evaluators"] = ev + add
    return add


def final_bet_data() -> dict[str, str]:
    """The final bets and the pair file each needs, for the coverage report."""
    from thorp import fleet, paths

    out: dict[str, str] = {}
    for key in FINAL_BETS:
        t = fleet.TRICKS.get(key)
        f = paths.resolve(t.pairs) if t and t.pairs else None
        out[key] = "present" if f and f.exists() else "not written"
    return out


def checkpoint_shape(run_id: str) -> tuple[int, int] | None:
    """(layers, width) from a run's latest model.safetensors, or None when it cannot be read."""
    from safetensors import safe_open

    from thorp import train

    ckpt = train.latest_checkpoint(run_id)
    if ckpt is None:
        return None
    f = ckpt / "model.safetensors"
    if not f.exists():
        return None
    with safe_open(str(f), framework="np") as sf:
        keys = list(sf.keys())
        if "tok.weight" not in keys:
            return None
        width = int(sf.get_slice("tok.weight").get_shape()[1])
        layers = sum(1 for k in keys if k.startswith("layers.") and k.endswith(".attn.proj.weight"))
    return layers, width


def compatible_with_preset(spec: dict, run_id: str) -> tuple[bool, str]:
    """Whether the checkpoint's layers/width match the current preset (a legacy shape can't load)."""
    shape = checkpoint_shape(run_id)
    if shape is None:
        return True, "no readable checkpoint"
    from thorp.models import registry

    preset = (spec.get("model") or {}).get("preset")
    cfg = registry.PRESETS.get(preset)
    if not cfg:
        return True, f"unknown preset {preset}"
    want = (int(cfg["layers"]), int(cfg["width"]))
    if shape != want:
        return False, f"legacy checkpoint {shape[0]}x{shape[1]}, preset {preset} is {want[0]}x{want[1]}"
    return True, "matches preset"


def repair_spec(spec: dict, run_id: str) -> None:
    """Put a checkpoint's own layers/width into its spec before a rescore.

    The preset names are stable but their shapes are not: a 300k was 2x64 before the deep ladder and
    is 6x48 now. The head count is kept from the base preset (only depth and width moved), so an old
    checkpoint loads into the model that wrote it instead of failing a reshape.
    """
    shape = checkpoint_shape(run_id)
    if shape is None:
        return
    from thorp.models import registry

    m = spec.setdefault("model", {})
    preset = str(m.get("preset") or "")
    base = preset.split("-")[0]
    cfg = registry.PRESETS.get(preset) or registry.PRESETS.get(base)
    if cfg is None:
        return
    layers, width = shape
    if layers != cfg["layers"] or width != cfg["width"]:
        m["preset"] = base
        m["layers"] = layers
        m["width"] = width
        m["heads"] = cfg["heads"]
