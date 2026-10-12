"""Tests for the environment: actions, grading, outcomes and step limits."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentgym.env import CodingEnv, classify_outcome
from agentgym.models import MAX_READ_CHARS

# --- outcome classification (pure, so these are instant) ---------------------


def test_error_beats_everything() -> None:
    assert (
        classify_outcome(
            reward=1.0,
            had_error=True,
            timed_out=True,
            out_of_steps=True,
            wrote_any_file=True,
        )
        == "error"
    )


def test_timeout_beats_a_zero_score() -> None:
    assert (
        classify_outcome(
            reward=0.0,
            had_error=False,
            timed_out=True,
            out_of_steps=False,
            wrote_any_file=True,
        )
        == "timeout"
    )


def test_full_reward_is_solved_even_at_the_step_limit() -> None:
    assert (
        classify_outcome(
            reward=1.0,
            had_error=False,
            timed_out=False,
            out_of_steps=True,
            wrote_any_file=True,
        )
        == "solved"
    )


def test_out_of_steps_beats_partial() -> None:
    assert (
        classify_outcome(
            reward=0.5,
            had_error=False,
            timed_out=False,
            out_of_steps=True,
            wrote_any_file=True,
        )
        == "out_of_steps"
    )


def test_no_change_when_nothing_was_written() -> None:
    assert (
        classify_outcome(
            reward=0.5,
            had_error=False,
            timed_out=False,
            out_of_steps=False,
            wrote_any_file=False,
        )
        == "no_change"
    )


def test_partial_when_some_hidden_tests_pass() -> None:
    assert (
        classify_outcome(
            reward=0.5,
            had_error=False,
            timed_out=False,
            out_of_steps=False,
            wrote_any_file=True,
        )
        == "partial"
    )


def test_wrong_fix_when_files_changed_but_nothing_passes() -> None:
    assert (
        classify_outcome(
            reward=0.0,
            had_error=False,
            timed_out=False,
            out_of_steps=False,
            wrote_any_file=True,
        )
        == "wrong_fix"
    )


# --- reset -------------------------------------------------------------------


def test_reset_gives_the_task_and_the_file_list(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        reset = env.reset(task_id)
        assert reset.task.id == task_id
        assert "src/code.py" in reset.file_list
        assert "tests/test_visible.py" in reset.file_list
        assert reset.task.description in reset.observation


def test_reset_writes_an_engine_owned_pytest_ini(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        assert env.workspace is not None
        assert (env.workspace / "pytest.ini").is_file()


def test_hidden_tests_are_never_in_the_workspace(make_task) -> None:
    """If the agent could read the grading tests, the reward would mean nothing."""
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        reset = env.reset(task_id)
        assert not any("hidden" in name for name in reset.file_list)


def test_reset_twice_gives_a_clean_workspace(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step({"type": "write_file", "path": "src/code.py", "content": "x = 1\n"})
        env.reset(task_id)
        result = env.step({"type": "read_file", "path": "src/code.py"})
        assert "def answer()" in result.observation


def test_close_removes_the_workspace(make_task) -> None:
    tasks_root, task_id = make_task()
    env = CodingEnv(tasks_root)
    env.reset(task_id)
    workspace = env.workspace
    assert workspace is not None and workspace.is_dir()
    env.close()
    assert not workspace.is_dir()


# --- individual actions ------------------------------------------------------


def test_step_before_reset_raises(make_task) -> None:
    env = CodingEnv()
    with pytest.raises(RuntimeError, match="reset"):
        env.step({"type": "list_files"})


def test_list_files_action(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "list_files"})
        assert "src/code.py" in result.observation
        assert result.reward == 0.0
        assert not result.done


def test_read_file_returns_the_source(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "read_file", "path": "src/code.py"})
        assert "return 1" in result.observation
        assert result.info["error"] is False


def test_read_file_can_read_the_visible_tests(make_task) -> None:
    # Reading tests is fine; only *writing* them is blocked.
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "read_file", "path": "tests/test_visible.py"})
        assert "test_answer_is_two" in result.observation
        assert result.info["error"] is False


def test_read_missing_file_is_an_error_not_an_exception(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "read_file", "path": "src/nope.py"})
        assert result.info["error"] is True
        assert "no such file" in result.observation.lower()
        assert not result.done


def test_read_outside_the_workspace_is_an_error(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "read_file", "path": "../../../etc/passwd"})
        assert result.info["error"] is True


def test_read_file_is_truncated(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        assert env.workspace is not None
        big = "# " + ("x" * (MAX_READ_CHARS + 500)) + "\n"
        (env.workspace / "big.txt").write_text(big, encoding="utf-8")
        result = env.step({"type": "read_file", "path": "big.txt"})
        assert "truncated" in result.observation
        assert len(result.observation) < MAX_READ_CHARS + 200


def test_write_file_then_read_it_back(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        write = env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 2\n"}
        )
        assert write.info["tamper_blocked"] is False
        assert env.files_written == 1
        read = env.step({"type": "read_file", "path": "src/code.py"})
        assert "return 2" in read.observation


def test_write_creates_missing_parent_folders(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step(
            {"type": "write_file", "path": "src/deep/new.py", "content": "x = 1\n"}
        )
        assert result.info["tamper_blocked"] is False
        listing = env.step({"type": "list_files"})
        assert "src/deep/new.py" in listing.observation


def test_blocked_write_counts_as_a_tamper_attempt(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step(
            {"type": "write_file", "path": "tests/test_visible.py", "content": "assert True"}
        )
        assert result.info["tamper_blocked"] is True
        # A refusal is not an "error": the action was well formed, just denied.
        assert result.info["error"] is False
        assert env.tamper_attempts == 1
        assert env.files_written == 0
        # The step still counted, so cheating costs the agent a turn.
        assert env.step_index == 1


def test_blocked_write_does_not_change_the_file(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        assert env.workspace is not None
        before = (env.workspace / "tests" / "test_visible.py").read_text(
            encoding="utf-8"
        )
        env.step(
            {"type": "write_file", "path": "tests/test_visible.py", "content": "assert True"}
        )
        after = (env.workspace / "tests" / "test_visible.py").read_text(
            encoding="utf-8"
        )
        assert before == after


def test_agent_cannot_replace_the_engine_pytest_ini(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        assert env.workspace is not None
        before = (env.workspace / "pytest.ini").read_text(encoding="utf-8")
        result = env.step(
            {"type": "write_file", "path": "pytest.ini", "content": "[pytest]\n"}
        )
        assert result.info["tamper_blocked"] is True
        assert (env.workspace / "pytest.ini").read_text(encoding="utf-8") == before


def test_run_tests_reports_a_failure_on_the_buggy_code(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "run_tests"})
        assert "visible tests" in result.observation
        assert "failed" in result.observation


def test_run_tests_reports_success_after_a_real_fix(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 2\n"}
        )
        result = env.step({"type": "run_tests"})
        assert "all visible tests passed" in result.observation


# --- malformed actions -------------------------------------------------------


@pytest.mark.parametrize(
    "bad_action",
    [
        {"type": "teleport"},
        {"type": 42},
        {},
        {"type": "read_file"},
        {"type": "read_file", "path": ""},
        {"type": "write_file", "path": "src/x.py"},
        {"type": "write_file", "content": "x = 1"},
        "submit",
        None,
        ["submit"],
    ],
)
def test_malformed_actions_become_error_observations(make_task, bad_action) -> None:
    """A confused agent should get feedback, not crash the episode."""
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step(bad_action)
        assert result.info["error"] is True
        assert result.observation.startswith("ERROR")
        assert not result.done
        # It still costs a step, so an agent cannot probe for free.
        assert env.step_index == 1
        assert len(env.steps) == 1


def test_unknown_action_lists_the_valid_ones(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "teleport"})
        assert "submit" in result.observation


# --- submitting and grading --------------------------------------------------


def test_submit_on_buggy_code_scores_partially(make_task) -> None:
    """The fixture's buggy `answer()` returns an int but the wrong one, so one
    of its two hidden tests passes."""
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "submit"})
        assert result.done is True
        assert result.reward == pytest.approx(0.5)
        assert result.info["tests_passed"] == 1
        assert result.info["tests_total"] == 2
        assert result.info["outcome"] == "no_change"


def test_submit_after_the_real_fix_scores_one(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 2\n"}
        )
        result = env.step({"type": "submit"})
        assert result.reward == 1.0
        assert result.info["outcome"] == "solved"
        assert result.info["tests_passed"] == 2


def test_a_partial_fix_is_labelled_partial(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        # Still an int, still not 2: one hidden test passes, one fails.
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 3\n"}
        )
        result = env.step({"type": "submit"})
        assert result.reward == pytest.approx(0.5)
        assert result.info["outcome"] == "partial"


def test_a_fix_that_passes_nothing_is_labelled_wrong_fix(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 'two'\n"}
        )
        result = env.step({"type": "submit"})
        assert result.reward == 0.0
        assert result.info["outcome"] == "wrong_fix"


def test_broken_source_is_graded_as_an_error_not_a_partial_pass(make_task) -> None:
    """A syntax error makes collection fail, which must not look like progress.

    Without the expected-count check this is the classic way a broken import
    scores 'one test, one error' and gets credited with a partial pass.
    """
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step({"type": "write_file", "path": "src/code.py", "content": "def answer(:\n"})
        result = env.step({"type": "submit"})
        assert result.reward == 0.0
        assert result.info["outcome"] == "error"


def test_wrong_hidden_test_count_is_an_error(make_task) -> None:
    """If task.json lies about the count, refuse to score rather than guess."""
    tasks_root, task_id = make_task(hidden_test_count=99)
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "submit"})
        assert result.reward == 0.0
        assert result.info["outcome"] == "error"
        assert result.info["observed_test_count"] == 2


def test_stepping_after_done_raises(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step({"type": "submit"})
        with pytest.raises(RuntimeError, match="already finished"):
            env.step({"type": "list_files"})


def test_visible_tests_unmodified_is_reported(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        result = env.step({"type": "submit"})
        # The guard makes this impossible; we record it to prove it stayed so.
        assert result.info["visible_tests_modified"] is False


# --- the step limit ----------------------------------------------------------


def test_reaching_the_step_limit_auto_submits(make_task) -> None:
    tasks_root, task_id = make_task(max_steps=3)
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        first = env.step({"type": "list_files"})
        assert not first.done
        second = env.step({"type": "list_files"})
        assert not second.done
        third = env.step({"type": "list_files"})

        assert third.done is True
        assert "Step limit reached" in third.observation
        assert third.info["outcome"] == "out_of_steps"
        assert env.step_index == 3  # never more than max_steps
        assert len(env.steps) == 3


def test_auto_submit_still_grades_the_work(make_task) -> None:
    """Running out of steps after a correct fix must still score it."""
    tasks_root, task_id = make_task(max_steps=2)
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 2\n"}
        )
        result = env.step({"type": "list_files"})
        assert result.done is True
        assert result.reward == 1.0
        # Full marks outranks the step limit in the outcome ordering.
        assert result.info["outcome"] == "solved"


def test_trajectory_records_every_step(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step({"type": "list_files"})
        env.step({"type": "read_file", "path": "src/code.py"})
        env.step({"type": "submit"})

    assert [step.action_type for step in env.steps] == [
        "list_files",
        "read_file",
        "submit",
    ]
    assert [step.index for step in env.steps] == [0, 1, 2]
    # Reward is zero everywhere except the final graded step.
    assert [step.reward for step in env.steps[:-1]] == [0.0, 0.0]
    assert env.steps[-1].reward > 0.0


def test_written_content_is_truncated_in_the_record(make_task) -> None:
    tasks_root, task_id = make_task()
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "notes.txt", "content": "y" * 25_000}
        )
    recorded = env.steps[0].to_dict()["action"]["content"]
    assert "truncated" in recorded
    assert len(recorded) < 21_000


def test_workspace_is_a_copy_so_the_task_folder_is_never_touched(
    make_task,
) -> None:
    tasks_root, task_id = make_task()
    original = Path(tasks_root) / task_id / "repo" / "src" / "code.py"
    before = original.read_text(encoding="utf-8")
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        env.step(
            {"type": "write_file", "path": "src/code.py", "content": "def answer():\n    return 2\n"}
        )
    assert original.read_text(encoding="utf-8") == before
