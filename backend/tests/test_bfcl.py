"""thorp/bfcl.py and thorp/evaluators/bfcl.py (14 November): rendering, reading a call, and the check, on hand-made
items in BFCL's own shape. No network."""

from __future__ import annotations

from thorp import bfcl
from thorp.evaluators.bfcl import _calls_in

AREA = {"name": "calculate_triangle_area", "description": "Calculate the area of a triangle given its base and height. "
        "Long words follow.", "parameters": {"type": "dict", "properties": {
            "base": {"type": "integer"}, "height": {"type": "integer"}, "unit": {"type": "string"}},
            "required": ["base", "height"]}}  # fmt: skip
PLAY = {"name": "spotify.play", "description": "Play songs.", "parameters": {"type": "dict", "properties": {
    "artist": {"type": "string"}, "duration": {"type": "integer"}}, "required": ["artist", "duration"]}}
SIMPLE = {"id": "simple_python_0", "question": [[{"role": "system", "content": "Be brief."},
          {"role": "user", "content": "Find the area of a triangle with a base of 10 and height of 5."}]],
          "function": [AREA], "answers": [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}]}  # fmt: skip
PARALLEL = {"id": "parallel_0", "question": [[{"role": "user", "content": "Play Taylor Swift for 20 and Maroon 5 for 15."}]],
            "function": [PLAY], "answers": [{"spotify.play": {"artist": ["Taylor Swift"], "duration": [20]}},
                                            {"spotify.play": {"artist": ["Maroon 5"], "duration": [15]}}]}  # fmt: skip


def test_render_is_plain_and_marks_optional_parameters():
    sig = bfcl.signature(AREA)
    assert sig == ("calculate_triangle_area(base: integer, height: integer, unit?: string) - "
                   "Calculate the area of a triangle given its base and height.")
    r = bfcl.rendered(SIMPLE)
    assert r.startswith("Tools:\ncalculate_triangle_area(") and r.endswith("base of 10 and height of 5.")
    assert "Be brief" not in r  # only the user's words


def test_parse_reads_keywords_positionals_and_dotted_names_without_running_them():
    assert bfcl.parse_call("calculate_triangle_area(base=10, height=5)") == {
        "name": "calculate_triangle_area", "args": {"base": 10, "height": 5}}
    assert bfcl.parse_call("calculate_triangle_area(10, 5)", [AREA])["args"] == {"base": 10, "height": 5}
    assert bfcl.parse_call("spotify.play(artist='Maroon 5', duration=15)")["name"] == "spotify.play"
    assert bfcl.parse_call("calculate_triangle_area(base=10") is None
    assert bfcl.parse_call("hello there") is None
    assert bfcl.parse_call("f(**x)") is None
    bad = bfcl.parse_call("calculate_triangle_area(base=__import__('os').getcwd(), height=5)")
    assert bad is not None and bad["args"]["base"] is bfcl._UNREADABLE  # read, never run


def test_check_follows_the_possible_answers():
    want = SIMPLE["answers"][0]
    ok = lambda s: bfcl.check(bfcl.parse_call(s, [AREA]), want, [AREA])[0]  # noqa: E731
    assert ok("calculate_triangle_area(base=10, height=5)")  # the optional unit left out
    assert ok("calculate_triangle_area(base=10.0, height=5, unit='Units')")  # a float for an int, case
    assert not ok("calculate_triangle_area(base=10)")  # a required one missing
    assert not ok("calculate_triangle_area(base=10, height=6)")
    assert not ok("calculate_triangle_area(base=10, height=5, colour='red')")  # no such parameter
    assert not ok("triangle_area(base=10, height=5)")


def test_score_simple_parallel_and_irrelevance():
    call = bfcl.parse_call("calculate_triangle_area(base=10, height=5)", [AREA])
    assert bfcl.score("simple_python", [call], SIMPLE)[0]
    assert not bfcl.score("simple_python", [call, call], SIMPLE)[0]
    assert not bfcl.score("simple_python", [None], SIMPLE)[0]
    a = bfcl.parse_call("spotify.play(artist='Maroon 5', duration=15)", [PLAY])
    b = bfcl.parse_call("spotify.play('Taylor Swift', 20)", [PLAY])
    assert bfcl.score("parallel", [a, b], PARALLEL)[0]  # any order
    assert not bfcl.score("parallel", [a, a], PARALLEL)[0]  # each answer matched once
    assert bfcl.score("irrelevance", [], {"function": [AREA], "answers": []})[0]
    assert not bfcl.score("irrelevance", [call], {"function": [AREA], "answers": []})[0]


def test_calls_are_read_from_what_a_ship_writes():
    text = "<call>spotify.play(artist='Maroon 5', duration=15)<result>done<call>spotify.play('Taylor Swift', 20)<result>"
    assert _calls_in(text) == ["spotify.play(artist='Maroon 5', duration=15)", "spotify.play('Taylor Swift', 20)"]
    assert _calls_in("<answer>No tool fits.<end>") == []
