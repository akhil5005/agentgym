"""Plain data containers shared by the whole engine.

These are dataclasses, not Pydantic models, because nothing here crosses a
network boundary. The backend has its own Pydantic schemas for that job.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# --- Truncation limits -------------------------------------------------------
# An agent could read a huge file or produce huge test output. We cap everything
# so a single step can never blow up the episode log or the model's context.
MAX_READ_CHARS = 20_000
MAX_TEST_OUTPUT_CHARS = 4_000
MAX_RECORD_CHARS = 20_000

Difficulty = Literal["easy", "medium", "hard"]


class UserFacingError(RuntimeError):
    """An error the CLI reports as one readable line, not a traceback.

    Lives here rather than in the module that raises it so the runner can catch
    it without importing the optional LLM agent (and its optional SDK).
    """

# The only action types the environment understands.
ACTION_TYPES = ("list_files", "read_file", "write_file", "run_tests", "submit")

# Outcome labels, in the order of precedence used by classify_outcome().
Outcome = Literal[
    "error", "timeout", "solved", "out_of_steps", "no_change", "partial", "wrong_fix"
]


def utc_now_iso() -> str:
    """Current time as an ISO-8601 string with an explicit UTC offset."""
    return datetime.now(timezone.utc).isoformat()


def truncate(text: str, limit: int = MAX_RECORD_CHARS) -> str:
    """Cut `text` to `limit` characters and say so, so nothing looks complete
    when it is not."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated, {len(text) - limit} more characters]"


def tail(text: str, limit: int) -> str:
    """Keep the *last* `limit` characters. Test output is most useful at the end
    (the failure summary lives there), so we trim from the front."""
    if len(text) <= limit:
        return text
    return f"...[truncated, {len(text) - limit} earlier characters]\n" + text[-limit:]


@dataclass(frozen=True)
class Task:
    """One buggy mini-project the agent is asked to fix."""

    id: str
    title: str
    difficulty: Difficulty
    category: str
    description: str
    max_steps: int
    hidden_test_count: int
    root: Path  # tasks/<id>/ on disk; never sent to the backend

    @property
    def repo_dir(self) -> Path:
        """What the agent sees: buggy source plus visible tests."""
        return self.root / "repo"

    @property
    def hidden_tests_dir(self) -> Path:
        """Grading tests. Never copied into the agent's workspace."""
        return self.root / "hidden_tests"

    @property
    def solution_dir(self) -> Path:
        """Reference fix. Used by `validate` and the oracle agent only."""
        return self.root / "solution"

    def public_dict(self) -> dict[str, Any]:
        """The subset that is safe to upload to the backend.

        Deliberately excludes `root` and `hidden_test_count`: the dashboard has
        no use for them, and keeping them local makes it impossible to leak
        grading details through the API.
        """
        return {
            "id": self.id,
            "title": self.title,
            "difficulty": self.difficulty,
            "category": self.category,
            "description": self.description,
            "max_steps": self.max_steps,
        }


@dataclass(frozen=True)
class Action:
    """A validated action. Agents hand us raw dicts; this is the parsed form."""

    type: str
    path: str | None = None
    content: str | None = None

    @classmethod
    def parse(cls, raw: Any) -> "Action":
        """Turn an agent's raw dict into an Action.

        Raises ValueError with a human-readable message on anything malformed.
        The environment catches that and turns it into an error observation, so
        a confused agent gets feedback instead of crashing the episode.
        """
        if not isinstance(raw, dict):
            raise ValueError(f"action must be a JSON object, got {type(raw).__name__}")

        action_type = raw.get("type")
        if not isinstance(action_type, str):
            raise ValueError("action is missing a string 'type' field")
        if action_type not in ACTION_TYPES:
            raise ValueError(
                f"unknown action type {action_type!r}; "
                f"valid types are: {', '.join(ACTION_TYPES)}"
            )

        path = raw.get("path")
        content = raw.get("content")

        if action_type in ("read_file", "write_file"):
            if not isinstance(path, str) or not path.strip():
                raise ValueError(f"{action_type} requires a non-empty 'path' string")
        if action_type == "write_file":
            if not isinstance(content, str):
                raise ValueError("write_file requires a 'content' string")

        return cls(type=action_type, path=path, content=content)

    def to_dict(self) -> dict[str, Any]:
        """JSON form for the episode log, with long content truncated."""
        out: dict[str, Any] = {"type": self.type}
        if self.path is not None:
            out["path"] = self.path
        if self.content is not None:
            out["content"] = truncate(self.content)
        return out


@dataclass
class StepResult:
    """What `env.step()` gives back: the classic RL tuple plus a details bag."""

    observation: str
    reward: float
    done: bool
    info: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    """One row of the trajectory, as stored and replayed in the dashboard."""

    index: int
    action_type: str
    action: dict[str, Any]
    observation: str
    reward: float
    error: bool
    tamper_blocked: bool
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["observation"] = truncate(data["observation"])
        return data


@dataclass
class EpisodeRecord:
    """One complete attempt at one task."""

    id: str
    task_id: str
    agent_name: str
    model: str | None
    trial: int
    reward: float
    outcome: str
    steps_used: int
    tamper_attempts: int
    tests_passed: int
    tests_total: int
    started_at: str
    finished_at: str
    steps: list[StepRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "agent_name": self.agent_name,
            "model": self.model,
            "trial": self.trial,
            "reward": self.reward,
            "outcome": self.outcome,
            "steps_used": self.steps_used,
            "tamper_attempts": self.tamper_attempts,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_jsonl(self) -> str:
        """One episode as a single JSON line, for `runs/*.jsonl`."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
