"""Database engine, session factory and the FastAPI dependency.

SQLAlchemy 2.x typed style: `DeclarativeBase` plus `Mapped` / `mapped_column`
annotations, so the models are checkable by a type checker rather than being
untyped class attributes.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def _schema() -> str | None:
    """The Postgres schema our tables live in, or None for the default.

    SQLite has no schemas, so the setting is ignored there rather than
    producing a confusing error on a developer machine.
    """
    if not settings.db_schema:
        return None
    if settings.database_url.startswith("sqlite"):
        return None
    return settings.db_schema


class Base(DeclarativeBase):
    """Parent class for every table."""

    # Qualifying the metadata is what actually isolates us: every table, index
    # and foreign key is then addressed as <schema>.<table>, so a project
    # sharing this database cannot be reached by our queries and we cannot be
    # reached by theirs.
    metadata = MetaData(schema=_schema())


def _engine_kwargs(url: str) -> dict[str, object]:
    """Connection arguments that differ between SQLite and Postgres."""
    if url.startswith("sqlite"):
        # SQLite refuses cross-thread use by default, and FastAPI serves
        # requests on a thread pool, so each connection would be rejected.
        return {"connect_args": {"check_same_thread": False}}
    # A hosted Postgres closes idle connections; recycling avoids handing a
    # dead one to the next request.
    return {"pool_pre_ping": True, "pool_recycle": 300}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_tables() -> None:
    """Create our schema if configured, then any missing tables.

    No migration tool: this store is append-only results data, so the simplest
    thing that works is enough. The trade-off is that *changing* a column later
    means dropping the table or adding Alembic. Noted in docs/DECISIONS.md.

    `create_all` only ever adds what is missing — it never drops or alters an
    existing table, so running this against a database that already holds our
    data is a no-op, and running it against someone else's schema is
    impossible once `db_schema` is set.
    """
    schema = _schema()
    if schema is not None:
        with engine.begin() as connection:
            # Validated as a plain identifier in config.py: CREATE SCHEMA takes
            # no bind parameters, so the guard has to live upstream.
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
