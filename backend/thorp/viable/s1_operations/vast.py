"""S1's chandler: the Vast.ai REST API, as far as a charter needs it (docs.vast.ai/api-reference, read 2026-11-08).

    search offers   POST   /api/v0/bundles/            {"gpu_name": {"eq": ...}, ..., "order": [[f, "asc"]], "limit": n}
    hire            PUT    /api/v0/asks/{offer}/       {"image", "disk", "label", "runtype": "ssh", "onstart"}
    show            GET    /api/v0/instances/{id}/     {"instances": {...}}
    list            GET    /api/v1/instances/          paged by next_token
    release         DELETE /api/v0/instances/{id}/
    ssh key         POST   /api/v0/instances/{id}/ssh/ {"ssh_key": ...}
    credit          GET    /api/v0/users/current/      {"credit": ...}

The key is read from VAST_API_KEY, else from data/secrets/vast-api-key (data/ is never in git); it is sent only to
console.vast.ai, in the Authorization header. Every call goes through `transport`, so the tests hire from a fake
market (tests/test_charter.py) and nothing here has touched the real API until Justin's key arrives: where the docs
were ambiguous (the gpu_name spelling, "RTX 4090" or "RTX_4090"; the credit field), `search` and `credit` try both.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

from thorp import paths

BASE = "https://console.vast.ai"

Transport = Callable[[str, str, dict | None, dict | None], dict]  # (method, path, json body, query) -> json


class NoKey(RuntimeError):
    pass


class VastError(RuntimeError):
    pass


def key_path():
    return paths.data_dir() / "secrets" / "vast-api-key"


def api_key() -> str:
    from thorp import providers

    k = providers.vast_key()
    if not k:
        raise NoKey(f"no Vast.ai API key: set VAST_API_KEY or write it to {key_path()} (never to git)")
    return k


def http_transport(key: str | None = None, retries: int = 4) -> Transport:
    import requests

    def call(method: str, path: str, body: dict | None = None, query: dict | None = None) -> dict:
        headers = {"Authorization": f"Bearer {key or api_key()}", "Accept": "application/json"}
        for attempt in range(retries + 1):
            r = requests.request(method, BASE + path, json=body, params=query, headers=headers, timeout=60)
            if r.status_code == 429 and attempt < retries:  # "API requests too frequent"
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise VastError(f"{method} {path}: {r.status_code} {r.text[:300]}")
            return r.json() if r.content else {}
        raise VastError(f"{method} {path}: still rate-limited")

    return call


def required_cuda(lock: Path | None = None) -> float:
    """The CUDA the box's torch is built against, read from backend/uv.lock (`nvidia-cuda-runtime`, as
    major.minor), or 0.0 when the lock cannot be read. A host's driver must support at least this: on 12 November
    a voyage reached the sea on a host whose driver stopped at CUDA 12.8 and died in `torch._C._cuda_init()`
    ("The NVIDIA driver on your system is too old (found version 12080)"), because the lock had moved to the
    CUDA 13.2 wheels while S5's `min_cuda` still said 12.8. The lock is the truth; the term is only a floor."""
    import re

    try:
        text = (lock or Path(__file__).resolve().parents[3] / "uv.lock").read_text(encoding="utf-8")
    except OSError:
        return 0.0
    m = re.search(r'name = "nvidia-cuda-runtime(?:-cu\d+)?"\s*\nversion = "(\d+)\.(\d+)', text)
    return float(f"{m.group(1)}.{m.group(2)}") if m else 0.0


