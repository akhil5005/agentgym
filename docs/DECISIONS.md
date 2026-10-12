# Decisions

One line per decision: what we chose and why. Newest at the bottom.

- **Package layout: `agentgym` installed editable from `engine/`** — one import name
  (`from agentgym.env import CodingEnv`) works from anywhere, so docs commands
  never depend on the current directory.
- **SQLite by default, Postgres via one `DATABASE_URL`** — zero setup locally,
  and the same code path works on a hosted database.
- **`Base.metadata.create_all` instead of Alembic migrations** — simplest thing
  that works for an append-only results store; the limitation is that changing a
  column later means dropping the table or adding migrations.
- **Native Windows support in the sandbox rather than requiring WSL2** — the
  author's machine is Windows, and `resource` limits degrade to a wall-clock
  timeout cleanly, so the project runs where it is actually developed.
- **No `__init__.py` in either tests folder; unique test file basenames instead** —
  both suites would otherwise import as a package called `tests` and collide.
