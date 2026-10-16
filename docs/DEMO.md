# Running the demo

How to operate AgentGym — for a screenshare, an interview, or just checking it
still works. Every command here is copy-paste from the repository root with the
virtualenv active.

```powershell
cd E:\BackendProjects2026\ScalerAi
.\.venv\Scripts\Activate.ps1
```

---

## The 60-second version

If you only remember one thing: **the dashboard shows results, the CLI produces
them.** Episodes run on your machine; the website just stores and displays what
you upload. That split is the security story, and it is the first thing to say
out loud.

---

## Before the call — five minutes

A GitHub Action pings both services every 10 minutes from **09:30 to 19:20
IST**, so during a normal working day they are already awake and respond in
well under a second. Outside that window they sleep, and the first request
takes 30-60 seconds while Render wakes them.

Two things worth knowing:

- **Demo outside the window?** Open the repo's Actions tab, pick *Keep
  deployment warm*, and hit **Run workflow**. That wakes both services on
  demand, about a minute before you need them.
- **Why not keep them awake all day?** Render's free tier gives 750 instance
  hours a month *shared across the whole workspace*, and running out suspends
  every free service until the next month. Two services round the clock needs
  ~1,488h. The 10-hour window costs 620h and leaves 130h spare.

Either way, open both URLs once before anyone is watching:

```powershell
curl https://agentgym-api.onrender.com/api/health   # {"status":"ok"}
start https://agentgym-web.onrender.com             # should show data, not zeros
```

If the dashboard shows zeros, the database is empty — see "Uploading results".

**Where the data lives.** A Neon Postgres, in a dedicated `agentgym` schema
(`DB_SCHEMA=agentgym` on the API service). It is deliberately *not* the
container's disk: Render's free tier has no persistent storage, so an earlier
SQLite setup lost every episode on each redeploy. Verified by uploading, forcing
a clean rebuild, and re-querying — the 36 episodes survived.

Both free tiers idle out: Render sleeps the web services after ~15 minutes, Neon
suspends the database after ~5. The first request absorbs both wake-ups, which
is what the API client's retry is for.

Have a local fallback running in two spare terminals, in case the wifi or the
free tier lets you down mid-call:

```powershell
# terminal 1
uvicorn app.main:app --reload --app-dir backend     # http://127.0.0.1:8000
# terminal 2
cd frontend ; npm run dev                           # http://127.0.0.1:3000
```

---

## The demo, in the order that tells the story

### 1. Show the problem, not the dashboard (30 seconds)

Open a task's buggy file and its visible tests side by side. Point out that the
visible tests pass on code that is still wrong — that is the whole premise.

```powershell
code tasks\02_slugify\repo\src\slugify.py
code tasks\02_slugify\repo\tests\test_visible.py
```

### 2. Run a real episode live (1 minute)

The oracle applies the reference fix, so it must score exactly 1.000. It is the
fastest honest thing to run in front of someone:

```powershell
python -m agentgym.runner run --agent oracle --tasks 02_slugify --out runs/demo.jsonl
```

Then the one that makes people lean in — an agent whose only goal is to cheat:

```powershell
python -m agentgym.runner run --agent tamper --tasks 02_slugify --out runs/demo.jsonl
```

Five blocked write attempts, reward no better than doing nothing. Say the line:
*"there is an agent whose only job is to cheat, it runs on every task, and a
test asserts it never outscores the agent that does nothing."*

### 3. Prove the benchmark is sound (30 seconds)

```powershell
python -m agentgym.runner validate --tasks all
```

Nine tasks × five checks — broken, fixable, counted, discriminating, solvable.
This is the slide that says you designed a benchmark, not just a harness.

### 4. Open the dashboard (2 minutes)

| Page | What to say |
| --- | --- |
| Overview | oracle 1.000 is the ceiling, noop 0.360 is the floor, Gemini 0.990 sits between them — a score with nothing either side of it means nothing |
| Leaderboard row `tamper` | 100% tamper rate, reward identical to noop. Cheating is detected *and* unrewarded |
| Matrix | click `02_slugify` — the one cell where Gemini is not 1.000 |
| Episode replay | step through Gemini's trajectory to the failure |

