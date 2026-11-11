"""ARC-AGI-2's encoding, parsing and scoring (11 November): the text form the models read and the
exact-match rule the benchmark uses."""

import json

from thorp import arc


def test_grid_text_round_trips():
    grid = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
    assert arc.grid_text(grid) == "3x3:010/101/010"
    assert arc.parse_grid("3x3:010/101/010") == (grid, True)


def test_parse_takes_the_last_headed_grid():
    text = "Example: input 2x2:01/10 -> output 2x2:11/11\nTest: input 1x1:0 -> output 1x1:1"
    assert arc.parse_grid(text) == ([[1]], True)


def test_parse_prefers_the_expected_shape():
    text = "2x2:01/10 then 1x1:7"
    assert arc.parse_grid(text, shape=(1, 1)) == ([[7]], True)


def test_parse_bare_digits_with_shape():
    assert arc.parse_grid("answer: 010101010", shape=(3, 3)) == ([[0, 1, 0], [1, 0, 1], [0, 1, 0]], True)


def test_parse_bare_rows_without_shape():
    assert arc.parse_grid("010/101/010") == ([[0, 1, 0], [1, 0, 1], [0, 1, 0]], True)


def test_parse_keeps_a_parsed_grid_of_another_shape():
    # a wrong-shaped answer is parsed (it is a grid) but cannot be exact: cell accuracy is 0
    assert arc.parse_grid("2x2:01/10", shape=(3, 3)) == ([[0, 1], [1, 0]], True)
    assert not arc.exact([[0, 1], [1, 0]], [[0, 1, 0], [1, 0, 1], [0, 1, 0]])
    assert arc.parse_grid("no grid here") == (None, False)


def test_exact_and_cell_accuracy():
    want = [[0, 1], [1, 0]]
    assert arc.exact([[0, 1], [1, 0]], want)
    assert not arc.exact([[0, 1], [1, 1]], want)
    assert arc.cell_accuracy([[0, 1], [1, 1]], want) == 0.75
    assert arc.cell_accuracy([[0, 1, 0]], want) == 0.0


def test_task_prompt_has_the_examples_and_an_open_output():
    task = {
        "train": [
            {"input": [[0]], "output": [[1]]},
            {"input": [[1]], "output": [[0]]},
        ],
        "test": [{"input": [[0]]}],
    }
    text = arc.task_prompt(task, pairs=1)
    assert "Example 1: input 1x1:0 -> output 1x1:1" in text
    assert "Example 2" not in text
    assert text.endswith("Test: input 1x1:0 -> output")


class _Chars:
    def encode(self, s):
        return [0] * len(s)


def test_fits_drops_examples_until_the_context_fits():
    task = {
        "train": [{"input": [[0] * 5] * 5, "output": [[1] * 5] * 5}] * 3,
        "test": [{"input": [[0] * 5] * 5}],
    }
    prompt, used = arc.fits(task, _Chars(), context=260, max_output=40)
    assert prompt is not None
    assert used == 0
    assert len(prompt) + 40 <= 260


def test_summary_counts_exact_and_second_attempts():
    rows = [
        {"exact": True, "exact2": True, "parsed": True, "cell_accuracy": 1.0},
        {"exact": False, "exact2": True, "parsed": True, "cell_accuracy": 0.5},
        {"exact": False, "exact2": False, "parsed": False, "cell_accuracy": 0.0},
    ]
    s = arc.summary(rows)
    assert s["tasks"] == 3 and s["solved"] == 1
    assert s["pass@1"] == 1 / 3 and s["pass@2"] == 2 / 3
    assert s["format_rate"] == 2 / 3
    assert s["cell_accuracy"] == 0.5


def test_tasks_loads_from_a_checkout(tmp_path):
    for split in ("training", "evaluation"):
        d = tmp_path / "data" / split
        d.mkdir(parents=True)
        (d / "a.json").write_text(json.dumps({"train": [], "test": [{"input": [[0]], "output": [[1]]}]}))
    got = arc.tasks("evaluation", base=tmp_path)
    assert len(got) == 1 and got[0]["id"] == "a"
    assert arc.count("training", base=tmp_path) == 1


def test_answer_text_reads_only_what_follows_the_thinking():
    # a grid quoted while thinking is not the answer; the one after </think> is
    text = "<think>the first row is 2x2:99/99, so...</think>\n1x1:7"
    assert arc.parse_grid(arc.answer_text(text)) == ([[7]], True)
    assert arc.answer_text("1x1:7") == "1x1:7"  # no thinking: the whole text


def test_answer_text_is_none_when_the_thinking_never_ended():
    # cut off at the token cap mid-thought: no answer, not a wrong grid
    assert arc.answer_text("<think>the output is 2x2:01/10 because") is None
    # a template that opens the thinking in the prompt: the output has no opening tag
    assert arc.answer_text("the output is 2x2:01/10 because", opened=True) is None
    assert arc.answer_text("so it flips.</think>1x1:7", opened=True) == "1x1:7"
    assert arc.answer_text("", opened=True) is None


def test_a_thinking_reading_has_its_own_name_and_the_same_model():
    from thorp.viable.s4_intelligence import readings

    assert arc.reading_name("org/m") == "arc-org/m" == arc.reading_name("org/m", "off")
    assert arc.reading_name("org/m", "on") == "arc-org/m@thinking"
    assert readings.kind_of("arc-org/m@thinking") == ("arc", "org/m") == readings.kind_of("arc-org/m")


def test_the_board_lists_both_readings_and_keeps_the_better_for_the_model(monkeypatch):
    from thorp import arc_scores
    from thorp.viable.s4_intelligence import readings

    stored = [
        ("arc-org/m", {"pass@2": 0.0, "tasks": 5, "pilot": True, "thinking": "off", "format_rate": 1.0}),
        ("arc-org/m@thinking", {"pass@2": 0.2, "tasks": 5, "pilot": True, "thinking": "on",
                                "max_output": 512, "max_thinking": 4096, "thinking_unfinished": 2}),
    ]
    monkeypatch.setattr(readings, "glob", lambda pattern: stored)
    rows = arc_scores.measured_rows()
    assert [(r["model"], r["thinking"], r["score"]) for r in rows] == [("org/m", "on", 20.0), ("org/m", "off", 0.0)]
    assert rows[0]["source"] == "our reading, 5-task pilot, 512-token cap, 4096 to think"
    assert rows[0]["thinking_unfinished"] == 2
    assert arc_scores.measured()["org/m"]["thinking"] == "on"
