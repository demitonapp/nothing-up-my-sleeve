"""A plan's version, `1.2.3` (8 November, Justin: "we need a numbering version for runs. with 1.2.3 where major
version is the journey of the ship, so order of the pretraining and postraining, the minor version is the content and
the last number can be something else").

- **Major — the journey.** The stages a ship lives through, in order: `["pretrain"]` today, so v1. A tutor or a
  post-training stage makes a new journey and a new major. The order *within* pretraining (metre before content, or
  content before metre) is a parameter, not a journey: it changes the patch.
- **Minor — the content.** The corpus list and its bytes, the tokeniser (kind, vocabulary, what it was trained on)
  and the cleaning. A new corpus version, or a list that adds a tutor's passages, is a new minor.
- **Patch — everything else that changes the plan.** The shape, the context, the optimiser, the passes, the
  scaffold's cards and schedule, a teacher. A **seed is not a version**: two seeds are one plan sailed twice.

The numbers are assigned on first sight of a plan and never reused (`s1.run_versions`), so a plan has exactly one
version and a *name* may have many runs — which is the trap this closes: the ledger holds three runs called
`fu-ogden-v0-1@1m-pre-s1`, two of them recalled stubs, and a reader who takes the first by name compares a finished
voyage with a three-minute one.

    uv run thorp version SPEC              # what this plan is, and its version if it has one
    uv run thorp version SPEC --assign     # assign one if it is new (a run does this itself at launch)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from thorp import paths


def _sha(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _list_sha(path: str | None) -> str | None:
    """A list's own bytes, so a corpus that is edited under the same name is a different content."""
    if not path:
        return None
    p = paths.resolve(path)
    if not p.exists():
        return None
    return hashlib.sha1(p.read_bytes()).hexdigest()


def journey(spec: dict) -> list[str]:
    """The stages a ship lives through, in order. Today every voyage is pretraining alone; a voyage with stages
    declared under `data.stages` names its own, and the order is the journey."""
    stages = (spec.get("data") or {}).get("stages") or []
    names = [str(s.get("name") or s.get("recipe") or "stage") for s in stages]
    return names or ["pretrain"]


def content_fp(spec: dict) -> str:
    """The content: the corpus (its path and its bytes), the tokeniser and the cleaning."""
    data = spec.get("data") or {}
    recipe = data.get("recipe") or ((data.get("stages") or [{}])[0] or {}).get("recipe")
    tok = spec.get("tokeniser") or {}
    return _sha({
        "recipe": recipe,
        "sha": _list_sha(recipe),
        "refuse": sorted(data.get("refuse") or []),
        "clean": data.get("clean"),
        "tokeniser": {k: tok.get(k) for k in ("kind", "vocab", "byte_fallback", "train_on")},
        "tokeniser_sha": _list_sha(tok.get("train_on")),
    })


def params_fp(spec: dict) -> str:
    """Everything else that changes the plan: the shape, the optimiser, the passes and order, the scaffold, a
    teacher. Not the seed (one plan, sailed twice), not the name, question, eval or sop (the standard is captured
    by the content and the parameters themselves)."""
    model = spec.get("model") or {}
    optim = {k: v for k, v in (spec.get("optim") or {}).items() if k != "seed"}
    data = spec.get("data") or {}
    return _sha({
        "model": {k: model.get(k) for k in ("family", "preset", "context", "positions", "backend")},
        "optim": optim,
        "passes": data.get("passes"),
        "order": data.get("order"),
        "stages": data.get("stages"),
    })


def describe(spec: dict) -> dict:
    """What a plan is, without the store: the journey, and the content and parameter fingerprints, short."""
    return {
        "journey": journey(spec),
        "content": content_fp(spec)[:12],
        "params": params_fp(spec)[:12],
    }


def of(spec: dict) -> str | None:
    """The version this plan already has, or None (by the registry; no store, no answer)."""
    from thorp import store
    from thorp.viable.records import RunVersion

    with store.session() as s:
        r = (
            s.query(RunVersion)
            .filter_by(journey_fp=_sha(journey(spec)), content_fp=content_fp(spec), params_fp=params_fp(spec))
            .first()
        )
        return r.version if r else None


def assign(spec: dict, *, run_id: str | None = None, spec_path: str | None = None) -> str:
    """The plan's version, assigned on first sight: a new journey takes the next major (minor and patch 0), a new
    content the next minor within its major (patch 0), anything else the next patch. Never reuses a number."""
    from thorp import store
    from thorp.viable.records import RunVersion

    j, c, p = _sha(journey(spec)), content_fp(spec), params_fp(spec)
    with store.session() as s:
        rows = s.query(RunVersion).all()
        for r in rows:
            if (r.journey_fp, r.content_fp, r.params_fp) == (j, c, p):
                if run_id and r.last_run != run_id:
                    r.last_run = run_id
                return r.version
        same_journey = [r for r in rows if r.journey_fp == j]
        if not same_journey:
            major, minor, patch = max((r.major for r in rows), default=0) + 1, 0, 0
        else:
            major = same_journey[0].major
            same_content = [r for r in same_journey if r.content_fp == c]
            if not same_content:
                minor, patch = max(r.minor for r in same_journey) + 1, 0
            else:
                minor = same_content[0].minor
                patch = max(r.patch for r in same_content) + 1
        version = f"{major}.{minor}.{patch}"
        s.add(
            RunVersion(
                version=version,
                major=major,
                minor=minor,
                patch=patch,
                journey_fp=j,
                content_fp=c,
                params_fp=p,
                journey=" > ".join(journey(spec)),
                first_spec=spec_path or str(spec.get("name") or ""),
                last_run=run_id,
            )
        )
    return version


def rows() -> list[dict]:
    """The register, oldest first: each version, its plan, the spec that made it and the last run that sailed it."""
    from thorp import store
    from thorp.viable.records import RunVersion

    with store.session() as s:
        return [
            {
                "version": r.version,
                "journey": r.journey,
                "first_spec": Path(r.first_spec).name,
                "last_run": (r.last_run or "")[:12],
                "created": r.created_at.strftime("%d %b %H:%M") if r.created_at else "",
            }
            for r in s.query(RunVersion).order_by(RunVersion.created_at).all()
        ]

def name_of(spec: dict) -> str:
    """The voyage's name, short: the size and the SOP version it is built to, e.g. `1m@v0.0.5` (9 November, Justin:
    "the journey fu-ogden-v0-1~sop005@1m-chart-pre-s1 should just be called 1m@v0.0.5 to simplify things"). A second
    arm of the same version carries its variation: `1m@v0.0.5-chart`. A voyage with no SOP keeps the old form."""
    preset = (spec.get("model") or {}).get("preset") or "?"
    sop = spec.get("sop")
    if not sop:
        return preset
    base = f"{preset}@v{sop}"
    var = str((spec.get("fitout") or {}).get("variation") or "").strip()
    tail = var.split("-")[-1] if var else ""
    return base if not tail or tail in ("", "launch") else f"{base}-{tail}"
