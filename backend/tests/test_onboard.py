"""The first run: state, catalogue, downloads, store switch and the token that guards the page."""

from __future__ import annotations

import time

import pytest

from thorp import config, foreign
from thorp.onboard import api, catalogue, downloads, state, store_setup


def test_the_wizard_resumes_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    state.reset(archive=False)
    state.set_sailing(True, ["300k", "1m"])
    state.set_models(["xsmall"], ["mlx-community/Qwen3-0.6B-4bit"])
    state.step("store")
    again = state.read()
    assert again["step"] == "store"
    assert again["sailing"] == {"enabled": True, "classes": ["300k", "1m"]}
    assert again["models"]["selected"] == ["mlx-community/Qwen3-0.6B-4bit"]
    assert again["completed_at"] is None


def test_a_completed_wizard_is_kept_and_a_reset_archives_it(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    state.reset(archive=False)
    state.set_sailing(False, [])
    state.complete()
    assert state.read()["completed_at"]
    state.reset(archive=True)
    assert state.read()["completed_at"] is None
    archived = list((tmp_path / "data").glob("onboarding-*.json"))
    assert len(archived) == 1


def test_the_environment_beats_the_install_file(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("THORP_PG", raising=False)
    config.set_store("local", "")
    assert config.store_url() == ""
    config.set_store("hosted", "postgresql://someone@example.test/thorp")
    assert config.store_url() == "postgresql://someone@example.test/thorp"
    monkeypatch.setenv("THORP_PG", "postgresql://env@example.test/thorp")
    from thorp.viable.s3_control import fitout_store

    assert fitout_store.url() == "postgresql://env@example.test/thorp"
    assert config.locked() is True


def test_the_catalogue_is_curated_and_bands_are_consistent():
    assert set(catalogue.band_counts()) == set(catalogue.BAND_KEYS)
    for model in catalogue.MODELS:
        assert catalogue.get(model["repo"]) is model
        assert model["band"] in catalogue.BAND_KEYS
        assert model["params"] > 0
        assert model["download_gb"] > 0
        assert model["run_gb"] > 0


def test_a_model_too_large_for_the_mac_is_marked_so():
    small = catalogue.get("mlx-community/Qwen3-0.6B-4bit")
    large = catalogue.get("mlx-community/Llama-3.3-70B-Instruct-4bit")
    assert small and large
    assert catalogue.fit(small, 16) == "fits"
    assert catalogue.fit(large, 16) == "needs-more"


def test_a_repo_outside_the_catalogue_cannot_be_queued(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    with pytest.raises(ValueError):
        downloads.start(["someone/else-4bit"])


def test_a_cached_model_is_ready_without_another_download(tmp_path, monkeypatch):
    repo = "mlx-community/Qwen3-0.6B-4bit"
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(downloads, "_cached", lambda r: r == repo)
    downloads._JOBS.clear()
    downloads._QUEUE.clear()
    rows = downloads.start([repo])
    row = next(r for r in rows if r["repo"] == repo)
    assert row["state"] == "ready"
    assert row["percent"] == 100.0


def test_a_download_snapshots_into_the_cache_and_becomes_ready(tmp_path, monkeypatch):
    repo = "mlx-community/Qwen3-0.6B-4bit"
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(downloads, "_cache_dir", lambda r: tmp_path / "hub" / "models--test")

    def fake_snapshot(**kwargs):
        d = downloads._cache_dir(kwargs["repo_id"]) / "snapshots" / "abc"
        d.mkdir(parents=True)
        (d / "config.json").write_text("{}")
        (d / "weights.safetensors").write_bytes(b"weights")
        return str(d)

    monkeypatch.setattr(downloads, "_snapshot", fake_snapshot)
    downloads._JOBS.clear()
    downloads._QUEUE.clear()
    downloads.start([repo])
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        row = next(r for r in downloads.status() if r["repo"] == repo)
        if row["state"] in ("ready", "failed"):
            break
        time.sleep(0.05)
    row = next(r for r in downloads.status() if r["repo"] == repo)
    assert row["state"] == "ready", row
    assert row["bytes_done"] > 0


def test_only_the_one_time_token_can_ask_the_api_to_do_work():
    token = api.begin()
    assert api.authorized({"X-Thorp-Onboard": token})
    assert api.authorized({"X-Thorp-Onboard": "wrong"}) is False
    assert api.authorized({}) is False


def test_the_store_switch_refuses_while_a_voyage_is_at_sea(monkeypatch):
    monkeypatch.delenv("THORP_PG", raising=False)
    monkeypatch.setattr(store_setup, "at_sea", lambda: 2)
    with pytest.raises(store_setup.SetupError) as caught:
        store_setup.switch("local")
    assert "at sea" in str(caught.value)


def test_a_catalogue_model_appears_in_chat_once_its_weights_are_cached(monkeypatch):
    monkeypatch.setattr(foreign, "_cached", lambda model: model == "mlx-community/Qwen3-0.6B-4bit")
    monkeypatch.setattr(foreign, "_read_names", lambda: {})
    monkeypatch.setattr("thorp.viable.s4_intelligence.readings.chain_grades", lambda: {})
    rows = foreign.chat_targets()
    hit = next(r for r in rows if r["model"] == "mlx-community/Qwen3-0.6B-4bit")
    assert hit["label"] == "Qwen3 0.6B"
    assert hit["params"] == 0.6e9
    assert hit["lab"] == "alibaba"


def test_the_switch_writes_the_install_file_and_asks_for_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("THORP_PG", raising=False)
    config.set_store("local", "")
    monkeypatch.setattr(store_setup, "at_sea", lambda: 0)
    monkeypatch.setattr(
        store_setup,
        "test",
        lambda url: {"ok": True, "version": "17", "schema": "abc", "has_schema": True, "url": url},
    )
    out = store_setup.switch("hosted", "postgresql://someone@example.test/thorp")
    assert out["mode"] == "hosted"
    assert out["restart_required"] is True
    assert config.mode() == "hosted"
    assert config.store_url() == "postgresql://someone@example.test/thorp"


def test_the_switch_refuses_a_store_without_the_thorp_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    monkeypatch.delenv("THORP_PG", raising=False)
    config.set_store("local", "")
    monkeypatch.setattr(store_setup, "at_sea", lambda: 0)
    monkeypatch.setattr(
        store_setup,
        "test",
        lambda url: {"ok": True, "version": "17", "schema": None, "has_schema": False, "url": url},
    )
    with pytest.raises(store_setup.SetupError) as caught:
        store_setup.switch("hosted", "postgresql://someone@example.test/thorp")
    assert "schema" in str(caught.value)


def test_the_first_run_validates_its_choices(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    state.reset(archive=False)
    api.begin()
    assert api.answer({"step": "welcome"})["next"] == "sail"
    assert (
        api.answer({"step": "sail", "value": {"enabled": True, "classes": ["300k"]}})["next"]
        == "models"
    )
    with pytest.raises(api.OnboardError):
        api.answer({"step": "sail", "value": {"enabled": True, "classes": ["999m"]}})
    with pytest.raises(api.OnboardError):
        api.answer({"step": "models", "value": {"bands": ["xsmall"], "selected": ["evil/repo"]}})


def test_the_wizard_state_is_not_world_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("THORP_DATA", str(tmp_path / "data"))
    state.reset(archive=False)
    assert state.path().stat().st_mode & 0o777 == 0o600


def test_fleet_can_import_before_the_store_is_migrated(monkeypatch):
    from thorp import fleet

    class NoStore:
        def __iter__(self):
            raise RuntimeError("s1.sizes does not exist yet")

    monkeypatch.setattr(fleet, "LADDER", NoStore())
    assert fleet._preset(lambda row: True, "300k") == "300k"
