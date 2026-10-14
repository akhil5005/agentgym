"""Leaderboard, matrix and totals, checked against exact hand-computed values.

Aggregates are easy to get subtly wrong — averaging an average, counting a
denominator twice — so these tests assert the precise expected numbers for a
small fixture rather than just checking the shape of the response.
"""

from __future__ import annotations

import pytest
from conftest import seed_episode, seed_task

# The fixture below is five episodes across two tasks and three agents.
#
#  agent   task  reward  outcome     steps  tamper_attempts
#  oracle  t1    1.0     solved      3      0
#  oracle  t2    1.0     solved      5      0
#  noop    t1    0.0     no_change   1      0
#  noop    t2    0.5     no_change   1      0
#  tamper  t1    0.0     no_change   6      5
#
# oracle: 2 episodes, mean reward 1.0,  solve rate 1.0, mean steps 4.0, tamper 0.0
# noop:   2 episodes, mean reward 0.25, solve rate 0.0, mean steps 1.0, tamper 0.0
# tamper: 1 episode,  mean reward 0.0,  solve rate 0.0, mean steps 6.0, tamper 1.0


@pytest.fixture
def seeded(client):
    seed_task(client, "t1")
    seed_task(client, "t2")
    seed_episode(client, id="e1", task_id="t1", agent_name="oracle",
                 reward=1.0, outcome="solved", steps_used=3, tamper_attempts=0)
    seed_episode(client, id="e2", task_id="t2", agent_name="oracle",
                 reward=1.0, outcome="solved", steps_used=5, tamper_attempts=0)
    seed_episode(client, id="e3", task_id="t1", agent_name="noop",
                 reward=0.0, outcome="no_change", steps_used=1, tamper_attempts=0)
    seed_episode(client, id="e4", task_id="t2", agent_name="noop",
                 reward=0.5, outcome="no_change", steps_used=1, tamper_attempts=0)
    seed_episode(client, id="e5", task_id="t1", agent_name="tamper",
                 reward=0.0, outcome="no_change", steps_used=6, tamper_attempts=5)
    return client


# --- leaderboard -------------------------------------------------------------


def test_leaderboard_is_empty_with_no_episodes(client) -> None:
    assert client.get("/api/leaderboard").json() == []


def test_leaderboard_has_one_row_per_agent(seeded) -> None:
    rows = seeded.get("/api/leaderboard").json()
    assert len(rows) == 3


def test_leaderboard_is_ordered_by_mean_reward(seeded) -> None:
    labels = [row["label"] for row in seeded.get("/api/leaderboard").json()]
    assert labels[0] == "oracle"
    assert labels.index("noop") < labels.index("tamper")


def test_leaderboard_oracle_numbers_are_exact(seeded) -> None:
    rows = {row["label"]: row for row in seeded.get("/api/leaderboard").json()}
    oracle = rows["oracle"]
    assert oracle["episodes"] == 2
    assert oracle["mean_reward"] == 1.0
    assert oracle["solve_rate"] == 1.0
    assert oracle["mean_steps"] == 4.0
    assert oracle["tamper_rate"] == 0.0


def test_leaderboard_noop_numbers_are_exact(seeded) -> None:
    rows = {row["label"]: row for row in seeded.get("/api/leaderboard").json()}
    noop = rows["noop"]
    assert noop["episodes"] == 2
    assert noop["mean_reward"] == 0.25  # (0.0 + 0.5) / 2
    assert noop["solve_rate"] == 0.0
    assert noop["mean_steps"] == 1.0


def test_leaderboard_tamper_rate_counts_episodes_not_attempts(seeded) -> None:
    """Five blocked attempts in one episode is a tamper rate of 1.0, not 5.0."""
    rows = {row["label"]: row for row in seeded.get("/api/leaderboard").json()}
    assert rows["tamper"]["tamper_rate"] == 1.0
    assert rows["tamper"]["episodes"] == 1


def test_the_tamper_agent_never_outscores_noop(seeded) -> None:
    """The headline anti-reward-hacking claim, asserted on real stored data."""
    rows = {row["label"]: row for row in seeded.get("/api/leaderboard").json()}
    assert rows["tamper"]["mean_reward"] <= rows["noop"]["mean_reward"]


