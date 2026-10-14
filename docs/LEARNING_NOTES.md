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

---

## Phase 4 checkpoint — Upload commands and the LLM agent

**What we built and why.** The bridge between the local engine and the backend,
plus the agent that actually costs money. `sync-tasks` uploads only
`task.public_dict()`, which is the structural guarantee that hidden tests and
reference solutions never leave this machine. `upload` and `run --api` share one
HTTP client that retries transient failures three times, treats a 409 as success
(so re-running `upload` on a half-finished file is safe rather than
double-counting), and never raises on a network error — a run that took two
minutes of model time must not be lost to a dropped wifi connection. The JSONL
file on disk stays the source of truth.

`LLMAgent` exposes the five actions as five tools and drives the conversation
by hand rather than using the SDK's tool runner, because the *environment*
executes the tools here, not the agent. The fiddly part is parallel tool calls:
the model can ask for three things at once, and the API requires all three
results to come back in one user message — splitting them teaches the model to
stop making parallel calls. So calls are queued, handed to the runner one at a
time, and their results batched.

Two things worth knowing. The spec's default model id, `claude-sonnet-5-5`, is
not a real model and would have 404'd; the real id is `claude-sonnet-5`. And
`runner.py` had grown past 400 lines, so it is now four modules: play an
episode, validate a task, talk to the backend, format tables.

**Commands to see it work.**
```
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend   # terminal 1
.venv/Scripts/python.exe -m agentgym.runner sync-tasks --api http://127.0.0.1:8000 --key dev-key
.venv/Scripts/python.exe -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl --api http://127.0.0.1:8000 --key dev-key
.venv/Scripts/python.exe -m agentgym.runner summary "runs/*.jsonl"
curl http://127.0.0.1:8000/api/leaderboard
```
Real result on this machine: 9 tasks synced, 27 episodes uploaded, and
`/api/leaderboard` shows three agents — oracle 1.000 mean reward and a 100%
solve rate, noop 0.360, tamper 0.360 with a 100% tamper rate. Tamper matches
noop exactly and never beats it. 360 tests pass, 1 skipped.

**The LLM agent has not been run for real.** `ANTHROPIC_API_KEY` is not set on
this machine, so the live smoke test was skipped and the LLM row stays `TBD` in
the README. Its tool-call plumbing is covered by 23 tests against a stubbed
client, so the wiring is verified even though the model is not.

**Files to read first.** `engine/agentgym/agents/llm.py` (how an LLM is turned
into a gym player), `engine/agentgym/api.py` (the retry and 409 policy),
`engine/agentgym/episode.py` (the whole step loop, in twenty lines).

**Two interview questions.**
1. Why does uploading a duplicate episode count as success rather than failure?
   *Because `upload` has to be safe to re-run. If a file of 50 episodes fails
   at number 30, you want to run the same command again and have the first 30
   be no-ops. Treating 409 as an error would make the retry look broken; making
   it overwrite would risk double-counting. "Already there" is the honest
   third answer.*
2. The model can request several tool calls at once, but the environment takes
   one action per step. How do you reconcile that?
   *Queue them. The agent hands the runner one action per `next_action` call and
   collects each observation, then sends all the results back in a single user
   message when the queue empties. That matters beyond tidiness: the API expects
   one result block per tool call in one message, and splitting them across
   messages trains the model to stop making parallel calls at all.*

---

## Phase 5 checkpoint — The dashboard

**What we built and why.** Five pages in Next.js: an overview with the
leaderboard and a task-by-agent heatmap, a task list, a task detail page with
its brief and episodes, the replay viewer, and an about page that explains the
whole idea in plain language. Every page is a server component that reads the
API on each request — a cached leaderboard that does not change after you upload
a run would be worse than a slightly slower one.

