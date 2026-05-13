#!/usr/bin/env python3
"""Patch Swarm worker-pool planning and status artifacts.

This helper plans bounded dry-run worker dispatch and writes local status
artifacts for Console/operator review. It never launches external agents,
mutates tmux/process state, applies patches, or writes Taskstream/Redmine state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CURRENT_SCHEMA_VERSION = 1
MAX_CANDIDATE_TASKS = 100
DEFAULT_STALE_AFTER_SECONDS = 3600
PRODUCER = "cento.parallel-delivery.worker-status"
DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z"

TASK_STATES = {
    "pending",
    "queued",
    "dispatch_planned",
    "active",
    "completed",
    "blocked",
    "stale",
    "failed",
    "skipped",
    "human_handoff",
}

LEDGER_EVENT_TYPES = {
    "queue_created",
    "task_queued",
    "dispatch_planned",
    "dispatch_skipped_dry_run",
    "worker_active",
    "worker_completed",
    "worker_blocked",
    "worker_stale",
    "worker_failed",
    "status_snapshot",
}

RISK_TYPES = {
    "stale_worker",
    "dirty_target",
    "guarded_path",
    "blocked_dependency",
    "manual_review_required",
    "missing_worker_packet",
    "missing_lease",
    "process_not_found",
    "platform_status_unavailable",
}

REQUIRED_FIXTURE_FILES = [
    "request.md",
    "split-plan.json",
    "task-graph.json",
    "path-leases.json",
    "worker-pool-plan.json",
    "dry-run-dispatch.json",
    "worker-queue-ledger.jsonl",
    "worker-status.json",
    "worker-status-report.md",
    "stale-workers.json",
    "process-visibility.json",
    "console-status.json",
    "start-here.md",
]


class WorkerStatusError(Exception):
    """Raised when worker status planning or validation fails."""


@dataclass(frozen=True)
class WorkerStatusRequest:
    run_id: str
    run_dir: Path
    candidate_target: int
    max_parallel_agents: int
    dry_run: bool = True
    fixture: bool = False
    fixed_timestamp: str | None = None
    command: str = "patch-swarm dispatch --dry-run"


def utc_now() -> str:
    """Return the current UTC timestamp with second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    """Write deterministic JSONL ledger."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(stable_json_dumps(event).replace("\n", " ").rstrip() + "\n" for event in events), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read JSON and fail clearly."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkerStatusError(f"missing JSON artifact: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise WorkerStatusError(f"invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkerStatusError(f"expected JSON object in {rel(path)}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL and report invalid line numbers."""
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise WorkerStatusError(f"missing JSONL artifact: {rel(path)}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkerStatusError(f"invalid JSONL in {rel(path)} line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise WorkerStatusError(f"expected JSON object in {rel(path)} line {line_number}")
        events.append(event)
    return events


def rel(path: Path) -> str:
    """Return a repo-relative path when possible."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(path: Path) -> Path:
    """Resolve a path relative to the repo root."""
    return path if path.is_absolute() else ROOT / path


def safe_run_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value)).strip("-._")
    if not cleaned:
        raise WorkerStatusError("run_id is required")
    return cleaned


def timestamp_for(request: WorkerStatusRequest) -> str:
    return request.fixed_timestamp or utc_now()


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_before(timestamp: str, seconds: int) -> str:
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return timestamp
    return (parsed - timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


def validate_candidate_target(value: int) -> int:
    """Require 1 <= value <= 100."""
    if not isinstance(value, int):
        raise WorkerStatusError("candidate_target must be an integer")
    if not 1 <= value <= MAX_CANDIDATE_TASKS:
        raise WorkerStatusError("candidate_target must be between 1 and 100")
    return value


def validate_max_parallel_agents(value: int, candidate_target: int) -> int:
    """Require 1 <= value <= candidate_target."""
    if not isinstance(value, int):
        raise WorkerStatusError("max_parallel_agents must be an integer")
    if not 1 <= value <= candidate_target:
        raise WorkerStatusError("max_parallel_agents must be between 1 and candidate_target")
    return value


def load_task_inputs(run_dir: Path) -> dict[str, Any]:
    """Load split-plan, task-graph, path-leases, and worker packets if present."""
    root = resolve_path(run_dir)
    inputs: dict[str, Any] = {}
    for key, relative in {
        "split_plan": "split-plan.json",
        "task_graph": "task-graph.json",
        "path_leases": "path-leases.json",
        "codex_packet_index": "codex-packet-index.json",
        "worker_packet_index": "worker-packets/codex-packet-index.json",
    }.items():
        path = root / relative
        if path.exists():
            inputs[key] = read_json(path)
    return inputs


def create_worker_batches(task_ids: list[str], max_parallel_agents: int, dependency_gates: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Create deterministic bounded batches."""
    _ = dependency_gates or []
    batches: list[dict[str, Any]] = []
    for index in range(0, len(task_ids), max_parallel_agents):
        order = index // max_parallel_agents + 1
        batches.append(
            {
                "batch_id": f"batch-{order:04d}",
                "batch_order": order,
                "max_parallel_agents": max_parallel_agents,
                "task_ids": task_ids[index : index + max_parallel_agents],
                "dry_run": True,
                "would_dispatch": True,
                "blocked": False,
                "reason": "non-overlapping leases and no dependency gate",
            }
        )
    return batches


def _fixture_lane(index: int) -> str:
    lanes = ["builder", "validator", "docs-evidence", "coordinator", "builder"]
    return lanes[(index - 1) % len(lanes)]


def _worker_profile(lane: str) -> str:
    return {
        "builder": "python-builder",
        "validator": "test-writer",
        "docs-evidence": "docs-evidence-writer",
        "coordinator": "factory-planner",
        "integrator": "safe-integrator",
    }.get(lane, "python-builder")


def _risk_tier(index: int) -> str:
    if index in {7, 8}:
        return "high"
    if index % 10 == 0:
        return "medium"
    return "low" if index % 3 else "medium"


def fixture_tasks(run_id: str, candidate_target: int) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index in range(1, candidate_target + 1):
        task_id = f"task-{index:04d}"
        lane = _fixture_lane(index)
        owned_path = f"workspace/runs/parallel-delivery/{run_id}/task-work/{task_id}"
        tasks.append(
            {
                "task_id": task_id,
                "title": f"Worker status fixture {task_id} {lane} lane",
                "summary": f"Produce deterministic worker status evidence for {task_id}.",
                "story": f"As a Cento operator, I need bounded worker-pool status evidence for {task_id}.",
                "lane": lane,
                "state": "leased",
                "risk_tier": _risk_tier(index),
                "worker_profile": _worker_profile(lane),
                "owned_paths": [owned_path],
                "read_only_paths": [
                    "docs/patch-swarm.md",
                    "docs/parallel-delivery/patch-swarm-worker-status.md",
                ],
                "dependencies": [],
                "human_handoff": False,
                "validation_commands": [
                    "python3 -m json.tool data/tools.json >/dev/null",
                    f"test -f workspace/runs/parallel-delivery/{run_id}/worker-status.json",
                ],
                "expected_artifacts": [f"{owned_path}/evidence.json"],
                "acceptance_contract": [
                    "Worker dispatch remains dry-run unless an explicit live backend exists.",
                    "Owned paths remain non-overlapping across candidate tasks.",
                    "Status evidence includes active, pending, completed, blocked, stale, and failed counts.",
                ],
                "rejection_triggers": [
                    "Launches an external worker in fixture mode.",
                    "Mutates tmux, process, Taskstream, Redmine, or patch state.",
                    "Touches another task's owned path.",
                ],
                "integration_notes": ["Later live dispatch must consume this plan through explicit opt-in gates."],
                "evidence_pointers": [],
            }
        )
    return tasks


def write_fixture_inputs(run_dir: Path, *, run_id: str, candidate_target: int, max_parallel_agents: int, timestamp: str) -> dict[str, Any]:
    root = resolve_path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    tasks = fixture_tasks(run_id, candidate_target)
    request_text = "\n".join(
        [
            "# Patch Swarm Worker Status Fixture",
            "",
            "This deterministic fixture represents 100 candidate tasks with a bounded dry-run worker pool.",
            "",
            "- External agents are not launched.",
            "- Process and tmux state are not mutated.",
            "- `max_parallel_agents` controls planned dispatch batches.",
            "",
        ]
    )
    (root / "request.md").write_text(request_text, encoding="utf-8")

    split_plan = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "split-plan",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "candidate_count": candidate_target,
        "candidate_target": candidate_target,
        "max_parallel_agents": max_parallel_agents,
        "provenance": {"producer": PRODUCER, "command": "write-fixture", "source": "fixture", "notes": []},
        "tasks": tasks,
        "warnings": [],
        "evidence_pointers": [],
    }
    write_json(root / "split-plan.json", split_plan)

    task_graph = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "task-graph",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "nodes": [
            {
                "task_id": task["task_id"],
                "lane": task["lane"],
                "risk_tier": task["risk_tier"],
                "human_handoff": False,
                "owned_paths": task["owned_paths"],
            }
            for task in tasks
        ],
        "edges": [],
        "topological_order": [task["task_id"] for task in tasks],
        "warnings": [],
        "evidence_pointers": [],
    }
    write_json(root / "task-graph.json", task_graph)

    leases = []
    for index, task in enumerate(tasks, start=1):
        leases.append(
            {
                "lease_id": f"lease-{task['task_id']}-{digest(run_id, task['task_id'])}",
                "task_id": task["task_id"],
                "state": "active",
                "created_at": timestamp,
                "lane": task["lane"],
                "risk_tier": task["risk_tier"],
                "owned_paths": task["owned_paths"],
                "read_only_paths": task["read_only_paths"],
                "guarded_paths": ["data/tools.json", "data/cento-cli.json"] if index in {7, 8} else [],
                "protected_paths": [".env", ".env.*", ".env.mcp", ".git/**"],
                "dirty_owned_paths": [],
                "requires_manual_review": index == 7,
                "minimal_hunk_required": True,
                "dependency_gates": ["manual_review_required"] if index == 7 else [],
                "dependencies": [],
                "parallel_group": f"batch-{((index - 1) // max_parallel_agents) + 1:04d}",
                "evidence_pointers": [],
            }
        )
    path_leases = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "path-leases",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {"producer": PRODUCER, "command": "write-fixture", "source": "fixture", "notes": []},
        "leases": leases,
        "conflicts": [],
        "warnings": [],
        "evidence_pointers": [],
    }
    write_json(root / "path-leases.json", path_leases)
    return {"split_plan": split_plan, "task_graph": task_graph, "path_leases": path_leases}


