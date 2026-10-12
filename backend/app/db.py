"""Database engine, session factory and the FastAPI dependency.

SQLAlchemy 2.x typed style: `DeclarativeBase` plus `Mapped` / `mapped_column`
annotations, so the models are checkable by a type checker rather than being
untyped class attributes.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Parent class for every table."""


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
    """Create any missing tables.

    No migration tool: this store is append-only results data, so the simplest
    thing that works is enough. The trade-off is that *changing* a column later
    means dropping the table or adding Alembic. Noted in docs/DECISIONS.md.
    """
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
