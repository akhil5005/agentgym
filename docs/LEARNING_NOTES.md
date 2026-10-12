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
