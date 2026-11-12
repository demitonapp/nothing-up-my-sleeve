"""The tool-call grammars (thorp.chat_tools): a template is read for the shape it asks for, and a call is
parsed in that shape.

Ling 3.0 Tiny (Bailing V3) was the one that failed in the console (12 November): its template says
"output the function name and arguments", so the detector chose `json`, but the grammar it actually asks
for is `<tool_call>NAME<arg_key>k</arg_key><arg_value>v</arg_value></tool_call>`. `json.loads` then failed
on the name at character 0, and four rounds of `unknown() → the call is not JSON` followed.
"""

from __future__ import annotations

from thorp import chat_tools

# the shape of the Ling template's tools block, cut to what the detector reads
LING_TEMPLATE = """{%- if tools %}
{{- "# Tools\\n\\nYou may call one or more functions..." }}
If you need to use a function, for each function call, output the function name and arguments within
the following XML format:
<tool_call>{function-name}
<arg_key>{arg-key-1}</arg_key>
<arg_value>{arg-value-1}</arg_value>
</tool_call>
{%- endif %}"""


def test_the_ling_template_is_read_as_its_own_xml_not_json():
    fmt = chat_tools.tool_format(LING_TEMPLATE)
    assert fmt["format"] == "bailing-xml"
    assert fmt["arg"] == "tools"


def test_a_bailing_call_parses_its_name_and_arg_key_pairs():
    text = (
        "<tool_call>queue_status\n"
        "<arg_key>find</arg_key>\n<arg_value>arc-ai2-21m</arg_value>\n"
        "<arg_key>next</arg_key>\n<arg_value>3</arg_value>\n"
        "</tool_call>"
    )
    assert chat_tools.parse_calls(text, "bailing-xml") == [
        {"name": "queue_status", "arguments": {"find": "arc-ai2-21m", "next": 3}}
    ]


def test_a_bailing_call_with_no_arguments_is_still_a_call():
    calls = chat_tools.parse_calls("<tool_call>current_time\n</tool_call>", "bailing-xml")
    assert calls == [{"name": "current_time", "arguments": {}}]


def test_a_bailing_model_that_wrote_json_anyway_is_read_as_json():
    text = '<tool_call>{"name": "queue_status", "arguments": {"next": 2}}</tool_call>'
    assert chat_tools.parse_calls(text, "bailing-xml") == [{"name": "queue_status", "arguments": {"next": 2}}]


def test_a_bailing_call_with_no_function_name_is_kept_as_an_error():
    text = "<tool_call><arg_key>find</arg_key><arg_value>x</arg_value></tool_call>"
    call = chat_tools.parse_calls(text, "bailing-xml")[0]
    assert call["name"] == "" and "no function name" in call["error"]
    assert call["raw"]


def test_the_json_grammar_still_parses():
    text = '<tool_call>{"name": "calculate", "arguments": {"expression": "2 + 2"}}</tool_call>'
    assert chat_tools.parse_calls(text, "json") == [{"name": "calculate", "arguments": {"expression": "2 + 2"}}]


def test_arguments_written_as_a_json_string_are_read():
    text = '<tool_call>{"name": "calculate", "arguments": "{\\"expression\\": \\"2 + 2\\"}"}</tool_call>'
    assert chat_tools.parse_calls(text, "json") == [{"name": "calculate", "arguments": {"expression": "2 + 2"}}]


def test_a_json_call_that_does_not_parse_keeps_its_raw_text():
    call = chat_tools.parse_calls("<tool_call>not json</tool_call>", "json")[0]
    assert call["name"] == "" and "not JSON" in call["error"] and call["raw"] == "not json"


def test_the_qwen_xml_grammar_is_unchanged():
    text = '<tool_call><function=queue_status><parameter=find>arc-ai2-21m</parameter></function></tool_call>'
    assert chat_tools.parse_calls(text, "qwen-xml") == [{"name": "queue_status", "arguments": {"find": "arc-ai2-21m"}}]


def test_a_template_with_no_tools_takes_none():
    assert chat_tools.tool_format("{{ messages }}")["format"] is None


def test_before_calls_keeps_the_prose_and_drops_the_call():
    assert chat_tools.before_calls('Let me look.\n<tool_call>queue_status</tool_call>') == "Let me look."
    assert chat_tools.before_calls("No call here.") == "No call here."


