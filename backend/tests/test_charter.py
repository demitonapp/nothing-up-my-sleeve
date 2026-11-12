"""The charter (thorp/viable/*/charter.py, s1_operations/vast.py): a voyage on a GPU hired from Vast.ai, against a fake
market (the client's own calls, answered in memory) and a fake box (a folder, where the torch voyage really sails on
the CPU). Nothing here reaches Vast.ai.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from thorp import paths, train, liberty_machine  # noqa: E402
from thorp.ledger import Ledger  # noqa: E402
from thorp.viable.s1_operations import charter as s1  # noqa: E402
from thorp.viable.s1_operations.vast import Vast  # noqa: E402
from thorp.viable.s2_coordination import charter as s2  # noqa: E402
from thorp.viable.s3_control import charter as s3  # noqa: E402
from thorp.viable.s3star_audit import charter as s3star  # noqa: E402
from thorp.viable.s5_policy import charter as s5  # noqa: E402


@pytest.fixture(autouse=True)
def _cpu(monkeypatch):
    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.delenv("THORP_BACKEND", raising=False)
    monkeypatch.delenv("VAST_API_KEY", raising=False)


class FakeMarket:
    """Vast.ai's REST API in memory, answering the paths the client calls."""

    def __init__(self, offers=None, credit=50.0, spelling="RTX 4090"):
        base = dict(verified=True, rentable=True, rented=False, reliability=0.995, inet_down=900.0, inet_up=500.0,
                    disk_space=200.0, cuda_max_good=13.4, num_gpus=1)  # fmt: skip
        self.offers = offers or [
            {**base, "id": 11, "gpu_name": spelling, "dph_total": 0.62},
            {**base, "id": 12, "gpu_name": spelling, "dph_total": 0.38},
            {**base, "id": 13, "gpu_name": spelling, "dph_total": 0.31, "verified": False},
            {**base, "id": 21, "gpu_name": "H100 SXM", "dph_total": 2.10},
        ]
        self.instances, self.calls, self.credit, self.next = {}, [], credit, 900

    def __call__(self, method, path, body=None, query=None):
        self.calls.append((method, path, body))
        if method == "POST" and path == "/api/v0/bundles/":
            def keeps(o):
                for k, cond in body.items():
                    if not isinstance(cond, dict) or k not in o:
                        continue
                    for op, v in cond.items():
                        x = o[k]
                        if (op == "eq" and x != v) or (op == "lte" and x > v) or (op == "gte" and x < v):
                            return False
                return True

            return {"offers": sorted([o for o in self.offers if keeps(o)], key=lambda o: o["dph_total"])[: body["limit"]]}
        if m := re.fullmatch(r"/api/v0/asks/(\d+)/", path):
            o = next(o for o in self.offers if o["id"] == int(m[1]))
            self.next += 1
            self.instances[self.next] = {"id": self.next, "label": body["label"], "actual_status": "running", "ssh_host": "ssh9.vast.ai",
                                         "ssh_port": 40000 + self.next, "dph_total": o["dph_total"], "gpu_name": o["gpu_name"], "image": body["image"]}  # fmt: skip
            return {"success": True, "new_contract": self.next}
        if m := re.fullmatch(r"/api/v0/instances/(\d+)/", path):
            if method == "DELETE":
                self.instances.pop(int(m[1]), None)
                return {"success": True}
            return {"instances": self.instances.get(int(m[1]), {})}
        if path == "/api/v1/instances/":  # one a page, to walk next_token
            items = sorted(self.instances.values(), key=lambda i: i["id"])
            at = int((query or {}).get("after_token") or 0)
            page = items[at : at + 1]
            return {"instances": page, "next_token": str(at + 1) if at + 1 < len(items) else None}
        if re.fullmatch(r"/api/v0/instances/(\d+)/ssh/", path):
            return {"success": True}
        if path == "/api/v0/users/current/":
            return {"credit": self.credit}
        raise AssertionError(f"unexpected call {method} {path}")


class FakeBox:
    """A folder as the hired machine: put and get copy files, and `launch` sails the voyage there (the torch loop
    on the CPU, with the box's data folder and ledger), as `thorp run` does on a real box."""

    def __init__(self, root: Path, resolver, monkeypatch, fail_at=None):
        self.root, self.resolver, self.mp, self.fail_at = root, resolver, monkeypatch, fail_at
        self.code_files = 0

    def wait_ssh(self, **kw):
        return 1

    def bootstrap(self):
        if self.fail_at == "bootstrap":
            raise RuntimeError("the box would not answer")

    def sync_env(self):
        pass

    def put(self, root, rels, dst=""):
        if Path(root) == paths.ROOT:  # the code: counted, not copied (the box runs this checkout)
            self.code_files = len(rels)
            return
        for r in rels:
            t = self.root / dst / r
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(root) / r, t)

    put_tar = put  # the real box takes the code and the data as one tar stream (9 November); here a copy is a copy

    def get(self, src, dst):
        s = self.root / src.rstrip("/")
        if not s.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(s, dst)
        return True

    def launch(self, rid):
        import os

        home = {k: os.environ.get(k) for k in ("THORP_DATA", "THORP_LEDGER", "THORP_BACKEND")}
        home["THORP_PAPERS"] = os.environ.get("THORP_PAPERS")
        home["THORP_SHIP_LOG"] = os.environ.get("THORP_SHIP_LOG")
        os.environ.update(THORP_DATA=str(self.root / "data"), THORP_LEDGER=str(self.root / "ledger.sqlite"), THORP_BACKEND="torch",
                          THORP_PAPERS=str(self.root / "data" / "charter" / f"{rid}.papers.json"),
                          THORP_SHIP_LOG="1")  # as Box.launch sets them: aboard, the box reads and writes its own log
        # aboard, Postgres is out of reach (a hired box has none): anything that asks it fails here as it would there
        from sqlalchemy import create_engine

        from thorp import store
        from thorp.viable.s3_control import fitout_store

        dead = create_engine("postgresql+psycopg://thorp@localhost:1/thorp", connect_args={"connect_timeout": 1})
        at_home = (store.engine, fitout_store.engine)
        from thorp import fleet, ship_store

        ship_store.reload()  # a box's process is new: nothing read at home is cached aboard
        fleet._REGISTER = None
        self.mp.setattr(store, "engine", lambda: dead)
        self.mp.setattr(fitout_store, "engine", lambda: dead)
        try:
            box_led = Ledger()
            self.papers_row = box_led.get_run(rid)  # the box's gate knows the run S3 passed at home
            spec = train.load_spec(self.root / "data" / "charter" / f"{rid}.yaml")
            assert train.run_id(spec) == rid
            prep = train.prepare(spec, resolver=self.resolver, log=lambda *a: None)
            code = 0
            try:
                train.train(spec, prep, box_led, stop_after=self.fail_at if isinstance(self.fail_at, int) else None, log=lambda *a: None)
            except Exception:  # noqa: BLE001
                code = 1
            box_led.checkpoint_wal()
            (self.root / "data" / "charter" / f"{rid}.exit").write_text(str(code))
        finally:
            self.mp.setattr(store, "engine", at_home[0])  # home again: the store is in reach
            self.mp.setattr(fitout_store, "engine", at_home[1])
            for k, v in home.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def finished(self, rid):
        p = self.root / "data" / "charter" / f"{rid}.exit"
        return int(p.read_text()) if p.exists() else None


