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

**Be clear about what this does and does not protect.**

What the engine *does* stop, and tests automatically:

- Writing to `tests/`, so an agent cannot rewrite the tests it is scored on.
- Writing `conftest.py`, `pytest.ini`, `sitecustomize.py`, `.pth` files and
  friends, so it cannot change how pytest or the interpreter behave.
- Paths that are absolute, contain `..`, or resolve outside the workspace.
- Python files that import `socket`, `subprocess`, `urllib`, `importlib` and
  similar, or call `exec`, `eval`, `compile` or `__import__`.
- Runaway processes: a wall-clock timeout kills the whole process tree, plus
  CPU, memory and file-size limits on POSIX.
- Reading your secrets: the test subprocess gets a minimal environment, so
  `ANTHROPIC_API_KEY` is not in `os.environ` where agent code runs.
- Grading tampering: hidden tests are never copied into the agent's workspace,
  grading happens in a separate directory, and the JUnit report is written
  outside that directory.

What it **does not** stop:

- **Agent-written code runs as your user.** `sandbox.py` is a contained
  subprocess, not a virtual machine or a container. It has your filesystem
  permissions.
- The `guard.py` checks are a static `ast` analysis. A determined attacker can
  get around static analysis; this is defense in depth, not a boundary.
- There is no network isolation at the OS level. The import ban makes network
  access inconvenient, not impossible.

**Therefore: untrusted agents only ever run on your own machine, through the
runner CLI.** The deployed backend stores and serves finished results and never
executes anything an agent wrote. That operational split — not the guard — is
the real security control.
