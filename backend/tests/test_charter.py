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

from thorp import paths, train, vsm  # noqa: E402
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
                    disk_space=200.0, cuda_max_good=12.9, num_gpus=1)  # fmt: skip
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
        os.environ.update(THORP_DATA=str(self.root / "data"), THORP_LEDGER=str(self.root / "ledger.sqlite"), THORP_BACKEND="torch",
                          THORP_PAPERS=str(self.root / "data" / "charter" / f"{rid}.papers.json"))  # as Box.launch sets it
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
    assert "charter" in vsm.POLICIES and vsm.POLICIES["charter"].enforced
    assert vsm.POLICIES["charter"].check(spec) == []
    assert train.run_id({**spec, "charter": {"quote": {"cost": 1}}}) == train.run_id(spec)  # where it sails moves no id
    bad = {"gpu": "RTX 4090", "dph": 0.9, "verified": True, "reliability": 0.99, "inet_down": 500, "inet_up": 300, "cost": 1.0}
    with pytest.raises(vsm.GateRefused, match="ceiling"):
        s1.gate(spec, bad)
    assert vsm.gate_log(1)[0]["where"] == "charter" and vsm.gate_log(1)[0]["verdict"] == "refused"


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
    assert aboard == [] and [d["where"] for d in vsm.gate_log()] == ["charter", "voyage"]  # both asked at home
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
    assert ev == [("hired", None), ("released", "home")]
    rel = s3.log()[-1]
    assert rel["cost"] >= 0 and rel["tokens_per_s"] > 0 and s3.out_now() == []
    with s2.berth(1, "next"):  # and the berth is free again: a second charter could hire
        pass


def test_a_charter_over_its_budget_hires_nothing(library, spec, tmp_thorp):
    small_terms(tmp_thorp, voyage_budget=0.0001)
    market = FakeMarket()
    with pytest.raises(vsm.GateRefused, match="budget"):
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


def test_a_lost_leg_sails_on_from_its_checkpoint(library, spec, tmp_thorp, monkeypatch):
    """The first ship is lost at step 50 (its checkpoint brought home); the second charter carries that checkpoint
    up, sails from it, and its rows replace only what came after."""
    small_terms(tmp_thorp)
    spec["optim"]["precision"] = "fp32"
    path = write_spec(spec, tmp_thorp)
    rid = train.run_id(spec)
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
    other = v.hire(21, "img", 80, "someone-else")  # not Thorp's: never touched
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