def store_ledger():
    """The store as the ledger at home (a PgLedger), each read ending its transaction: PgLedger.query leaves its read
    open, and an open read holds s1's tables against the truncate of a test running beside this one, which then holds
    up this test's own next write (11 November: the store-at-home voyage hung so)."""
    from thorp.ledger_store import PgLedger

    class Reading(PgLedger):
        def query(self, sql, params=()):
            try:
                return super().query(sql, params)
            finally:
                self._s.commit()

    return Reading()


def write_spec(spec, tmp_thorp) -> str:
    p = tmp_thorp / "voyage.yaml"
    p.write_text(json.dumps(spec))  # JSON is YAML
    return str(p)


def small_terms(tmp_thorp, **over):
    t = {"gpus": {"RTX 4090": 0.50, "H100 SXM": 2.60}, "voyage_budget": 5.0, "weekly_budget": 20.0, **over}
    for k, v in t.items():
        s5.set_term(k, v, "a test")


# ---------------------------------------------------------------- S5 and S3


def test_terms_are_the_defaults_under_s5s_changes(tmp_thorp):
    assert s5.terms() == s5.DEFAULTS
    small_terms(tmp_thorp, gpus={"RTX 4090": 0.4})
    t = s5.terms()
    assert t["gpus"]["RTX 4090"] == 0.4 and t["gpus"]["RTX 5090"] == s5.DEFAULTS["gpus"]["RTX 5090"]  # merged, not replaced
    assert t["voyage_budget"] == 5.0 and t["verified"] is True


def test_each_term_is_held():
    t = s5.DEFAULTS
    ok = {"gpu": "RTX 4090", "dph": 0.4, "verified": True, "reliability": 0.99, "inet_down": 500, "inet_up": 300,
          "cost": 2.0, "week_spent": 0.0, "credit": 100.0, "instances_out": 0}  # fmt: skip
    assert s3.violations(ok, t) == []
    for change, words in [
        ({"gpu": "A100"}, "not a class"),
        ({"dph": 0.9}, "ceiling"),
        ({"verified": False}, "verified"),
        ({"reliability": 0.9}, "reliability"),
        ({"inet_up": 10}, "line up"),
        ({"cost": 11.0}, "one voyage's budget"),
        ({"week_spent": 29.0}, "week's budget"),
        ({"credit": 2.4}, "credit"),
        ({"instances_out": 1}, "already hired"),
    ]:
        found = s3.violations({**ok, **change}, t)
        assert len(found) == 1 and words in found[0], (change, found)


def test_the_charter_policy_governs_only_chartered_voyages(spec, tmp_thorp):
    assert "charter" in liberty_machine.POLICIES and liberty_machine.POLICIES["charter"].enforced
    assert liberty_machine.POLICIES["charter"].check(spec) == []
    assert train.run_id({**spec, "charter": {"quote": {"cost": 1}}}) == train.run_id(spec)  # where it sails moves no id
    bad = {"gpu": "RTX 4090", "dph": 0.9, "verified": True, "reliability": 0.99, "inet_down": 500, "inet_up": 300, "cost": 1.0}
    with pytest.raises(liberty_machine.GateRefused, match="ceiling"):
        s1.gate(spec, bad)
    assert liberty_machine.gate_log(1)[0]["where"] == "charter" and liberty_machine.gate_log(1)[0]["verdict"] == "refused"


@pytest.mark.parametrize("positions", ["learned", "rope"])
def test_the_quote_counts_parameters_as_the_models_do(positions):
    from thorp.models import registry

    cfg = registry.config("9m", 2048, 512, positions)
    assert s3.params(cfg) == registry.build("gpt", "9m", 2048, 512, positions, backend="torch").parameter_counts()


# ---------------------------------------------------------------- the client


@pytest.mark.parametrize("spelling", ["RTX 4090", "RTX_4090"])
def test_the_client_reads_the_market_and_hires(spelling):
    m = FakeMarket(spelling=spelling)
    v = Vast(m)
    offers = v.search("RTX 4090", s5.DEFAULTS)
    assert [o["offer_id"] for o in offers] == [12]  # 11 is over the ceiling, 13 is unverified
    assert offers[0]["dph"] == 0.38 and offers[0]["verified"]
    i = v.hire(12, "img", 80, "thorp:abc")
    assert v.show(i)["actual_status"] == "running" and v.wait_running(i, sleep=lambda s: None)["ssh_port"]
    j = v.hire(21, "img", 80, "thorp:def")
    assert [x["id"] for x in v.instances()] == [i, j]  # walked page by page
    v.release(i)
    assert [x["id"] for x in v.instances()] == [j] and v.credit() == 50.0


def test_a_quote_without_a_key_is_priced_at_the_ceilings(library, spec, tmp_thorp):
    spec["model"]["backend"] = "torch"
    q = s1.quote(write_spec(spec, tmp_thorp), resolver=library["resolver"], log=lambda *a: None)
    assert q["market"].startswith("ceilings")
    assert {x["gpu"] for x in q["quotes"]} == set(s5.DEFAULTS["gpus"])
    assert q["plan"]["tokens_left"] == q["plan"]["total_steps"] * q["plan"]["tokens_per_step"] > 0
    with pytest.raises(s1.NoKey):
        s1.sail(write_spec(spec, tmp_thorp), resolver=library["resolver"], log=lambda *a: None)


# ---------------------------------------------------------------- the voyage


