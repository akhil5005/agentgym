"""Loading tasks from the `tasks/` folder on disk.

A task is just a folder with a `task.json` plus three sub-folders. Keeping tasks
as plain files (instead of rows in a database) means adding a task is a `git add`
and nothing else, and a human can read the whole task in an editor.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agentgym.models import Difficulty, Task

DEFAULT_MAX_STEPS = 15
_VALID_DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")


def tasks_dir() -> Path:
    """Where the task folders live.

    Normally the `tasks/` folder next to `engine/` in the repo. The env var
    override exists so tests can point at a throwaway fixture directory.
    """
    override = os.environ.get("AGENTGYM_TASKS_DIR")
    if override:
        return Path(override).resolve()
    # engine/agentgym/tasks.py -> agentgym -> engine -> repo root
    return Path(__file__).resolve().parents[2] / "tasks"


def list_task_ids(root: Path | None = None) -> list[str]:
    """Every task id, sorted, so run order is reproducible."""
    root = root or tasks_dir()
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "task.json").is_file()
    )


def load_task(task_id: str, root: Path | None = None) -> Task:
    """Read one task folder into a `Task`, failing loudly on bad metadata.

    We validate here rather than trusting `task.json`, because a typo in a task
    file would otherwise show up much later as a confusing grading bug.
    """
    root = root or tasks_dir()
    task_root = root / task_id
    manifest = task_root / "task.json"
    if not manifest.is_file():
        available = ", ".join(list_task_ids(root)) or "(none found)"
        raise FileNotFoundError(
            f"no task.json for task {task_id!r} at {manifest}. Available: {available}"
        )

    data = json.loads(manifest.read_text(encoding="utf-8"))

    for required in ("id", "title", "difficulty", "category", "description"):
        if required not in data:
            raise ValueError(f"{manifest}: missing required field {required!r}")

    if data["id"] != task_id:
        raise ValueError(
            f"{manifest}: id field {data['id']!r} does not match folder name {task_id!r}"
        )
    if data["difficulty"] not in _VALID_DIFFICULTIES:
        raise ValueError(
            f"{manifest}: difficulty must be one of {_VALID_DIFFICULTIES}, "
            f"got {data['difficulty']!r}"
        )

    hidden_count = data.get("hidden_test_count")
    if not isinstance(hidden_count, int) or hidden_count <= 0:
        raise ValueError(
            f"{manifest}: hidden_test_count must be a positive integer, "
            f"got {hidden_count!r}"
        )

    max_steps = data.get("max_steps", DEFAULT_MAX_STEPS)
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise ValueError(f"{manifest}: max_steps must be a positive integer")

    task = Task(
        id=data["id"],
        title=data["title"],
        difficulty=data["difficulty"],
        category=data["category"],
        description=data["description"].strip(),
        max_steps=max_steps,
        hidden_test_count=hidden_count,
        root=task_root,
    )

    if not task.repo_dir.is_dir():
        raise ValueError(f"task {task_id}: missing repo/ folder at {task.repo_dir}")
    if not task.hidden_tests_dir.is_dir():
        raise ValueError(f"task {task_id}: missing hidden_tests/ folder")

    return task


def load_all_tasks(root: Path | None = None) -> list[Task]:
    """Every task on disk, in id order."""
    root = root or tasks_dir()
    return [load_task(task_id, root) for task_id in list_task_ids(root)]


def resolve_task_ids(selector: str, root: Path | None = None) -> list[str]:
    """Turn a CLI `--tasks` value into a list of ids.

    Accepts "all" or a comma-separated list. Unknown ids raise immediately so a
    typo does not silently run fewer episodes than you asked for.
    """
    root = root or tasks_dir()
    known = list_task_ids(root)
    if selector.strip() == "all":
        return known

    wanted = [part.strip() for part in selector.split(",") if part.strip()]
    unknown = [task_id for task_id in wanted if task_id not in known]
    if unknown:
        raise ValueError(
            f"unknown task id(s): {', '.join(unknown)}. Available: {', '.join(known)}"
        )
    return wanted
