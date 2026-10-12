"""Playing one episode from reset to done.

Lives in its own module because both the runner and `validate` need it, and
because this loop is the heart of the project: everything else is setup,
storage, or presentation around these twenty lines.
"""

from __future__ import annotations

import uuid
from typing import Any

from agentgym.env import CodingEnv
from agentgym.models import EpisodeRecord, utc_now_iso


# --- running one episode -----------------------------------------------------


def run_episode(
    env: CodingEnv, agent: Any, task_id: str, trial: int = 0
) -> EpisodeRecord:
    """Play one episode to the end and package it as an `EpisodeRecord`.

    The loop always terminates: the environment auto-submits once the agent
    reaches `max_steps`, so an agent that never submits still gets graded.
    """
    reset = env.reset(task_id)
    started_at = utc_now_iso()
    agent.start(reset.task.description, reset.file_list)

    observation = reset.observation
    final_reward = 0.0

    while True:
        try:
            action = agent.next_action(observation)
        except Exception as exc:  # noqa: BLE001 - an agent crash must not lose the episode
            # Submit so the episode is still graded and stored, with the crash
            # visible in the trajectory instead of lost in a stack trace.
            observation = f"ERROR: the agent raised {type(exc).__name__}: {exc}"
            action = {"type": "submit"}

        result = env.step(action)
        observation = result.observation
        if result.done:
            final_reward = result.reward
            break

    info = env.final_info
    return EpisodeRecord(
        id=str(uuid.uuid4()),
        task_id=task_id,
        agent_name=agent.name,
        model=getattr(agent, "model", None),
        trial=trial,
        reward=final_reward,
        outcome=str(info.get("outcome", "error")),
        steps_used=env.step_index,
        tamper_attempts=env.tamper_attempts,
        tests_passed=int(info.get("tests_passed", 0)),
        tests_total=int(info.get("tests_total", 0)),
        started_at=started_at,
        finished_at=utc_now_iso(),
        steps=list(env.steps),
    )