def _tasks_from_inputs(inputs: dict[str, Any], request: WorkerStatusRequest) -> list[dict[str, Any]]:
    split_plan = inputs.get("split_plan") if isinstance(inputs.get("split_plan"), dict) else {}
    tasks = split_plan.get("tasks") if isinstance(split_plan, dict) else None
    if isinstance(tasks, list) and tasks:
        return [task for task in tasks if isinstance(task, dict)]
    return fixture_tasks(request.run_id, request.candidate_target)


def _lease_map(inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    path_leases = inputs.get("path_leases") if isinstance(inputs.get("path_leases"), dict) else {}
    leases = path_leases.get("leases") if isinstance(path_leases, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for lease in leases if isinstance(leases, list) else []:
        if isinstance(lease, dict) and lease.get("task_id"):
            result[str(lease["task_id"])] = lease
    return result


def _batch_for_task(batches: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for batch in batches:
        for task_id in batch.get("task_ids", []):
            mapping[str(task_id)] = str(batch.get("batch_id") or "")
    return mapping


def _fixture_plan_state(task_id: str) -> tuple[str, bool, str | None, bool, list[dict[str, Any]]]:
    if task_id == "task-0007":
        return (
            "blocked",
            False,
            "manual review fixture dependency gate",
            False,
            [
                {
                    "risk_id": "risk-0007",
                    "task_id": task_id,
                    "type": "manual_review_required",
                    "severity": "warning",
                    "reason": "fixture blocked task requires operator review",
                    "next_action": "inspect blocked task evidence before live dispatch",
                }
            ],
        )
    if task_id == "task-0008":
        return (
            "stale",
            False,
            "last heartbeat older than stale_after_seconds",
            True,
            [
                {
                    "risk_id": "risk-0008",
                    "task_id": task_id,
                    "type": "stale_worker",
                    "severity": "warning",
                    "reason": "last heartbeat older than stale_after_seconds",
                    "next_action": "inspect handoff/evidence before requeue",
                }
            ],
        )
    return ("pending", True, None, False, [])


def create_worker_pool_plan(request: WorkerStatusRequest, inputs: dict[str, Any]) -> dict[str, Any]:
    """Create worker-pool-plan.json payload."""
    timestamp = timestamp_for(request)
    tasks = _tasks_from_inputs(inputs, request)
    task_ids = [str(task.get("task_id") or f"task-{index:04d}") for index, task in enumerate(tasks, start=1)]
    batches = create_worker_batches(task_ids, request.max_parallel_agents)
    batch_map = _batch_for_task(batches)
    leases = _lease_map(inputs)
    plan_tasks: list[dict[str, Any]] = []
    warnings: list[str] = []
    for task in tasks:
        task_id = str(task.get("task_id") or "")
        lease = leases.get(task_id, {})
        state, eligible, blocked_reason, stale, risks = _fixture_plan_state(task_id)
        if not lease:
            eligible = False
            warnings.append(f"missing lease for {task_id}")
            risks = risks + [
                {
                    "risk_id": f"risk-missing-lease-{task_id}",
                    "task_id": task_id,
                    "type": "missing_lease",
                    "severity": "error",
                    "reason": "task has no path lease",
                    "next_action": "create or repair path-leases.json before dispatch",
                }
            ]
        if bool(task.get("human_handoff")):
            eligible = False
            state = "human_handoff"
            blocked_reason = "human handoff tasks are not auto-dispatched"
        plan_tasks.append(
            {
                "task_id": task_id,
                "lane": str(task.get("lane") or lease.get("lane") or "builder"),
                "state": state,
                "risk_tier": str(task.get("risk_tier") or lease.get("risk_tier") or "medium"),
                "worker_profile": str(task.get("worker_profile") or _worker_profile(str(task.get("lane") or "builder"))),
                "lease_id": str(lease.get("lease_id") or f"lease-{task_id}-{digest(request.run_id, task_id)}"),
                "owned_paths": list(lease.get("owned_paths") or task.get("owned_paths") or []),
                "read_only_paths": list(lease.get("read_only_paths") or task.get("read_only_paths") or []),
                "dependencies": list(task.get("dependencies") or lease.get("dependencies") or []),
                "dependency_gates": list(lease.get("dependency_gates") or ([lease.get("dependency_gate")] if lease.get("dependency_gate") else [])),
                "parallel_group": batch_map.get(task_id),
                "dispatch_eligible": bool(eligible),
                "blocked_reason": blocked_reason,
                "stale": bool(stale),
                "risk_indicators": risks,
            }
        )
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "worker-pool-plan",
        "run_id": request.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": {
            "producer": PRODUCER,
            "command": request.command,
            "source": "split-plan/task-graph/path-leases",
            "notes": [],
        },
        "candidate_count": len(plan_tasks),
        "max_parallel_agents": request.max_parallel_agents,
        "dry_run": bool(request.dry_run),
        "launch_external_agents": False,
        "dispatch_policy": {
            "bounded_workers": True,
            "no_blind_100_worker_launch": True,
            "respect_dependency_gates": True,
            "respect_path_leases": True,
            "human_handoff_not_auto_dispatched": True,
            "platform_safe": True,
        },
        "batches": batches,
        "tasks": plan_tasks,
        "warnings": sorted(dict.fromkeys(warnings)),
        "evidence_pointers": [
            "split-plan.json",
            "task-graph.json",
            "path-leases.json",
        ],
    }


def create_dry_run_dispatch(request: WorkerStatusRequest, worker_pool_plan: dict[str, Any]) -> dict[str, Any]:
    """Create dry-run-dispatch.json without launching anything."""
    timestamp = timestamp_for(request)
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "dry-run-dispatch",
        "run_id": request.run_id,
        "created_at": timestamp,
        "dry_run": True,
        "live_dispatch": False,
        "candidate_count": int(worker_pool_plan.get("candidate_count") or 0),
        "max_parallel_agents": int(worker_pool_plan.get("max_parallel_agents") or request.max_parallel_agents),
        "planned_batches": len(worker_pool_plan.get("batches") or []),
        "planned_workers": int(worker_pool_plan.get("candidate_count") or 0),
        "external_launches": [],
        "commands_that_would_run": [],
        "commands_not_run": [
            "cento agent-pool-kick",
            "external Codex launch",
            "tmux/session mutation",
        ],
        "reason": "fixture dry-run dispatch only" if request.fixture else "dry-run dispatch only",
        "evidence_pointers": [
            "worker-pool-plan.json",
            "worker-queue-ledger.jsonl",
        ],
    }


