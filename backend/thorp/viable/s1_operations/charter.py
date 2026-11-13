"""S1: a chartered voyage, the same voyage on a GPU hired from Vast.ai (2026-11-08, Justin: "i'm going to use vast.ai
can you build the code via the Liberty Machine system in order to leverage vast.ai").

    thorp charter quote ships/specs/<voyage>.yaml        what it would cost on each class the terms allow
    thorp charter sail  ships/specs/<voyage>.yaml        hire, sail, bring home, release
    thorp charter attach <run id | instance | name>      take up a ship still hired whose charter died
    thorp charter audit [--release-orphans]              S3*: nothing hired is forgotten

The voyage, in order, each step owned by its system:

1. **Prepared here** (train.prepare: S3's gate on the voyage, the tokeniser, the shards), and its plan read: the
   steps left from its last checkpoint, so a voyage cut short by a lost ship sails on from where it was.
2. **Quoted** (S4, s4_intelligence.market): the cheapest offer of each class the terms allow, priced for this
   voyage's tokens; the cheapest voyage is chosen.
3. **Gated** (S3 for S5, liberty_machine.POLICIES["charter"]): the quote against the terms (the ceiling an hour, a verified and
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

What an outage on this Mac may and may not do to a ship (11 November, the architecture audit's item 2):

- **Lost contact releases nothing.** A poll the box does not answer is logged and tried again, every minute,
  until the box answers or the overrun deadline comes. Only the deadline (the quote times the terms' overrun,
  S5's policy, unchanged) brings a ship home unfinished. Until 11 November ten silent minutes released it.
- **SIGTERM and SIGHUP are a recall, not a death.** While a ship is hired they raise `Recalled` in the charter,
  so the same clean-up runs as for any failure: the ship is released and the release is logged with its
  instance. Before, the process died where it stood and the ship went on billing with no charter.
- **A charter that does die** (SIGKILL, a power cut) leaves its hire in S3's spend log, as it always did, and
  now the deadline too (an `at sea` event). `attach` reads them and takes up the polling, the pulls, the
  deadline and the release of the ship that is still up, where `sail` would hire a second.
"""

from __future__ import annotations

import contextlib
import json
import os
import shlex
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import yaml

from thorp import paths, store
from thorp.ledger import Ledger, reader
from thorp.viable.s1_operations.vast import (
    NoKey,
    Vast,
    VastError,
    api_key,
    http_transport,
    ssh_route,
)
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
    # the sources' catalogues, the classics shelf and the local foreign models are not what a voyage trains or
    # reads on: carrying them put 8.4 GB of the 9.07 GB the 9m candidate uploaded aboard (12 November)
    "catalogue", "classics", "models",
    # never aboard a hired box (13 November): the drones' browser profile (its cookies and saved logins), the e-mail
    # accounts and their secrets, the phone's calls, and what was downloaded for the library (data/downloads: AI2's ARC
    # corpus, research use only and not to be redistributed, 2.17 GB, carried on every hire for an hour). None is read
    # by a voyage; NOT_CARRIED_WORDS below keeps anything named like a secret home as well
    "browser-profile", "browser-sites.json", "drones", "drones.json", "email-accounts.json", "email-secrets.json",
    "phone-calls.json", "personaplex.log", "downloads",
}  # fmt: skip
# a file or folder whose name says it holds a secret stays home, whatever folder it is in
NOT_CARRIED_WORDS = ("secret", "credential", "cookie", "login", "password", "token", ".env", "id_rsa", "id_ed25519")


def _secret_named(rel: str) -> bool:
    low = rel.lower()
    return any(w in low for w in NOT_CARRIED_WORDS) and not low.startswith(("tokenisers/", "shards/", "texts/"))


class NoOffer(RuntimeError):
    pass


class BoxError(RuntimeError):
    """A command on the box failed; the message carries ssh's or the command's own stderr."""


class NeverBoarded(BoxError):
    """The hire never let us aboard: Vast.ai never showed it running, or its ssh never answered. Nothing of the
    voyage reached it, so it is the host that failed, and the charter may hire another (`REHIRES`)."""


# Boarding (12 November, the hardening after offer 60289338): that one 4090 host refused ssh for the whole ten
# minutes on two hires five hours apart, and the charter hired it again at once each time, because it was still
# the cheapest. A healthy box answers ssh within three tries (45 s) on every hire on record.
BOARD_SSH_S = 300.0  # how long a new box's ssh is waited on before the box is given up
REFRESH_EVERY = 4  # tries of ssh between readings of the instance at Vast.ai (gone, or moved to another address)
REHIRES = 1  # a box that never boards is released and this many more are hired, each on another machine
# Four charters read the same market within the same minute, and Vast.ai's cheapest offer can be taken in the
# seconds between the reading and the hire (12 November, 21:12: `no_such_ask ... is not available` for
# 1m-control). Nothing is hired then, so nothing is spent: the next offer is tried, up to this many times.
OFFERS_GONE = 3


class OfferGone(RuntimeError):
    """Vast.ai refused the hire because the offer is no longer there: nothing was hired."""


def offer_gone(e: Exception) -> bool:
    """Whether a refused hire says the offer has gone (taken by another renter), not that the hire was wrong."""
    s = str(e).lower()
    return "no_such_ask" in s or "is not available" in s
AVOID_HOURS = 12.0  # a host whose box never boarded is not hired again for this long, by any charter


class Recalled(BaseException):
    """SIGTERM or SIGHUP reached a charter with a ship hired. A BaseException, as KeyboardInterrupt is, so
    that no `except Exception` on the way (a failed pull that "sails on") swallows it before the release."""


class NotAttachable(RuntimeError):
    """`attach` found no ship to take up: no such hire, its charter still alive, or the instance not up."""


# ---------------------------------------------------------------- where a hire's time goes


class Phases:
    """Where one hire's time went, measured by the charter itself as it passes each step (12 November, Justin:
    "Vast needs to make measurements not only on processing but also setup times").

    The dashboard's timing table reads the same steps back out of `data/runs/charter.log`; this is the record:
    it is written on the hire's `released` line in S3's spend log, so S4 can plan on a measured set-up instead of
    S5's constant, and so the rate at sea is the voyage's tokens over its *training* seconds, not over the hire
    less a guess. The names are the timing table's: provision, ssh, code, data, board (the manifest, the spec and
    the papers), env, then train and home. `mb` is what each transfer carried.

    A hire that ends before `train` never sailed: `failed_in` names the step it died in."""

    SETUP = ("provision", "ssh", "code", "data", "board", "env", "fitout")

    def __init__(self, started: float, clock=time.time):
        self.clock, self.at, self.open = clock, float(started), "provision"
        self.seconds: dict[str, float] = {}
        self.mb: dict[str, float] = {}

    def mark(self, name: str, mb: float | None = None) -> None:
        """The step now beginning: the one before it ends here."""
        now = self.clock()
        if self.open:
            self.seconds[self.open] = self.seconds.get(self.open, 0.0) + max(0.0, now - self.at)
        self.open, self.at = name, now
        if mb is not None:
            self.mb[name] = round(float(mb), 1)

    @property
    def sailed(self) -> bool:
        return self.open in ("train", "home") or "train" in self.seconds

    def record(self, ended: float | None = None) -> dict:
        """The hire's timing as the spend log keeps it (the open step closed at `ended`, nothing changed here)."""
        ended = self.clock() if ended is None else float(ended)
        secs = dict(self.seconds)
        if self.open:
            secs[self.open] = secs.get(self.open, 0.0) + max(0.0, ended - self.at)
        return {
            "phases": {k: round(v, 1) for k, v in secs.items()},
            "mb": dict(self.mb),
            "setup_s": round(sum(v for k, v in secs.items() if k in self.SETUP), 1),
            "train_s": round(secs.get("train", 0.0), 1) if self.sailed else None,
            "home_s": round(secs["home"], 1) if "home" in secs else None,
            "sailed": self.sailed,
            "failed_in": None if self.sailed else self.open,
        }

    @classmethod
    def taken_up(cls, started: float, at_sea: float | None, clock=time.time) -> Phases:
        """For `attach`: the steps before it are not known one by one, only that the fit-out ran from the hire to
        the `at sea` mark (when there is one) and the voyage has been training since."""
        ph = cls(started, clock)
        if at_sea is not None and at_sea >= ph.at:
            ph.seconds["fitout"] = at_sea - ph.at
            ph.open, ph.at = "train", float(at_sea)
        else:
            ph.open = "fitout"
        return ph


