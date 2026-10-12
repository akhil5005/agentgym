"""Running pytest in a contained subprocess.

Everything the agent wrote gets executed here, so this module is where we put
the limits: a wall-clock timeout, POSIX resource limits where the platform has
them, and a deliberately tiny environment so agent code cannot read your API
keys out of `os.environ`.

Only the standard library is used (`subprocess`, `os`, `signal`, `resource`),
so there is nothing to install and nothing to configure.

Honest limitation: this is a *contained* subprocess, not a sandbox in the
virtual-machine sense. It runs as your user, with your filesystem permissions.
See the README's "Threat model".
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from agentgym.models import MAX_TEST_OUTPUT_CHARS, tail

# `resource` is POSIX-only. On Windows we degrade to the wall-clock timeout
# rather than refusing to run, and say so in the result.
try:
    import resource  # type: ignore[import-not-found]

    RESOURCE_LIMITS_AVAILABLE = True
except ImportError:  # pragma: no cover - platform dependent
    resource = None  # type: ignore[assignment]
    RESOURCE_LIMITS_AVAILABLE = False

CPU_SECONDS = 10  # CPU time, which a busy-loop burns through fast
ADDRESS_SPACE_BYTES = 1_536 * 1024 * 1024  # ~1.5 GB
FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB, so no filling the disk
DEFAULT_TIMEOUT_SECONDS = 20
GRADING_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one pytest run."""

    returncode: int
    output: str  # stdout and stderr interleaved, trimmed to the last N chars
    timed_out: bool
    duration_seconds: float


def _apply_resource_limits() -> None:  # pragma: no cover - runs in the child
    """Set POSIX limits in the child, just before pytest replaces it.

    Each limit is wrapped separately: macOS silently refuses RLIMIT_AS, and we
    would rather lose one limit than fail to run the tests at all. We do *not*
    set RLIMIT_NPROC, because it counts processes per user, not per subprocess,
    and would start failing other programs you are running.
    """
    assert resource is not None
    for limit_name, soft, hard in (
        ("RLIMIT_CPU", CPU_SECONDS, CPU_SECONDS + 5),
        ("RLIMIT_AS", ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES),
        ("RLIMIT_FSIZE", FILE_SIZE_BYTES, FILE_SIZE_BYTES),
        ("RLIMIT_CORE", 0, 0),
    ):
        try:
            resource.setrlimit(getattr(resource, limit_name), (soft, hard))
        except (ValueError, OSError):
            pass


def _child_environment(cwd: Path) -> dict[str, str]:
    """A minimal environment for the test process.

    Nothing is inherited by default. That is the point: if `ANTHROPIC_API_KEY`
    is in your shell, agent-written code must not be able to read it. We add
    back only the variables an interpreter genuinely needs to start, plus HOME
    pointed at the throwaway workspace so stray writes land there.
    """
    env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONDONTWRITEBYTECODE": "1",  # no __pycache__ cluttering the listing
        "PYTHONHASHSEED": "0",  # deterministic dict/set iteration order
        "HOME": str(cwd),
    }

    if os.name == "nt":
        # Windows needs these for a working interpreter (DLL search, temp dir).
        # None of them carry secrets.
        for key in ("SYSTEMROOT", "SystemRoot", "SYSTEMDRIVE", "COMSPEC", "PATHEXT"):
            value = os.environ.get(key)
            if value:
                env[key] = value
        env["USERPROFILE"] = str(cwd)
        env["TEMP"] = str(cwd)
        env["TMP"] = str(cwd)

    return env


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill the test process *and anything it spawned*.

    Killing only the direct child would leave grandchildren holding the pipes
    open, so the read would hang forever, which is exactly the failure the
    timeout exists to prevent.
    """
    if os.name == "nt":
        # No process groups to signal; ask Windows to kill the tree for us.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
        process.kill()
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()


def run_pytest(
    cwd: Path,
    extra_args: tuple[str, ...] | list[str] = (),
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    output_limit: int = MAX_TEST_OUTPUT_CHARS,
) -> SandboxResult:
    """Run pytest inside `cwd` and come back with its output, whatever happens.

    This function does not raise on test failure or on timeout: both are normal
    results in a gym, and the caller turns them into a reward.
    """
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",  # do not write .pytest_cache into the workspace
        "-q",
        "--disable-warnings",
        "--tb=short",
        *extra_args,
    ]

    popen_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": _child_environment(cwd),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,  # one interleaved stream is easier to read
        "stdin": subprocess.DEVNULL,  # a test that waits for input fails fast
        "text": True,
        "errors": "replace",  # agent code may emit undecodable bytes
        # shell=True is never used: the command is a fixed argv list, so there
        # is no shell for agent-controlled text to be interpreted by.
    }

    if os.name == "nt":
        # Own process group, so the taskkill above reaches the whole tree.
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True  # detach from our terminal
        if RESOURCE_LIMITS_AVAILABLE:
            popen_kwargs["preexec_fn"] = _apply_resource_limits

    started = time.monotonic()
    timed_out = False

    process = subprocess.Popen(command, **popen_kwargs)  # type: ignore[call-overload]
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(process)
        # Collect whatever was printed before the kill; the process is dead, so
        # this cannot block.
        output, _ = process.communicate()
        output = (output or "") + (
            f"\n\n[agentgym] TIMEOUT: the tests were killed after "
            f"{timeout_seconds}s. An infinite loop or a hang is the usual cause."
        )

    duration = time.monotonic() - started
    return SandboxResult(
        returncode=process.returncode,
        output=tail(output or "", output_limit),
        timed_out=timed_out,
        duration_seconds=round(duration, 3),
    )
