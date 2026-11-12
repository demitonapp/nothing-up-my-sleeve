"""Smoke-test Vast.ai GPU classes: hire the cheapest offer, check the GPU and CUDA, release.

This is not a voyage: no spec, no data, no queue line. It exists to answer one question — does a class
come up, answer ssh, see its GPU, and run a bf16 CUDA matmul in the image's torch? — for a few cents a
class. Each hire and release is written to the spend log, labelled `thorp:smoke-...`, so the week's
spend stays honest and an interrupted run is visible to `thorp charter audit`.

The charter's S5 filters still apply, with one deliberate exception for a class with no offer inside
them: the price ceiling is relaxed by 15% and reliability to 0.94. The result says when it was relaxed,
and nothing here changes the terms a voyage sails under.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/smoke_vast_gpus.py
    ... --gpus "RTX 4090" "H100 SXM"
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import time
from pathlib import Path

from thorp import paths
from thorp.viable.s1_operations import charter as c
from thorp.viable.s1_operations.vast import Vast
from thorp.viable.s3_control import charter as s3
from thorp.viable.s5_policy import charter as s5

DEFAULT_GPUS = ["RTX 4090", "RTX 5090", "H100 SXM", "H100 PCIE"]
SMOKE_CODE = """
import json, torch
out = {"torch": torch.__version__, "cuda": torch.version.cuda, "available": bool(torch.cuda.is_available())}
if out["available"]:
    out["device"] = torch.cuda.get_device_name(0)
    out["capability"] = list(torch.cuda.get_device_capability(0))
    a = torch.randn(2048, 2048, device="cuda", dtype=torch.bfloat16)
    b = (a @ a).float()
    out["matmul_mean"] = round(float(b.abs().mean()), 4)
    m = torch.nn.Linear(128, 128, device="cuda")
    x = torch.randn(256, 128, device="cuda")
    loss = (m(x) ** 2).mean()
    loss.backward()
    torch.optim.AdamW(m.parameters()).step()
    out["train_step_loss"] = round(float(loss), 4)
