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
import os
import re
import subprocess
from datetime import UTC, datetime
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


# ---------------------------------------------------------------- provenance: what a run id does not pin
#
# 11 November (the architecture audit, item 3). A run id is the SHA-1 of the spec as hashed (train.canonical, after
# ladder.ensure), and the spec names its lists by path, its parents by name, and its code not at all: an edited list
# trains other books under the old id, a reused name hands a seed or a teacher from another run, and 177 of 180 runs
# carry a "-dirty" commit that cannot tell one dirty tree from another. The id cannot change (a changed id makes
# every finished voyage look unsailed, and the coordinator would sail them again), so what pins a voyage is written
# beside it at the start of every sailing, by both trainers: this document, as a `provenance` artifact (which a
# hired box's own ledger carries home with the rest, charter.bring_home) and, at home, a row of s1.run_provenance.
# The readers take the row, and the artifact where there is no row (a box's voyage, folded home): one reader, two
# places, and no fold-home step to forget. Never a reason to stop a voyage: a failure is logged and it sails on.

# The environment the trainers and the code they call read (11 November, by grep of os.environ over train.py,
# train_torch.py, data.py, models/, evaluators/ and what they import). These change what is trained or measured:
RESULT_ENV = (
    "THORP_BACKEND",  # which loop sails the spec (models/backend.py)
    "THORP_DEVICE",  # the torch device: CPU and CUDA give other numbers (train_torch.device)
    "THORP_TORCH_COMPILE",  # torch.compile's kernels (train_torch.train)
    "THORP_DATA",  # the books, shards and tokenisers read (paths.data_dir)
    "THORP_SHIPS",  # the lists and specs read (paths.ships_dir)
    "THORP_IFEVAL_LIMIT",  # how many IFEval prompts are scored (evaluators/ifeval.py)
    "THORP_SHAPES_LEXICON",  # the shapes evaluator's lexicon (evaluators/shapes.py)
    "THORP_ARC_LIMIT", "THORP_ARC_MAX_OUTPUT", "THORP_ARC_IDS", "THORP_ARC",  # the ARC puzzles scored (arc.py)
    "THORP_BLIMP",  # the BLiMP pairs read (blimp.py)
    "NLTK_DATA",  # IFEval's and the answers evaluator's word lists
    "THORP_GENERATE_CACHE",  # 0 turns off the cached greedy writing (models/ops.Decoder); a bf16 near-tie can differ
)
# ... and these only say where rows are written or read, who holds the helm, or whom to name: recorded by name only
# (THORP_PG may carry a password).
LOGGING_ENV = (
    "THORP_LEDGER", "THORP_LEDGER_PG", "THORP_LEDGER_DUAL", "THORP_SHIP_LOG", "THORP_PG", "THORP_PAPERS",
    "THORP_LIBRARY_PG", "THORP_HELM_SLOTS", "THORP_HELM_SLOT", "THORP_CONTACT",
)
LIST_SUFFIXES = (".csv", ".tsv", ".txt", ".json", ".jsonl")
# the parents a voyage reads from, by where the spec names them (the same three as charter.related_runs)
PARENTS = {
    "seeded_from": ("seeded_from", "run"),
    "teacher": ("optim", "teacher", "run"),
    "transplant": ("transplant", "from_run"),
}
_RUN_ID = re.compile(r"[0-9a-f]{40}")


def is_run_id(ref) -> bool:
    """Whether a parent is named by its run id (forty hex characters) rather than by a name."""
    return isinstance(ref, str) and bool(_RUN_ID.fullmatch(ref))


def _is_list_path(v) -> bool:
    return (
        isinstance(v, str)
        and 0 < len(v) < 512
        and not any(c.isspace() for c in v)
        and (v.startswith("lists/") or v.lower().endswith(LIST_SUFFIXES))
    )