def test_a_chartered_voyage_sails_and_comes_home(library, spec, tmp_thorp, monkeypatch):
    small_terms(tmp_thorp)
    (paths.data_dir() / "secrets").mkdir(parents=True)
    (paths.data_dir() / "secrets" / "vast-api-key").write_text("not-to-be-carried")
    spec["optim"]["precision"] = "fp32"
    market, box_root = FakeMarket(), tmp_thorp / "box"
    boxes = []

    def make_box(inst):
        boxes.append(FakeBox(box_root, library["resolver"], monkeypatch))
        return boxes[0]

    rec = Ledger()
    out = s1.sail(write_spec(spec, tmp_thorp), vast=Vast(market), resolver=library["resolver"], box_factory=make_box,
                  rec=rec, log=lambda *a: None, sleep=lambda s: None, poll_s=0)  # fmt: skip
    rid = train.run_id(spec)
    assert out["status"] == "home" and out["run_id"] == rid
    assert market.instances == {}, "the ship is released"
    hired = [c for c in market.calls if c[0] == "PUT"]
    assert len(hired) == 1 and hired[0][1] == "/api/v0/asks/12/" and hired[0][2]["label"] == "thorp:" + rid
    # what was carried: the library, the voyage's tokeniser and shards, the papers; never the key
    assert boxes[0].code_files > 50
    assert not (box_root / "data" / "secrets").exists()
    assert (box_root / "data" / "manifest.sqlite").exists() and (box_root / "data" / "texts" / "local" / "loc-a.txt").exists()
    assert boxes[0].papers_row and boxes[0].papers_row["run_id"] == rid
    # the box sailed under the papers carried aboard (the S5 state its gate would read); its gate knew the run S3
    # passed at home, so it made no decision of its own, and nothing came home as one (tests/test_store.py folds one)
    assert (box_root / "data" / "charter" / f"{rid}.papers.json").exists()
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import GateDecision

    with store.session() as ss:
        aboard = ss.scalars(select(GateDecision).where(GateDecision.source == f"box papers {rid}")).all()
    assert aboard == [] and [d["where"] for d in liberty_machine.gate_log()] == ["charter", "voyage"]  # both asked at home
    # home: the run finished in this ledger, its rows and checkpoints, the hire on its hardware line
    run = rec.get_run(rid)
    assert run["status"] == "finished" and "vast.ai instance" in run["hardware"] and "torch" in run["hardware"]
    total = rec.query("select value from metrics where run_id=? and name='plan/total_steps'", [rid])[0]["value"]
    n = rec.query("select count(distinct step) n from metrics where run_id=? and name='loss'", [rid])[0]["n"]
    assert n == total > 50
    assert rec.query("select count(*) n from evals where run_id=?", [rid])[0]["n"] >= 1
    assert train.latest_checkpoint(rid) is not None
    # the spend log: hired, then released with its cost and the rate it made
    ev = [(r["event"], r.get("status")) for r in s3.log()]
    assert ev == [("hired", None), ("at sea", None), ("released", "home")]  # at sea: the deadline, for an attach (11 November)
    rel = s3.log()[-1]
    assert rel["cost"] >= 0 and rel["tokens_per_s"] > 0 and s3.out_now() == []
    with s2.berth(1, "next"):  # and the berth is free again: a second charter could hire
        pass


def test_a_charter_over_its_budget_hires_nothing(library, spec, tmp_thorp):
    small_terms(tmp_thorp, voyage_budget=0.0001)
    market = FakeMarket()
    with pytest.raises(liberty_machine.GateRefused, match="budget"):
        s1.sail(write_spec(spec, tmp_thorp), vast=Vast(market), resolver=library["resolver"], log=lambda *a: None)
    assert not [c for c in market.calls if c[0] == "PUT"] and s3.log() == []


def test_a_ship_is_released_whatever_goes_wrong(library, spec, tmp_thorp, monkeypatch):
    small_terms(tmp_thorp)
    market = FakeMarket()
    with pytest.raises(RuntimeError, match="would not answer"):
        s1.sail(write_spec(spec, tmp_thorp), vast=Vast(market), resolver=library["resolver"],
                box_factory=lambda i: FakeBox(tmp_thorp / "box", library["resolver"], monkeypatch, fail_at="bootstrap"),
                log=lambda *a: None, sleep=lambda s: None, poll_s=0)  # fmt: skip
    assert market.instances == {}
    assert [(r["event"], r.get("status")) for r in s3.log()] == [("hired", None), ("released", "lost")]


@pytest.mark.parametrize("home", ["sqlite", "store"])
def test_a_lost_leg_sails_on_from_its_checkpoint(library, spec, tmp_thorp, monkeypatch, home):
    """The first ship is lost at step 50 (its checkpoint brought home); the second charter carries that checkpoint
    up, sails from it, and its rows replace only what came after. At home either a SQLite ledger or the store
    (Postgres, as on this Mac: 11 November, until when no fold into it could succeed)."""
    small_terms(tmp_thorp)
    spec["optim"]["precision"] = "fp32"
    path = write_spec(spec, tmp_thorp)
    rid = train.run_id(spec)
    if home == "store":
        rec = store_ledger()
    else:
        rec = Ledger()

    def leg(n, fail_at):
        return s1.sail(path, vast=Vast(FakeMarket()), resolver=library["resolver"], rec=rec,
                       box_factory=lambda i: FakeBox(tmp_thorp / f"box{n}", library["resolver"], monkeypatch, fail_at=fail_at),
                       log=lambda *a: None, sleep=lambda s: None, poll_s=0)  # fmt: skip

    assert leg(1, 50)["status"] == "came in unfinished"  # stop_after 50: the box's voyage comes in short, exit 0
    assert train.latest_checkpoint(rid).name == "step-50"
    first = {r["step"] for r in rec.query("select step from metrics where run_id=? and name='loss'", [rid])}
    assert max(first) == 50
    out = leg(2, None)
    assert out["status"] == "home" and (tmp_thorp / "box2" / "data" / "checkpoints" / rid / "step-50").exists()
    steps = [r["step"] for r in rec.query("select step from metrics where run_id=? and name='loss' order by step", [rid])]
    assert steps == list(range(1, len(steps) + 1)), "no step lost or doubled across the two legs"
    assert rec.get_run(rid)["status"] == "finished"


def test_the_audit_finds_orphans_and_ghosts(tmp_thorp):
    market = FakeMarket()
    v = Vast(market)
    orphan = v.hire(12, "img", 80, "thorp:deadrun")
    other = v.hire(21, "img", 80, "someone-else")  # not Nothing up my sleeve's: never touched
    s3.record("hired", instance=orphan, run_id="deadrun", gpu="RTX 4090", dph=0.38, started=0.0)
    s3.record("hired", instance=4242, run_id="gonerun", gpu="RTX 4090", dph=0.38, started=0.0)  # Vast no longer has it
    r = s3star.audit(v, log=lambda *a: None)
    assert r["orphans"] == [orphan] and r["ghosts"] == [4242] and r["released"] == []
    with s2.berth(1, "deadrun"):  # a charter sailing it: not an orphan
        assert s3star.audit(v, log=lambda *a: None)["orphans"] == []
    r = s3star.audit(v, release_orphans=True, log=lambda *a: None)
    assert r["released"] == [orphan] and set(market.instances) == {other}
    assert s3.out_now() == []
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Audit

    with store.session() as ss:  # S3*'s own record: the ghost closed once, the orphan released once
        found = [(a.finding, a.instance, a.action) for a in ss.scalars(select(Audit).order_by(Audit.id))]
    assert found == [("ghost", 4242, "closed in the spend log"), ("orphan", orphan, "released")]


