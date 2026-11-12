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
    assert "vsm_status" not in chat_tools.TOOLS