def test_queue_status_gives_rows_goals_eta_and_learnings(monkeypatch):
    """queue_status (12 November): the next lines with their goals, when the queue finishes, and goal by goal
    what it will have taught, from the queue page's own plan."""
    serves = {"text": "Control tokens in our embeddings", "expedition_name": "The Kipling Expedition"}
    plan = {
        "hours_left": 10.0,
        "without_a_time": 1,
        "rows": [
            {"n": None, "name": "9m-at-sea", "status": "at sea", "goal_id": "k:2", "serves": serves},
            {"n": 1, "name": "300k-a", "kind": "voyage", "lane": "mac", "status": "queued", "starts_in_min": 30, "est_min": 33, "goal_id": "k:2", "serves": serves},
            {"n": 2, "name": "300k-b", "kind": "voyage", "lane": "mac", "status": "queued", "starts_in_min": 63, "est_min": 33, "goal_id": "k:2", "serves": serves},
            {"n": 3, "name": "a step", "kind": "step", "lane": "mac", "status": "queued", "starts_in_min": 96, "est_min": None},
        ],
    }
    goals = {"k:2": {"text": "Control tokens in our embeddings", "name": "The Kipling Expedition", "why": "how control tokens work",
                     "detail": "marked against plain, seed for seed", "evidence": "", "status": "open"}}
    monkeypatch.setattr(chat_tools, "_fleet", lambda next=5, find=None: {"summary": "nothing at sea", "running_now": [], "next": [], "_n": 2})
    monkeypatch.setattr(chat_tools, "_plan", lambda: plan)
    monkeypatch.setattr(chat_tools, "_goals", lambda: goals)
    out = chat_tools.run("queue_status", {"next": 2})
    assert [r["name"] for r in out["next"]] == ["300k-a", "300k-b"]
    assert out["next"][0]["goal"] == "Control tokens in our embeddings" and out["next"][0]["starts_in"] == "30 min"
    assert out["eta"]["hours_left"] == 10.0 and "at least" in out["eta"]["note"]
    assert out["learnings"] == [{
        "goal": "Control tokens in our embeddings", "expedition": "The Kipling Expedition", "lines": 2,
        "known_in": "1.6 h", "will_learn": "how control tokens work", "measured_by": "marked against plain, seed for seed",
        "so_far": "open",
    }]
    assert "1 line(s) serve no recorded goal" in out["summary"] and "_n" not in out


# ---- vsm_status, system_status, expedition_status (12 November) -------------------------------------------

AUDIT = {
    "S1": {"expeditions": {"kipling": "at sea", "ogden": "home"}, "acquisition": {"books": 19506}},
    "S3": {"policies": {"period": {"enforced": True, "refused_lately": 0}, "sop": {"enforced": False, "refused_lately": 0}},
           "exceptions": {"stores": {}}, "runs_not_finished": 3},
    "S3*": {"cleaning": {"version": "unwrap-v2"}},
    "S4": {"competitors": ["qwen"], "reference_ladder": ["pythia-14m"]},
    "S5": {"period": {"statement": "pre-1930 only", "adopted": "2026-11-07, Justin", "enforced": True},
           "sop": {"statement": "built to its SOP", "adopted": "2026-11-08, Justin", "enforced": False}},
    "breaking": {"sop": ["fitouts/300k@v0.0.6-base"]},
}
CYCLE = {
    "ticking": True,
    "last": {
        "at": "2026-11-12T11:56", "how": "by hand",
        "envelope": {"week_spent": 1.5, "weekly_budget": 30, "week_left": 28.5, "cycle_allowance": 3.56, "spendable": 2.37,
                     "cycles_left": 8, "purser": "routing"},
        "plan": {"ships": 1, "stay": 57, "abroad": [{"name": "9m-gqa", "gpu": "RTX 4090", "cost": 0.9}],
                 "options": [{"ships": 1, "all_done_h": 53.6}], "mac_only_h": 62.9},
        "proposals": [{"to": "S5", "what": "allow 2 ships at once", "why": "home sooner"}],
        "audit": {"findings": ["1 hire(s) never sailed"], "spend": 0.44, "wasted": 0.44,
                  "hires": [{"name": "9m-cand", "gpu": "RTX 4090", "quote": 0.36, "cost": 0.44, "sailed": False, "status": "recalled", "failed_in": "board"}]},
    },
    "failures": {"hires": 12, "failed": 7, "wasted_cost": 1.89, "wasted_min": 250},
    "classes": [{"gpu": "RTX 4090", "hires": 6, "sailed": 4, "failed": 2, "overhead_min": 6.2, "source": "measured"}],
    "judge": {"name": "qwen3.8-27b"}, "judge_can_run": [True, ""], "judgments": [], "to_judge": [],
}


