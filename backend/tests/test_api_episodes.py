"""Episode endpoints: ingest, duplicate handling, filters, paging, detail."""

from __future__ import annotations

from conftest import (
    AUTH,
    episode_payload,
    seed_episode,
    seed_task,
    step_payload,
)

from app.schemas import MAX_TEXT_CHARS


def test_ingest_stores_an_episode(client) -> None:
    seed_task(client)
    response = client.post("/api/episodes", json=episode_payload(), headers=AUTH)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "episode-1"
    assert body["reward"] == 1.0
    # The list representation leaves steps out.
    assert "steps" not in body


def test_a_duplicate_id_returns_409(client) -> None:
    """Re-uploading a run file must be safe, not double-count."""
    seed_task(client)
    seed_episode(client)
    response = client.post("/api/episodes", json=episode_payload(), headers=AUTH)
    assert response.status_code == 409
    assert len(client.get("/api/episodes").json()) == 1


def test_an_unknown_task_gives_a_helpful_400(client) -> None:
    response = client.post(
        "/api/episodes", json=episode_payload(task_id="never_synced"), headers=AUTH
    )
    assert response.status_code == 400
    assert "sync-tasks" in response.json()["detail"]


def test_a_reward_above_one_is_rejected(client) -> None:
    """Reward is a fraction of hidden tests passed, so it cannot exceed 1."""
    seed_task(client)
    response = client.post(
        "/api/episodes", json=episode_payload(reward=1.5), headers=AUTH
    )
    assert response.status_code == 422


def test_a_negative_reward_is_rejected(client) -> None:
    seed_task(client)
    response = client.post(
        "/api/episodes", json=episode_payload(reward=-0.1), headers=AUTH
    )
    assert response.status_code == 422


def test_an_unknown_outcome_is_rejected(client) -> None:
    seed_task(client)
    response = client.post(
        "/api/episodes", json=episode_payload(outcome="vibes"), headers=AUTH
    )
    assert response.status_code == 422


def test_too_many_steps_is_rejected(client) -> None:
    seed_task(client)
    payload = episode_payload(steps=[step_payload(i) for i in range(101)])
    response = client.post("/api/episodes", json=payload, headers=AUTH)
    assert response.status_code == 422


def test_exactly_one_hundred_steps_is_accepted(client) -> None:
    seed_task(client)
    payload = episode_payload(steps=[step_payload(i) for i in range(100)])
    response = client.post("/api/episodes", json=payload, headers=AUTH)
    assert response.status_code == 201


def test_an_oversized_observation_is_truncated_by_the_server(client) -> None:
    """The backend does not trust its client, even an authenticated one."""
    seed_task(client)
    huge = "x" * (MAX_TEXT_CHARS + 5_000)
    payload = episode_payload(steps=[step_payload(0, observation=huge)])
    client.post("/api/episodes", json=payload, headers=AUTH)

    stored = client.get("/api/episodes/episode-1").json()["steps"][0]["observation"]
    assert len(stored) < MAX_TEXT_CHARS + 100
    assert "truncated by the server" in stored


def test_an_episode_with_no_steps_is_accepted(client) -> None:
    seed_task(client)
    response = client.post(
        "/api/episodes", json=episode_payload(steps=[]), headers=AUTH
    )
    assert response.status_code == 201
    assert client.get("/api/episodes/episode-1").json()["steps"] == []


# --- listing, filtering, paging ----------------------------------------------


def _seed_three(client) -> None:
    seed_task(client, "t1")
    seed_task(client, "t2")
    seed_episode(
        client, id="e1", task_id="t1", agent_name="oracle", outcome="solved",
        reward=1.0, finished_at="2026-10-12T10:00:01+00:00",
    )
    seed_episode(
        client, id="e2", task_id="t1", agent_name="noop", outcome="no_change",
        reward=0.2, finished_at="2026-10-12T10:00:02+00:00",
    )
    seed_episode(
        client, id="e3", task_id="t2", agent_name="noop", outcome="no_change",
        reward=0.3, finished_at="2026-10-12T10:00:03+00:00",
    )


def test_list_is_newest_first(client) -> None:
    _seed_three(client)
    ids = [episode["id"] for episode in client.get("/api/episodes").json()]
    assert ids == ["e3", "e2", "e1"]


