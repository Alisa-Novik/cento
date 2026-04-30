#!/usr/bin/env python3
"""Manifest-driven cluster job runner for Cento."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLUSTER_SH = ROOT / "scripts" / "cluster.sh"
DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "cento"
CLUSTER_FILE = DEFAULT_CONFIG / "cluster.json"
RUN_ROOT = ROOT / "workspace" / "runs" / "cluster-jobs"


def die(message: str, code: int = 1) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(code)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "feature"


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        die(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        die(f"Invalid JSON in {path}: {exc}")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def cluster_nodes() -> list[dict[str, Any]]:
    if not CLUSTER_FILE.exists():
        subprocess.run([str(CLUSTER_SH), "init"], cwd=ROOT, check=True)
    data = read_json(CLUSTER_FILE)
    nodes = data.get("nodes") or []
    if not nodes:
        die(f"No nodes configured in {CLUSTER_FILE}")
    return nodes


def parse_nodes(value: str | None, limit: int) -> list[dict[str, Any]]:
    nodes = cluster_nodes()
    by_id = {node["id"]: node for node in nodes}
    if value:
        selected = []
        for node_id in [part.strip() for part in value.split(",") if part.strip()]:
            if node_id not in by_id:
                die(f"Unknown node '{node_id}'. Known nodes: {', '.join(sorted(by_id))}")
            selected.append(by_id[node_id])
    else:
        selected = nodes
    return selected[:limit]


def default_agent_command() -> list[str]:
    env_value = os.environ.get("CENTO_CLUSTER_AGENT")
    if env_value:
        return shlex.split(env_value)
    return [
        "codex",
        "exec",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "-",
    ]


def task_prompt(feature: str, task: dict[str, Any], job: dict[str, Any]) -> str:
    sibling_tasks = [
        f"- {item['id']} on {item['node']}: {item['title']}"
        for item in job["tasks"]
        if item["id"] != task["id"]
    ]
    sibling_text = "\n".join(sibling_tasks) or "- none"
    ownership = "\n".join(f"- {item}" for item in task["ownership"])
    return "\n".join(
        [
            "You are one agent in a Cento cluster job.",
            "",
            "Feature request:",
            feature,
            "",
            "Your task:",
            task["title"],
            "",
            "Scope:",
            task["scope"],
            "",
            "Ownership:",
            ownership,
            "",
            "Parallel sibling tasks:",
            sibling_text,
            "",
            "Work rules:",
            "- You are not alone in the codebase; do not revert unrelated edits or work from other agents.",
            "- Keep your changes within your ownership where practical.",
            "- If a needed change crosses ownership, document it in your final message instead of making a broad refactor.",
            "- Run focused validation when feasible.",
            "- Leave the worktree on the task branch with your edits, and include changed files plus verification results in the final answer.",
        ]
    )


def planned_tasks(feature: str, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(nodes) == 1:
        node = nodes[0]
        return [
            {
                "id": "agent-1-implementation",
                "node": node["id"],
                "title": "Implement the feature end to end",
                "scope": "Inspect the codebase, make the smallest coherent implementation, update docs or tests as needed, and validate it.",
                "ownership": ["primary implementation", "focused tests", "docs touched by the feature"],
            }
        ]

    first, second = nodes[0], nodes[1]
    return [
        {
            "id": "agent-1-core",
            "node": first["id"],
            "title": "Core implementation slice",
            "scope": "Find the primary command, API, or module surface for the feature and implement the core behavior with focused validation.",
            "ownership": ["core/runtime code", "command surface", "minimal docs for the command or API"],
        },
        {
            "id": "agent-2-verification",
            "node": second["id"],
            "title": "Tests, edge cases, and integration slice",
            "scope": "Work in parallel on tests, edge cases, docs, and integration checks. Add implementation only where required by that ownership.",
            "ownership": ["tests and fixtures", "docs/examples", "edge-case fixes discovered during validation"],
        },
    ]


def create_plan(args: argparse.Namespace) -> Path:
    feature = " ".join(args.feature).strip()
    if not feature:
        die("Feature text is required")
    nodes = parse_nodes(args.nodes, args.agents)
    if not nodes:
        die("No nodes selected")

    job_id = f"{timestamp()}-{slugify(feature)}"
    run_dir = RUN_ROOT / job_id
    tasks = planned_tasks(feature, nodes)
    payload = {
        "schema_version": "1.0",
        "id": job_id,
        "status": "planned",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "feature": feature,
        "repo": str(ROOT),
        "run_dir": str(run_dir),
        "agent_command": args.agent_command or " ".join(shlex.quote(part) for part in default_agent_command()),
        "tasks": tasks,
        "artifacts": {
            "summary": str(run_dir / "summary.md"),
            "logs": str(run_dir / "logs"),
            "task_manifests": str(run_dir / "tasks"),
        },
    }
    job_path = run_dir / "job.json"
    write_json(job_path, payload)
    for task in tasks:
        task_payload = dict(task)
        task_payload["prompt"] = task_prompt(feature, task, payload)
        write_json(run_dir / "tasks" / f"{task['id']}.json", task_payload)
    print(job_path)
    return job_path


def find_job(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.exists():
        return candidate.resolve()
    candidate = RUN_ROOT / value / "job.json"
    if candidate.exists():
        return candidate.resolve()
    matches = sorted(RUN_ROOT.glob(f"*{value}*/job.json"))
    if len(matches) == 1:
        return matches[0].resolve()
    if len(matches) > 1:
        die(f"Ambiguous job id '{value}': " + ", ".join(path.parent.name for path in matches))
    die(f"Unknown job: {value}")


def shell_script(job: dict[str, Any], task: dict[str, Any], prompt: str, agent_command: list[str]) -> str:
    node = next((item for item in cluster_nodes() if item["id"] == task["node"]), None)
    if node is None:
        die(f"Task {task['id']} uses unknown node {task['node']}")
    repo = node.get("repo") or job["repo"]
    branch = f"cento/{job['id']}/{task['id']}"
    worktree = f"{repo}/workspace/cluster-worktrees/{job['id']}/{task['id']}"
    prompt_file = f"{worktree}/.cento-task-prompt.md"
    summary_file = f"{worktree}/.cento-task-summary.md"
    command = " ".join(shlex.quote(part) for part in agent_command)
    return "\n".join(
        [
            "set -euo pipefail",
            f"repo={shlex.quote(repo)}",
            f"worktree={shlex.quote(worktree)}",
            f"branch={shlex.quote(branch)}",
            f"prompt_file={shlex.quote(prompt_file)}",
            f"summary_file={shlex.quote(summary_file)}",
            'mkdir -p "$(dirname "$worktree")"',
            'if ! git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then',
            '  echo "Not a git repository: $repo" >&2',
            "  exit 2",
            "fi",
            'if [[ ! -e "$worktree/.git" ]]; then',
            '  git -C "$repo" worktree add -B "$branch" "$worktree" HEAD',
            "fi",
            'cd "$worktree"',
            'cat > "$prompt_file" <<\'CENTO_PROMPT_EOF\'',
            prompt,
            "CENTO_PROMPT_EOF",
            f'{command} < "$prompt_file" | tee "$summary_file"',
            "git status --short > .cento-task-status.txt",
            "git diff --stat > .cento-task-diffstat.txt || true",
            "git diff > .cento-task.patch || true",
        ]
    )


@dataclass
class TaskResult:
    task_id: str
    node: str
    returncode: int
    log_path: Path
    elapsed: float


def run_task(job: dict[str, Any], task: dict[str, Any], agent_command: list[str], dry_run: bool) -> TaskResult:
    run_dir = Path(job["run_dir"])
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{task['id']}.log"
    task_file = run_dir / "tasks" / f"{task['id']}.json"
    task_payload = read_json(task_file)
    prompt = task_payload["prompt"]
    script = shell_script(job, task, prompt, agent_command)
    script_path = run_dir / "tasks" / f"{task['id']}.sh"
    script_path.write_text(script + "\n")

    command = [str(CLUSTER_SH), "exec", task["node"], "--", "bash", "-lc", script]
    started = time.monotonic()
    with log_path.open("w") as log:
        log.write("$ " + " ".join(shlex.quote(part) for part in command[:5]) + " <script>\n")
        log.write(f"# task: {task['id']} on {task['node']}\n")
        log.write(f"# script: {script_path}\n\n")
        if dry_run:
            log.write(script + "\n")
            return TaskResult(task["id"], task["node"], 0, log_path, time.monotonic() - started)
        process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, text=True)
    return TaskResult(task["id"], task["node"], process.returncode, log_path, time.monotonic() - started)


def update_job_status(job_path: Path, job: dict[str, Any], status: str, results: list[TaskResult]) -> None:
    job["status"] = status
    job["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    job["results"] = [
        {
            "task": result.task_id,
            "node": result.node,
            "returncode": result.returncode,
            "log": str(result.log_path),
            "elapsed_seconds": round(result.elapsed, 2),
        }
        for result in results
    ]
    write_json(job_path, job)


def write_summary(job: dict[str, Any], results: list[TaskResult], dry_run: bool) -> Path:
    summary = Path(job["artifacts"]["summary"])
    lines = [
        f"# Cluster Job {job['id']}",
        "",
        f"- feature: {job['feature']}",
        f"- status: {job['status']}",
        f"- mode: {'dry-run' if dry_run else 'executed'}",
        "",
        "## Tasks",
        "",
    ]
    for result in results:
        state = "ok" if result.returncode == 0 else f"failed ({result.returncode})"
        lines.append(f"- `{result.task_id}` on `{result.node}`: {state}; log `{result.log_path}`")
    lines.extend(
        [
            "",
            "## Next Integration Step",
            "",
            "Inspect each task worktree under `workspace/cluster-worktrees/`, compare patches, then merge or cherry-pick the useful branches.",
        ]
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text("\n".join(lines) + "\n")
    return summary


def run_job(args: argparse.Namespace) -> int:
    job_path = find_job(args.job)
    job = read_json(job_path)
    agent_command = shlex.split(args.agent_command) if args.agent_command else shlex.split(job["agent_command"])
    tasks = job.get("tasks") or []
    if not tasks:
        die(f"Job has no tasks: {job_path}")

    print(f"job {job['id']}")
    print(f"feature: {job['feature']}")
    print(f"tasks: {len(tasks)}")
    print(f"mode: {'dry-run' if args.dry_run else 'execute'}")

    results: list[TaskResult] = []
    max_workers = 1 if args.serial else len(tasks)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_task, job, task, agent_command, args.dry_run) for task in tasks]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            state = "ok" if result.returncode == 0 else f"failed:{result.returncode}"
            print(f"{result.task_id} {result.node} {state} {result.log_path}")

    results.sort(key=lambda item: item.task_id)
    status = "dry-run" if args.dry_run else ("succeeded" if all(item.returncode == 0 for item in results) else "failed")
    update_job_status(job_path, job, status, results)
    summary = write_summary(job, results, args.dry_run)
    print(f"summary: {summary}")
    return 0 if all(item.returncode == 0 for item in results) else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Plan and run Cento cluster agent jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Create a cluster job manifest for a feature")
    plan.add_argument("feature", nargs="+", help="Feature request text")
    plan.add_argument("--nodes", help="Comma-separated node ids; defaults to the first configured nodes")
    plan.add_argument("--agents", type=int, default=2, help="Number of parallel agents to plan")
    plan.add_argument("--agent-command", help="Agent command used by run; defaults to CENTO_CLUSTER_AGENT or codex exec")

    run = sub.add_parser("run", help="Run a planned cluster job")
    run.add_argument("job", help="Path, full job id, or unique job id fragment")
    run.add_argument("--dry-run", action="store_true", help="Write task scripts and logs without launching agents")
    run.add_argument("--serial", action="store_true", help="Run tasks one at a time")
    run.add_argument("--agent-command", help="Override the job agent command")

    impl = sub.add_parser("implement", help="Plan and run a feature request")
    impl.add_argument("feature", nargs="+", help="Feature request text")
    impl.add_argument("--nodes", help="Comma-separated node ids")
    impl.add_argument("--agents", type=int, default=2)
    impl.add_argument("--agent-command", help="Override the agent command")
    impl.add_argument("--dry-run", action="store_true")
    impl.add_argument("--serial", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "plan":
        create_plan(args)
        return 0
    if args.command == "run":
        return run_job(args)
    if args.command == "implement":
        job_path = create_plan(args)
        args.job = str(job_path)
        return run_job(args)
    die(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
