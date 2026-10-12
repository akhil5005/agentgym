"""Task endpoints: upsert, list with stats, fetch one."""

from __future__ import annotations

from conftest import AUTH, seed_episode, seed_task, task_payload


def test_upsert_creates_a_task(client) -> None:
    response = client.put("/api/tasks/t1", json=task_payload(), headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "t1"
    assert body["difficulty"] == "easy"
    assert body["episodes"] == 0


def test_upsert_is_idempotent(client) -> None:
    """`sync-tasks` is run repeatedly, so a second PUT must not duplicate."""
    client.put("/api/tasks/t1", json=task_payload(), headers=AUTH)
    client.put("/api/tasks/t1", json=task_payload(), headers=AUTH)
    assert len(client.get("/api/tasks").json()) == 1


def test_upsert_replaces_the_fields(client) -> None:
    client.put("/api/tasks/t1", json=task_payload(), headers=AUTH)
    client.put(
        "/api/tasks/t1",
        json=task_payload(title="A better title", difficulty="hard"),
        headers=AUTH,
    )
    body = client.get("/api/tasks/t1").json()
    assert body["title"] == "A better title"
    assert body["difficulty"] == "hard"


def test_an_invalid_difficulty_is_rejected(client) -> None:
    response = client.put(
        "/api/tasks/t1", json=task_payload(difficulty="impossible"), headers=AUTH
    )
    assert response.status_code == 422


def test_a_zero_max_steps_is_rejected(client) -> None:
    response = client.put(
        "/api/tasks/t1", json=task_payload(max_steps=0), headers=AUTH
    )
    assert response.status_code == 422


def test_an_empty_title_is_rejected(client) -> None:
    response = client.put("/api/tasks/t1", json=task_payload(title=""), headers=AUTH)
    assert response.status_code == 422


def test_list_is_empty_to_start_with(client) -> None:
    assert client.get("/api/tasks").json() == []


def test_list_is_ordered_by_id(client) -> None:
    for task_id in ("03_c", "01_a", "02_b"):
        seed_task(client, task_id)
    ids = [task["id"] for task in client.get("/api/tasks").json()]
    assert ids == ["01_a", "02_b", "03_c"]


def test_a_task_with_no_episodes_reports_zeroes_not_nulls(client) -> None:
    """SQL averages are NULL with no rows; the API must not pass that through."""
    seed_task(client, "t1")
    body = client.get("/api/tasks/t1").json()
    assert body["episodes"] == 0
    assert body["solve_rate"] == 0.0
    assert body["mean_reward"] == 0.0
    assert body["mean_steps"] == 0.0


def test_task_stats_are_computed_from_its_episodes(client) -> None:
    seed_task(client, "t1")
    seed_episode(client, id="e1", task_id="t1", reward=1.0, outcome="solved",
                 steps_used=3)
    seed_episode(client, id="e2", task_id="t1", reward=0.5, outcome="partial",
                 steps_used=7)

    body = client.get("/api/tasks/t1").json()
    assert body["episodes"] == 2
    assert body["mean_reward"] == 0.75
    assert body["mean_steps"] == 5.0
    assert body["solve_rate"] == 0.5  # one of two episodes solved


def test_task_stats_ignore_other_tasks_episodes(client) -> None:
    seed_task(client, "t1")
    seed_task(client, "t2")
    seed_episode(client, id="e1", task_id="t1", reward=1.0, outcome="solved")
    seed_episode(client, id="e2", task_id="t2", reward=0.0, outcome="wrong_fix")

    by_id = {task["id"]: task for task in client.get("/api/tasks").json()}
    assert by_id["t1"]["mean_reward"] == 1.0
    assert by_id["t2"]["mean_reward"] == 0.0


def test_a_missing_task_is_a_404(client) -> None:
    response = client.get("/api/tasks/nope")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_the_task_response_carries_no_grading_details(client) -> None:
    """Hidden tests and their count must never reach the API."""
    seed_task(client, "t1")
    body = client.get("/api/tasks/t1").json()
    assert "hidden_test_count" not in body
    assert "hidden_tests" not in body
    assert "solution" not in body
