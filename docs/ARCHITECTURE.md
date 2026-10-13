# Architecture

## The idea in one paragraph

AgentGym is a **reinforcement-learning environment** for coding agents. An
environment is just a world with two buttons: `reset` starts a fresh attempt,
and `step` applies one action and tells you what happened. Here the world is a
small Python project with a bug in it. The agent reads files, writes files and
runs the tests it can see. When it submits, we grade it against a *different*
set of tests it has never seen. The score — the **reward** — is the fraction of
those hidden tests that pass. Because the agent cannot see what it is graded on,
the only reliable way to score well is to actually fix the bug.

## The three vocabulary words

| Word | Meaning here |
| --- | --- |
| **Environment** | `CodingEnv`. Owns the workspace and the rules. `reset(task_id)` / `step(action)`. |
| **Episode** | One attempt at one task, from `reset` until `done` is true. |
| **Trajectory** | The ordered list of steps in an episode: action → observation → reward. This is what the replay viewer plays back. |
| **Reward** | `0.0` on every step except the last. The final reward is `hidden tests passed / hidden tests total`. |

## Data flow

```
            YOUR MACHINE (trusted side)                    |   PUBLIC (untrusted-code-free)
                                                           |
  tasks/<id>/                                              |
    task.json      repo/        hidden_tests/  solution/   |
       |             |              |             |        |
       |             v              |             |        |
       |      copy into a           |             |        |
       |      temp workspace        |             |        |
       |             |              |             |        |
       v             v              |             |        |
  +----------------------+          |             |        |
  |      CodingEnv       |          |             |        |
  |  reset() / step()    |          |             |        |
  +----------+-----------+          |             |        |
             |                      |             |        |
     action  |  observation         |             |        |
             v                      |             |        |
  +----------------------+          |             |        |
  |        Agent         |          |             |        |
  | noop / oracle /      |<---------+-------------+        |
  | tamper / llm         |   (oracle only reads solution/) |
  +----------------------+          |                      |
             |                      |                      |
   write_file|                      |                      |
             v                      |                      |
      +-------------+               |                      |
      |   guard.py  |  reject cheats (tests/, conftest.py, |
      +------+------+   imports, escapes, size, count)     |
             | allowed                                     |
             v                                             |
      +-------------+    run_tests / grading               |
      |  sandbox.py |----------------------+               |
      | subprocess, timeout, rlimits,      |               |
      | minimal env (no API keys)          |               |
      +------------------------------------+               |
             |                                             |
             v  on submit: copy workspace, swap in          |
         hidden_tests/, run pytest --junitxml               |
             |                                             |
             v                                             |
      EpisodeRecord (reward, outcome, steps)                |
             |                                             |
             +--> runs/NAME.jsonl  (local log)             |
             |                                             |
             +--> runner upload ---------------------------> FastAPI backend
                                                           |   tasks / episodes / steps
                                                           |   (SQLite or Postgres)
                                                           |         |
                                                           |         v
                                                           |   Next.js dashboard
                                                           |   leaderboard, matrix, replay
```

The vertical line matters. **Everything that executes agent-written code is on
the left**, on your machine, launched by the runner CLI. The backend on the
right only ever receives finished results: numbers, action logs and
observations. Hidden tests and reference solutions never cross the line.

## One episode, step by step

1. `reset("04_merge_intervals")` copies `tasks/04_merge_intervals/repo/` into a
   fresh temp directory and writes an engine-owned `pytest.ini` there.
2. The agent gets the task description and the file list. It does **not** get
   the hidden tests, the solution, or any hint about where the bug is.
3. Each `step(action)` does one of five things: `list_files`, `read_file`,
   `write_file`, `run_tests`, `submit`.
4. Every `write_file` passes through `guard.py` first. A rejected write does not
   happen, still costs a step, and increments `tamper_attempts`.
5. `run_tests` runs the *visible* tests in `sandbox.py`: a subprocess with a
   wall-clock timeout, POSIX resource limits where available, and an
   environment stripped of everything except what an interpreter needs to boot.
6. On `submit` — or automatically once the agent hits `max_steps` — the engine
   copies the workspace somewhere new, deletes the visible `tests/`, drops in
   `hidden_tests/`, and runs pytest with `--junitxml`. The report is written
   *outside* the graded directory so agent code cannot edit its own grade.
7. `reward = passed / total`. If the report's test count does not match
   `hidden_test_count` in `task.json`, the reward is forced to `0.0` and the
   outcome is `error` — a broken import must never look like a partial pass.
8. The episode becomes an `EpisodeRecord` with its full trajectory, written to
   `runs/*.jsonl` and optionally uploaded.

## Outcome labels

Computed in this order of precedence, most-specific first:

`error` → `timeout` → `solved` (reward 1.0) → `out_of_steps` → `no_change`
(never wrote a file) → `partial` (0 < reward < 1) → `wrong_fix` (wrote files,
reward 0).

`tamper_attempts` is a separate counter, not an outcome: an agent can cheat
*and* fix the bug, and we want to see both.

## Why the three scripted agents exist

A single LLM score is uninterpretable on its own. The baselines make it mean
something:

- **noop** submits immediately. Its reward is what the buggy code already
  passes — the floor. An LLM at or below this did nothing.
- **oracle** applies `solution/`. It must score 1.0 on every task, which proves
  each task is solvable and correctly counted. It is a test of the *task*, not a
  leaderboard contender.
- **tamper** only tries to cheat. Every attempt must be blocked and its reward
  must never exceed noop's. This is the anti-reward-hacking claim, checked
  automatically rather than asserted in a README.

## Module map

| File | Responsibility |
| --- | --- |
| `engine/agentgym/models.py` | Dataclasses and truncation limits. No logic. |
| `engine/agentgym/tasks.py` | Load and validate `tasks/*/task.json`. |
| `engine/agentgym/guard.py` | Decide whether a `write_file` is allowed. |
| `engine/agentgym/sandbox.py` | Run pytest with limits and a stripped environment. |
| `engine/agentgym/env.py` | `CodingEnv`: the step loop, grading, outcome labels. |
| `engine/agentgym/episode.py` | Play one episode from reset to done. |
| `engine/agentgym/validate.py` | The five health checks that prove a task is sound. |
| `engine/agentgym/api.py` | HTTP client for uploading results. Retries, never raises. |
| `engine/agentgym/summary.py` | Turn saved run files into Markdown tables. |
| `engine/agentgym/agents/` | The agent protocol, three scripted agents, the LLM agent. |
| `engine/agentgym/runner.py` | CLI wiring: `validate`, `run`, `sync-tasks`, `upload`, `summary`. |
| `backend/app/` | FastAPI: store and serve episodes, leaderboard, matrix. |
| `frontend/` | Next.js dashboard: leaderboard, results matrix, replay viewer. |

The engine modules are deliberately small and single-purpose. If you are reading
this to understand the project, `episode.py` is the twenty lines that matter:
everything else is setup, storage, or presentation around that loop.