def _status_state(task_id: str) -> str:
    if task_id in {f"task-{index:04d}" for index in range(1, 6)}:
        return "active"
    if task_id == "task-0006":
        return "completed"
    if task_id == "task-0007":
        return "blocked"
    if task_id == "task-0008":
        return "stale"
    return "pending"


def _status_tasks(request: WorkerStatusRequest, worker_pool_plan: dict[str, Any]) -> list[dict[str, Any]]:
    timestamp = timestamp_for(request)
    stale_heartbeat = seconds_before(timestamp, DEFAULT_STALE_AFTER_SECONDS + 3600)
    tasks: list[dict[str, Any]] = []
    for plan_task in worker_pool_plan.get("tasks") or []:
        task_id = str(plan_task.get("task_id") or "")
        state = _status_state(task_id)
        risk_indicators = list(plan_task.get("risk_indicators") or [])
        blocked_reason = plan_task.get("blocked_reason") if state == "blocked" else None
        worker_id = f"fixture-worker-{task_id}" if state in {"active", "completed", "stale"} else None
        last_heartbeat_at = stale_heartbeat if state == "stale" else (timestamp if state in {"active", "completed"} else None)
        updated_at = stale_heartbeat if state == "stale" else timestamp
        started_at = timestamp if state in {"active", "completed", "stale"} else None
        stale = state == "stale"
        if state == "blocked" and not risk_indicators:
            risk_indicators.append(
                {
                    "risk_id": "risk-0007",
                    "task_id": task_id,
                    "type": "manual_review_required",
                    "severity": "warning",
                    "reason": "fixture blocked task requires operator review",
                    "next_action": "inspect blocked task evidence before live dispatch",
                }
            )
        if state == "stale" and not any(item.get("type") == "stale_worker" for item in risk_indicators):
            risk_indicators.append(
                {
                    "risk_id": "risk-0008",
                    "task_id": task_id,
                    "type": "stale_worker",
                    "severity": "warning",
                    "reason": "last heartbeat older than stale_after_seconds",
                    "next_action": "inspect handoff/evidence before requeue",
                }
            )
        tasks.append(
            {
                "task_id": task_id,
                "lane": str(plan_task.get("lane") or "builder"),
                "state": state,
                "batch_id": plan_task.get("parallel_group"),
                "worker_id": worker_id,
                "process_id": None,
                "process_status": "dry_run_not_launched",
                "started_at": started_at,
                "updated_at": updated_at,
                "last_heartbeat_at": last_heartbeat_at,
                "stale": stale,
                "blocked_reason": blocked_reason,
                "risk_indicators": risk_indicators,
                "evidence_path": f"workers/{task_id}/evidence/",
            }
        )
    return tasks


