"""Shared fixtures for the engine tests.

Most tests run against a tiny throwaway task rather than the real nine. That
keeps them fast (each grading run starts a fresh pytest process) and keeps the
engine tests honest: they test the engine, not the quality of the tasks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

# A task small enough that a grading run finishes almost instantly.
FIXTURE_SOURCE_BUGGY = "def answer():\n    return 1\n"
FIXTURE_SOURCE_FIXED = "def answer():\n    return 2\n"
FIXTURE_VISIBLE_TESTS = (
    "from src.code import answer\n\n\n"
    "def test_answer_is_two():\n"
    "    assert answer() == 2\n"
)
FIXTURE_HIDDEN_TESTS = (
    "from src.code import answer\n\n\n"
    "def test_answer_is_two():\n"
    "    assert answer() == 2\n\n\n"
    "def test_answer_is_an_int():\n"
    "    assert isinstance(answer(), int)\n"
)

TaskFactory = Callable[..., tuple[Path, str]]


@pytest.fixture
def make_task(tmp_path: Path) -> TaskFactory:
    """Return a function that writes a throwaway task and gives back its root.

    Usage: `tasks_root, task_id = make_task(max_steps=3)`.
    """

    def factory(
        task_id: str = "fixture_task",
        max_steps: int = 15,
        hidden_test_count: int = 2,
    ) -> tuple[Path, str]:
        tasks_root = tmp_path / "tasks"
        task_dir = tasks_root / task_id
        for sub in ("repo/src", "repo/tests", "hidden_tests", "solution/src"):
            (task_dir / sub).mkdir(parents=True, exist_ok=True)

        (task_dir / "task.json").write_text(
            json.dumps(
                {
                    "id": task_id,
                    "title": "Fixture task",
                    "difficulty": "easy",
                    "category": "fixture",
                    "description": "answer() must return 2.",
                    "max_steps": max_steps,
                    "hidden_test_count": hidden_test_count,
                }
            ),
            encoding="utf-8",
        )
        (task_dir / "repo/src/__init__.py").write_text("", encoding="utf-8")
        (task_dir / "repo/src/code.py").write_text(
            FIXTURE_SOURCE_BUGGY, encoding="utf-8"
        )
        (task_dir / "repo/tests/test_visible.py").write_text(
            FIXTURE_VISIBLE_TESTS, encoding="utf-8"
        )
        (task_dir / "hidden_tests/test_hidden.py").write_text(
            FIXTURE_HIDDEN_TESTS, encoding="utf-8"
        )
        (task_dir / "solution/src/code.py").write_text(
            FIXTURE_SOURCE_FIXED, encoding="utf-8"
        )
        return tasks_root, task_id

    return factory


@pytest.fixture
def real_tasks_root() -> Path:
    """The repository's real `tasks/` folder."""
    from agentgym.tasks import tasks_dir

    root = tasks_dir()
    if not root.is_dir():
        pytest.skip(f"no tasks folder at {root}")
    return root