def test_the_real_box_speaks_ssh_and_rsync(tmp_thorp):
    import subprocess

    seen = []

    def run(argv, **kw):
        seen.append(argv)
        out = "0\n" if argv[0] == "ssh" and "cat " in argv[-1] else ""
        return subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")

    b = s1.Box("ssh9.vast.ai", 40123, run=run)
    b.bootstrap()
    b.put(tmp_thorp, ["a/b.txt"], "data")
    assert b.get("ledger.sqlite", tmp_thorp / "x" / "l.sqlite")
    b.launch("rid1")
    assert b.finished("rid1") == 0
    ssh = [a for a in seen if a[0] == "ssh"]
    assert all(a[a.index("-p") + 1] == "40123" and "root@ssh9.vast.ai" in a for a in ssh)
    assert "THORP_BACKEND=torch" in ssh[1][-1] and "thorp run data/charter/rid1.yaml" in ssh[1][-1] and ssh[1][-1].endswith("&")
    assert "THORP_PAPERS=/root/thorp/data/charter/rid1.papers.json" in ssh[1][-1]  # the box's gate sails under papers
    rs = [a for a in seen if a[0] == "rsync"]
    assert rs[0][-1] == f"root@ssh9.vast.ai:{s1.REMOTE}/data/" and any(x.startswith("--files-from=") for x in rs[0])
    assert rs[1][-2] == f"root@ssh9.vast.ai:{s1.REMOTE}/ledger.sqlite"


def test_a_dead_box_cannot_hold_a_transfer_forever(tmp_thorp):
    """12 November: the 9m candidate's manifest rsync sat on a box whose ssh had died for 18 minutes, and no
    step had a timeout; the hire only ended when the charter was killed by hand."""
    import subprocess

    seen = []

    def run(argv, **kw):
        seen.append((argv, kw))
        raise subprocess.TimeoutExpired(argv, kw.get("timeout") or 0)

    b = s1.Box("ssh9.vast.ai", 40123, run=run)
    with pytest.raises(s1.BoxError, match="stopped reading"):
        b.put(tmp_thorp, ["a/b.txt"], "data")
    argv, kw = seen[-1]
    assert kw["timeout"] == 1800 and "--timeout=120" in argv and "--contimeout=30" in argv


def test_fitting_out_has_a_deadline(tmp_thorp):
    """The whole fit-out is bounded: a box that stops reading is released, not waited on until the quote is gone."""
    import subprocess
    import time

    def run(argv, **kw):
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    b = s1.Box("ssh9.vast.ai", 40123, run=run)
    b.deadline = time.time() - 1
    with pytest.raises(s1.BoxError, match="deadline"):
        b.sh("true")


def test_the_fitout_limit_reads_the_switch(monkeypatch):
    assert s1.fitout_limit() == 30 * 60
    monkeypatch.setenv("THORP_FITOUT_MINUTES", "45")
    assert s1.fitout_limit() == 45 * 60
    monkeypatch.setenv("THORP_FITOUT_MINUTES", "0")
    assert s1.fitout_limit() == 0


def test_the_box_waits_for_ssh_and_attaches_the_key_again(tmp_thorp):
    """The first real charter (2026-11-08): Vast.ai said "running", the first ssh failed (255) and the fit-out gave up."""
    import subprocess

    answers = iter(["ssh: connect to host ssh1.vast.ai port 18576: Connection refused"] * 2
                   + ["root@ssh1.vast.ai: Permission denied (publickey)."] * 5 + [""])  # fmt: skip
    attached = []

    def run(argv, **kw):
        err = next(answers)
        return subprocess.CompletedProcess(argv, 255 if err else 0, stdout="", stderr=err)

    b = s1.Box("ssh1.vast.ai", 18576, run=run)
    assert b.wait_ssh(sleep=lambda s: None, on_denied=lambda: attached.append(1)) == 8
    assert attached == [1]  # attached again once, after six tries


def test_a_box_that_never_answers_says_why(tmp_thorp):
    import subprocess

    def run(argv, **kw):
        return subprocess.CompletedProcess(argv, 255, stdout="", stderr="Permission denied (publickey).")

    b = s1.Box("ssh1.vast.ai", 18576, run=run)
    with pytest.raises(s1.BoxError, match="Permission denied"):
        b.wait_ssh(timeout_s=45, every_s=15, sleep=lambda s: None)
    with pytest.raises(s1.BoxError, match="exit 255: Permission denied"):
        b.sh("true")
    assert "BatchMode=yes" in b.opts


def test_the_cli_shows_the_terms(tmp_thorp, capsys):
    from thorp import cli

    assert cli.main(["charter", "terms"]) == 0
    assert json.loads(capsys.readouterr().out)["max_instances"] == 1


def test_an_unmeasured_class_is_priced_no_faster_than_the_mac(monkeypatch):
    """The parity run (2026-11-08): until a class has sailed a preset, the quote is the FLOP guess or this Mac's
    wall-clock rate, whichever is slower, so the deadline (the quote times the overrun) does not cut a voyage short."""
    from thorp.models.registry import GPTConfig
    from thorp.viable.s4_intelligence import market

    cfg = GPTConfig(vocab=2048, context=1024, layers=6, width=192, heads=6)
    o = {"gpu": "RTX 4090", "dph": 0.5}
    monkeypatch.setattr(market, "throughput", lambda gpu, preset: None)
    monkeypatch.setattr(market, "mac_rate", lambda preset: None)
    guessed = market.price(cfg, "9m", 269_221_888, o)
    monkeypatch.setattr(market, "mac_rate", lambda preset: 63_000.0)
    floored = market.price(cfg, "9m", 269_221_888, o)
    assert floored["hours"] > guessed["hours"] and "this Mac" in floored["speed"]
    assert abs(floored["hours"] - (269_221_888 / 63_000 / 3600 + 0.35)) < 1e-6
    monkeypatch.setattr(market, "throughput", lambda gpu, preset: 400_000.0)  # once measured, the measure rules
    assert market.price(cfg, "9m", 269_221_888, o)["speed"].startswith("measured")


def test_the_launch_returns_at_once_not_at_the_end_of_the_voyage(tmp_thorp):
    """P1 (2026-11-08): `cd X && cmd > /dev/null &` backgrounds the whole list as a subshell that still holds ssh's
    stdout, so the launch's ssh stayed open to the end of the voyage and the charter never polled or pulled."""
    import subprocess

    seen = []

    def run(argv, **kw):
        seen.append((argv, kw))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    s1.Box("ssh9.vast.ai", 40123, run=run).launch("rid1")
    argv, kw = seen[0]
    cmd = argv[-1]
    assert kw["timeout"] == 120
    assert cmd.endswith("> /dev/null 2>&1 < /dev/null &")
    head, _, tail = cmd.partition("; ")
    assert head.startswith("cd ") and "&&" not in head  # the cd is its own command, outside the backgrounded one
    assert tail.startswith("THORP_BACKEND=torch") and "nohup sh -c" in tail and "&&" not in tail.split("sh -c", 1)[0]