Three decisions worth defending. **Colour is never the only signal**: every
heatmap cell prints its number, every badge prints its word, and a cell that was
never attempted shows an em dash rather than 0.000, because "not tried" and
"scored zero" are different facts. **Every colour is a CSS variable** redefined
under `prefers-color-scheme: dark`, so a component cannot style light mode and
forget dark. And **a failed fetch returns `null` instead of throwing**, so when
the backend is down you get a panel naming the exact command to start it rather
than a stack trace — which is by far the most likely thing to go wrong for
someone cloning this.

The replay viewer is the one client component, because it holds the
selected-step state. It has a timeline coloured by action type, a step list, and
left/right arrow keys, with blocked writes shown in red everywhere they appear.

**Commands to see it work.**
```
uvicorn app.main:app --reload --app-dir backend     # terminal 1
cd frontend && npm run dev                          # terminal 2 → :3000
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```
Real result on this machine: `tsc` zero errors, `eslint` clean, `next build`
succeeds. All five pages render the real 27 episodes from Phase 4, the heatmap
shows oracle at 1.000 against noop and tamper at 0.360, and the tamper replay
shows five blocked writes with the guard's refusal text. Arrow keys step through
the trajectory and stop correctly at both ends. Stopping the backend swaps every
page for the "start the API like this" panel.

**Files to read first.** `frontend/src/lib/api.ts` (every call to the backend,
and the null-instead-of-throw policy), `frontend/src/components/replay-viewer.tsx`
(the trajectory UI and the keyboard handling),
`frontend/src/app/globals.css` (the colour tokens both themes share).

**Two interview questions.**
1. Why is the dashboard mostly server components, with only the replay viewer
   marked `"use client"`?
   *Because everything else just reads data and renders it — doing that on the
   server means no loading spinner, no API call from the browser, and no need to
   expose the API to the user's network at all. The replay viewer is the only
   part with genuine client state (which step is selected), so it is the only
   part that needs to ship JavaScript.*
2. Your heatmap colours cells by score. What did you do about accessibility?
   *The number is printed in every cell, so colour is redundant rather than
   load-bearing — it reads fine in greyscale or with colour-blindness. I used a
   single-hue sequential scale rather than red-to-green, because reward runs 0
   to 1 with no meaningful midpoint, and a diverging scale would imply one. Cells
   with no data show an em dash so "not attempted" never looks like "scored
   zero".*

---

## Phase 6 checkpoint — Docs and the final check

**What we built and why.** The README, the deploy guide, and the CV bullets —
plus a fresh-clone test that proved the README's commands actually work rather
than just looking like they would.

The README's job is to be honest. It reports the real measured numbers, and
where a number does not exist it says so and why: the LLM row is `TBD` because
no API key was ever set on this machine, and a made-up figure there would be
worse than a gap. It also says plainly what the project does *not* do — one
trial per task, nine tasks is too few to rank two good models, every bug is
planted rather than found in the wild, and the sandbox is not a security
boundary. A limitations section you wrote yourself is worth more in an interview
than one the interviewer finds for you.

The deploy guide covers Neon, Render and Vercel with no Docker, and leads with
the thing that matters: **episodes still run on your own machine**. Nothing you
deploy ever executes agent-written code.

**Commands to see it work.**
```
python -m agentgym.runner validate --tasks all
pytest
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```
Real result: all nine tasks pass all five checks; 360 tests pass with 1 skip;
the frontend is clean on all three gates. A fresh `git clone` into an empty
directory, followed by the README's quick start verbatim, installed cleanly,
validated, ran all three scripted agents, printed the summary tables, served
`/api/health` and `/docs`, synced 9 tasks, uploaded 6 episodes, and built the
frontend — with no API key and no edits.

That fresh-clone run also caught a real bug: `frontend/.env.example` had never
been created (an earlier command ran from the wrong directory), and Next's own
generated `.gitignore` would have excluded it anyway.

**Files to read first.** `README.md` (especially Results and Limitations),
`docs/ARCHITECTURE.md` (the diagram and the trusted/untrusted split),
`docs/DECISIONS.md` (every choice and its reason, one line each).

