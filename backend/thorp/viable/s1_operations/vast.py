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
import os
import time
from collections.abc import Callable

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


class Vast:
    def __init__(self, transport: Transport | None = None):
        self.call = transport or http_transport()

    # ---- the market

    def search(self, gpu: str, terms: dict, limit: int = 20) -> list[dict]:
        """Offers of one GPU class that keep the host terms, cheapest first, each normalised (`offer`)."""
        q = {
            "num_gpus": {"eq": 1},
            "rentable": {"eq": True},
            "rented": {"eq": False},
            "reliability": {"gte": float(terms["min_reliability"])},
            "inet_down": {"gte": float(terms["min_inet_down_mbps"])},
            "inet_up": {"gte": float(terms["min_inet_up_mbps"])},
            "disk_space": {"gte": float(terms["disk_gb"])},
            "cuda_max_good": {"gte": float(terms["min_cuda"])},
            "dph_total": {"lte": float(terms["gpus"][gpu])},
            "order": [["dph_total", "asc"]],
            "type": "ondemand",
            "limit": limit,
        }
        if terms.get("verified"):
            q["verified"] = {"eq": True}
        for name in dict.fromkeys((gpu, gpu.replace(" ", "_"))):  # the docs spell it both ways
            res = self.call("POST", "/api/v0/bundles/", {**q, "gpu_name": {"eq": name}}, None)
            offers = res.get("offers") or []
            if isinstance(offers, dict):
                offers = [offers]
            if offers:
                return [offer(o, gpu) for o in offers]
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
    }