def test_aboard_no_evaluator_asks_the_store(library, spec, tmp_thorp, monkeypatch):
    """A hired box has no Postgres (2026-11-08, the parity voyage: cards, nevermore, stars and pips failed at every
    reading with 'connection to 127.0.0.1:5433 refused'). Every evaluator that reads a deck, a size or a ship must
    read it from the papers carried aboard: aboard, none may record an eval_error."""
    small_terms(tmp_thorp)
    spec["optim"]["precision"] = "fp32"
    spec["model"]["context"] = 256  # the decks' prompts fit (as in test_torch)
    spec["eval"]["evaluators"] = ["ce_bpb", "samples", "stars", "nevermore", "cards", "pips", "discovery"]
    market, box_root, said = FakeMarket(), tmp_thorp / "box", []
    rec = Ledger()
    out = s1.sail(write_spec(spec, tmp_thorp), vast=Vast(market), resolver=library["resolver"],
                  box_factory=lambda inst: FakeBox(box_root, library["resolver"], monkeypatch),
                  rec=rec, log=said.append, sleep=lambda s: None, poll_s=0)  # fmt: skip
    rid = train.run_id(spec)
    assert out["status"] == "home"
    errors = [json.loads(r["text"])["error"] for r in rec.query("select text from artifacts where run_id=? and kind='eval_error'", [rid])]
    assert errors == []
    # registered with its ship at home, since aboard it cannot be (the toy preset is no size, so it says why)
    home = [x for x in said if "regist" in x]
    assert len(home) == 1 and "aboard" not in home[0] and ("registered as a voyage" in home[0] or "no size for preset 'tiny'" in home[0])


# ---------------------------------------------------------------- an outage on this Mac (11 November)
#
# The architecture audit's item 2: lost contact releases nothing, SIGTERM and SIGHUP run the charter's clean-up,
# and `attach` takes up a ship still hired. The box here only answers polls (no voyage is trained), the market is
# the fake above, and the pulls are counted, so these read the charter's decisions and nothing else.


class QuietBox:
    """A box that answers each poll as it is told: None (still at sea), an exit status, an exception (no
    answer), or a function to call. Its fit-out does nothing."""

    def __init__(self, answers=()):
        self.answers, self.polls, self.launched, self.log = list(answers), 0, None, None

    def finished(self, rid):
        self.polls += 1
        a = self.answers.pop(0) if self.answers else None
        if callable(a):
            a = a()
        if isinstance(a, BaseException):
            raise a
        return a

    def wait_ssh(self, **kw):
        return 1

    def launch(self, rid):
        self.launched = rid

    def bootstrap(self):
        pass

    sync_env = bootstrap

    def put(self, root, rels, dst=""):
        pass

    put_tar = put


@pytest.fixture
def pulls(monkeypatch):
    """`bring_home` counted, not done: `made` is each pull asked for, and each writes the run's row as the box
    would have it (`status[0]`: set it to "running" for a voyage that came in short)."""
    from types import SimpleNamespace

    made, status = [], ["finished"]

    def bring_home(box, rid, start, rec, hire, commit):
        made.append({"rid": rid, "start": start, "commit": commit, "instance": hire["instance"]})
        rec.run({"run_id": rid, "name": hire.get("name"), "status": status[0]})
        return {"metrics": len(made)}

    monkeypatch.setattr(s1, "bring_home", bring_home)
    monkeypatch.setattr(s1, "_register_home", lambda rec, rid, log: None)
    return SimpleNamespace(made=made, status=status)


def _hire(market, rid="r-attach-0123456789", name="1m@attach", **over) -> dict:
    """A ship hired by a charter that has since died: out at the market, and in S3's spend log."""
    import time

    instance = Vast(market).hire(12, "img", 80, s1.LABEL + rid)
    fields = dict(instance=instance, run_id=rid, name=name, gpu="RTX 4090", dph=0.38, offer=12, started=time.time() - 600,
                  quote=0.76, quote_hours=2.0, preset="9m", start_step=120, commit="abc1234")  # fmt: skip
    return s3.record("hired", **{**fields, **over})


def _attach(market, box, which, said=None, **kw):
    return s1.attach(which, vast=Vast(market), box_factory=lambda inst: box, rec=Ledger(),
                     log=(said.append if said is not None else (lambda *a: None)), sleep=lambda s: None, poll_s=0, **kw)  # fmt: skip


def test_lost_contact_releases_nothing(tmp_thorp, pulls):
    """Forty polls the box does not answer (it was ten that released it): each is logged, the ship stays hired,
    and when the box answers again the voyage goes on to its end."""
    import subprocess

    market, said = FakeMarket(), []
    hire = _hire(market)
    still_hired = []
    silence = [s1.BoxError("ssh ssh9.vast.ai:40901 exit 255: Connection timed out")] * 39 + [subprocess.TimeoutExpired("ssh", 60)]
    box = QuietBox([None, *silence, lambda: still_hired.append(hire["instance"] in market.instances), 0])
    out = _attach(market, box, hire["instance"], said)
    assert out["status"] == "home" and box.polls == 43 and still_hired == [True]
    misses = [m for m in said if "did not answer" in m]
    assert len(misses) == 40 and "miss 1," in misses[0] and "miss 40," in misses[-1]
    assert all("stays hired" in m for m in misses)
    assert any("answers again, after 40 missed poll(s)" in m for m in said)
    assert [c for c in market.calls if c[0] == "DELETE"] == [("DELETE", f"/api/v0/instances/{hire['instance']}/", None)]
    assert len(pulls.made) == 1  # the last pull only: none was tried into the silence
    assert [(r["event"], r.get("status")) for r in s3.log()] == [("hired", None), ("released", "home")]


def test_the_overrun_deadline_still_brings_a_silent_ship_home(tmp_thorp, pulls):
    """The deadline is policy and is kept: a box out of contact past it is brought home and released."""
    import time

    market, said = FakeMarket(), []
    hire = _hire(market, started=time.time() - 3 * 3600, quote_hours=1.0)  # 1 h quoted, 1.5 h allowed, 3 h gone
    box = QuietBox([s1.BoxError("no route to host")] * 5)
    out = _attach(market, box, hire["run_id"], said)
    assert out["status"] == "overran" and box.polls == 1 and market.instances == {}
    assert any("past its deadline" in m for m in said)
    assert s3.log()[-1]["status"] == "overran" and s3.out_now() == []
    assert Ledger().get_run(hire["run_id"])["status"] == "finished"  # as the pull left it; a short leg says so below