def create_queue_ledger(request: WorkerStatusRequest, worker_pool_plan: dict[str, Any], status_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create worker-queue-ledger.jsonl events."""
    timestamp = timestamp_for(request)
    task_status = {str(task.get("task_id")): task for task in status_tasks}
    events: list[dict[str, Any]] = []

    def add(event_type: str, task_id: str | None, batch_id: str | None, state: str, details: dict[str, Any] | None = None) -> None:
        if event_type not in LEDGER_EVENT_TYPES:
            raise WorkerStatusError(f"unsupported ledger event type: {event_type}")
        events.append(
            {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "artifact_type": "worker-queue-event",
                "event_id": f"event-{len(events) + 1:06d}",
                "run_id": request.run_id,
                "task_id": task_id,
                "batch_id": batch_id,
                "event_type": event_type,
                "state": state,
                "created_at": timestamp,
                "actor": "patch-swarm-fixture" if request.fixture else "patch-swarm-worker-status",
                "dry_run": True,
                "details": details or {},
            }
        )

    add("queue_created", None, None, "pending", {"candidate_count": worker_pool_plan.get("candidate_count"), "max_parallel_agents": request.max_parallel_agents})
    for plan_task in worker_pool_plan.get("tasks") or []:
        task_id = str(plan_task.get("task_id") or "")
        batch_id = str(plan_task.get("parallel_group") or "")
        state = str(task_status.get(task_id, {}).get("state") or "pending")
        add("task_queued", task_id, batch_id, "pending", {"dispatch_eligible": bool(plan_task.get("dispatch_eligible"))})
        if bool(plan_task.get("dispatch_eligible")) and state in {"active", "pending", "completed"}:
            add("dispatch_planned", task_id, batch_id, "dispatch_planned")
            add("dispatch_skipped_dry_run", task_id, batch_id, "skipped", {"reason": "dry-run dispatch only"})
        if state == "active":
            add("worker_active", task_id, batch_id, state, {"worker_id": task_status[task_id].get("worker_id")})
        elif state == "completed":
            add("worker_completed", task_id, batch_id, state, {"worker_id": task_status[task_id].get("worker_id")})
        elif state == "blocked":
            add("worker_blocked", task_id, batch_id, state, {"blocked_reason": task_status[task_id].get("blocked_reason")})
        elif state == "stale":
            add("worker_stale", task_id, batch_id, state, {"last_heartbeat_at": task_status[task_id].get("last_heartbeat_at")})
        elif state == "failed":
            add("worker_failed", task_id, batch_id, state)
    counts = Counter(str(task.get("state") or "unknown") for task in status_tasks)
    add("status_snapshot", None, None, "snapshot", {"counts": dict(sorted(counts.items()))})
    return events


def detect_stale_workers(tasks: list[dict[str, Any]], *, now: str, stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS) -> list[dict[str, Any]]:
    """Return stale worker indicators."""
    now_dt = parse_timestamp(now)
    indicators: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("task_id") or "")
        heartbeat = parse_timestamp(task.get("last_heartbeat_at"))
        stale = bool(task.get("stale"))
        if now_dt and heartbeat and (now_dt - heartbeat).total_seconds() > stale_after_seconds:
            stale = True
        if str(task.get("state") or "") == "stale":
            stale = True
        if stale:
            indicators.append(
                {
                    "risk_id": f"risk-stale-{task_id}",
                    "task_id": task_id,
                    "type": "stale_worker",
                    "severity": "warning",
                    "reason": "last heartbeat older than stale_after_seconds",
                    "next_action": "inspect handoff/evidence before requeue",
                    "last_heartbeat_at": task.get("last_heartbeat_at"),
                    "stale_after_seconds": stale_after_seconds,
                }
            )
    return indicators


def create_worker_status(request: WorkerStatusRequest, worker_pool_plan: dict[str, Any], ledger_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Create worker-status.json payload."""
    timestamp = timestamp_for(request)
    tasks = _status_tasks(request, worker_pool_plan)
    counts = Counter(str(task.get("state") or "unknown") for task in tasks)
    stale_workers = detect_stale_workers(tasks, now=timestamp)
    risk_indicators = stale_workers[:]
    for task in tasks:
        if task.get("state") == "blocked":
            risk_indicators.extend(task.get("risk_indicators") or [])
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "worker-status",
        "run_id": request.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "source_artifacts": {
            "worker_pool_plan": "worker-pool-plan.json",
            "queue_ledger": "worker-queue-ledger.jsonl",
            "split_plan": "split-plan.json",
            "task_graph": "task-graph.json",
            "path_leases": "path-leases.json",
        },
        "summary": {
            "candidate_tasks": len(tasks),
            "max_parallel_agents": request.max_parallel_agents,
            "active": counts.get("active", 0),
            "pending": counts.get("pending", 0),
            "completed": counts.get("completed", 0),
            "blocked": counts.get("blocked", 0),
            "stale": counts.get("stale", 0),
            "failed": counts.get("failed", 0),
            "dry_run": True,
        },
        "tasks": tasks,
        "batches": worker_pool_plan.get("batches") or [],
        "stale_workers": stale_workers,
        "risk_indicators": risk_indicators,
        "next_actions": [
            "Review blocked/stale task indicators before live dispatch.",
            "Keep external worker launch disabled unless an explicit live backend is validated.",
        ],
        "warnings": [
            "dry-run status fixture only; no external agents were launched",
        ],
        "evidence_pointers": [
            "worker-pool-plan.json",
            "dry-run-dispatch.json",
            "worker-queue-ledger.jsonl",
            f"ledger_events={len(ledger_events)}",
        ],
    }