_PHASES: dict[int, Phases] = {}  # by instance: the hires this process is sailing


def _phase(instance, name: str, mb: float | None = None) -> None:
    """Mark a step of this hire; a timing must never cost the voyage."""
    with contextlib.suppress(Exception):
        ph = _PHASES.get(int(instance))
        if ph is not None:
            ph.mark(name, mb)


# ---------------------------------------------------------------- the box


# The fitting-out deadline: the whole of bootstrap, code, data, papers and environment. A box that stops reading
# must not sit behind a hire's quote (12 November: a dead box held rsync for 18 minutes, and the overrun guard
# only runs after "at sea"). THORP_FITOUT_MINUTES overrides it; 0 removes it (a very large checkpoint on a slow
# link, deliberately).
FITOUT_MINUTES = 30.0


def lock_tag(lock: Path | None = None) -> str | None:
    """The box image's tag for this lock: `lock-` and the first 12 hex of backend/uv.lock's sha256, as the workflow
    that builds it (.github/workflows/box-image.yml) names it. None when the lock cannot be read."""
    import hashlib

    try:
        return "lock-" + hashlib.sha256((lock or paths.ROOT / "backend" / "uv.lock").read_bytes()).hexdigest()[:12]
    except OSError:
        return None


def image_exists(ref: str, get=None) -> bool:
    """Whether a public image is in its registry (ghcr.io's anonymous pull token, then the manifest). False on any
    failure: a charter never hires an image it could not see."""
    import requests

    try:
        name, tag = ref.split("/", 1)[1].rsplit(":", 1)
        host = ref.split("/", 1)[0]
        get = get or requests.get
        tok = get(f"https://{host}/token", params={"scope": f"repository:{name}:pull"}, timeout=15).json().get("token")
        r = get(f"https://{host}/v2/{name}/manifests/{tag}", timeout=15, headers={
            "Authorization": f"Bearer {tok}",
            "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, "
                      "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"})  # fmt: skip
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def box_image(t: dict, exists=image_exists) -> tuple[str, str]:
    """The image a hire sails with, and why: the prebuilt box image for the lock this charter carries
    (S5's `box_image`, tagged by `lock_tag`), where it has been published; else the terms' plain `image`, on
    which the box syncs its whole environment as before (12 November, Justin: "lets do a pre built image")."""
    repo, tag = str(t.get("box_image") or ""), lock_tag()
    if not repo:
        return t["image"], "no box image in the terms: the environment is synced on the box"
    if not tag:
        return t["image"], "the lock cannot be read: the environment is synced on the box"
    ref = f"{repo}:{tag}"
    if exists(ref):
        return ref, "prebuilt for this lock: torch is already aboard"
    return t["image"], f"{ref} is not published yet (built on GitHub when the lock changes): the environment is synced on the box"


ENV_POLL_S = 15.0  # how often the environment sync is looked at
ENV_STALL_S = 180.0  # a sync whose network and cache have not moved for this long is stalled


