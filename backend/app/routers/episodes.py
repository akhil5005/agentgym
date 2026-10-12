"""Episode endpoints: ingest one (authenticated), list them, read one in full."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Episode, Step, Task
from app.schemas import EpisodeDetail, EpisodeIn, EpisodeSummary, StepOut
from app.security import require_api_key

router = APIRouter(prefix="/episodes", tags=["episodes"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@router.post(
    "",
    response_model=EpisodeSummary,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
    summary="Store one episode and its trajectory",
)
def ingest_episode(
    payload: EpisodeIn, session: Session = Depends(get_session)
) -> Episode:
    """Store an episode.

    Returns 409 if the id already exists. That makes re-uploading a run file
    safe: the duplicates are rejected individually instead of either crashing
    or silently doubling every number on the leaderboard.
    """
    if session.get(Episode, payload.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"episode {payload.id!r} has already been uploaded",
        )

    if session.get(Task, payload.task_id) is None:
        # A foreign-key error here would surface as a 500. Saying what to do
        # instead is far more useful.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"unknown task {payload.task_id!r}; "
                f"run 'python -m agentgym.runner sync-tasks' first"
            ),
        )

    episode = Episode(
        **payload.model_dump(exclude={"steps"}),
        steps=[
            Step(
                idx=step.index,
                action_type=step.action_type,
                action_json=json.dumps(step.action, ensure_ascii=False),
                observation=step.observation,
                reward=step.reward,
                error=step.error,
                tamper_blocked=step.tamper_blocked,
                created_at=step.created_at,
            )
            for step in payload.steps
        ],
    )
    session.add(episode)
    session.commit()
    session.refresh(episode)
    return episode


@router.get(
    "",
    response_model=list[EpisodeSummary],
    summary="List episodes, newest first, without their steps",
)
def list_episodes(
    task_id: str | None = Query(default=None),
    agent: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[Episode]:
    """Steps are left out on purpose: a list of 50 trajectories would be huge,
    and no list view shows them."""
    query = select(Episode)
    if task_id:
        query = query.where(Episode.task_id == task_id)
    if agent:
        query = query.where(Episode.agent_name == agent)
    if outcome:
        query = query.where(Episode.outcome == outcome)

    # `id` breaks ties so paging is stable when episodes share a timestamp;
    # without it, the same row could appear on two pages.
    query = query.order_by(Episode.finished_at.desc(), Episode.id.desc())
    return list(session.scalars(query.limit(limit).offset(offset)))


@router.get(
    "/{episode_id}",
    response_model=EpisodeDetail,
    summary="One episode with its full trajectory",
)
def get_episode(
    episode_id: str, session: Session = Depends(get_session)
) -> EpisodeDetail:
    episode = session.scalar(
        select(Episode)
        # Load the steps in one extra query rather than one per step.
        .options(selectinload(Episode.steps))
        .where(Episode.id == episode_id)
    )
    if episode is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"no episode {episode_id!r}"
        )

    return EpisodeDetail(
        id=episode.id,
        task_id=episode.task_id,
        agent_name=episode.agent_name,
        model=episode.model,
        trial=episode.trial,
        reward=episode.reward,
        outcome=episode.outcome,
        steps_used=episode.steps_used,
        tamper_attempts=episode.tamper_attempts,
        tests_passed=episode.tests_passed,
        tests_total=episode.tests_total,
        started_at=episode.started_at,
        finished_at=episode.finished_at,
        steps=[
            StepOut(
                index=step.idx,
                action_type=step.action_type,
                action=_load_action(step.action_json),
                observation=step.observation,
                reward=step.reward,
                error=step.error,
                tamper_blocked=step.tamper_blocked,
                created_at=step.created_at,
            )
            # The relationship is ordered by idx, but sorting here too means a
            # hand-inserted row cannot scramble a replay.
            for step in sorted(episode.steps, key=lambda step: step.idx)
        ],
    )


def _load_action(action_json: str) -> dict:
    """Decode a stored action, tolerating a bad row rather than 500-ing.

    One unreadable step should not make a whole trajectory unviewable.
    """
    try:
        parsed = json.loads(action_json)
    except json.JSONDecodeError:
        return {"type": "unreadable", "raw": action_json[:200]}
    return parsed if isinstance(parsed, dict) else {"type": "unreadable"}
