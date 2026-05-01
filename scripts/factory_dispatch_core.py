#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import factory_plan
import validation_manifest


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "workspace" / "runs" / "factory"
WORKTREE_ROOT = ROOT / "workspace" / "cluster-worktrees"

QUEUE_STATUSES = {
    "planned",
    "queued",
    "leased",
    "running",
    "collecting",
    "validating",
    "ready_to_integrate",
    "integrated",
    "blocked",
    "expired",
    "deadletter",
}

ACTIVE_LEASE_STATUSES = {"active", "running", "validating"}
RUNNABLE_QUEUE_STATUSES = {"queued", "leased", "running", "validating", "ready_to_integrate"}
PROTECTED_SHARED_PATHS = {
    "README.md",
    "Makefile",
    "data/tools.json",
    "data/cento-cli.json",
    "docs/tool-index.md",
    "docs/platform-support.md",
    "scripts/cento",
}
DEFAULT_STOP_RULES = [
    "do_not_edit_unowned_paths",
    "stop_if_owned_scope_is_insufficient",
    "stop_if_dependency_missing",
    "stop_if_validation_manifest_missing",
    "stop_after_one_ai_call_unless_budget_allows_more",
    "stop_after_two_failed_attempts",
    "stop_if_patch_touches_unowned_paths",
    "stop_if_command_requires_unavailable_secret_device_or_network",
    "do_not_merge",
    "produce_patch_bundle_only",
]
DEFAULT_BACKPRESSURE = {
    "max_live_builders": 4,
    "max_live_validators": 3,
    "max_live_coordinators": 1,
    "max_stale_warning": 5,
    "max_duplicate_runs": 0,
    "max_unintegrated_patches": 8,
    "max_failed_recent": 5,
    "max_ai_calls_per_task": 1,
    "max_strong_model_calls_per_run": 0,
    "default_ai_budget_usd": 2.0,
}


class FactoryDispatchError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve_run_dir(value: str | Path) -> Path:
    text = str(value)
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    if "/" in text or text.startswith("."):
        return ROOT / path
    return RUN_ROOT / text


