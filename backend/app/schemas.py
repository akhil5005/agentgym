"""Pydantic v2 request and response models.

These are the API's contract. Keeping them separate from the SQLAlchemy models
means the database shape can change without silently changing what clients see,
and it is the layer that validates what the runner uploads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# A reward is a fraction of hidden tests passed, so it can only live in [0, 1].
Reward = Annotated[float, Field(ge=0.0, le=1.0)]

MAX_STEPS_PER_EPISODE = 100
MAX_TEXT_CHARS = 20_000

OUTCOMES = (
    "solved",
    "partial",
    "wrong_fix",
    "no_change",
    "out_of_steps",
    "timeout",
    "error",
)


def _truncate(text: str) -> str:
    """Server-side cap on stored text.

    The engine already truncates, but the backend must not trust its client:
    anything holding this API key could post a megabyte of observation.
    """
    if len(text) <= MAX_TEXT_CHARS:
        return text
    return text[:MAX_TEXT_CHARS] + "\n...[truncated by the server]"


# --- tasks -------------------------------------------------------------------


class TaskIn(BaseModel):
    """Task metadata, as uploaded by `runner sync-tasks`."""

    title: str = Field(min_length=1, max_length=200)
    difficulty: Literal["easy", "medium", "hard"]
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    max_steps: int = Field(gt=0, le=1000)


class TaskOut(BaseModel):
    """One task, with the stats the dashboard shows next to it."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    difficulty: str
    category: str
    description: str
    max_steps: int
    episodes: int = 0
    solve_rate: float = 0.0
    mean_reward: float = 0.0
    mean_steps: float = 0.0


# --- steps and episodes ------------------------------------------------------


class StepIn(BaseModel):
    """One step of a trajectory, as uploaded."""

    index: int = Field(ge=0)
    action_type: str = Field(min_length=1, max_length=30)
    action: dict[str, Any] = Field(default_factory=dict)
    observation: str = ""
    reward: float = 0.0
    error: bool = False
    tamper_blocked: bool = False
    created_at: datetime

    @field_validator("observation")
    @classmethod
    def cap_observation(cls, value: str) -> str:
        return _truncate(value)


class StepOut(BaseModel):
    """One step, as served to the replay viewer."""

    index: int
    action_type: str
    action: dict[str, Any]
    observation: str
    reward: float
    error: bool
    tamper_blocked: bool
    created_at: datetime


class EpisodeIn(BaseModel):
    """A complete episode with its trajectory."""

    id: str = Field(min_length=1, max_length=64)
    task_id: str = Field(min_length=1, max_length=100)
    agent_name: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    trial: int = Field(default=0, ge=0)

    reward: Reward
    outcome: str = Field(min_length=1, max_length=30)
    steps_used: int = Field(ge=0)
    tamper_attempts: int = Field(default=0, ge=0)
    tests_passed: int = Field(default=0, ge=0)
    tests_total: int = Field(default=0, ge=0)

    started_at: datetime
    finished_at: datetime

    steps: list[StepIn] = Field(default_factory=list, max_length=MAX_STEPS_PER_EPISODE)

    @field_validator("outcome")
    @classmethod
    def known_outcome(cls, value: str) -> str:
        """Reject outcome labels the dashboard has no colour for."""
        if value not in OUTCOMES:
            raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}")
        return value


class EpisodeSummary(BaseModel):
    """An episode without its steps, for list views."""

    model_config = ConfigDict(from_attributes=True)

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
    started_at: datetime
    finished_at: datetime


class EpisodeDetail(EpisodeSummary):
    """An episode with its full trajectory, for the replay viewer."""

    steps: list[StepOut]


# --- aggregates --------------------------------------------------------------


class LeaderboardRow(BaseModel):
    """One agent label's overall performance."""

    agent_name: str
    model: str | None
    label: str  # "llm (claude-sonnet-5-5)" or just "oracle"
    episodes: int
    mean_reward: float
    solve_rate: float
    mean_steps: float
    tamper_rate: float


class MatrixCell(BaseModel):
    """One task-by-agent cell of the results matrix."""

    task_id: str
    label: str
    n: int
    solve_rate: float
    mean_reward: float


class Stats(BaseModel):
    """Totals for the dashboard header."""

    tasks: int
    episodes: int
    agents: int
