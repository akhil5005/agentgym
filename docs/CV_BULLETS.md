# CV bullets

Filled in from the real runs recorded in the README on 2026-10-14. **Do not
edit a number here without re-running the command that produces it** — an
interviewer who asks "how did you measure that?" should get a command, not a
shrug.

Model evaluated: `gemini-3.5-flash-lite`, on Google's free tier, one trial per
task.

---

## Ready to use

> **Built a reinforcement-learning environment for AI coding agents** (Python,
> FastAPI, Next.js): 9 benchmark tasks where an agent debugs a real codebase and
> is graded on 10–12 hidden tests it never sees, with a sandboxed executor and
> an anti-reward-hacking guard that blocked 100% of 45 scripted cheat attempts.
> 394 tests.

> **Benchmarked Gemini 3.5 Flash-Lite end to end**: 0.990 mean reward and 8/9
> tasks solved, against a measured no-op floor of 0.360 and an oracle ceiling of
> 1.000 — so the score is anchored at both ends rather than quoted in isolation.

> **Caught a real generalisation failure the visible tests missed.** On the one
> task Gemini did not solve, its fix passed every test the agent could run and
> failed a hidden edge case: it used `[^\w]+` to split a URL slug, and `\w`
> matches the underscore, so `snake_case_name` was returned unchanged. That is
> the hidden-test design paying for itself in one regex.

> **Designed and validated the benchmark itself, not just the harness.** Each
> task is automatically checked for five properties — broken, fixable, honestly
> counted, discriminating, and solvable at exactly 1.0 — which caught two tasks
> where doing nothing already scored 0.73 and 0.82. Rewriting their hidden tests
> brought the no-op floor down to 0.33 and 0.50.

> **Shipped the full stack**: a sandboxed Python engine (subprocess isolation,
> process-tree timeouts, static analysis of agent-written code), a FastAPI +
> SQLAlchemy results API with SQL-aggregate leaderboards, and a Next.js
> dashboard with a step-by-step trajectory replay viewer.

---

## Talking points

| Claim | Where it comes from |
| --- | --- |
| 9 tasks, 3 difficulty levels, 10–12 hidden tests each | `tasks/*/task.json` |
| Gemini 0.990 mean reward, 8/9 solved, 7.4 mean steps | `runner summary "runs/*.jsonl"` |
| No-op floor 0.360, oracle ceiling 1.000 | same command |
| 45 cheat attempts, all blocked (5 per task × 9 tasks) | tamper agent's `tamper_attempts` |
| Gemini made 0 blocked writes across 9 tasks | its `tamper_attempts` is 0 everywhere |
| 394 tests, 318 engine + 76 backend | `pytest` |
| Runs with no API key | the three scripted agents and the whole dashboard |

## The three questions to be ready for

**"How do you know an agent cannot cheat?"** Do not answer with the guard's
feature list. Answer that there is an agent whose only job is to cheat, it runs
on every task, and the test suite asserts its reward never exceeds the no-op
agent's. Then be honest that the guard is static analysis, not a sandbox, and
that the real control is that untrusted code only ever runs locally.

**"Gemini scored 0.990. Is your benchmark too easy?"** Yes, and say so first.
Nine tasks with a capable model is close to saturated — it separates a working
agent from a broken one, not two good models. The useful signal was the *shape*
of the one failure, not the headline average. Harder tasks, more trials, and a
variance figure are what it would take to rank models.

**"What else is wrong with it?"** One trial per task, every bug is planted
rather than found in the wild, grading is pass/fail per test so a nearly-correct
fix scores like a bad one, and only one model has actually been measured. The
README's Limitations section lists the rest — having written it yourself is the
point.
