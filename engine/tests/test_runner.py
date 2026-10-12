"""Tests for the runner: episode packaging, the validate checks, the CLI.

These run against the throwaway fixture task so they stay fast. The real nine
tasks are checked by `python -m agentgym.runner validate`, which is the Phase 2
gate, and by test_agents.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentgym.agents.scripted import NoOpAgent, build_scripted_agent
from agentgym.env import CodingEnv
from agentgym.episode import run_episode
from agentgym.runner import main
from agentgym.validate import validate_task
from agentgym.tasks import load_task

# --- run_episode -------------------------------------------------------------


def test_run_episode_produces_a_complete_record(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        record = run_episode(env, NoOpAgent(), task_id, trial=3)

    assert record.task_id == task_id
    assert record.agent_name == "noop"
    assert record.model is None
    assert record.trial == 3
    assert record.outcome == "no_change"
    assert 0.0 <= record.reward <= 1.0
    assert record.tests_total == 2
    assert record.steps_used == 1
    assert len(record.steps) == 1
    assert record.started_at <= record.finished_at
    # A uuid4 string, so two episodes never collide in the database.
    assert len(record.id) == 36


def test_run_episode_with_the_oracle_scores_full_marks(make_task) -> None:
    tasks_root, task_id = make_task()
    task = load_task(task_id, tasks_root)
    with CodingEnv(tasks_root) as env:
        record = run_episode(env, build_scripted_agent("oracle", task), task_id)
    assert record.reward == 1.0
    assert record.outcome == "solved"


def test_run_episode_records_the_model_for_llm_style_agents(make_task) -> None:
    class FakeLLM:
        name = "llm"
        model = "claude-sonnet-5-5"

        def start(self, task_description: str, file_list: list[str]) -> None:
            return None

        def next_action(self, last_observation: str) -> dict:
            return {"type": "submit"}

    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        record = run_episode(env, FakeLLM(), task_id)
    assert record.model == "claude-sonnet-5-5"


def test_run_episode_terminates_an_agent_that_never_submits(make_task) -> None:
    """The step limit is what guarantees the loop ends."""

    class StubbornAgent:
        name = "stubborn"
        model = None

        def start(self, task_description: str, file_list: list[str]) -> None:
            return None

        def next_action(self, last_observation: str) -> dict:
            return {"type": "list_files"}

    tasks_root, task_id = make_task(max_steps=4)
    with CodingEnv(tasks_root) as env:
        record = run_episode(env, StubbornAgent(), task_id)

    assert record.steps_used == 4
    assert record.outcome == "out_of_steps"


def test_run_episode_survives_an_agent_that_raises(make_task) -> None:
    class BrokenAgent:
        name = "broken"
        model = None

        def start(self, task_description: str, file_list: list[str]) -> None:
            return None

        def next_action(self, last_observation: str) -> dict:
            raise ValueError("no idea what to do")

    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        record = run_episode(env, BrokenAgent(), task_id)

    # Graded and kept rather than lost to a stack trace.
    assert record.tests_total == 2
    assert record.steps_used == 1


# --- validate_task -----------------------------------------------------------


def test_validate_passes_on_a_sound_task(make_task) -> None:
    tasks_root, task_id = make_task()
    checks = validate_task(task_id, tasks_root)
    assert checks["visible_fail_on_buggy"] is True
    assert checks["visible_pass_with_solution"] is True
    assert checks["hidden_count_matches"] is True
    assert checks["buggy_reward_below_one"] is True
    assert checks["solution_reward_is_one"] is True


def test_validate_notices_a_task_that_is_not_broken(make_task) -> None:
    """A task whose visible tests already pass measures nothing."""
    tasks_root, task_id = make_task()
    (tasks_root / task_id / "repo" / "src" / "code.py").write_text(
        "def answer():\n    return 2\n", encoding="utf-8"
    )
    checks = validate_task(task_id, tasks_root)
    assert checks["visible_fail_on_buggy"] is False
    assert checks["buggy_reward_below_one"] is False


def test_validate_notices_a_solution_that_does_not_fix_anything(make_task) -> None:
    tasks_root, task_id = make_task()
    (tasks_root / task_id / "solution" / "src" / "code.py").write_text(
        "def answer():\n    return 99\n", encoding="utf-8"
    )
    checks = validate_task(task_id, tasks_root)
    assert checks["visible_pass_with_solution"] is False
    assert checks["solution_reward_is_one"] is False


def test_validate_notices_a_wrong_hidden_test_count(make_task) -> None:
    tasks_root, task_id = make_task(hidden_test_count=7)
    checks = validate_task(task_id, tasks_root)
    assert checks["hidden_count_matches"] is False
    assert checks["_observed_count"] == 2
    assert checks["_expected_count"] == 7


# --- the CLI -----------------------------------------------------------------


def test_validate_command_exits_zero_on_a_sound_task(make_task, capsys) -> None:
    tasks_root, task_id = make_task()
    code = main(["validate", "--tasks", task_id, "--tasks-root", str(tasks_root)])
    assert code == 0
    assert "All checks passed" in capsys.readouterr().out


def test_validate_command_exits_nonzero_on_a_broken_task(make_task, capsys) -> None:
    """A non-zero exit is what makes this usable in CI."""
    tasks_root, task_id = make_task(hidden_test_count=7)
    code = main(["validate", "--tasks", task_id, "--tasks-root", str(tasks_root)])
    assert code == 1
    assert "FAILED" in capsys.readouterr().out


def test_run_command_writes_one_json_line_per_episode(
    make_task, tmp_path: Path
) -> None:
    tasks_root, task_id = make_task()
    out = tmp_path / "out" / "episodes.jsonl"

    code = main(
        [
            "run",
            "--agent",
            "noop",
            "--tasks",
            task_id,
            "--trials",
            "2",
            "--out",
            str(out),
            "--tasks-root",
            str(tasks_root),
        ]
    )

    assert code == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert [record["trial"] for record in records] == [0, 1]
    # Each episode must be independently identifiable.
    assert records[0]["id"] != records[1]["id"]
    assert records[0]["steps"][0]["action_type"] == "submit"


def test_run_command_creates_the_output_folder(make_task, tmp_path: Path) -> None:
    tasks_root, task_id = make_task()
    out = tmp_path / "deeply" / "nested" / "run.jsonl"
    main(
        [
            "run",
            "--agent",
            "noop",
            "--tasks",
            task_id,
            "--out",
            str(out),
            "--tasks-root",
            str(tasks_root),
        ]
    )
    assert out.is_file()


def test_run_command_rejects_an_unknown_task_id(make_task, tmp_path: Path) -> None:
    tasks_root, _ = make_task()
    with pytest.raises(ValueError, match="unknown task id"):
        main(
            [
                "run",
                "--agent",
                "noop",
                "--tasks",
                "does_not_exist",
                "--out",
                str(tmp_path / "x.jsonl"),
                "--tasks-root",
                str(tasks_root),
            ]
        )


def test_run_command_rejects_an_unknown_agent(make_task, tmp_path: Path) -> None:
    tasks_root, task_id = make_task()
    with pytest.raises(SystemExit):
        main(
            [
                "run",
                "--agent",
                "wizard",
                "--tasks",
                task_id,
                "--out",
                str(tmp_path / "x.jsonl"),
                "--tasks-root",
                str(tasks_root),
            ]
        )
