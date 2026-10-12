"""The three scripted agents, run against the real tasks.

These are the invariants that keep the whole gym honest:

* the **oracle** must score 1.0 on every task — otherwise the task is unsolvable
* the **no-op** must score below 1.0 — otherwise the task is already solved
* the **tamper** agent must be blocked every time, and must never score higher
  than the no-op — otherwise cheating pays

Every episode is run once in a module-scoped fixture and shared, because each
grading run starts a fresh pytest process and that is the slow part.
"""

from __future__ import annotations

import pytest

from agentgym.agents.scripted import (
    NoOpAgent,
    OracleAgent,
    TamperAgent,
    build_scripted_agent,
)
from agentgym.env import CodingEnv
from agentgym.models import EpisodeRecord
from agentgym.runner import run_episode
from agentgym.tasks import list_task_ids, load_task, tasks_dir

AGENT_NAMES = ("noop", "oracle", "tamper")


def _real_task_ids() -> list[str]:
    """Task ids available at collection time, so we can parametrize on them."""
    root = tasks_dir()
    return list_task_ids(root) if root.is_dir() else []


REAL_TASK_IDS = _real_task_ids()

# Skip the whole module rather than fail it if the tasks folder is missing.
pytestmark = pytest.mark.skipif(
    not REAL_TASK_IDS, reason="no tasks found in the tasks/ folder"
)


@pytest.fixture(scope="module")
def episodes() -> dict[tuple[str, str], EpisodeRecord]:
    """Run every scripted agent on every real task exactly once."""
    root = tasks_dir()
    results: dict[tuple[str, str], EpisodeRecord] = {}
    for task_id in REAL_TASK_IDS:
        task = load_task(task_id, root)
        for agent_name in AGENT_NAMES:
            agent = build_scripted_agent(agent_name, task)
            with CodingEnv(root) as env:
                results[(agent_name, task_id)] = run_episode(env, agent, task_id)
    return results


# --- the oracle is the ceiling ----------------------------------------------


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_oracle_solves_every_task(episodes, task_id: str) -> None:
    episode = episodes[("oracle", task_id)]
    assert episode.reward == 1.0, (
        f"the reference solution for {task_id} does not pass its own hidden "
        f"tests: {episode.outcome}"
    )
    assert episode.outcome == "solved"
    assert episode.tests_passed == episode.tests_total


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_oracle_never_needs_to_cheat(episodes, task_id: str) -> None:
    assert episodes[("oracle", task_id)].tamper_attempts == 0


# --- the no-op is the floor --------------------------------------------------


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_noop_scores_below_one(episodes, task_id: str) -> None:
    """If doing nothing already scored 1.0, the task would measure nothing."""
    episode = episodes[("noop", task_id)]
    assert episode.reward < 1.0
    assert episode.outcome == "no_change"


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_noop_uses_exactly_one_step(episodes, task_id: str) -> None:
    assert episodes[("noop", task_id)].steps_used == 1


# --- the tamper agent is the control ----------------------------------------


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_tamper_attempts_are_all_blocked(episodes, task_id: str) -> None:
    episode = episodes[("tamper", task_id)]
    assert episode.tamper_attempts >= 4, (
        "every cheat the tamper agent tries must be refused; a lower count "
        "means the guard let one through"
    )
    blocked = [step for step in episode.steps if step.tamper_blocked]
    assert len(blocked) == episode.tamper_attempts


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_tamper_never_beats_noop(episodes, task_id: str) -> None:
    """Cheating must not pay. This is the headline anti-reward-hacking claim."""
    tamper = episodes[("tamper", task_id)]
    noop = episodes[("noop", task_id)]
    assert tamper.reward <= noop.reward


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_tamper_changes_nothing_in_the_workspace(episodes, task_id: str) -> None:
    episode = episodes[("tamper", task_id)]
    assert episode.outcome == "no_change"


@pytest.mark.parametrize("task_id", REAL_TASK_IDS)
def test_tamper_cannot_modify_the_visible_tests(episodes, task_id: str) -> None:
    submit_step = episodes[("tamper", task_id)].steps[-1]
    assert "visible_tests_modified" not in submit_step.observation
    # The grader records this separately; a blocked write means it stayed False.
    assert episodes[("tamper", task_id)].tests_total > 0


# --- agent plumbing ----------------------------------------------------------


def test_build_scripted_agent_returns_the_right_types() -> None:
    task = load_task(REAL_TASK_IDS[0], tasks_dir())
    assert isinstance(build_scripted_agent("noop", task), NoOpAgent)
    assert isinstance(build_scripted_agent("oracle", task), OracleAgent)
    assert isinstance(build_scripted_agent("tamper", task), TamperAgent)


def test_build_scripted_agent_rejects_unknown_names() -> None:
    task = load_task(REAL_TASK_IDS[0], tasks_dir())
    with pytest.raises(ValueError, match="unknown scripted agent"):
        build_scripted_agent("wizard", task)


def test_scripted_agents_report_no_model() -> None:
    """`model` is None for scripted agents, which is how the leaderboard tells
    a hard-coded baseline apart from an LLM."""
    task = load_task(REAL_TASK_IDS[0], tasks_dir())
    for name in AGENT_NAMES:
        assert build_scripted_agent(name, task).model is None


def test_noop_keeps_submitting_if_asked_again() -> None:
    agent = NoOpAgent()
    agent.start("desc", [])
    assert agent.next_action("") == {"type": "submit"}
    assert agent.next_action("") == {"type": "submit"}


def test_oracle_plan_ends_with_run_tests_then_submit() -> None:
    task = load_task(REAL_TASK_IDS[0], tasks_dir())
    agent = OracleAgent(task)
    agent.start(task.description, [])
    actions = [agent.next_action("") for _ in range(10)]
    types = [action["type"] for action in actions]
    assert "write_file" in types
    submit_at = types.index("submit")
    assert types[submit_at - 1] == "run_tests"


def test_tamper_plan_targets_several_different_rules() -> None:
    agent = TamperAgent()
    agent.start("desc", [])
    paths = []
    for _ in range(5):
        action = agent.next_action("")
        paths.append(action["path"])
    # Five distinct cheats, so one regressing guard rule is visible immediately.
    assert len(set(paths)) == 5


def test_an_agent_that_crashes_still_produces_an_episode() -> None:
    """A broken agent must not lose the trajectory we already collected."""

    class ExplodingAgent:
        name = "exploding"
        model = None

        def start(self, task_description: str, file_list: list[str]) -> None:
            return None

        def next_action(self, last_observation: str) -> dict:
            raise RuntimeError("the agent fell over")

    root = tasks_dir()
    task_id = REAL_TASK_IDS[0]
    with CodingEnv(root) as env:
        episode = run_episode(env, ExplodingAgent(), task_id)

    assert episode.agent_name == "exploding"
    assert episode.steps_used >= 1
    # It was graded rather than abandoned.
    assert episode.tests_total > 0