print(json.dumps(out))
"""


def slug(gpu: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", gpu.lower()).strip("-")


def offers_for(v: Vast, gpu: str, terms: dict, relaxed: bool) -> list[dict]:
    t = dict(terms)
    if relaxed:
        t = {**t, "gpus": {**t["gpus"], gpu: float(t["gpus"][gpu]) * 1.15}, "min_reliability": 0.94}
    return v.search(gpu, t)


def smoke(gpu: str, terms: dict) -> dict:
    v = Vast()
    t0 = time.time()
    row: dict = {"gpu": gpu, "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "failed"}
    relaxed = False
    offers = offers_for(v, gpu, terms, relaxed=False)
    if not offers:
        relaxed = True
        offers = offers_for(v, gpu, terms, relaxed=True)
    row["relaxed"] = relaxed
    if not offers:
        row["status"] = "no offer"
        print(f"[{gpu}] no offer inside the terms or the 15% smoke exception", flush=True)
        return row
    o = offers[0]
    if o["dph"] > 4.0:
        row["status"] = f"refused: ${o['dph']:.2f}/h over the smoke cap"
        return row
    row.update({"offer": o["offer_id"], "dph": round(o["dph"], 4), "ceiling": terms["gpus"][gpu],
                "machine": o.get("machine_id"), "reliability": o.get("reliability")})  # fmt: skip
    instance = None
    run_id = f"smoke-{slug(gpu)}-{int(t0)}"
    hire = None
    try:
        print(f"[{gpu}] hiring offer {o['offer_id']} at ${o['dph']:.3f}/h"
              f"{' (relaxed terms)' if relaxed else ''}", flush=True)
        instance = v.hire(o["offer_id"], terms["image"], int(terms["disk_gb"]), f"thorp:{run_id}")
        row["instance"] = instance
        hire = {"instance": instance, "run_id": run_id, "gpu": gpu, "dph": o["dph"], "started": time.time(),
                "name": f"smoke {gpu}", "quote_hours": 0.25}  # fmt: skip
        s3.record("hired", instance=instance, run_id=run_id, gpu=gpu, dph=o["dph"], started=hire["started"],
                  name=hire["name"], quote=0.25, quote_hours=0.25)  # fmt: skip
        key = c._public_key(terms)
        if key:
            v.attach_ssh(instance, key)
        inst = v.wait_running(instance, sleep=time.sleep)
        row["provision_s"] = round(time.time() - t0, 1)
        box = c.Box(inst["ssh_host"], inst["ssh_port"])
        box.log = lambda m: print(f"  [{gpu}] {m}", flush=True)
        box.deadline = time.time() + 600
        t_ssh = time.time()
        tries = box.wait_ssh(sleep=time.sleep)
        row["ssh_s"] = round(time.time() - t_ssh, 1)
        row["ssh_tries"] = tries
        gpu_line = box.sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader", timeout=60)
        row["nvidia_smi"] = (gpu_line.stdout or "").strip().splitlines()[:1]
        py = box.sh("python3 -c " + shlex.quote(SMOKE_CODE), timeout=180)
        if py.returncode != 0:
            raise c.BoxError(f"torch smoke failed: {(py.stderr or py.stdout or '')[-400:]}")
        info = json.loads((py.stdout or "").strip().splitlines()[-1])
        row.update({"torch": info.get("torch"), "cuda": info.get("cuda"), "available": info.get("available"),
                    "device": info.get("device"), "capability": info.get("capability"),
                    "matmul_mean": info.get("matmul_mean"), "train_step_loss": info.get("train_step_loss")})  # fmt: skip
        row["status"] = "ok" if info.get("available") and info.get("matmul_mean") is not None else "failed: cuda unavailable"
        row["box"] = {"nproc": box.sh("nproc", timeout=30).stdout.strip(),
                      "mem_gb": box.sh("free -g | awk 'NR==2{print $2}'", timeout=30).stdout.strip(),
                      "disk": box.sh("df -h /root | tail -1", timeout=30).stdout.strip()}  # fmt: skip
    except Exception as e:  # noqa: BLE001 - one class failing must not stop the others
        row["status"] = f"failed: {type(e).__name__}: {str(e)[:300]}"
        print(f"[{gpu}] FAILED: {row['status']}", flush=True)
    finally:
        ended = time.time()
        released = False
        if instance is not None:
            try:
                v.release(instance)
                released = True
            except Exception as e:  # noqa: BLE001
                print(f"[{gpu}] release failed: {e}", flush=True)
            if hire is not None:
                s3.record("released", instance=instance, run_id=run_id, gpu=gpu, dph=hire["dph"],
                          started=hire["started"], ended=ended, cost=s3.cost_of(hire, ended),
                          status=("smoke ok" if row["status"] == "ok" else f"smoke {row['status']}")
                          if released else "smoke release failed")  # fmt: skip
        row["cost"] = round(s3.cost_of(hire, ended), 4) if hire else 0.0
        row["wall_s"] = round(ended - t0, 1)
        row["released"] = released
        print(f"[{gpu}] {row['status']} — {row.get('device', '–')}, {row['wall_s']} s, ${row['cost']:.3f}", flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="smoke-test Vast.ai GPU classes")
    ap.add_argument("--gpus", nargs="+", default=DEFAULT_GPUS)
    ap.add_argument("--out", default=str(paths.data_dir() / "runs" / "smoke-vast.json"))
    a = ap.parse_args()
    terms = s5.terms()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    for gpu in a.gpus:
        print(f"\n=== {gpu} ===", flush=True)
        results.append(smoke(gpu, terms))
        out.write_text(json.dumps(results, indent=1))
    print("\n=== summary ===")
    for r in results:
        print(f"{r['gpu']:12s} {r['status']:8s} {r.get('device', '–'):22s} ${r.get('cost', 0):.3f} {r.get('wall_s', 0):.0f} s")
    print(f"\nwritten to {out}")
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