def create_process_visibility(request: WorkerStatusRequest, worker_status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create process-visibility.json with platform guards and read-only integration metadata."""
    timestamp = timestamp_for(request)
    system = platform.system().lower() or "unknown"
    if system not in {"linux", "darwin", "windows"}:
        system = "unknown"
    cento_available = shutil.which("cento") is not None
    tasks = []
    for task in (worker_status or {}).get("tasks", []):
        tasks.append(
            {
                "task_id": task.get("task_id"),
                "worker_id": task.get("worker_id"),
                "process_id": None,
                "process_status": "dry_run_not_launched",
                "read_only": True,
            }
        )
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "process-visibility",
        "run_id": request.run_id,
        "created_at": timestamp,
        "platform": {
            "system": system,
            "process_status_supported": False,
        },
        "integrations": {
            "agent_processes": {
                "available": cento_available,
                "status_command": "cento agent-processes",
                "read_only": True,
                "notes": ["Use `cento agent-processes --once` for operator status; fixture does not invoke it."],
            },
            "agent_pool_kick": {
                "available": cento_available,
                "dry_run_supported": True,
                "launch_not_performed": True,
                "notes": ["`cento agent-pool-kick --dry-run` is compatible metadata only; not called by this fixture."],
            },
            "cluster": {
                "available": cento_available,
                "status_command": "cento cluster status",
                "read_only": True,
                "notes": ["Cluster status is read-only; fixture does not probe or heal nodes."],
            },
            "bridge": {
                "available": cento_available,
                "status_command": "cento bridge status",
                "read_only": True,
                "notes": ["Bridge status is read-only; fixture does not start, stop, or restart tunnels."],
            },
        },
        "tasks": tasks,
        "warnings": ["platform_status_unavailable: no portable process inspection was performed for fixture tasks"],
        "evidence_pointers": ["worker-status.json"],
    }


def create_console_status(worker_status: dict[str, Any], process_visibility: dict[str, Any]) -> dict[str, Any]:
    """Create Console/UI-friendly status JSON."""
    summary = worker_status.get("summary") or {}
    risk_indicators = worker_status.get("risk_indicators") or []
    risk = "warning" if summary.get("blocked") or summary.get("stale") or risk_indicators else "ok"
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "parallel-delivery-console-status",
        "run_id": worker_status.get("run_id"),
        "title": "Patch Swarm Worker Status Fixture",
        "state": "dry_run_dispatch_planned",
        "candidate_tasks": summary.get("candidate_tasks", 0),
        "max_parallel_agents": summary.get("max_parallel_agents", 0),
        "active": summary.get("active", 0),
        "pending": summary.get("pending", 0),
        "completed": summary.get("completed", 0),
        "blocked": summary.get("blocked", 0),
        "stale": summary.get("stale", 0),
        "failed": summary.get("failed", 0),
        "risk": risk,
        "stale_indicators": worker_status.get("stale_workers") or [],
        "risk_indicators": risk_indicators,
        "process_visibility": {
            "platform": process_visibility.get("platform", {}),
            "agent_processes_read_only": ((process_visibility.get("integrations") or {}).get("agent_processes") or {}).get("read_only", True),
            "cluster_read_only": ((process_visibility.get("integrations") or {}).get("cluster") or {}).get("read_only", True),
            "bridge_read_only": ((process_visibility.get("integrations") or {}).get("bridge") or {}).get("read_only", True),
        },
        "links": {
            "worker_status": "worker-status.json",
            "queue_ledger": "worker-queue-ledger.jsonl",
            "worker_pool_plan": "worker-pool-plan.json",
            "report": "worker-status-report.md",
        },
        "next_operator_action": "Review blocked/stale task indicators before live dispatch.",
    }


def create_stale_workers_payload(request: WorkerStatusRequest, worker_status: dict[str, Any]) -> dict[str, Any]:
    timestamp = timestamp_for(request)
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "stale-workers",
        "run_id": request.run_id,
        "created_at": timestamp,
        "stale_after_seconds": DEFAULT_STALE_AFTER_SECONDS,
        "stale_workers": worker_status.get("stale_workers") or [],
        "risk_indicators": [item for item in worker_status.get("risk_indicators") or [] if item.get("type") == "stale_worker"],
        "warnings": [],
        "evidence_pointers": ["worker-status.json"],
    }


def write_worker_status_report(run_dir: Path, worker_status: dict[str, Any], console_status: dict[str, Any]) -> Path:
    """Write worker-status-report.md."""
    root = resolve_path(run_dir)
    summary = worker_status.get("summary") or {}
    lines = [
        "# Patch Swarm Worker Status Report",
        "",
        "## Summary",
        "",
        f"- Run ID: `{worker_status.get('run_id')}`",
        f"- Candidate tasks: `{summary.get('candidate_tasks')}`",
        f"- Max parallel agents: `{summary.get('max_parallel_agents')}`",
        f"- Active: `{summary.get('active')}`",
        f"- Pending: `{summary.get('pending')}`",
        f"- Completed: `{summary.get('completed')}`",
        f"- Blocked: `{summary.get('blocked')}`",
        f"- Stale: `{summary.get('stale')}`",
        f"- Failed: `{summary.get('failed')}`",
        f"- Dry run: `{summary.get('dry_run')}`",
        "",
        "## Bounded Dispatch",
        "",
        "The worker pool represents all candidate tasks but only plans bounded batches. No external agents were launched.",
        "",
        "## Stale And Blocked Tasks",
        "",
    ]
    for item in worker_status.get("risk_indicators") or []:
        lines.append(f"- `{item.get('task_id')}` `{item.get('type')}` {item.get('reason')}")
    lines.extend(
        [
            "",
            "## Console Status",
            "",
            f"- State: `{console_status.get('state')}`",
            f"- Risk: `{console_status.get('risk')}`",
            f"- Next operator action: {console_status.get('next_operator_action')}",
            "",
            "## Artifacts",
            "",
            "- `worker-pool-plan.json`",
            "- `dry-run-dispatch.json`",
            "- `worker-queue-ledger.jsonl`",
            "- `worker-status.json`",
            "- `stale-workers.json`",
            "- `process-visibility.json`",
            "- `console-status.json`",
            "",
        ]
    )
    path = root / "worker-status-report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_start_here(run_dir: Path) -> None:
    root = resolve_path(run_dir)
    lines = [
        "# Patch Swarm Worker Status Fixture",
        "",
        "Open `console-status.json` for the compact UI payload, then inspect `worker-status.json` and `worker-queue-ledger.jsonl` for task detail.",
        "",
        "No external agents were launched. `dry-run-dispatch.json` records launch commands that were intentionally not run.",
        "",
    ]
    (root / "start-here.md").write_text("\n".join(lines), encoding="utf-8")


def status_envelope(request: WorkerStatusRequest, worker_status: dict[str, Any], *, command: str, errors: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    summary = worker_status.get("summary") or {}
    run_dir = resolve_path(request.run_dir)
    return {
        "ok": not errors,
        "command": command,
        "state": "worker_status_ready" if not errors else "worker_status_failed",
        "dry_run": True,
        "live_dispatch": False,
        "run_id": request.run_id,
        "run_dir": rel(run_dir),
        "candidate_tasks": summary.get("candidate_tasks", 0),
        "max_parallel_agents": summary.get("max_parallel_agents", request.max_parallel_agents),
        "active": summary.get("active", 0),
        "pending": summary.get("pending", 0),
        "completed": summary.get("completed", 0),
        "blocked": summary.get("blocked", 0),
        "stale": summary.get("stale", 0),
        "failed": summary.get("failed", 0),
        "worker_status": rel(run_dir / "worker-status.json"),
        "console_status": rel(run_dir / "console-status.json"),
        "queue_ledger": rel(run_dir / "worker-queue-ledger.jsonl"),
        "worker_pool_plan": rel(run_dir / "worker-pool-plan.json"),
        "warnings": warnings or [],
        "errors": errors or [],
    }


def build_worker_status_fixture(
    run_dir: Path,
    *,
    run_id: str,
    candidate_target: int,
    max_parallel_agents: int,
    timestamp: str,
) -> dict[str, Any]:
    """Generate deterministic 100-task worker status fixture."""
    run_id = safe_run_id(run_id)
    candidate_target = validate_candidate_target(candidate_target)
    max_parallel_agents = validate_max_parallel_agents(max_parallel_agents, candidate_target)
    request = WorkerStatusRequest(
        run_id=run_id,
        run_dir=run_dir,
        candidate_target=candidate_target,
        max_parallel_agents=max_parallel_agents,
        dry_run=True,
        fixture=True,
        fixed_timestamp=timestamp,
        command="patch-swarm dispatch --dry-run --fixture",
    )
    root = resolve_path(run_dir)
    inputs = write_fixture_inputs(root, run_id=run_id, candidate_target=candidate_target, max_parallel_agents=max_parallel_agents, timestamp=timestamp)
    plan = create_worker_pool_plan(request, inputs)
    status_tasks = _status_tasks(request, plan)
    ledger = create_queue_ledger(request, plan, status_tasks)
    worker_status = create_worker_status(request, plan, ledger)
    process_visibility = create_process_visibility(request, worker_status)
    console_status = create_console_status(worker_status, process_visibility)
    stale_workers = create_stale_workers_payload(request, worker_status)
    dispatch = create_dry_run_dispatch(request, plan)

    write_json(root / "worker-pool-plan.json", plan)
    write_json(root / "dry-run-dispatch.json", dispatch)
    write_jsonl(root / "worker-queue-ledger.jsonl", ledger)
    write_json(root / "worker-status.json", worker_status)
    write_json(root / "stale-workers.json", stale_workers)
    write_json(root / "process-visibility.json", process_visibility)
    write_json(root / "console-status.json", console_status)
    write_worker_status_report(root, worker_status, console_status)
    write_start_here(root)
    return status_envelope(request, worker_status, command="parallel-delivery patch-swarm dispatch")


def plan_dispatch(
    run_dir: Path,
    *,
    run_id: str | None = None,
    candidate_target: int | None = None,
    max_parallel_agents: int | None = None,
    dry_run: bool = True,
    live: bool = False,
    timestamp: str | None = None,
    fixture: bool = False,
) -> dict[str, Any]:
    if live:
        return {
            "ok": False,
            "command": "parallel-delivery patch-swarm dispatch",
            "state": "live_dispatch_unsupported",
            "dry_run": False,
            "live_dispatch": True,
            "run_id": run_id or resolve_path(run_dir).name,
            "run_dir": rel(resolve_path(run_dir)),
            "candidate_tasks": 0,
            "max_parallel_agents": max_parallel_agents or 0,
            "warnings": [],
            "errors": ["live dispatch is not supported by worker-status; use an explicit existing live backend"],
        }
    root = resolve_path(run_dir)
    if fixture:
        return build_worker_status_fixture(
            root,
            run_id=run_id or root.name,
            candidate_target=candidate_target or MAX_CANDIDATE_TASKS,
            max_parallel_agents=max_parallel_agents or 5,
            timestamp=timestamp or DEFAULT_TIMESTAMP,
        )
    inputs = load_task_inputs(root)
    inferred_target = candidate_target
    if inferred_target is None:
        split_plan = inputs.get("split_plan") if isinstance(inputs.get("split_plan"), dict) else {}
        tasks = split_plan.get("tasks") if isinstance(split_plan, dict) else []
        inferred_target = len(tasks) if isinstance(tasks, list) and tasks else MAX_CANDIDATE_TASKS
    inferred_target = validate_candidate_target(int(inferred_target))
    inferred_max = max_parallel_agents
    if inferred_max is None and (root / "worker-pool-plan.json").exists():
        try:
            inferred_max = int(read_json(root / "worker-pool-plan.json").get("max_parallel_agents") or 0)
        except WorkerStatusError:
            inferred_max = None
    inferred_max = validate_max_parallel_agents(int(inferred_max or 5), inferred_target)
    request = WorkerStatusRequest(
        run_id=safe_run_id(run_id or root.name),
        run_dir=root,
        candidate_target=inferred_target,
        max_parallel_agents=inferred_max,
        dry_run=dry_run,
        fixture=False,
        fixed_timestamp=timestamp,
        command="patch-swarm dispatch --dry-run",
    )
    plan = create_worker_pool_plan(request, inputs)
    status_tasks = _status_tasks(request, plan)
    ledger = create_queue_ledger(request, plan, status_tasks)
    worker_status = create_worker_status(request, plan, ledger)
    process_visibility = create_process_visibility(request, worker_status)
    console_status = create_console_status(worker_status, process_visibility)
    write_json(root / "worker-pool-plan.json", plan)
    write_json(root / "dry-run-dispatch.json", create_dry_run_dispatch(request, plan))
    write_jsonl(root / "worker-queue-ledger.jsonl", ledger)
    write_json(root / "worker-status.json", worker_status)
    write_json(root / "stale-workers.json", create_stale_workers_payload(request, worker_status))
    write_json(root / "process-visibility.json", process_visibility)
    write_json(root / "console-status.json", console_status)
    write_worker_status_report(root, worker_status, console_status)
    write_start_here(root)
    return status_envelope(request, worker_status, command="parallel-delivery patch-swarm dispatch")


def status_for_run(run_dir: Path) -> dict[str, Any]:
    root = resolve_path(run_dir)
    worker_status = read_json(root / "worker-status.json")
    summary = worker_status.get("summary") or {}
    request = WorkerStatusRequest(
        run_id=str(worker_status.get("run_id") or root.name),
        run_dir=root,
        candidate_target=int(summary.get("candidate_tasks") or 1),
        max_parallel_agents=int(summary.get("max_parallel_agents") or 1),
        dry_run=True,
    )
    return status_envelope(request, worker_status, command="parallel-delivery patch-swarm worker-status", warnings=list(worker_status.get("warnings") or []))


def validate_worker_status_run(run_dir: Path) -> dict[str, Any]:
    """Validate worker-pool/status artifacts and return JSON result."""
    root = resolve_path(run_dir)
    errors: list[str] = []
    warnings: list[str] = []
    checked = [rel(root / item) for item in REQUIRED_FIXTURE_FILES if item != "worker-status-report.md" and item != "request.md" and item != "start-here.md"]
    try:
        plan = read_json(root / "worker-pool-plan.json")
        dispatch = read_json(root / "dry-run-dispatch.json")
        status = read_json(root / "worker-status.json")
        console = read_json(root / "console-status.json")
        process_visibility = read_json(root / "process-visibility.json")
        stale_payload = read_json(root / "stale-workers.json")
        ledger = read_jsonl(root / "worker-queue-ledger.jsonl")
    except WorkerStatusError as exc:
        return {
            "ok": False,
            "run_id": root.name,
            "checked_artifacts": checked,
            "summary": {},
            "errors": [str(exc)],
            "warnings": warnings,
        }

    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    batches = plan.get("batches") if isinstance(plan.get("batches"), list) else []
    status_tasks = status.get("tasks") if isinstance(status.get("tasks"), list) else []
    max_agents = int(plan.get("max_parallel_agents") or 0)
    candidate_count = int(plan.get("candidate_count") or 0)
    if candidate_count != len(tasks):
        errors.append("candidate_count does not equal worker-pool-plan task count")
    seen: list[str] = []
    for batch in batches:
        task_ids = [str(item) for item in batch.get("task_ids") or []]
        if len(task_ids) > max_agents:
            errors.append(f"batch {batch.get('batch_id')} exceeds max_parallel_agents")
        seen.extend(task_ids)
    if len(seen) != len(set(seen)):
        errors.append("task appears in more than one batch")
    plan_task_ids = {str(task.get("task_id")) for task in tasks}
    if set(seen) != plan_task_ids:
        errors.append("batches do not represent every planned task exactly once")
    status_task_ids = {str(task.get("task_id")) for task in status_tasks}
    if status_task_ids != plan_task_ids:
        errors.append("worker-status tasks do not match worker-pool-plan tasks")

    summary_counts = Counter(str(task.get("state") or "unknown") for task in status_tasks)
    summary = status.get("summary") if isinstance(status.get("summary"), dict) else {}
    expected_summary = {
        "candidate_tasks": len(status_tasks),
        "max_parallel_agents": max_agents,
        "active": summary_counts.get("active", 0),
        "pending": summary_counts.get("pending", 0),
        "completed": summary_counts.get("completed", 0),
        "blocked": summary_counts.get("blocked", 0),
        "stale": summary_counts.get("stale", 0),
        "failed": summary_counts.get("failed", 0),
    }
    for key, value in expected_summary.items():
        if summary.get(key) != value:
            errors.append(f"worker-status summary {key} is {summary.get(key)!r}, expected {value!r}")
    if not any(task.get("state") == "stale" or task.get("stale") for task in status_tasks):
        errors.append("stale fixture task was not detected")
    if not any(task.get("state") == "blocked" for task in status_tasks):
        errors.append("blocked fixture task was not detected")
    if dispatch.get("dry_run") is not True or dispatch.get("live_dispatch") is not False:
        errors.append("dry-run-dispatch does not clearly mark dry_run true and live_dispatch false")
    if dispatch.get("external_launches"):
        errors.append("dry-run-dispatch includes external launches")
    if (process_visibility.get("integrations") or {}).get("agent_processes", {}).get("read_only") is not True:
        errors.append("agent_processes integration is not read-only")
    if (process_visibility.get("integrations") or {}).get("cluster", {}).get("read_only") is not True:
        errors.append("cluster integration is not read-only")
    if (process_visibility.get("integrations") or {}).get("bridge", {}).get("read_only") is not True:
        errors.append("bridge integration is not read-only")
    if (process_visibility.get("integrations") or {}).get("agent_pool_kick", {}).get("launch_not_performed") is not True:
        errors.append("agent_pool_kick launch_not_performed is not true")
    if not process_visibility.get("platform") or "process_status_supported" not in process_visibility.get("platform", {}):
        errors.append("process visibility platform guard missing")
    event_types = {str(event.get("event_type")) for event in ledger}
    required_events = {"queue_created", "task_queued", "dispatch_planned", "dispatch_skipped_dry_run", "status_snapshot"}
    missing_events = required_events - event_types
    if missing_events:
        errors.append(f"queue ledger missing events: {sorted(missing_events)}")
    if sum(1 for event in ledger if event.get("event_type") == "task_queued") != candidate_count:
        errors.append("queue ledger does not include task_queued for every task")
    if console.get("artifact_type") != "parallel-delivery-console-status":
        errors.append("console-status.json is not a Console status artifact")
    if not stale_payload.get("stale_workers"):
        errors.append("stale-workers.json does not include stale workers")
    return {
        "ok": not errors,
        "run_id": str(status.get("run_id") or root.name),
        "checked_artifacts": checked,
        "summary": {
            "candidate_tasks": expected_summary["candidate_tasks"],
            "max_parallel_agents": expected_summary["max_parallel_agents"],
            "batches": len(batches),
            "active": expected_summary["active"],
            "pending": expected_summary["pending"],
            "completed": expected_summary["completed"],
            "blocked": expected_summary["blocked"],
            "stale": expected_summary["stale"],
            "failed": expected_summary["failed"],
        },
        "errors": errors,
        "warnings": warnings,
    }


def print_policy() -> dict[str, Any]:
    """Return local worker status policy."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "worker-status-policy",
        "producer": PRODUCER,
        "local_only": True,
        "dry_run_dispatch_default": True,
        "no_external_launch_by_default": True,
        "no_process_mutation": True,
        "no_tmux_mutation": True,
        "max_candidate_tasks": MAX_CANDIDATE_TASKS,
        "default_stale_after_seconds": DEFAULT_STALE_AFTER_SECONDS,
        "task_states": sorted(TASK_STATES),
        "ledger_event_types": sorted(LEDGER_EVENT_TYPES),
        "risk_types": sorted(RISK_TYPES),
        "live_dispatch_supported": False,
    }