def test_filter_by_task(client) -> None:
    _seed_three(client)
    ids = [e["id"] for e in client.get("/api/episodes?task_id=t1").json()]
    assert sorted(ids) == ["e1", "e2"]


def test_filter_by_agent(client) -> None:
    _seed_three(client)
    ids = [e["id"] for e in client.get("/api/episodes?agent=noop").json()]
    assert sorted(ids) == ["e2", "e3"]


def test_filter_by_outcome(client) -> None:
    _seed_three(client)
    ids = [e["id"] for e in client.get("/api/episodes?outcome=solved").json()]
    assert ids == ["e1"]


def test_filters_combine(client) -> None:
    _seed_three(client)
    ids = [e["id"] for e in client.get("/api/episodes?task_id=t1&agent=noop").json()]
    assert ids == ["e2"]


def test_a_filter_matching_nothing_returns_an_empty_list(client) -> None:
    _seed_three(client)
    assert client.get("/api/episodes?agent=nobody").json() == []


def test_limit_and_offset_page_through_results(client) -> None:
    _seed_three(client)
    first = client.get("/api/episodes?limit=2&offset=0").json()
    second = client.get("/api/episodes?limit=2&offset=2").json()
    assert [e["id"] for e in first] == ["e3", "e2"]
    assert [e["id"] for e in second] == ["e1"]


def test_the_default_limit_is_fifty(client) -> None:
    seed_task(client, "t1")
    for index in range(60):
        seed_episode(
            client,
            id=f"e{index:03d}",
            task_id="t1",
            finished_at=f"2026-10-12T10:{index // 60:02d}:{index % 60:02d}+00:00",
        )
    assert len(client.get("/api/episodes").json()) == 50


def test_a_limit_over_the_maximum_is_rejected(client) -> None:
    assert client.get("/api/episodes?limit=201").status_code == 422


def test_a_zero_limit_is_rejected(client) -> None:
    assert client.get("/api/episodes?limit=0").status_code == 422


def test_a_negative_offset_is_rejected(client) -> None:
    assert client.get("/api/episodes?offset=-1").status_code == 422


# --- detail ------------------------------------------------------------------


def test_detail_returns_steps_in_order(client) -> None:
    seed_task(client)
    # Upload the steps out of order on purpose: the replay viewer must still
    # play them forwards.
    payload = episode_payload(
        steps=[
            step_payload(2, action_type="submit", action={"type": "submit"}),
            step_payload(0, action_type="list_files"),
            step_payload(1, action_type="read_file",
                         action={"type": "read_file", "path": "src/stats.py"}),
        ]
    )
    client.post("/api/episodes", json=payload, headers=AUTH)

    steps = client.get("/api/episodes/episode-1").json()["steps"]
    assert [step["index"] for step in steps] == [0, 1, 2]
    assert [step["action_type"] for step in steps] == [
        "list_files",
        "read_file",
        "submit",
    ]


def test_detail_round_trips_the_action_object(client) -> None:
    seed_task(client)
    action = {"type": "write_file", "path": "src/stats.py", "content": "x = 1\n"}
    payload = episode_payload(
        steps=[step_payload(0, action_type="write_file", action=action)]
    )
    client.post("/api/episodes", json=payload, headers=AUTH)

    stored = client.get("/api/episodes/episode-1").json()["steps"][0]["action"]
    assert stored == action


def test_detail_reports_tamper_blocked_steps(client) -> None:
    """The replay viewer badges these, so the flag has to survive the round trip."""
    seed_task(client)
    payload = episode_payload(
        tamper_attempts=1,
        steps=[
            step_payload(
                0,
                action_type="write_file",
                action={"type": "write_file", "path": "tests/test_visible.py"},
                observation="BLOCKED: the tests/ folder is read-only",
                tamper_blocked=True,
            )
        ],
    )
    client.post("/api/episodes", json=payload, headers=AUTH)

    body = client.get("/api/episodes/episode-1").json()
    assert body["tamper_attempts"] == 1
    assert body["steps"][0]["tamper_blocked"] is True


def test_a_missing_episode_is_a_404(client) -> None:
    response = client.get("/api/episodes/nope")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]
