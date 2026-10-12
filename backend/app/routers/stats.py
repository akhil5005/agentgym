"""Aggregate endpoints: leaderboard, task-by-agent matrix, overall totals.

Every number here comes from a SQL aggregate. Loading episodes into Python and
counting them in a loop would work on a laptop with 30 rows and fall over at
30,000.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import case, distinct, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Episode, Task
from app.schemas import LeaderboardRow, MatrixCell, Stats

router = APIRouter(tags=["stats"])


def agent_label(agent_name: str, model: str | None) -> str:
    """How an agent is named on the leaderboard.

    The model is part of the identity: "llm" running Sonnet and "llm" running
    Haiku are different competitors and must not share a row.
    """
    return f"{agent_name} ({model})" if model else agent_name


#: Reusable aggregate columns, so the leaderboard and the matrix cannot drift
#: apart in how they define "solve rate" or "mean reward".
_EPISODES = func.count(Episode.id)
_SOLVED = func.sum(case((Episode.outcome == "solved", 1), else_=0))
_TAMPERED = func.sum(case((Episode.tamper_attempts > 0, 1), else_=0))


@router.get("/leaderboard", response_model=list[LeaderboardRow])
def leaderboard(session: Session = Depends(get_session)) -> list[LeaderboardRow]:
    """One row per agent label, best mean reward first."""
    rows = session.execute(
        select(
            Episode.agent_name,
            Episode.model,
            _EPISODES.label("episodes"),
            func.avg(Episode.reward).label("mean_reward"),
            _SOLVED.label("solved"),
            func.avg(Episode.steps_used).label("mean_steps"),
            _TAMPERED.label("tampered"),
        )
        .group_by(Episode.agent_name, Episode.model)
        .order_by(func.avg(Episode.reward).desc())
    ).all()

    return [
        LeaderboardRow(
            agent_name=row.agent_name,
            model=row.model,
            label=agent_label(row.agent_name, row.model),
            episodes=int(row.episodes),
            mean_reward=round(float(row.mean_reward or 0.0), 4),
            solve_rate=round(int(row.solved or 0) / int(row.episodes), 4),
            mean_steps=round(float(row.mean_steps or 0.0), 2),
            # The share of this agent's episodes in which it tried to cheat at
            # least once, not the number of attempts.
            tamper_rate=round(int(row.tampered or 0) / int(row.episodes), 4),
        )
        for row in rows
        if int(row.episodes) > 0
    ]


@router.get("/matrix", response_model=list[MatrixCell])
def matrix(session: Session = Depends(get_session)) -> list[MatrixCell]:
    """One cell per (task, agent label) pair that has at least one episode."""
    rows = session.execute(
        select(
            Episode.task_id,
            Episode.agent_name,
            Episode.model,
            _EPISODES.label("episodes"),
            func.avg(Episode.reward).label("mean_reward"),
            _SOLVED.label("solved"),
        )
        .group_by(Episode.task_id, Episode.agent_name, Episode.model)
        .order_by(Episode.task_id, Episode.agent_name)
    ).all()

    return [
        MatrixCell(
            task_id=row.task_id,
            label=agent_label(row.agent_name, row.model),
            n=int(row.episodes),
            solve_rate=round(int(row.solved or 0) / int(row.episodes), 4),
            mean_reward=round(float(row.mean_reward or 0.0), 4),
        )
        for row in rows
        if int(row.episodes) > 0
    ]


@router.get("/stats", response_model=Stats)
def stats(session: Session = Depends(get_session)) -> Stats:
    """Totals for the dashboard header."""
    tasks = session.scalar(select(func.count(Task.id))) or 0
    episodes = session.scalar(select(func.count(Episode.id))) or 0
    # Count distinct (agent, model) pairs, to match the leaderboard's rows.
    agents = (
        session.scalar(
            select(func.count()).select_from(
                select(distinct(Episode.agent_name), Episode.model)
                .group_by(Episode.agent_name, Episode.model)
                .subquery()
            )
        )
        or 0
    )
    return Stats(tasks=int(tasks), episodes=int(episodes), agents=int(agents))
