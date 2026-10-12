"""`CodingEnv`: the gym itself.

An **environment** is the world an agent acts in. Like the classic RL
environments (CartPole and friends) it has exactly two methods:

* `reset(task_id)` — start a fresh **episode**: copy a buggy mini-project into a
  throwaway workspace and hand back the task description plus the file list.
* `step(action)` — apply one action and return `(observation, reward, done, info)`.

An **episode** is one attempt at one task. A **trajectory** is the list of steps
in it. **Reward** is 0.0 on every step except the last; the final reward is the
fraction of *hidden* tests that pass. The agent never sees the hidden tests, so
the only way to score is to actually fix the bug.
"""

from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentgym import sandbox
from agentgym.guard import check_write, list_workspace_files
from agentgym.models import (
    MAX_READ_CHARS,
    MAX_TEST_OUTPUT_CHARS,
    Action,
    StepRecord,
    StepResult,
    Task,
    tail,
    truncate,
    utc_now_iso,
)
from agentgym.tasks import load_task

# The engine owns the workspace pytest config. The guard refuses to let an agent
# write a file with this name, so the agent can read it but never change it.
ENGINE_PYTEST_INI = "[pytest]\npythonpath = .\ntestpaths = tests\n"


@dataclass
class Reset:
    """What `reset()` hands back, ready to pass to `agent.start()`."""

    task: Task
    file_list: list[str]
    observation: str


def classify_outcome(
    *,
    reward: float,
    had_error: bool,
    timed_out: bool,
    out_of_steps: bool,
    wrote_any_file: bool,
) -> str:
    """Put an episode in one bucket, most-specific problem first.

    The order matters: a timeout that happens to score 0.0 is reported as a
    timeout, not as `wrong_fix`, because the useful signal is *why* it failed.
    """
    if had_error:
        return "error"
    if timed_out:
        return "timeout"
    if reward >= 1.0:
        return "solved"
    if out_of_steps:
        return "out_of_steps"
    if not wrote_any_file:
        return "no_change"
    if reward > 0.0:
        return "partial"
    return "wrong_fix"


@dataclass
class _Grade:
    """Result of running the hidden tests."""

    reward: float
    tests_passed: int
    tests_total: int
    timed_out: bool
    had_error: bool
    detail: str
    # How many tests the report actually contained. Usually equal to
    # tests_total, but they differ when the count check below fails, and
    # `validate` needs the real number to tell you what went wrong.
    observed_test_count: int = 0


