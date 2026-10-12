"""Tests for the contained pytest runner.

The important one is `test_infinite_loop_is_killed_instead_of_hanging`: without
it, a single bad agent could wedge the whole run forever.
"""

from __future__ import annotations

import time
from pathlib import Path

from agentgym.sandbox import (
    RESOURCE_LIMITS_AVAILABLE,
    SandboxResult,
    run_pytest,
)

PYTEST_INI = "[pytest]\npythonpath = .\ntestpaths = tests\n"


def _make_project(tmp_path: Path, test_source: str) -> Path:
    """A minimal pytest project containing exactly the given test file."""
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_sample.py").write_text(test_source, encoding="utf-8")
    (tmp_path / "pytest.ini").write_text(PYTEST_INI, encoding="utf-8")
    return tmp_path


def test_passing_tests_return_zero(tmp_path: Path) -> None:
    project = _make_project(tmp_path, "def test_ok():\n    assert True\n")
    result = run_pytest(project)
    assert isinstance(result, SandboxResult)
    assert result.returncode == 0
    assert not result.timed_out


def test_failing_tests_return_nonzero(tmp_path: Path) -> None:
    project = _make_project(tmp_path, "def test_bad():\n    assert 1 == 2\n")
    result = run_pytest(project)
    assert result.returncode != 0
    assert not result.timed_out


def test_infinite_loop_is_killed_instead_of_hanging(tmp_path: Path) -> None:
    """A busy loop in agent code must end in a timeout, not a wedged run.

    We assert on elapsed wall-clock time as well as the flag: the point is not
    just that we *notice* the timeout, but that control actually comes back.
    """
    project = _make_project(
        tmp_path, "def test_hang():\n    while True:\n        pass\n"
    )
    timeout_seconds = 5

    started = time.monotonic()
    result = run_pytest(project, timeout_seconds=timeout_seconds)
    elapsed = time.monotonic() - started

    assert result.timed_out is True
    assert "TIMEOUT" in result.output
    # Generous upper bound: the kill plus process reaping takes a moment, but it
    # must be nowhere near forever.
    assert elapsed < timeout_seconds + 20


def test_sleeping_forever_is_killed_too(tmp_path: Path) -> None:
    """A blocked (not busy) test must also time out.

    This is the case POSIX CPU limits would *not* catch, because a sleeping
    process burns no CPU. Only the wall-clock timeout saves us.
    """
    project = _make_project(
        tmp_path,
        "import time\n\n\ndef test_sleep():\n    time.sleep(600)\n",
    )
    result = run_pytest(project, timeout_seconds=5)
    assert result.timed_out is True


def test_secrets_are_not_visible_to_agent_code(
    tmp_path: Path, monkeypatch
) -> None:
    """The child environment must not carry our API key.

    Agent-written code runs inside this subprocess, so anything in `os.environ`
    there is readable by the agent.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-leak")
    monkeypatch.setenv("INGEST_API_KEY", "also-must-not-leak")
    project = _make_project(
        tmp_path,
        "import os\n\n\n"
        "def test_no_secrets():\n"
        "    assert 'ANTHROPIC_API_KEY' not in os.environ\n"
        "    assert 'INGEST_API_KEY' not in os.environ\n",
    )
    result = run_pytest(project)
    assert result.returncode == 0, f"a secret leaked into the sandbox:\n{result.output}"


def test_output_is_truncated_to_the_limit(tmp_path: Path) -> None:
    project = _make_project(
        tmp_path,
        "def test_noisy():\n"
        "    for _ in range(2000):\n"
        "        print('noise ' * 20)\n"
        "    assert False\n",
    )
    result = run_pytest(project, output_limit=1_000)
    # The limit plus the short "earlier characters" notice the tail adds.
    assert len(result.output) < 1_200
    assert "truncated" in result.output


def test_bytecode_is_not_written_into_the_workspace(tmp_path: Path) -> None:
    """`__pycache__` would otherwise show up in the agent's file listing."""
    project = _make_project(tmp_path, "def test_ok():\n    assert True\n")
    (project / "src").mkdir()
    (project / "src" / "code.py").write_text("x = 1\n", encoding="utf-8")
    run_pytest(project)
    assert not list(project.rglob("__pycache__"))
    assert not list(project.rglob(".pytest_cache"))


def test_resource_limit_flag_matches_the_platform() -> None:
    """Document the degradation rather than silently depending on it.

    On POSIX we get CPU, memory and file-size limits. On Windows `resource`
    does not exist, so the wall-clock timeout is the only limit, which the
    timeout tests above prove still works.
    """
    import os

    assert RESOURCE_LIMITS_AVAILABLE == (os.name != "nt")
