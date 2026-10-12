# AgentGym

A small, complete system for training and evaluating AI coding agents.

Each episode hands an agent a tiny Python project with a bug in it. The agent can
list files, read files, write files, run the visible tests, and submit. When it
submits, the engine grades the work against **hidden tests the agent never sees**
and returns a reward between 0.0 and 1.0.

> **Status: under construction.** This README is filled in during Phase 6 with
> real numbers from real runs on this machine. Anything not yet measured says
> `TBD`.

## Parts

| Folder | What it is |
| --- | --- |
| `engine/` | The gym: environment, sandbox, anti-cheat guard, agents, runner CLI |
| `tasks/` | Nine buggy mini-projects with visible tests, hidden tests and reference fixes |
| `backend/` | FastAPI + SQLAlchemy service that stores episodes and serves stats |
| `frontend/` | Next.js dashboard: leaderboard, results matrix, episode replay |

## Quick start

TBD — written in Phase 6 once every command has been verified end to end.

## Threat model

TBD — written in Phase 1 alongside the guard and sandbox.