class Vast:
    def __init__(self, transport: Transport | None = None):
        self.call = transport or http_transport()

    # ---- the market

    def search(self, gpu: str, terms: dict, limit: int = 20, avoid: frozenset | set = frozenset()) -> list[dict]:
        """Offers of one GPU class that keep the host terms, cheapest first, each normalised (`offer`).

        `avoid` holds offers (`o<offer id>`) and machines (`m<machine id>`) not to be offered again: a box on them
        never answered (12 November: the same cheapest 4090 offer was hired again a minute after its box had
        refused ssh for ten minutes). They are dropped here, and as many more are asked for."""
        q = {
            "num_gpus": {"eq": 1},
            "rentable": {"eq": True},
            "rented": {"eq": False},
            "reliability": {"gte": float(terms["min_reliability"])},
            "inet_down": {"gte": float(terms["min_inet_down_mbps"])},
            "inet_up": {"gte": float(terms["min_inet_up_mbps"])},
            "disk_space": {"gte": float(terms["disk_gb"])},
            # the driver must carry the torch the box installs (the lock), whatever the term's floor says
            "cuda_max_good": {"gte": max(float(terms["min_cuda"]), required_cuda())},
            "dph_total": {"lte": float(terms["gpus"][gpu])},
            "order": [["dph_total", "asc"]],
            "type": "ondemand",
            "limit": limit + len(avoid),
        }
        if terms.get("verified"):
            q["verified"] = {"eq": True}
        for name in dict.fromkeys((gpu, gpu.replace(" ", "_"))):  # the docs spell it both ways
            res = self.call("POST", "/api/v0/bundles/", {**q, "gpu_name": {"eq": name}}, None)
            offers = res.get("offers") or []
            if isinstance(offers, dict):
                offers = [offers]
            if offers:
                kept = [x for x in (offer(o, gpu) for o in offers) if not avoided(x, avoid)]
                return kept[:limit]
        return []

    # ---- a ship

    def hire(self, offer_id: int, image: str, disk_gb: int, label: str, onstart: str = "") -> int:
        body = {"image": image, "disk": disk_gb, "label": label, "runtype": "ssh", "target_state": "running"}
        if onstart:
            body["onstart"] = onstart
        res = self.call("PUT", f"/api/v0/asks/{int(offer_id)}/", body, None)
        if not res.get("success") or not res.get("new_contract"):
            raise VastError(f"hire of offer {offer_id} refused: {json.dumps(res)[:300]}")
        return int(res["new_contract"])

    def show(self, instance: int) -> dict:
        res = self.call("GET", f"/api/v0/instances/{int(instance)}/", None, None)
        inst = res.get("instances", res)
        if isinstance(inst, list):
            inst = inst[0] if inst else {}
        return inst or {}

    def instances(self) -> list[dict]:
        out, token = [], None
        while True:
            q = {"limit": 25, **({"after_token": token} if token else {})}
            res = self.call("GET", "/api/v1/instances/", None, q)
            out += res.get("instances") or []
            token = res.get("next_token")
            if not token:
                return out

    def attach_ssh(self, instance: int, public_key: str) -> None:
        self.call("POST", f"/api/v0/instances/{int(instance)}/ssh/", {"ssh_key": public_key}, None)

    def release(self, instance: int) -> None:
        """Destroy the instance: its rental and its storage stop. Irreversible (what was not brought home is lost)."""
        self.call("DELETE", f"/api/v0/instances/{int(instance)}/", None, None)

    def charges(self) -> list[dict]:
        """What Vast.ai has billed this account, a line an instance a kind a day (`charge`): the GPU's hours, the
        disk's hours, and the gigabytes moved down and up. The same lines as the invoice CSV the console exports
        (12 November: they came to $9.29 where the spend log counted $6.22, the account's `total_spend`)."""
        res = self.call("GET", "/api/v0/users/me/invoices/", None, {"inc_charges": "true"})
        return [charge(x) for x in res.get("invoices") or [] if x.get("type") == "charge"]

    def credit(self) -> float | None:
        try:
            u = self.call("GET", "/api/v0/users/current/", None, None)
        except VastError:
            return None
        for k in ("credit", "balance"):
            if isinstance(u.get(k), int | float):
                return float(u[k])
        return None

    def wait_running(self, instance: int, timeout: float = 900, every: float = 10, sleep=time.sleep) -> dict:
        """Until the instance is running with an SSH address (pulling a large image takes minutes)."""
        t0 = time.time()
        while True:
            inst = self.show(instance)
            if inst.get("actual_status") == "running" and inst.get("ssh_host") and inst.get("ssh_port"):
                return inst
            if inst.get("actual_status") in ("exited", "offline") or time.time() - t0 > timeout:
                raise VastError(f"instance {instance} did not come up: {inst.get('actual_status')!r} {inst.get('status_msg', '')}")
            sleep(every)


def avoided(o: dict, avoid) -> bool:
    """Whether an offer (as `offer` normalises it) is one `avoid` names, by its id or its machine's."""
    return f"o{o.get('offer_id')}" in avoid or (o.get("machine_id") is not None and f"m{o['machine_id']}" in avoid)


def ssh_route(inst: dict) -> tuple[str, int] | None:
    """Where an instance's ssh answers, as Vast.ai says now: its proxy host and port, or None before it has one."""
    host, port = inst.get("ssh_host"), inst.get("ssh_port")
    return (str(host), int(port)) if host and port else None


def charge(x: dict) -> dict:
    """One billed line, as the spend reads it: the instance, its kind (gpu, storage, download, upload or other),
    the day it was billed on (UTC midnight, as Vast.ai buckets them) and the dollars."""
    d = str(x.get("description") or "").lower()
    kind = next((k for k, w in (("gpu", "gpu"), ("storage", "storage"), ("download", "download"), ("upload", "upload")) if w in d), "other")
    iid = x.get("instance_id")
    return {"instance": int(iid) if iid not in (None, "") else None, "kind": kind, "at": float(x.get("timestamp") or 0.0),
            "amount": float(x.get("amount") or 0.0), "quantity": float(x.get("quantity") or 0.0)}  # fmt: skip


def offer(o: dict, gpu: str) -> dict:
    """An offer as the charter reads it."""
    return {
        "offer_id": int(o.get("id") or o.get("ask_contract_id")),
        "gpu": gpu,
        "gpu_name": o.get("gpu_name", gpu),
        "dph": float(o.get("dph_total", 0.0)),
        "verified": bool(o.get("verified", o.get("verification") == "verified")),
        "reliability": float(o.get("reliability", o.get("reliability2", 0.0)) or 0.0),
        "inet_down": float(o.get("inet_down", 0.0) or 0.0),
        "inet_up": float(o.get("inet_up", 0.0) or 0.0),
        "cuda": float(o.get("cuda_max_good", 0.0) or 0.0),
        "disk_gb": float(o.get("disk_space", 0.0) or 0.0),
        "geolocation": o.get("geolocation", ""),
        "machine_id": o.get("machine_id"),
        # billed apart from `dph` (12 November): the disk a GB a month, the line a GB each way
        "storage_cost": float(o.get("storage_cost", 0.0) or 0.0),
        "inet_down_cost": float(o.get("inet_down_cost", 0.0) or 0.0),
        "inet_up_cost": float(o.get("inet_up_cost", 0.0) or 0.0),
    }