def _world(monkeypatch, **over):
    readers = {
        "_audit": lambda: AUDIT,
        "_cycle": lambda: CYCLE,
        "_lanes": lambda: [{"lane": "mac", "kind": "local", "seats": 2, "open": True, "note": "this Mac"},
                           {"lane": "vast", "kind": "charter", "seats": 1, "open": False, "note": "a GPU | paused 12 Nov 12:33: the driver is too old"}],
        "_lints": lambda: [],
        "_jobs": lambda: [{"key": "queue-cycle", "enabled": True, "when": "0 6,18 * * *", "next": "18:00", "last": None}],
        "_hires": lambda: [],
        "_terms": lambda: {"weekly_budget": 30, "voyage_budget": 10, "max_instances": 1, "purser": "routing"},
        "_launch": lambda: LAUNCH,
        "_fleet": lambda next=5, find=None: {"summary": "", "running_now": [{"name": "9m-cand", "kind": "voyage"}], "queue_length": 58, "next": [], "_n": 1},
    }
    readers.update(over)
    for name, fn in readers.items():
        monkeypatch.setattr(chat_tools, name, fn)


def test_vsm_status_gives_a_line_a_system_and_names_what_needs_attention(monkeypatch):
    _world(monkeypatch)
    out = chat_tools.run("vsm_status", {})
    assert [s["system"] for s in out["systems"]] == ["S1", "S2", "S3", "S3*", "S4", "S5"]
    by = {s["system"]: s for s in out["systems"]}
    assert "1 job(s) at sea now (9m-cand)" in by["S1"]["status"] and by["S1"]["attention"] == []
    assert by["S2"]["attention"] == ["the vast lane is paused: 12 Nov 12:33: the driver is too old"]
    assert "proposal to S5: allow 2 ships at once" in by["S3"]["attention"]
    assert "1 queued run(s) break the sop policy" in by["S3*"]["attention"]
    assert out["summary"].startswith("4 of 6 systems need attention") and "could_not_read" not in out


def test_a_reading_that_fails_is_named_and_the_rest_still_answer(monkeypatch):
    def boom():
        raise RuntimeError("no store")

    _world(monkeypatch, _cycle=boom)
    out = chat_tools.run("vsm_status", {})
    assert out["could_not_read"] == ["cycle: RuntimeError: no store"]
    s3 = next(s for s in out["systems"] if s["system"] == "S3")
    assert "no planning cycle has been kept yet" in s3["status"] and "9 of" not in s3["status"]


def test_system_status_reads_one_system_by_any_of_its_names(monkeypatch):
    _world(monkeypatch)
    s3 = chat_tools.run("system_status", {"system": "s3"})
    assert s3["system"] == "S3" and s3["budget"]["this_cycle_may_commit"] == "$3.56"
    assert s3["last_cycle"]["queue_home_in_hours"] == 53.6 and s3["gate"]["advisory"] == ["sop"]
    assert chat_tools.run("system_status", {"system": "audit"})["system"] == "S3*"
    assert chat_tools.run("system_status", {"system": "Intelligence"})["judge"]["name"] == "qwen3.8-27b"
    assert chat_tools.run("system_status", {"system": "S5"})["policies"][0] == {
        "policy": "period", "enforced": True, "says": "pre-1930 only", "adopted": "2026-11-07, Justin"}
    assert "no system called 'S9'" in chat_tools.run("system_status", {"system": "S9"})["error"]


