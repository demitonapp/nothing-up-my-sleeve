"""S1: a chartered voyage, the same voyage on a GPU hired from Vast.ai (2026-11-08, Justin: "i'm going to use vast.ai
can you build the code via the VSM system in order to leverage vast.ai").

    thorp charter quote ships/specs/<voyage>.yaml        what it would cost on each class the terms allow
    thorp charter sail  ships/specs/<voyage>.yaml        hire, sail, bring home, release
    thorp charter audit [--release-orphans]              S3*: nothing hired is forgotten

The voyage, in order, each step owned by its system:

1. **Prepared here** (train.prepare: S3's gate on the voyage, the tokeniser, the shards), and its plan read: the
   steps left from its last checkpoint, so a voyage cut short by a lost ship sails on from where it was.
2. **Quoted** (S4, s4_intelligence.market): the cheapest offer of each class the terms allow, priced for this
   voyage's tokens; the cheapest voyage is chosen.
3. **Gated** (S3 for S5, vsm.POLICIES["charter"]): the quote against the terms (the ceiling an hour, a verified and
   reliable host, the voyage's budget, the week's, the account's credit, the ships already out). Refused, nothing
   is hired.
4. **Hired** (S1, a berth held by S2): the instance created with the label `thorp:<run id>`, logged in S3's spend
   log the moment it exists, so S3* can find it if this process dies.
5. **Fitted out**: rsync and uv put aboard; the code (what git tracks of backend/ and ships/), the library the
   voyage reads (data/ without the checkpoints, the logs or the secrets; the shards and tokeniser of its own
   tokeniser only), the ship's papers (s2_coordination.charter.papers, never the whole ledger), and its last
   checkpoint and those of the runs it is seeded from or taught by.
6. **At sea**: `thorp run` on the box with THORP_BACKEND=torch (the spec's own run id), checked every minute;
   every `pull_every_min` its checkpoints and rows are brought home (so the dashboard shows it sailing); after
   the quote's hours times the terms' overrun it is brought home and released, whatever its state.
7. **Home and released**: the checkpoints, the log and the rows brought home (s2_coordination.charter.bring_home),
   and the instance destroyed in a `finally`: a failure anywhere after the hire still releases the ship. The
   release is logged with what the voyage cost and the tokens a second it made (S4's measured rate next time).
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import yaml

from thorp import paths, store
from thorp.ledger import Ledger
from thorp.viable.s1_operations.vast import NoKey, Vast, api_key, http_transport
from thorp.viable.s2_coordination import charter as s2
from thorp.viable.s3_control import charter as s3
from thorp.viable.s4_intelligence import market
from thorp.viable.s5_policy import charter as s5

REMOTE = "/root/thorp"  # the repository's root on the box: backend/, ships/, data/, ledger.sqlite
LABEL = "thorp:"  # every instance a charter hires is labelled thorp:<run id>
PULL_EVERY_MIN = 20

# data/ entries never carried aboard: the checkpoints (only the voyage's own are), the logs, the local stores,
# and above all the secrets (the Vast.ai key)
NOT_CARRIED = {
    "checkpoints", "runs", "compare", "loop", "postgres", "secrets", "shards", "tokenisers", "charter",
    "acquisition", "helm.lock", "helm.json", "gate-log.jsonl", "postgres.log", "postgres-init.log", "lanes.json", "lanes.lock",
}  # fmt: skip


class NoOffer(RuntimeError):
    pass


class BoxError(RuntimeError):
    """A command on the box failed; the message carries ssh's or the command's own stderr."""


# ---------------------------------------------------------------- the box


class Box:
    """The hired machine, reached by ssh and rsync as root (Vast.ai's SSH)."""

    def __init__(self, host: str, port: int, key_file: str | None = None, run=subprocess.run, log=None):
        self.host, self.port, self.run = host, int(port), run
        self.log = log  # every step says when it starts and how long it took (9 November: a silent box looked stuck)
        kh = paths.data_dir() / "charter" / "known_hosts"
        kh.parent.mkdir(parents=True, exist_ok=True)
        # BatchMode: never stop at a prompt (a passphrase comes from the agent or the keychain, or not at all)
        self.opts = ["-p", str(self.port), "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={kh}",
                     "-o", "ServerAliveInterval=30", "-o", "ConnectTimeout=20", "-o", "BatchMode=yes"] + (["-i", key_file] if key_file else [])  # fmt: skip

    def _say(self, what: str, t0: float | None = None) -> None:
        """One line of the box's log: what it is doing, and how long that took."""
        if not self.log:
            return
        took = f" ({time.time() - t0:.1f}s)" if t0 else ""
        self.log(f"[box] {what}{took}")

    def sh(self, cmd: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess:
        t0 = time.time()
        self._say(f"ssh: {cmd[:100]}")
        r = self.run(["ssh", *self.opts, f"root@{self.host}", cmd], check=False, capture_output=True, text=True, timeout=timeout)
        self._say(f"ssh done, exit {r.returncode}", t0)
        if r.returncode != 0:
            tail = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()[-800:]
            if tail:
                self._say(f"its words: {tail}")
        if check and r.returncode != 0:  # ssh's own words (255: it could not connect or was refused), not just a code
            raise BoxError(f"ssh {self.host}:{self.port} exit {r.returncode}: {(r.stderr or '').strip()[-600:]} (ran: {cmd[:120]})")
        return r

    def wait_ssh(self, timeout_s: float = 600, every_s: float = 15, sleep=time.sleep, on_denied=None, denied_after: int = 6) -> int:
        """Until the box answers ssh (2026-11-08: the first charter's box was "running" by Vast.ai's API but refused the
        first ssh, and the fit-out gave up at once). Vast.ai's ssh proxy and the instance's key can take a minute or more
        after "running". If the box still refuses the key after `denied_after` tries, `on_denied` (attach the key again)
        is called once. Returns the tries it took; raises BoxError with ssh's last words at the timeout."""
        last, tries, denied_fixed = "", max(1, int(timeout_s // every_s)), False
        for i in range(1, tries + 1):
            r = self.run(["ssh", *self.opts, f"root@{self.host}", "true"], check=False, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return i
            last = (r.stderr or "").strip()
            if on_denied and not denied_fixed and i >= denied_after and "denied" in last.lower():
                on_denied()
                denied_fixed = True
            sleep(every_s)
        raise BoxError(f"ssh {self.host}:{self.port} never answered in {timeout_s:.0f} s: {last[-600:]}")

    def _rsh(self) -> str:
        return "ssh " + " ".join(shlex.quote(o) for o in self.opts)

    def put_tar(self, root: Path, rels: list[str], dst: str = "") -> None:
        """The files `rels` to REMOTE/dst as **one tar over ssh** (9 November: rsync'ing 20,000 small files to the box
        took most of an hour; a single stream is minutes). Bytes are equal; the transfer is one connection."""
        if not rels:
            return
        t0 = time.time()
        self._say(f"tar {len(rels)} files to {dst or '/'}")
        lst = paths.data_dir() / "charter" / f"tar-{os.getpid()}.txt"
        lst.write_text("\n".join(rels) + "\n")
        tar_cmd = ["tar", "czf", "-", "-C", str(root), f"--files-from={lst}"]
        remote = f"mkdir -p {REMOTE}/{dst} && tar xzf - -C {REMOTE}/{dst}"
        send = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        r = self.run(["ssh", *self.opts, f"root@{self.host}", remote], stdin=send.stdout, capture_output=True, text=True)
        send.stdout.close()
        send.wait()
        lst.unlink(missing_ok=True)
        self._say(f"tar done ({len(rels)} files)", t0)
        if r.returncode != 0:
            raise BoxError(f"tar upload failed: {(r.stderr or '').strip()[-400:]}")

    def put(self, root: Path, rels: list[str], dst: str = "") -> None:
        """The files `rels` (relative to `root`) to REMOTE/dst, their paths kept."""
        if not rels:
            return
        lst = paths.data_dir() / "charter" / f"files-{os.getpid()}.txt"
        lst.write_text("\n".join(rels) + "\n")
        target = f"root@{self.host}:{REMOTE}/{dst}".rstrip("/") + "/"
        t0 = time.time()
        self._say(f"rsync {len(rels)} files to {dst or '/'}")
        self.run(["rsync", "-a", "--partial", "-e", self._rsh(), f"--files-from={lst}", f"{root}/", target], check=True)
        self._say(f"rsync done ({len(rels)} files)", t0)
        lst.unlink(missing_ok=True)

    def get(self, src: str, dst: Path) -> bool:
        """REMOTE/src (a folder or a file) to dst; False when it is not there yet."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        r = self.run(["rsync", "-a", "--partial", "-e", self._rsh(), f"root@{self.host}:{REMOTE}/{src}", str(dst)], check=False)
        return r.returncode == 0

    def bootstrap(self) -> None:
        self.sh(
            "set -e; command -v rsync >/dev/null || (apt-get update -qq && apt-get install -y -qq rsync);"
            " command -v uv >/dev/null || [ -x ~/.local/bin/uv ] || (curl -LsSf https://astral.sh/uv/install.sh | sh);"
            f" mkdir -p {REMOTE}/data/charter",
            timeout=900,
        )

    def sync_env(self) -> None:
        self._say("syncing the box's environment (uv sync --group torch): this is the step that stalled on 8 November")
        self.sh(f"cd {REMOTE} && ~/.local/bin/uv sync --project backend --group torch -q", timeout=1800)

    def launch(self, rid: str) -> None:
        inner = (
            f"~/.local/bin/uv run --project backend --group torch thorp run data/charter/{rid}.yaml "
            f"> data/charter/{rid}.out 2>&1; echo $? > data/charter/{rid}.exit"
        )
        # One backgrounded command with all three of its streams redirected: `cd X && cmd > /dev/null &` backgrounds the
        # whole && list as a subshell whose stdout is still ssh's, so ssh stayed open for the whole voyage (2026-11-08, P1:
        # the charter never reached its poll loop, so no mid-run pulls and no overrun deadline).
        papers = f"{REMOTE}/data/charter/{rid}.papers.json"  # the S5 state its gate reads (thorp/store.py)
        self.sh(f"cd {REMOTE}; THORP_BACKEND=torch THORP_DEVICE=cuda THORP_PAPERS={papers} nohup sh -c {shlex.quote(inner)} > /dev/null 2>&1 < /dev/null &", timeout=120)

    def finished(self, rid: str) -> int | None:
        """The voyage's exit status once it has come in, else None."""
        r = self.sh(f"cat {REMOTE}/data/charter/{rid}.exit 2>/dev/null || true", check=False, timeout=60)
        out = (r.stdout or "").strip()
        return int(out) if out.lstrip("-").isdigit() else None


# ---------------------------------------------------------------- the plan and the quote


def plan(spec: dict, prep) -> dict:
    """The voyage's tokens in all and from its last checkpoint on, as train.train will stream them."""
    from thorp import data, train

    o, m = spec["optim"], spec["model"]
    books = prep.books()
    families = {b: books[b].family for b in books}
    if spec["data"].get("stages"):
        stream = data.Staged(
            spec["data"]["stages"],
            [data.stream(ids, prep.tokeniser.id, spec["seed"] * 1000 + i, o["batch_tokens"], m["context"], st["passes"], families)
             for i, (st, ids) in enumerate(zip(spec["data"]["stages"], prep.stage_recipes, strict=True))],
        )  # fmt: skip
    else:
        stream = data.stream(
            prep.recipe, prep.tokeniser.id, spec["seed"], o["batch_tokens"], m["context"], spec["data"]["passes"],
            families, first=prep.first, first_repeats=spec["data"].get("first_repeats", 1),
        )  # fmt: skip
    rid = train.run_id(spec)
    ck = train.latest_checkpoint(rid)
    start = int(ck.name.split("-")[1]) if ck else 0
    return {
        "run_id": rid,
        "total_steps": stream.total_steps,
        "start": start,
        "tokens_per_step": stream.tokens_per_step,
        "tokens_left": (stream.total_steps - start) * stream.tokens_per_step,
    }


def _cfg(spec: dict, vocab: int):
    from thorp.models import registry

    m = spec["model"]
    return registry.config(m["preset"], vocab, m["context"], m.get("positions", "learned"))


class _Ceilings:
    """The market when no key is in hand: every class at its ceiling, a host that just keeps the terms."""

    def search(self, gpu, terms, limit=5):
        return [{"offer_id": 0, "gpu": gpu, "gpu_name": gpu, "dph": float(terms["gpus"][gpu]), "verified": True,
                 "reliability": float(terms["min_reliability"]), "inet_down": float(terms["min_inet_down_mbps"]),
                 "inet_up": float(terms["min_inet_up_mbps"]), "cuda": float(terms["min_cuda"]),
                 "disk_gb": float(terms["disk_gb"]), "geolocation": "", "machine_id": None}]  # fmt: skip

    def credit(self):
        return None


def quote(spec_path: str, gpu: str | None = None, vast=None, resolver=None, log=print) -> dict:
    """Prepare the voyage here, read its plan and the market; returns {spec, prep, plan, quotes, market}. Without a
    Vast.ai key the market is the terms' ceilings (an upper bound, marked as such)."""
    from thorp import train

    spec = train.load_spec(spec_path)
    if spec["model"].get("backend", "torch") != "torch":
        raise ValueError(f"model.backend is {spec['model']['backend']!r}: a chartered voyage sails on torch")
    t = s5.terms()
    prep = train.prepare(spec, **({"resolver": resolver} if resolver else {}), log=log)
    p = plan(spec, prep)
    market_read = "market"
    if vast is None:
        try:
            vast = Vast(http_transport(api_key()))
        except NoKey:
            vast, market_read = _Ceilings(), "ceilings (no Vast.ai key: the terms' ceiling prices)"
    qs = market.quotes(vast, _cfg(spec, prep.tokeniser.vocab_size), spec["model"]["preset"], p["tokens_left"], t,
                       gpus=[gpu] if gpu else None)  # fmt: skip
    credit = vast.credit()
    out_ = len(s3.out_now())
    spent = s3.week_spent()
    for q in qs:
        q.update(week_spent=spent, credit=credit, instances_out=out_, tokens=p["tokens_left"], run_id=p["run_id"])
        q["breaks"] = s3.violations(q, t)
    return {"spec": spec, "prep": prep, "plan": p, "quotes": qs, "market": market_read, "vast": vast, "terms": t}


def gate(spec: dict, q: dict) -> None:
    """S3 asks S5's charter policy of the chosen quote (vsm.gate_one: refused, nothing is hired)."""
    from thorp import vsm

    vsm.gate_one("charter", {**spec, "charter": {**(spec.get("charter") or {}), "quote": q}}, where="charter")


# ---------------------------------------------------------------- the voyage


def voyage_books(prep) -> set[str]:
    """The books a voyage reads, by id: its recipe, its stages and opening books, its judge sets, and the fixed
    books its evaluators read (Goldsmith's essays, the Nevermore's and the copying cards' passage). Refused books
    are checked by id alone and need no text."""
    from thorp.evaluators.nevermore import NATURAL_BOOK

    ids = set(prep.recipe) | set(getattr(prep, "first", []) or []) | {NATURAL_BOOK}
    for s in getattr(prep, "stage_recipes", []) or []:
        ids |= set(s)
    for s in prep.eval_sets.values():
        ids |= set(s)
    return ids


def text_files(ids: set[str]) -> list[str]:
    """Where each book's text lies under data/ (sources: a Gutenberg book pgN is texts/gutenberg/N.txt; any
    other source's book is texts/<source>/<id>.txt), the ones that exist."""
    from thorp import manifest

    d, out = paths.data_dir(), []
    for bid in sorted(ids):
        b = manifest.get(bid)  # a book not in this library (a fixed evaluator book, say) is skipped
        if b is None:
            continue
        rel = f"texts/gutenberg/{int(bid[2:])}.txt" if b.source == "gutenberg" and bid.startswith("pg") else f"texts/{b.source}/{bid}.txt"
        if (d / rel).is_file():
            out.append(rel)
    return out


def carried_data(tok_id: str, books: set[str] | None = None) -> list[str]:
    """data/ as the box needs it, relative to data/: the library's records, the texts of the books the voyage
    reads (`books`; the whole library when None, or with THORP_CARRY_ALL_TEXTS=1), the voyage's own tokeniser and
    shards; never the checkpoints, the logs or the secrets. SQLite files are carried as copies (`stage`).
    (8 November: P1 carried the whole 1.8 GB library, 1.65 GB of it unread, most of its 22 minutes' fitting out.)"""
    d = paths.data_dir()
    trim = books is not None and os.environ.get("THORP_CARRY_ALL_TEXTS") != "1"
    out = []
    for p in sorted(d.iterdir()):
        if p.name in NOT_CARRIED or p.name.startswith("charter") or p.suffix in (".sqlite-wal", ".sqlite-shm") or p.suffix == ".sqlite":
            continue
        if trim and p.name == "texts":
            continue
        out += [str(f.relative_to(d)) for f in ([p] if p.is_file() else sorted(p.rglob("*"))) if f.is_file()]
    if trim:
        out += text_files(books)
    for sub in ("tokenisers", "shards"):
        root = d / sub / tok_id
        if root.exists():
            out += [str(f.relative_to(d)) for f in sorted(root.rglob("*")) if f.is_file()]
    return out


def stage(rid: str) -> Path:
    """Consistent copies of data/'s SQLite files (the manifest), made with SQLite's backup, for carrying."""
    st = paths.data_dir() / "charter" / rid / "stage"
    if st.exists():
        shutil.rmtree(st)
    st.mkdir(parents=True)
    for db in paths.data_dir().glob("*.sqlite"):
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        dst = sqlite3.connect(st / db.name)
        src.backup(dst)
        src.close()
        dst.close()
    return st


def checkpoints_carried(rid: str, spec: dict, rec: Ledger) -> list[str]:
    """The latest checkpoint of the voyage and of each run it reads from, relative to data/."""
    from thorp import train

    rids = [rid] + [
        r[0]["run_id"]
        for n in s2.related_runs(spec)
        if (r := rec.query("select run_id from runs where name=? and status='finished' order by started desc", [n]))
    ]
    out = []
    for r in rids:
        ck = train.latest_checkpoint(r)
        if ck:
            out += [str(f.relative_to(paths.data_dir())) for f in sorted(ck.rglob("*")) if f.is_file()]
    return out


def _public_key(t: dict) -> str | None:
    for p in [t.get("ssh_key")] + [str(Path.home() / ".ssh" / n) for n in ("id_ed25519.pub", "id_rsa.pub")]:
        if p and Path(p).expanduser().exists():
            return Path(p).expanduser().read_text().strip()
    return None


def bring_home(box, rid: str, start: int, rec: Ledger, hire: dict, commit: str) -> dict:
    """The checkpoints, the box's log and the voyage's rows, home."""
    from thorp import train

    box.get(f"data/checkpoints/{rid}/", train.checkpoint_root(rid))
    box.get(f"data/runs/{rid}.log", paths.runs_dir() / f"{rid}.box.log")
    box.get(f"data/charter/{rid}.out", paths.data_dir() / "charter" / rid / "box.out")
    gate_log = paths.data_dir() / "charter" / rid / "box-gate-log.jsonl"
    if box.get(f"data/charter/{rid}.papers.gate-log.jsonl", gate_log):  # the box's gate decisions, into s3.gate_decisions
        store.fold_gate_log(gate_log, source=f"box papers {rid}")
    led = paths.data_dir() / "charter" / rid / "box-ledger.sqlite"
    if not box.get("ledger.sqlite", led):
        return {}
    for side in ("-wal", "-shm"):  # the box's ledger is in WAL mode: its last rows may be in the -wal file
        box.get(f"ledger.sqlite{side}", led.with_name(led.name + side))
    try:
        return s2.bring_home(led, rid, start, rec, commit=commit,
                             hardware=f"{_box_hardware(led, rid)} · vast.ai instance {hire['instance']} at ${hire['dph']:.3f}/h")  # fmt: skip
    except LookupError:
        return {}


def _register_home(rec: Ledger, rid: str, log) -> None:
    """The voyage registered with its ship, at home (aboard there is no store to register it in)."""
    from thorp import fleet

    row = rec.get_run(rid)
    if not row:
        return
    try:
        ship = fleet.ship_of_run(row)
        log(f"charter: {row.get('name')} registered as a voyage of {ship.name} ({ship.key})")
    except Exception as e:  # noqa: BLE001  (a ship not registered never costs a voyage; said, not hidden)
        log(f"charter: {row.get('name')} not registered with its ship: {e!r}")


def _box_hardware(led: Path, rid: str) -> str:
    con = sqlite3.connect(f"file:{led}?mode=ro", uri=True)
    r = con.execute("select hardware from runs where run_id=?", (rid,)).fetchone()
    con.close()
    return (r[0] if r and r[0] else "torch").replace("unknown (FileNotFoundError) · ", "")


def _measured_rate(rec: Ledger, rid: str, start: int) -> float | None:
    rows = rec.query("select value from metrics where run_id=? and name='tokens_per_s' and step>? order by value", [rid, start + 5])
    return rows[len(rows) // 2]["value"] if rows else None


_LOG_PATH: list = []


def _say(*a, **k) -> None:
    """Print, flush, **and append to `data/runs/charter.log`** with a timestamp: a charter's log is read while it runs
    (9 November: two hires stalled silently — Python buffers stdout when it is a file, and the lane's log held nothing)."""
    import time

    msg = " ".join(str(x) for x in a)
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, **k, flush=True)
    try:
        from thorp import paths

        f = _LOG_PATH[0] if _LOG_PATH else (paths.data_dir() / "runs" / "charter.log")
        _LOG_PATH[:] = [f]
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def sail(spec_path: str, gpu: str | None = None, vast=None, resolver=None, box_factory=None, rec: Ledger | None = None,
         log=_say, sleep=time.sleep, poll_s: float = 60.0) -> dict:  # fmt: skip
    """The chartered voyage, from the quote to the release. Returns what it came home with."""
    from thorp import train

    rec = rec or Ledger()
    q0 = quote(spec_path, gpu=gpu, vast=vast, resolver=resolver, log=log)
    spec, p, t, vast = q0["spec"], q0["plan"], q0["terms"], q0["vast"]
    rid = p["run_id"]
    if (rec.get_run(rid) or {}).get("status") == "finished":
        log(f"charter: {rid[:12]} has finished; nothing to sail")
        return {"run_id": rid, "status": "finished"}
    if isinstance(vast, _Ceilings):
        raise NoKey("a charter needs a Vast.ai key to hire (VAST_API_KEY or data/secrets/vast-api-key)")
    if not q0["quotes"]:
        raise NoOffer(f"no offer keeps the terms for {gpu or ', '.join(t['gpus'])}")
    q = q0["quotes"][0]
    gate(spec, q)
    log(f"charter: {q['gpu']} offer {q['offer_id']} at ${q['dph']:.3f}/h, about {q['hours']:.1f} h, ${q['cost']:.2f} ({q['speed']})")
    commit = train.git_commit()
    with s2.berth(t["max_instances"], rid):
        instance = vast.hire(q["offer_id"], t["image"], int(t["disk_gb"]), LABEL + rid)
        hire = s3.record("hired", instance=instance, run_id=rid, name=spec.get("name"), gpu=q["gpu"], dph=q["dph"],
                         offer=q["offer_id"], started=time.time(), quote=q["cost"], quote_hours=q["hours"],
                         preset=spec["model"]["preset"], start_step=p["start"])  # fmt: skip
        s2.note(rid, event="hired", instance=instance, gpu=q["gpu"], dph=q["dph"])
        status, counts = "lost", {}
        try:
            key = _public_key(t)
            if key:
                vast.attach_ssh(instance, key)
            inst = vast.wait_running(instance, sleep=sleep)
            box = (box_factory or (lambda i: Box(i["ssh_host"], i["ssh_port"])))(inst)
            try:
                box.log = log
            except Exception:
                pass
            log(f"charter: instance {instance} is up ({inst.get('ssh_host')}:{inst.get('ssh_port')}); waiting for its ssh")
            tries = box.wait_ssh(sleep=sleep, on_denied=(lambda: vast.attach_ssh(instance, key)) if key else None)
            log(f"charter: ssh answered (try {tries}); fitting out")
            box.bootstrap()
            code = subprocess.run(["git", "ls-files", "backend", "ships"], cwd=paths.ROOT, capture_output=True, text=True, check=True).stdout.split()
            box.put_tar(paths.ROOT, code)  # one stream: rsync'ing 20k small files took most of an hour on 9 November
            box.put_tar(paths.data_dir(), carried_data(q0["prep"].tokeniser.id, voyage_books(q0["prep"])) + checkpoints_carried(rid, spec, rec), "data")  # the data too, as one stream (8,907 files took 16 min by rsync)
            st = stage(rid)
            s2.papers(st / "ledger.sqlite", spec, rid, rec)
            box.put(st, sorted(f.name for f in st.glob("*.sqlite") if f.name != "ledger.sqlite"), "data")
            box.put(st, ["ledger.sqlite"])
            (st / f"{rid}.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
            (st / f"{rid}.papers.json").write_text(json.dumps(store.papers_for_box(), ensure_ascii=False, indent=1))
            box.put(st, [f"{rid}.yaml", f"{rid}.papers.json"], "data/charter")
            box.sync_env()
            box.launch(rid)
            log(f"charter: {spec.get('name')} is at sea on instance {instance}")
            deadline = time.time() + q["hours"] * float(t["overrun"]) * 3600
            last_pull = time.time()
            strikes = 0  # consecutive polls the box did not answer; a blip is logged, a lost box is brought home after ten
            while True:
                try:
                    code_ = box.finished(rid)
                    strikes = 0
                except (BoxError, subprocess.TimeoutExpired) as e:
                    code_, strikes = None, strikes + 1
                    log(f"charter: the box did not answer ({strikes}/10): {str(e)[-200:]}")
                    if strikes >= 10:
                        status = "lost contact"
                        break
                if code_ is not None:
                    status = "home" if code_ == 0 else f"failed (exit {code_})"
                    break
                if time.time() > deadline:
                    status = "overran"
                    log(f"charter: past {q['hours'] * float(t['overrun']):.1f} h (the quote times the overrun): bringing it home")
                    break
                if time.time() - last_pull > PULL_EVERY_MIN * 60:
                    try:  # a failed mid-run pull must not release the box: the next pull, or the last, takes it
                        counts = bring_home(box, rid, p["start"], rec, hire, commit)
                    except Exception as e:  # noqa: BLE001
                        log(f"charter: a mid-run pull failed ({e!r}); sailing on")
                    last_pull = time.time()
                sleep(poll_s)
            for attempt in range(3):  # the last pull is the voyage: try it three times before the box is released
                try:
                    counts = bring_home(box, rid, p["start"], rec, hire, commit)
                    break
                except Exception as e:  # noqa: BLE001
                    log(f"charter: the last pull failed (try {attempt + 1}/3): {e!r}")
                    if attempt == 2:
                        raise
                    sleep(30)
            _register_home(rec, rid, log)
            if status == "home" and (rec.get_run(rid) or {}).get("status") != "finished":
                status = "came in unfinished"  # the box's voyage stopped short (its checkpoint is home: sail again)
        finally:
            ended = time.time()
            try:
                vast.release(instance)
                released = True
            except Exception as e:  # noqa: BLE001
                released = False
                log(f"charter: RELEASE FAILED for instance {instance} ({e!r}): thorp charter audit --release-orphans")
            if released:
                rate = _measured_rate(rec, rid, p["start"])
                s3.record("released", instance=instance, run_id=rid, gpu=q["gpu"], dph=q["dph"], preset=spec["model"]["preset"],
                          started=hire["started"], ended=ended, cost=s3.cost_of(hire, ended), status=status, tokens_per_s=rate)  # fmt: skip
            s2.note(rid, event="released" if released else "release failed", instance=instance, status=status)
    cost = s3.cost_of(hire, ended)
    log(f"charter: {spec.get('name')} {status}; instance {instance} released; ${cost:.2f} for {(ended - hire['started']) / 3600:.2f} h")
    if status != "home" and (rec.get_run(rid) or {}).get("status") == "running":
        rec.run({"run_id": rid, "status": f"chartered: {status}"})
    return {"run_id": rid, "status": status, "instance": instance, "cost": cost, "rows": counts}
