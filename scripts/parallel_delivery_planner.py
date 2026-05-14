#!/usr/bin/env python3
"""Patch Swarm request splitter and bounded task planner.

This module creates durable planner artifacts for Patch Swarm runs. It writes
split-plan and task-graph contracts only; it does not dispatch workers, call
live models by default, apply patches, or mutate Taskstream state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import parallel_delivery_artifacts as artifact_schema
except ImportError:  # pragma: no cover - direct import fallback for unusual cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import parallel_delivery_artifacts as artifact_schema


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"
PRODUCER = "cento.parallel-delivery.planner"
CURRENT_SCHEMA_VERSION = artifact_schema.CURRENT_SCHEMA_VERSION
MAX_CANDIDATE_TASKS = 100

PLANNER_MODES = {"fixture", "no-model", "proreq", "manual-import"}
TASK_LANES = {"builder", "validator", "docs-evidence", "coordinator", "integrator", "human-handoff"}
RISK_TIERS = {"low", "medium", "high", "human"}
WORKER_PROFILES = {
    "python-builder",
    "cli-builder",
    "schema-validator",
    "test-writer",
    "docs-evidence-writer",
    "safe-integrator",
    "factory-planner",
    "workset-lease-planner",
    "human-operator",
}
EDGE_TYPES = set(artifact_schema.EDGE_TYPES)
TASK_STATES = set(artifact_schema.TASK_STATES)

LANE_CYCLE = [
    ("coordinator", "factory-planner", "medium"),
    ("builder", "python-builder", "medium"),
    ("validator", "test-writer", "low"),
    ("docs-evidence", "docs-evidence-writer", "low"),
    ("integrator", "safe-integrator", "high"),
]

SUBJECTIVE_OR_UNSAFE_KEYWORDS = [
    "visual polish",
    "looks good",
    "try on device",
    "production credentials",
    "browser-only",
    "manual approval",
    "deploy to prod",
    "real customer",
    "secret",
    "token",
    ".env",
]


class PlannerValidationError(Exception):
    """Raised when planner input or output is invalid."""


@dataclass(frozen=True)
class PlannerRequest:
    request_text: str
    request_file: str | None
    run_id: str
    run_dir: Path
    mode: str
    candidate_target: int
    max_parallel_agents: int
    live_pro: bool = False
    import_plan: Path | None = None
    dry_run: bool = False
    command: str = "patch-swarm split"
    timestamp: str | None = None


@dataclass(frozen=True)
class PlannerResult:
    run_id: str
    run_dir: Path
    mode: str
    candidate_target: int
    candidate_count: int
    max_parallel_agents: int
    split_plan: dict[str, Any]
    task_graph: dict[str, Any]
    artifacts: list[str]
    warnings: list[str]
    errors: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: dict[str, Any]) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return artifact_schema.stable_json_dumps(payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    artifact_schema.write_json_artifact(path, payload)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _timestamp(value: str | None) -> str:
    return value or utc_now()


def _provenance(command: str, mode: str, source: str) -> dict[str, Any]:
    return {
        "command": command,
        "mode": mode,
        "notes": [],
        "producer": PRODUCER,
        "repo": "cento",
        "source": source,
    }


def _common(artifact_type: str, request: PlannerRequest, timestamp: str, source: str) -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "evidence_pointers": [],
        "provenance": _provenance(request.command, request.mode, source),
        "run_id": request.run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }


def _metadata_comment(artifact_type: str, run_id: str, timestamp: str) -> str:
    metadata = {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "run_id": run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    return f"<!-- cento-artifact: {json.dumps(metadata, sort_keys=True, separators=(',', ':'))} -->"


def read_request_text(request_file: Path | None, fallback: str | None = None) -> str:
    """Read request text safely; fail clearly if required input is missing."""
    if request_file:
        path = request_file if request_file.is_absolute() else ROOT / request_file
        if not path.exists():
            raise PlannerValidationError(f"request file does not exist: {request_file}")
        if any(part == ".env.mcp" for part in path.parts):
            raise PlannerValidationError("request file must not point to .env.mcp")
        return path.read_text(encoding="utf-8")
    if fallback and fallback.strip():
        return fallback
    raise PlannerValidationError("request-file or request text is required for this planner mode")


def validate_candidate_target(candidate_target: int) -> int:
    """Require 1 <= candidate_target <= 100."""
    if not isinstance(candidate_target, int):
        raise PlannerValidationError("candidate_target must be an integer")
    if not 1 <= candidate_target <= MAX_CANDIDATE_TASKS:
        raise PlannerValidationError("candidate_target must be between 1 and 100")
    return candidate_target


def validate_max_parallel_agents(max_parallel_agents: int, candidate_target: int) -> int:
    """Require 1 <= max_parallel_agents <= candidate_target."""
    if not isinstance(max_parallel_agents, int):
        raise PlannerValidationError("max_parallel_agents must be an integer")
    if not 1 <= max_parallel_agents <= candidate_target:
        raise PlannerValidationError("max_parallel_agents must be between 1 and candidate_target")
    return max_parallel_agents


def normalize_mode(args: argparse.Namespace) -> str:
    """Resolve --mode plus shorthand flags into fixture/no-model/proreq/manual-import."""
    shorthand = [
        ("fixture", bool(getattr(args, "fixture", False))),
        ("no-model", bool(getattr(args, "no_model", False))),
        ("proreq", bool(getattr(args, "proreq", False))),
        ("manual-import", bool(getattr(args, "manual_import", False))),
    ]
    selected = [mode for mode, enabled in shorthand if enabled]
    if len(selected) > 1:
        raise PlannerValidationError(f"planner mode shorthands conflict: {', '.join(selected)}")
    explicit = getattr(args, "mode", "") or ""
    if selected and explicit and explicit != selected[0]:
        raise PlannerValidationError(f"--mode {explicit} conflicts with --{selected[0]}")
    mode = selected[0] if selected else explicit or "fixture"
    if mode not in PLANNER_MODES:
        raise PlannerValidationError(f"planner mode must be one of {', '.join(sorted(PLANNER_MODES))}")
    return mode


def normalize_relative_path(path: str) -> str:
    """Normalize a path and reject absolute paths, '..', .env.mcp, and secret-like paths."""
    value = str(path).replace("\\", "/").strip()
    value = re.sub(r"/+", "/", value).rstrip("/")
    errors = artifact_schema.validate_relative_artifact_path(value)
    if errors:
        raise PlannerValidationError("; ".join(errors))
    return value


def _path_errors(path: str) -> list[str]:
    try:
        normalize_relative_path(path)
        return []
    except PlannerValidationError as exc:
        return [str(exc)]


def _normalize_path_list(paths: Any, field: str) -> list[str]:
    if paths is None:
        return []
    if not isinstance(paths, list):
        raise PlannerValidationError(f"{field} must be a list")
    normalized = []
    for item in paths:
        if not isinstance(item, str):
            raise PlannerValidationError(f"{field} entries must be strings")
        normalized.append(normalize_relative_path(item))
    return sorted(dict.fromkeys(normalized))


def validate_non_overlapping_owned_paths(tasks: list[dict[str, Any]]) -> list[str]:
    """Return errors for duplicate or overlapping owned paths."""
    errors: list[str] = []
    owned: list[tuple[str, str]] = []
    for task in tasks:
        task_id = str(task.get("task_id", "unknown"))
        for path in task.get("owned_paths", []):
            owned.append((task_id, str(path).rstrip("/")))
    for index, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index + 1 :]:
            if path_a == path_b:
                errors.append(f"owned path overlap: {task_a} and {task_b} both own {path_a}")
            elif path_a.startswith(path_b + "/") or path_b.startswith(path_a + "/"):
                errors.append(f"owned path prefix overlap: {task_a}:{path_a} and {task_b}:{path_b}")
    return errors


def validate_planned_task(task: dict[str, Any]) -> list[str]:
    """Validate required task fields, lane, risk tier, acceptance contract, validation commands."""
    errors: list[str] = []
    required = [
        "task_id",
        "title",
        "story",
        "summary",
        "lane",
        "state",
        "risk_tier",
        "human_handoff",
        "worker_profile",
        "owned_paths",
        "read_only_paths",
        "dependencies",
        "acceptance_contract",
        "validation_commands",
        "expected_artifacts",
        "integration_notes",
        "rejection_triggers",
        "evidence_pointers",
    ]
    for field in required:
        if field not in task:
            errors.append(f"{task.get('task_id', 'task')}: missing {field}")
    if task.get("lane") not in TASK_LANES:
        errors.append(f"{task.get('task_id', 'task')}: lane must be known")
    if task.get("risk_tier") not in RISK_TIERS:
        errors.append(f"{task.get('task_id', 'task')}: risk_tier must be known")
    if task.get("worker_profile") not in WORKER_PROFILES:
        errors.append(f"{task.get('task_id', 'task')}: worker_profile must be known")
    if task.get("state") not in TASK_STATES:
        errors.append(f"{task.get('task_id', 'task')}: state must be known")
    if not isinstance(task.get("human_handoff"), bool):
        errors.append(f"{task.get('task_id', 'task')}: human_handoff must be boolean")
    for field in [
        "owned_paths",
        "read_only_paths",
        "dependencies",
        "acceptance_contract",
        "validation_commands",
        "expected_artifacts",
        "integration_notes",
        "rejection_triggers",
        "evidence_pointers",
    ]:
        if field in task and not isinstance(task[field], list):
            errors.append(f"{task.get('task_id', 'task')}: {field} must be a list")
    for field in ["owned_paths", "read_only_paths"]:
        if isinstance(task.get(field), list):
            for path in task[field]:
                errors.extend(f"{task.get('task_id', 'task')}.{field}: {error}" for error in _path_errors(str(path)))
    if not task.get("human_handoff"):
        if not task.get("acceptance_contract"):
            errors.append(f"{task.get('task_id', 'task')}: non-human tasks require acceptance_contract")
        if not task.get("validation_commands"):
            errors.append(f"{task.get('task_id', 'task')}: non-human tasks require validation_commands")
    if task.get("human_handoff") and task.get("worker_profile") != "human-operator":
        errors.append(f"{task.get('task_id', 'task')}: human handoff tasks must use human-operator")
    return errors


def validate_split_plan(plan: dict[str, Any]) -> list[str]:
    """Validate split-plan schema and planner-specific rules."""
    errors = artifact_schema.validate_split_plan(plan)
    if plan.get("artifact_type") != "split-plan":
        errors.append("split-plan artifact_type must be split-plan")
    for field in ["candidate_target", "candidate_count", "max_parallel_agents", "planner_mode", "planning_policy", "lanes"]:
        if field not in plan:
            errors.append(f"split-plan missing {field}")
    if plan.get("planner_mode") not in PLANNER_MODES:
        errors.append("split-plan planner_mode must be known")
    candidate_target = plan.get("candidate_target")
    candidate_count = plan.get("candidate_count")
    max_parallel_agents = plan.get("max_parallel_agents")
    if not isinstance(candidate_target, int) or not 1 <= candidate_target <= MAX_CANDIDATE_TASKS:
        errors.append("split-plan.candidate_target must be between 1 and 100")
    if not isinstance(candidate_count, int) or not 1 <= candidate_count <= MAX_CANDIDATE_TASKS:
        errors.append("split-plan.candidate_count must be between 1 and 100")
    if isinstance(candidate_count, int) and isinstance(candidate_target, int) and candidate_count > candidate_target:
        errors.append("split-plan.candidate_count must not exceed candidate_target")
    if not isinstance(max_parallel_agents, int) or (
        isinstance(candidate_target, int) and not 1 <= max_parallel_agents <= candidate_target
    ):
        errors.append("split-plan.max_parallel_agents must be between 1 and candidate_target")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return errors + ["split-plan.tasks must be a non-empty list"]
    if isinstance(candidate_count, int) and len(tasks) != candidate_count:
        errors.append("split-plan.candidate_count must equal tasks length")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("split-plan.tasks entries must be objects")
            continue
        errors.extend(validate_planned_task(task))
        task_id = str(task.get("task_id", ""))
        if task_id in seen:
            errors.append(f"duplicate task_id {task_id}")
        seen.add(task_id)
    for task in tasks:
        if isinstance(task, dict):
            for dependency in task.get("dependencies", []):
                if dependency not in seen:
                    errors.append(f"{task.get('task_id')}: unknown dependency {dependency}")
    errors.extend(validate_non_overlapping_owned_paths([task for task in tasks if isinstance(task, dict)]))
    return errors


def _depends_on_edges_from_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for task in tasks:
        for dependency in task.get("dependencies", []):
            edges.append(
                {
                    "from": dependency,
                    "reason": f"{task['task_id']} consumes {dependency} output",
                    "to": task["task_id"],
                    "type": "depends_on",
                }
            )
    return edges


def _topological_order(task_ids: list[str], edges: list[dict[str, str]]) -> list[str]:
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    incoming_count: dict[str, int] = {task_id: 0 for task_id in task_ids}
    for edge in edges:
        if edge.get("type") != "depends_on":
            continue
        source = edge["from"]
        target = edge["to"]
        if source not in incoming_count:
            raise PlannerValidationError(f"unknown dependency {source}")
        if target not in incoming_count:
            raise PlannerValidationError(f"unknown dependency target {target}")
        outgoing.setdefault(source, []).append(target)
        incoming_count[target] = incoming_count.get(target, 0) + 1
    ready = deque(sorted(task_id for task_id in task_ids if incoming_count.get(task_id, 0) == 0))
    order: list[str] = []
    while ready:
        task_id = ready.popleft()
        order.append(task_id)
        for target in sorted(outgoing.get(task_id, [])):
            incoming_count[target] -= 1
            if incoming_count[target] == 0:
                ready.append(target)
    if len(order) != len(task_ids):
        raise PlannerValidationError("depends_on graph must be acyclic")
    return order


def _parallel_groups(
    order: list[str],
    tasks_by_id: dict[str, dict[str, Any]],
    max_parallel_agents: int,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: list[str] = []
    for task_id in order:
        task = tasks_by_id[task_id]
        if task.get("human_handoff"):
            if current:
                groups.append({"automated": True, "group_id": f"group-{len(groups) + 1:04d}", "task_ids": current})
                current = []
            groups.append({"automated": False, "group_id": f"group-{len(groups) + 1:04d}", "task_ids": [task_id]})
            continue
        current.append(task_id)
        if len(current) >= max_parallel_agents:
            groups.append({"automated": True, "group_id": f"group-{len(groups) + 1:04d}", "task_ids": current})
            current = []
    if current:
        groups.append({"automated": True, "group_id": f"group-{len(groups) + 1:04d}", "task_ids": current})
    return groups


def build_task_graph(split_plan: dict[str, Any], *, max_parallel_agents: int) -> dict[str, Any]:
    """Build task graph, topological order, and parallel groups."""
    tasks = split_plan["tasks"]
    task_ids = [task["task_id"] for task in tasks]
    depends_edges = _depends_on_edges_from_tasks(tasks)
    context_edges: list[dict[str, str]] = []
    last_builder = ""
    for task in tasks:
        if task["lane"] == "builder":
            last_builder = task["task_id"]
        if task["lane"] == "docs-evidence" and last_builder:
            context_edges.append(
                {
                    "from": last_builder,
                    "reason": f"{task['task_id']} shares context with builder output",
                    "to": task["task_id"],
                    "type": "shares_context",
                }
            )
    order = _topological_order(task_ids, depends_edges)
    tasks_by_id = {task["task_id"]: task for task in tasks}
    graph = {
        "artifact_type": "task-graph",
        "created_at": split_plan["created_at"],
        "edges": depends_edges + context_edges,
        "evidence_pointers": [],
        "max_parallel_agents": max_parallel_agents,
        "nodes": [
            {
                "human_handoff": task["human_handoff"],
                "lane": task["lane"],
                "owned_paths": task["owned_paths"],
                "risk_tier": task["risk_tier"],
                "task_id": task["task_id"],
            }
            for task in tasks
        ],
        "parallel_groups": _parallel_groups(order, tasks_by_id, max_parallel_agents),
        "provenance": split_plan["provenance"],
        "run_id": split_plan["run_id"],
        "schema_version": CURRENT_SCHEMA_VERSION,
        "topological_order": order,
        "updated_at": split_plan["updated_at"],
    }
    return graph


def validate_task_graph(graph: dict[str, Any], split_plan: dict[str, Any]) -> list[str]:
    """Validate nodes, edges, acyclicity, topological order, and parallel group width."""
    errors = artifact_schema.validate_task_graph(graph)
    task_ids = [task["task_id"] for task in split_plan.get("tasks", []) if isinstance(task, dict)]
    task_set = set(task_ids)
    graph_nodes = [node.get("task_id") for node in graph.get("nodes", []) if isinstance(node, dict)]
    if set(graph_nodes) != task_set:
        errors.append("task-graph nodes must match split-plan tasks")
    order = graph.get("topological_order")
    if not isinstance(order, list) or set(order) != task_set or len(order) != len(task_ids):
        errors.append("task-graph topological_order must include every task exactly once")
    else:
        positions = {task_id: index for index, task_id in enumerate(order)}
        for edge in graph.get("edges", []):
            if isinstance(edge, dict) and edge.get("type") == "depends_on":
                if positions.get(edge.get("from"), 0) > positions.get(edge.get("to"), 0):
                    errors.append(f"depends_on order violation: {edge.get('from')} -> {edge.get('to')}")
    max_parallel_agents = graph.get("max_parallel_agents")
    for group in graph.get("parallel_groups", []):
        if not isinstance(group, dict):
            errors.append("parallel_groups entries must be objects")
            continue
        task_group = group.get("task_ids")
        if not isinstance(task_group, list):
            errors.append("parallel_groups.task_ids must be a list")
            continue
        if isinstance(max_parallel_agents, int) and len(task_group) > max_parallel_agents:
            errors.append("parallel group exceeds max_parallel_agents")
        for task_id in task_group:
            if task_id not in task_set:
                errors.append(f"parallel group references unknown task {task_id}")
    return errors


def _request_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or fallback
        if stripped:
            return stripped[:80]
    return fallback


def _task(
    index: int,
    *,
    title: str,
    summary: str,
    lane: str,
    risk_tier: str,
    worker_profile: str,
    owned_paths: list[str],
    read_only_paths: list[str],
    dependencies: list[str] | None = None,
    human_handoff: bool = False,
    validation_commands: list[str] | None = None,
    acceptance_contract: list[str] | None = None,
    expected_artifacts: list[str] | None = None,
    integration_notes: list[str] | None = None,
    rejection_triggers: list[str] | None = None,
) -> dict[str, Any]:
    task_id = f"task-{index:04d}"
    if human_handoff:
        worker_profile = "human-operator"
        risk_tier = "human"
        lane = "human-handoff"
    return {
        "acceptance_contract": acceptance_contract
        or [
            "Required artifacts are written under the task's owned paths.",
            "No unrelated dirty work or secret-like paths are touched.",
            "Validation commands complete or exact failure evidence is recorded.",
        ],
        "dependencies": dependencies or [],
        "evidence_pointers": [],
        "expected_artifacts": expected_artifacts or [f"task-contracts/{task_id}.md"],
        "human_handoff": human_handoff,
        "integration_notes": integration_notes
        or ["Planner output only; later Safe Integrator calls decide apply order."],
        "lane": lane,
        "owned_paths": _normalize_path_list(owned_paths, f"{task_id}.owned_paths"),
        "read_only_paths": _normalize_path_list(read_only_paths, f"{task_id}.read_only_paths"),
        "rejection_triggers": rejection_triggers
        or [
            "Touches an unowned path.",
            "Drops required acceptance or validation evidence.",
            "Introduces live dispatch, patch apply, or secret copying.",
        ],
        "risk_tier": risk_tier,
        "state": "created",
        "story": f"As a Cento operator, I need {summary.rstrip('.').lower()} so Patch Swarm can proceed with bounded evidence.",
        "summary": summary,
        "task_id": task_id,
        "title": title,
        "validation_commands": validation_commands
        or [
            "python3 -m json.tool data/tools.json >/dev/null",
            "cento docs parallel-delivery >/tmp/cento-parallel-delivery-docs-check.txt",
        ],
        "worker_profile": worker_profile,
    }


def create_fixture_tasks(candidate_target: int, run_dir: Path) -> list[dict[str, Any]]:
    """Create deterministic fixture tasks for 5/20/100 and other valid target counts."""
    validate_candidate_target(candidate_target)
    tasks: list[dict[str, Any]] = []
    last_validator = ""
    for index in range(1, candidate_target + 1):
        lane, profile, risk = LANE_CYCLE[(index - 1) % len(LANE_CYCLE)]
        task_id = f"task-{index:04d}"
        dependencies: list[str] = []
        if lane == "integrator" and last_validator:
            dependencies.append(last_validator)
        if lane == "validator":
            last_validator = task_id
        title = f"Planner fixture {task_id} {lane} lane"
        summary = f"Produce deterministic {lane} planner evidence for {task_id}."
        tasks.append(
            _task(
                index,
                title=title,
                summary=summary,
                lane=lane,
                risk_tier=risk,
                worker_profile=profile,
                owned_paths=[f"workspace/runs/parallel-delivery/planner-fixture/task-work/{task_id}/"],
                read_only_paths=["docs/patch-swarm.md", "docs/parallel-delivery/patch-swarm-artifacts.md"],
                dependencies=dependencies,
                expected_artifacts=[f"task-contracts/{task_id}.md", f"task-work/{task_id}/evidence.json"],
                validation_commands=[
                    f"test -f workspace/runs/parallel-delivery/planner-fixture/task-contracts/{task_id}.md",
                    "python3 -m json.tool workspace/runs/parallel-delivery/planner-fixture/split-plan.json >/dev/null",
                ],
            )
        )
    return tasks


def _source_for_mode(mode: str) -> str:
    return {"fixture": "fixture", "manual-import": "manual-import", "no-model": "local", "proreq": "local"}[mode]


def _build_split_plan(request: PlannerRequest, tasks: list[dict[str, Any]], timestamp: str) -> dict[str, Any]:
    title = _request_title(request.request_text, "Patch Swarm planner request")
    split_plan = {
        **_common("split-plan", request, timestamp, _source_for_mode(request.mode)),
        "candidate_count": len(tasks),
        "candidate_target": request.candidate_target,
        "lanes": sorted(TASK_LANES),
        "max_candidate_tasks": request.candidate_target,
        "max_parallel_agents": request.max_parallel_agents,
        "planner_mode": request.mode,
        "planning_policy": {
            "avoid_overlapping_owned_paths": True,
            "coarse_lanes_first": True,
            "do_not_blindly_fill_to_target": request.mode != "fixture",
            "human_handoff_for_subjective_or_device_bound": True,
        },
        "request": {
            "request_file": request.request_file or "request.md",
            "summary": request.request_text.strip()[:240],
            "title": title,
        },
        "tasks": tasks,
        "updated_at": timestamp,
    }
    return split_plan


def _validate_or_raise(split_plan: dict[str, Any], task_graph: dict[str, Any]) -> None:
    errors = validate_split_plan(split_plan)
    errors.extend(validate_task_graph(task_graph, split_plan))
    if errors:
        raise PlannerValidationError("; ".join(errors))


def plan_fixture(request: PlannerRequest) -> PlannerResult:
    """Create deterministic fixture split plan and graph."""
    timestamp = _timestamp(request.timestamp)
    tasks = create_fixture_tasks(request.candidate_target, request.run_dir)
    split_plan = _build_split_plan(request, tasks, timestamp)
    task_graph = build_task_graph(split_plan, max_parallel_agents=request.max_parallel_agents)
    _validate_or_raise(split_plan, task_graph)
    result = PlannerResult(
        artifacts=[],
        candidate_count=len(tasks),
        candidate_target=request.candidate_target,
        errors=[],
        max_parallel_agents=request.max_parallel_agents,
        mode=request.mode,
        run_dir=request.run_dir,
        run_id=request.run_id,
        split_plan=split_plan,
        task_graph=task_graph,
        warnings=[],
    )
    return write_planner_artifacts(result)


def _keyword_hits(text: str) -> set[str]:
    lowered = text.lower()
    hits: set[str] = set()
    keyword_map = {
        "builder": ["code", "implement", "script", "python", "helper", "schema", "planner", "split"],
        "cli": ["cli", "command", "help", "flag", "argument", "cento"],
        "docs-evidence": ["doc", "docs", "readme", "evidence", "report", "summary"],
        "validator": ["test", "validation", "validate", "fixture", "json"],
        "integrator": ["integrate", "integration", "factory", "workset", "apply", "release"],
    }
    for key, values in keyword_map.items():
        if any(value in lowered for value in values):
            hits.add(key)
    if any(value in lowered for value in SUBJECTIVE_OR_UNSAFE_KEYWORDS):
        hits.add("human")
    return hits


def _no_model_tasks(request: PlannerRequest) -> list[dict[str, Any]]:
    text = request.request_text
    hits = _keyword_hits(text)
    small = any(phrase in text.lower() for phrase in ["small request", "one existing cli", "help text", "clarification"])
    task_specs: list[dict[str, Any]] = []
    task_specs.append(
        {
            "lane": "coordinator",
            "owned": ["workspace/runs/parallel-delivery/planner-output/coordinator/"],
            "profile": "factory-planner",
            "risk": "medium",
            "summary": "Normalize the request into a bounded Patch Swarm planning contract.",
            "title": "Normalize planner scope and surfaces",
        }
    )
    if hits & {"builder", "cli"}:
        task_specs.append(
            {
                "lane": "builder",
                "owned": ["scripts/parallel_delivery_planner.py"],
                "profile": "python-builder" if "builder" in hits else "cli-builder",
                "risk": "medium",
                "summary": "Implement the bounded planner or CLI routing slice requested by the operator.",
                "title": "Implement bounded planner surface",
            }
        )
    if "validator" in hits or not small:
        task_specs.append(
            {
                "lane": "validator",
                "owned": ["tests/test_parallel_delivery_planner.py"],
                "profile": "test-writer",
                "risk": "low",
                "summary": "Validate planner counts, paths, graph ordering, and JSON responses.",
                "title": "Add planner validation coverage",
            }
        )
    if "docs-evidence" in hits or small:
        task_specs.append(
            {
                "lane": "docs-evidence",
                "owned": ["docs/parallel-delivery/patch-swarm-planner.md"],
                "profile": "docs-evidence-writer",
                "risk": "low",
                "summary": "Document planner modes, task contract fields, unsafe path rules, and evidence outputs.",
                "title": "Document planner contract",
            }
        )
    if "integrator" in hits and not small:
        task_specs.append(
            {
                "lane": "integrator",
                "owned": ["workspace/runs/parallel-delivery/planner-output/integration/"],
                "profile": "safe-integrator",
                "risk": "high",
                "summary": "Prepare integration sequencing guidance without applying patches.",
                "title": "Plan safe integration sequencing",
            }
        )
    if "human" in hits:
        task_specs.append(
            {
                "human": True,
                "lane": "human-handoff",
                "owned": [],
                "profile": "human-operator",
                "risk": "human",
                "summary": "Record human review for subjective, credential-bound, or device-bound decisions.",
                "title": "Human handoff for unsafe or subjective work",
            }
        )
    if small:
        task_specs = task_specs[: min(len(task_specs), 5)]
    task_specs = task_specs[: request.candidate_target]
    tasks: list[dict[str, Any]] = []
    for index, spec in enumerate(task_specs, start=1):
        human = bool(spec.get("human", False))
        tasks.append(
            _task(
                index,
                title=str(spec["title"]),
                summary=str(spec["summary"]),
                lane=str(spec["lane"]),
                risk_tier=str(spec["risk"]),
                worker_profile=str(spec["profile"]),
                owned_paths=list(spec["owned"]),
                read_only_paths=["data/tools.json", "docs/patch-swarm.md", "scripts/parallel_delivery.py"],
                dependencies=["task-0001"] if index > 1 and spec["lane"] in {"integrator", "docs-evidence"} else [],
                human_handoff=human,
                validation_commands=[] if human else None,
                acceptance_contract=["Human operator decision is recorded with exact rationale."] if human else None,
                expected_artifacts=[f"task-contracts/task-{index:04d}.md"],
            )
        )
    return tasks or create_fixture_tasks(min(request.candidate_target, 3), request.run_dir)


def plan_no_model(request: PlannerRequest, repo_hints: dict[str, Any] | None = None) -> PlannerResult:
    """Rule-based planner using request text and safe repo hints."""
    del repo_hints
    timestamp = _timestamp(request.timestamp)
    tasks = _no_model_tasks(request)
    split_plan = _build_split_plan(request, tasks, timestamp)
    task_graph = build_task_graph(split_plan, max_parallel_agents=request.max_parallel_agents)
    _validate_or_raise(split_plan, task_graph)
    result = PlannerResult(
        artifacts=[],
        candidate_count=len(tasks),
        candidate_target=request.candidate_target,
        errors=[],
        max_parallel_agents=request.max_parallel_agents,
        mode=request.mode,
        run_dir=request.run_dir,
        run_id=request.run_id,
        split_plan=split_plan,
        task_graph=task_graph,
        warnings=[],
    )
    return write_planner_artifacts(result)


def plan_proreq(request: PlannerRequest) -> PlannerResult:
    """Emit ProReq planning prompt/manifest without live Pro call by default."""
    if request.live_pro:
        raise PlannerValidationError("live Pro planning is not wired to a safe backend in this call; omit --live-pro")
    seed_request = PlannerRequest(
        candidate_target=request.candidate_target,
        command=request.command,
        dry_run=request.dry_run,
        import_plan=request.import_plan,
        live_pro=request.live_pro,
        max_parallel_agents=request.max_parallel_agents,
        mode="proreq",
        request_file=request.request_file,
        request_text=request.request_text,
        run_dir=request.run_dir,
        run_id=request.run_id,
        timestamp=request.timestamp,
    )
    timestamp = _timestamp(seed_request.timestamp)
    tasks = _no_model_tasks(seed_request)
    split_plan = _build_split_plan(seed_request, tasks, timestamp)
    task_graph = build_task_graph(split_plan, max_parallel_agents=seed_request.max_parallel_agents)
    _validate_or_raise(split_plan, task_graph)
    result = PlannerResult(
        artifacts=[],
        candidate_count=len(tasks),
        candidate_target=seed_request.candidate_target,
        errors=[],
        max_parallel_agents=seed_request.max_parallel_agents,
        mode=seed_request.mode,
        run_dir=seed_request.run_dir,
        run_id=seed_request.run_id,
        split_plan=split_plan,
        task_graph=task_graph,
        warnings=["live Pro was not called; prompt artifacts were generated for manual Pro planning."],
    )
    return write_planner_artifacts(result)


def _normalize_imported_task(raw: dict[str, Any], index: int) -> dict[str, Any]:
    lane = raw.get("lane", "builder")
    human = bool(raw.get("human_handoff", False) or lane == "human-handoff")
    profile = raw.get("worker_profile") or ("human-operator" if human else "python-builder")
    risk = raw.get("risk_tier") or ("human" if human else "medium")
    return _task(
        index,
        title=str(raw.get("title") or f"Imported task {index:04d}"),
        summary=str(raw.get("summary") or raw.get("story") or f"Normalize imported task {index:04d}."),
        lane=str(lane),
        risk_tier=str(risk),
        worker_profile=str(profile),
        owned_paths=_normalize_path_list(raw.get("owned_paths", []), "owned_paths"),
        read_only_paths=_normalize_path_list(raw.get("read_only_paths", []), "read_only_paths"),
        dependencies=[str(item) for item in raw.get("dependencies", [])],
        human_handoff=human,
        validation_commands=[str(item) for item in raw.get("validation_commands", [])],
        acceptance_contract=[str(item) for item in raw.get("acceptance_contract", [])],
        expected_artifacts=[str(item) for item in raw.get("expected_artifacts", [f"task-contracts/task-{index:04d}.md"])],
        integration_notes=[str(item) for item in raw.get("integration_notes", [])],
        rejection_triggers=[str(item) for item in raw.get("rejection_triggers", [])],
    )


def plan_manual_import(request: PlannerRequest) -> PlannerResult:
    """Validate and normalize an imported Pro-generated split plan."""
    if not request.import_plan:
        raise PlannerValidationError("--import-plan is required for manual-import mode")
    import_path = request.import_plan if request.import_plan.is_absolute() else ROOT / request.import_plan
    try:
        imported = json.loads(import_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlannerValidationError(f"import plan not found: {request.import_plan}") from exc
    except json.JSONDecodeError as exc:
        raise PlannerValidationError(f"import plan invalid JSON: {exc.msg}") from exc
    if not isinstance(imported, dict):
        raise PlannerValidationError("import plan must be a JSON object")
    raw_tasks = imported.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise PlannerValidationError("import plan tasks must be a non-empty list")
    if len(raw_tasks) > MAX_CANDIDATE_TASKS:
        raise PlannerValidationError("import plan candidate_count must not exceed 100")
    timestamp = _timestamp(request.timestamp)
    tasks = [_normalize_imported_task(raw, index) for index, raw in enumerate(raw_tasks, start=1) if isinstance(raw, dict)]
    if len(tasks) != len(raw_tasks):
        raise PlannerValidationError("import plan tasks entries must be objects")
    candidate_target = max(len(tasks), min(request.candidate_target, MAX_CANDIDATE_TASKS))
    normalized_request = PlannerRequest(
        candidate_target=candidate_target,
        command=request.command,
        dry_run=request.dry_run,
        import_plan=request.import_plan,
        live_pro=request.live_pro,
        max_parallel_agents=min(request.max_parallel_agents, candidate_target),
        mode=request.mode,
        request_file=request.request_file,
        request_text=request.request_text or "Manual-import Patch Swarm split plan.",
        run_dir=request.run_dir,
        run_id=request.run_id,
        timestamp=request.timestamp,
    )
    split_plan = _build_split_plan(normalized_request, tasks, timestamp)
    task_graph = build_task_graph(split_plan, max_parallel_agents=normalized_request.max_parallel_agents)
    _validate_or_raise(split_plan, task_graph)
    result = PlannerResult(
        artifacts=[],
        candidate_count=len(tasks),
        candidate_target=candidate_target,
        errors=[],
        max_parallel_agents=normalized_request.max_parallel_agents,
        mode=normalized_request.mode,
        run_dir=normalized_request.run_dir,
        run_id=normalized_request.run_id,
        split_plan=split_plan,
        task_graph=task_graph,
        warnings=[],
    )
    return write_planner_artifacts(result)


def write_task_contracts(run_dir: Path, tasks: list[dict[str, Any]]) -> list[str]:
    """Write task-contracts/task-XXXX.md files."""
    contract_dir = run_dir / "task-contracts"
    contract_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for task in tasks:
        path = contract_dir / f"{task['task_id']}.md"
        body = [
            f"# {task['task_id']} {task['title']}",
            "",
            f"Task ID: {task['task_id']}",
            f"Title: {task['title']}",
            f"Lane: {task['lane']}",
            f"Risk tier: {task['risk_tier']}",
            f"Worker profile: {task['worker_profile']}",
            f"Human handoff: {str(task['human_handoff']).lower()}",
            "",
            "## Story",
            task["story"],
            "",
            "## Owned Paths",
            *([f"- `{item}`" for item in task["owned_paths"]] or ["- None"]),
            "",
            "## Read-Only Paths",
            *([f"- `{item}`" for item in task["read_only_paths"]] or ["- None"]),
            "",
            "## Dependencies",
            *([f"- `{item}`" for item in task["dependencies"]] or ["- None"]),
            "",
            "## Acceptance Contract",
            *([f"- {item}" for item in task["acceptance_contract"]] or ["- Human decision required."]),
            "",
            "## Validation Commands",
            *([f"- `{item}`" for item in task["validation_commands"]] or ["- Human handoff validation evidence required."]),
            "",
            "## Expected Artifacts",
            *([f"- `{item}`" for item in task["expected_artifacts"]] or ["- None"]),
            "",
            "## Integration Notes",
            *([f"- {item}" for item in task["integration_notes"]] or ["- None"]),
            "",
            "## Rejection Triggers",
            *([f"- {item}" for item in task["rejection_triggers"]] or ["- None"]),
            "",
            "## Evidence To Produce",
            "- Update task evidence pointers or run-scoped validation logs before closeout.",
            "",
        ]
        path.write_text("\n".join(body), encoding="utf-8")
        paths.append(rel(path))
    return paths


def _write_request_artifact(run_dir: Path, request: PlannerRequest, timestamp: str) -> str:
    path = run_dir / "request.md"
    body = [
        _metadata_comment("request", request.run_id, timestamp),
        f"# {_request_title(request.request_text, 'Patch Swarm planner request')}",
        "",
        request.request_text.strip() or "Patch Swarm planner request.",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return rel(path)


def _planner_report(result: PlannerResult) -> str:
    lane_counts = Counter(task["lane"] for task in result.split_plan["tasks"])
    risk_counts = Counter(task["risk_tier"] for task in result.split_plan["tasks"])
    human = [task["task_id"] for task in result.split_plan["tasks"] if task["human_handoff"]]
    lines = [
        "# Patch Swarm Planner Report",
        "",
        "## Request",
        result.split_plan["request"]["title"],
        "",
        "## Planner Mode",
        result.mode,
        "",
        "## Candidate Target and Actual Count",
        f"target={result.candidate_target} actual={result.candidate_count}",
        "",
        "## Max Parallel Agents",
        str(result.max_parallel_agents),
        "",
        "## Lane Distribution",
        *[f"- {lane}: {count}" for lane, count in sorted(lane_counts.items())],
        "",
        "## Risk Distribution",
        *[f"- {risk}: {count}" for risk, count in sorted(risk_counts.items())],
        "",
        "## Human Handoff Tasks",
        *([f"- {task_id}" for task_id in human] or ["- None"]),
        "",
        "## Path Ownership Summary",
        f"{sum(len(task['owned_paths']) for task in result.split_plan['tasks'])} owned path assignments, validated for non-overlap.",
        "",
        "## Dependencies",
        f"{len([edge for edge in result.task_graph['edges'] if edge['type'] == 'depends_on'])} depends_on edges.",
        "",
        "## Validation Commands",
        "- Planner validation checks split-plan, task-graph, non-overlap, and path safety.",
        "",
        "## Artifacts",
        *[f"- `{item}`" for item in result.artifacts],
        "",
        "## Warnings",
        *([f"- {item}" for item in result.warnings] or ["- None"]),
        "",
    ]
    return "\n".join(lines)


def _start_here(result: PlannerResult, timestamp: str) -> str:
    return "\n".join(
        [
            _metadata_comment("start-here", result.run_id, timestamp),
            f"# Patch Swarm Planner Run: {result.run_id}",
            "",
            "## What This Is",
            "A durable split-plan and task-graph bundle for Patch Swarm planning. It is not live dispatch or patch application.",
            "",
            "## Artifact Index",
            "- `request.md`",
            "- `split-plan.json`",
            "- `task-graph.json`",
            "- `task-contracts/`",
            "- `planner-report.md`",
            "- `proreq/`",
            "",
            "## Validation Result",
            "Planner artifacts were validated locally before write completion.",
            "",
            "## Next Operator Action",
            "Review task contracts, then route later work through Patch Swarm, Factory, Workset, or Build surfaces.",
            "",
        ]
    )


def _proreq_prompt(result: PlannerResult) -> str:
    return "\n".join(
        [
            f"# ChatGPT Pro Patch Swarm Planner Request: {result.run_id}",
            "",
            "Produce a Cento Patch Swarm split plan that matches `split-plan.json` and `task-graph.json`.",
            "Use coarse product lanes before microtasks. Do not exceed 100 candidates.",
            "Avoid overlapping owned paths. Reject absolute paths, `..`, `.env.mcp`, and secret-like paths.",
            "Mark subjective, device-bound, credential-bound, production-operation, or unsafe tasks as `human_handoff: true`.",
            "",
            "Required task lanes: builder, validator, docs-evidence, coordinator, integrator, human-handoff.",
            "Required risk tiers: low, medium, high, human.",
            "Return JSON only for the plan if the operator asks for manual import.",
            "",
            "## Request",
            result.split_plan["request"]["summary"],
            "",
        ]
    )


def _write_proreq_artifacts(result: PlannerResult) -> list[str]:
    proreq_dir = result.run_dir / "proreq"
    proreq_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "artifact_type": "proreq-planning-manifest",
        "candidate_target": result.candidate_target,
        "created_at": result.split_plan["created_at"],
        "evidence_pointers": [],
        "expected_output_schema": {
            "split_plan": "split-plan.json",
            "task_graph": "task-graph.json",
        },
        "live_pro_called": False,
        "max_parallel_agents": result.max_parallel_agents,
        "prompt_path": "proreq/chatgpt-pro-planner-prompt.md",
        "provenance": _provenance("patch-swarm split --mode proreq", result.mode, "local"),
        "request_file": result.split_plan["request"]["request_file"],
        "run_id": result.run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    manifest_path = proreq_dir / "planning-manifest.json"
    prompt_path = proreq_dir / "chatgpt-pro-planner-prompt.md"
    instructions_path = proreq_dir / "manual-import-instructions.md"
    write_json(manifest_path, manifest)
    prompt_path.write_text(_proreq_prompt(result), encoding="utf-8")
    instructions_path.write_text(
        "\n".join(
            [
                "# Manual Import Instructions",
                "",
                "Ask ChatGPT Pro for a split plan JSON object, save it locally, then run:",
                "",
                "```bash",
                "cento parallel-delivery patch-swarm split --mode manual-import --import-plan PLAN.json --run-dir workspace/runs/parallel-delivery/imported-plan --json",
                "```",
                "",
                "The import validator rejects unknown dependencies, overlapping paths, unsafe paths, and missing contracts.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return [rel(manifest_path), rel(prompt_path), rel(instructions_path)]


def write_planner_artifacts(result: PlannerResult) -> PlannerResult:
    """Write split-plan.json, task-graph.json, task contracts, planner report, and start-here."""
    result.run_dir.mkdir(parents=True, exist_ok=True)
    timestamp = result.split_plan["created_at"]
    artifacts: list[str] = []
    request = PlannerRequest(
        candidate_target=result.candidate_target,
        max_parallel_agents=result.max_parallel_agents,
        mode=result.mode,
        request_file=result.split_plan["request"]["request_file"],
        request_text=result.split_plan["request"]["summary"],
        run_dir=result.run_dir,
        run_id=result.run_id,
        timestamp=timestamp,
    )
    artifacts.append(_write_request_artifact(result.run_dir, request, timestamp))
    split_path = result.run_dir / "split-plan.json"
    graph_path = result.run_dir / "task-graph.json"
    write_json(split_path, result.split_plan)
    write_json(graph_path, result.task_graph)
    artifacts.extend([rel(split_path), rel(graph_path)])
    artifacts.extend(write_task_contracts(result.run_dir, result.split_plan["tasks"]))
    proreq_artifacts = _write_proreq_artifacts(result)
    artifacts.extend(proreq_artifacts)
    report_result = PlannerResult(
        artifacts=artifacts,
        candidate_count=result.candidate_count,
        candidate_target=result.candidate_target,
        errors=result.errors,
        max_parallel_agents=result.max_parallel_agents,
        mode=result.mode,
        run_dir=result.run_dir,
        run_id=result.run_id,
        split_plan=result.split_plan,
        task_graph=result.task_graph,
        warnings=result.warnings,
    )
    report_path = result.run_dir / "planner-report.md"
    start_path = result.run_dir / "start-here.md"
    report_path.write_text(_planner_report(report_result), encoding="utf-8")
    start_path.write_text(_start_here(report_result, timestamp), encoding="utf-8")
    artifacts.extend([rel(report_path), rel(start_path)])
    return PlannerResult(
        artifacts=artifacts,
        candidate_count=result.candidate_count,
        candidate_target=result.candidate_target,
        errors=result.errors,
        max_parallel_agents=result.max_parallel_agents,
        mode=result.mode,
        run_dir=result.run_dir,
        run_id=result.run_id,
        split_plan=result.split_plan,
        task_graph=result.task_graph,
        warnings=result.warnings,
    )


def run_planner(request: PlannerRequest) -> PlannerResult:
    """Dispatch by planner mode."""
    validate_candidate_target(request.candidate_target)
    validate_max_parallel_agents(request.max_parallel_agents, request.candidate_target)
    if request.mode == "fixture":
        return plan_fixture(request)
    if request.mode == "no-model":
        return plan_no_model(request)
    if request.mode == "proreq":
        return plan_proreq(request)
    if request.mode == "manual-import":
        return plan_manual_import(request)
    raise PlannerValidationError(f"unknown planner mode: {request.mode}")


def _response(result: PlannerResult, command: str, dry_run: bool, live_pro: bool) -> dict[str, Any]:
    return {
        "artifacts": result.artifacts,
        "candidate_count": result.candidate_count,
        "candidate_target": result.candidate_target,
        "command": command,
        "dry_run": dry_run,
        "errors": result.errors,
        "live_pro": live_pro,
        "max_parallel_agents": result.max_parallel_agents,
        "ok": not result.errors,
        "planner_mode": result.mode,
        "run_dir": rel(result.run_dir),
        "run_id": result.run_id,
        "state": "split_plan_created" if not result.errors else "split_plan_failed",
        "warnings": result.warnings,
    }


def _error_response(
    *,
    command: str,
    dry_run: bool,
    live_pro: bool,
    mode: str,
    candidate_target: int,
    max_parallel_agents: int,
    run_dir: Path,
    run_id: str,
    error: str,
) -> dict[str, Any]:
    return {
        "artifacts": [],
        "candidate_count": 0,
        "candidate_target": candidate_target,
        "command": command,
        "dry_run": dry_run,
        "errors": [error],
        "live_pro": live_pro,
        "max_parallel_agents": max_parallel_agents,
        "ok": False,
        "planner_mode": mode,
        "run_dir": rel(run_dir),
        "run_id": run_id,
        "state": "split_plan_failed",
        "warnings": [],
    }


def run_planner_command(
    *,
    command: str = "parallel-delivery patch-swarm split",
    request_file: str | Path | None = None,
    request_text: str | None = None,
    run_id: str | None = None,
    run_dir: str | Path | None = None,
    mode: str = "fixture",
    candidate_target: int = 100,
    max_parallel_agents: int = 5,
    import_plan: str | Path | None = None,
    dry_run: bool = False,
    live_pro: bool = False,
    timestamp: str | None = None,
) -> tuple[dict[str, Any], int]:
    resolved_run_id = run_id or f"planner-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    resolved_run_dir = Path(run_dir) if run_dir else RUNS_ROOT / resolved_run_id
    if not resolved_run_dir.is_absolute():
        resolved_run_dir = ROOT / resolved_run_dir
    try:
        mode = mode or "fixture"
        if mode not in PLANNER_MODES:
            raise PlannerValidationError(f"planner mode must be one of {', '.join(sorted(PLANNER_MODES))}")
        validate_candidate_target(int(candidate_target))
        validate_max_parallel_agents(int(max_parallel_agents), int(candidate_target))
        text = request_text or ""
        if mode in {"no-model", "proreq"}:
            text = read_request_text(Path(request_file) if request_file else None, text or None)
        elif mode == "fixture":
            text = text or (
                "Build a local-first Patch Swarm planner fixture with bounded candidate tasks, "
                "safe path ownership, task contracts, and deterministic task graph artifacts."
            )
            if request_file:
                text = read_request_text(Path(request_file), text)
        elif mode == "manual-import":
            text = text or "Manual-import Patch Swarm split plan."
            if request_file:
                text = read_request_text(Path(request_file), text)
        request = PlannerRequest(
            candidate_target=int(candidate_target),
            command=command,
            dry_run=dry_run,
            import_plan=Path(import_plan) if import_plan else None,
            live_pro=live_pro,
            max_parallel_agents=int(max_parallel_agents),
            mode=mode,
            request_file=str(request_file) if request_file else None,
            request_text=text,
            run_dir=resolved_run_dir,
            run_id=resolved_run_id,
            timestamp=timestamp,
        )
        result = run_planner(request)
        return _response(result, command, dry_run, live_pro), 0
    except PlannerValidationError as exc:
        return (
            _error_response(
                candidate_target=int(candidate_target) if str(candidate_target).isdigit() else 0,
                command=command,
                dry_run=dry_run,
                error=str(exc),
                live_pro=live_pro,
                max_parallel_agents=int(max_parallel_agents) if str(max_parallel_agents).isdigit() else 0,
                mode=mode or "fixture",
                run_dir=resolved_run_dir,
                run_id=resolved_run_id,
            ),
            2,
        )


def run_from_args(args: argparse.Namespace, *, command: str = "parallel-delivery patch-swarm split") -> tuple[dict[str, Any], int]:
    mode = normalize_mode(args)
    candidate_target = int(getattr(args, "candidate_target", 100) or getattr(args, "max_tasks", 100) or 100)
    max_parallel_agents = int(getattr(args, "max_parallel_agents", 5) or 5)
    return run_planner_command(
        candidate_target=candidate_target,
        command=command,
        dry_run=bool(getattr(args, "dry_run", False)),
        import_plan=getattr(args, "import_plan", "") or None,
        live_pro=bool(getattr(args, "live_pro", False)),
        max_parallel_agents=max_parallel_agents,
        mode=mode,
        request_file=getattr(args, "request_file", "") or None,
        request_text=getattr(args, "request_text", "") or None,
        run_dir=getattr(args, "run_dir", "") or None,
        run_id=getattr(args, "run_id", "") or None,
        timestamp=getattr(args, "fixed_timestamp", "") or None,
    )


def add_split_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--request-file", default="")
    parser.add_argument("--request-text", default="", help=argparse.SUPPRESS)
    parser.add_argument("--candidate-target", type=int, default=100)
    parser.add_argument("--max-tasks", dest="candidate_target", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--max-parallel-agents", type=int, default=5)
    parser.add_argument("--mode", choices=sorted(PLANNER_MODES), default="")
    parser.add_argument("--fixture", action="store_true", help="Generate deterministic fixture tasks.")
    parser.add_argument("--no-model", action="store_true", help="Use the deterministic rule-based splitter.")
    parser.add_argument("--proreq", action="store_true", help="Emit ChatGPT Pro planner prompt artifacts.")
    parser.add_argument("--manual-import", action="store_true", help="Normalize and validate an imported split plan.")
    parser.add_argument("--import-plan", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live-pro", action="store_true")
    parser.add_argument("--fixed-timestamp", default="", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create Patch Swarm split-plan and task-graph artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    split = sub.add_parser("split", help="Write planner artifacts for a Patch Swarm request.")
    add_split_args(split)
    split.set_defaults(func=command_split)
    return parser


def command_split(args: argparse.Namespace) -> int:
    payload, code = run_from_args(args, command="parallel-delivery patch-swarm split")
    if args.json:
        print(stable_json_dumps(payload), end="")
    elif payload["ok"]:
        print(f"{payload['state']} {payload['candidate_count']} tasks {payload['run_dir']}")
    else:
        print("; ".join(payload["errors"]), file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
