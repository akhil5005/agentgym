"""Backend test fixtures.

The environment variables below are set at *import* time, not inside a fixture.
`app.config` reads its settings when it is first imported, and pytest imports
this conftest before any test module, so this is the only place early enough to
point the app at a throwaway database instead of the real `agentgym.db`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="agentgym-test-db-"))
os.environ["ENV"] = "dev"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEMP_DIR / 'test.db').as_posix()}"
os.environ["INGEST_API_KEY"] = "test-key"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:3000"

import pytest  # noqa: E402 - must come after the env vars above
from fastapi.testclient import TestClient  # noqa: E402

API_KEY = "test-key"
AUTH = {"X-API-Key": API_KEY}


@pytest.fixture
def client() -> Any:
    """A TestClient against an empty database.

    Every test starts from nothing, so no test can depend on rows another one
    happened to leave behind.
    """
    from app.db import Base, engine
    from app.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client


# --- payload builders --------------------------------------------------------


def task_payload(**overrides: Any) -> dict[str, Any]:
    """A valid task body, with any field overridable."""
    payload = {
        "title": "Moving average over a sliding window",
        "difficulty": "easy",
        "category": "off-by-one",
        "description": "Fix moving_average so it returns every window.",
        "max_steps": 15,
    }
    payload.update(overrides)
    return payload


def step_payload(index: int = 0, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "index": index,
        "action_type": "list_files",
        "action": {"type": "list_files"},
        "observation": "src/stats.py\ntests/test_visible.py",
        "reward": 0.0,
        "error": False,
        "tamper_blocked": False,
        "created_at": "2026-10-12T10:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def episode_payload(**overrides: Any) -> dict[str, Any]:
    """A valid episode body with a two-step trajectory."""
    payload: dict[str, Any] = {
        "id": "episode-1",
        "task_id": "01_moving_average",
        "agent_name": "oracle",
        "model": None,
        "trial": 0,
        "reward": 1.0,
        "outcome": "solved",
        "steps_used": 2,
        "tamper_attempts": 0,
        "tests_passed": 10,
        "tests_total": 10,
        "started_at": "2026-10-12T10:00:00+00:00",
        "finished_at": "2026-10-12T10:00:09+00:00",
        "steps": [
            step_payload(0),
            step_payload(
                1,
                action_type="submit",
                action={"type": "submit"},
                observation="passed 10/10",
                reward=1.0,
            ),
        ],
    }
    payload.update(overrides)
    return payload


def seed_task(client: Any, task_id: str = "01_moving_average", **overrides: Any) -> None:
    """Create a task, failing the test loudly if that did not work."""
    response = client.put(
        f"/api/tasks/{task_id}", json=task_payload(**overrides), headers=AUTH
    )
    assert response.status_code == 200, response.text


def seed_episode(client: Any, **overrides: Any) -> dict[str, Any]:
    """Ingest an episode, failing the test loudly if that did not work."""
    payload = episode_payload(**overrides)
    response = client.post("/api/episodes", json=payload, headers=AUTH)
    assert response.status_code == 201, response.text
    return payload
