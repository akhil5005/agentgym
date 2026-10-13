# AgentGym — rules for Claude Code sessions

## What this is
A reinforcement-learning environment for AI coding agents. Each episode hands an
agent a small Python project containing a bug. The agent reads files, writes
files, runs the visible tests, and submits. The engine then grades the work with
hidden tests the agent never sees. Reward = fraction of hidden tests passing.

Three parts: `engine/` (the gym + agents + runner CLI), `backend/` (FastAPI +
SQLAlchemy, stores results), `frontend/` (Next.js dashboard).

## Stack
- Python 3.11+ · FastAPI · SQLAlchemy 2.x typed style · Pydantic v2 · pytest
- Node 20+ · Next.js App Router · TypeScript strict · Tailwind
- One venv at the repo root: `.venv`

## Hard constraints
- No Docker, Terraform, AWS, Kubernetes, or cloud SDKs. Plain Python and Node.
- Sandboxing uses only the standard library: `subprocess`, `tempfile`,
  `resource`, `ast`, `signal`, `os`.
- **Untrusted code never runs on a public server.** Episodes run locally via the
  runner CLI. The deployed backend only stores and serves results.
- **Never upload hidden tests or reference solutions to the backend.**
- The project must work with no API key: the three scripted agents and the whole
  dashboard need no LLM. Only the LLM agents need a key.
- **Gemini is the project's LLM.** `GeminiAgent` (google-genai, `GEMINI_API_KEY`)
  is what `--agent llm` and `--agent gemini` both build, and it is what every
  evaluation and leaderboard number comes from. The Anthropic agent is kept in
  the tree and tested, but is never used for results. Do not add Anthropic calls.
- No secrets in git. Use env vars and `.env.example` files.
- SQLite by default, Postgres in production, through one `DATABASE_URL`.

## Style
Small files (< ~300 lines), clear names over clever ones, type hints
everywhere, strict TypeScript. Comments explain *why*, not *what*. The author is
a beginner who must be able to explain every line in an interview.

## Commands (run from the repo root with the venv active)
```
pip install -e "./engine[dev]" -r backend/requirements.txt
pytest                                           # both test suites
python -m agentgym.runner validate               # check all 9 tasks
python -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl
python -m agentgym.runner summary "runs/*.jsonl"   # Markdown result tables
uvicorn app.main:app --reload --app-dir backend  # backend on :8000
cd frontend && npm run dev                       # dashboard on :3000
```

The LLM agent is an optional extra and the only thing needing a key:
```
pip install -e "./engine[llm]"            # installs google-genai
export GEMINI_API_KEY=...                 # PowerShell: $env:GEMINI_API_KEY = "..."
python -m agentgym.runner models          # check the model is available first
python -m agentgym.runner run --agent gemini --tasks all --out runs/gemini.jsonl
```

## Engine modules
Keep them small and single-purpose. `env.py` is the step loop and grading,
`episode.py` plays one episode, `guard.py` refuses cheats, `sandbox.py` runs
pytest with limits, `validate.py` proves a task is sound, `api.py` uploads,
`summary.py` formats tables, and `runner.py` is only CLI wiring.

## Frontend
After adding a route, run `npx next typegen` so the generated `PageProps<"/...">`
helpers know about it. Pages that read the API need `export const instant = false`
(Next 16 will not prerender a route that reads uncached data).

## Import conventions
- Engine is an installed editable package: `from agentgym.env import CodingEnv`.
- Inside `backend/app/`, import as `from app.config import settings`.
- Root `pytest.ini` sets `pythonpath = backend` so `pytest` works from the root.

## Honesty rule
Every number in the README or docs must come from a real run on this machine.
Until a real run exists, write `TBD`. Never invent results.