def test_the_model_is_part_of_the_agent_identity(client) -> None:
    """Two models behind one agent name must not share a leaderboard row."""
    seed_task(client, "t1")
    seed_episode(client, id="a", task_id="t1", agent_name="llm",
                 model="claude-sonnet-5-5", reward=1.0, outcome="solved")
    seed_episode(client, id="b", task_id="t1", agent_name="llm",
                 model="claude-haiku-4-5", reward=0.0, outcome="wrong_fix")

    rows = client.get("/api/leaderboard").json()
    labels = sorted(row["label"] for row in rows)
    assert labels == ["llm (claude-haiku-4-5)", "llm (claude-sonnet-5-5)"]
    assert all(row["episodes"] == 1 for row in rows)


def test_an_agent_with_no_model_is_labelled_by_name_alone(seeded) -> None:
    rows = {row["label"]: row for row in seeded.get("/api/leaderboard").json()}
    assert rows["oracle"]["model"] is None


# --- matrix ------------------------------------------------------------------


def test_matrix_is_empty_with_no_episodes(client) -> None:
    assert client.get("/api/matrix").json() == []


def test_matrix_has_one_cell_per_task_and_agent(seeded) -> None:
    cells = seeded.get("/api/matrix").json()
    # t1 has all three agents, t2 has oracle and noop.
    assert len(cells) == 5


def test_matrix_cell_values_are_exact(seeded) -> None:
    cells = {(c["task_id"], c["label"]): c for c in seeded.get("/api/matrix").json()}

    assert cells[("t1", "oracle")]["solve_rate"] == 1.0
    assert cells[("t1", "oracle")]["mean_reward"] == 1.0
    assert cells[("t1", "oracle")]["n"] == 1

    assert cells[("t2", "noop")]["solve_rate"] == 0.0
    assert cells[("t2", "noop")]["mean_reward"] == 0.5

    assert cells[("t1", "tamper")]["mean_reward"] == 0.0


def test_matrix_cells_split_the_agent_name_from_the_model(client) -> None:
    """The dashboard lays the two out separately. Joined into one string, a long
    model id stretches its whole column and strands the numbers."""
    seed_task(client, "t1")
    seed_episode(client, id="g1", task_id="t1", agent_name="gemini",
                 model="gemini-3.5-flash-lite", reward=1.0, outcome="solved")

    cell = client.get("/api/matrix").json()[0]
    assert cell["agent_name"] == "gemini"
    assert cell["model"] == "gemini-3.5-flash-lite"
    # The joined label stays, so nothing that used it breaks.
    assert cell["label"] == "gemini (gemini-3.5-flash-lite)"


def test_matrix_model_is_null_for_a_scripted_agent(seeded) -> None:
    cells = {c["label"]: c for c in seeded.get("/api/matrix").json()}
    assert cells["oracle"]["model"] is None
    assert cells["oracle"]["agent_name"] == "oracle"


def test_matrix_has_no_cell_for_a_pair_with_no_episodes(seeded) -> None:
    cells = {(c["task_id"], c["label"]) for c in seeded.get("/api/matrix").json()}
    assert ("t2", "tamper") not in cells


def test_matrix_averages_repeated_trials(client) -> None:
    seed_task(client, "t1")
    seed_episode(client, id="x1", task_id="t1", agent_name="llm",
                 model="m", trial=0, reward=1.0, outcome="solved")
    seed_episode(client, id="x2", task_id="t1", agent_name="llm",
                 model="m", trial=1, reward=0.0, outcome="wrong_fix")

    cell = client.get("/api/matrix").json()[0]
    assert cell["n"] == 2
    assert cell["mean_reward"] == 0.5
    assert cell["solve_rate"] == 0.5


# --- totals ------------------------------------------------------------------


def test_stats_on_an_empty_database(client) -> None:
    assert client.get("/api/stats").json() == {
        "tasks": 0,
        "episodes": 0,
        "agents": 0,
    }


def test_stats_counts_tasks_episodes_and_agents(seeded) -> None:
    assert seeded.get("/api/stats").json() == {
        "tasks": 2,
        "episodes": 5,
        "agents": 3,
    }


def test_stats_counts_a_task_with_no_episodes(client) -> None:
    seed_task(client, "t1")
    body = client.get("/api/stats").json()
    assert body["tasks"] == 1
    assert body["episodes"] == 0
    assert body["agents"] == 0


def test_stats_agent_count_matches_the_leaderboard_rows(client) -> None:
    """The header number and the table below it must never disagree."""
    seed_task(client, "t1")
    seed_episode(client, id="a", task_id="t1", agent_name="llm", model="m1")
    seed_episode(client, id="b", task_id="t1", agent_name="llm", model="m2")
    seed_episode(client, id="c", task_id="t1", agent_name="noop", model=None)

    assert client.get("/api/stats").json()["agents"] == 3
    assert len(client.get("/api/leaderboard").json()) == 3
