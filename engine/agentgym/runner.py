"""Command line entry point: `python -m agentgym.runner <command>`.

Commands:
  validate    check that every task is solvable, broken, and counted correctly
  run         play episodes and write them to a JSONL file
  sync-tasks  upload task metadata to the backend (never hidden tests)
  upload      send a saved JSONL file to the backend
  summary     print Markdown tables from saved JSONL files
  models      list the Gemini models this API key can use

Everything that executes agent code lives on this side of the wall. The backend
only ever receives finished results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from agentgym.agents.scripted import build_scripted_agent
from agentgym.api import BackendClient
from agentgym.env import CodingEnv
from agentgym.episode import run_episode
from agentgym.models import EpisodeRecord, Task, UserFacingError
from agentgym.summary import expand_paths, load_records, summarize
from agentgym.tasks import load_all_tasks, load_task, resolve_task_ids, tasks_dir
from agentgym.validate import command_validate

# Re-exported so `from agentgym.runner import run_episode` keeps working.
__all__ = ["run_episode", "build_parser", "main"]

SCRIPTED_AGENTS = ("noop", "oracle", "tamper")

#: Gemini is the project's LLM. "llm" is kept as an alias for it so older
#: commands and docs keep working. The Anthropic agent is still in the tree
#: and still tested, but nothing here selects it unless you name it.
LLM_AGENTS = ("gemini", "llm", "anthropic")
DEFAULT_LLM = "gemini"



# --- run ---------------------------------------------------------------------


def command_run(args: argparse.Namespace) -> int:
    """Play episodes, write them to --out, and optionally upload each one."""
    root = Path(args.tasks_root).resolve() if args.tasks_root else None
    task_ids = resolve_task_ids(args.tasks, root)

    client = _build_client(args)
    if client is not None:
        reachable, detail = client.health()
        if not reachable:
            # Fail before spending model time rather than after.
            print(f"Backend not reachable: {detail}")
            return 1

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

                line = (
                    f"{task_id:<22} {record.outcome:<13} "
                    f"reward {record.reward:>5.3f}  steps {record.steps_used:>2}  "
                    f"tamper {record.tamper_attempts}"
                )
                # Token usage is interesting enough to show per episode, and
                # only LLM agents have any.
                usage = getattr(agent, "usage_summary", None)
                if callable(usage):
                    line += f"  tokens {usage()}"
                if client is not None:
                    line += f"  upload {client.post_episode(record.to_dict()).outcome}"
                print(line)

    print(f"\nWrote {len(records)} episode(s) to {out_path}")
    return 0


# --- sync-tasks --------------------------------------------------------------


def command_sync_tasks(args: argparse.Namespace) -> int:
    """Upload every task's public metadata.

    Only `public_dict()` is sent, which is the guard against ever leaking the
    hidden test count, the hidden tests themselves, or the reference solution.
    """
    root = Path(args.tasks_root).resolve() if args.tasks_root else None
    tasks = load_all_tasks(root)
    if not tasks:
        print(f"No tasks found in {root or tasks_dir()}")
        return 1

    client = BackendClient(args.api, args.key)
    reachable, detail = client.health()
    if not reachable:
        print(f"Backend not reachable: {detail}")
        return 1

    failures = 0
    for task in tasks:
        payload = task.public_dict()
        result = client.put_task(task.id, {k: v for k, v in payload.items() if k != "id"})
        print(f"{task.id:<22} {result.outcome:<10} {result.detail}")
        if not result.ok:
            failures += 1

    print(f"\nSynced {len(tasks) - failures}/{len(tasks)} task(s) to {args.api}")
    return 1 if failures else 0


# --- upload ------------------------------------------------------------------


def command_upload(args: argparse.Namespace) -> int:
    """Upload a saved JSONL file. Never deletes or rewrites it."""
    paths = expand_paths(args.files)
    if not paths:
        print(f"No run files matched: {', '.join(args.files)}")
        return 1

    client = BackendClient(args.api, args.key)
    reachable, detail = client.health()
    if not reachable:
        print(f"Backend not reachable: {detail}")
        return 1

    records = load_records(paths)
    counts = {"uploaded": 0, "duplicate": 0, "failed": 0}
    for record in records:
        result = client.post_episode(record)
        counts[result.outcome] += 1
        if result.outcome == "failed":
            print(f"  FAILED {record.get('id', '?')}: {result.detail}")

    print(
        f"\n{counts['uploaded']} uploaded, {counts['duplicate']} already present, "
        f"{counts['failed']} failed, out of {len(records)} episode(s)."
    )
    if counts["failed"]:
        print("The run file is untouched — fix the problem and run upload again.")
    return 1 if counts["failed"] else 0


# --- summary -----------------------------------------------------------------


def command_summary(args: argparse.Namespace) -> int:
    """Print Markdown tables from saved run files."""
    paths = expand_paths(args.files)
    if not paths:
        print(f"No run files matched: {', '.join(args.files)}")
        return 1
    print(summarize(load_records(paths)))
    return 0


# --- models ------------------------------------------------------------------


def command_models(args: argparse.Namespace) -> int:
    """List the Gemini models this API key can actually use.

    Run this before an evaluation: model names and free-tier availability both
    change, and a benchmark that fails twenty minutes in because the model id
    was stale has wasted twenty minutes.
    """
    from agentgym.agents.gemini import DEFAULT_MODEL, list_usable_models

    rows = list_usable_models()
    flash = [row for row in rows if "flash" in row[0]]

    print(f"{len(rows)} model(s) usable for generateContent with this key.")
    print("\nFlash models (preferred on the free tier):")
    for name, label in flash:
        marker = "   <- current default" if name == DEFAULT_MODEL else ""
        print(f"  {name:<42} {label}{marker}")

    if args.all:
        flash_names = {name for name, _ in flash}
        print("\nEverything else:")
        for name, label in rows:
            if name not in flash_names:
                print(f"  {name:<42} {label}")

    if DEFAULT_MODEL in {name for name, _ in rows}:
        print(f"\nDefault model {DEFAULT_MODEL!r} is available.")
        return 0

    print(f"\nWARNING: default model {DEFAULT_MODEL!r} is not in this key's list.")
    print("Set AGENTGYM_GEMINI_MODEL to one of the names above.")
    return 1


def _build_client(args: argparse.Namespace) -> BackendClient | None:
    """A client when both --api and --key were given, otherwise None."""
    api = getattr(args, "api", None)
    key = getattr(args, "key", None)
    if api and key:
        return BackendClient(api, key)
    if api or key:
        raise ValueError("--api and --key must be given together")
    return None


def _build_agent(name: str, task: Task) -> Any:
    """Make an agent by CLI name, importing an LLM agent only if asked.

    The lazy imports matter: both SDKs are optional dependencies, and the
    scripted agents must keep working when neither is installed.
    """
    if name in SCRIPTED_AGENTS:
        return build_scripted_agent(name, task)
    if name in ("gemini", "llm"):
        from agentgym.agents.gemini import GeminiAgent

        return GeminiAgent()
    if name == "anthropic":
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
    run.add_argument(
        "--agent",
        required=True,
        choices=[*SCRIPTED_AGENTS, *LLM_AGENTS],
        help=f"scripted agent, or an LLM ({DEFAULT_LLM} is the default LLM)",
    )
    run.add_argument("--tasks", default="all", help="all, or id1,id2")
    run.add_argument("--trials", type=int, default=1, help="episodes per task")
    run.add_argument("--out", required=True, help="output JSONL path")
    run.add_argument("--tasks-root", default=None, help="override tasks/ folder")
    run.add_argument("--api", default=None, help="backend URL, to upload as we go")
    run.add_argument("--key", default=None, help="backend X-API-Key")
    run.set_defaults(func=command_run)

    sync = subparsers.add_parser(
        "sync-tasks", help="upload task metadata (never hidden tests or solutions)"
    )
    sync.add_argument("--api", required=True, help="backend URL")
    sync.add_argument("--key", required=True, help="backend X-API-Key")
    sync.add_argument("--tasks-root", default=None, help="override tasks/ folder")
    sync.set_defaults(func=command_sync_tasks)

    upload = subparsers.add_parser("upload", help="upload saved run files")
    upload.add_argument("files", nargs="+", help="JSONL paths or patterns")
    upload.add_argument("--api", required=True, help="backend URL")
    upload.add_argument("--key", required=True, help="backend X-API-Key")
    upload.set_defaults(func=command_upload)

    models = subparsers.add_parser(
        "models", help="list the Gemini models this API key can use"
    )
    models.add_argument("--all", action="store_true", help="also list non-Flash models")
    models.set_defaults(func=command_models)

    summary = subparsers.add_parser("summary", help="print Markdown result tables")
    summary.add_argument("files", nargs="+", help="JSONL paths or patterns")
    summary.set_defaults(func=command_summary)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except UserFacingError as exc:
        # One readable line instead of a stack trace a beginner has to decode.
        print(f"\n{exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