def list_fields(spec: dict) -> dict[str, str]:
    """Every list the hashed part of a spec names, by where it names it ("data.recipe", "data.stages[0].recipe",
    "data.refuse[0]", "eval.sets[3]", "tokeniser.train_on", an evaluator's pair file under eval.options ...): any
    string that is a list's path (under lists/, or a .csv/.tsv/.txt/.json/.jsonl file). Walked rather than named, so a
    list field added tomorrow is not missed. The labels (train.NOT_HASHED) are not looked into."""
    from thorp.train import NOT_HASHED

    out: dict[str, str] = {}

    def walk(v, p: str) -> None:
        if isinstance(v, dict):
            for k, x in v.items():
                if not p and k in NOT_HASHED:
                    continue
                walk(x, f"{p}.{k}" if p else str(k))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, f"{p}[{i}]")
        elif _is_list_path(v):
            out[p] = v

    walk(spec, "")
    return out


def list_shas(spec: dict) -> dict[str, str | None]:
    """The SHA-1 of each named list's bytes today, by path (None: no such file)."""
    out = {}
    for p in sorted(set(list_fields(spec).values())):
        try:
            out[p] = _list_sha(p)
        except Exception:  # noqa: BLE001
            out[p] = None
    return out


def parent_refs(spec: dict) -> dict[str, str]:
    """The parents a spec names, as it names them (a run id or a name), by role."""
    out = {}
    for role, keys in PARENTS.items():
        v = spec
        for k in keys:
            v = v.get(k) if isinstance(v, dict) else None
        if v:
            out[role] = str(v)
    return out


def parents(spec: dict) -> dict[str, dict]:
    """Each named parent resolved to the run id the trainer reads (train.parent_run: by id when named by id, else
    the newest finished run of that name), with how it was named."""
    from thorp import train

    out = {}
    for role, ref in parent_refs(spec).items():
        entry = {"ref": ref, "by": "id" if is_run_id(ref) else "name", "run_id": None}
        try:
            entry["run_id"] = train.parent_run(ref, role)["run_id"]
        except Exception as e:  # noqa: BLE001  (the trainer raises for a missing parent; here it is noted)
            entry["error"] = f"{e.__class__.__name__}: {e}"
        out[role] = entry
    return out


def _git(*args: str, text: bool = True):
    return subprocess.run(["git", *args], cwd=paths.ROOT, capture_output=True, text=text, timeout=60)


def code_state() -> dict:
    """The code that trains: the commit, whether the tree is dirty, and a SHA-1 of `git diff HEAD -- backend` and of
    the untracked files under backend/thorp, so one dirty run can be told from another."""
    head = _git("rev-parse", "HEAD")
    if head.returncode != 0:
        return {"commit": None, "error": (head.stderr or "").strip()[:200] or "not a git checkout"}
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no").stdout.strip())
    diff = _git("diff", "HEAD", "--", "backend", text=False).stdout or b""
    untracked = sorted(_git("ls-files", "--others", "--exclude-standard", "--", "backend/thorp").stdout.split())
    h = hashlib.sha1()
    for f in untracked:
        h.update(f.encode() + b"\0")
        try:
            h.update((paths.ROOT / f).read_bytes())
        except OSError:
            pass
        h.update(b"\0")
    return {
        "commit": head.stdout.strip(),
        "dirty": dirty,
        "diff_sha1": hashlib.sha1(diff).hexdigest() if diff else None,
        "diff_bytes": len(diff),
        "untracked": untracked,
        "untracked_sha1": h.hexdigest() if untracked else None,
    }


