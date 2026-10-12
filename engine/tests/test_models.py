"""Tests for the data containers: action parsing, truncation, serialisation."""

from __future__ import annotations

import json

import pytest

from agentgym.models import (
    ACTION_TYPES,
    MAX_RECORD_CHARS,
    Action,
    EpisodeRecord,
    StepRecord,
    tail,
    truncate,
    utc_now_iso,
)


# --- truncation --------------------------------------------------------------


def test_short_text_is_untouched() -> None:
    assert truncate("hello", 10) == "hello"


def test_text_at_the_limit_is_untouched() -> None:
    assert truncate("12345", 5) == "12345"


def test_long_text_is_cut_and_says_so() -> None:
    result = truncate("x" * 50, 10)
    assert result.startswith("x" * 10)
    assert "truncated" in result
    assert "40 more characters" in result


def test_tail_keeps_the_end_not_the_beginning() -> None:
    """Test output is most useful at the end, where the failure summary is."""
    result = tail("abcdefghij", 3)
    assert result.endswith("hij")
    assert "truncated" in result


def test_tail_of_short_text_is_untouched() -> None:
    assert tail("abc", 10) == "abc"


def test_utc_now_is_iso_with_an_offset() -> None:
    stamp = utc_now_iso()
    assert "T" in stamp
    assert stamp.endswith("+00:00")


# --- action parsing ----------------------------------------------------------


@pytest.mark.parametrize("action_type", ["list_files", "run_tests", "submit"])
def test_actions_without_arguments_parse(action_type: str) -> None:
    action = Action.parse({"type": action_type})
    assert action.type == action_type
    assert action.path is None


def test_read_file_parses_its_path() -> None:
    action = Action.parse({"type": "read_file", "path": "src/a.py"})
    assert action.path == "src/a.py"


def test_write_file_parses_path_and_content() -> None:
    action = Action.parse({"type": "write_file", "path": "src/a.py", "content": "x = 1"})
    assert action.path == "src/a.py"
    assert action.content == "x = 1"


def test_write_file_accepts_empty_content() -> None:
    """Emptying a file is a legitimate edit, so "" must not look like missing."""
    action = Action.parse({"type": "write_file", "path": "src/a.py", "content": ""})
    assert action.content == ""


def test_extra_fields_are_ignored() -> None:
    # Models sometimes add commentary fields; ignoring them is kinder than
    # failing the step.
    action = Action.parse({"type": "submit", "reason": "I am confident"})
    assert action.type == "submit"


def test_unknown_type_names_the_valid_types() -> None:
    with pytest.raises(ValueError) as info:
        Action.parse({"type": "teleport"})
    message = str(info.value)
    for valid in ACTION_TYPES:
        assert valid in message


@pytest.mark.parametrize("raw", [None, "submit", 42, ["submit"]])
def test_non_dict_actions_are_rejected(raw: object) -> None:
    with pytest.raises(ValueError, match="JSON object"):
        Action.parse(raw)


def test_missing_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="'type'"):
        Action.parse({"path": "src/a.py"})


def test_write_without_content_is_rejected() -> None:
    with pytest.raises(ValueError, match="content"):
        Action.parse({"type": "write_file", "path": "src/a.py"})


@pytest.mark.parametrize("bad_path", ["", "   ", None, 7])
def test_read_without_a_usable_path_is_rejected(bad_path: object) -> None:
    with pytest.raises(ValueError, match="path"):
        Action.parse({"type": "read_file", "path": bad_path})


def test_action_to_dict_truncates_content() -> None:
    action = Action.parse(
        {"type": "write_file", "path": "a.txt", "content": "y" * (MAX_RECORD_CHARS + 100)}
    )
    payload = action.to_dict()
    assert "truncated" in payload["content"]
    assert len(payload["content"]) < MAX_RECORD_CHARS + 100


def test_action_to_dict_omits_unused_fields() -> None:
    assert Action.parse({"type": "submit"}).to_dict() == {"type": "submit"}


# --- records -----------------------------------------------------------------


def _step(index: int = 0, observation: str = "ok") -> StepRecord:
    return StepRecord(
        index=index,
        action_type="list_files",
        action={"type": "list_files"},
        observation=observation,
        reward=0.0,
        error=False,
        tamper_blocked=False,
        created_at=utc_now_iso(),
    )


def test_step_record_truncates_its_observation() -> None:
    payload = _step(observation="z" * (MAX_RECORD_CHARS + 500)).to_dict()
    assert "truncated" in payload["observation"]


def test_episode_record_round_trips_through_json() -> None:
    record = EpisodeRecord(
        id="abc",
        task_id="01_moving_average",
        agent_name="llm",
        model="claude-sonnet-5-5",
        trial=0,
        reward=0.75,
        outcome="partial",
        steps_used=2,
        tamper_attempts=0,
        tests_passed=6,
        tests_total=8,
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        steps=[_step(0), _step(1)],
    )
    parsed = json.loads(record.to_jsonl())
    assert parsed["id"] == "abc"
    assert parsed["model"] == "claude-sonnet-5-5"
    assert parsed["reward"] == 0.75
    assert len(parsed["steps"]) == 2
    assert parsed["steps"][1]["index"] == 1


def test_episode_jsonl_is_a_single_line() -> None:
    """The run file is JSONL, so one episode must never span two lines."""
    record = EpisodeRecord(
        id="abc",
        task_id="t",
        agent_name="noop",
        model=None,
        trial=0,
        reward=0.0,
        outcome="no_change",
        steps_used=1,
        tamper_attempts=0,
        tests_passed=0,
        tests_total=2,
        started_at=utc_now_iso(),
        finished_at=utc_now_iso(),
        steps=[_step(0, observation="line one\nline two")],
    )
    assert "\n" not in record.to_jsonl()