LAUNCH = {
    "name": "Nothing up my sleeve", "version": "0.1", "frozen": False, "draft": "0.0.6",
    "phases": [{"key": "trials", "name": "Test voyages", "state": "active", "note": "1 deciding goal open"},
               {"key": "launch", "name": "Launch", "state": "ahead", "note": "0 of 2 ships home"}],
    "readiness": {"params": 3, "signed": 1, "ready": 1, "waiting": 1, "drifted": 0, "blocking": 1, "ships": 2, "home": 0},
    "charter": {"columns": [{"class": "9m", "base": "9m@v0.0.6"}],
                "groups": [{"name": "the ship", "params": [{"name": "layers", "state": "ready"}, {"name": "width", "state": "waiting"}]}]},
    "parts": [{"goal_id": "kipling:8", "expedition": "kipling", "expedition_name": "The Kipling Expedition", "text": "The hull: deep against wide",
               "status": "open", "part": "decides", "why": "the hull's shape", "params": ["ship.width"]}],
    "preparations": {"kipling": {"kind": "test voyages", "decides": ["the ship: width"], "blocking": 1}},
    "fleet": [{"class": "9m", "voyages": 21, "mean_minutes": 75.8,
               "base": {"ship": "9m@v0.1", "state": "not laid", "rehearsals": [{"name": "9m@v0.0.6", "state": "home"}]},
               "instruct": {"ship": "9m@v0.1-instruct", "state": "not laid", "rehearsals": []}}],
}
GOALS = [
    {"goal_id": "kipling:8", "expedition_key": "kipling", "text": "The hull: deep against wide", "status": "open", "evidence": "", "words": ""},
    {"goal_id": "kipling:9", "expedition_key": "kipling", "text": "The window every class reads", "status": "done", "evidence": "ctx 512", "words": ""},
]
PLAN = {"rows": [
    {"name": "9m-hull-a", "status": "at sea", "goal_id": "kipling:8"},
    {"n": 1, "name": "9m-hull-b", "status": "queued", "goal_id": "kipling:8", "starts_in_min": 40},
]}


def _expedition_world(monkeypatch):
    monkeypatch.setattr(chat_tools, "_launch", lambda: LAUNCH)
    monkeypatch.setattr(chat_tools, "_plan", lambda: PLAN)
    monkeypatch.setattr(chat_tools, "_goal_rows", lambda: GOALS)
    monkeypatch.setattr(chat_tools, "_expeditions", lambda: {"kipling": {"name": "The Kipling Expedition", "goal": "the fleet's shape", "state": "at sea"}})


def test_expedition_status_reads_v01_its_charter_its_open_goals_and_its_fleet(monkeypatch):
    _expedition_world(monkeypatch)
    out = chat_tools.run("expedition_status", {})
    assert out["summary"].startswith("Nothing up my sleeve v0.1 is in Test voyages (not frozen: the draft standard is SOP v0.0.6)")
    assert "1 of 3 parameters of the master charter are signed, 1 are ready" in out["summary"]
    assert out["ready_to_sign"] == ["the ship: layers"]
    assert out["goals_still_deciding"] == [{
        "goal_id": "kipling:8", "goal": "The hull: deep against wide", "status": "open", "expedition": "The Kipling Expedition",
        "decides": ["ship.width"], "queued_for_it": 1, "at_sea_for_it": ["9m-hull-a"]}]
    assert out["fleet"] == [{"class": "9m",
                             "base": "the v0.1 ship 9m@v0.1 is not laid yet (no spec written) (only a rehearsal, 9m@v0.0.6, is home)",
                             "instruct": "the v0.1 ship 9m@v0.1-instruct is not laid yet (no spec written) (no rehearsal has sailed)"}]
    assert out["goals_still_deciding"][0]["goal_id"] == "kipling:8"
    assert chat_tools.run("expedition_status", {"find": "v0.1"})["summary"] == out["summary"]


def test_expedition_status_finds_a_preparation_a_goal_or_a_class(monkeypatch):
    _expedition_world(monkeypatch)
    k = chat_tools.run("expedition_status", {"find": "Kipling"})
    assert k["expedition"] == "kipling" and "1 of 2 goal(s) done" in k["summary"] and "1 of its goals still hold up" in k["summary"]
    assert k["goals"][0]["next_queued"] == "9m-hull-b" and k["goals"][0]["next_starts_in"] == "40 min"
    g = chat_tools.run("expedition_status", {"find": "kipling:9"})
    assert g["status"] == "done" and g["evidence"] == "ctx 512"
    assert chat_tools.run("expedition_status", {"find": "window"})["goals"][0]["goal_id"] == "kipling:9"
    assert chat_tools.run("expedition_status", {"find": "9m"})["summary"].startswith("the 9m class of Nothing up my sleeve v0.1")
    assert "nothing called 'zzz'" in chat_tools.run("expedition_status", {"find": "zzz"})["error"]


def test_every_tool_has_a_schema_and_ling_can_call_the_new_ones():
    assert {s["function"]["name"] for s in chat_tools.SCHEMAS} == set(chat_tools.TOOLS)
    text = "<tool_call>system_status\n<arg_key>system</arg_key>\n<arg_value>S3*</arg_value>\n</tool_call>"
    assert chat_tools.parse_calls(text, "bailing-xml") == [{"name": "system_status", "arguments": {"system": "S3*"}}]
