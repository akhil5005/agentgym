"""Command line entry point: `python -m agentgym.runner <command>`.

Commands:
  validate    check that every task is solvable, broken, and counted correctly
  run         play episodes and write them to a JSONL file
  sync-tasks  upload task metadata to the backend (never hidden tests)
  upload      send a saved JSONL file to the backend
  summary     print Markdown tables from saved JSONL files

Everything that executes agent code lives on this side of the wall. The backend
only ever receives finished results.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

from agentgym.agents.scripted import build_scripted_agent
from agentgym.env import CodingEnv
from agentgym.models import EpisodeRecord, Task, utc_now_iso
from agentgym.sandbox import run_pytest
from agentgym.tasks import load_task, resolve_task_ids, tasks_dir

SCRIPTED_AGENTS = ("noop", "oracle", "tamper")


# --- running one episode -----------------------------------------------------


def run_episode(
    env: CodingEnv, agent: Any, task_id: str, trial: int = 0
) -> EpisodeRecord:
    """Play one episode to the end and package it as an `EpisodeRecord`.

    The loop always terminates: the environment auto-submits once the agent
    reaches `max_steps`, so an agent that never submits still gets graded.
    """
    reset = env.reset(task_id)
    started_at = utc_now_iso()
    agent.start(reset.task.description, reset.file_list)

    observation = reset.observation
    final_reward = 0.0

    while True:
        try:
            action = agent.next_action(observation)
        except Exception as exc:  # noqa: BLE001 - an agent crash must not lose the episode
            # Submit so the episode is still graded and stored, with the crash
            # visible in the trajectory instead of lost in a stack trace.
            observation = f"ERROR: the agent raised {type(exc).__name__}: {exc}"
            action = {"type": "submit"}

        result = env.step(action)
        observation = result.observation
        if result.done:
            final_reward = result.reward
            break

    info = env.final_info
    return EpisodeRecord(
        id=str(uuid.uuid4()),
        task_id=task_id,
        agent_name=agent.name,
        model=getattr(agent, "model", None),
        trial=trial,
        reward=final_reward,
        outcome=str(info.get("outcome", "error")),
        steps_used=env.step_index,
        tamper_attempts=env.tamper_attempts,
        tests_passed=int(info.get("tests_passed", 0)),
        tests_total=int(info.get("tests_total", 0)),
        started_at=started_at,
        finished_at=utc_now_iso(),
        steps=list(env.steps),
    )


# --- validate ----------------------------------------------------------------


def _apply_solution(task: Task, workspace: Path) -> None:
    """Copy the reference fix over the workspace, as the oracle agent would."""
    for path in sorted(task.solution_dir.rglob("*")):
        if not path.is_file():
            continue
        target = workspace / path.relative_to(task.solution_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def validate_task(task_id: str, tasks_root: Path | None = None) -> dict[str, Any]:
    """Run the four health checks on one task.

    A task is only useful if it is *broken* (the visible tests fail), *fixable*
    (the reference solution makes them pass), *honestly counted* (the hidden
    test count in task.json is real) and *discriminating* (the buggy code does
    not already score 1.0).
    """
    task = load_task(task_id, tasks_root)
    checks: dict[str, Any] = {}

    # (a) and (b): the visible tests, before and after the reference fix.
    with CodingEnv(tasks_root) as env:
        env.reset(task_id)
        assert env.workspace is not None
        buggy_run = run_pytest(env.workspace)
        checks["visible_fail_on_buggy"] = buggy_run.returncode != 0

        _apply_solution(task, env.workspace)
        fixed_run = run_pytest(env.workspace)
        checks["visible_pass_with_solution"] = fixed_run.returncode == 0
        checks["_visible_output"] = fixed_run.output

    # (d, floor): the buggy code must not already score full marks.
    with CodingEnv(tasks_root) as env:
        noop = run_episode(env, build_scripted_agent("noop", task), task_id)
    checks["buggy_reward_below_one"] = noop.reward < 1.0
    checks["_noop_reward"] = round(noop.reward, 3)

    # (c) and (d, ceiling): the reference fix must score exactly 1.0, over
    # exactly the number of hidden tests task.json promises.
    with CodingEnv(tasks_root) as env:
        oracle = run_episode(env, build_scripted_agent("oracle", task), task_id)
        observed = int(env.final_info.get("observed_test_count", 0))
    checks["hidden_count_matches"] = observed == task.hidden_test_count
    checks["solution_reward_is_one"] = oracle.reward == 1.0
    checks["_observed_count"] = observed
    checks["_expected_count"] = task.hidden_test_count
    checks["_oracle_detail"] = oracle.steps[-1].observation if oracle.steps else ""

    return checks


#: Each check with the short column label used in the printed table.
CHECKS: tuple[tuple[str, str], ...] = (
    ("visible_fail_on_buggy", "broken"),
    ("visible_pass_with_solution", "fixable"),
    ("hidden_count_matches", "counted"),
    ("buggy_reward_below_one", "floor<1"),
    ("solution_reward_is_one", "ceiling=1"),
)
CHECK_NAMES = tuple(name for name, _label in CHECKS)


def command_validate(args: argparse.Namespace) -> int:
    """Validate every selected task and print a pass/fail table."""
    root = Path(args.tasks_root).resolve() if args.tasks_root else None
    task_ids = resolve_task_ids(args.tasks, root)
    if not task_ids:
        print(f"No tasks found in {root or tasks_dir()}")
        return 1

    print(
        "broken    = the visible tests fail on the buggy code\n"
        "fixable   = they pass once the reference solution is applied\n"
        "counted   = task.json's hidden_test_count matches reality\n"
        "floor<1   = doing nothing does not already score 1.0\n"
        "ceiling=1 = the reference solution scores exactly 1.0\n"
    )
    header = f"{'task':<22} " + " ".join(f"{label:<10}" for _n, label in CHECKS)
    header += "   noop   hidden"
    print(header)
    print("-" * len(header))

    all_ok = True
    failures: list[tuple[str, dict[str, Any]]] = []

    for task_id in task_ids:
        checks = validate_task(task_id, root)
        cells = []
        task_ok = True
        for name in CHECK_NAMES:
            ok = bool(checks[name])
            task_ok = task_ok and ok
            cells.append(f"{'PASS' if ok else 'FAIL':<10}")
        print(
            f"{task_id:<22} "
            + " ".join(cells)
            + f"   {checks['_noop_reward']:<6} {checks['_observed_count']}"
        )
        if not task_ok:
            all_ok = False
            failures.append((task_id, checks))

    print()
    for task_id, checks in failures:
        print(f"--- {task_id}: details ---")
        print(f"  noop reward: {checks['_noop_reward']}")
        print(
            f"  hidden tests: expected {checks['_expected_count']}, "
            f"observed {checks['_observed_count']}"
        )
        if not checks["visible_pass_with_solution"]:
            print("  visible tests with the solution applied:")
            print("    " + checks["_visible_output"].replace("\n", "\n    "))
        if not checks["solution_reward_is_one"]:
            print("  oracle grading observation:")
            print("    " + str(checks["_oracle_detail"]).replace("\n", "\n    "))
        print()

    print("All checks passed." if all_ok else "Some checks FAILED (see above).")
    return 0 if all_ok else 1


# --- run ---------------------------------------------------------------------


def command_run(args: argparse.Namespace) -> int:
    """Play episodes and write one JSON object per line to --out."""
    root = Path(args.tasks_root).resolve() if args.tasks_root else None
    task_ids = resolve_task_ids(args.tasks, root)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records: list[EpisodeRecord] = []
    with out_path.open("w", encoding="utf-8") as handle:
        for task_id in task_ids:
            task = load_task(task_id, root)
            for trial in range(args.trials):
                agent = _build_agent(args.agent, task)
                with CodingEnv(root) as env:
                    record = run_episode(env, agent, task_id, trial=trial)
                handle.write(record.to_jsonl() + "\n")
                handle.flush()  # survive a crash mid-run
                records.append(record)
                print(
                    f"{task_id:<22} {record.outcome:<13} "
                    f"reward {record.reward:>5.3f}  steps {record.steps_used:>2}  "
                    f"tamper {record.tamper_attempts}"
                )

    print(f"\nWrote {len(records)} episode(s) to {out_path}")
    return 0


def _build_agent(name: str, task: Task) -> Any:
    """Make an agent by CLI name, importing the LLM agent only if asked.

    The lazy import matters: the Anthropic SDK is an optional dependency, and
    the scripted agents must keep working when it is not installed.
    """
    if name in SCRIPTED_AGENTS:
        return build_scripted_agent(name, task)
    if name == "llm":
        from agentgym.agents.llm import LLMAgent

        return LLMAgent()
    raise ValueError(f"unknown agent {name!r}")


# --- argument parsing --------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m agentgym.runner",
        description="Run and validate AgentGym episodes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="check every task is sound")
    validate.add_argument("--tasks", default="all", help="all, or id1,id2")
    validate.add_argument("--tasks-root", default=None, help="override tasks/ folder")
    validate.set_defaults(func=command_validate)

    run = subparsers.add_parser("run", help="play episodes")
    run.add_argument("--agent", required=True, choices=[*SCRIPTED_AGENTS, "llm"])
    run.add_argument("--tasks", default="all", help="all, or id1,id2")
    run.add_argument("--trials", type=int, default=1, help="episodes per task")
    run.add_argument("--out", required=True, help="output JSONL path")
    run.add_argument("--tasks-root", default=None, help="override tasks/ folder")
    run.set_defaults(func=command_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
