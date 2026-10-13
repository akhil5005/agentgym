# CV bullets

Filled in from the real runs recorded in the README on 2026-10-13. **Do not
edit a number here without re-running the command that produces it** — an
interviewer who asks "how did you measure that?" should get a command, not a
shrug.

Anything still in `<angle brackets>` has not been measured yet.

---

## Ready to use

> **Built a reinforcement-learning environment for AI coding agents** (Python,
> FastAPI, Next.js): 9 benchmark tasks where an agent debugs a real codebase and
> is graded on 10–12 hidden tests it never sees, with a sandboxed executor and
> an anti-reward-hacking guard that blocked 100% of 45 scripted cheat attempts.
> 360 tests.

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

## Needs a real LLM run first

Set `ANTHROPIC_API_KEY`, run
`python -m agentgym.runner run --agent llm --tasks all --trials 5 --out runs/llm.jsonl`,
then `python -m agentgym.runner summary "runs/*.jsonl"` and fill these in.

> **Benchmarked `<model>` on 9 debugging tasks**, scoring `<X>` mean reward
> against a no-op floor of 0.360 and an oracle ceiling of 1.000, solving
> `<N>`/9 tasks outright across `<T>` trials per task.

> **Measured where coding agents fail**: `<model>` solved `<N>`/3 easy tasks but
> `<N>`/3 hard ones, with `<X>%` of failures being fixes that passed the visible
> tests and failed the hidden edge cases.

---

## Talking points

Numbers that make the project concrete in conversation:

| Claim | Where it comes from |
| --- | --- |
| 9 tasks, 3 difficulty levels, 10–12 hidden tests each | `tasks/*/task.json` |
| No-op floor 0.360, oracle ceiling 1.000 | `runner summary "runs/*.jsonl"` |
| 45 cheat attempts, all blocked (5 per task x 9 tasks) | tamper agent's `tamper_attempts` |
| 360 tests, 284 engine + 76 backend | `pytest` |
| Runs with no API key | the three scripted agents and the whole dashboard |

## The two questions to be ready for

**"How do you know an agent cannot cheat?"** Do not answer with the guard's
feature list. Answer that there is an agent whose only job is to cheat, it runs
on every task, and the test suite asserts its reward never exceeds the no-op
agent's. Then be honest that the guard is static analysis, not a sandbox, and
that the real control is that untrusted code only ever runs locally.

**"What is wrong with this benchmark?"** Have an answer ready — one trial per
task so far, nine tasks is too few to rank two good models, every bug is planted
rather than found in the wild, and grading is pass/fail per test so a
nearly-correct fix scores the same as a bad one. The Limitations section of the
README lists the rest.
