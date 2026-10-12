"""Task endpoints: upsert one (authenticated), read them with their stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Episode, Task
from app.schemas import TaskIn, TaskOut
from app.security import require_api_key

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_stats_subquery() -> Select:
    """Per-task aggregates, computed by the database rather than in Python.

    Looping over every episode row in Python would mean loading the whole table
    into memory just to count it, which stops working as soon as there are a
    few thousand episodes.
    """
    return (
        select(
            Episode.task_id.label("task_id"),
            func.count(Episode.id).label("episodes"),
            func.avg(Episode.reward).label("mean_reward"),
            func.avg(Episode.steps_used).label("mean_steps"),
            # `case` turns "is this row solved?" into 1/0 so SUM can count them.
            func.sum(case((Episode.outcome == "solved", 1), else_=0)).label("solved"),
        )
        .group_by(Episode.task_id)
        .subquery()
    )


def _to_task_out(task: Task, episodes: int, mean_reward, mean_steps, solved) -> TaskOut:
    """Build the response row, treating "no episodes yet" as zeroes.

    SQL aggregates come back as NULL for a task nobody has attempted, and a
    dashboard showing `null` would just look broken.
    """
    count = int(episodes or 0)
    return TaskOut(
        id=task.id,
        title=task.title,
        difficulty=task.difficulty,
        category=task.category,
        description=task.description,
        max_steps=task.max_steps,
        episodes=count,
        solve_rate=(int(solved or 0) / count) if count else 0.0,
        mean_reward=float(mean_reward or 0.0),
        mean_steps=float(mean_steps or 0.0),
    )


@router.put(
    "/{task_id}",
    response_model=TaskOut,
    dependencies=[Depends(require_api_key)],
    summary="Create or replace one task's metadata",
)
def upsert_task(
    task_id: str, payload: TaskIn, session: Session = Depends(get_session)
) -> TaskOut:
    """Idempotent by design, so `sync-tasks` can be run as often as you like."""
    task = session.get(Task, task_id)
    if task is None:
        task = Task(id=task_id, **payload.model_dump())
        session.add(task)
    else:
        for field, value in payload.model_dump().items():
            setattr(task, field, value)

    session.commit()
    session.refresh(task)
    return _to_task_out(task, 0, 0.0, 0.0, 0)


@router.get("", response_model=list[TaskOut], summary="List tasks with their stats")
def list_tasks(session: Session = Depends(get_session)) -> list[TaskOut]:
    stats = _task_stats_subquery()
    rows = session.execute(
        select(
            Task,
            stats.c.episodes,
            stats.c.mean_reward,
            stats.c.mean_steps,
            stats.c.solved,
        )
        .outerjoin(stats, Task.id == stats.c.task_id)
        .order_by(Task.id)
    ).all()
    return [_to_task_out(*row) for row in rows]


@router.get("/{task_id}", response_model=TaskOut, summary="One task with its stats")
def get_task(task_id: str, session: Session = Depends(get_session)) -> TaskOut:
    stats = _task_stats_subquery()
    row = session.execute(
        select(
            Task,
            stats.c.episodes,
            stats.c.mean_reward,
            stats.c.mean_steps,
            stats.c.solved,
        )
        .outerjoin(stats, Task.id == stats.c.task_id)
        .where(Task.id == task_id)
    ).first()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no task {task_id!r}"
        )
    return _to_task_out(*row)