### 5. Land on the best result you have (1 minute)

`02_slugify`, reward 0.909, 10 of 11 hidden tests. Gemini wrote exactly this:

```python
slug = re.sub(r"[^\w]+", "-", lowered, flags=re.UNICODE)
```

Every visible test passed. `\w` matches the underscore, so `snake_case_name`
came back unchanged, and the hidden test `test_underscores_become_hyphens`
caught it. One regex that shows exactly why hidden tests exist.

The detail worth having ready: `flags=re.UNICODE` is the tell. The model was
thinking about accented characters — a real edge case — and reached for a
character class that silently includes `_`. It is a *plausible* wrong answer,
not a careless one, which is what makes it a good demonstration.

---

## Uploading results

The dashboard is empty until you send it something. Run this once; the episode
files are already on disk, so nothing needs re-running.

```powershell
$env:AGENTGYM_API = "https://agentgym-api.onrender.com"
$env:AGENTGYM_KEY = "<Render -> agentgym-api -> Environment -> INGEST_API_KEY>"

python -m agentgym.runner sync-tasks --api $env:AGENTGYM_API --key $env:AGENTGYM_KEY
python -m agentgym.runner upload "runs/*.jsonl" --api $env:AGENTGYM_API --key $env:AGENTGYM_KEY
```

Task metadata must go first — episodes reference tasks. Re-running is safe:
episodes already stored come back as "already present" rather than duplicating.

Uploading sends only each task's id, title, difficulty, category, description
and step limit. Hidden tests, reference solutions and the hidden test count
never leave your machine; `Task.public_dict()` enforces that in code.

---

## Producing fresh results

```powershell
# the three scripted agents - no API key, ~3 minutes for all 27 episodes
python -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl
python -m agentgym.runner run --agent noop   --tasks all --out runs/noop.jsonl
python -m agentgym.runner run --agent tamper --tasks all --out runs/tamper.jsonl

# the tables that go in the README
python -m agentgym.runner summary "runs/*.jsonl"
```

Gemini needs a key and spends free-tier quota, so only re-run it when you
actually want new numbers:

```powershell
$env:GEMINI_API_KEY = "..."
python -m agentgym.runner models                      # check the model first
python -m agentgym.runner run --agent gemini --tasks all --out runs/gemini.jsonl
```

Add `--trials 3` to any run to measure variance. One trial per task is the
honest weak spot in the current numbers — say so before you are asked.

---

## If something breaks mid-demo

| Symptom | What to do |
| --- | --- |
| Dashboard spins, then "Could not load the results" | The API is asleep. Reload after ~45 seconds, or switch to localhost |
| Dashboard shows all zeros | Database empty, or the API is pointed at a different database. Switch to localhost and keep talking |
| Render site is down entirely | `npm run dev` + `uvicorn` locally — identical UI, same data |
| An episode hangs | Ctrl-C. The sandbox kills the process tree on timeout, but the CLI is still yours to interrupt |

**Switching to the local fallback is not an admission of failure** — the whole
architecture is that episodes run locally. Narrate it as the design working.

---

## Questions you will get

**"Could an agent just edit the tests?"** No, and the interesting part is why:
the guard refuses writes to `tests/`, protected config filenames, `.pth` files
and anything that escapes the workspace via a resolved path. But the real
control is that hidden tests are not in the workspace at all — grading happens
in a separate temp directory the agent never touches.

**"Gemini scored 0.990 — is the benchmark too easy?"** Yes, say it first. Nine
tasks against a capable model is near-saturated. It separates a working agent
from a broken one; it cannot rank two good models. The signal was the *shape*
of the one failure, not the average.

**"Why is a tamper agent's reward the same as noop's, not zero?"** Because
blocked writes change nothing, so it is graded on the original buggy code —
exactly what the no-op agent is graded on. Punishing it further would be a
second mechanism to get wrong; the guarantee that matters is "cheating never
pays", and equality already gives you that.

**"What would you do next?"** More trials with a variance figure, harder tasks
that are not single-file, and a second model for comparison. All three are in
the README's Limitations section, written before anyone asked.
