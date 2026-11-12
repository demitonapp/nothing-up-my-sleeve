"""The drone fleet (thorp/drones.py): the browser drone's pilots, choosing one, and the run the file
kept when a dashboard restart cut it off."""

from __future__ import annotations

import json

import pytest

from thorp import chat_tools, drones


@pytest.fixture
def fleet(tmp_path, monkeypatch):
    monkeypatch.setattr(drones, "STATE", tmp_path / "drones.json")
    monkeypatch.setattr(drones, "MODELS", tmp_path / "models")
    monkeypatch.setattr(drones, "RUNS", tmp_path / "drones")
    monkeypatch.setattr(drones, "_RECONCILED", False)
    drones._RUNS.clear()
    drones._DOWNLOADS.clear()
    return tmp_path


def _install(root, key: str) -> None:
    p = drones.PILOTS[key]
    d = root / "models" / key
    d.mkdir(parents=True)
    (d / p.quant).write_bytes(b"gguf")
    (d / p.mmproj).write_bytes(b"mmproj")


def test_the_first_drone_is_the_browser_drone_and_fara_is_its_recommended_pilot(fleet):
    payload = drones.payload("browser")
    assert payload["drone"]["name"] == "Browser drone"
    assert payload["drone"]["label"] == "D1"
    assert payload["selected"] == "fara-1.5-9b"
    assert next(m for m in payload["models"] if m["recommended"])["key"] == "fara-1.5-9b"
    assert payload["models"][0]["harness"] == "fara"


def test_only_a_downloaded_pilot_can_be_chosen(fleet):
    with pytest.raises(ValueError, match="not downloaded"):
        drones.select("browser", "fara-1.5-4b")
    _install(fleet, "fara-1.5-4b")
    assert drones.select("browser", "fara-1.5-4b")["selected"] == "fara-1.5-4b"
    # the choice survives a re-read of the file
    assert drones.selected("browser") == "fara-1.5-4b"


def test_a_run_left_flying_by_a_restart_is_said_not_left_flying(fleet):
    drones.STATE.write_text(
        json.dumps(
            {
                "browser": {
                    "model": "fara-1.5-9b",
                    "runs": [
                        {"id": "cut-off", "drone": "browser", "state": "running", "started": "2026-11-12T14:00:00"}
                    ],
                }
            }
        )
    )
    run = drones.payload("browser")["runs"][0]
    assert run["state"] == "error"
    assert "restarted" in run["error"]


def test_the_chat_terminal_has_the_browser_tools():
    names = [s["function"]["name"] for s in chat_tools.SCHEMAS]
    assert "browser_task" in names and "browser_task_status" in names
    assert "browser_task" in chat_tools.TOOLS and "browser_task_status" in chat_tools.TOOLS
    assert chat_tools.run("browser_task_status", {"id": "no-such-run"}) == {
        "error": "no browser drone run 'no-such-run'"
    }


def test_the_drone_visits_http_and_https_only():
    assert drones._clean_url("example.com") == "https://example.com"
    assert drones._clean_url("https://example.com/a") == "https://example.com/a"
    with pytest.raises(ValueError, match="http and https"):
        drones._clean_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="http and https"):
        drones._clean_url("javascript:alert(1)")


def test_the_fleet_has_three_drones_and_the_email_drone_flies_a_text_pilot(fleet):
    assert [d["key"] for d in drones.fleet_payload()["drones"]] == ["browser", "email", "phone"]
    mail = drones.payload("email")
    assert mail["drone"]["name"] == "Email drone"
    assert mail["drone"]["label"] == "D2"
    assert [m["key"] for m in mail["models"]] == ["qwen3.5-9b-instruct", "qwen3.5-4b-instruct"]
    assert all(m["harness"] == "text" and not m["installed"] for m in mail["models"])
    assert mail["bridge"]["configured"] is False
    assert mail["bridge"]["options"]


def test_a_text_pilot_cannot_be_sent_to_a_web_page(fleet):
    with pytest.raises(ValueError, match="not a browser pilot"):
        drones.start_task("open example.com", model="qwen3.5-9b-instruct")


def test_the_phone_drone_has_a_voice_bridge_and_its_safety_terms(fleet):
    phone = drones.payload("phone")
    assert phone["drone"]["label"] == "D3"
    assert phone["drone"]["name"] == "Phone drone"
    assert [m["key"] for m in phone["models"]] == ["qwen3.5-9b-instruct", "qwen3.5-4b-instruct"]
    bridge = phone["bridge"]
    assert bridge["configured"] is True
    assert bridge["mode"] == "local"
    assert len(bridge["options"]) == 3
    assert any("Whisper" in x for x in bridge["voice"])
    assert any("says it is an AI" in x for x in bridge["safety"])
    assert any("emergency" in x for x in bridge["safety"])


def test_the_phone_drone_will_not_start_without_a_downloaded_text_pilot(fleet):
    from thorp import phone

    with pytest.raises(ValueError, match="not downloaded"):
        phone.start("Ask the supplier about the oak boards")


def test_the_chat_terminal_has_the_local_phone_tools():
    names = [s["function"]["name"] for s in chat_tools.SCHEMAS]
    assert {"phone_call", "phone_say", "phone_end"} <= set(names)
    assert {"phone_call", "phone_say", "phone_end"} <= set(chat_tools.TOOLS)
    assert chat_tools.run("phone_end", {"id": "no-such-call"}) == {"error": "no test call 'no-such-call'"}
