"""Tests for loading tasks off disk.

Task metadata is hand-written JSON, so a typo is likely. These tests make the
loader fail loudly at load time instead of producing a confusing grading bug
twenty seconds later.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentgym.tasks import (
    list_task_ids,
    load_all_tasks,
    load_task,
    resolve_task_ids,
    tasks_dir,
)


def _rewrite_manifest(tasks_root: Path, task_id: str, **changes: object) -> None:
    """Patch fields in a fixture task's task.json."""
    manifest = tasks_root / task_id / "task.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.update(changes)
    manifest.write_text(json.dumps(data), encoding="utf-8")


def test_load_task_reads_the_manifest(make_task) -> None:
    tasks_root, task_id = make_task()
    task = load_task(task_id, tasks_root)
    assert task.id == task_id
    assert task.difficulty == "easy"
    assert task.max_steps == 15
    assert task.hidden_test_count == 2


def test_task_paths_point_at_the_right_folders(make_task) -> None:
    tasks_root, task_id = make_task()
    task = load_task(task_id, tasks_root)
    assert task.repo_dir.is_dir()
    assert task.hidden_tests_dir.is_dir()
    assert task.solution_dir.is_dir()


def test_missing_task_raises_with_the_available_ids(make_task) -> None:
    tasks_root, task_id = make_task()
    with pytest.raises(FileNotFoundError) as info:
        load_task("no_such_task", tasks_root)
    # The error should tell you what you *could* have asked for.
    assert task_id in str(info.value)


def test_id_must_match_the_folder_name(make_task) -> None:
    tasks_root, task_id = make_task()
    _rewrite_manifest(tasks_root, task_id, id="something_else")
    with pytest.raises(ValueError, match="does not match folder name"):
        load_task(task_id, tasks_root)


def test_difficulty_must_be_one_of_the_three(make_task) -> None:
    tasks_root, task_id = make_task()
    _rewrite_manifest(tasks_root, task_id, difficulty="impossible")
    with pytest.raises(ValueError, match="difficulty"):
        load_task(task_id, tasks_root)


@pytest.mark.parametrize("bad_count", [0, -1, "ten", None, 2.5])
def test_hidden_test_count_must_be_a_positive_integer(make_task, bad_count) -> None:
    tasks_root, task_id = make_task()
    _rewrite_manifest(tasks_root, task_id, hidden_test_count=bad_count)
    with pytest.raises(ValueError, match="hidden_test_count"):
        load_task(task_id, tasks_root)


@pytest.mark.parametrize("bad_steps", [0, -3, "lots"])
def test_max_steps_must_be_a_positive_integer(make_task, bad_steps) -> None:
    tasks_root, task_id = make_task()
    _rewrite_manifest(tasks_root, task_id, max_steps=bad_steps)
    with pytest.raises(ValueError, match="max_steps"):
        load_task(task_id, tasks_root)


def test_max_steps_defaults_to_fifteen(make_task) -> None:
    tasks_root, task_id = make_task()
    manifest = tasks_root / task_id / "task.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["max_steps"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert load_task(task_id, tasks_root).max_steps == 15


@pytest.mark.parametrize(
    "missing", ["title", "difficulty", "category", "description"]
)
def test_required_fields_are_required(make_task, missing: str) -> None:
    tasks_root, task_id = make_task()
    manifest = tasks_root / task_id / "task.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data[missing]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=missing):
        load_task(task_id, tasks_root)


def test_list_task_ids_is_sorted(make_task) -> None:
    tasks_root, _ = make_task(task_id="bbb")
    make_task(task_id="aaa")
    assert list_task_ids(tasks_root) == ["aaa", "bbb"]


def test_list_task_ids_on_a_missing_folder_is_empty(tmp_path: Path) -> None:
    assert list_task_ids(tmp_path / "nope") == []


def test_resolve_all_returns_every_task(make_task) -> None:
    tasks_root, _ = make_task(task_id="aaa")
    make_task(task_id="bbb")
    assert resolve_task_ids("all", tasks_root) == ["aaa", "bbb"]


def test_resolve_a_comma_separated_list(make_task) -> None:
    tasks_root, _ = make_task(task_id="aaa")
    make_task(task_id="bbb")
    assert resolve_task_ids("bbb, aaa", tasks_root) == ["bbb", "aaa"]


def test_resolve_rejects_an_unknown_id(make_task) -> None:
    """A typo must stop the run, not silently run fewer episodes."""
    tasks_root, _ = make_task(task_id="aaa")
    with pytest.raises(ValueError, match="unknown task id"):
        resolve_task_ids("aaa,typo", tasks_root)


def test_tasks_dir_honours_the_environment_override(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("AGENTGYM_TASKS_DIR", str(tmp_path))
    assert tasks_dir() == tmp_path.resolve()


# --- the real tasks ----------------------------------------------------------


def test_every_real_task_loads() -> None:
    root = tasks_dir()
    if not root.is_dir():
        pytest.skip("no tasks folder")
    tasks = load_all_tasks(root)
    assert tasks, "expected at least one real task"
    for task in tasks:
        assert task.description, f"{task.id} has an empty description"
        assert task.hidden_tests_dir.is_dir()
        assert any(task.solution_dir.rglob("*.py")), f"{task.id} has no solution files"


def test_real_tasks_have_a_failing_visible_test_file() -> None:
    root = tasks_dir()
    if not root.is_dir():
        pytest.skip("no tasks folder")
    for task in load_all_tasks(root):
        visible = task.repo_dir / "tests" / "test_visible.py"
        assert visible.is_file(), f"{task.id} is missing tests/test_visible.py"


def test_task_descriptions_do_not_leak_the_hidden_tests() -> None:
    """The briefing explains the goal; it must not mention the grading tests."""
    root = tasks_dir()
    if not root.is_dir():
        pytest.skip("no tasks folder")
    for task in load_all_tasks(root):
        lowered = task.description.lower()
        assert "hidden" not in lowered, f"{task.id} mentions hidden tests"
        assert "test_hidden" not in lowered


def test_public_dict_excludes_grading_details() -> None:
    """What goes to the backend must not include the hidden test count."""
    root = tasks_dir()
    if not root.is_dir():
        pytest.skip("no tasks folder")
    payload = load_all_tasks(root)[0].public_dict()
    assert set(payload) == {
        "id",
        "title",
        "difficulty",
        "category",
        "description",
        "max_steps",
    }
    assert "hidden_test_count" not in payload
    assert "root" not in payload