def test_attach_takes_up_a_ship_still_hired_and_hires_nothing(tmp_thorp, pulls):
    market, said = FakeMarket(), []
    hire = _hire(market)
    s3.record("at sea", instance=hire["instance"], run_id=hire["run_id"], deadline=hire["started"] + 9 * 3600)
    assert s1._deadline(hire, s5.terms()) == hire["started"] + 9 * 3600  # the charter's own deadline, when on record
    assert s1._deadline({**hire, "instance": 1}, s5.terms()) == hire["started"] + 2.0 * s5.terms()["overrun"] * 3600
    box = QuietBox([None, None, 0])
    out = _attach(market, box, "1m@attach", said)
    assert out["status"] == "home" and out["instance"] == hire["instance"] and out["run_id"] == hire["run_id"]
    assert box.launched is None and box.polls == 3  # nothing fitted out or launched: the voyage never stopped
    assert len([c for c in market.calls if c[0] == "PUT"]) == 1  # the hire this test made; attach made none
    assert market.instances == {} and s3.out_now() == []
    assert pulls.made == [{"rid": hire["run_id"], "start": 120, "commit": "abc1234", "instance": hire["instance"]}]
    rel = s3.log()[-1]
    assert (rel["event"], rel["status"], rel["instance"], rel["preset"], rel["gpu"]) == ("released", "home", hire["instance"], "9m", "RTX 4090")
    assert rel["started"] == hire["started"] and rel["cost"] > 0  # the whole hire is paid for, not the attached part
    assert any(f"attached to instance {hire['instance']}" in m for m in said)
    notes = (paths.runs_dir() / f"{hire['run_id']}.log").read_text()
    assert '"event": "attached"' in notes and '"event": "released"' in notes
    with s2.berth(1, "next"):  # its berth is free again
        pass


def test_a_ship_is_found_by_its_instance_its_run_or_its_name(tmp_thorp):
    market = FakeMarket()
    a = _hire(market, rid="aaaaaaaaaaaa1111", name="one")
    b = _hire(market, rid="aaaaaaaaaaaa2222", name="two")
    assert s1.hired(a["instance"])["name"] == "one" and s1.hired(str(b["instance"]))["name"] == "two"
    assert s1.hired("aaaaaaaaaaaa2222")["name"] == "two" and s1.hired("two")["instance"] == b["instance"]
    with pytest.raises(s1.NotAttachable, match="more than one"):
        s1.hired("aaaaaaaa")  # the start of both run ids
    with pytest.raises(s1.NotAttachable, match="no hired ship is out as 'three'; out now: instance"):
        s1.hired("three")
    s3.record("released", instance=a["instance"], run_id=a["run_id"], status="home", ended=0, cost=0)
    assert s1.hired("aaaaaaaa")["name"] == "two"  # one left out: six characters or more of its id are enough


def test_attach_refuses_and_touches_nothing(tmp_thorp, pulls):
    market = FakeMarket()
    with pytest.raises(s1.NotAttachable, match="no hired ship"):
        _attach(market, QuietBox(), "nothing-out")
    hire = _hire(market)
    with s2.berth(1, hire["run_id"]):  # its charter is alive
        with pytest.raises(s1.NotAttachable, match="still sailing"):
            _attach(market, QuietBox([0]), hire["instance"])
    assert hire["instance"] in market.instances
    market.instances[hire["instance"]]["actual_status"] = "exited"
    with pytest.raises(s1.NotAttachable, match="not up at Vast.ai.*'exited'"):
        _attach(market, QuietBox([0]), hire["instance"])
    market.instances.clear()  # Vast.ai no longer has it at all
    with pytest.raises(s1.NotAttachable, match="not up at Vast.ai"):
        _attach(market, QuietBox([0]), hire["instance"])
    assert not [c for c in market.calls if c[0] == "DELETE"] and pulls.made == []
    assert [r["event"] for r in s3.log()] == ["hired"]  # the log is the audit's to close, not attach's
    old = s3.record("hired", instance=4, run_id="r-old", dph=0.4, started=0.0)
    with pytest.raises(s1.NotAttachable, match="no quote on record"):
        s1._deadline(old, s5.terms())


def test_a_voyage_that_came_in_short_while_no_one_watched_says_so(tmp_thorp, pulls):
    market = FakeMarket()
    hire = _hire(market)
    pulls.status[0] = "running"  # the box's voyage exited 0 with its run unfinished (a stop_after, say)
    out = _attach(market, QuietBox([0]), hire["instance"])
    assert out["status"] == "came in unfinished" and market.instances == {}
    assert Ledger().get_run(hire["run_id"])["status"] == "chartered: came in unfinished"


def _canned_sail(monkeypatch, tmp_thorp, rid="r-sail-0123456789"):
    """`sail` with its quote and its cargo canned: what is under test is the charter after the hire."""
    from types import SimpleNamespace

    spec = {"name": "1m@sail", "model": {"preset": "9m", "backend": "torch"}}
    q = {"offer_id": 12, "gpu": "RTX 4090", "dph": 0.38, "hours": 1.0, "cost": 0.38, "speed": "canned"}

    def quote(spec_path, gpu=None, vast=None, resolver=None, log=print):
        return {"spec": spec, "prep": SimpleNamespace(tokeniser=SimpleNamespace(id="tok")), "quotes": [q], "market": "market",
                "plan": {"run_id": rid, "start": 0}, "vast": vast, "terms": s5.terms()}  # fmt: skip

    def stage(r):
        d = paths.data_dir() / "charter" / r / "stage"
        d.mkdir(parents=True, exist_ok=True)
        return d

    monkeypatch.setattr(s1, "quote", quote)
    monkeypatch.setattr(s1, "gate", lambda spec, q: None)
    monkeypatch.setattr(s1, "_public_key", lambda t: None)
    monkeypatch.setattr(s1, "voyage_books", lambda prep: set())
    monkeypatch.setattr(s1, "carried_data", lambda tok, books=None: [])
    monkeypatch.setattr(s1, "checkpoints_carried", lambda rid, spec, rec: [])
    monkeypatch.setattr(s1, "stage", stage)
    monkeypatch.setattr(s2, "papers", lambda *a, **k: [])
    return rid


def _sail(market, box, said=None):
    return s1.sail("canned.yaml", vast=Vast(market), box_factory=lambda inst: box, rec=Ledger(),
                   log=(said.append if said is not None else (lambda *a: None)), sleep=lambda s: None, poll_s=0)  # fmt: skip


