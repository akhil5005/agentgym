"""API-key check for the two endpoints that write to the database.

Reads are public: the dashboard is meant to be shareable. Writes need the key,
so only the machine that actually ran the episodes can add results.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import settings


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency: raise 401 unless the X-API-Key header matches.

    `compare_digest` instead of `==` because a plain string comparison returns
    as soon as two characters differ, and the time it took leaks how much of
    the key was right. This comparison always takes the same time.
    """
    if not secrets.compare_digest(x_api_key, settings.ingest_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="a valid X-API-Key header is required for this endpoint",
        )
