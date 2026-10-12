"""Checking that every task is sound.

A task is only worth having if it is *broken* (the visible tests fail),
*fixable* (the reference solution makes them pass), *honestly counted*
(`hidden_test_count` matches what pytest actually collects) and
*discriminating* (doing nothing does not already score well).

`validate` checks all five properties for every task and exits non-zero on any
failure, which is what makes it usable as a CI gate.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from agentgym.agents.scripted import build_scripted_agent
from agentgym.env import CodingEnv
from agentgym.episode import run_episode
from agentgym.models import Task
from agentgym.sandbox import run_pytest
from agentgym.tasks import load_task, resolve_task_ids, tasks_dir


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