def test_a_canned_sail_goes_to_sea_and_records_its_deadline(tmp_thorp, pulls, monkeypatch):
    import time

    rid = _canned_sail(monkeypatch, tmp_thorp)
    market, box = FakeMarket(), QuietBox([None, 0])
    t0 = time.time()
    out = _sail(market, box)
    assert out["status"] == "home" and box.launched == rid and market.instances == {}
    hired_, at_sea, released = s3.log()
    assert [hired_["event"], at_sea["event"], released["event"]] == ["hired", "at sea", "released"]
    assert hired_["start_step"] == 0 and hired_["quote_hours"] == 1.0 and hired_["commit"]  # all attach will need
    assert at_sea["instance"] == hired_["instance"] == released["instance"]
    want = t0 + 1.0 * float(s5.terms()["overrun"]) * 3600  # the quote times the overrun, from the launch: unchanged
    assert want - 1 <= at_sea["deadline"] <= want + 30
    assert s3.out_now() == [] and s3.week_spent() >= 0  # the new line is no hire and no spend


def test_sigterm_runs_the_clean_up_and_the_ship_is_released(tmp_thorp, pulls, monkeypatch):
    """SIGTERM used to end the charter where it stood: no `finally`, no release, the ship billing on. Now it is
    raised in the charter as `Recalled`, the ship is released and the release is on record with its instance."""
    import os
    import signal

    rid = _canned_sail(monkeypatch, tmp_thorp)
    market, said = FakeMarket(), []
    before = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)
    box = QuietBox([None, lambda: os.kill(os.getpid(), signal.SIGTERM), None, 0])
    real_release, again = Vast.release, []

    def release(self, instance):  # a second signal, mid-release, must not cut the release short
        os.kill(os.getpid(), signal.SIGHUP)
        again.append(instance)
        real_release(self, instance)

    monkeypatch.setattr(Vast, "release", release)
    with pytest.raises(s1.Recalled, match="SIGTERM"):
        _sail(market, box, said)
    assert box.polls == 2 and market.instances == {} and len(again) == 1
    rel = s3.log()[-1]
    assert (rel["event"], rel["status"], rel["instance"]) == ("released", "recalled (SIGTERM)", again[0])
    assert s3.out_now() == [] and pulls.made == []
    assert any("SIGTERM while instance" in m for m in said) and any("SIGHUP again, during SIGTERM" in m for m in said)
    notes = (paths.runs_dir() / f"{rid}.log").read_text()
    assert f'"instance": {again[0]}' in notes and "recalled (SIGTERM)" in notes
    assert (signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGHUP)) == before  # the handlers put back


def test_sighup_to_an_attached_charter_is_a_recall_too(tmp_thorp, pulls):
    import os
    import signal

    market = FakeMarket()
    hire = _hire(market)
    with pytest.raises(s1.Recalled, match="SIGHUP"):
        _attach(market, QuietBox([lambda: os.kill(os.getpid(), signal.SIGHUP), None]), hire["instance"])
    assert market.instances == {} and s3.log()[-1]["status"] == "recalled (SIGHUP)"


def test_a_signal_is_not_swallowed_by_a_pull_that_sails_on(tmp_thorp, monkeypatch):
    """A mid-run pull that fails is logged and the voyage sails on (`except Exception`); a recall that arrives
    during one must still reach the release, which is why `Recalled` is a BaseException."""
    import os
    import signal
    import time

    market = FakeMarket()
    hire = _hire(market)

    def bring_home(*a):
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.01)  # the handler runs here, inside the pull
        return {}

    monkeypatch.setattr(s1, "bring_home", bring_home)
    monkeypatch.setattr(s1, "PULL_EVERY_MIN", -1)  # a pull at every poll
    with pytest.raises(s1.Recalled):
        _attach(market, QuietBox([None, None]), hire["instance"])
    assert market.instances == {} and s3.log()[-1]["status"] == "recalled (SIGTERM)"


def test_a_hire_the_spend_log_could_not_take_is_still_released(tmp_thorp, pulls, monkeypatch):
    """The hire's record used to sit before the `try`: a store that refused it left the ship out with no charter.
    Now the instance is in the voyage's own log first, and whatever fails after the hire releases the ship."""
    rid = _canned_sail(monkeypatch, tmp_thorp)
    market, real = FakeMarket(), s3.record

    def record(event, **fields):
        if event == "hired":
            raise RuntimeError("the store would not take it")
        return real(event, **fields)

    monkeypatch.setattr(s3, "record", record)
    with pytest.raises(RuntimeError, match="would not take it"):
        _sail(market, QuietBox([0]))
    assert market.instances == {} and len([c for c in market.calls if c[0] == "DELETE"]) == 1
    assert [(r["event"], r["status"]) for r in s3.log()] == [("released", "lost")]
    assert '"event": "hired"' in (paths.runs_dir() / f"{rid}.log").read_text()


def test_a_box_that_cannot_be_reached_is_a_miss_not_a_voyage_still_at_sea(tmp_thorp):
    import subprocess

    answer = {}

    def run(argv, **kw):
        return subprocess.CompletedProcess(argv, answer["code"], stdout=answer.get("out", ""), stderr=answer.get("err", ""))

    b = s1.Box("ssh9.vast.ai", 40123, run=run)
    answer.update(code=0, out="")
    assert b.finished("rid1") is None  # reached, and not in yet
    answer.update(code=0, out="3\n")
    assert b.finished("rid1") == 3
    answer.update(code=255, out="", err="ssh: connect to host ssh9.vast.ai port 40123: Operation timed out")
    with pytest.raises(s1.BoxError, match="exit 255: ssh: connect to host"):
        b.finished("rid1")  # ssh itself failed: until 11 November this read as "not in yet"


def test_the_cli_attaches_by_name_and_says_when_there_is_nothing(tmp_thorp, capsys):
    from thorp import cli

    assert cli.main(["charter", "attach"]) == 2
    assert "needs a run id, an instance id or a voyage's name" in capsys.readouterr().err
    assert cli.main(["charter", "attach", "no-such-voyage"]) == 2  # refused before any key or network is asked for
    assert "no hired ship is out as 'no-such-voyage'" in capsys.readouterr().err


# ---------------------------------------------------------------- the fold into the store (11 November, item 4)

RID = "f" * 40


def box_ledger(path: Path, steps, *, first=1, start: float = 1000.0) -> Ledger:
    """A hired box's own SQLite log, as the trainer leaves it: the run row and, per step, a few metrics; an evals row
    and an artifact every tenth step."""
    box = Ledger(path)
    box.run({"run_id": RID, "name": "folded", "status": "running", "hardware": "torch · RTX 4090"})
    write_steps(box, range(first, steps + 1), start)
    return box


def write_steps(box: Ledger, steps, start: float = 1000.0) -> None:
    for s in steps:
        box.metrics(RID, s, {"loss": 5.0 - s / 100, "lr": 1e-3})
        if s % 10 == 0:
            box.evals([{"run_id": RID, "step": s, "set": "hole", "book_id": "loc-hole", "ce_nats": 1.0, "bpb": 2.0 - s / 1000,
                        "tokens": 10, "bytes": 40}])  # fmt: skip
            box.artifact(RID, s, "checkpoint", f"data/checkpoints/{RID}/step-{s}")


