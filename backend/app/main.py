"""The FastAPI application.

This service **stores and serves results only**. It never runs agent-written
code: episodes are played on your own machine by the runner CLI, which uploads
finished records here. See the README's "Threat model".
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_tables
from app.routers import episodes, stats, tasks


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Create any missing tables on startup."""
    create_tables()
    yield


app = FastAPI(
    title="AgentGym API",
    version="0.1.0",
    summary="Results store for the AgentGym coding-agent environment.",
    description=(
        "Read endpoints are public so the dashboard can be shared. The two "
        "write endpoints require an X-API-Key header. No agent code ever runs "
        "on this server."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Only the configured frontend may call us (plus localhost in dev).
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness check. Also the thing to curl when the dashboard looks empty."""
    return {"status": "ok"}


app.include_router(tasks.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