def _num(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fitout_limit() -> float:
    raw = os.environ.get("THORP_FITOUT_MINUTES")
    if raw is None:
        return FITOUT_MINUTES * 60
    try:
        return max(0.0, float(raw)) * 60
    except ValueError:
        return FITOUT_MINUTES * 60


# macOS's tar packs a file's extended attributes (com.apple.provenance, on nearly everything) as a hidden AppleDouble
# twin, `._name`, and its own listing hides them. On the box they unpack as real files: on 12 November
# `ships/lists/tricks/._again.csv` and 26 more were read by a `glob("*.csv")` and the voyage died at sea on
# `UnicodeDecodeError ... Mac OS X`. Neither the twins nor the attributes go aboard.
TAR = ["tar", "--no-mac-metadata", "--no-xattrs"] if sys.platform == "darwin" else ["tar"]


def _size(root: Path, rels: list[str]) -> int:
    """The bytes a transfer carries, for the log and the timing table (a file that vanished is left out)."""
    total = 0
    for rel in rels:
        try:
            total += (root / rel).stat().st_size
        except OSError:
            pass
    return total


class Box:
    """The hired machine, reached by ssh and rsync as root (Vast.ai's SSH)."""

    def __init__(self, host: str, port: int, key_file: str | None = None, run=subprocess.run, log=None):
        self.host, self.port, self.run = host, int(port), run
        self.log = log  # every step says when it starts and how long it took (9 November: a silent box looked stuck)
        self.deadline: float | None = None  # the end of fitting out, set by sail; no step may run past it
        kh = paths.data_dir() / "charter" / "known_hosts"
        kh.parent.mkdir(parents=True, exist_ok=True)
        # BatchMode: never stop at a prompt (a passphrase comes from the agent or the keychain, or not at all)
        self.opts = ["-p", str(self.port), "-o", "StrictHostKeyChecking=accept-new", "-o", f"UserKnownHostsFile={kh}",
                     "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", "-o", "ConnectTimeout=20",
                     "-o", "BatchMode=yes"] + (["-i", key_file] if key_file else [])  # fmt: skip

    def _limit(self, default: float) -> float:
        """How long one step may take: its own bound, never past the fitting-out deadline."""
        if self.deadline is None:
            return default
        left = self.deadline - time.time()
        if left <= 0:
            raise BoxError(
                f"fitting out ran past its deadline ({FITOUT_MINUTES:.0f} min, THORP_FITOUT_MINUTES to change it): releasing the box"
            )
        return min(default, left)

    def _say(self, what: str, t0: float | None = None) -> None:
        """One line of the box's log: what it is doing, and how long that took."""
        if not self.log:
            return
        took = f" ({time.time() - t0:.1f}s)" if t0 else ""
        self.log(f"[box] {what}{took}")

    def sh(self, cmd: str, check: bool = True, timeout: float | None = 600, quiet: bool = False) -> subprocess.CompletedProcess:
        t0 = time.time()
        if quiet:  # a poll: its result is what the caller logs (12 November: the environment's progress)
            say, self.log = self.log, None
            try:
                return self.sh(cmd, check=check, timeout=timeout)
            finally:
                self.log = say
        self._say(f"ssh: {cmd[:100]}")
        limit = self._limit(timeout or 600)
        try:
            r = self.run(["ssh", *self.opts, f"root@{self.host}", cmd], check=False, capture_output=True, text=True, timeout=limit)
        except subprocess.TimeoutExpired as e:
            self._say(f"ssh did not answer in {limit:.0f}s", t0)
            raise BoxError(f"ssh {self.host}:{self.port} did not answer in {limit:.0f}s (ran: {cmd[:120]})") from e
        self._say(f"ssh done, exit {r.returncode}", t0)
        if r.returncode != 0:
            tail = ((r.stderr or "") + "\n" + (r.stdout or "")).strip()[-800:]
            if tail:
                self._say(f"its words: {tail}")
        if check and r.returncode != 0:  # ssh's own words (255: it could not connect or was refused), not just a code
            raise BoxError(f"ssh {self.host}:{self.port} exit {r.returncode}: {(r.stderr or '').strip()[-600:]} (ran: {cmd[:120]})")
        return r

    def wait_ssh(self, timeout_s: float = 600, every_s: float = 15, sleep=time.sleep, on_denied=None, denied_after: int = 6,
                 refresh=None, refresh_every: int = REFRESH_EVERY) -> int:  # fmt: skip
        """Until the box answers ssh (2026-11-08: the first charter's box was "running" by Vast.ai's API but refused the
        first ssh, and the fit-out gave up at once). Vast.ai's ssh proxy and the instance's key can take a minute or more
        after "running". If the box still refuses the key after `denied_after` tries, `on_denied` (attach the key again)
        is called once. Returns the tries it took; raises NeverBoarded with ssh's last words at the timeout.

        `refresh` (the instance as Vast.ai shows it now) is read every `refresh_every` tries: an instance that has
        exited or gone is given up at once, not waited on to the timeout, and one whose ssh address has changed is
        followed to it (the address is read once, at "running", and nothing read it again before 12 November)."""
        last, tries, denied_fixed = "", max(1, int(timeout_s // every_s)), False
        for i in range(1, tries + 1):
            r = self.run(["ssh", *self.opts, f"root@{self.host}", "true"], check=False, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return i
            last = (r.stderr or "").strip()
            if on_denied and not denied_fixed and i >= denied_after and "denied" in last.lower():
                on_denied()
                denied_fixed = True
            if refresh and i % max(1, refresh_every) == 0:
                self._follow(refresh, last)
            sleep(every_s)
        raise NeverBoarded(f"ssh {self.host}:{self.port} never answered in {timeout_s:.0f} s: {last[-600:]}")

    def _follow(self, refresh, last: str) -> None:
        """The instance read again during the wait for ssh: gone or stopped ends the wait; a new address is taken.
        A failed reading (Vast.ai's API, not the box) changes nothing."""
        try:
            inst = refresh() or {}
        except Exception as e:  # noqa: BLE001
            self._say(f"the instance could not be read at Vast.ai ({e!r}); still waiting for ssh")
            return
        state = inst.get("actual_status")
        if not inst or state in ("exited", "offline", "stopped"):
            raise NeverBoarded(f"the instance is {state or 'gone'} at Vast.ai while ssh {self.host}:{self.port} refused us: {last[-300:]}")
        route = ssh_route(inst)
        if route and route != (self.host, self.port):
            self._say(f"Vast.ai moved the box's ssh from {self.host}:{self.port} to {route[0]}:{route[1]}: following it")
            self.host, self.port = route
            self.opts[self.opts.index("-p") + 1] = str(self.port)

    def _rsh(self) -> str:
        return "ssh " + " ".join(shlex.quote(o) for o in self.opts)

    def put_tar(self, root: Path, rels: list[str], dst: str = "", timeout: float = 1800) -> None:
        """The files `rels` to REMOTE/dst as **one tar over ssh** (9 November: rsync'ing 20,000 small files to the box
        took most of an hour; a single stream is minutes). Bytes are equal; the transfer is one connection, and it
        may not run forever: a box that stops reading is a failed fit-out, not a hire to wait on (12 November)."""
        if not rels:
            return
        t0, size = time.time(), _size(root, rels)
        self._say(f"tar {len(rels)} files ({size / 1e6:.1f} MB) to {dst or '/'}")
        lst = paths.data_dir() / "charter" / f"tar-{os.getpid()}.txt"
        lst.write_text("\n".join(rels) + "\n")
        tar_cmd = TAR + ["-czf", "-", "-C", str(root), f"--files-from={lst}"]
        remote = (f"mkdir -p {REMOTE}/{dst} && tar xzf - -C {REMOTE}/{dst}; s=$?; "
                  f"find {REMOTE}/{dst} -name '._*' -type f -delete; exit $s")  # no AppleDouble twin is left aboard
        limit = self._limit(timeout)
        send = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "COPYFILE_DISABLE": "1"})
        try:
            r = self.run(["ssh", *self.opts, f"root@{self.host}", remote], stdin=send.stdout, capture_output=True,
                         text=True, timeout=limit)  # fmt: skip
        except subprocess.TimeoutExpired as e:
            self._say(f"tar did not finish in {limit:.0f}s", t0)
            raise BoxError(
                f"tar upload of {size / 1e6:.1f} MB did not finish in {limit:.0f}s: the box stopped reading"
            ) from e
        finally:
            send.stdout.close()
            if send.poll() is None:
                send.kill()
            send.wait()
            lst.unlink(missing_ok=True)
        self._say(f"tar done ({len(rels)} files, {size / 1e6:.1f} MB)", t0)
        if r.returncode != 0:
            raise BoxError(f"tar upload failed: {(r.stderr or '').strip()[-400:]}")

    def put(self, root: Path, rels: list[str], dst: str = "", timeout: float = 1800) -> None:
        """The files `rels` (relative to `root`) to REMOTE/dst, their paths kept. Rsync's own `--timeout` ends a
        connection that stops moving, and the whole step is bounded too (12 November: a dead box held the 211 MB
        manifest for 18 minutes with no timeout at all)."""
        if not rels:
            return
        size = _size(root, rels)
        lst = paths.data_dir() / "charter" / f"files-{os.getpid()}.txt"
        lst.write_text("\n".join(rels) + "\n")
        target = f"root@{self.host}:{REMOTE}/{dst}".rstrip("/") + "/"
        t0 = time.time()
        self._say(f"rsync {len(rels)} files ({size / 1e6:.1f} MB) to {dst or '/'}")
        try:
            self.run(["rsync", "-a", "--partial", "--timeout=120", "--contimeout=30", "-e", self._rsh(),
                      f"--files-from={lst}", f"{root}/", target], check=True, timeout=self._limit(timeout))  # fmt: skip
        except subprocess.TimeoutExpired as e:
            self._say(f"rsync did not finish in {timeout:.0f}s", t0)
            raise BoxError(
                f"rsync of {size / 1e6:.1f} MB did not finish in {self._limit(timeout):.0f}s: the box stopped reading"
            ) from e
        finally:
            lst.unlink(missing_ok=True)
        self._say(f"rsync done ({len(rels)} files, {size / 1e6:.1f} MB)", t0)

    def get(self, src: str, dst: Path, timeout: float = 900) -> bool:
        """REMOTE/src (a folder or a file) to dst; False when it is not there yet. Bounded, and rsync's own
        `--timeout` ends a silent connection (12 November)."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = self.run(["rsync", "-a", "--partial", "--timeout=120", "--contimeout=30", "-e", self._rsh(),
                          f"root@{self.host}:{REMOTE}/{src}", str(dst)], check=False, timeout=self._limit(timeout))  # fmt: skip
        except subprocess.TimeoutExpired as e:
            raise BoxError(f"rsync pull of {src} did not finish in {self._limit(timeout):.0f}s") from e
        return r.returncode == 0

    def bootstrap(self) -> None:
        self.sh(
            "set -e; command -v rsync >/dev/null || (apt-get update -qq && apt-get install -y -qq rsync);"
            " command -v uv >/dev/null || [ -x ~/.local/bin/uv ] || (curl -LsSf https://astral.sh/uv/install.sh | sh);"
            f" mkdir -p {REMOTE}/data/charter",
            timeout=900,
        )

    def sync_env(self, sleep=time.sleep, every_s: float = ENV_POLL_S, stall_s: float = ENV_STALL_S, clock=time.time) -> None:
        """`uv sync --group torch` on the box, watched (12 November, Justin: "is there any way we can have some form
        of visibility into the environment sync if it gets stuck?"). It runs in the background on the box, writing
        uv's own lines to data/charter/env.log; every `every_s` the charter reads how many megabytes uv's cache and
        the venv hold, how many the box's network has taken in, and uv's last line, and logs them as
        `[box] env: ...`, so the Vast page shows what it is doing. A sync whose network and cache have not moved
        for `stall_s` is stopped as stalled, not waited on until the fit-out deadline; one that is slow but moving
        runs on. The fit-out deadline still bounds the whole."""
        self._say("syncing the box's environment (uv sync --group torch): this is the step that stalled on 8 November")
        t0 = clock()
        log, done = f"{REMOTE}/data/charter/env.log", f"{REMOTE}/data/charter/env.exit"
        # --inexact keeps the tagger group a pre-built image carries: the shapes evaluator needs it, but a
        # GitHub 504 while fetching that wheel must not hold a GPU (it did before 9 November).
        inner = f"cd {REMOTE} && ~/.local/bin/uv sync --project backend --group torch --inexact > {log} 2>&1; echo $? > {done}"
        self.sh(f"rm -f {done}; nohup sh -c {shlex.quote(inner)} > /dev/null 2>&1 < /dev/null &", timeout=120, quiet=True)
        probe = (f"cat {done} 2>/dev/null; echo '|'; du -sm ~/.cache/uv {REMOTE}/backend/.venv 2>/dev/null | awk '{{s+=$1}} END {{print s+0}}';"
                 " echo '|'; awk 'NR>2 && $1 !~ /^lo:/ {s+=$2} END {print s+0}' /proc/net/dev; echo '|';"
                 f" tail -c 2000 {log} 2>/dev/null | tr '\\r' '\\n' | grep -v '^ *$' | tail -n 1")
        last_net, last_mb, moved_at, first_net = None, None, clock(), None
        while True:
            sleep(every_s)
            r = self.sh(probe, check=False, timeout=60, quiet=True)
            parts = [x.strip() for x in (r.stdout or "").split("|")]
            if r.returncode != 0 or len(parts) < 4:
                if clock() - moved_at > stall_s:
                    raise BoxError(f"the environment sync could not be watched for {stall_s:.0f} s (ssh exit {r.returncode}): the box stopped answering")
                continue
            code, mb, net, line = parts[0], _num(parts[1]), _num(parts[2]), parts[3][-160:]
            if code:
                took = clock() - t0
                if code.strip() != "0":
                    tail = self.sh(f"tail -n 15 {log}", check=False, timeout=60, quiet=True).stdout or ""
                    self._say(f"env: uv sync failed (exit {code}): {tail.strip()[-600:]}")
                    raise BoxError(f"uv sync on the box failed (exit {code}): {tail.strip()[-300:]}")
                self._say(f"environment synced ({took:.0f}s, {mb:,.0f} MB)")
                self.sync_tagger()
                return
            first_net = net if first_net is None else first_net
            rate = (net - last_net) / 1e6 / every_s if last_net is not None and net >= last_net else None
            if last_net is None or net != last_net or mb != last_mb:
                moved_at = clock()
            still = clock() - moved_at
            self._say(f"env: {mb:,.0f} MB in uv's cache and venv, {(net - first_net) / 1e6:,.0f} MB taken in"
                      + (f" at {rate:.1f} MB/s" if rate is not None else "")
                      + (f"; NOTHING MOVED FOR {still:.0f}s" if still >= every_s * 2 else "")
                      + (f"; uv: {line}" if line else ""))  # fmt: skip
            if still > stall_s:
                self.sh("pkill -f 'uv sync' || true", check=False, timeout=60, quiet=True)
                raise BoxError(f"the environment sync stalled: nothing came in for {still:.0f} s ({mb:,.0f} MB in the cache; uv's last line: {line or 'none'})")
            last_net, last_mb = net, mb

    def sync_tagger(self) -> None:
        """Install the shapes tagger (`en-core-web-sm`, its own dependency group) if the box does not have it.

        The tagger is needed at sea: every light evaluation runs `shapes`, and without the pinned model each
        reading failed with `Can't find model 'en_core_web_sm'` (12 November: the bridge's whole run lost its
        shapes). It is kept out of the main sync because the wheel is hosted on GitHub and a 504 there once held
        a box's set-up for half an hour. So: use the image's copy when it has one, otherwise fetch it with a
        five-minute bound, and never fail the fit-out for it."""
        probe = (f"cd {REMOTE} && backend/.venv/bin/python -c 'import en_core_web_sm' >/dev/null 2>&1 && echo present || "
                 "(timeout 300 ~/.local/bin/uv sync --project backend --group tagger --inexact "
                 "> data/charter/tagger.log 2>&1; echo $?)")  # fmt: skip
        try:
            r = self.sh(probe, check=False, timeout=330, quiet=True)
            code = ((r.stdout or "").strip().splitlines() or [""])[-1].strip()
        except Exception as e:  # noqa: BLE001 - a missing tagger must never stop a voyage
            self._say(f"shapes tagger not installed ({e!r}); the voyage sails without shape readings")
            return
        if code in ("present", "0"):
            self._say("shapes tagger ready")
            return
        tail = self.sh(f"tail -n 4 {REMOTE}/data/charter/tagger.log", check=False, timeout=60, quiet=True).stdout or ""
        self._say(f"shapes tagger not installed (exit {code or '?'}); the voyage sails without shape readings: "
                  f"{tail.strip()[-400:]}")  # fmt: skip

    def launch(self, rid: str) -> None:
        inner = (
            f"~/.local/bin/uv run --project backend --group torch thorp run data/charter/{rid}.yaml "
            f"> data/charter/{rid}.out 2>&1; echo $? > data/charter/{rid}.exit"
        )
        # One backgrounded command with all three of its streams redirected: `cd X && cmd > /dev/null &` backgrounds the
        # whole && list as a subshell whose stdout is still ssh's, so ssh stayed open for the whole voyage (2026-11-08, P1:
        # the charter never reached its poll loop, so no mid-run pulls and no overrun deadline).
        papers = f"{REMOTE}/data/charter/{rid}.papers.json"  # the S5 state its gate reads (thorp/store.py)
        self.sh(f"cd {REMOTE}; THORP_BACKEND=torch THORP_DEVICE=cuda THORP_PAPERS={papers} THORP_SHIP_LOG=1 nohup sh -c {shlex.quote(inner)} > /dev/null 2>&1 < /dev/null &", timeout=120)

    def finished(self, rid: str) -> int | None:
        """The voyage's exit status once it has come in, else None."""
        r = self.sh(f"cat {REMOTE}/data/charter/{rid}.exit 2>/dev/null || true", check=False, timeout=60)
        if r.returncode != 0:
            # the command cannot fail (`|| true`), so this is ssh not reaching the box. Until 11 November it
            # read as "not in yet" and an unreachable box was polled in silence; now it is a miss, logged.
            raise BoxError(f"ssh {self.host}:{self.port} exit {r.returncode}: {(r.stderr or '').strip()[-300:]}")
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

    def search(self, gpu, terms, limit=5, avoid=frozenset()):
        return [{"offer_id": 0, "gpu": gpu, "gpu_name": gpu, "dph": float(terms["gpus"][gpu]), "verified": True,
                 "reliability": float(terms["min_reliability"]), "inet_down": float(terms["min_inet_down_mbps"]),
                 "inet_up": float(terms["min_inet_up_mbps"]), "cuda": float(terms["min_cuda"]),
                 "disk_gb": float(terms["disk_gb"]), "geolocation": "", "machine_id": None}]  # fmt: skip

    def credit(self):
        return None


def class_of(spec: dict) -> str | None:
    """The GPU class a voyage asks for (`gpu:`, a label: it moves no run id), or None for the cheapest. (13 November:
    the deep 50m ran out of memory on an RTX 4090's 24 GB twice, drawing the scaffold's maps over 36 layers; the
    cheapest class is not always one the voyage fits in. Not `charter.gpu`: a `charter:` block is S5's request for a
    hire that carries its own quote, s5_policy/charter.check.)"""
    want = spec.get("gpu")
    return str(want) if want else None


def quote(spec_path: str, gpu: str | None = None, vast=None, resolver=None, log=print) -> dict:
    """Prepare the voyage here, read its plan and the market; returns {spec, prep, plan, quotes, market}. Without a
    Vast.ai key the market is the terms' ceilings (an upper bound, marked as such)."""
    from thorp import train

    spec = train.load_spec(spec_path)
    if spec["model"].get("backend", "torch") != "torch":
        raise ValueError(f"model.backend is {spec['model']['backend']!r}: a chartered voyage sails on torch")
    gpu = gpu or class_of(spec)
    # (11 November) the torch loop refuses a spec it would only honour in part; ask it here, before the voyage is
    # prepared or a box is hired, so the refusal costs nothing. Without torch on this machine the question cannot be
    # put: the box's own loop still refuses at its first line, after the hire.
    try:
        from thorp import train_torch
    except ImportError:
        log("charter: torch is not installed here: the spec was not read against the torch loop before the quote")
    else:
        train_torch.refuse_unsupported(spec)
    t = s5.terms()
    prep = train.prepare(spec, **({"resolver": resolver} if resolver else {}), log=log)
    p = plan(spec, prep)
    market_read = "market"
    if vast is None:
        try:
            vast = Vast(http_transport(api_key()))
        except NoKey:
            vast, market_read = _Ceilings(), "ceilings (no Vast.ai key: the terms' ceiling prices)"
    avoid = avoided_now()
    if avoid:
        log(f"charter: not hiring {', '.join(sorted(avoid))}: a box there never boarded in the last {AVOID_HOURS:.0f} h")
    qs = _priced(vast, spec, prep, p, t, gpu, avoid)
    return {"spec": spec, "prep": prep, "plan": p, "quotes": qs, "market": market_read, "vast": vast, "terms": t, "avoid": avoid}


def _priced(vast, spec: dict, prep, p: dict, t: dict, gpu: str | None, avoid) -> list[dict]:
    """The market's quotes for this voyage, each with what the gate reads beside it (the week's spend, the
    credit, the ships out) and the terms it breaks: for the first hire and for a hire again after a dead box."""
    qs = market.quotes(vast, _cfg(spec, prep.tokeniser.vocab_size), spec["model"]["preset"], p["tokens_left"], t,
                       gpus=[gpu] if gpu else None, avoid=avoid)  # fmt: skip
    credit = vast.credit()
    out_ = len(s3.out_now())
    spent = s3.week_spent()
    for q in qs:
        q.update(week_spent=spent, credit=credit, instances_out=out_, tokens=p["tokens_left"], run_id=p["run_id"])
        q["breaks"] = s3.violations(q, t)
    return qs


def avoid_keys(offer_id=None, machine_id=None) -> set[str]:
    """What `Vast.search` avoids for one host: its offer and, when known, its machine."""
    return ({f"o{offer_id}"} if offer_id is not None else set()) | ({f"m{machine_id}"} if machine_id is not None else set())


def avoided_now(rows: list[dict] | None = None, hours: float = AVOID_HOURS, now: float | None = None) -> set[str]:
    """The offers and machines whose box never boarded (released having failed in `provision` or `ssh`) in the
    last `hours`, read from S3's spend log: no charter hires them again until then. Older hires carry only
    their offer; since 12 November the hire records its machine too. Never raises: no log, nothing avoided."""
    from datetime import datetime

    try:
        rows = s3.log() if rows is None else rows
    except Exception:  # noqa: BLE001
        return set()
    now = time.time() if now is None else now
    hires = {r.get("instance"): r for r in rows if r.get("event") == "hired"}
    out: set[str] = set()
    for r in rows:
        if r.get("event") != "released" or r.get("failed_in") not in ("provision", "ssh"):
            continue
        try:
            at = datetime.fromisoformat(str(r.get("at"))).timestamp()
        except ValueError:
            continue
        if now - at > hours * 3600:
            continue
        h = hires.get(r.get("instance")) or {}
        out |= avoid_keys(h.get("offer"), h.get("machine_id"))
    return out


def gate(spec: dict, q: dict) -> None:
    """S3 asks S5's charter policy of the chosen quote (liberty_machine.gate_one: refused, nothing is hired)."""
    from thorp import liberty_machine

    liberty_machine.gate_one("charter", {**spec, "charter": {**(spec.get("charter") or {}), "quote": q}}, where="charter")


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
    # The Gutenberg catalogue is 20 MB and `prepare` needs it to resolve a recipe; the 2.3 GB catalogue cache
    # stays home. Without this the box fetched it on every fitting out and a flaky connection killed the
    # voyage (12 November: the gqa hire died in `prepare` on a ChunkedEncodingError).
    for rel in ("catalogue/pg_catalog.csv", "catalogue/authority.json", "catalogue/hf-files.json"):
        f = d / rel
        if f.is_file() and rel not in out:
            out.append(rel)
    for sub in ("tokenisers", "shards"):
        root = d / sub / tok_id
        if root.exists():
            files = sorted(root.rglob("*"))
            if trim and sub == "shards":
                # only the voyage's own books' shards (13 November: the fleet's tokeniser holds the 50m's 25,327 books,
                # 3.45 GB, and a 9m on Ogden carried all of it; two hosts could not take it inside the fit-out's 30
                # minutes and the breaker closed the lane). A shard left home is made again on the box from its text.
                files = [f for f in files if f.stem in books]
            out += [str(f.relative_to(d)) for f in files if f.is_file()]
    return [f for f in out if not _secret_named(f)]


def voyage_lists(spec: dict) -> list[str]:
    """Every list the voyage's spec reads, as paths from the repository root: its stages' shelves, its recipe, the
    decks it refuses and is scored on, what it reads first and what its tokeniser was trained on."""
    d, out = spec.get("data") or {}, []
    names = [st.get("recipe") for st in d.get("stages") or []] + [d.get("recipe"), d.get("first")]
    names += list(d.get("refuse") or []) + list((spec.get("eval") or {}).get("sets") or [])
    train_on = (spec.get("tokeniser") or {}).get("train_on")
    if train_on and train_on != "recipe":
        names.append(train_on)
    for n in names:
        if not n or not isinstance(n, str):
            continue
        with contextlib.suppress(Exception):
            f = paths.resolve(n)
            if f.is_file():
                rel = str(f.relative_to(paths.ROOT))
                if rel not in out:
                    out.append(rel)
    return out


def code_carried(spec: dict | None = None, run=subprocess.run) -> list[str]:
    """The code the box sails with: what git tracks under backend/ and ships/, what it does not yet track there
    (a module written today and not committed is still imported by the files that are), and the voyage's own
    lists whether git keeps them or not. 12 November: the first voyage to reach the sea on the trimmed cargo
    died in its first second, `FileNotFoundError: ships/lists/ogden-v0.1.4.csv`: the list every v0.0.6 voyage
    reads is in .gitignore, and only tracked files were carried."""
    def ls(*flags: str) -> list[str]:
        r = run(["git", "ls-files", *flags, "backend", "ships"], cwd=paths.ROOT, capture_output=True, text=True, check=True)
        return [f for f in r.stdout.split("\n") if f]

    files = ls()
    with contextlib.suppress(Exception):  # untracked and not ignored: new source, never a secret or a build
        files += [f for f in ls("--others", "--exclude-standard") if f not in files]
    files = [f for f in files if (paths.ROOT / f).is_file()]  # tracked but deleted in the working tree: nothing to carry
    for f in voyage_lists(spec or {}):
        if f not in files:
            files.append(f)
    return files


def stage(rid: str) -> Path:
    """The files carried to a hired box: the manifest, exported from the store when the home no longer keeps a
    `data/manifest.sqlite` (12 November: the local SQLite copy was retired); any other `data/*.sqlite` is copied
    consistently. The papers' ledger is written into the same stage by `s2.papers`."""
    from thorp import manifest_store

    st = paths.data_dir() / "charter" / rid / "stage"
    if st.exists():
        shutil.rmtree(st)
    st.mkdir(parents=True)
    for db in paths.data_dir().glob("*.sqlite"):
        # the register is always exported from the store (13 November: an empty `data/manifest.sqlite`, made at 07:54
        # by a process that read the library from the file, was carried instead, and every box staged 0 books)
        if db.name == "manifest.sqlite":
            continue
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        dst = sqlite3.connect(st / db.name)
        src.backup(dst)
        src.close()
        dst.close()
    if not (st / "manifest.sqlite").exists():
        manifest_store.export_sqlite(st / "manifest.sqlite")
    return st


def checkpoints_carried(rid: str, spec: dict, rec: Ledger) -> list[str]:
    """The latest checkpoint of the voyage and of each run it reads from, relative to data/."""
    from thorp import train

    # each parent by its id or its name, as the papers carry it (s2.related_rows, 11 November): a parent pinned by
    # run id was looked up as a name here, found nothing, and sailed without its checkpoint
    rids = [rid] + [r["run_id"] for r in s2.related_rows(spec, rec)]
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


CHECKPOINT_PULLS = 4  # tries at bringing the checkpoints home, each resuming where the last stopped
CHECKPOINT_PULL_S = 1800  # one try's bound


def pull_checkpoints(box, rid: str, dst: Path) -> None:
    """The voyage's checkpoints home, retried (13 November: the 21m's 1.6 GB came home at about 1.3 MB/s, the pull was
    cut at 900 s with 1.2 GB here, and the voyage was failed and sailed again from the start; a 50m's are about 6 GB).
    rsync's `--partial` keeps what arrived, so each try carries on from where the last stopped."""
    for attempt in range(1, CHECKPOINT_PULLS + 1):
        try:
            box.get(f"data/checkpoints/{rid}/", dst, timeout=CHECKPOINT_PULL_S)
            return
        except BoxError as e:
            if attempt == CHECKPOINT_PULLS:
                raise
            say = getattr(box, "_say", None)
            if say:
                say(f"checkpoint pull stopped ({e}); resuming where it stopped, try {attempt + 1} of {CHECKPOINT_PULLS}")


def bring_home(box, rid: str, start: int, rec: Ledger, hire: dict, commit: str) -> dict:
    """The checkpoints, the box's log and the voyage's rows, home."""
    from thorp import train

    pull_checkpoints(box, rid, train.checkpoint_root(rid))
    box.get(f"data/runs/{rid}.log", paths.runs_dir() / f"{rid}.box.log")
    box.get(f"data/charter/{rid}.out", paths.data_dir() / "charter" / rid / "box.out")
    gate_log = paths.data_dir() / "charter" / rid / "box-gate-log.jsonl"
    if box.get(f"data/charter/{rid}.papers.gate-log.jsonl", gate_log):  # the box's gate decisions, into s3.gate_decisions
        store.fold_gate_log(gate_log, source=f"box papers {rid}")
    led = paths.data_dir() / "charter" / rid / "box-ledger.sqlite"
    # The box's ledger is open in WAL mode while the voyage trains. rsyncing the file (and hoping the -wal came
    # with it) produced a malformed database on the bridge's homecoming (12 November: 220k metrics recovered from
    # its dump). Ask SQLite for a consistent snapshot instead; a box whose python cannot make one falls back to
    # the old copy, and s2.bring_home recovers a malformed copy from its dump.
    snap_rel = f"data/charter/{rid}.ledger.snapshot.sqlite"
    snap = paths.data_dir() / "charter" / rid / "box-ledger.snapshot.sqlite"
    made = False
    with contextlib.suppress(Exception):
        inner = (
            "import sqlite3; s=sqlite3.connect('ledger.sqlite'); "
            f"d=sqlite3.connect('{snap_rel}'); s.backup(d); d.close(); s.close()"
        )
        box.sh(f"cd {REMOTE} && backend/.venv/bin/python -c {shlex.quote(inner)}", timeout=300)
        made = box.get(snap_rel, snap)
        box.sh(f"rm -f {snap_rel}", check=False, timeout=60, quiet=True)
    if made:
        led = snap
    else:
        if not box.get("ledger.sqlite", led):
            return {}
        for side in ("-wal", "-shm"):  # a raw fallback: its last rows may be in the -wal file
            box.get(f"ledger.sqlite{side}", led.with_name(led.name + side))
    try:
        return s2.bring_home(led, rid, start, rec, commit=commit,
                             hardware=f"{_box_hardware(led, rid)} · vast.ai instance {hire['instance']} at ${hire['dph']:.3f}/h")  # fmt: skip
    except LookupError:
        return {}
    finally:
        if made:
            with contextlib.suppress(OSError):
                snap.unlink()


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


def _drop_queued_home(hire: dict, log) -> None:
    """Remove the queued line that asked for a voyage now home: a recovery (`thorp charter attach`) finishes a
    line the coordinator had already requeued after an earlier failure, and leaving it would sail the finished run
    again (12 November: the bridge finished on the 4090 while its queue line waited at the top)."""
    with contextlib.suppress(Exception):
        from thorp.viable.s2_coordination import queue_store

        for row in queue_store.lines():
            if row.get("kind") == "spec" and queue_store.name_of(row) == hire.get("name"):
                if queue_store.drop(row["text"], by=queue_store.COORDINATOR):  # the coordinator's own requeue, undone
                    log(f"charter: removed {row['text']!r} from the queue: its run is home")


def _box_hardware(led: Path, rid: str) -> str:
    try:
        con = sqlite3.connect(f"file:{led}?mode=ro", uri=True)
        try:
            r = con.execute("select hardware from runs where run_id=?", (rid,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error:  # a raw fallback for a malformed ledger: the fold's recovery will read it
        return "torch"
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


class _Guard:
    """Whether the clean-up has begun: from then on a signal is noted and no more."""

    def __init__(self):
        self.taken: str | None = None

    def closing(self) -> None:
        self.taken = self.taken or "the clean-up"


@contextlib.contextmanager
def _recallable(log):
    """While a ship is hired, SIGTERM and SIGHUP raise `Recalled` where the charter stands (once: a second
    signal, or one that comes when the clean-up has begun, is logged and does not cut the release short).
    The handlers are put back on leaving. Outside the main thread Python allows no handler, and none is set."""
    guard = _Guard()

    def handler(signum, frame):
        name = signal.Signals(signum).name
        if guard.taken:
            # nothing here may raise into the release it interrupts: not even the log (a handler that
            # prints while the interrupted code is printing is a RuntimeError)
            with contextlib.suppress(Exception):
                log(f"charter: {name} again, during {guard.taken}: the release goes on")
            return
        guard.taken = name
        raise Recalled(name)

    old = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        with contextlib.suppress(ValueError):
            old[sig] = signal.signal(sig, handler)
    try:
        yield guard
    finally:
        for sig, was in old.items():
            signal.signal(sig, was)


def _watch(box, rid: str, start: int, rec: Ledger, hire: dict, commit: str, deadline: float, log, sleep, poll_s: float) -> tuple[str, dict]:  # fmt: skip
    """A voyage at sea on its box, watched to its end: asked every `poll_s` whether it is in, its rows pulled
    home every PULL_EVERY_MIN. Returns (how it ended, the last mid-run pull's counts): "home", "failed (exit
    N)", or "overran" at the deadline.

    A poll the box does not answer releases nothing (11 November): each miss is logged and the box is asked
    again, until it answers or the deadline comes. A short outage on this Mac, its network or Vast.ai's ssh
    proxy is then a gap in the log, not the end of a voyage that was sailing all along."""
    counts: dict = {}
    last_pull = time.time()
    misses, silent_since = 0, 0.0
    until = time.strftime("%d %b %H:%M", time.localtime(deadline))
    while True:
        try:
            code_ = box.finished(rid)
            if misses:
                log(f"charter: the box answers again, after {misses} missed poll(s) over {(time.time() - silent_since) / 60:.0f} min")
            misses = 0
        except (BoxError, subprocess.TimeoutExpired) as e:
            code_, misses = None, misses + 1
            silent_since = silent_since if misses > 1 else time.time()
            log(f"charter: the box did not answer (miss {misses}, {(time.time() - silent_since) / 60:.0f} min out of contact); "
                f"it stays hired and is asked again until its deadline, {until}: {str(e)[-200:]}")  # fmt: skip
        if code_ is not None:
            return ("home" if code_ == 0 else f"failed (exit {code_})"), counts
        if time.time() > deadline:
            hours = (deadline - float(hire["started"])) / 3600
            log(f"charter: past its deadline, {hours:.1f} h after the hire (the quote times the overrun): bringing it home")
            return "overran", counts
        if not misses and time.time() - last_pull > PULL_EVERY_MIN * 60:
            try:  # a failed mid-run pull must not release the box: the next pull, or the last, takes it
                counts = bring_home(box, rid, start, rec, hire, commit)
            except Exception as e:  # noqa: BLE001
                log(f"charter: a mid-run pull failed ({e!r}); sailing on")
            last_pull = time.time()
        sleep(poll_s)


def _last_pull(box, rid: str, start: int, rec: Ledger, hire: dict, commit: str, log, sleep) -> dict:
    """The last pull is the voyage: tried three times before the box is released."""
    for attempt in range(3):
        try:
            return bring_home(box, rid, start, rec, hire, commit)
        except Exception as e:  # noqa: BLE001
            log(f"charter: the last pull failed (try {attempt + 1}/3): {e!r}")
            if attempt == 2:
                raise
            sleep(30)
    return {}


def _release(vast, hire: dict, status: str, rec: Ledger, log, error: str | None = None) -> tuple[float, bool]:
    """Release the ship and log it, with what it cost, the rate it made and, for a hire that failed, why
    (`error`: until 12 November a lost hire's release said only "lost", and the reason was in a traceback in
    the line's own .out file, overwritten by the next try). Returns (when, whether Vast.ai took the release)."""
    instance, rid, ended = hire["instance"], hire["run_id"], time.time()
    try:
        vast.release(instance)
        released = True
    except Exception as e:  # noqa: BLE001
        released = False
        log(f"charter: RELEASE FAILED for instance {instance} ({e!r}): thorp charter audit --release-orphans")
    timing: dict = {}
    with contextlib.suppress(Exception):  # where the hire's time went (Phases); never worth the release
        ph = _PHASES.pop(int(instance), None)
        if ph is not None:
            timing = ph.record(ended)
    if released:
        rate = _measured_rate(rec, rid, int(hire.get("start_step") or 0))
        s3.record("released", instance=instance, run_id=rid, gpu=hire.get("gpu"), dph=hire["dph"], preset=hire.get("preset"),
                  started=hire["started"], ended=ended, cost=s3.cost_of(hire, ended), status=status, tokens_per_s=rate,
                  name=hire.get("name"), **timing, **({"error": error[:600]} if error else {}))  # fmt: skip
    s2.note(rid, event="released" if released else "release failed", instance=instance, status=status,
            **({"error": error[:600]} if error else {}))  # fmt: skip
    return ended, released


def _close(rec: Ledger, hire: dict, status: str, ended: float, counts: dict, log) -> dict:
    """The charter's last words and what it returns, once its ship is released."""
    rid, instance = hire["run_id"], hire["instance"]
    cost = s3.cost_of(hire, ended)
    log(f"charter: {hire.get('name')} {status}; instance {instance} released; ${cost:.2f} for {(ended - hire['started']) / 3600:.2f} h")
    if status != "home" and (rec.get_run(rid) or {}).get("status") == "running":
        rec.run({"run_id": rid, "status": f"chartered: {status}"})
        # the final state beside the status (11 November, item 11); never raises
        from thorp import run_state

        run_state.ended(rid, f"chartered: {status}", rec, log)
    return {"run_id": rid, "status": status, "instance": instance, "cost": cost, "rows": counts}


def sail(spec_path: str, gpu: str | None = None, vast=None, resolver=None, box_factory=None, rec: Ledger | None = None,
         log=_say, sleep=time.sleep, poll_s: float = 60.0) -> dict:  # fmt: skip
    """The chartered voyage, from the quote to the release. Returns what it came home with."""
    from thorp import train

    rec = rec or reader()
    q0 = quote(spec_path, gpu=gpu, vast=vast, resolver=resolver, log=log)
    spec, p, t, vast = q0["spec"], q0["plan"], q0["terms"], q0["vast"]
    gpu = gpu or class_of(spec)  # a hire again after a dead box keeps to the class the voyage needs
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
    commit = train.git_commit()
    avoid = set(q0.get("avoid") or ())
    never_boarded, gone = 0, 0
    with s2.berth(t["max_instances"], rid):
        while True:
            log(f"charter: {q['gpu']} offer {q['offer_id']} at ${q['dph']:.3f}/h, about {q['hours']:.1f} h, ${q['cost']:.2f} ({q['speed']})")
            try:
                hire, status, ended, counts, failure = _sail_one(spec, q0["prep"], q, p, t, rid, commit, rec, vast,
                                                                  box_factory, log, sleep, poll_s)  # fmt: skip
            except OfferGone as e:
                # nothing was hired: another renter took the offer between the market's reading and the hire
                gone, last = gone + 1, e
                log(f"charter: offer {q['offer_id']} was taken before it could be hired ({gone} of {OFFERS_GONE + 1}); nothing is hired")
                if gone > OFFERS_GONE:
                    raise
                avoid |= avoid_keys(q.get("offer_id"))
                why = "the last offer was taken"
            else:
                if failure is None:
                    break
                never_boarded, last = never_boarded + 1, failure
                if never_boarded > REHIRES:
                    raise failure
                avoid |= avoid_keys(q.get("offer_id"), q.get("machine_id"))  # the host, not only the offer
                why = f"the last box never boarded ({never_boarded} of {REHIRES + 1})"
            # the market read again without what failed, and the new quote gated as the first was
            qs = _priced(vast, spec, q0["prep"], p, t, gpu, avoid)
            if not qs:
                log(f"charter: no other offer keeps the terms; giving up: {why}")
                raise last
            q = qs[0]
            log(f"charter: hiring again on another offer: {why}")
            gate(spec, q)
    return _close(rec, hire, status, ended, counts, log)


def _sail_one(spec: dict, prep, q: dict, p: dict, t: dict, rid: str, commit: str, rec: Ledger, vast, box_factory, log, sleep,
              poll_s: float) -> tuple[dict, str, float, dict, NeverBoarded | None]:  # fmt: skip
    """One hire, from the hire to its release: (the hire, how it ended, when it was released, the rows home,
    and the NeverBoarded when its box never let us aboard, so `sail` may hire another). Any other failure is
    logged with its reason, recorded on the release, and raised after the ship is released."""
    image, why_image = box_image(t)
    log(f"charter: image {image} ({why_image})")
    try:
        instance = vast.hire(q["offer_id"], image, int(t["disk_gb"]), LABEL + rid)
    except VastError as e:
        if offer_gone(e):
            raise OfferGone(str(e)) from e
        raise
    # the instance is on record against its run from here: in the voyage's own log (a file) and then in
    # S3's spend log, with all `attach` needs to take the ship up again (the step it set out from, the
    # quote's hours, the commit). The hire is inside the `try` now: a spend log that could not be
    # written used to raise with the ship already out and nothing to release it (11 November).
    s2.note(rid, event="hired", instance=instance, gpu=q["gpu"], dph=q["dph"])
    hire = {"instance": instance, "run_id": rid, "name": spec.get("name"), "gpu": q["gpu"], "dph": q["dph"],
            "started": time.time(), "preset": spec["model"]["preset"], "start_step": p["start"]}  # fmt: skip
    status, counts, error, failure = "lost", {}, None, None
    with _recallable(log) as guard:
        try:
            hire = s3.record("hired", **{k: v for k, v in hire.items() if k != "started"}, offer=q["offer_id"],
                             machine_id=q.get("machine_id"), storage_dph=q.get("storage_dph"), started=hire["started"], quote=q["cost"],
                             quote_hours=q["hours"], commit=commit, setup_assumed_h=q.get("setup_hours"))  # fmt: skip
            _PHASES[int(instance)] = Phases(hire["started"])  # provision runs from the hire
            key = _public_key(t)
            if key:
                vast.attach_ssh(instance, key)
            try:
                inst = vast.wait_running(instance, sleep=sleep)
            except VastError as e:  # it never came up: the host's failure, as a refused ssh is
                raise NeverBoarded(str(e)) from e
            actual = float(inst.get("dph_total") or 0.0)
            if actual > 0 and abs(actual - float(hire.get("dph") or 0.0)) > 1e-9:
                s3.reprice(instance, actual)
                hire["dph"] = actual
            box = (box_factory or (lambda i: Box(i["ssh_host"], i["ssh_port"])))(inst)
            try:
                box.log = log
                limit = fitout_limit()
                box.deadline = time.time() + limit if limit else None  # fitting out ends here, whatever step it is in
            except Exception:
                pass
            log(f"charter: instance {instance} is up ({inst.get('ssh_host')}:{inst.get('ssh_port')}); waiting for its ssh")
            _phase(instance, "ssh")
            tries = box.wait_ssh(timeout_s=BOARD_SSH_S, sleep=sleep, refresh=lambda: vast.show(instance),
                                 on_denied=(lambda: vast.attach_ssh(instance, key)) if key else None)  # fmt: skip
            log(f"charter: ssh answered (try {tries}); fitting out")
            _phase(instance, "code")
            box.bootstrap()
            code = code_carried(spec)
            _phase(instance, "code", _size(paths.ROOT, code) / 1e6)
            box.put_tar(paths.ROOT, code)  # one stream: rsync'ing 20k small files took most of an hour on 9 November
            aboard = carried_data(prep.tokeniser.id, voyage_books(prep)) + checkpoints_carried(rid, spec, rec)
            _phase(instance, "data", _size(paths.data_dir(), aboard) / 1e6)
            box.put_tar(paths.data_dir(), aboard, "data")  # the data too, as one stream (8,907 files took 16 min by rsync)
            _phase(instance, "board")
            st = stage(rid)
            s2.papers(st / "ledger.sqlite", spec, rid, rec)
            box.put(st, sorted(f.name for f in st.glob("*.sqlite") if f.name != "ledger.sqlite"), "data")
            box.put(st, ["ledger.sqlite"])
            (st / f"{rid}.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True))
            (st / f"{rid}.papers.json").write_text(json.dumps(store.papers_for_box(), ensure_ascii=False, indent=1))
            box.put(st, [f"{rid}.yaml", f"{rid}.papers.json"], "data/charter")
            with contextlib.suppress(OSError):  # the box has them; no 200 MB SQLite copy stays at home
                shutil.rmtree(st)
            _phase(instance, "env")
            box.sync_env()
            box.launch(rid)
            # the fit-out is over: its deadline bounds fitting out only. Left set, it refused every poll, pull
            # and the bringing home 30 minutes after fitting out began (12 November: the bridge trained on a
            # 4090 while its charter was told "fitting out ran past its deadline" for 23 minutes on end)
            with contextlib.suppress(Exception):
                box.deadline = None
            _phase(instance, "train")
            log(f"charter: {spec.get('name')} is at sea on instance {instance}")
            deadline = time.time() + q["hours"] * float(t["overrun"]) * 3600
            with contextlib.suppress(Exception):  # the deadline on record, for an `attach`; never worth the voyage
                s3.record("at sea", instance=instance, run_id=rid, deadline=deadline)
            status, counts = _watch(box, rid, p["start"], rec, hire, commit, deadline, log, sleep, poll_s)
            _phase(instance, "home")
            counts = _last_pull(box, rid, p["start"], rec, hire, commit, log, sleep)
            _register_home(rec, rid, log)
            if status == "home" and (rec.get_run(rid) or {}).get("status") != "finished":
                status = "came in unfinished"  # the box's voyage stopped short (its checkpoint is home: sail again)
            if status == "home":
                _drop_queued_home(hire, log)
        except NeverBoarded as e:
            error, failure = f"never boarded: {e}", e
            log(f"charter: instance {instance} never boarded, released: {e}")
        except Recalled as e:
            status, error = f"recalled ({e})", f"recalled ({e})"
            log(f"charter: {e} while instance {instance} is hired: releasing it (what it had pulled home is kept)")
            raise
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            log(f"charter: {spec.get('name')} failed on instance {instance}, releasing it: {error[-600:]}")
            raise
        finally:
            guard.closing()
            ended, _ = _release(vast, hire, status, rec, log, error=error)
    return hire, status, ended, counts, failure


def hired(which: str | int) -> dict:
    """The hire still out that `which` names: an instance id, a run id (or its first six characters or more),
    a voyage's name, or the voyage's spec file. NotAttachable when none is out under that name, or two are."""
    w = str(which).strip()
    if w.endswith((".yaml", ".yml")) and Path(w).exists():
        from thorp import train

        w = train.run_id(train.load_spec(w))
    out = s3.out_now()
    found = [
        h for h in out
        if w == str(h.get("instance")) or w == h.get("name")
        or (h.get("run_id") and (w == h["run_id"] or (len(w) >= 6 and str(h["run_id"]).startswith(w))))
    ]  # fmt: skip
    if len(found) != 1:
        ships = ", ".join(f"instance {h.get('instance')} ({h.get('name')}, run {str(h.get('run_id'))[:12]})" for h in out) or "none"
        raise NotAttachable(f"{'no' if not found else 'more than one'} hired ship is out as {w!r}; out now: {ships}")
    return found[0]


def _deadline(hire: dict, t: dict) -> float:
    """When the ship must be brought home, whatever its state: the deadline its charter recorded when the
    voyage went to sea, else (a charter that died while fitting out, or a hire from before 11 November) the
    hire's own time plus the quote's hours times the terms' overrun, which is earlier and so errs towards
    the budget."""
    marks = [r for r in s3.log() if r["event"] == "at sea" and r.get("instance") == hire["instance"] and r.get("deadline")]
    if marks:
        return float(marks[-1]["deadline"])
    if not hire.get("quote_hours"):
        raise NotAttachable(f"the hire of instance {hire['instance']} has no quote on record, so no deadline: "
                            "release it by hand (thorp charter audit --release-orphans)")  # fmt: skip
    return float(hire["started"]) + float(hire["quote_hours"]) * float(t["overrun"]) * 3600


def attach(which: str | int, vast=None, box_factory=None, rec: Ledger | None = None, log=_say, sleep=time.sleep,
           poll_s: float = 60.0) -> dict:  # fmt: skip
    """Take up a ship that is still hired though its charter is gone (11 November): the polling, the pulls,
    the overrun deadline and the release, exactly as `sail` would have gone on with them. Nothing is hired and
    nothing is fitted out; the voyage on the box never stopped. `which` is what `hired` reads.

    It refuses, and touches nothing, when the run's charter is still alive (its berth is held) or when
    Vast.ai does not show the instance up. A voyage that came in while no one watched is brought home and its
    ship released at once; one past its deadline likewise, as the terms say."""
    from thorp import train
    from thorp.viable.s3star_audit.charter import held_berths

    rec = rec or reader()
    hire = hired(which)
    rid, instance = hire["run_id"], int(hire["instance"])
    if rid in held_berths():
        raise NotAttachable(f"a charter is still sailing {rid[:12]} (its berth is held): there is nothing to take up")
    t = s5.terms()
    vast = vast or Vast(http_transport(api_key()))
    with s2.berth(t["max_instances"], rid):
        inst = vast.show(instance)
        if not (inst.get("actual_status") == "running" and inst.get("ssh_host") and inst.get("ssh_port")):
            raise NotAttachable(f"instance {instance} is not up at Vast.ai (it says {inst.get('actual_status')!r}): nothing was "
                                "touched. `thorp charter audit` closes the log for a ship that is gone, and "
                                "`--release-orphans` releases one that is there")  # fmt: skip
        actual = float(inst.get("dph_total") or 0.0)
        if actual > 0 and abs(actual - float(hire.get("dph") or 0.0)) > 1e-9:
            s3.reprice(instance, actual)
            hire["dph"] = actual
        deadline = _deadline(hire, t)
        start, commit = int(hire.get("start_step") or 0), hire.get("commit") or train.git_commit()
        box = (box_factory or (lambda i: Box(i["ssh_host"], i["ssh_port"])))(inst)
        with contextlib.suppress(Exception):
            box.log = log
        s2.note(rid, event="attached", instance=instance)
        with contextlib.suppress(Exception):  # the fit-out's length is the hire to its `at sea` mark, when it left one
            from datetime import datetime

            seas = [r for r in s3.log() if r["event"] == "at sea" and r.get("instance") == instance]
            sea = datetime.fromisoformat(str(seas[-1]["at"])).timestamp() if seas else None
            _PHASES[instance] = Phases.taken_up(float(hire["started"]), sea)
        log(f"charter: attached to instance {instance} ({hire.get('name')}, run {rid[:12]}), hired "
            f"{(time.time() - float(hire['started'])) / 3600:.1f} h ago; its deadline is {time.strftime('%d %b %H:%M', time.localtime(deadline))}")  # fmt: skip
        status, counts = "lost", {}
        with _recallable(log) as guard:
            try:
                status, counts = _watch(box, rid, start, rec, hire, commit, deadline, log, sleep, poll_s)
                _phase(instance, "home")
                counts = _last_pull(box, rid, start, rec, hire, commit, log, sleep)
                _register_home(rec, rid, log)
                if status == "home" and (rec.get_run(rid) or {}).get("status") != "finished":
                    status = "came in unfinished"
                if status == "home":
                    _drop_queued_home(hire, log)
            except Recalled as e:
                status = f"recalled ({e})"
                log(f"charter: {e} while instance {instance} is hired: releasing it (what it had pulled home is kept)")
                raise
            finally:
                guard.closing()
                ended, _ = _release(vast, hire, status, rec, log)
    return _close(rec, hire, status, ended, counts, log)
