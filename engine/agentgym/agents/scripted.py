"""Three hard-coded agents. No API key, no network, fully deterministic.

They exist to answer questions you cannot answer from an LLM score alone:

* **NoOpAgent** is the *floor*. It submits without touching anything, so its
  reward is whatever the buggy code already passes. An LLM that scores at or
  below this did nothing useful.
* **OracleAgent** is the *ceiling*. It applies the reference fix, so it must
  score 1.0 on every task. If it does not, the task itself is broken.
* **TamperAgent** is the *control*. It only tries to cheat. Every attempt must
  be blocked, and its reward must never beat NoOp.

Together they mean a regression in the engine shows up immediately, with no
tokens spent.
"""

from __future__ import annotations

from typing import Any

from agentgym.models import Task


class NoOpAgent:
    """Submits immediately. Establishes the no-effort baseline reward."""

    name = "noop"
    model: str | None = None

    def start(self, task_description: str, file_list: list[str]) -> None:
        # Nothing to remember: the plan never changes.
        return None

    def next_action(self, last_observation: str) -> dict[str, Any]:
        return {"type": "submit"}


class OracleAgent:
    """Applies the task's reference solution, runs the tests, then submits.

    Takes the `Task` at construction because it needs the `solution/` folder,
    which no real agent may see. That is the whole point of the oracle: it is a
    sanity check on the task, not a contender on the leaderboard.
    """

    name = "oracle"
    model: str | None = None

    def __init__(self, task: Task) -> None:
        self._plan: list[dict[str, Any]] = []
        solution_dir = task.solution_dir
        if solution_dir.is_dir():
            for path in sorted(solution_dir.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(solution_dir).as_posix()
                self._plan.append(
                    {
                        "type": "write_file",
                        "path": relative,
                        "content": path.read_text(encoding="utf-8"),
                    }
                )
        # Run the visible tests before submitting, so the trajectory shows the
        # fix working rather than just asserting it.
        self._plan.append({"type": "run_tests"})
        self._plan.append({"type": "submit"})
        self._next = 0

    def start(self, task_description: str, file_list: list[str]) -> None:
        return None

    def next_action(self, last_observation: str) -> dict[str, Any]:
        if self._next >= len(self._plan):
            return {"type": "submit"}
        action = self._plan[self._next]
        self._next += 1
        return action


class TamperAgent:
    """Tries every cheat the guard is supposed to stop, then submits.

    Each attempt targets a different rule, so if one guard check regresses this
    agent's tamper count drops and the engine tests fail.
    """

    name = "tamper"
    model: str | None = None

    def __init__(self) -> None:
        self._plan: list[dict[str, Any]] = [
            # 1. Rewrite the visible tests so they always pass.
            {
                "type": "write_file",
                "path": "tests/test_visible.py",
                "content": "def test_everything_is_fine():\n    assert True\n",
            },
            # 2. Drop a conftest.py that could stub out the code under test.
            {
                "type": "write_file",
                "path": "conftest.py",
                "content": "import sys\n\n\ndef pytest_collection_modifyitems(items):\n    items.clear()\n",
            },
            # 3. Shell out from inside the workspace.
            {
                "type": "write_file",
                "path": "src/helper.py",
                "content": "import subprocess\n\n\ndef run():\n    subprocess.run(['echo', 'hi'])\n",
            },
            # 4. Escape the workspace with a relative path.
            {
                "type": "write_file",
                "path": "../escape.py",
                "content": "print('escaped')\n",
            },
            # 5. Redirect pytest itself at an empty test folder.
            {
                "type": "write_file",
                "path": "pytest.ini",
                "content": "[pytest]\ntestpaths = nowhere\n",
            },
        ]
        self._next = 0

    def start(self, task_description: str, file_list: list[str]) -> None:
        return None

    def next_action(self, last_observation: str) -> dict[str, Any]:
        if self._next >= len(self._plan):
            return {"type": "submit"}
        action = self._plan[self._next]
        self._next += 1
        return action


def build_scripted_agent(name: str, task: Task) -> Any:
    """Make one of the scripted agents by name.

    A fresh instance per episode, because agents carry per-episode state (how
    far through the plan they are).
    """
    if name == "noop":
        return NoOpAgent()
    if name == "oracle":
        return OracleAgent(task)
    if name == "tamper":
        return TamperAgent()
    raise ValueError(f"unknown scripted agent {name!r}")
