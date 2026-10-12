# Learning notes

A checkpoint for every build phase: what we built, how to see it work, what to
read, and what an interviewer might ask.

---

## Phase 0 checkpoint — Scaffold

**What we built and why.** The skeleton of the whole project: four top-level
folders (`engine/`, `tasks/`, `backend/`, `frontend/`) so each part has one
obvious home. The engine is installed as an *editable package* named `agentgym`,
which means `import agentgym` works from any directory and the docs commands do
not depend on where you are standing. A root `pytest.ini` points at both test
suites so one `pytest` command checks everything. `.gitignore` keeps the
virtualenv, `node_modules`, databases, run logs and real `.env` files out of git
from the very first commit, which is the only reliable moment to get that right.

**Commands to see it work.**
```
.venv/Scripts/python.exe -c "import agentgym; print(agentgym.__version__)"
git log --oneline
git ls-files
```
(On Linux/macOS use `source .venv/bin/activate` then plain `python`.)

**Files to read first.** `CLAUDE.md` (the project rules in one page),
`engine/pyproject.toml` (how the package is defined and installed),
`.gitignore` (what we refuse to commit, and why).

**Two interview questions.**
1. What does `pip install -e` actually do, and why is an editable install better
   here than copying the engine into `site-packages`?
   *Because it installs a link to the source tree rather than a copy, so code
   changes take effect with no reinstall — and the import name stays stable.*
2. Why put `pythonpath = backend` in `pytest.ini` instead of adding
   `sys.path` hacks at the top of the test files?
   *Because it keeps path setup in one declarative place that both the test
   runner and the reader can see, instead of scattering imperative side effects
   through test modules.*

---

## Phase 1 checkpoint — Engine core

**What we built and why.** The gym itself. `CodingEnv` has the two classic RL
methods, `reset` and `step`, and five actions an agent can take. The interesting
parts are the two layers that make the score trustworthy. `guard.py` inspects
every `write_file` before it touches disk and refuses the obvious cheats —
editing `tests/`, dropping a `conftest.py`, importing `subprocess`, escaping the
workspace with `..`. `sandbox.py` runs pytest in a subprocess with a wall-clock
timeout, POSIX resource limits where the platform has them, and an environment
stripped down to almost nothing so agent code cannot read your API key.
Grading happens in a *separate* directory with the hidden tests swapped in and
the JUnit report written outside it, so the agent cannot edit its own grade. The
three scripted agents turn all of this into automatic tests: the oracle proves
each task is solvable, the no-op proves it is not already solved, and the tamper
agent proves cheating does not pay.

**Commands to see it work.**
```
.venv/Scripts/python.exe -m pytest engine/tests -q
.venv/Scripts/python.exe -m agentgym.runner validate --tasks all
.venv/Scripts/python.exe -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl
.venv/Scripts/python.exe -m agentgym.runner run --agent tamper --tasks all --out runs/tamper.jsonl
```
Real result on this machine: 198 passed, 1 skipped (the symlink test needs
permissions Windows does not give by default). Oracle scores 1.000 on all three
tasks; no-op scores 0.200 / 0.273 / 0.100; tamper is blocked 5 times out of 5
and scores exactly what no-op scores.

**Files to read first.** `engine/agentgym/env.py` (the step loop and grading),
`engine/agentgym/guard.py` (every anti-cheat rule, one per function branch),
`docs/ARCHITECTURE.md` (the diagram and the trusted/untrusted split).

**Two interview questions.**
1. Why grade with hidden tests instead of the tests the agent can run?
   *Because the agent optimises whatever it is measured on. If it could see the
   grading tests it could special-case them — pass the three examples and fail
   every other input. Hidden tests mean the cheapest way to score is to write a
   general fix. The visible tests still matter: they are the feedback signal
   during the episode.*
2. Why force reward to 0.0 when the hidden-test count does not match
   `task.json`?
   *Because a syntax error or bad import makes pytest report something like
   "1 test, 1 error". Dividing passed by total on that would credit a crashed
   submission with a partial score. Checking the count against a number
   committed in advance turns "the tests did not really run" into an honest
   `error` outcome instead of fake progress.*

---

## Phase 2 checkpoint — All nine tasks and the validate command

