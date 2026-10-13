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
- **Task 06 plants one realistic root cause (doubled-quote escaping) rather than
  two stacked bugs** — the comma-after-a-quote cases are then genuine
  consequences of that single bug, which reads like code a hurried engineer
  wrote; two unrelated planted bugs would turn the task into a puzzle hunt.
- **Default LLM model is `claude-sonnet-5`, not `claude-sonnet-5-5`** — the spec
  asked for `claude-sonnet-5-5`, which is not a real model id and would 404. The
  nearest valid id is used; override with `AGENTGYM_MODEL`.
- **The LLM agent drives the tool loop by hand instead of using the SDK's tool
  runner** — the *environment* executes the tools and the runner owns the step
  loop, so there is nothing for the SDK runner to run. It also keeps the agent
  off a beta API surface.
- **Split `runner.py` into `episode.py`, `validate.py`, `api.py` and
  `summary.py`** — one file was heading past 400 lines, and "play an episode",
  "check a task is sound", "talk to the backend" and "format tables" are four
  separate jobs.
- **`UserFacingError` lives in `models.py`** — so the runner can catch the LLM
  agent's missing-key error without importing the optional Anthropic SDK.
- **The runner expands `runs/*.jsonl` itself** — PowerShell and cmd.exe do not
  expand globs before handing arguments to a program, so the documented command
  would otherwise match nothing on the author's own machine.
- **Frontend colour is driven by CSS variables, not Tailwind `dark:` variants** —
  one set of token names is redefined under `prefers-color-scheme: dark`, so a
  component can never style one theme and forget the other.
- **The matrix heatmap colours by mean reward, not solve rate** — with one trial
  per cell a solve rate is only ever 0 or 1, which throws away the difference
  between a 0.1 and a 0.9. The number shown is the number the colour encodes.
- **Data pages set `export const instant = false`** — Next 16's Cache Components
  refuses to prerender a route that reads uncached data. These pages must show
  current results, so blocking on the API is the correct behaviour.
- **`npm audit` reports 5 high findings and they are left alone** — all are
  dev-only transitive dependencies of `eslint-config-next` (braces, micromatch,
  fast-glob). `npm audit fix --force` would downgrade eslint-config-next from 16
  to 14, which is a real regression to fix a lint-time-only issue. Nothing
  vulnerable ships to the browser.