def home_rows(pg, table="metrics") -> list[tuple]:
    """(id, step, ...) at home for the run, in id order: what a fold kept, moved or wrote again."""
    key = {"metrics": "name", "evals": "book_id", "artifacts": "kind"}[table]
    return [(r["id"], r["step"], r[key]) for r in pg.query(f"select id, step, {key} from {table} where run_id=? order by id", [RID])]


def marks(pg) -> dict:
    return {r["tbl"]: (r["leg_start"], r["last_id"], r["rows"]) for r in pg.query("select * from s2.fold_marks where run_id=?", [RID])}


@pytest.fixture
def pg(tmp_thorp):
    p = store_ledger()
    yield p
    p.close()


def test_a_fold_into_the_store_is_incremental_and_folding_again_changes_nothing(tmp_thorp, pg):
    led = tmp_thorp / "box-ledger.sqlite"
    box = box_ledger(led, 40)
    out = s2.bring_home(led, RID, 0, pg, commit="abc")
    assert {t: out[t] for t in ("metrics", "evals", "artifacts")} == {"metrics": 80, "evals": 4, "artifacts": 4}
    assert {t: f["mode"] for t, f in out["fold"].items()} == dict.fromkeys(("metrics", "evals", "artifacts"), "replaced")
    first = home_rows(pg)
    assert len(first) == 80 and pg.get_run(RID)["commit"] == "abc" and marks(pg)["metrics"] == (-1, 80, 80)
    # again, with nothing new aboard: not a row deleted, written or renumbered, and the marks as they were
    again = s2.bring_home(led, RID, 0, pg, commit="abc")
    assert {f["mode"] for f in again["fold"].values()} == {"unchanged"} and home_rows(pg) == first
    assert sum(f["inserted"] + f["deleted"] for f in again["fold"].values()) == 0
    # twenty more steps aboard: only those come home, after the rows already there
    write_steps(box, range(41, 61))
    more = s2.bring_home(led, RID, 0, pg, commit="abc")
    assert more["fold"]["metrics"] == {"mode": "incremental", "deleted": 0, "inserted": 40}
    assert more["fold"]["evals"] == {"mode": "incremental", "deleted": 0, "inserted": 2}
    now = home_rows(pg)
    assert now[:80] == first and len(now) == 120 and [r[1] for r in now[80:]] == sorted(r[1] for r in now[80:])
    assert [r["step"] for r in pg.query("select step from metrics where run_id=? and name='loss' order by step", [RID])] == list(range(1, 61))


def test_a_box_resumed_past_a_truncation_folds_the_leg_again(tmp_thorp, pg):
    """The box's voyage died at 60 and resumed from its checkpoint at 50 aboard: it forgot 51-60 and wrote them again
    (SQLite gives the new rows the rowids it freed). The rows folded up to the mark are no longer the box's, so the
    leg is folded whole, in the one transaction, and nothing is doubled."""
    led = tmp_thorp / "box-ledger.sqlite"
    box = box_ledger(led, 60)
    s2.bring_home(led, RID, 0, pg)
    box.truncate_after(RID, 50)
    write_steps(box, range(51, 66))
    out = s2.bring_home(led, RID, 0, pg)
    assert out["fold"]["metrics"]["mode"] == "replaced" and out["fold"]["metrics"]["deleted"] == 120
    steps = [r["step"] for r in pg.query("select step from metrics where run_id=? and name='loss' order by step", [RID])]
    assert steps == list(range(1, 66)), "no step lost or doubled"
    assert s2.bring_home(led, RID, 0, pg)["fold"]["metrics"]["mode"] == "unchanged"


def test_a_new_leg_on_a_new_box_replaces_only_what_lies_past_its_start(tmp_thorp, pg):
    led = tmp_thorp / "box-ledger.sqlite"
    box_ledger(led, 60)
    s2.bring_home(led, RID, 0, pg)
    kept = [r for r in home_rows(pg) if r[1] <= 50]
    # the second leg sails from the checkpoint at 50 on another box: its log starts again at rowid 1
    led2 = tmp_thorp / "box2-ledger.sqlite"
    box_ledger(led2, 90, first=51)
    out = s2.bring_home(led2, RID, 50, pg)
    assert out["fold"]["metrics"] == {"mode": "replaced", "deleted": 20, "inserted": 80}
    assert [r for r in home_rows(pg) if r[1] <= 50] == kept  # the first leg's rows before the start, untouched
    # a third box from the same checkpoint, whose rowids reach past the second's mark: its rows are not the ones
    # folded, so the leg is folded whole again rather than its first rows skipped
    led3 = tmp_thorp / "box3-ledger.sqlite"
    box_ledger(led3, 140, first=51, start=2000.0)
    assert s2.bring_home(led3, RID, 50, pg)["fold"]["metrics"]["mode"] == "replaced"
    steps = [r["step"] for r in pg.query("select step from metrics where run_id=? and name='loss' order by step", [RID])]
    assert steps == list(range(1, 141))
    assert marks(pg)["metrics"][0] == 50


def test_a_fold_that_fails_part_way_leaves_the_store_as_it_was(tmp_thorp, pg, monkeypatch):
    from thorp import ledger_store

    led = tmp_thorp / "box-ledger.sqlite"
    box = box_ledger(led, 40)
    s2.bring_home(led, RID, 0, pg)
    before, before_marks = home_rows(pg), marks(pg)
    write_steps(box, range(41, 61))

    def boom(*a, **k):
        raise RuntimeError("the run row would not go")

    monkeypatch.setattr(ledger_store, "put_run", boom)  # the last write of the fold, after every table's rows
    with pytest.raises(RuntimeError, match="would not go"):
        s2.bring_home(led, RID, 0, pg)
    assert home_rows(pg) == before and marks(pg) == before_marks, "one transaction: all of the fold or none"
    monkeypatch.undo()
    assert s2.bring_home(led, RID, 0, pg)["fold"]["metrics"]["inserted"] == 40


def test_a_parent_pinned_by_run_id_has_its_checkpoint_carried(tmp_thorp):
    rec = Ledger()
    parent = "a" * 40
    rec.run({"run_id": parent, "name": "seedling", "status": "finished", "started": "2026-11-11T10:00:00"})
    ck = train.checkpoint_root(parent) / "step-10"
    ck.mkdir(parents=True)
    (ck / "state.json").write_text("{}")
    by_id = {"seeded_from": {"run": parent, "mode": "freeze"}}
    by_name = {"seeded_from": {"run": "seedling", "mode": "freeze"}}
    want = [f"checkpoints/{parent}/step-10/state.json"]
    assert s1.checkpoints_carried(RID, by_id, rec) == want and s1.checkpoints_carried(RID, by_name, rec) == want