**What we built and why.** Six more tasks (4 to 9) and the `validate` command
that proves all nine are sound. A task is only worth having if it is *broken*
(the visible tests fail), *fixable* (the reference solution makes them pass),
*honestly counted* (`hidden_test_count` matches what pytest actually collects)
and *discriminating* (doing nothing does not already score well). `validate`
checks all five properties per task and exits non-zero on any failure, so it
works as a CI gate.

That last property turned out to matter. The first drafts of tasks 4 and 5 let a
no-op agent score 0.727 and 0.818, because most of their hidden tests happened
to pass on the buggy code. A leaderboard built on that would flatter any agent.
Rewriting those hidden tests to aim at the planted bug brought the floors down
to 0.333 and 0.5. The no-op floor across all nine is now 0.1 to 0.5.

**Commands to see it work.**
```
.venv/Scripts/python.exe -m agentgym.runner validate --tasks all
.venv/Scripts/python.exe -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl
.venv/Scripts/python.exe -m pytest engine/tests -q
```
Real result on this machine: all nine tasks pass all five checks. Oracle scores
1.000 on all nine. 261 engine tests pass, 1 skipped, in about 1 minute 45.

**Files to read first.** `engine/agentgym/runner.py` (the `validate_task`
function is the whole quality argument in 40 lines), `tasks/09_bank_transfer/`
(the hardest task: two files, atomicity and Decimal), any `task.json` (the shape
of a task).

**Two interview questions.**
1. How do you know a task is actually hard, rather than just badly described?
   *Compare the no-op floor with the oracle ceiling. The oracle must hit 1.0,
   which proves the task is solvable and that the hidden tests agree with the
   reference fix. The no-op floor tells you how much of the score an agent gets
   for free. A task where the floor is 0.82 is not measuring much, no matter how
   hard the bug looks — that is a measurement bug, and I fixed two of them.*
2. Why does `validate` check the hidden test count against a number stored in
   `task.json`, rather than just counting whatever pytest collects?
   *Because the count in `task.json` is a commitment made in advance. If a
   source file fails to import, pytest reports one test and one error; counting
   whatever shows up would then score a crashed submission as a partial pass.
   Comparing against a pre-committed number turns that into an honest error.*

---

## Phase 3 checkpoint — Backend

**What we built and why.** A FastAPI service whose only job is to store and
serve results. It never runs agent code, which is the whole reason the project
can be deployed publicly at all. Three tables: tasks, episodes, and the steps
inside them (with a cascade delete, so removing an episode takes its trajectory
with it). Reads are public so the dashboard can be shared; the two write
endpoints need an `X-API-Key` header, compared with `secrets.compare_digest` so
the comparison takes the same time whether the first character is wrong or the
last. Every aggregate — leaderboard, matrix, per-task stats — is a SQL
`GROUP BY`, not a Python loop over rows, so it keeps working past a few hundred
episodes. One `DATABASE_URL` switches between SQLite locally and Postgres in
production, and a validator rewrites the legacy `postgres://` prefix that
hosting providers hand out into the psycopg 3 driver we actually install.

**Commands to see it work.**
```
.venv/Scripts/python.exe -m pytest backend/tests -q
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --app-dir backend
curl http://127.0.0.1:8000/api/health
# then open http://127.0.0.1:8000/docs in a browser
```
Real result on this machine: 76 backend tests pass. `/api/health` returns
`{"status":"ok"}`, `/docs` returns 200, reads return 200 without a key, and a
`PUT` without a key returns 401.

**Files to read first.** `backend/app/routers/stats.py` (the leaderboard and
matrix aggregates — the most interesting SQL in the project),
`backend/app/schemas.py` (the API contract and what the server refuses to
trust), `backend/app/config.py` (settings, the Postgres URL rewrite, and why
prod refuses to boot with the dev key).

**Two interview questions.**
1. Why is `reward` validated as being between 0 and 1 on the server when the
   engine already guarantees it?
   *Because the server does not trust its client. Anything holding the API key
   can post whatever it likes, including a reward of 50 that would silently top
   the leaderboard. The engine's guarantee protects against bugs; the schema
   protects against a bad or compromised client. Same reason observations are
   truncated server-side even though the engine truncates them first.*
2. Why does uploading the same episode twice return 409 instead of overwriting
   it or just succeeding?
   *Because an episode is an immutable record of something that happened. Making
   it an error means re-running `upload` on a file that partly succeeded is safe:
   the already-stored episodes are rejected individually and the rest go through,
   with no risk of double-counting every number on the leaderboard.*
