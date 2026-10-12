"""Database tables: tasks, episodes and the steps inside them.

Three tables with one shape each. Columns that the dashboard filters or groups
by are indexed; nothing else is.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Task(Base):
    """Public metadata for one task.

    Deliberately holds no hidden tests, no reference solution and no hidden test
    count. Those stay on the machine that runs episodes.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    max_steps: Mapped[int] = mapped_column(Integer)

    episodes: Mapped[list["Episode"]] = relationship(back_populates="task")


class Episode(Base):
    """One agent's complete attempt at one task."""

    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("tasks.id"), index=True
    )
    agent_name: Mapped[str] = mapped_column(String(100), index=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    trial: Mapped[int] = mapped_column(Integer, default=0)

    reward: Mapped[float] = mapped_column(Float)
    outcome: Mapped[str] = mapped_column(String(30), index=True)
    steps_used: Mapped[int] = mapped_column(Integer)
    tamper_attempts: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_total: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    task: Mapped["Task"] = relationship(back_populates="episodes")
    steps: Mapped[list["Step"]] = relationship(
        back_populates="episode",
        # Deleting an episode must take its steps with it, or the steps table
        # fills up with rows pointing at nothing.
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Step.idx",
    )

    __table_args__ = (
        # The leaderboard groups by agent and model together, and the matrix
        # groups by task as well.
        Index("ix_episodes_agent_model", "agent_name", "model"),
        Index("ix_episodes_task_agent", "task_id", "agent_name"),
    )


class Step(Base):
    """One action in a trajectory, as replayed in the dashboard."""

    __tablename__ = "steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("episodes.id", ondelete="CASCADE"),
        index=True,
    )
    idx: Mapped[int] = mapped_column(Integer)
    action_type: Mapped[str] = mapped_column(String(30))
    # The action as JSON text. Stored as text rather than a JSON column so the
    # same code works unchanged on SQLite and Postgres.
    action_json: Mapped[str] = mapped_column(Text)
    observation: Mapped[str] = mapped_column(Text)
    reward: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[bool] = mapped_column(Boolean, default=False)
    tamper_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    episode: Mapped["Episode"] = relationship(back_populates="steps")