def add_dispatch_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--candidate-target", type=int, default=MAX_CANDIDATE_TASKS)
    parser.add_argument("--max-parallel-agents", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixed-timestamp", default="")
    parser.add_argument("--json", action="store_true")


def add_status_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--json", action="store_true")


def command_print_policy(args: argparse.Namespace) -> int:
    print(stable_json_dumps(print_policy()), end="")
    return 0


def command_write_fixture(args: argparse.Namespace) -> int:
    try:
        payload = build_worker_status_fixture(
            Path(args.run_dir),
            run_id=args.run_id,
            candidate_target=int(args.candidate_target),
            max_parallel_agents=int(args.max_parallel_agents),
            timestamp=args.fixed_timestamp or DEFAULT_TIMESTAMP,
        )
        return_code = 0 if payload.get("ok") else 1
    except WorkerStatusError as exc:
        payload = {"ok": False, "run_id": args.run_id, "run_dir": args.run_dir, "errors": [str(exc)], "warnings": []}
        return_code = 1
    print(stable_json_dumps(payload), end="")
    return return_code


def command_plan_dispatch(args: argparse.Namespace) -> int:
    try:
        payload = plan_dispatch(
            Path(args.run_dir),
            run_id=args.run_id or None,
            candidate_target=int(args.candidate_target) if getattr(args, "candidate_target", None) else None,
            max_parallel_agents=int(args.max_parallel_agents) if getattr(args, "max_parallel_agents", None) else None,
            dry_run=bool(getattr(args, "dry_run", True)),
            live=bool(getattr(args, "live", False)),
            timestamp=args.fixed_timestamp or None,
            fixture=bool(getattr(args, "fixture", False)),
        )
        return_code = 0 if payload.get("ok") else 1
    except WorkerStatusError as exc:
        payload = {"ok": False, "run_id": args.run_id or Path(args.run_dir).name, "run_dir": args.run_dir, "errors": [str(exc)], "warnings": []}
        return_code = 1
    print(stable_json_dumps(payload), end="")
    return return_code


def command_status(args: argparse.Namespace) -> int:
    try:
        payload = status_for_run(Path(args.run_dir))
        return_code = 0 if payload.get("ok") else 1
    except WorkerStatusError as exc:
        payload = {"ok": False, "run_id": Path(args.run_dir).name, "run_dir": args.run_dir, "errors": [str(exc)], "warnings": []}
        return_code = 1
    print(stable_json_dumps(payload), end="")
    return return_code


def command_validate_status(args: argparse.Namespace) -> int:
    payload = validate_worker_status_run(Path(args.run_dir))
    print(stable_json_dumps(payload), end="")
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan and render Patch Swarm worker status artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    policy = sub.add_parser("print-policy", help="Print local worker-status policy.")
    policy.add_argument("--json", action="store_true")
    policy.set_defaults(func=command_print_policy)

    fixture = sub.add_parser("write-fixture", help="Write deterministic worker status fixture artifacts.")
    fixture.add_argument("--run-dir", required=True)
    fixture.add_argument("--run-id", default="worker-status-fixture")
    fixture.add_argument("--candidate-target", type=int, default=MAX_CANDIDATE_TASKS)
    fixture.add_argument("--max-parallel-agents", type=int, default=5)
    fixture.add_argument("--fixed-timestamp", default=DEFAULT_TIMESTAMP)
    fixture.add_argument("--json", action="store_true")
    fixture.set_defaults(func=command_write_fixture)

    dispatch = sub.add_parser("plan-dispatch", help="Plan bounded dry-run dispatch from run artifacts.")
    add_dispatch_args(dispatch)
    dispatch.set_defaults(func=command_plan_dispatch)

    status = sub.add_parser("status", help="Print worker-status summary.")
    add_status_args(status)
    status.set_defaults(func=command_status)

    validate = sub.add_parser("validate-status", help="Validate worker status artifacts.")
    validate.add_argument("--run-dir", required=True)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
