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
- **Gemini is the project's LLM; the Anthropic agent is kept but unused** — the
  `Agent` protocol made this a new file plus one line in the runner's factory,
  with the environment, guard, sandbox, grading, backend and dashboard all
  unchanged. `--agent llm` is an alias for `--agent gemini` so older commands and
  docs keep working.
- **The google-genai SDK's automatic function calling is switched off** — the
  *environment* executes the actions. If the SDK invoked them it would bypass the
  guard, the step counter and the step limit, which are the whole point.
- **A per-minute 429 is retried; a daily free-tier 429 stops the run** — waiting
  out a per-minute limit is correct, but the only way past a daily limit is
  billing, and the instruction is to stop rather than spend money.
- **Gemini calls are paced (default 4s apart) rather than sprinting into a 429** —
  free-tier quotas are per-minute, so pacing is cheaper than backing off.
- **Gemini model is `gemini-3.6-flash`, chosen by probing rather than by name** —
  `models.list()` advertises 45 usable models, but calling `gemini-2.5-flash`
  (the obvious free-tier Flash choice) returns 404 "no longer available to new
  users". Google's suggested replacement, `gemini-3.8-flash`, plus `3.7-flash`
  and `flash-latest`, were all returning 503 "high demand". `3.6-flash` is the
  newest full Flash model that answered reliably. Being listed is not the same
  as being callable, so `runner models` now sends a real one-token request
  instead of trusting the catalogue.
- **Raw `httpx` errors are retried alongside SDK errors** — a transient DNS
  failure surfaced as `httpx.ConnectError`, which the SDK does not wrap. A run
  that has already spent minutes of quota should not die because a name lookup
  blipped.
- **An agent crash now attaches its error to the final step** — `run_episode`
  built an error observation and then threw it away, because `env.step()`
  overwrote the variable before it was recorded. The first Gemini smoke test
  failed with a 404 and the episode log showed only the grading output, which
  made a configuration error look like a bad model.
- **The default model is `gemini-3.5-flash-lite`, chosen by free-tier capacity** —
  the full Flash models allow 20 requests per *day* on the free tier, and one
  task costs 7-11 calls, so no plain Flash model can complete a nine-task
  benchmark in a day. Flash-Lite has enough daily quota for the whole run, which
  is what makes a single-model, reproducible result possible at all.
- **The smoke run on `gemini-3.6-flash` was deleted rather than uploaded** —
  it was a different model, and mixing models inside one `gemini` leaderboard
  row would report a number that no single model actually scored.
- **`MatrixCell` carries `agent_name` and `model` as well as the joined label** —
  a browser pass found that one long model id (`gemini-3.5-flash-lite`) stretched
  its matrix column to several times the width of the others, stranding the
  numbers far from their header. Splitting the two in the API lets the header put
  the model on its own line and give every agent column equal width.
- **Arrow-key navigation in the replay moves focus, not just the highlight** —
  previously the selection moved and focus stayed where it was, leaving two
  competing "current" markers on screen and giving a screen reader nothing to
  announce.
- **Deploy with a single Render blueprint (`render.yaml`) instead of three
  providers wired by hand** — one `Apply` creates the database and both
  services, and `fromDatabase` plus `generateValue` mean the connection string
  and the ingest key are never copied, pasted, or written down anywhere.
- **The two cross-service URLs are prompted (`sync: false`), not `fromService`
  references** — `fromService` yields a web service's *private* hostname, and
  both of these URLs are used by a browser, so the automatic reference would
  produce a CORS failure and an unreachable API that both look like code bugs.
- **`pytest` removed from `backend/requirements.txt`** — that file is the
  production install set; the test runner belongs in the engine's `[dev]` extra,
  which it already was, so nothing local changed.
- **Repository name and visibility left to the user rather than defaulted** —
  publishing source code is irreversible in practice, so it is not a choice to
  make on someone's behalf.
- **`runs/*.jsonl` stays gitignored, so the episode records are not published**
  — the post-submit observation names the hidden tests that failed, so
  committing the run files would disclose roughly two-thirds of the hidden
  suite and make the benchmark reusable only once.
- **The six hidden tests that duplicate a visible test are documented, not
  deleted** — they are deliberate regression checks, but they are not unseen
  signal, so the README says exactly which tasks they are in rather than
  implying every hidden test is a fresh edge case.
