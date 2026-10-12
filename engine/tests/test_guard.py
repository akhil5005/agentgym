"""The guard is the anti-reward-hacking layer, so each rule gets its own test.

If one of these ever goes green-to-red, an agent has gained a way to fake a
pass. That is why they are spelled out one rule per test instead of looped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentgym.guard import (
    MAX_CONTENT_CHARS,
    MAX_WORKSPACE_FILES,
    check_write,
    list_workspace_files,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_visible.py").write_text("x = 1", encoding="utf-8")
    return tmp_path


def test_ordinary_source_write_is_allowed(workspace: Path) -> None:
    verdict = check_write(workspace, "src/code.py", "def f():\n    return 1\n")
    assert verdict.allowed
    assert verdict.resolved_path == (workspace / "src" / "code.py").resolve()


def test_new_nested_file_is_allowed(workspace: Path) -> None:
    assert check_write(workspace, "src/deep/new.py", "x = 1").allowed


def test_non_python_file_is_allowed(workspace: Path) -> None:
    assert check_write(workspace, "notes.md", "some notes").allowed


def test_writing_into_tests_is_blocked(workspace: Path) -> None:
    verdict = check_write(workspace, "tests/test_visible.py", "assert True")
    assert not verdict.allowed
    assert "tests/" in verdict.reason


def test_nested_path_inside_tests_is_blocked(workspace: Path) -> None:
    assert not check_write(workspace, "tests/unit/test_x.py", "assert True").allowed


@pytest.mark.parametrize(
    "filename",
    [
        "conftest.py",
        "pytest.ini",
        "setup.cfg",
        "tox.ini",
        "pyproject.toml",
        "sitecustomize.py",
        "usercustomize.py",
    ],
)
def test_protected_config_filenames_are_blocked(workspace: Path, filename: str) -> None:
    assert not check_write(workspace, filename, "whatever").allowed


def test_protected_filename_is_blocked_in_a_subfolder(workspace: Path) -> None:
    # A conftest.py anywhere on the path is collected by pytest, so the check
    # must look at the file name, not just the top level.
    assert not check_write(workspace, "src/conftest.py", "x = 1").allowed


def test_pth_files_are_blocked(workspace: Path) -> None:
    assert not check_write(workspace, "evil.pth", "import os").allowed


@pytest.mark.parametrize(
    "bad_path",
    ["../escape.py", "src/../../escape.py", "a/b/../../../out.py"],
)
def test_parent_traversal_is_blocked(workspace: Path, bad_path: str) -> None:
    assert not check_write(workspace, bad_path, "x = 1").allowed


@pytest.mark.parametrize(
    "bad_path",
    ["/etc/passwd", "C:/Windows/evil.py", "C:\\Windows\\evil.py", "//server/share/x.py"],
)
def test_absolute_paths_are_blocked(workspace: Path, bad_path: str) -> None:
    assert not check_write(workspace, bad_path, "x = 1").allowed


def test_empty_path_is_blocked(workspace: Path) -> None:
    assert not check_write(workspace, "   ", "x = 1").allowed


def test_symlink_pointing_outside_the_workspace_is_blocked(
    workspace: Path, tmp_path: Path
) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    link = workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this platform/user cannot create symlinks")
    assert not check_write(workspace, "link/sneaky.py", "x = 1").allowed


@pytest.mark.parametrize(
    "source",
    [
        "import socket",
        "import subprocess",
        "import ctypes",
        "import multiprocessing",
        "import urllib.request",
        "import http.client",
        "import requests",
        "import ftplib",
        "import smtplib",
        "import pty",
        "import importlib",
        "import runpy",
        "from socket import socket",
        "from urllib import request",
        "import os, socket",
    ],
)
def test_forbidden_imports_are_blocked(workspace: Path, source: str) -> None:
    assert not check_write(workspace, "src/x.py", source).allowed


@pytest.mark.parametrize(
    "source",
    [
        "exec('x = 1')",
        "eval('1 + 1')",
        "compile('x = 1', '<s>', 'exec')",
        "__import__('socket')",
        "import builtins\nbuiltins.exec('x = 1')",
    ],
)
def test_forbidden_dynamic_calls_are_blocked(workspace: Path, source: str) -> None:
    assert not check_write(workspace, "src/x.py", source).allowed


def test_relative_import_is_allowed(workspace: Path) -> None:
    # `from . import helper` stays inside the workspace, so it is not a risk.
    assert check_write(workspace, "src/x.py", "from . import helper").allowed


def test_forbidden_import_in_a_non_python_file_is_allowed(workspace: Path) -> None:
    # The AST check only applies to .py files; a text file is never executed.
    assert check_write(workspace, "notes.txt", "import subprocess").allowed


def test_syntax_error_is_written_not_treated_as_tampering(workspace: Path) -> None:
    """A broken file is the agent's own problem, not an attack.

    We allow it so the agent sees the failure next time it runs the tests,
    which is the feedback loop the gym is built around.
    """
    verdict = check_write(workspace, "src/x.py", "def broken(:\n")
    assert verdict.allowed


def test_oversized_content_is_blocked(workspace: Path) -> None:
    assert not check_write(workspace, "src/x.py", "x" * (MAX_CONTENT_CHARS + 1)).allowed


def test_content_at_the_size_limit_is_allowed(workspace: Path) -> None:
    assert check_write(workspace, "notes.txt", "x" * MAX_CONTENT_CHARS).allowed


def test_too_many_files_is_blocked(workspace: Path) -> None:
    # Fill the workspace right up to the limit, then ask for one more.
    existing = len(list_workspace_files(workspace))
    for index in range(MAX_WORKSPACE_FILES - existing - 1):
        (workspace / f"filler_{index}.txt").write_text("x", encoding="utf-8")
    verdict = check_write(workspace, "one_too_many.txt", "x")
    assert not verdict.allowed
    assert "limit" in verdict.reason


def test_overwriting_an_existing_file_ignores_the_file_count(workspace: Path) -> None:
    existing = len(list_workspace_files(workspace))
    for index in range(MAX_WORKSPACE_FILES - existing + 5):
        (workspace / f"filler_{index}.txt").write_text("x", encoding="utf-8")
    # Replacing a file adds nothing, so the count must not block it.
    assert check_write(workspace, "filler_0.txt", "updated").allowed


def test_list_workspace_files_skips_pycache_and_dotfiles(workspace: Path) -> None:
    (workspace / "src" / "code.py").write_text("x = 1", encoding="utf-8")
    (workspace / "src" / "__pycache__").mkdir()
    (workspace / "src" / "__pycache__" / "code.pyc").write_bytes(b"\x00")
    (workspace / ".hidden").write_text("secret", encoding="utf-8")

    names = list_workspace_files(workspace)
    assert "src/code.py" in names
    assert "tests/test_visible.py" in names
    assert not any("__pycache__" in name for name in names)
    assert not any(name.startswith(".") for name in names)


def test_list_workspace_files_is_sorted(workspace: Path) -> None:
    (workspace / "zz.txt").write_text("z", encoding="utf-8")
    (workspace / "aa.txt").write_text("a", encoding="utf-8")
    names = list_workspace_files(workspace)
    assert names == sorted(names)
