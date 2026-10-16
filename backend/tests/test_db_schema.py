"""Schema isolation: what lets AgentGym share a Postgres with another project.

Our table names — tasks, episodes, steps — are generic enough to collide, and
`create_all` skips a table that already exists rather than failing, so a
collision would silently bind our models to someone else's table. Putting our
tables in a dedicated schema removes that possibility.

The schema name reaches a CREATE SCHEMA statement, which cannot take a bind
parameter, so these tests care a lot about what is accepted as a name.
"""

from __future__ import annotations

import pytest
from app.config import Settings
from pydantic import ValidationError


def make(**kwargs: object) -> Settings:
    """A Settings that ignores any .env file the developer happens to have."""
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


# --- what counts as a usable schema name -------------------------------------


@pytest.mark.parametrize(
    "name",
    ["agentgym", "agent_gym", "_private", "a", "s123", "A" * 63],
)
def test_a_plain_identifier_is_accepted(name: str) -> None:
    assert make(db_schema=name).db_schema == name


def test_the_default_is_empty_meaning_the_default_schema() -> None:
    assert make().db_schema == ""


def test_surrounding_whitespace_is_trimmed_not_rejected() -> None:
    assert make(db_schema="  agentgym  ").db_schema == "agentgym"


# --- what must not get through ----------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        'agentgym"; DROP TABLE tasks; --',   # the obvious one
        "public.tasks",                      # qualified, not an identifier
        "agent-gym",                         # hyphen is not valid unquoted
        "9lives",                            # cannot start with a digit
        "has space",
        "has\"quote",
        "tab\there",
        "newline\nhere",
        "A" * 64,                            # past Postgres' identifier limit
    ],
)
def test_anything_that_is_not_a_plain_identifier_is_refused(name: str) -> None:
    with pytest.raises(ValidationError):
        make(db_schema=name)


def test_the_injection_attempt_is_refused_before_it_reaches_sql() -> None:
    """The guard has to be at the settings boundary, not at the call site."""
    with pytest.raises(ValidationError) as caught:
        make(db_schema='x"; CREATE TABLE evil(i int); --')
    assert "plain identifier" in str(caught.value)


# --- how it interacts with the two databases we support ----------------------


def test_sqlite_ignores_the_schema_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite has no schemas; asking for one must not break local development."""
    import app.db as db

    monkeypatch.setattr(db.settings, "db_schema", "agentgym")
    monkeypatch.setattr(db.settings, "database_url", "sqlite:///./x.db")
    assert db._schema() is None


def test_postgres_uses_the_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.db as db

    monkeypatch.setattr(db.settings, "db_schema", "agentgym")
    monkeypatch.setattr(
        db.settings, "database_url", "postgresql+psycopg://u:p@host/db"
    )
    assert db._schema() == "agentgym"


def test_an_unset_schema_means_the_default_even_on_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.db as db

    monkeypatch.setattr(db.settings, "db_schema", "")
    monkeypatch.setattr(
        db.settings, "database_url", "postgresql+psycopg://u:p@host/db"
    )
    assert db._schema() is None


# --- auto_create_tables: the serverless-correctness flag ---------------------


def test_tables_are_created_on_startup_by_default() -> None:
    """A long-running server and a fresh clone both want this on."""
    assert make().auto_create_tables is True


def test_table_creation_can_be_turned_off() -> None:
    """On serverless the startup hook runs per cold start, so it must be
    possible to skip the CREATE SCHEMA / reflect round trip."""
    assert make(auto_create_tables=False).auto_create_tables is False


def test_the_flag_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTO_CREATE_TABLES", "false")
    assert Settings(_env_file=None).auto_create_tables is False  # type: ignore[call-arg]
