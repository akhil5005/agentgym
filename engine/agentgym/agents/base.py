"""The interface every agent implements.

This is a `Protocol`, not a base class, so an agent only has to *look* like this
to work. There is no inheritance to understand and nothing to call `super()` on.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Agent(Protocol):
    """Something that can play one episode of the gym."""

    # Shown on the leaderboard, e.g. "oracle" or "llm".
    name: str
    # Model identifier for LLM agents; None for scripted ones.
    model: str | None

    def start(self, task_description: str, file_list: list[str]) -> None:
        """Called once, before the first action, with everything the agent is
        allowed to know up front."""
        ...

    def next_action(self, last_observation: str) -> dict[str, Any]:
        """Return the next action as a plain dict, e.g. `{"type": "submit"}`.

        `last_observation` is what the environment said about the previous
        action (or the task briefing, on the first call).
        """
        ...