def backend_state(spec: dict) -> dict:
    """The loop that sails the spec and the versions of what computes it."""
    import importlib.metadata as md
    import platform

    from thorp.models.backend import backend_of

    def ver(pkg: str) -> str | None:
        try:
            return md.version(pkg)
        except Exception:  # noqa: BLE001
            return None

    return {
        "backend": backend_of(spec),
        "THORP_BACKEND": os.environ.get("THORP_BACKEND"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        **{p: ver(p) for p in ("mlx", "torch", "numpy", "sentencepiece")},
    }


def env_state() -> dict:
    """The environment that changes results, by value; that which only moves records, by name."""
    return {
        "changes_results": {k: os.environ[k] for k in RESULT_ENV if k in os.environ},
        "logging_only_set": sorted(k for k in LOGGING_ENV if k in os.environ),
    }


def _section(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001  (one section that cannot be read never loses the others)
        return {"error": f"{e.__class__.__name__}: {e}"}


def provenance(spec: dict, rid: str, tokeniser_id: str | None = None, start: int = 0) -> dict:
    """What this sailing of run `rid` is trained from: the spec exactly as hashed, the bytes of every list it names,
    its parents by run id, the tokeniser, the code, the backend and the environment that changes results."""
    from thorp import train

    canon = train.canonical(spec)
    return {
        "v": 1,
        "run_id": rid,
        "id_of_spec": hashlib.sha1(canon.encode()).hexdigest(),  # equals run_id when the spec is the one hashed
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "from_step": int(start),
        "spec": json.loads(canon),
        "list_fields": _section(list_fields, spec),
        "lists": _section(list_shas, spec),
        "parents": _section(parents, spec),
        "tokeniser_id": tokeniser_id,
        "code": _section(code_state),
        "backend": _section(backend_state, spec),
        "env": _section(env_state),
    }


def _home_store(rec) -> bool:
    """Whether `rec` writes the home store (Postgres, or the dual recorder): only then is the side table written
    and read, so a box's own ledger, or a test's, answers from its artifacts alone."""
    try:
        from thorp.ledger_store import PgLedger
    except Exception:  # noqa: BLE001
        return False
    return isinstance(rec, PgLedger) or isinstance(getattr(rec, "__dict__", {}).get("pg"), PgLedger)


def _store_row(rid: str, doc: dict) -> None:
    """The side table's row: a sailing from step 0 replaces it; a resume is appended under `resumes` (its spec
    left out: the id says it is the same)."""
    from sqlalchemy import text

    from thorp import store

    body = json.dumps(doc, ensure_ascii=False, default=str)
    resume = json.dumps({k: v for k, v in doc.items() if k != "spec"}, ensure_ascii=False, default=str)
    if doc.get("from_step", 0) == 0:
        sql = (
            "insert into s1.run_provenance (run_id, doc) values (:r, cast(:d as jsonb)) "
            "on conflict (run_id) do update set doc = excluded.doc, recorded_at = now()"
        )
    else:
        sql = (
            "insert into s1.run_provenance (run_id, doc) values (:r, cast(:d as jsonb)) "
            "on conflict (run_id) do update set doc = s1.run_provenance.doc || jsonb_build_object('resumes', "
            "coalesce(s1.run_provenance.doc->'resumes', '[]'::jsonb) || jsonb_build_array(cast(:e as jsonb)))"
        )
    with store.session() as s:
        s.execute(text("SET LOCAL lock_timeout = '5s'"))
        s.execute(text(sql), {"r": rid, "d": body, "e": resume})


def stored_provenance(rid: str, rec=None) -> dict | None:
    """The provenance a run was first recorded with: the side table's row at home, else its earliest `provenance`
    artifact (a box's voyage, or a ledger that is not the home store). None when it has none (every run before 11
    November)."""
    from thorp.ledger import reader

    rec = rec or reader()
    if _home_store(rec):
        try:
            from sqlalchemy import text

            from thorp import store

            with store.session() as s:
                row = s.execute(text("select doc from s1.run_provenance where run_id = :r"), {"r": rid}).first()
            if row is not None:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:  # noqa: BLE001  (no side table yet, or the store is away: the artifact answers)
            pass
    rows = rec.query(
        "select text from artifacts where run_id=? and kind='provenance' order by step asc, rowid asc limit 1", [rid]
    )
    return json.loads(rows[0]["text"]) if rows and rows[0].get("text") else None


def list_drift(doc: dict) -> dict[str, tuple[str | None, str | None]]:
    """The lists a recorded run read whose bytes differ today: path -> (the SHA-1 then, the SHA-1 now)."""
    then = doc.get("lists") or {}
    if not isinstance(then, dict) or "error" in then:
        return {}
    out = {}
    for p, sha in then.items():
        try:
            now = _list_sha(p)
        except Exception:  # noqa: BLE001
            now = None
        if now != sha:
            out[p] = (sha, now)
    return out


def drift_lines(rid: str, changed: dict) -> list[str]:
    """The loud warning for lists that changed under a finished run's id."""
    return [
        f"WARNING: run {rid[:12]} was trained on lists whose bytes have changed since; its result stands for the "
        "old contents, and sailing this spec again would not reproduce it:",
        *(f"WARNING:   {p}: {(a or 'missing')[:12]} then, {(b or 'missing')[:12]} now" for p, (a, b) in changed.items()),
    ]


def record_provenance(spec: dict, rid: str, tokeniser_id: str | None, rec, log=print, start: int = 0) -> dict | None:
    """Write this sailing's provenance (called by both trainers once the run row is written and, from step 0,
    after the step-0 clear-out). The artifact is at step 0 for a sailing from the start, else at `start + 1`: a
    resume truncates what lies after its checkpoint's step and charter.bring_home folds home only what lies after
    the leg's first step, so the resumed leg's document survives both. A resume whose lists have changed since the
    first sailing is said loudly. Returns the document, or None when it could not be made; never raises."""
    try:
        doc = provenance(spec, rid, tokeniser_id, start)
        if start > 0:
            earlier = None
            try:
                earlier = stored_provenance(rid, rec)
            except Exception:  # noqa: BLE001
                pass
            changed = list_drift(earlier) if earlier else {}
            for line in drift_lines(rid, changed) if changed else []:
                log(line.replace("was trained", "was first trained"))
        rec.artifact(rid, 0 if start == 0 else start + 1, "provenance", "", "", json.dumps(doc, ensure_ascii=False, default=str))
        if _home_store(rec):
            try:
                _store_row(rid, doc)
            except Exception as e:  # noqa: BLE001  (the artifact holds it; the readers fall back to it)
                log(f"provenance: side table not written ({e.__class__.__name__}: {e}); the artifact holds it")
        code = doc["code"] if isinstance(doc.get("code"), dict) else {}
        par = doc["parents"] if isinstance(doc.get("parents"), dict) else {}
        log(
            f"provenance: {len(doc['lists']) if 'error' not in doc['lists'] else '?'} lists hashed, code "
            f"{(code.get('commit') or '?')[:12]}"
            + (f" dirty (diff {(code.get('diff_sha1') or '-')[:8]})" if code.get("dirty") else "")
            + "".join(f", {role} {p.get('ref')} = run {(p.get('run_id') or '?')[:12]}" for role, p in par.items() if isinstance(p, dict))
        )
        return doc
    except Exception as e:  # noqa: BLE001  (bookkeeping never stops a voyage)
        try:
            log(f"provenance: not recorded ({e.__class__.__name__}: {e})")
        except Exception:  # noqa: BLE001
            pass
        return None


def warn_if_lists_changed(rid: str, rec=None, out=print) -> dict:
    """For `thorp run` of a spec already finished: when the run's provenance is recorded and a list it read has
    other bytes today, say so loudly (no re-sail, no refusal: the old result stands for the old contents). Returns
    the changed lists."""
    doc = stored_provenance(rid, rec)
    changed = list_drift(doc) if doc else {}
    for line in drift_lines(rid, changed) if changed else []:
        out(line)
    return changed


def tokeniser_mismatch(checkpoint_state: dict, tokeniser_id: str) -> str | None:
    """Why a resume must be refused, or None: the checkpoint was written under another tokeniser than the one this
    sailing built (a list edited, a cleaning or a setting changed under the same run id). A checkpoint that names no
    tokeniser (older ones) is not judged."""
    was = (checkpoint_state or {}).get("tokeniser_id")
    if not was or was == tokeniser_id:
        return None
    return (
        f"refusing to resume run {str(checkpoint_state.get('run_id') or '')[:12]}: its checkpoint (step "
        f"{checkpoint_state.get('step')}) was trained with tokeniser {was[:12]}, and this sailing built "
        f"{tokeniser_id[:12]} (a list, the cleaning or a tokeniser setting has changed under the same run id). "
        "The weights would read other pieces than they learned. Restore the lists the run was trained on, or sail "
        "the changed spec as a new run."
    )


# ---------------------------------------------------------------- the drift report (read-only)


def drift_report(only: set[str] | None = None) -> dict:
    """For every finished run whose spec names lists: whether today's list files still hash to what the run read.
    Only knowable where something was recorded: the provenance (from 11 November), or the plan register's
    content fingerprint (s1.run_versions.content_fp, 8 November on), which covers the corpus list (`data.recipe`, or
    the first stage's) and the tokeniser's `train_on`, and is tied to a run only as the register's `last_run`.
    Reads the store; writes nothing. `only`: these run ids alone (a test's, in a shared test database)."""
    from thorp import store
    from thorp.ledger_store import PgLedger, Run
    from thorp.viable.records import RunVersion

    with store.session() as s:
        runs = [
            (r.run_id, r.name, r.spec_json)
            for r in s.query(Run).filter(Run.status == "finished").all()
            if only is None or r.run_id in only
        ]
        plans = s.query(RunVersion).all()
        versions = {r.last_run: r for r in plans if r.last_run}
    pg = PgLedger()
    out = {
        "finished": len(runs), "naming_lists": 0, "with_provenance": 0, "with_content_record": 0, "no_record": 0,
        "same": 0, "changed": 0, "changed_runs": [], "missing_lists_today": 0,
        "plan_registered": 0, "plan_content_same": 0, "plan_content_changed": 0, "plan_changed_runs": [],
    }
    for rid, name, spec_json in runs:
        try:
            spec = json.loads(spec_json or "{}")
        except ValueError:
            continue
        if not list_fields(spec):
            continue
        out["naming_lists"] += 1
        if any(sha is None for sha in list_shas(spec).values()):
            out["missing_lists_today"] += 1
        doc = None
        try:
            doc = stored_provenance(rid, pg)
        except Exception:  # noqa: BLE001
            pass
        if doc:
            out["with_provenance"] += 1
            changed = sorted(list_drift(doc))
        elif rid in versions:
            out["with_content_record"] += 1
            changed = [] if content_fp(spec) == versions[rid].content_fp else ["data.recipe / tokeniser.train_on"]
        else:
            out["no_record"] += 1
            # weaker, by plan not by run: the register holds this plan (its journey and parameters) under some
            # run, and today's content fingerprint is, or is not, one it was registered with
            jp = (_sha(journey(spec)), params_fp(spec))
            seen = {v.content_fp for v in plans if (v.journey_fp, v.params_fp) == jp}
            if seen:
                out["plan_registered"] += 1
                if content_fp(spec) in seen:
                    out["plan_content_same"] += 1
                else:
                    out["plan_content_changed"] += 1
                    out["plan_changed_runs"].append({"run_id": rid[:12], "name": name})
            continue
        if changed:
            out["changed"] += 1
            out["changed_runs"].append({"run_id": rid[:12], "name": name, "lists": changed})
        else:
            out["same"] += 1
    pg.close()
    return out


if __name__ == "__main__":  # python -m thorp.versioning drift: the read-only report, printed
    import sys

    if sys.argv[1:2] == ["drift"]:
        print(json.dumps(drift_report(), indent=1, ensure_ascii=False))
