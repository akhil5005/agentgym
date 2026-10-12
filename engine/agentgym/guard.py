"""Anti-reward-hacking checks for `write_file`.

An agent graded on "do the tests pass?" has an obvious shortcut: change the
tests. Or drop a `conftest.py` that monkey-patches the thing under test. Or
shell out. This module rejects those writes before they touch disk.

READ THIS: the guard is **defense in depth, not a security boundary.** Code the
agent writes still runs as your user when the tests run. A determined attacker
could get around these checks. The real protection is operational: untrusted
agents only ever run on your own machine, through the runner CLI, never on a
public server. See the "Threat model" section of the README.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

# Writing any of these lets an agent change how pytest itself behaves, which
# would let it fake a pass without fixing anything.
FORBIDDEN_FILENAMES = frozenset(
    {
        "conftest.py",  # pytest hooks: could stub out the buggy function
        "pytest.ini",  # engine-owned config: could redirect which tests run
        "setup.cfg",
        "tox.ini",
        "pyproject.toml",
        "sitecustomize.py",  # imported automatically at interpreter start
        "usercustomize.py",
    }
)

# `.pth` files in a site directory execute lines starting with "import" at
# interpreter start, which is an easy and well-known escape hatch.
FORBIDDEN_SUFFIX = ".pth"

# Modules that let agent code reach the network, spawn processes, or rewrite the
# interpreter's own behaviour. A correct fix to any of our nine tasks needs none
# of them.
FORBIDDEN_IMPORTS = frozenset(
    {
        "socket",
        "subprocess",
        "ctypes",
        "multiprocessing",
        "urllib",
        "http",
        "requests",
        "ftplib",
        "smtplib",
        "pty",
        "importlib",
        "runpy",
    }
)

# Dynamic-execution builtins: with these, the import check above is trivial to
# bypass (for example __import__ called with a string module name).
FORBIDDEN_CALLS = frozenset({"exec", "eval", "compile", "__import__"})

MAX_CONTENT_CHARS = 100_000
MAX_WORKSPACE_FILES = 50


@dataclass(frozen=True)
class GuardVerdict:
    """The guard's answer. `allowed=False` means the write never happens."""

    allowed: bool
    reason: str = ""
    # Absolute path to write to. Only meaningful when allowed is True.
    resolved_path: Path | None = None


def list_workspace_files(workspace: Path) -> list[str]:
    """Relative paths of the files an agent is allowed to see.

    Skips `__pycache__` and dotfiles so the listing shows the project, not the
    interpreter's bookkeeping. Sorted for reproducible observations.
    """
    results: list[str] = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(workspace).parts
        if any(part == "__pycache__" or part.startswith(".") for part in parts):
            continue
        results.append("/".join(parts))
    return sorted(results)


def _looks_absolute(raw_path: str) -> bool:
    """True for POSIX roots, drive letters and UNC shares alike.

    We check both path flavours regardless of the host OS: the agent is a text
    generator and may well emit a Windows path on Linux or the reverse.
    """
    return (
        os.path.isabs(raw_path)
        or PurePosixPath(raw_path).is_absolute()
        or PureWindowsPath(raw_path).is_absolute()
    )


def _path_parts(raw_path: str) -> list[str]:
    """Split on both separators, so a backslash path is analysed like a slash one.

    Whitespace-only segments are dropped as if they were empty. Windows quietly
    strips trailing spaces from file names, so a path like "   " would otherwise
    resolve to the workspace directory itself and look like a legitimate write.
    """
    return [part for part in raw_path.replace("\\", "/").split("/") if part.strip()]


def _banned_python_constructs(source: str) -> str | None:
    """Return a reason string if the Python source uses a banned import or call.

    A syntax error returns None on purpose: a broken file is the agent's own
    problem, not an attack. We let it be written so the agent sees the failure
    when it runs the tests, which is the feedback loop we want.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # A dotted import like http.client has top-level module "http".
                top = alias.name.split(".")[0]
                if top in FORBIDDEN_IMPORTS:
                    return f"imports the forbidden module {top!r}"
        elif isinstance(node, ast.ImportFrom):
            # A relative import has module=None; those stay inside the
            # workspace, so they are fine.
            if node.module:
                top = node.module.split(".")[0]
                if top in FORBIDDEN_IMPORTS:
                    return f"imports the forbidden module {top!r}"
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Catches an attribute form such as builtins.exec(...) too.
                name = node.func.attr
            if name in FORBIDDEN_CALLS:
                return f"calls the forbidden builtin {name!r}"

    return None


def check_write(workspace: Path, raw_path: str, content: str) -> GuardVerdict:
    """Decide whether `write_file(raw_path, content)` may proceed.

    Checks run cheapest-and-most-dangerous first, so the returned reason names
    the most relevant problem rather than an incidental one.
    """
    workspace = workspace.resolve()

    # --- Path shape ----------------------------------------------------------
    if _looks_absolute(raw_path):
        return GuardVerdict(False, "absolute paths are not allowed")

    parts = _path_parts(raw_path)
    if not parts:
        return GuardVerdict(False, "empty path")
    if ".." in parts:
        return GuardVerdict(False, "'..' is not allowed in a path")

    # Resolve symlinks too (realpath), so a link planted inside the workspace
    # cannot point out of it.
    target = Path(os.path.realpath(workspace / raw_path))
    if not target.is_relative_to(workspace):
        return GuardVerdict(False, "path resolves outside the workspace")
    if target == workspace:
        return GuardVerdict(False, "path points at the workspace root, not a file")
    if target.is_dir():
        return GuardVerdict(False, f"{raw_path!r} is a directory, not a file")

    # --- Protected locations and names ---------------------------------------
    if target.is_relative_to(workspace / "tests"):
        return GuardVerdict(
            False, "the tests/ folder is read-only: fix the source, not the tests"
        )

    filename = target.name
    if filename in FORBIDDEN_FILENAMES:
        return GuardVerdict(False, f"{filename} is a protected configuration file")
    if filename.endswith(FORBIDDEN_SUFFIX):
        return GuardVerdict(False, "'.pth' files are not allowed")

    # --- Size and count ------------------------------------------------------
    if len(content) > MAX_CONTENT_CHARS:
        return GuardVerdict(
            False,
            f"content is {len(content)} characters, over the "
            f"{MAX_CONTENT_CHARS} limit",
        )
    if not target.exists():
        existing = len(list_workspace_files(workspace))
        if existing + 1 >= MAX_WORKSPACE_FILES:
            return GuardVerdict(
                False,
                f"workspace already holds {existing} files, "
                f"the limit is {MAX_WORKSPACE_FILES}",
            )

    # --- Python source contents ----------------------------------------------
    if filename.endswith(".py"):
        reason = _banned_python_constructs(content)
        if reason is not None:
            return GuardVerdict(False, f"file {reason}")

    return GuardVerdict(True, resolved_path=target)