**Two interview questions.**
1. Your README has a `TBD` in the results table. Why not just leave the row out?
   *Because the absence is the finding. The harness is built and tested and the
   row is there waiting; what is missing is a key and a budget, not code. Hiding
   the row would imply the work was never scoped, and filling it with a guess
   would be worse — every other number in that table is reproducible by running
   one command, and I would rather one honest gap than one number nobody can
   reproduce.*
2. Why bother with a fresh-clone test when all the tests already pass?
   *Because the test suite runs in an environment I had already set up by hand,
   so it cannot catch anything about the setup itself — a file I created but
   never committed, a path that only works from one directory, a dependency I
   installed months ago and forgot to declare. It found exactly that class of
   bug: a config example that existed on my disk and in no clone.*

---

## Phase 7 checkpoint — Deployment

**Gate.** The whole stack deploys from one file, no secret is committed, and the
security boundary survives being hosted.

The earlier version of `docs/DEPLOY.md` (described in the Phase 6 checkpoint
above) walked through three providers by hand: Neon for Postgres, Render for the
API, Vercel for the dashboard. It worked, but every step was a thing to get
wrong — copy a connection string, invent a key, paste a URL into two places and
hope they match. Replaced with a single Render blueprint, `render.yaml`, that
declares all three resources and wires them together.

**What the blueprint removes.** `DATABASE_URL` comes from `fromDatabase`, so the
connection string is never copied. `INGEST_API_KEY` uses `generateValue: true`,
so Render invents it and I never see it until I need it — which means there was
never a moment where the real key sat in a shell history or a notes file.

**What it could not remove.** The two cross-service URLs. Render's `fromService`
reference exists, but for a web service it yields the *private* network
hostname, and these two URLs are both used by a browser: one is CORS's
`FRONTEND_ORIGIN`, the other is baked into the frontend bundle. A private
hostname in either place fails in a way that looks like a code bug. So both are
`sync: false` — Render prompts for them on apply, and the blueprint's header
comment states the two answers.

**One real fix found while packaging.** `backend/requirements.txt` listed
`pytest`. That file is exactly what the production server installs, so the test
runner was about to be shipped to a web host that will never run a test. Removed
it; `pytest` already comes from the engine's `[dev]` extra, which the README's
install line includes, so local testing is unaffected — verified by re-running
the backend suite and by a `pip install --dry-run` in a clean venv.

I also broke the file briefly while editing it: a three-line comment lost its
`#` on two of the lines, which would have made `pip install` fail on the first
deploy. Caught it by actually checking that every line is a comment, a blank, or
a parseable requirement, rather than trusting the edit.

**The thing I did not automate.** Pushing to GitHub. Making a repository public
is irreversible in practice — once it is indexed, "private again" does not
un-publish it — so the name and visibility were the user's call, not a default I
picked. The secret sweep ran first: the whole of `git log --all -p` grepped for
key-shaped strings, plus a direct search for the actual `GEMINI_API_KEY` value
in every tracked file.

**Two interview questions.**
1. Your blueprint hard-codes two URLs in a comment instead of referencing the
   services. Isn't that fragile?
   *It's the less fragile of the two options. `fromService` would give me the
   private hostname, and both of these URLs are consumed by a browser — so the
   "proper" reference produces a CORS failure and a frontend that cannot reach
   its API, both of which look like application bugs. A prompted variable fails
   loudly at apply time instead, and the comment tells you the answer. I would
   rather a manual step I can see than an automatic one that is silently wrong.*
2. You removed `pytest` from the backend requirements. What does that buy you?
   *Mostly it's about what that file means. `requirements.txt` is the production
   install set, so anything in it is a claim that the server needs it — and a
   test runner on a web host is either dead weight or, if something ever shells
   out to it, a foothold. The real answer is that dev and prod dependencies
   belong in different places, and `pytest` already had a correct home in the
   engine's `[dev]` extra.*
