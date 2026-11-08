"""Thorp's own schedule (S2, thorp/viable/s2_coordination/schedule.py) and its judge (S5): jobs and firings in the
store, each due time fired once, missed ones logged, a firing run through the judge chosen in s5.judges."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta

import pytest

from thorp import store
from thorp.viable.records import JobFiring, ScheduledJob
from thorp.viable.s2_coordination import schedule as sch

TZ = datetime.now().astimezone().tzinfo


def at(h, m=0, d=8):
    return datetime(2026, 11, d, h, m, tzinfo=TZ)


def job(key="j", cron="10 */2 * * *", fire_at=None, enabled=True, enabled_at=None, **kw):
    sch.put_job(key, title=key, system="S2", kind=kw.pop("kind", "judge"), cron=None if fire_at else cron, fire_at=fire_at,
                enabled=enabled, enabled_at=enabled_at or at(0), prompt=kw.pop("prompt", "Check the queue."),
                command=kw.pop("command", None), limits=kw.pop("limits", {}), **kw)  # fmt: skip


def firings(key="j"):
    with store.session() as s:
        return [(f.due_at, f.outcome, f.summary) for f in s.query(JobFiring).filter_by(job_key=key).order_by(JobFiring.id)]


def test_cron_is_read_as_cron_reads_it():
    assert sch.matches("10 */2 * * *", at(14, 10)) and not sch.matches("10 */2 * * *", at(15, 10))
    assert sch.matches("0 9 1,15 * *", datetime(2026, 11, 15, 9, 0, tzinfo=TZ))
    assert sch.matches("0 9 * * 0", datetime(2026, 11, 8, 9, 0, tzinfo=TZ))  # 8 November 2026 is a Sunday
    assert sch.matches("0 9 * * 7", datetime(2026, 11, 8, 9, 0, tzinfo=TZ))
    assert sch.last_due("10 */2 * * *", at(15, 40), at(0)) == at(14, 10)
    assert sch.next_due("10 */2 * * *", at(14, 10)) == at(16, 10)
    with pytest.raises(ValueError):
        sch.parse_cron("61 * * * *")


def test_a_due_time_fires_once_however_many_ticks_see_it():
    job()
    spawned = []
    out = sch.tick(at(14, 11), spawn=lambda fid: spawned.append(fid) or 4242)
    assert [x["how"] for x in out] == ["fire"] and len(spawned) == 1
    assert sch.tick(at(14, 12), spawn=lambda fid: spawned.append(fid) or 1) == [] and len(spawned) == 1
    with store.session() as s:
        assert s.get(JobFiring, spawned[0]).pid == 4242


def test_nothing_is_owed_before_it_was_enabled_and_a_stale_time_is_missed_not_fired():
    job(enabled_at=at(14, 30))
    assert sch.tick(at(14, 40), spawn=lambda fid: 1) == []  # 14:10 came before it was switched on
    out = sch.tick(at(16, 50), spawn=lambda fid: pytest.fail("a stale due time must not fire"))
    assert [x["how"][:6] for x in out] == ["missed"] and firings()[0][1] == "missed"


def test_a_job_still_running_misses_its_next_time():
    job()
    sch.tick(at(14, 10), spawn=lambda fid: 1)
    out = sch.tick(at(16, 10), spawn=lambda fid: pytest.fail("not while the last firing runs"))
    assert out[0]["how"].startswith("missed: firing") and [o for _, o, _ in firings()] == ["running", "missed"]


def test_a_one_time_job_fires_once_then_is_off():
    job(fire_at=at(12))
    assert len(sch.tick(at(12, 5), spawn=lambda fid: 1)) == 1
    with store.session() as s:
        assert s.get(ScheduledJob, "j").enabled is False


def test_a_disabled_job_never_fires():
    job(enabled=False)
    assert sch.tick(at(14, 10), spawn=lambda fid: pytest.fail("off")) == []


def _fired(**kw):
    job(**kw)
    (x,) = sch.tick(at(14, 10), spawn=lambda fid: 1)
    return x["firing"]


def test_the_judge_is_s5s_choice_and_gets_the_prompt_word_for_word(tmp_thorp):
    fid = _fired(prompt="You are keeping watch.\nDo this:\n1. Health.")
    seen = {}

    def runner(argv, input, cwd, capture_output, text, timeout):
        seen.update(argv=argv, input=input, timeout=timeout)
        return subprocess.CompletedProcess(argv, 0, stdout="all healthy\nsummary line", stderr="")

    assert sch.run_firing(fid, runner=runner)["outcome"] == "failed"  # no judge chosen: says so, guesses nothing
    assert "no judge chosen" in firings()[0][2]
    fid = _fired(key="k", prompt="You are keeping watch.\nDo this:\n1. Health.")
    sch.set_judge("claude", ["claude", "-p"], "Justin: claude initially")
    r = sch.run_firing(fid, runner=runner)
    assert r == {"firing": fid, "job": "k", "judge": "claude", "outcome": "ok", "exit_code": 0}
    assert seen["argv"] == ["claude", "-p"] and seen["input"] == "You are keeping watch.\nDo this:\n1. Health."
    assert seen["timeout"] == 60 * 60 and firings("k")[0][2].endswith("summary line")
    sch.set_judge("thorp:21m", ["uv", "run", "thorp", "judge", "21m"], "later: a Thorp model")  # no code changes
    fid = _fired(key="m", prompt="p")
    assert sch.run_firing(fid, runner=runner)["judge"] == "thorp:21m" and seen["argv"][-1] == "21m"


def test_a_command_job_and_a_timeout(tmp_thorp):
    fid = _fired(kind="command", command="echo docked", prompt=None)
    r = sch.run_firing(fid)
    assert r["outcome"] == "ok" and r["judge"] == "command" and firings()[0][2] == "docked"
    fid = _fired(key="slow", kind="command", command="sleep 5", prompt=None, limits={"max_minutes": 0.01})
    assert sch.run_firing(fid)["outcome"] == "timeout"


def test_a_judge_that_cannot_start_fails_the_firing(tmp_thorp):
    sch.set_judge("claude", ["/no/such/claude", "-p"], "a test")
    fid = _fired()
    assert sch.run_firing(fid)["outcome"] == "failed" and "could not be started" in firings()[0][2]


def test_claude_codes_tasks_come_in_word_for_word_and_switched_off(tmp_path):
    for key, body in (("thorp-first-light", "You are steering.\n\n1. Health.\n"), ("land-search-recheck", "not Thorp's")):
        (tmp_path / key).mkdir()
        (tmp_path / key / "SKILL.md").write_text(f"---\nname: {key}\ndescription: d\n---\n\n{body}")
    listing = [{"taskId": "thorp-first-light", "title": "First Light", "cronExpression": "10 */2 * * *", "enabled": True},
               {"taskId": "land-search-recheck", "cronExpression": "0 9 1,15 * *", "enabled": True}]  # fmt: skip
    assert sch.import_claude(listing, tmp_path) == ["thorp-first-light"]
    with store.session() as s:
        j = s.get(ScheduledJob, "thorp-first-light")
        assert j.prompt == "You are steering.\n\n1. Health.\n" and j.enabled is False and j.cron == "10 */2 * * *"
        assert "enabled there" in j.source and s.get(ScheduledJob, "land-search-recheck") is None


def test_the_cli_enables_with_words_and_lists(capsys):
    job(enabled=False)
    assert sch.main(["enable", "j", "on", "--words", "Justin: switch over"]) == 0
    sch.main(["list"])
    (row,) = json.loads(capsys.readouterr().out)
    assert row["enabled"] and row["next"] is not None
    with store.session() as s:
        assert s.get(ScheduledJob, "j").enabled_at > datetime.now().astimezone() - timedelta(minutes=1)
