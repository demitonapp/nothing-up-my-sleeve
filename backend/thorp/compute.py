"""Compute resources (10 November): the machines a yard can run on, what they are, what a test measured, what
they may spend, and which ships fit.

    uv run --project backend python -m thorp.compute detect
    uv run --project backend python -m thorp.compute add --kind mac --name "This Mac"
    uv run --project backend python -m thorp.compute test <resource_id>
    uv run --project backend python -m thorp.compute list
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time

from thorp.models import registry

# the throughput floor (tokens/s) a ship needs to be worth putting on a resource: below this the voyage takes
# longer than the queue can wait, so the resource is not its harbour
FLOOR = {"300k": 20_000, "1m": 8_000, "9m": 2_500, "21m": 1_200, "50m": 600, "100m": 300, "350m": 100}


def _sh(cmd: str) -> str | None:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def detect() -> dict:
    chip = _sh("sysctl -n machdep.cpu.brand_string") or platform.processor() or platform.machine()
    mem = _sh("sysctl -n hw.memsize")
    cores = _sh("sysctl -n hw.ncpu")
    gpu = _sh("system_profiler SPDisplaysDataType 2>/dev/null | grep 'Total Number of Cores' | head -1")
    return {"chip": chip, "machine": platform.machine(), "os": platform.platform(),
            "memory_gb": round(int(mem) / 1e9, 1) if mem and mem.isdigit() else None,
            "cpu_cores": int(cores) if cores and cores.isdigit() else None,
            "gpu": gpu}


def _id(kind: str, name: str) -> str:
    return "compute-" + hashlib.sha1(f"{kind}|{platform.node()}|{name}".encode()).hexdigest()[:10]


def add(kind: str = "mac", name: str = "This Mac", specs: dict | None = None,
        caps: dict | None = None) -> dict:
    from thorp import store, yard
    from thorp.viable.records import ComputeResource

    rid = _id(kind, name)
    yid = yard.ensure()
    with store.session() as s:
        r = s.get(ComputeResource, rid)
        if r is None:
            s.add(ComputeResource(resource_id=rid, yard_id=yid, kind=kind, name=name,
                                  specs=specs or (detect() if kind == "mac" else {}),
                                  caps=caps or {}, status="active"))
    return get(rid)


def get(resource_id: str) -> dict:
    from thorp import store
    from thorp.viable.records import ComputeResource

    with store.session() as s:
        r = s.get(ComputeResource, resource_id)
        if r is None:
            raise LookupError(f"no compute resource {resource_id}")
        return _row(r)


def _row(r) -> dict:
    return {"resource_id": r.resource_id, "yard_id": r.yard_id, "kind": r.kind, "name": r.name,
            "specs": r.specs or {}, "bench": r.bench or {}, "caps": r.caps or {}, "status": r.status}


def resources() -> list[dict]:
    from thorp import store
    from thorp.viable.records import ComputeResource

    with store.session() as s:
        return [_row(r) for r in s.query(ComputeResource).order_by(ComputeResource.name).all()]


def _memory_gb(preset: str) -> float | None:
    """A rough training memory: params in fp32 twice (weights + AdamW moments) plus activations. Enough to
    decide a harbour, not to predict a byte."""
    cfg = registry.PRESETS.get(preset) or {}
    if not cfg:
        return None
    params = cfg.get("params") or 0
    if not params:
        layers, width = cfg.get("layers", 0), cfg.get("width", 0)
        vocab = cfg.get("vocab", 2048)
        params = 12 * layers * width * width + layers * 4 * width * width + 2 * vocab * width
    return round(params * 4 * 2 / 1e9, 2)


def test(resource_id: str, preset: str = "300k", steps: int = 8, batch: int = 8, context: int = 256) -> dict:
    """A short measured test: forward steps on random tokens, tokens/s and peak memory, then the harbours."""
    import numpy as np
    import mlx.core as mx

    from thorp import store
    from thorp.viable.records import ComputeResource

    r = get(resource_id)
    cfg = registry.PRESETS[preset]
    model = registry.build("gpt", preset, vocab=cfg.get("vocab", 2048), context=context)
    x = mx.array(np.random.randint(0, cfg.get("vocab", 2048), (batch, context)).astype(np.int32))
    # warm-up (compilation is not throughput), then the measured steps
    mx.eval(model(x)[0] if isinstance(model(x), (list, tuple)) else model(x))
    t0 = time.time()
    for _ in range(steps):
        out = model(x)
        mx.eval(out[0] if isinstance(out, (list, tuple)) else out)
    dt = time.time() - t0
    tokens_s = steps * batch * context / dt if dt > 0 else 0.0
    peak = None
    try:
        peak = round(mx.metal.get_peak_memory() / 1e9, 2)
    except Exception:  # noqa: BLE001
        pass
    mem = (r["specs"] or {}).get("memory_gb")
    base = registry.PRESETS.get(preset) or {}
    p0 = base.get("params") or 1
    fits = {}
    for p in registry.PRESETS:
        need = _memory_gb(p)
        pp = (registry.PRESETS.get(p) or {}).get("params") or p0
        est = tokens_s * (p0 / pp) if pp else 0.0
        fits[p] = bool(need is not None and mem and need <= mem * 0.8 and est >= FLOOR.get(p, 0))
    bench = {"preset": preset, "tokens_s": round(tokens_s, 1), "peak_memory_gb": peak,
             "memory_need_gb": {p: _memory_gb(p) for p in registry.PRESETS},
             "fits": fits, "measured": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with store.session() as s:
        rr = s.get(ComputeResource, resource_id)
        rr.bench = bench
    return bench


def set_caps(resource_id: str, caps: dict) -> dict:
    """Record a resource's daily and weekly limits (USD and hours). The charter is what must enforce them."""
    from thorp import store
    from thorp.viable.records import ComputeResource

    with store.session() as s:
        r = s.get(ComputeResource, resource_id)
        if r is None:
            raise LookupError(f"no compute resource {resource_id}")
        r.caps = {**(r.caps or {}), **caps}
    return get(resource_id)


def list_() -> list[dict]:
    return resources()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(prog="thorp.compute")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect")
    a = sub.add_parser("add")
    a.add_argument("--kind", default="mac")
    a.add_argument("--name", default="This Mac")
    t = sub.add_parser("test")
    t.add_argument("resource_id")
    t.add_argument("--preset", default="300k")
    sub.add_parser("list")
    args = p.parse_args()
    if args.cmd == "detect":
        print(json.dumps(detect(), indent=1))
    elif args.cmd == "add":
        print(json.dumps(add(args.kind, args.name), indent=1))
    elif args.cmd == "test":
        print(json.dumps(test(args.resource_id, args.preset), indent=1))
    else:
        print(json.dumps(list_(), indent=1))