def queue_dir(run_dir: Path) -> Path:
    return run_dir / "queue"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FactoryDispatchError(f"missing JSON file: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise FactoryDispatchError(f"invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FactoryDispatchError(f"expected object JSON: {rel(path)}")
    return payload


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def append_event(run_dir: Path, event: str, **fields: Any) -> None:
    path = queue_dir(run_dir) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": now_iso(), "event": event, **fields}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def load_plan(run_dir: Path) -> dict[str, Any]:
    plan = read_json(run_dir / "factory-plan.json")
    errors = factory_plan.validate_plan(plan)
    if errors:
        raise FactoryDispatchError("Invalid factory plan:\n" + "\n".join(f"- {error}" for error in errors))
    return plan


def plan_tasks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [task for task in plan.get("tasks") or [] if isinstance(task, dict)]


def task_id(task: dict[str, Any]) -> str:
    return str(task.get("id") or task.get("task_id") or "").strip()


def owned_paths_for(task: dict[str, Any]) -> list[str]:
    paths = task.get("owned_paths")
    if paths is None:
        paths = task.get("owned_scope")
    return [str(path).strip() for path in paths or [] if str(path).strip()]


def git_sha(short: bool = True) -> str:
    command = ["git", "rev-parse", "--short", "HEAD"] if short else ["git", "rev-parse", "HEAD"]
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def path_overlaps(left: str, right: str) -> bool:
    left = left.strip().strip("/")
    right = right.strip().strip("/")
    if not left or not right:
        return False
    return left == right or left.startswith(f"{right}/") or right.startswith(f"{left}/")


def path_allowed(path: str, owned_paths: list[str]) -> bool:
    return any(path_overlaps(path, owned) for owned in owned_paths)


def stable_hash(*items: Any) -> str:
    digest = hashlib.sha256()
    for item in items:
        digest.update(json.dumps(item, sort_keys=True, default=str).encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


@contextmanager
def queue_lock(run_dir: Path, owner: str, ttl_seconds: int = 600):
    qdir = queue_dir(run_dir)
    lock_dir = qdir / "queue.lock"
    qdir.mkdir(parents=True, exist_ok=True)
    acquired = False
    try:
        try:
            lock_dir.mkdir()
            acquired = True
        except FileExistsError:
            meta = read_json(lock_dir / "owner.json") if (lock_dir / "owner.json").exists() else {}
            heartbeat = parse_time(str(meta.get("heartbeat_at") or meta.get("acquired_at") or ""))
            age = (datetime.now(timezone.utc) - heartbeat).total_seconds() if heartbeat else ttl_seconds + 1
            pid = int(meta.get("pid") or 0)
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
            if alive and age <= ttl_seconds:
                raise FactoryDispatchError(f"queue lock is active: {rel(lock_dir)}")
            shutil.rmtree(lock_dir, ignore_errors=True)
            lock_dir.mkdir()
            acquired = True
            append_event(run_dir, "queue_lock_recovered", previous_owner=meta)
        write_json(lock_dir / "owner.json", {"owner": owner, "pid": os.getpid(), "acquired_at": now_iso(), "heartbeat_at": now_iso()})
        yield
    finally:
        if acquired:
            shutil.rmtree(lock_dir, ignore_errors=True)


def manifest_paths(run_dir: Path, item: dict[str, Any]) -> tuple[Path, Path]:
    tid = task_id(item)
    story = str(item.get("story_manifest") or f"tasks/{tid}/story.json")
    validation = str(item.get("validation_manifest") or f"tasks/{tid}/validation.json")
    return (ROOT / story if not Path(story).is_absolute() else Path(story), ROOT / validation if not Path(validation).is_absolute() else Path(validation))


def validate_materialized(run_dir: Path, plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for task in plan_tasks(plan):
        tid = task_id(task)
        story_path = run_dir / "tasks" / tid / "story.json"
        validation_path = run_dir / "tasks" / tid / "validation.json"
        if not story_path.exists():
            errors.append(f"task {tid}: missing story.json")
        if not validation_path.exists():
            errors.append(f"task {tid}: missing validation.json")
            continue
        try:
            validation = validation_manifest.load_validation(validation_path)
            for error in validation_manifest.validate_validation_manifest(validation):
                errors.append(f"task {tid}: invalid validation.json: {error}")
        except Exception as exc:
            errors.append(f"task {tid}: invalid validation.json: {exc}")
    return errors


def validate_dependencies(tasks: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    ids = [task_id(item) for item in tasks]
    known = set(ids)
    if len(ids) != len(known):
        errors.append("task ids must be unique")
    graph: dict[str, list[str]] = {}
    for item in tasks:
        tid = task_id(item)
        deps = [str(dep) for dep in item.get("dependencies") or []]
        graph[tid] = deps
        for dep in deps:
            if dep not in known:
                errors.append(f"task {tid}: unknown dependency {dep}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(tid: str, trail: list[str]) -> None:
        if tid in visited:
            return
        if tid in visiting:
            errors.append("dependency cycle: " + " -> ".join([*trail, tid]))
            return
        visiting.add(tid)
        for dep in graph.get(tid, []):
            visit(dep, [*trail, tid])
        visiting.remove(tid)
        visited.add(tid)

    for tid in ids:
        visit(tid, [])
    return errors


def normalize_queue_tasks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("tasks") or []
    if isinstance(raw, dict):
        return [item for item in raw.values() if isinstance(item, dict)]
    return [item for item in raw if isinstance(item, dict)]


def validate_queue_payload(payload: dict[str, Any], run_dir: Path | None = None) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "factory-queue/v1":
        errors.append("schema_version must be factory-queue/v1")
    tasks = normalize_queue_tasks(payload)
    if not tasks:
        errors.append("tasks must be a non-empty list or object")
        return errors
    errors.extend(validate_dependencies(tasks))
    runnable: list[dict[str, Any]] = []
    for item in tasks:
        tid = task_id(item)
        if not tid:
            errors.append("task missing task_id")
            continue
        status = str(item.get("status") or "")
        if status not in QUEUE_STATUSES:
            errors.append(f"task {tid}: invalid status {status}")
        owned = owned_paths_for(item)
        if not owned:
            errors.append(f"task {tid}: owned_paths must be declared")
        story = item.get("story_manifest")
        validation = item.get("validation_manifest")
        if not story:
            errors.append(f"task {tid}: missing story_manifest")
        if not validation:
            errors.append(f"task {tid}: missing validation_manifest")
        if run_dir:
            for label, value in (("story_manifest", story), ("validation_manifest", validation)):
                if value:
                    path = Path(str(value))
                    resolved = path if path.is_absolute() else ROOT / path
                    if not resolved.exists():
                        errors.append(f"task {tid}: {label} not found: {value}")
        if status in RUNNABLE_QUEUE_STATUSES:
            runnable.append(item)
    for index, left in enumerate(runnable):
        for right in runnable[index + 1 :]:
            for left_path in owned_paths_for(left):
                for right_path in owned_paths_for(right):
                    if path_overlaps(left_path, right_path):
                        errors.append(f"runnable owned path overlap: {left_path} claimed by {task_id(left)} and {task_id(right)}")
    return errors


def task_priority(task: dict[str, Any]) -> int:
    risk = str(task.get("risk") or "medium")
    lane = str(task.get("lane") or "builder")
    score = {"low": 10, "medium": 20, "high": 30}.get(risk, 20)
    if bool(task.get("no_model_eligible")):
        score -= 3
    if lane == "docs-evidence":
        score += 8
    if lane == "validator":
        score += 4
    return max(1, score)


def issue_lookup(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "taskstream-issues.json"
    if not path.exists():
        return {}
    payload = read_json(path)
    return {str(item.get("task")): item.get("issue") for item in payload.get("issues") or [] if isinstance(item, dict)}


def queue_stats(tasks: list[dict[str, Any]]) -> dict[str, int]:
    stats = {status: 0 for status in sorted(QUEUE_STATUSES)}
    for item in tasks:
        status = str(item.get("status") or "planned")
        stats[status] = stats.get(status, 0) + 1
    stats["total"] = len(tasks)
    stats["waiting"] = stats.get("planned", 0)
    stats["done"] = stats.get("integrated", 0)
    return stats


def write_queue_compat(run_dir: Path, queue: dict[str, Any]) -> None:
    qdir = queue_dir(run_dir)
    tasks = normalize_queue_tasks(queue)
    task_map = {task_id(item): item for item in tasks}
    state = {
        "schema_version": "factory-queue/v1",
        "run_dir": rel(run_dir),
        "run_id": queue.get("run_id"),
        "package": queue.get("package"),
        "generated_at": queue.get("created_at"),
        "merge_order": [task_id(item) for item in tasks],
        "tasks": task_map,
        "stats": queue_stats(tasks),
    }
    write_json(qdir / "state.json", state)
    write_jsonl(qdir / "queued.jsonl", [item for item in tasks if item.get("status") == "queued"])
    write_jsonl(qdir / "waiting.jsonl", [item for item in tasks if item.get("status") == "planned"])
    write_jsonl(qdir / "leased.jsonl", [item for item in tasks if item.get("status") == "leased"])
    write_jsonl(qdir / "validating.jsonl", [item for item in tasks if item.get("status") == "validating"])
    write_jsonl(qdir / "blocked.jsonl", [item for item in tasks if item.get("status") == "blocked"])
    write_jsonl(qdir / "done.jsonl", [item for item in tasks if item.get("status") == "integrated"])
    owner_map: dict[str, str] = {}
    for item in tasks:
        for path in owned_paths_for(item):
            owner_map[path] = task_id(item)
    write_json(qdir / "owned-paths.json", {"schema_version": "factory-owned-paths/v1", "paths": owner_map})


def generate_queue(run_dir: Path, mode: str = "dry_run") -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    with queue_lock(run_dir, "factory-queue"):
        plan = load_plan(run_dir)
        materialized_errors = validate_materialized(run_dir, plan)
        if materialized_errors:
            raise FactoryDispatchError("Factory task manifests are incomplete:\n" + "\n".join(f"- {error}" for error in materialized_errors))
        issues = issue_lookup(run_dir)
        tasks = []
        for task in plan_tasks(plan):
            tid = task_id(task)
            deps = [str(dep) for dep in task.get("dependencies") or []]
            status = "queued" if not deps else "planned"
            tasks.append(
                {
                    "task_id": tid,
                    "issue_id": issues.get(tid),
                    "title": str(task.get("title") or tid),
                    "lane": str(task.get("lane") or "builder"),
                    "node": str(task.get("node") or "linux"),
                    "status": status,
                    "priority": task_priority(task),
                    "risk": str(task.get("risk") or "medium"),
                    "no_model_eligible": bool(task.get("no_model_eligible")),
                    "owned_paths": owned_paths_for(task),
                    "dependencies": deps,
                    "story_manifest": rel(run_dir / "tasks" / tid / "story.json"),
                    "validation_manifest": rel(run_dir / "tasks" / tid / "validation.json"),
                    "worktree": None,
                    "lease_id": None,
                    "attempts": 0,
                    "max_attempts": int(task.get("max_attempts") or 2),
                    "ai_call_budget": int(task.get("ai_call_budget") or 1),
                    "estimated_cost_limit_usd": float(task.get("estimated_cost_limit_usd") or 0.25),
                    "patch_bundle": None,
                    "last_event": status,
                }
            )
        queue = {
            "schema_version": "factory-queue/v1",
            "run_id": str(plan.get("run_id") or run_dir.name),
            "package": str(plan.get("package") or run_dir.name),
            "base_sha": git_sha(),
            "created_at": now_iso(),
            "mode": mode,
            "tasks": tasks,
            "stats": queue_stats(tasks),
        }
        errors = validate_queue_payload(queue, run_dir)
        if errors:
            raise FactoryDispatchError("Invalid generated queue:\n" + "\n".join(f"- {error}" for error in errors))
        qdir = queue_dir(run_dir)
        write_json(qdir / "queue.json", queue)
        write_json(qdir / "leases.json", {"schema_version": "factory-leases/v1", "run_id": queue["run_id"], "leases": []})
        write_json(qdir / "backpressure.json", {"schema_version": "factory-backpressure/v1", "run_id": queue["run_id"], "thresholds": DEFAULT_BACKPRESSURE, "blocked": False, "reasons": []})
        write_jsonl(qdir / "deadletter.jsonl", [])
        write_queue_compat(run_dir, queue)
        events = [
            {"ts": now_iso(), "event": "queue_generated", "run_id": queue["run_id"], "tasks": len(tasks)},
            *[
                {"ts": now_iso(), "event": "task_queued" if item["status"] == "queued" else "task_planned", "task_id": item["task_id"], "status": item["status"]}
                for item in tasks
            ],
        ]
        write_jsonl(qdir / "events.jsonl", events)
        write_json(
            run_dir / "task-graph.json",
            {
                "schema_version": "factory-task-graph/v1",
                "run_id": queue["run_id"],
                "nodes": [item["task_id"] for item in tasks],
                "edges": [{"from": dep, "to": item["task_id"]} for item in tasks for dep in item.get("dependencies") or []],
            },
        )
        return queue


def load_queue(run_dir: Path) -> dict[str, Any]:
    path = queue_dir(run_dir) / "queue.json"
    if path.exists():
        return read_json(path)
    legacy = queue_dir(run_dir) / "state.json"
    if legacy.exists():
        payload = read_json(legacy)
        tasks = normalize_queue_tasks(payload)
        converted = {
            "schema_version": "factory-queue/v1",
            "run_id": str(payload.get("run_id") or run_dir.name),
            "package": str(payload.get("package") or ""),
            "base_sha": git_sha(),
            "created_at": str(payload.get("generated_at") or now_iso()),
            "mode": "dry_run",
            "tasks": tasks,
            "stats": queue_stats(tasks),
        }
        write_json(path, converted)
        return converted
    return generate_queue(run_dir)


def save_queue(run_dir: Path, queue: dict[str, Any]) -> None:
    queue["stats"] = queue_stats(normalize_queue_tasks(queue))
    write_json(queue_dir(run_dir) / "queue.json", queue)
    write_queue_compat(run_dir, queue)


def find_queue_task(queue: dict[str, Any], tid: str) -> dict[str, Any]:
    for item in normalize_queue_tasks(queue):
        if task_id(item) == tid:
            return item
    raise FactoryDispatchError(f"task not found in queue: {tid}")


def load_leases(run_dir: Path) -> dict[str, Any]:
    path = queue_dir(run_dir) / "leases.json"
    if not path.exists():
        queue = load_queue(run_dir)
        payload = {"schema_version": "factory-leases/v1", "run_id": queue.get("run_id") or run_dir.name, "leases": []}
        write_json(path, payload)
        return payload
    return read_json(path)


def save_leases(run_dir: Path, leases: dict[str, Any]) -> None:
    write_json(queue_dir(run_dir) / "leases.json", leases)


def expire_leases(run_dir: Path, leases: dict[str, Any]) -> None:
    changed = False
    now = datetime.now(timezone.utc)
    for lease in leases.get("leases") or []:
        if not isinstance(lease, dict) or lease.get("status") not in ACTIVE_LEASE_STATUSES:
            continue
        expires_at = parse_time(str(lease.get("expires_at") or ""))
        heartbeat = parse_time(str(lease.get("heartbeat_at") or ""))
        missed = heartbeat and (now - heartbeat).total_seconds() > 600
        if (expires_at and expires_at < now) or missed:
            lease["status"] = "expired"
            lease["release_reason"] = "ttl_expired" if expires_at and expires_at < now else "missed_heartbeat"
            changed = True
            append_event(run_dir, "lease_expired", task_id=lease.get("task_id"), lease_id=lease.get("lease_id"))
    if changed:
        save_leases(run_dir, leases)


def lease_conflicts(candidate_paths: list[str], leases: dict[str, Any]) -> list[str]:
    conflicts: list[str] = []
    for lease in leases.get("leases") or []:
        if not isinstance(lease, dict) or lease.get("status") not in ACTIVE_LEASE_STATUSES:
            continue
        for candidate in candidate_paths:
            for active in lease.get("owned_paths") or []:
                if path_overlaps(str(candidate), str(active)):
                    conflicts.append(f"{candidate} conflicts with active lease {lease.get('lease_id')} on {active}")
    return conflicts


def worktree_metadata(run_dir: Path, item: dict[str, Any], *, status: str = "allocated") -> dict[str, Any]:
    tid = task_id(item)
    path = WORKTREE_ROOT / run_dir.name / tid
    return {
        "schema_version": "factory-worktree/v1",
        "task_id": tid,
        "base_sha": git_sha(),
        "path": rel(path),
        "created_at": now_iso(),
        "status": status,
    }


def write_worktree(run_dir: Path, item: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    meta = worktree_metadata(run_dir, item, status="planned" if dry_run else "allocated")
    task_dir = run_dir / "tasks" / task_id(item)
    write_json(task_dir / "worktree.json", meta)
    return meta


def simulate_or_acquire_lease(run_dir: Path, tid: str, *, dry_run: bool, runtime: str = "codex", owner: str = "factory-dispatch") -> dict[str, Any]:
    queue = load_queue(run_dir)
    item = find_queue_task(queue, tid)
    leases = load_leases(run_dir)
    expire_leases(run_dir, leases)
    conflicts = lease_conflicts(owned_paths_for(item), leases)
    worktree = write_worktree(run_dir, item, dry_run=dry_run)
    allowed = not conflicts and str(item.get("status")) in {"queued", "planned", "expired"}
    acquired_at = datetime.now(timezone.utc).replace(microsecond=0)
    lease = {
        "lease_id": f"lease-{tid}-{str(item.get('node') or 'node')}-{len(leases.get('leases') or []) + 1:03d}",
        "task_id": tid,
        "issue_id": item.get("issue_id"),
        "lane": item.get("lane"),
        "node": item.get("node"),
        "runtime": runtime,
        "owner": owner,
        "status": "simulated" if dry_run else "active",
        "owned_paths": owned_paths_for(item),
        "worktree": worktree["path"],
        "acquired_at": acquired_at.isoformat().replace("+00:00", "Z"),
        "heartbeat_at": acquired_at.isoformat().replace("+00:00", "Z"),
        "expires_at": (acquired_at + timedelta(minutes=45)).isoformat().replace("+00:00", "Z"),
        "release_reason": None,
        "dry_run": dry_run,
    }
    payload = {
        "schema_version": "factory-lease-result/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "task_id": tid,
        "dry_run": dry_run,
        "allowed": allowed,
        "conflicts": conflicts,
        "lease": lease,
        "worktree": worktree,
    }
    write_json(run_dir / "tasks" / tid / ("lease-simulation.json" if dry_run else "lease.json"), payload)
    if allowed and not dry_run:
        leases.setdefault("leases", []).append(lease)
        save_leases(run_dir, leases)
        item["status"] = "leased"
        item["lease_id"] = lease["lease_id"]
        item["worktree"] = worktree["path"]
        item["last_event"] = "leased"
        save_queue(run_dir, queue)
    append_event(run_dir, "lease_simulated" if dry_run else "lease_acquired", task_id=tid, allowed=allowed, conflicts=conflicts)
    return payload


def render_worker_prompt(run_dir: Path, item: dict[str, Any], *, mode: str = "dry_run") -> dict[str, Any]:
    tid = task_id(item)
    task_dir = run_dir / "tasks" / tid
    story_path = task_dir / "story.json"
    validation_path = task_dir / "validation.json"
    story = read_json(story_path)
    validation = read_json(validation_path)
    prompt_lines = [
        f"# Factory Worker Prompt: {tid}",
        "",
        "You are a bounded patch producer for the Factory Execution Control Plane.",
        "",
        "## Task",
        "",
        f"- Title: {item.get('title')}",
        f"- Lane: {item.get('lane')}",
        f"- Node: {item.get('node')}",
        f"- Risk: {item.get('risk')}",
        f"- Mode: {mode}",
        "",
        "## Owned Paths",
        "",
        *[f"- `{path}`" for path in owned_paths_for(item)],
        "",
        "## Required Inputs",
        "",
        f"- `{rel(story_path)}`",
        f"- `{rel(validation_path)}`",
        f"- `{rel(run_dir / 'factory-plan.json')}`",
        "",
        "## Required Outputs",
        "",
        "- `patch.diff`",
        "- `changed-files.txt`",
        "- `diffstat.txt`",
        "- `validation-result.json`",
        "- `handoff.md`",
        "- `evidence/`",
        "",
        "## Stop Rules",
        "",
        *[f"- {rule}" for rule in DEFAULT_STOP_RULES],
        "",
    ]
    prompt = "\n".join(prompt_lines)
    prompt_path = task_dir / "worker-prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    record = {
        "schema_version": "factory-prompt-record/v1",
        "task_id": tid,
        "template_id": "factory-worker/v1",
        "input_hash": stable_hash(item),
        "context_hash": stable_hash(story, validation),
        "prompt_hash": stable_hash(prompt),
        "runtime": "codex",
        "model_tier": "cheap_worker",
        "ai_call_budget": int(item.get("ai_call_budget") or 1),
        "estimated_cost_limit_usd": float(item.get("estimated_cost_limit_usd") or 0.25),
        "cache_status": "new",
    }
    write_json(task_dir / "prompt-record.json", record)
    dispatch = {
        "schema_version": "factory-dispatch/v1",
        "task_id": tid,
        "mode": mode,
        "runtime": "codex",
        "model_tier": "cheap_worker",
        "worker_prompt": "worker-prompt.md",
        "context_files": ["story.json", "validation.json", "../../factory-plan.json"],
        "forbidden_paths": [".env", "data/secrets.json"],
        "stop_rules": DEFAULT_STOP_RULES,
    }
    write_json(task_dir / "dispatch.json", dispatch)
    return {"prompt": rel(prompt_path), "record": rel(task_dir / "prompt-record.json"), "dispatch": rel(task_dir / "dispatch.json")}


def task_dependencies_satisfied(queue: dict[str, Any], item: dict[str, Any]) -> bool:
    tasks = {task_id(task): task for task in normalize_queue_tasks(queue)}
    for dep in item.get("dependencies") or []:
        dep_task = tasks.get(str(dep))
        if not dep_task or dep_task.get("status") not in {"integrated", "ready_to_integrate"}:
            return False
    return True


def select_dispatch_tasks(queue: dict[str, Any], *, lane: str, limit: int, include_waiting: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks = sorted(normalize_queue_tasks(queue), key=lambda item: (int(item.get("priority") or 20), task_id(item)))
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in tasks:
        reason = ""
        if lane and str(item.get("lane") or "") != lane:
            reason = "lane_mismatch"
        elif str(item.get("status")) not in {"queued", "planned", "expired"}:
            reason = f"status_{item.get('status')}"
        elif not include_waiting and not task_dependencies_satisfied(queue, item):
            reason = "dependencies_not_satisfied"
        elif len(selected) >= limit:
            reason = "max_selected"
        if reason:
            skipped.append({"task_id": task_id(item), "reason": reason, "status": item.get("status"), "lane": item.get("lane")})
        else:
            selected.append(item)
    return selected, skipped


def manager_scan() -> tuple[int, dict[str, Any], str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "agent_manager.py"), "scan", "--json"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    payload: dict[str, Any] = {}
    if proc.returncode == 0:
        try:
            decoded = json.loads(proc.stdout)
            payload = decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            payload = {}
    return proc.returncode, payload, proc.stderr.strip() or proc.stdout.strip()[-500:]


def git_dirty_files() -> list[str]:
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    files: list[str] = []
    if proc.returncode != 0:
        return files
    for line in proc.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[-1]
        files.append(path)
    return files


def preflight(run_dir: Path, *, max_actionable_stale: int = 5, max_risk_count: int = 10) -> dict[str, Any]:
    queue = load_queue(run_dir)
    queue_errors = validate_queue_payload(queue, run_dir)
    manager_exit, manager_payload, manager_error = manager_scan()
    summary = manager_payload.get("summary") if isinstance(manager_payload.get("summary"), dict) else {}
    reasons: list[str] = []
    if queue_errors:
        reasons.extend(f"queue: {error}" for error in queue_errors)
    if manager_exit != 0:
        reasons.append(f"agent_manager_unavailable: {manager_error}")
    if int(summary.get("critical", 0) or 0) > 0:
        reasons.append(f"agent_manager_critical: {summary.get('critical')}")
    actionable_stale = int(summary.get("actionable_stale", 0) or 0)
    risk_count = int(summary.get("risk_count", 0) or 0)
    if actionable_stale > max_actionable_stale:
        reasons.append(f"actionable_stale {actionable_stale} exceeds {max_actionable_stale}")
    if risk_count > max_risk_count:
        reasons.append(f"risk_count {risk_count} exceeds {max_risk_count}")
    owned = [
        path
        for item in normalize_queue_tasks(queue)
        if str(item.get("status") or "") in RUNNABLE_QUEUE_STATUSES
        for path in owned_paths_for(item)
    ]
    run_artifact_prefix = rel(run_dir).rstrip("/") + "/"
    dirty_owned = [
        path
        for path in git_dirty_files()
        if not path.startswith(run_artifact_prefix) and any(path_overlaps(path, owned_path) for owned_path in owned)
    ]
    if dirty_owned:
        reasons.append("dirty_git_touches_owned_paths: " + ", ".join(dirty_owned[:12]))
    unintegrated = [
        path
        for path in (run_dir / "patches").glob("*/patch.json")
        if read_json(path).get("integration_status") not in {"integrated", "rejected"}
    ] if (run_dir / "patches").exists() else []
    if len(unintegrated) > DEFAULT_BACKPRESSURE["max_unintegrated_patches"]:
        reasons.append(f"unintegrated_patch_count {len(unintegrated)} exceeds {DEFAULT_BACKPRESSURE['max_unintegrated_patches']}")
    payload = {
        "schema_version": "factory-preflight/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "run_dir": rel(run_dir),
        "agent_manager_exit_code": manager_exit,
        "agent_manager_available": manager_exit == 0,
        "blocked": bool(reasons),
        "reasons": reasons,
        "reason": "; ".join(reasons),
        "manager_summary": summary,
        "queue_errors": queue_errors,
        "dirty_owned_paths": dirty_owned,
        "thresholds": {**DEFAULT_BACKPRESSURE, "max_stale_warning": max_actionable_stale, "max_failed_recent": max_risk_count},
        "tasks": len(normalize_queue_tasks(queue)),
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "preflight-summary.json", payload)
    write_json(run_dir / "preflight.json", payload)
    write_json(
        queue_dir(run_dir) / "backpressure.json",
        {
            "schema_version": "factory-backpressure/v1",
            "run_id": payload["run_id"],
            "blocked": payload["blocked"],
            "reasons": reasons,
            "thresholds": payload["thresholds"],
            "generated_at": payload["generated_at"],
        },
    )
    append_event(run_dir, "preflight_completed", blocked=payload["blocked"], reasons=reasons)
    return payload


def dispatch_dry_run(
    run_dir: Path,
    *,
    lane: str = "",
    limit: int = 4,
    include_waiting: bool = False,
    execute: bool = False,
    max_actionable_stale: int = 5,
    max_risk_count: int = 10,
) -> dict[str, Any]:
    preflight_payload = preflight(run_dir, max_actionable_stale=max_actionable_stale, max_risk_count=max_risk_count)
    if execute and preflight_payload["blocked"]:
        raise FactoryDispatchError("execution blocked by preflight: " + preflight_payload["reason"])
    queue = load_queue(run_dir)
    selected, skipped = select_dispatch_tasks(queue, lane=lane, limit=limit, include_waiting=include_waiting)
    selected_payload: list[dict[str, Any]] = []
    for item in selected:
        tid = task_id(item)
        lease_result = simulate_or_acquire_lease(run_dir, tid, dry_run=not execute)
        prompt = render_worker_prompt(run_dir, item, mode="execute" if execute else "dry_run")
        selected_payload.append(
            {
                "task_id": tid,
                "issue_id": item.get("issue_id"),
                "lane": item.get("lane"),
                "node": item.get("node"),
                "priority": item.get("priority"),
                "risk": item.get("risk"),
                "owned_paths": owned_paths_for(item),
                "lease": lease_result["lease"],
                "worktree": lease_result["worktree"],
                "prompt_bundle": prompt,
                "estimated_cost_limit_usd": item.get("estimated_cost_limit_usd", 0.25),
                "validation_commands": read_json(run_dir / "tasks" / tid / "validation.json").get("checks", []),
                "stop_rules": DEFAULT_STOP_RULES,
                "would_run": execute,
            }
        )
    for item in normalize_queue_tasks(queue):
        task_dir = run_dir / "tasks" / task_id(item)
        if not (task_dir / "worker-prompt.md").exists() or not (task_dir / "dispatch.json").exists():
            render_worker_prompt(run_dir, item, mode="dry_run_staged")
    payload = {
        "schema_version": "factory-dispatch-plan/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "run_dir": rel(run_dir),
        "mode": "execute" if execute else "dry_run",
        "dry_run": not execute,
        "lane": lane,
        "max": limit,
        "selected": selected_payload,
        "skipped": skipped,
        "preflight_blocked": preflight_payload["blocked"],
        "preflight_reasons": preflight_payload["reasons"],
        "blocked_reason": "" if selected_payload else "no runnable tasks matched lane/dependency filters",
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": round(sum(float(item.get("estimated_cost_limit_usd") or 0) for item in selected_payload), 4) if execute else 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "dispatch-plan.json", payload)
    append_event(run_dir, "dispatch_planned" if not execute else "dispatch_execute_gated", selected=len(selected_payload), skipped=len(skipped), lane=lane)
    return payload


def changed_files_from_patch(path: Path) -> list[str]:
    if not path.exists():
        return []
    changed: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("+++ b/"):
            changed.append(line[6:])
        elif line.startswith("--- a/"):
            candidate = line[6:]
            if candidate != "/dev/null":
                changed.append(candidate)
    return sorted(set(changed))


def read_changed_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)
    return True


def synth_validation_result(task_dir: Path, status: str) -> Path:
    path = task_dir / "validation-result.json"
    if not path.exists():
        write_json(
            path,
            {
                "schema_version": "factory-validation-result/v1",
                "status": status,
                "ai_calls_used": 0,
                "estimated_ai_cost_usd": 0,
                "generated_at": now_iso(),
            },
        )
    return path


def collect_patches(run_dir: Path) -> dict[str, Any]:
    queue = load_queue(run_dir)
    patches_dir = run_dir / "patches"
    collected: list[dict[str, Any]] = []
    for item in normalize_queue_tasks(queue):
        tid = task_id(item)
        task_dir = run_dir / "tasks" / tid
        patch_dir = patches_dir / tid
        patch_dir.mkdir(parents=True, exist_ok=True)
        sources = [
            task_dir,
            WORKTREE_ROOT / run_dir.name / tid,
        ]
        patch_src = next((source / "patch.diff" for source in sources if (source / "patch.diff").exists()), None)
        changed_src = next((source / "changed-files.txt" for source in sources if (source / "changed-files.txt").exists()), None)
        diffstat_src = next((source / "diffstat.txt" for source in sources if (source / "diffstat.txt").exists()), None)
        handoff_src = next((source / "handoff.md" for source in sources if (source / "handoff.md").exists()), None)
        validation_src = next((source / "validation-result.json" for source in sources if (source / "validation-result.json").exists()), None)
        evidence_src = next((source / "evidence" for source in sources if (source / "evidence").exists()), None)
        patch_present = bool(patch_src and patch_src.exists())
        if patch_src:
            copy_if_exists(patch_src, patch_dir / "patch.diff")
        else:
            (patch_dir / "patch.diff").write_text("", encoding="utf-8")
        changed_files = read_changed_files(changed_src) if changed_src else changed_files_from_patch(patch_dir / "patch.diff")
        if changed_src:
            copy_if_exists(changed_src, patch_dir / "changed-files.txt")
        else:
            (patch_dir / "changed-files.txt").write_text("\n".join(changed_files) + ("\n" if changed_files else ""), encoding="utf-8")
        if diffstat_src:
            copy_if_exists(diffstat_src, patch_dir / "diffstat.txt")
        else:
            (patch_dir / "diffstat.txt").write_text("No patch produced.\n" if not patch_present else "Patch diffstat unavailable.\n", encoding="utf-8")
        if handoff_src:
            copy_if_exists(handoff_src, patch_dir / "handoff.md")
        else:
            (patch_dir / "handoff.md").write_text(f"# {tid} Handoff\n\nPatch bundle is explicitly missing in dry-run collection.\n", encoding="utf-8")
        if validation_src:
            copy_if_exists(validation_src, patch_dir / "validation-result.json")
        else:
            copy_if_exists(synth_validation_result(task_dir, "not_run" if not patch_present else "unknown"), patch_dir / "validation-result.json")
        if evidence_src:
            copy_if_exists(evidence_src, patch_dir / "evidence")
        else:
            (patch_dir / "evidence").mkdir(exist_ok=True)
            (patch_dir / "evidence" / "README.md").write_text("Dry-run patch collection evidence placeholder.\n", encoding="utf-8")
        outside = [path for path in changed_files if not path_allowed(path, owned_paths_for(item))]
        protected = [path for path in changed_files if path in PROTECTED_SHARED_PATHS and not path_allowed(path, owned_paths_for(item))]
        validation_result = read_json(patch_dir / "validation-result.json")
        patch = {
            "schema_version": "factory-patch/v1",
            "run_id": queue.get("run_id") or run_dir.name,
            "task_id": tid,
            "issue_id": item.get("issue_id"),
            "base_sha": queue.get("base_sha") or git_sha(),
            "worker_run_id": "",
            "patch_file": "patch.diff",
            "changed_files": changed_files,
            "diffstat_file": "diffstat.txt",
            "handoff_file": "handoff.md",
            "validation_result": "validation-result.json",
            "evidence_paths": ["evidence/README.md"],
            "collection_state": "collected" if patch_present else "missing",
            "owned_path_check": "passed" if not outside else "failed",
            "owned_path_failures": outside,
            "protected_path_failures": protected,
            "git_apply_check": "pending" if patch_present else "skipped_no_patch",
            "docs_registry_gate": "not_applicable",
            "validation_status": validation_result.get("status", "unknown"),
            "integration_status": "candidate" if patch_present and not outside and not protected else "missing" if not patch_present else "rejected",
        }
        write_json(patch_dir / "patch.json", patch)
        item["patch_bundle"] = rel(patch_dir / "patch.json")
        if patch_present:
            item["status"] = "collecting"
        collected.append({"task_id": tid, "patch_bundle": rel(patch_dir / "patch.json"), "state": patch["collection_state"], "integration_status": patch["integration_status"]})
    save_queue(run_dir, queue)
    payload = {
        "schema_version": "factory-patch-collection/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "patches": collected,
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(run_dir / "patch-collection-summary.json", payload)
    append_event(run_dir, "patch_collection_completed", patches=len(collected))
    return payload


def validate_patch_json(path: Path) -> list[str]:
    payload = read_json(path)
    errors = []
    if payload.get("schema_version") != "factory-patch/v1":
        errors.append("schema_version must be factory-patch/v1")
    for field in ("run_id", "task_id", "patch_file", "changed_files", "owned_path_check", "integration_status"):
        if field not in payload:
            errors.append(f"missing field: {field}")
    if payload.get("owned_path_check") == "failed":
        errors.append("owned_path_check failed")
    return errors


def git_apply_check(patch_path: Path) -> tuple[str, str]:
    if not patch_path.exists() or not patch_path.read_text(encoding="utf-8", errors="ignore").strip():
        return "skipped_no_patch", ""
    proc = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return ("passed" if proc.returncode == 0 else "failed", proc.stderr.strip() or proc.stdout.strip())


def docs_gate_status(changed_files: list[str]) -> tuple[str, str]:
    command_surface = any(path.startswith("scripts/") or path in {"data/tools.json", "data/cento-cli.json"} for path in changed_files)
    if not command_surface:
        return "not_applicable", ""
    required = {"data/tools.json", "data/cento-cli.json", "docs/tool-index.md", "docs/platform-support.md", "README.md"}
    missing = sorted(required - set(changed_files))
    if missing:
        return "failed", "missing docs/registry updates: " + ", ".join(missing)
    return "passed", ""


def integration_dry_run(run_dir: Path) -> dict[str, Any]:
    queue = load_queue(run_dir)
    plan = load_plan(run_dir)
    merge_order = [str(item) for item in (plan.get("integration") or {}).get("merge_order") or [task_id(item) for item in normalize_queue_tasks(queue)]]
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    seen_files: dict[str, str] = {}
    for tid in merge_order:
        item = find_queue_task(queue, tid)
        patch_path = run_dir / "patches" / tid / "patch.json"
        if not patch_path.exists():
            missing.append({"task_id": tid, "reason": "patch_bundle_missing"})
            continue
        patch = read_json(patch_path)
        changed_files = [str(path) for path in patch.get("changed_files") or []]
        apply_status, apply_error = git_apply_check(patch_path.parent / str(patch.get("patch_file") or "patch.diff"))
        outside = [path for path in changed_files if not path_allowed(path, owned_paths_for(item))]
        protected = [path for path in changed_files if path in PROTECTED_SHARED_PATHS and not path_allowed(path, owned_paths_for(item))]
        docs_status, docs_reason = docs_gate_status(changed_files)
        validation = read_json(patch_path.parent / str(patch.get("validation_result") or "validation-result.json"))
        task_conflicts = []
        for changed in changed_files:
            if changed in seen_files:
                task_conflicts.append({"file": changed, "first_task": seen_files[changed], "second_task": tid})
            else:
                seen_files[changed] = tid
        conflicts.extend(task_conflicts)
        reasons = []
        if patch.get("collection_state") == "missing":
            missing.append({"task_id": tid, "reason": "patch_explicitly_missing"})
            continue
        if outside:
            reasons.append("changed_files_outside_owned_paths")
        if protected:
            reasons.append("protected_shared_files_touched")
        if apply_status == "failed":
            reasons.append("git_apply_check_failed")
        if docs_status == "failed":
            reasons.append("docs_registry_gate_failed")
        if task_conflicts:
            reasons.append("patch_conflict")
        if validation.get("status") not in {"passed", "pass", "ok"}:
            reasons.append("validation_not_passed")
        record = {
            "task_id": tid,
            "patch_bundle": rel(patch_path),
            "changed_files": changed_files,
            "owned_path_check": "passed" if not outside else "failed",
            "git_apply_check": apply_status,
            "git_apply_error": apply_error,
            "docs_registry_gate": docs_status,
            "docs_registry_reason": docs_reason,
            "validation_status": validation.get("status", "unknown"),
            "reasons": reasons,
        }
        if reasons:
            rejected.append(record)
        else:
            candidates.append(record)
    integration_dir = run_dir / "integration"
    rollback = {
        "schema_version": "factory-rollback/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "strategy": "reverse_patch",
        "base_sha": queue.get("base_sha") or git_sha(),
        "patches": [
            {
                "task_id": item["task_id"],
                "patch_file": rel(run_dir / "patches" / item["task_id"] / "patch.diff"),
                "reverse_command": f"git apply -R {rel(run_dir / 'patches' / item['task_id'] / 'patch.diff')}",
            }
            for item in candidates
        ],
    }
    release_gates = {
        "schema_version": "factory-release-gates/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "required_gates": ["owned_path_check", "git_apply_check", "validation_passed", "docs_registry_alignment", "release_packet_present"],
        "gates": {
            "owned_path_check": "passed" if not any("changed_files_outside_owned_paths" in item.get("reasons", []) for item in rejected) else "failed",
            "git_apply_check": "passed" if not any("git_apply_check_failed" in item.get("reasons", []) for item in rejected) else "failed",
            "validation_passed": "passed" if not any("validation_not_passed" in item.get("reasons", []) for item in rejected) else "failed",
            "docs_registry_alignment": "passed" if not any("docs_registry_gate_failed" in item.get("reasons", []) for item in rejected) else "failed",
            "release_packet_present": "pending",
        },
        "status": "failed" if rejected or conflicts else "passed",
        "missing_patches": missing,
    }
    integration = {
        "schema_version": "factory-integration/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "base_sha": queue.get("base_sha") or git_sha(),
        "mode": "dry_run",
        "merge_order": merge_order,
        "candidates": candidates,
        "rejected": rejected,
        "missing": missing,
        "conflicts": conflicts,
        "required_gates": release_gates["required_gates"],
        "rollback": {"strategy": "patch_reverse", "rollback_plan": "rollback-plan.json"},
        "decision": "blocked" if rejected or conflicts else "dry_run_complete",
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
        "generated_at": now_iso(),
    }
    write_json(integration_dir / "integration-plan.json", integration)
    write_json(integration_dir / "conflict-report.json", {"schema_version": "factory-conflict-report/v1", "run_id": integration["run_id"], "conflicts": conflicts, "rejected": rejected})
    write_json(integration_dir / "rollback-plan.json", rollback)
    write_json(integration_dir / "release-gates.json", release_gates)
    lines = [
        "# Factory Integration Dry-Run",
        "",
        f"- Run: `{integration['run_id']}`",
        f"- Decision: `{integration['decision']}`",
        f"- Candidates: `{len(candidates)}`",
        f"- Rejected: `{len(rejected)}`",
        f"- Missing patches: `{len(missing)}`",
        f"- Conflicts: `{len(conflicts)}`",
        "- AI calls used: `0`",
        "",
        "## Merge Order",
        "",
        *[f"- `{tid}`" for tid in merge_order],
        "",
    ]
    if rejected:
        lines.extend(["## Rejected", "", *[f"- `{item['task_id']}`: {', '.join(item['reasons'])}" for item in rejected], ""])
    (integration_dir / "dry-run-summary.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(run_dir / "integration-plan.json", integration)
    append_event(run_dir, "integration_dry_run_completed", decision=integration["decision"], candidates=len(candidates), rejected=len(rejected))
    return integration


def validation_summary(run_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    queue = load_queue(run_dir)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str = "", evidence: str = "") -> None:
        checks.append({"name": name, "passed": passed, "detail": detail, "evidence": evidence})

    queue_errors = validate_queue_payload(queue, run_dir)
    add("T0 queue validates", not queue_errors, "; ".join(queue_errors), rel(queue_dir(run_dir) / "queue.json"))
    for item in normalize_queue_tasks(queue):
        tid = task_id(item)
        story = run_dir / "tasks" / tid / "story.json"
        validation = run_dir / "tasks" / tid / "validation.json"
        prompt = run_dir / "tasks" / tid / "worker-prompt.md"
        dispatch = run_dir / "tasks" / tid / "dispatch.json"
        patch = run_dir / "patches" / tid / "patch.json"
        add(f"T0 manifests {tid}", story.exists() and validation.exists(), "", rel(validation))
        add(f"T0 prompt bundle {tid}", prompt.exists() and dispatch.exists(), "", rel(prompt))
        add(f"T0 patch bundle known {tid}", patch.exists(), "", rel(patch))
    preflight_payload = read_json(run_dir / "preflight-summary.json") if (run_dir / "preflight-summary.json").exists() else {}
    add("T1 preflight completed", bool(preflight_payload) and not preflight_payload.get("blocked", True), str(preflight_payload.get("reason") or ""), rel(run_dir / "preflight-summary.json"))
    add("T1 dispatch dry-run completed", (run_dir / "dispatch-plan.json").exists(), "", rel(run_dir / "dispatch-plan.json"))
    add("T1 integration dry-run completed", (run_dir / "integration" / "integration-plan.json").exists(), "", rel(run_dir / "integration" / "integration-plan.json"))
    add("T2 screenshot stub", True, "Console screenshot validation is a separate deterministic command for this package.", rel(run_dir / "evidence" / "validation-summary.json"))
    critical_names = {"T0 queue validates", "T1 preflight completed", "T1 dispatch dry-run completed", "T1 integration dry-run completed"}
    critical_pass = all(item["passed"] for item in checks if item["name"] in critical_names)
    payload = {
        "schema_version": "factory-validation-summary/v1",
        "run_id": queue.get("run_id") or run_dir.name,
        "run_dir": rel(run_dir),
        "decision": "approve" if critical_pass else "blocked",
        "checks": checks,
        "task_status": [
            {
                "task_id": task_id(item),
                "queue_status": item.get("status"),
                "patch_bundle": item.get("patch_bundle"),
                "integration_status": read_json(ROOT / str(item.get("patch_bundle"))).get("integration_status") if item.get("patch_bundle") and (ROOT / str(item.get("patch_bundle"))).exists() else "unknown",
            }
            for item in normalize_queue_tasks(queue)
        ],
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "residual_risk": [
            "Live remote worker dispatch remains gated behind explicit execute mode.",
            "Actual patch application is deferred to factory-integration-v1.",
        ],
        "stats": {
            "total_duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_at": now_iso(),
        },
    }
    write_json(run_dir / "evidence" / "validation-summary.json", payload)
    write_json(run_dir / "validation-summary.json", payload)
    return payload


def release_packet(run_dir: Path) -> dict[str, Any]:
    queue = load_queue(run_dir)
    validation = read_json(run_dir / "evidence" / "validation-summary.json") if (run_dir / "evidence" / "validation-summary.json").exists() else {}
    integration = read_json(run_dir / "integration" / "integration-plan.json") if (run_dir / "integration" / "integration-plan.json").exists() else {}
    lines = [
        "# Factory Dispatch Release Packet",
        "",
        f"- Run: `{queue.get('run_id') or run_dir.name}`",
        f"- Package: `{queue.get('package') or ''}`",
        f"- Queue tasks: `{len(normalize_queue_tasks(queue))}`",
        f"- Validation decision: `{validation.get('decision', 'not_run')}`",
        f"- Integration dry-run: `{integration.get('decision', 'not_run')}`",
        "- AI calls used: `0`",
        "",
        "## Evidence",
        "",
        "- `queue/queue.json`",
        "- `dispatch-plan.json`",
        "- `patch-collection-summary.json`",
        "- `integration/dry-run-summary.md`",
        "- `evidence/validation-summary.json`",
        "",
        "## Deferred",
        "",
        "- Live runtime execution adapter.",
        "- Actual patch application to an integration branch.",
        "- Cross-node build farm validation.",
        "- Strong-model review automation.",
        "",
    ]
    (run_dir / "release-packet.md").write_text("\n".join(lines), encoding="utf-8")
    return {"release_packet": rel(run_dir / "release-packet.md")}


def status(run_dir: Path) -> dict[str, Any]:
    plan = read_json(run_dir / "factory-plan.json") if (run_dir / "factory-plan.json").exists() else {}
    queue = read_json(queue_dir(run_dir) / "queue.json") if (queue_dir(run_dir) / "queue.json").exists() else {}
    validation = read_json(run_dir / "evidence" / "validation-summary.json") if (run_dir / "evidence" / "validation-summary.json").exists() else {}
    preflight_payload = read_json(run_dir / "preflight-summary.json") if (run_dir / "preflight-summary.json").exists() else {}
    integration = read_json(run_dir / "integration" / "integration-plan.json") if (run_dir / "integration" / "integration-plan.json").exists() else {}
    tasks = normalize_queue_tasks(queue) if queue else []
    no_model = [item for item in tasks if item.get("no_model_eligible")]
    return {
        "schema_version": "factory-status/v1",
        "run_id": str(plan.get("run_id") or queue.get("run_id") or run_dir.name),
        "run_dir": rel(run_dir),
        "package": str(plan.get("package") or queue.get("package") or ""),
        "mode": str(queue.get("mode") or plan.get("mode") or ""),
        "base_sha": str(queue.get("base_sha") or git_sha()),
        "tasks": queue_stats(tasks) if tasks else {},
        "ai_calls_used": int(validation.get("ai_calls_used", 0) or 0),
        "estimated_cost_usd": float(validation.get("estimated_cost_usd", 0) or 0),
        "no_model_coverage": round((len(no_model) / len(tasks)) * 100, 2) if tasks else 0,
        "preflight_status": "blocked" if preflight_payload.get("blocked") else "passed" if preflight_payload else "not_run",
        "validation_decision": validation.get("decision", ""),
        "integration_decision": integration.get("decision", ""),
        "artifacts": {
            "queue": (queue_dir(run_dir) / "queue.json").exists(),
            "leases": (queue_dir(run_dir) / "leases.json").exists(),
            "dispatch_plan": (run_dir / "dispatch-plan.json").exists(),
            "patch_collection": (run_dir / "patch-collection-summary.json").exists(),
            "integration": (run_dir / "integration" / "integration-plan.json").exists(),
            "validation_summary": (run_dir / "evidence" / "validation-summary.json").exists(),
            "start_hub": (run_dir / "start-here.html").exists(),
            "release_packet": (run_dir / "release-packet.md").exists(),
        },
    }