class CodingEnv:
    """One environment instance. Reusable: call `reset()` again for a new episode."""

    def __init__(self, tasks_root: Path | None = None) -> None:
        self._tasks_root = tasks_root
        self.task: Task | None = None
        self.workspace: Path | None = None
        self.done = False
        self.step_index = 0
        self.tamper_attempts = 0
        self.files_written = 0
        self.steps: list[StepRecord] = []
        self._temp_dirs: list[Path] = []
        self._final_info: dict[str, Any] = {}

    # --- lifecycle -----------------------------------------------------------

    def reset(self, task_id: str) -> Reset:
        """Begin a new episode on `task_id`."""
        self.close()  # throw away any previous workspace

        task = load_task(task_id, self._tasks_root)
        workspace = Path(tempfile.mkdtemp(prefix=f"agentgym-{task_id}-"))
        self._temp_dirs.append(workspace)

        # symlinks=False copies what links point at rather than the links
        # themselves, so the workspace cannot reach outside itself.
        shutil.copytree(
            task.repo_dir,
            workspace,
            dirs_exist_ok=True,
            symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        (workspace / "pytest.ini").write_text(ENGINE_PYTEST_INI, encoding="utf-8")

        self.task = task
        self.workspace = workspace
        self.done = False
        self.step_index = 0
        self.tamper_attempts = 0
        self.files_written = 0
        self.steps = []
        self._final_info = {}

        file_list = list_workspace_files(workspace)
        observation = (
            f"Task: {task.title}\n\n{task.description}\n\n"
            f"Files:\n" + "\n".join(f"  {name}" for name in file_list) + "\n\n"
            f"You have {task.max_steps} steps. Fix the bug, then submit."
        )
        return Reset(task=task, file_list=file_list, observation=observation)

    def close(self) -> None:
        """Delete every workspace this env created."""
        for directory in self._temp_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        self._temp_dirs = []
        self.workspace = None

    def __enter__(self) -> "CodingEnv":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # --- the step loop -------------------------------------------------------

    def step(self, raw_action: Any) -> StepResult:
        """Apply one action. Never raises on bad agent input, only on misuse."""
        if self.task is None or self.workspace is None:
            raise RuntimeError("call reset() before step()")
        if self.done:
            raise RuntimeError(
                "this episode is already finished; call reset() to start a new one"
            )

        index = self.step_index
        self.step_index += 1

        is_error = False
        tamper_blocked = False
        reward = 0.0
        done = False
        info: dict[str, Any] = {}

        # A malformed action is feedback, not a crash: the agent gets told what
        # was wrong and spends a step learning it.
        try:
            action = Action.parse(raw_action)
        except ValueError as exc:
            observation = f"ERROR: {exc}"
            self._record(index, "invalid", {"raw": truncate(repr(raw_action))},
                         observation, 0.0, True, False)
            return StepResult(observation, 0.0, False,
                              {"error": True, "tamper_blocked": False,
                               "step_index": index})

        if action.type == "list_files":
            names = list_workspace_files(self.workspace)
            observation = "\n".join(names) if names else "(workspace is empty)"

        elif action.type == "read_file":
            observation, is_error = self._read_file(action.path or "")

        elif action.type == "write_file":
            observation, is_error, tamper_blocked = self._write_file(
                action.path or "", action.content or ""
            )

        elif action.type == "run_tests":
            observation = self._run_visible_tests()

        else:  # submit
            observation, reward, info = self._finish(out_of_steps=False)
            done = True

        # Out of steps: grade what we have rather than ending with no score.
        if not done and self.step_index >= self.task.max_steps:
            final_observation, reward, info = self._finish(out_of_steps=True)
            observation = (
                f"{observation}\n\n[agentgym] Step limit reached, submitting "
                f"automatically.\n{final_observation}"
            )
            done = True

        info.update(
            {
                "error": is_error,
                "tamper_blocked": tamper_blocked,
                "step_index": index,
            }
        )
        self._record(index, action.type, action.to_dict(), observation, reward,
                     is_error, tamper_blocked)
        if done:
            self.done = True
        return StepResult(observation, reward, done, info)

    # --- individual actions --------------------------------------------------

    def _read_file(self, raw_path: str) -> tuple[str, bool]:
        """Read a file, refusing to look outside the workspace."""
        assert self.workspace is not None
        # Reuse the guard's path analysis with empty content: the path checks
        # (absolute, "..", escaping the workspace) are exactly what we need, and
        # reading tests/ is allowed, so we only reject real escapes.
        verdict = check_write(self.workspace, raw_path, "")
        candidate = (self.workspace / raw_path.replace("\\", "/")).resolve()
        if not verdict.allowed and not candidate.is_relative_to(
            self.workspace.resolve()
        ):
            return f"ERROR: cannot read {raw_path!r}: {verdict.reason}", True

        if not candidate.is_file():
            available = ", ".join(list_workspace_files(self.workspace))
            return (
                f"ERROR: no such file {raw_path!r}. Files here: {available}",
                True,
            )

        text = candidate.read_text(encoding="utf-8", errors="replace")
        return truncate(text, MAX_READ_CHARS), False

    def _write_file(self, raw_path: str, content: str) -> tuple[str, bool, bool]:
        """Write a file if the guard allows it. Returns (obs, error, tampered)."""
        assert self.workspace is not None
        verdict = check_write(self.workspace, raw_path, content)
        if not verdict.allowed:
            self.tamper_attempts += 1
            return (
                f"BLOCKED: refusing to write {raw_path!r} because "
                f"{verdict.reason}. This counted as a step and was recorded as a "
                f"tamper attempt.",
                False,  # a blocked write is not an "error", it is a refusal
                True,
            )

        target = verdict.resolved_path
        assert target is not None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        self.files_written += 1
        line_count = content.count("\n") + 1
        return f"Wrote {raw_path} ({len(content)} characters, {line_count} lines).", False, False

    def _run_visible_tests(self) -> str:
        """Run the tests the agent can see, and show it the tail of the output."""
        assert self.workspace is not None
        result = sandbox.run_pytest(
            self.workspace, timeout_seconds=sandbox.DEFAULT_TIMEOUT_SECONDS
        )
        status = "TIMED OUT" if result.timed_out else (
            "all visible tests passed" if result.returncode == 0 else "some tests failed"
        )
        return (
            f"[visible tests: {status} in {result.duration_seconds}s]\n\n"
            f"{tail(result.output, MAX_TEST_OUTPUT_CHARS)}"
        )

    # --- grading -------------------------------------------------------------

    def _finish(self, *, out_of_steps: bool) -> tuple[str, float, dict[str, Any]]:
        """Grade the episode with the hidden tests and build the final info."""
        assert self.task is not None and self.workspace is not None

        visible_modified = self._visible_tests_modified()
        grade = self._grade()

        outcome = classify_outcome(
            reward=grade.reward,
            had_error=grade.had_error,
            timed_out=grade.timed_out,
            out_of_steps=out_of_steps,
            wrote_any_file=self.files_written > 0,
        )

        info = {
            "tests_passed": grade.tests_passed,
            "tests_total": grade.tests_total,
            "outcome": outcome,
            "observed_test_count": grade.observed_test_count,
            # Informational only: the guard should have made this impossible.
            "visible_tests_modified": visible_modified,
        }
        self._final_info = info

        observation = (
            f"[graded with {grade.tests_total} hidden tests]\n"
            f"passed {grade.tests_passed}/{grade.tests_total}  "
            f"reward {grade.reward:.3f}  outcome {outcome}\n"
            f"{grade.detail}"
        )
        return observation, grade.reward, info

    def _visible_tests_modified(self) -> bool:
        """Did the workspace's visible tests drift from the originals?"""
        assert self.task is not None and self.workspace is not None
        original_dir = self.task.repo_dir / "tests"
        current_dir = self.workspace / "tests"
        if not original_dir.is_dir():
            return False
        for original in sorted(original_dir.rglob("*")):
            if not original.is_file():
                continue
            current = current_dir / original.relative_to(original_dir)
            if not current.is_file():
                return True
            if current.read_bytes() != original.read_bytes():
                return True
        return False

    def _grade(self) -> _Grade:
        """Run the hidden tests against a copy of the agent's workspace.

        We grade in a *separate* directory so the hidden tests never exist in a
        place the agent could have read, and we write the JUnit report outside
        that directory so agent code cannot edit its own grade.
        """
        assert self.task is not None and self.workspace is not None

        grade_root = Path(tempfile.mkdtemp(prefix="agentgym-grade-"))
        self._temp_dirs.append(grade_root)
        grade_dir = grade_root / "work"
        report_path = grade_root / "report.xml"  # outside grade_dir on purpose

        shutil.copytree(
            self.workspace,
            grade_dir,
            symlinks=False,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.rmtree(grade_dir / "tests", ignore_errors=True)
        shutil.copytree(self.task.hidden_tests_dir, grade_dir / "tests", symlinks=False)
        (grade_dir / "pytest.ini").write_text(ENGINE_PYTEST_INI, encoding="utf-8")

        result = sandbox.run_pytest(
            grade_dir,
            extra_args=(f"--junitxml={report_path}",),
            timeout_seconds=sandbox.GRADING_TIMEOUT_SECONDS,
        )

        counts = _parse_junit(report_path)
        expected = self.task.hidden_test_count

        if counts is None:
            return _Grade(
                0.0, 0, expected, result.timed_out, True,
                "Could not read a test report: the hidden tests failed to run "
                "at all (usually an import error or a crash in the source). "
                f"reward 0.0.\n\n{result.output}",
                observed_test_count=0,
            )

        total, failures, errors, skipped = counts
        if total != expected:
            # A collection error can report "1 test, 1 error" and look like a
            # partial pass. Refusing to score it keeps a broken import honest.
            return _Grade(
                0.0, 0, expected, result.timed_out, True,
                f"Expected {expected} hidden tests but the report had {total}. "
                f"Treating this as an error with reward 0.0.\n\n{result.output}",
                observed_test_count=total,
            )

        passed = max(0, total - failures - errors - skipped)
        reward = passed / total if total else 0.0
        detail = "" if reward >= 1.0 else f"\n{tail(result.output, MAX_TEST_OUTPUT_CHARS)}"
        return _Grade(
            reward, passed, total, result.timed_out, False, detail,
            observed_test_count=total,
        )

    # --- bookkeeping ---------------------------------------------------------

    def _record(
        self,
        index: int,
        action_type: str,
        action: dict[str, Any],
        observation: str,
        reward: float,
        error: bool,
        tamper_blocked: bool,
    ) -> None:
        self.steps.append(
            StepRecord(
                index=index,
                action_type=action_type,
                action=action,
                observation=observation,
                reward=reward,
                error=error,
                tamper_blocked=tamper_blocked,
                created_at=utc_now_iso(),
            )
        )

    @property
    def final_info(self) -> dict[str, Any]:
        """Grading details, available once the episode is done."""
        return dict(self._final_info)


def _parse_junit(report_path: Path) -> tuple[int, int, int, int] | None:
    """Read (tests, failures, errors, skipped) out of a JUnit XML report.

    Returns None when the file is missing or unreadable, which means pytest did
    not get far enough to produce one.
    """
    if not report_path.is_file():
        return None
    try:
        root = ElementTree.parse(report_path).getroot()
    except ElementTree.ParseError:
        return None

    # pytest writes <testsuites><testsuite/></testsuites>; older tools write a
    # bare <testsuite>. Handle both, summing in case there are several suites.
    suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
    if not suites:
        return None

    totals = [0, 0, 0, 0]
    for suite in suites:
        for position, attribute in enumerate(("tests", "failures", "errors", "skipped")):
            totals[position] += int(suite.get(attribute, 0) or 0)
    return totals[0], totals[1], totals[2], totals[3]
