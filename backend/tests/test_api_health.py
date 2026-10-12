"""Health check, auth, and the settings rules."""

from __future__ import annotations

import pytest
from conftest import AUTH, episode_payload, task_payload

from app.config import Settings


def test_health_is_public(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_docs_are_served(client) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


# --- authentication ----------------------------------------------------------


def test_upsert_task_without_a_key_is_rejected(client) -> None:
    response = client.put("/api/tasks/t1", json=task_payload())
    assert response.status_code == 401


def test_upsert_task_with_a_wrong_key_is_rejected(client) -> None:
    response = client.put(
        "/api/tasks/t1", json=task_payload(), headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401


def test_ingest_episode_without_a_key_is_rejected(client) -> None:
    response = client.post("/api/episodes", json=episode_payload())
    assert response.status_code == 401


def test_a_wrong_key_does_not_write_anything(client) -> None:
    """A rejected write must leave the database untouched."""
    client.put("/api/tasks/t1", json=task_payload(), headers={"X-API-Key": "nope"})
    assert client.get("/api/tasks").json() == []


@pytest.mark.parametrize("path", ["/api/tasks", "/api/episodes", "/api/leaderboard",
                                 "/api/matrix", "/api/stats"])
def test_read_endpoints_need_no_key(client, path: str) -> None:
    """The dashboard is meant to be shareable, so reads are public."""
    assert client.get(path).status_code == 200


def test_writes_work_with_the_right_key(client) -> None:
    response = client.put("/api/tasks/t1", json=task_payload(), headers=AUTH)
    assert response.status_code == 200


# --- settings ----------------------------------------------------------------


def test_postgres_url_is_rewritten_to_psycopg() -> None:
    """Providers hand out `postgres://`; we install the psycopg 3 driver."""
    settings = Settings(database_url="postgres://user:pw@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pw@host:5432/db"


def test_postgresql_url_is_also_rewritten() -> None:
    settings = Settings(database_url="postgresql://user:pw@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pw@host:5432/db"


def test_sqlite_url_is_left_alone() -> None:
    settings = Settings(database_url="sqlite:///./agentgym.db")
    assert settings.database_url == "sqlite:///./agentgym.db"


def test_production_refuses_to_start_with_the_default_key() -> None:
    """Loud failure at startup beats silently accepting a public key."""
    with pytest.raises(ValueError, match="INGEST_API_KEY"):
        Settings(env="prod", ingest_api_key="dev-key")


def test_production_refuses_an_empty_key() -> None:
    with pytest.raises(ValueError, match="INGEST_API_KEY"):
        Settings(env="prod", ingest_api_key="")


def test_production_starts_with_a_real_key() -> None:
    settings = Settings(env="prod", ingest_api_key="a-real-secret")
    assert settings.is_dev is False


def test_dev_allows_localhost_as_an_origin() -> None:
    settings = Settings(env="dev", frontend_origin="https://example.com")
    assert "http://localhost:3000" in settings.allowed_origins


def test_production_does_not_allow_localhost() -> None:
    """A deployed backend must not trust a page served from a laptop."""
    settings = Settings(
        env="prod", ingest_api_key="secret", frontend_origin="https://example.com"
    )
    assert settings.allowed_origins == ["https://example.com"]
