#!/usr/bin/env python3
"""Patch Swarm path lease helper.

This module creates and validates Patch Swarm path leases. It is a safety and
evidence layer only: it does not dispatch workers, apply patches, or mutate
Taskstream/Redmine state.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import cento_workset  # type: ignore  # noqa: E402
except Exception:  # pragma: no cover - import availability is reported in compatibility output
    cento_workset = None  # type: ignore


CURRENT_SCHEMA_VERSION = 1
PRODUCER = "cento.parallel-delivery.leases"

LEASE_STATES = {
    "proposed",
    "active",
    "blocked",
    "conflict",
    "released",
    "expired",
    "rejected",
}

ALLOWED_OPERATIONS = {
    "create",
    "modify",
    "delete",
    "rename",
}

BLOCKED_OPERATIONS = {
    "binary_patch",
    "broad_cleanup",
}

SECRET_PROTECTED_PATTERNS = [
    ".env",
    ".env.*",
    ".env.mcp",
    "*.pem",
    "*.key",
    "*secret*",
    "*token*",
    "*credential*",
]

GUARDED_PATHS = {
    "data/tools.json",
    "data/cento-cli.json",
    "Makefile",
    "pyproject.toml",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "requirements.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
}

LOCKFILE_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "npm-shrinkwrap.json",
    "Cargo.lock",
    "Gemfile.lock",
    "Pipfile.lock",
    "poetry.lock",
    "requirements.lock",
    "uv.lock",
    "go.sum",
}

LEASE_REQUIRED_FIELDS = [
    "lease_id",
    "task_id",
    "state",
    "lane",
    "risk_tier",
    "owned_paths",
    "read_only_paths",
    "guarded_paths",
    "protected_paths",
    "dirty_owned_paths",
    "allowed_operations",
    "blocked_operations",
    "dependencies",
    "dependency_gate",
    "parallel_group",
    "requires_minimal_hunks",
    "requires_manual_review",
    "created_at",
    "evidence_pointers",
]

TOP_LEVEL_REQUIRED_FIELDS = [
    "schema_version",
    "artifact_type",
    "run_id",
    "created_at",
    "updated_at",
    "provenance",
    "lease_policy",
    "leases",
    "conflicts",
    "dependency_gates",
    "parallel_groups",
    "workset_manifest",
    "dirty_targets",
    "warnings",
    "evidence_pointers",
]

ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MARKDOWN_PREFIX = "<!-- cento-artifact:"


class LeaseValidationError(Exception):
    """Raised when a lease or planned operation violates Patch Swarm path safety."""


def utc_now() -> str:
    """Return current UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: dict[str, Any]) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LeaseValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LeaseValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LeaseValidationError(f"expected JSON object in {path}")
    return payload


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def metadata_comment(artifact_type: str, run_id: str, timestamp: str) -> str:
    metadata = {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "run_id": run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
    }
    return f"<!-- cento-artifact: {json.dumps(metadata, sort_keys=True, separators=(',', ':'))} -->"


def lease_policy() -> dict[str, Any]:
    """Return the Patch Swarm lease policy."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "read_many_write_few": True,
        "reject_overlapping_owned_paths": True,
        "reject_protected_secret_paths": True,
        "guard_lockfiles": True,
        "reject_unowned_renames": True,
        "reject_unsafe_deletes": True,
        "reject_binary_patches": True,
        "reject_broad_cleanup": True,
        "dirty_targets_require_minimal_hunks": True,
        "protected_patterns": sorted(SECRET_PROTECTED_PATTERNS),
        "guarded_paths": sorted(GUARDED_PATHS),
    }


def provenance(command: str, source: str = "split-plan/task-graph") -> dict[str, Any]:
    return {
        "producer": PRODUCER,
        "command": command,
        "source": source,
        "repo": "cento",
        "notes": [],
    }


def normalize_repo_path(path: str) -> str:
    """Normalize and validate a relative repo path."""
    value = str(path).strip().replace("\\", "/")
    value = re.sub(r"/+", "/", value)
    while value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    if value in {"", ".", "/", "*", "**"}:
        raise LeaseValidationError(f"{path}: broad cleanup or repo-root paths are not allowed")
    if value.startswith("/") or value.startswith("~"):
        raise LeaseValidationError(f"{path}: absolute or home-relative paths are not allowed")
    parts = value.split("/")
    if ".." in parts:
        raise LeaseValidationError(f"{path}: parent traversal is not allowed")
    if parts[0] == ".git" or ".git" in parts:
        raise LeaseValidationError(f"{path}: .git paths are not allowed")
    if is_secret_protected_path(value):
        raise LeaseValidationError(f"{path}: protected secret-like paths are not allowed")
    return value


def normalize_path_list(paths: Any, field: str) -> tuple[list[str], list[str], list[str]]:
    normalized: list[str] = []
    protected: list[str] = []
    errors: list[str] = []
    if paths is None:
        return [], [], []
    if not isinstance(paths, list):
        return [], [], [f"{field} must be a list"]
    for item in paths:
        if not isinstance(item, str):
            errors.append(f"{field} entries must be strings")
            continue
        try:
            normalized.append(normalize_repo_path(item))
        except LeaseValidationError as exc:
            errors.append(str(exc))
            protected.append(str(item))
    return sorted(dict.fromkeys(normalized)), sorted(dict.fromkeys(protected)), errors


def is_secret_protected_path(path: str) -> bool:
    """Return true for always-rejected secret/protected paths."""
    lowered = str(path).replace("\\", "/").lower().strip()
    parts = [part for part in lowered.split("/") if part]
    candidates = [lowered, *parts]
    for candidate in candidates:
        for pattern in SECRET_PROTECTED_PATTERNS:
            if fnmatch.fnmatch(candidate, pattern.lower()):
                return True
    return False


def is_lockfile_path(path: str) -> bool:
    return path.split("/")[-1] in LOCKFILE_NAMES


def is_guarded_path(path: str) -> bool:
    """Return true for registry/config/lockfile paths requiring explicit contract and review."""
    return path in GUARDED_PATHS or is_lockfile_path(path)


def paths_overlap(a: str, b: str) -> bool:
    """Return true for exact or parent/child write path overlap."""
    left = a.rstrip("/")
    right = b.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def path_is_owned(path: str, owned_paths: list[str]) -> bool:
    return any(path == owned or path.startswith(owned.rstrip("/") + "/") for owned in owned_paths)


def _conflict(
    index: int,
    conflict_type: str,
    task_ids: list[str],
    paths: list[str],
    reason: str,
    *,
    resolution: str = "narrow one lease, add dependency gate, or group tasks sequentially",
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "conflict_id": f"conflict-{index:04d}",
        "type": conflict_type,
        "severity": severity,
        "task_ids": sorted(dict.fromkeys(task_ids)),
        "paths": sorted(dict.fromkeys(paths)),
        "reason": reason,
        "resolution": resolution,
    }


def detect_owned_path_conflicts(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect exact and parent/child write/write conflicts."""
    conflicts: list[dict[str, Any]] = []
    owned: list[tuple[str, str]] = []
    for task in tasks:
        for path in task.get("owned_paths", []):
            owned.append((str(task.get("task_id") or "unknown"), str(path)))
    for index, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index + 1 :]:
            if path_a == path_b:
                conflicts.append(
                    _conflict(
                        len(conflicts) + 1,
                        "owned_path_overlap",
                        [task_a, task_b],
                        [path_a, path_b],
                        "exact owned path overlap",
                    )
                )
            elif paths_overlap(path_a, path_b):
                conflicts.append(
                    _conflict(
                        len(conflicts) + 1,
                        "owned_path_overlap",
                        [task_a, task_b],
                        [path_a, path_b],
                        "parent/child owned path overlap",
                    )
                )
    return conflicts


def parse_git_status_porcelain(text: str) -> list[dict[str, str]]:
    """Parse git status --porcelain=v1 without reading file contents."""
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line:
            continue
        status = line[:2]
        raw_path = line[3:] if len(line) > 3 else line[2:].strip()
        old_path = ""
        if " -> " in raw_path:
            old_path, raw_path = raw_path.split(" -> ", 1)
        rows.append({"status": status.strip() or status, "path": raw_path, "old_path": old_path})
    return rows


def detect_dirty_targets(tasks: list[dict[str, Any]], dirty_files: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Find dirty files under owned paths and produce warnings."""
    dirty_targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for dirty in dirty_files:
        raw_path = dirty.get("path", "")
        try:
            dirty_path = normalize_repo_path(raw_path)
        except LeaseValidationError:
            continue
        for task in tasks:
            task_id = str(task.get("task_id"))
            owned_paths = [str(path) for path in task.get("owned_paths", [])]
            if any(paths_overlap(dirty_path, owned) for owned in owned_paths):
                key = (dirty_path, task_id)
                if key in seen:
                    continue
                seen.add(key)
                dirty_targets.append(
                    {
                        "path": dirty_path,
                        "status": dirty.get("status", ""),
                        "task_ids": [task_id],
                        "risk": "high",
                        "required_handling": (
                            "inspect before editing; preserve unrelated hunks; minimal additive hunks only; "
                            "no reset/checkout/clean/stash"
                        ),
                    }
                )
    return dirty_targets


def make_lease_id(run_id: str, task_id: str, owned_paths: list[str], read_only_paths: list[str]) -> str:
    """Create stable lease-task-id-hash."""
    payload = {
        "owned_paths": sorted(owned_paths),
        "read_only_paths": sorted(read_only_paths),
        "run_id": run_id,
        "task_id": task_id,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    return f"lease-{task_id}-{digest}"


def task_contract_allows_lockfile(task: dict[str, Any]) -> bool:
    text = " ".join(
        str(item)
        for field in ("acceptance_contract", "validation_commands", "title", "summary")
        for item in (task.get(field) if isinstance(task.get(field), list) else [task.get(field, "")])
    ).lower()
    return "lockfile" in text or "lock file" in text or "package" in text or "dependency" in text


def extract_task_contracts(split_plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    tasks: list[dict[str, Any]] = []
    raw_tasks = split_plan.get("tasks")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        return [], ["split-plan.tasks must be a non-empty list"]
    for index, raw_task in enumerate(raw_tasks, start=1):
        if not isinstance(raw_task, dict):
            errors.append(f"split-plan.tasks[{index}] must be an object")
            continue
        task_id = str(raw_task.get("task_id") or raw_task.get("id") or f"task-{index:04d}")
        owned_paths, protected_owned, owned_errors = normalize_path_list(
            raw_task.get("owned_paths", raw_task.get("write_paths", [])),
            f"{task_id}.owned_paths",
        )
        read_only_paths, protected_read, read_errors = normalize_path_list(
            raw_task.get("read_only_paths", raw_task.get("read_paths", [])),
            f"{task_id}.read_only_paths",
        )
        errors.extend(owned_errors)
        errors.extend(read_errors)
        task = {
            "task_id": task_id,
            "title": str(raw_task.get("title") or raw_task.get("task") or task_id),
            "summary": str(raw_task.get("summary") or raw_task.get("description") or ""),
            "lane": str(raw_task.get("lane") or "builder"),
            "risk_tier": str(raw_task.get("risk_tier") or "medium"),
            "human_handoff": bool(raw_task.get("human_handoff", False)),
            "owned_paths": owned_paths,
            "read_only_paths": read_only_paths,
            "protected_paths": sorted(dict.fromkeys([*protected_owned, *protected_read])),
            "dependencies": [str(item) for item in raw_task.get("dependencies", raw_task.get("depends_on", [])) or []],
            "acceptance_contract": [str(item) for item in raw_task.get("acceptance_contract", []) or []],
            "validation_commands": [str(item) for item in raw_task.get("validation_commands", []) or []],
            "lockfile_contract_ok": task_contract_allows_lockfile(raw_task),
        }
        tasks.append(task)
    return tasks, errors


def _dependency_edges(task_graph: dict[str, Any] | None, tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    if isinstance(task_graph, dict):
        for edge in task_graph.get("edges", []):
            if isinstance(edge, dict) and edge.get("type") == "depends_on":
                edges.append({"from": str(edge.get("from")), "to": str(edge.get("to")), "type": "depends_on"})
    known = {task["task_id"] for task in tasks}
    existing = {(edge["from"], edge["to"]) for edge in edges}
    for task in tasks:
        for dep in task.get("dependencies", []):
            if dep in known and (dep, task["task_id"]) not in existing:
                edges.append({"from": dep, "to": task["task_id"], "type": "depends_on"})
    return edges


def _topological_order(tasks: list[dict[str, Any]], edges: list[dict[str, str]]) -> list[str]:
    ids = sorted(task["task_id"] for task in tasks)
    incoming = {task_id: 0 for task_id in ids}
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in ids}
    for edge in edges:
        source = edge.get("from", "")
        target = edge.get("to", "")
        if source not in incoming or target not in incoming:
            continue
        outgoing[source].append(target)
        incoming[target] += 1
    ready = sorted(task_id for task_id, count in incoming.items() if count == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for target in sorted(outgoing.get(current, [])):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
        ready.sort()
    if len(order) != len(ids):
        return ids
    return order


def build_dependency_gates(
    split_plan: dict[str, Any],
    task_graph: dict[str, Any] | None,
    leases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create dependency gates from task dependencies and guarded/dirty/manual review constraints."""
    tasks, _ = extract_task_contracts(split_plan)
    edges = _dependency_edges(task_graph, tasks)
    gates: list[dict[str, Any]] = []
    for edge in edges:
        gates.append(
            {
                "gate_id": f"gate-{len(gates) + 1:04d}",
                "type": "dependency",
                "before": [edge["from"]],
                "after": [edge["to"]],
                "reason": f"{edge['to']} depends on {edge['from']}",
                "enforced_by": "task-graph",
            }
        )
    for lease in leases:
        if lease.get("guarded_paths"):
            gates.append(
                {
                    "gate_id": f"gate-{len(gates) + 1:04d}",
                    "type": "guarded_path",
                    "before": [],
                    "after": [lease["task_id"]],
                    "reason": "guarded path requires manual review and minimal hunks",
                    "enforced_by": "path-lease-policy",
                }
            )
        if lease.get("dirty_owned_paths"):
            gates.append(
                {
                    "gate_id": f"gate-{len(gates) + 1:04d}",
                    "type": "dirty_target",
                    "before": [],
                    "after": [lease["task_id"]],
                    "reason": "dirty owned path requires preserving unrelated hunks",
                    "enforced_by": "git-status",
                }
            )
        if lease.get("requires_manual_review") or lease.get("lane") == "human-handoff":
            gates.append(
                {
                    "gate_id": f"gate-{len(gates) + 1:04d}",
                    "type": "manual_review",
                    "before": [],
                    "after": [lease["task_id"]],
                    "reason": "manual review required before automated integration",
                    "enforced_by": "path-lease-policy",
                }
            )
    return gates


def build_parallel_groups(
    split_plan: dict[str, Any],
    task_graph: dict[str, Any] | None,
    leases: list[dict[str, Any]],
    dependency_gates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group tasks that can safely run in parallel."""
    tasks, _ = extract_task_contracts(split_plan)
    edges = _dependency_edges(task_graph, tasks)
    order = task_graph.get("topological_order") if isinstance(task_graph, dict) else None
    if not isinstance(order, list) or set(str(item) for item in order) != {task["task_id"] for task in tasks}:
        order = _topological_order(tasks, edges)
    max_parallel = int(split_plan.get("max_parallel_agents") or split_plan.get("max_parallel") or 5)
    leases_by_task = {lease["task_id"]: lease for lease in leases}
    dependency_targets = {edge["to"] for edge in edges}
    groups: list[dict[str, Any]] = []
    current: list[str] = []

    def flush(reason: str = "non-overlapping owned paths and no dependency gate") -> None:
        nonlocal current
        if current:
            groups.append(
                {
                    "group_id": f"parallel-group-{len(groups) + 1:04d}",
                    "task_ids": current,
                    "safe_parallel": True,
                    "reason": reason,
                }
            )
            current = []

    for task_id_value in order:
        task_id = str(task_id_value)
        lease = leases_by_task.get(task_id)
        if not lease:
            continue
        manual = bool(lease.get("requires_manual_review")) or lease.get("lane") == "human-handoff"
        blocked = lease.get("state") not in {"active", "proposed", "released"}
        has_dependency = task_id in dependency_targets
        if manual or blocked or has_dependency:
            flush()
            groups.append(
                {
                    "group_id": f"parallel-group-{len(groups) + 1:04d}",
                    "task_ids": [task_id],
                    "safe_parallel": not blocked and not manual,
                    "reason": (
                        "manual review or high-risk guarded path"
                        if manual
                        else "dependency gate requires sequential placement"
                        if has_dependency
                        else "lease is blocked or rejected"
                    ),
                }
            )
            continue
        current.append(task_id)
        if len(current) >= max_parallel:
            flush()
    flush()
    return groups


def create_leases(
    split_plan: dict[str, Any],
    task_graph: dict[str, Any] | None,
    *,
    git_status_text: str,
    timestamp: str,
    command: str = "patch-swarm leases",
) -> dict[str, Any]:
    """Create path-leases.json payload."""
    run_id = str(split_plan.get("run_id") or (task_graph or {}).get("run_id") or "lease-fixture")
    tasks, task_errors = extract_task_contracts(split_plan)
    dirty_files = parse_git_status_porcelain(git_status_text)
    dirty_targets = detect_dirty_targets(tasks, dirty_files)
    dirty_by_task: dict[str, list[str]] = {}
    for target in dirty_targets:
        for task_id in target["task_ids"]:
            dirty_by_task.setdefault(task_id, []).append(target["path"])

    leases: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, task in enumerate(tasks, start=1):
        task_id = task["task_id"]
        guarded_paths = sorted(path for path in task["owned_paths"] if is_guarded_path(path))
        dirty_owned_paths = sorted(dict.fromkeys(dirty_by_task.get(task_id, [])))
        lockfiles = sorted(path for path in task["owned_paths"] if is_lockfile_path(path))
        protected_paths = list(task.get("protected_paths", []))
        risk_tier = task.get("risk_tier") or "medium"
        requires_manual_review = bool(task.get("human_handoff") or guarded_paths or dirty_owned_paths or protected_paths)
        requires_minimal_hunks = bool(guarded_paths or dirty_owned_paths or protected_paths)
        state = "active"
        if task.get("human_handoff"):
            risk_tier = "human"
        if guarded_paths or dirty_owned_paths or protected_paths:
            risk_tier = "high" if risk_tier != "human" else "human"
        if protected_paths:
            state = "rejected"
            conflicts.append(
                _conflict(
                    len(conflicts) + 1,
                    "protected_path",
                    [task_id],
                    protected_paths,
                    "always-protected secret-like path is rejected",
                    resolution="remove secret-like paths from the task contract",
                )
            )
        for lockfile in lockfiles:
            if not task.get("lockfile_contract_ok"):
                state = "rejected"
                conflicts.append(
                    _conflict(
                        len(conflicts) + 1,
                        "lockfile_contract_missing",
                        [task_id],
                        [lockfile],
                        "lockfile changes require explicit lockfile/package dependency validation in the task contract",
                        resolution="add explicit lockfile/package dependency validation or remove the lockfile path",
                    )
                )
        for dirty_path in dirty_owned_paths:
            warnings.append(
                {
                    "type": "dirty_target",
                    "task_id": task_id,
                    "path": dirty_path,
                    "message": "dirty target; preserve unrelated hunks; minimal additive edits only; no reset/checkout/clean/stash",
                }
            )
        lease = {
            "lease_id": make_lease_id(run_id, task_id, task["owned_paths"], task["read_only_paths"]),
            "task_id": task_id,
            "state": state,
            "lane": task.get("lane") or "builder",
            "risk_tier": risk_tier,
            "owned_paths": task["owned_paths"],
            "read_only_paths": task["read_only_paths"],
            "guarded_paths": guarded_paths,
            "protected_paths": protected_paths,
            "dirty_owned_paths": dirty_owned_paths,
            "allowed_operations": ["create", "modify"],
            "blocked_operations": ["delete", "rename", "binary_patch", "broad_cleanup"],
            "dependencies": task.get("dependencies", []),
            "dependency_gate": None,
            "parallel_group": None,
            "requires_minimal_hunks": requires_minimal_hunks,
            "requires_manual_review": requires_manual_review,
            "contract_allows_lockfile": bool(task.get("lockfile_contract_ok")),
            "created_at": timestamp,
            "evidence_pointers": [],
        }
        if not lease["owned_paths"] and not lease["requires_manual_review"]:
            lease["state"] = "blocked"
            warnings.append({"type": "missing_owned_paths", "task_id": task_id, "message": "automated tasks should declare owned paths"})
        leases.append(lease)

    normalized_tasks = [{"task_id": lease["task_id"], "owned_paths": lease["owned_paths"]} for lease in leases if lease["state"] == "active"]
    conflicts.extend(detect_owned_path_conflicts(normalized_tasks))
    conflicted_tasks = {task_id for conflict in conflicts for task_id in conflict.get("task_ids", []) if conflict.get("type") == "owned_path_overlap"}
    for lease in leases:
        if lease["task_id"] in conflicted_tasks:
            lease["state"] = "conflict"

    dependency_gates = build_dependency_gates(split_plan, task_graph, leases)
    gate_by_task: dict[str, str] = {}
    for gate in dependency_gates:
        for task_id in gate.get("after", []):
            gate_by_task.setdefault(str(task_id), str(gate.get("gate_id")))
    for lease in leases:
        lease["dependency_gate"] = gate_by_task.get(lease["task_id"])

    parallel_groups = build_parallel_groups(split_plan, task_graph, leases, dependency_gates)
    group_by_task: dict[str, int] = {}
    for index, group in enumerate(parallel_groups, start=1):
        for task_id in group.get("task_ids", []):
            group_by_task[str(task_id)] = index
    for lease in leases:
        lease["parallel_group"] = group_by_task.get(lease["task_id"])

    for error in task_errors:
        conflicts.append(
            _conflict(
                len(conflicts) + 1,
                "task_contract_invalid",
                [],
                [],
                error,
                resolution="fix split-plan path and task contract fields",
            )
        )

    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "path-leases",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": provenance(command),
        "lease_policy": lease_policy(),
        "leases": leases,
        "conflicts": conflicts,
        "dependency_gates": dependency_gates,
        "parallel_groups": parallel_groups,
        "workset_manifest": None,
        "dirty_targets": dirty_targets,
        "warnings": warnings,
        "evidence_pointers": [],
    }


def _validate_iso(value: Any, field: str) -> list[str]:
    if not isinstance(value, str) or not ISO_Z_RE.match(value):
        return [f"{field} must be ISO-8601 UTC with trailing Z"]
    return []


def validate_path_list(paths: Any, field: str) -> list[str]:
    if not isinstance(paths, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    for index, item in enumerate(paths, start=1):
        if not isinstance(item, str):
            errors.append(f"{field}[{index}] must be a string")
            continue
        try:
            normalize_repo_path(item)
        except LeaseValidationError as exc:
            errors.append(f"{field}[{index}]: {exc}")
    return errors


def validate_path_leases(path_leases: dict[str, Any]) -> list[str]:
    """Validate required fields, path safety, non-overlap, and lease policy."""
    errors: list[str] = []
    for field in TOP_LEVEL_REQUIRED_FIELDS:
        if field not in path_leases:
            errors.append(f"path-leases missing {field}")
    if path_leases.get("schema_version") != CURRENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CURRENT_SCHEMA_VERSION}")
    if path_leases.get("artifact_type") != "path-leases":
        errors.append("artifact_type must be path-leases")
    if not isinstance(path_leases.get("run_id"), str) or not path_leases.get("run_id"):
        errors.append("run_id must be a non-empty string")
    errors.extend(_validate_iso(path_leases.get("created_at"), "created_at"))
    errors.extend(_validate_iso(path_leases.get("updated_at"), "updated_at"))
    if not isinstance(path_leases.get("lease_policy"), dict):
        errors.append("lease_policy must be an object")
    leases = path_leases.get("leases")
    if not isinstance(leases, list):
        return errors + ["leases must be a list"]

    active_tasks: list[dict[str, Any]] = []
    for index, lease in enumerate(leases, start=1):
        label = f"leases[{index}]"
        if not isinstance(lease, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in LEASE_REQUIRED_FIELDS:
            if field not in lease:
                errors.append(f"{label} missing {field}")
        if lease.get("state") not in LEASE_STATES:
            errors.append(f"{label}.state must be a known lease state")
        errors.extend(_validate_iso(lease.get("created_at"), f"{label}.created_at"))
        errors.extend(validate_path_list(lease.get("owned_paths"), f"{label}.owned_paths"))
        errors.extend(validate_path_list(lease.get("read_only_paths"), f"{label}.read_only_paths"))
        errors.extend(validate_path_list(lease.get("guarded_paths"), f"{label}.guarded_paths"))
        errors.extend(validate_path_list(lease.get("dirty_owned_paths"), f"{label}.dirty_owned_paths"))
        protected_paths = lease.get("protected_paths")
        if not isinstance(protected_paths, list):
            errors.append(f"{label}.protected_paths must be a list")
        elif protected_paths:
            errors.append(f"{label}.protected_paths must be empty for valid leases: {', '.join(map(str, protected_paths))}")
        for field in ["requires_minimal_hunks", "requires_manual_review"]:
            if not isinstance(lease.get(field), bool):
                errors.append(f"{label}.{field} must be boolean")
        for guarded_path in lease.get("guarded_paths", []) if isinstance(lease.get("guarded_paths"), list) else []:
            if guarded_path not in lease.get("owned_paths", []):
                errors.append(f"{label}.guarded_paths must also be owned: {guarded_path}")
            if lease.get("risk_tier") not in {"high", "human"}:
                errors.append(f"{label}: guarded paths require high risk tier")
            if lease.get("requires_manual_review") is not True:
                errors.append(f"{label}: guarded paths require manual review")
            if lease.get("requires_minimal_hunks") is not True:
                errors.append(f"{label}: guarded paths require minimal hunks")
        if lease.get("dirty_owned_paths"):
            if lease.get("risk_tier") not in {"high", "human"}:
                errors.append(f"{label}: dirty targets require high risk tier")
            if lease.get("requires_minimal_hunks") is not True:
                errors.append(f"{label}: dirty targets require minimal hunks")
        if isinstance(lease.get("owned_paths"), list) and isinstance(lease.get("read_only_paths"), list):
            expected = make_lease_id(
                str(path_leases.get("run_id") or ""),
                str(lease.get("task_id") or ""),
                [str(item) for item in lease.get("owned_paths")],
                [str(item) for item in lease.get("read_only_paths")],
            )
            if lease.get("lease_id") != expected:
                errors.append(f"{label}.lease_id must be deterministic: expected {expected}")
        if lease.get("state") in {"active", "proposed"}:
            active_tasks.append({"task_id": str(lease.get("task_id")), "owned_paths": lease.get("owned_paths", [])})

    errors.extend(conflict["reason"] for conflict in detect_owned_path_conflicts(active_tasks))
    conflicts = path_leases.get("conflicts")
    if not isinstance(conflicts, list):
        errors.append("conflicts must be a list")
    else:
        for conflict in conflicts:
            if isinstance(conflict, dict) and conflict.get("severity", "error") == "error":
                errors.append(f"{conflict.get('conflict_id', 'conflict')}: {conflict.get('reason', 'conflict present')}")
    if not isinstance(path_leases.get("dependency_gates"), list):
        errors.append("dependency_gates must be a list")
    if not isinstance(path_leases.get("parallel_groups"), list):
        errors.append("parallel_groups must be a list")
    if not isinstance(path_leases.get("dirty_targets"), list):
        errors.append("dirty_targets must be a list")
    if not isinstance(path_leases.get("warnings"), list):
        errors.append("warnings must be a list")
    if not isinstance(path_leases.get("evidence_pointers"), list):
        errors.append("evidence_pointers must be a list")
    return sorted(dict.fromkeys(errors))


def validate_planned_operations(path_leases: dict[str, Any], operations: dict[str, Any]) -> list[str]:
    """Reject unowned writes, unsafe deletes, unowned renames, binary patches, lockfile violations, broad cleanup."""
    errors: list[str] = []
    if operations.get("schema_version") != CURRENT_SCHEMA_VERSION:
        errors.append(f"planned-operations.schema_version must be {CURRENT_SCHEMA_VERSION}")
    if operations.get("artifact_type") != "planned-operations":
        errors.append("planned-operations.artifact_type must be planned-operations")
    leases_by_task = {
        str(lease.get("task_id")): lease
        for lease in path_leases.get("leases", [])
        if isinstance(lease, dict) and lease.get("state") in {"active", "proposed", "released"}
    }
    raw_operations = operations.get("operations")
    if not isinstance(raw_operations, list):
        return errors + ["planned-operations.operations must be a list"]
    for index, operation in enumerate(raw_operations, start=1):
        label = f"operations[{index}]"
        if not isinstance(operation, dict):
            errors.append(f"{label} must be an object")
            continue
        task_id = str(operation.get("task_id") or "")
        lease = leases_by_task.get(task_id)
        if not lease:
            errors.append(f"{label}: no active lease for task {task_id}")
            continue
        owned_paths = [str(path) for path in lease.get("owned_paths", [])]
        for field in ["changed_paths", "created_paths", "deleted_paths", "binary_paths", "lockfile_paths"]:
            if field in operation and not isinstance(operation[field], list):
                errors.append(f"{label}.{field} must be a list")
        for field in ["changed_paths", "created_paths", "deleted_paths"]:
            for raw_path in operation.get(field, []) or []:
                try:
                    path = normalize_repo_path(str(raw_path))
                except LeaseValidationError as exc:
                    errors.append(f"{label}.{field}: {exc}")
                    continue
                if not path_is_owned(path, owned_paths):
                    errors.append(f"{label}.{field}: {path} is outside owned paths for {task_id}")
                if path in {".", "*", "**"}:
                    errors.append(f"{label}.{field}: broad cleanup path is rejected: {path}")
        for raw_path in operation.get("deleted_paths", []) or []:
            try:
                path = normalize_repo_path(str(raw_path))
            except LeaseValidationError:
                continue
            if not path_is_owned(path, owned_paths) or "delete" not in lease.get("allowed_operations", []):
                errors.append(f"{label}.deleted_paths: unsafe delete is rejected: {path}")
        for raw_path in operation.get("binary_paths", []) or []:
            errors.append(f"{label}.binary_paths: binary patch is rejected: {raw_path}")
        renames = operation.get("renames", []) or []
        if not isinstance(renames, list):
            errors.append(f"{label}.renames must be a list")
        else:
            for rename_index, rename in enumerate(renames, start=1):
                if not isinstance(rename, dict):
                    errors.append(f"{label}.renames[{rename_index}] must be an object")
                    continue
                for side in ["from", "to"]:
                    try:
                        path = normalize_repo_path(str(rename.get(side) or ""))
                    except LeaseValidationError as exc:
                        errors.append(f"{label}.renames[{rename_index}].{side}: {exc}")
                        continue
                    if not path_is_owned(path, owned_paths):
                        errors.append(f"{label}.renames[{rename_index}].{side}: unowned rename path is rejected: {path}")
        for raw_path in operation.get("lockfile_paths", []) or []:
            try:
                path = normalize_repo_path(str(raw_path))
            except LeaseValidationError as exc:
                errors.append(f"{label}.lockfile_paths: {exc}")
                continue
            if not is_lockfile_path(path):
                errors.append(f"{label}.lockfile_paths: {path} is not a known lockfile path")
            if not path_is_owned(path, owned_paths):
                errors.append(f"{label}.lockfile_paths: lockfile change outside owned paths is rejected: {path}")
            if not lease.get("contract_allows_lockfile"):
                errors.append(f"{label}.lockfile_paths: lockfile change requires explicit task contract validation: {path}")
        for raw_path in operation.get("broad_cleanup_paths", []) or []:
            errors.append(f"{label}.broad_cleanup_paths: broad cleanup is rejected: {raw_path}")
    return sorted(dict.fromkeys(errors))


def write_conflict_report(run_dir: Path, path_leases: dict[str, Any]) -> Path:
    """Write lease-conflict-report.md."""
    path = run_dir / "lease-conflict-report.md"
    lines = [
        metadata_comment("lease-conflict-report", str(path_leases.get("run_id", "")), str(path_leases.get("created_at", utc_now()))),
        f"# Patch Swarm Lease Conflict Report: {path_leases.get('run_id', '')}",
        "",
        "## Summary",
        f"- Conflicts: {len(path_leases.get('conflicts', []))}",
        f"- Dirty targets: {len(path_leases.get('dirty_targets', []))}",
        "",
        "## Conflicts",
    ]
    conflicts = path_leases.get("conflicts", [])
    if conflicts:
        for conflict in conflicts:
            lines.extend(
                [
                    f"- `{conflict.get('conflict_id')}` `{conflict.get('type')}`: {conflict.get('reason')}",
                    f"  - Tasks: {', '.join(conflict.get('task_ids', [])) or 'n/a'}",
                    f"  - Paths: {', '.join(conflict.get('paths', [])) or 'n/a'}",
                    f"  - Resolution: {conflict.get('resolution')}",
                ]
            )
    else:
        lines.append("- No conflicts in the valid lease artifact.")
    lines.extend(["", "## Dirty Targets"])
    for target in path_leases.get("dirty_targets", []) or []:
        lines.append(f"- `{target.get('path')}` for {', '.join(target.get('task_ids', []))}: {target.get('required_handling')}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def write_validation_report(run_dir: Path, validation: dict[str, Any]) -> Path:
    path = run_dir / "lease-validation-report.md"
    lines = [
        metadata_comment("lease-validation-report", str(validation.get("run_id", "")), utc_now()),
        "# Patch Swarm Lease Validation Report",
        "",
        "## Summary",
        f"- OK: {validation.get('ok')}",
        f"- Errors: {len(validation.get('errors', []))}",
        f"- Warnings: {len(validation.get('warnings', []))}",
        "",
        "## Errors",
        *([f"- {error}" for error in validation.get("errors", [])] or ["- None"]),
        "",
        "## Warnings",
        *([f"- {warning}" for warning in validation.get("warnings", [])] or ["- None"]),
        "",
        "## Evidence",
        "- `path-leases.json`",
        "- `lease-conflicts.json`",
        "- `planned-operations.json`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_workset_manifest_if_supported(run_dir: Path, path_leases: dict[str, Any], discovered_format: dict[str, Any] | None = None) -> Path:
    """Write workset-manifest.json or workset-compatibility.json."""
    workset_tasks = []
    for lease in path_leases.get("leases", []):
        if not isinstance(lease, dict):
            continue
        if lease.get("state") != "active" or lease.get("requires_manual_review"):
            continue
        workset_tasks.append(
            {
                "id": lease["task_id"],
                "task": f"Patch Swarm lease {lease['task_id']}",
                "write_paths": lease.get("owned_paths", []),
                "read_paths": lease.get("read_only_paths", []),
                "depends_on": lease.get("dependencies", []),
            }
        )
    compatibility = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "workset-compatibility",
        "run_id": path_leases.get("run_id"),
        "created_at": path_leases.get("created_at"),
        "provenance": provenance("patch-swarm leases", "workset-compatibility"),
        "cento_workset_check_supported": bool(cento_workset and workset_tasks),
        "workset_manifest_format": "cento.workset.v1" if cento_workset else None,
        "discovered_command": "cento workset check WORKSET --allow-creates --json" if cento_workset else "",
        "common_manifest_flag_supported": False,
        "reason": (
            "Generated Workset v1 manifest for automatable active leases only; guarded/manual leases stay in path-leases.json."
            if cento_workset and workset_tasks
            else "No compatible automatable Workset manifest subset discovered"
        ),
        "path_leases": "path-leases.json",
        "evidence_pointers": [],
    }
    compat_path = run_dir / "workset-compatibility.json"
    write_json(compat_path, compatibility)
    if cento_workset and workset_tasks:
        manifest = {
            "schema_version": "cento.workset.v1",
            "id": f"patch_swarm_{path_leases.get('run_id')}",
            "mode": "fast",
            "max_parallel": max(1, min(5, len(workset_tasks))),
            "tasks": workset_tasks,
        }
        manifest_path = run_dir / "workset-manifest.json"
        write_json(manifest_path, manifest)
        path_leases["workset_manifest"] = "workset-manifest.json"
        write_json(run_dir / "path-leases.json", path_leases)
        return manifest_path
    path_leases["workset_manifest"] = None
    write_json(run_dir / "path-leases.json", path_leases)
    return compat_path


def validate_workset_compatibility(run_dir: Path) -> dict[str, Any]:
    """Run or prepare cento workset check compatibility if possible."""
    manifest_path = run_dir / "workset-manifest.json"
    if not manifest_path.exists():
        return {
            "ok": True,
            "status": "skipped",
            "reason": "No workset-manifest.json generated; see workset-compatibility.json.",
        }
    if cento_workset is None:
        return {"ok": False, "status": "unavailable", "reason": "cento_workset import unavailable"}
    manifest = read_json(manifest_path)
    result = cento_workset.validate_workset(manifest, allow_missing_write_paths=True)
    command = ["cento", "workset", "check", rel(manifest_path), "--allow-creates", "--json"]
    return {
        "ok": result.get("status") == "passed",
        "status": result.get("status"),
        "command": command,
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
    }


def validate_run_directory(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "path-leases.json"
    payload = read_json(path)
    errors = validate_path_leases(payload)
    warnings = [str(item.get("message", item)) for item in payload.get("warnings", []) if isinstance(item, dict)]
    report = {
        "ok": not errors,
        "run_id": payload.get("run_id", ""),
        "run_dir": rel(run_dir),
        "path_leases": rel(path),
        "checked_artifacts": ["path-leases.json"],
        "errors": errors,
        "warnings": warnings,
        "workset_compatibility": validate_workset_compatibility(run_dir),
    }
    return report


def _fixture_split_plan(run_id: str, timestamp: str) -> dict[str, Any]:
    tasks = [
        {
            "task_id": "task-0001",
            "title": "Docs-only lease fixture A",
            "story": "As an operator, I need one docs-only fixture task.",
            "summary": "Write the first non-conflicting docs evidence file.",
            "lane": "docs-evidence",
            "state": "created",
            "risk_tier": "low",
            "human_handoff": False,
            "worker_profile": "docs-evidence-writer",
            "owned_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/docs-task-a.md"],
            "read_only_paths": ["docs/patch-swarm.md"],
            "dependencies": [],
            "acceptance_contract": ["Only the owned fixture docs file is changed."],
            "validation_commands": ["python3 -m json.tool workspace/runs/parallel-delivery/lease-fixture/path-leases.json >/dev/null"],
            "expected_artifacts": ["task-work/docs-task-a.md"],
            "integration_notes": ["Safe to run with other docs-only task."],
            "rejection_triggers": ["Touches unowned paths."],
            "evidence_pointers": [],
        },
        {
            "task_id": "task-0002",
            "title": "Docs-only lease fixture B",
            "story": "As an operator, I need a second docs-only fixture task.",
            "summary": "Write the second non-conflicting docs evidence file.",
            "lane": "docs-evidence",
            "state": "created",
            "risk_tier": "low",
            "human_handoff": False,
            "worker_profile": "docs-evidence-writer",
            "owned_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/docs-task-b.md"],
            "read_only_paths": ["docs/patch-swarm.md"],
            "dependencies": [],
            "acceptance_contract": ["Only the owned fixture docs file is changed."],
            "validation_commands": ["python3 -m json.tool workspace/runs/parallel-delivery/lease-fixture/path-leases.json >/dev/null"],
            "expected_artifacts": ["task-work/docs-task-b.md"],
            "integration_notes": ["Shares read-only context with task-0001."],
            "rejection_triggers": ["Touches unowned paths."],
            "evidence_pointers": [],
        },
        {
            "task_id": "task-0003",
            "title": "Dependency-gated validation fixture",
            "story": "As an operator, I need a task that waits for docs output.",
            "summary": "Validate evidence produced by task-0001.",
            "lane": "validator",
            "state": "created",
            "risk_tier": "medium",
            "human_handoff": False,
            "worker_profile": "test-writer",
            "owned_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/validation-task-0003.json"],
            "read_only_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/docs-task-a.md"],
            "dependencies": ["task-0001"],
            "acceptance_contract": ["Validation evidence references task-0001 output without editing it."],
            "validation_commands": ["python3 -m json.tool workspace/runs/parallel-delivery/lease-fixture/lease-validation.json >/dev/null"],
            "expected_artifacts": ["task-work/validation-task-0003.json"],
            "integration_notes": ["Runs after task-0001."],
            "rejection_triggers": ["Runs in the same parallel group as task-0001."],
            "evidence_pointers": [],
        },
        {
            "task_id": "task-0004",
            "title": "Guarded registry path fixture",
            "story": "As an operator, I need guarded registry writes to be high risk.",
            "summary": "Declare a guarded registry path and require manual review.",
            "lane": "coordinator",
            "state": "created",
            "risk_tier": "medium",
            "human_handoff": False,
            "worker_profile": "factory-planner",
            "owned_paths": ["data/tools.json"],
            "read_only_paths": ["docs/parallel-delivery/patch-swarm-planner.md"],
            "dependencies": [],
            "acceptance_contract": ["Registry edits are explicitly owned, high risk, manually reviewed, and minimal-hunk only."],
            "validation_commands": ["python3 -m json.tool data/tools.json >/dev/null"],
            "expected_artifacts": ["data/tools.json"],
            "integration_notes": ["Manual review gate required."],
            "rejection_triggers": ["Touches another registry path."],
            "evidence_pointers": [],
        },
        {
            "task_id": "task-0005",
            "title": "Explicit lockfile contract fixture",
            "story": "As an operator, I need lockfile writes to require dependency validation.",
            "summary": "Declare an explicit lockfile package dependency validation contract.",
            "lane": "builder",
            "state": "created",
            "risk_tier": "medium",
            "human_handoff": False,
            "worker_profile": "cli-builder",
            "owned_paths": ["package-lock.json"],
            "read_only_paths": ["docs/cento-build.md"],
            "dependencies": [],
            "acceptance_contract": ["Lockfile package dependency validation is explicitly required before integration."],
            "validation_commands": ["echo lockfile package dependency validation evidence"],
            "expected_artifacts": ["package-lock.json"],
            "integration_notes": ["Manual review gate required for lockfile changes."],
            "rejection_triggers": ["Lockfile change lacks validation evidence."],
            "evidence_pointers": [],
        },
    ]
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "split-plan",
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": provenance("write-fixture", "fixture"),
        "max_candidate_tasks": 5,
        "candidate_target": 5,
        "candidate_count": 5,
        "max_parallel_agents": 3,
        "planner_mode": "fixture",
        "planning_policy": {"read_many_write_few": True, "avoid_overlapping_owned_paths": True},
        "lanes": ["docs-evidence", "validator", "coordinator", "builder"],
        "tasks": tasks,
        "evidence_pointers": [],
    }


def _fixture_task_graph(split_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "task-graph",
        "run_id": split_plan["run_id"],
        "created_at": split_plan["created_at"],
        "updated_at": split_plan["updated_at"],
        "provenance": split_plan["provenance"],
        "nodes": [
            {
                "task_id": task["task_id"],
                "lane": task["lane"],
                "risk_tier": task["risk_tier"],
                "owned_paths": task["owned_paths"],
                "human_handoff": task["human_handoff"],
            }
            for task in split_plan["tasks"]
        ],
        "edges": [
            {
                "from": "task-0001",
                "to": "task-0003",
                "type": "depends_on",
                "reason": "task-0003 validates task-0001 output",
            }
        ],
        "topological_order": ["task-0001", "task-0002", "task-0003", "task-0004", "task-0005"],
        "parallel_groups": [],
        "max_parallel_agents": 3,
        "evidence_pointers": [],
    }


def _planned_operations(run_id: str, timestamp: str) -> dict[str, Any]:
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "planned-operations",
        "run_id": run_id,
        "created_at": timestamp,
        "provenance": provenance("write-fixture", "fixture"),
        "operations": [
            {
                "task_id": "task-0001",
                "changed_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/docs-task-a.md"],
                "created_paths": [],
                "deleted_paths": [],
                "renames": [],
                "binary_paths": [],
                "lockfile_paths": [],
            },
            {
                "task_id": "task-0002",
                "changed_paths": ["workspace/runs/parallel-delivery/lease-fixture/task-work/docs-task-b.md"],
                "created_paths": [],
                "deleted_paths": [],
                "renames": [],
                "binary_paths": [],
                "lockfile_paths": [],
            },
            {
                "task_id": "task-0004",
                "changed_paths": ["data/tools.json"],
                "created_paths": [],
                "deleted_paths": [],
                "renames": [],
                "binary_paths": [],
                "lockfile_paths": [],
            },
            {
                "task_id": "task-0005",
                "changed_paths": ["package-lock.json"],
                "created_paths": [],
                "deleted_paths": [],
                "renames": [],
                "binary_paths": [],
                "lockfile_paths": ["package-lock.json"],
            },
        ],
        "evidence_pointers": [],
    }


def _conflict_example(base: dict[str, Any], name: str) -> dict[str, Any]:
    payload = copy.deepcopy(base)
    payload["run_id"] = f"lease-fixture-{name}"
    payload["conflicts"] = []
    for lease in payload.get("leases", []):
        lease["lease_id"] = make_lease_id(payload["run_id"], lease["task_id"], lease["owned_paths"], lease["read_only_paths"])
    if name == "exact-overlap":
        payload["leases"][1]["owned_paths"] = list(payload["leases"][0]["owned_paths"])
        payload["leases"][1]["lease_id"] = make_lease_id(
            payload["run_id"], payload["leases"][1]["task_id"], payload["leases"][1]["owned_paths"], payload["leases"][1]["read_only_paths"]
        )
    elif name == "parent-child-overlap":
        payload["leases"][0]["owned_paths"] = ["workspace/runs/parallel-delivery/lease-fixture/conflict-parent"]
        payload["leases"][1]["owned_paths"] = ["workspace/runs/parallel-delivery/lease-fixture/conflict-parent/child.md"]
        for lease in payload["leases"][:2]:
            lease["lease_id"] = make_lease_id(payload["run_id"], lease["task_id"], lease["owned_paths"], lease["read_only_paths"])
    elif name == "protected-path":
        payload["leases"][0]["owned_paths"] = [".env.mcp"]
        payload["leases"][0]["protected_paths"] = [".env.mcp"]
    else:
        reasons = {
            "unsafe-delete": "unsafe delete outside owned paths is rejected",
            "unowned-rename": "unowned rename is rejected",
            "binary-patch": "binary patch metadata is rejected",
            "broad-cleanup": "broad cleanup path is rejected",
            "lockfile-outside-contract": "lockfile change outside explicit contract is rejected",
        }
        payload["conflicts"].append(
            _conflict(
                1,
                name.replace("-", "_"),
                ["task-0001"],
                ["docs/unowned.md"],
                reasons[name],
                resolution="fix planned operation metadata before integration",
            )
        )
    return payload


def build_lease_fixture(run_dir: Path, *, run_id: str, timestamp: str) -> dict[str, Any]:
    """Generate deterministic valid lease fixture plus conflict examples."""
    run_dir.mkdir(parents=True, exist_ok=True)
    request_text = "\n".join(
        [
            metadata_comment("request", run_id, timestamp),
            "# Patch Swarm Lease Fixture Request",
            "",
            "Generate deterministic path leases for docs-only tasks, dependency gates, guarded paths, lockfiles, and conflict examples.",
            "",
        ]
    )
    (run_dir / "request.md").write_text(request_text, encoding="utf-8")
    split_plan = _fixture_split_plan(run_id, timestamp)
    task_graph = _fixture_task_graph(split_plan)
    write_json(run_dir / "split-plan.json", split_plan)
    write_json(run_dir / "task-graph.json", task_graph)
    git_status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout
    leases = create_leases(split_plan, task_graph, git_status_text=git_status, timestamp=timestamp, command="write-fixture")
    write_json(run_dir / "path-leases.json", leases)
    write_workset_manifest_if_supported(run_dir, leases)
    validation = validate_run_directory(run_dir)
    write_json(run_dir / "lease-validation.json", validation)
    write_validation_report(run_dir, validation)
    write_json(run_dir / "planned-operations.json", _planned_operations(run_id, timestamp))

    conflict_examples = {}
    examples_dir = run_dir / "conflict-examples"
    examples_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "exact-overlap",
        "parent-child-overlap",
        "protected-path",
        "unsafe-delete",
        "unowned-rename",
        "binary-patch",
        "broad-cleanup",
        "lockfile-outside-contract",
    ]:
        example = _conflict_example(leases, name)
        conflict_examples[name] = {"path": f"conflict-examples/{name}.json", "conflicts": example.get("conflicts", [])}
        write_json(examples_dir / f"{name}.json", example)
    write_json(
        run_dir / "lease-conflicts.json",
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "artifact_type": "lease-conflicts",
            "run_id": run_id,
            "created_at": timestamp,
            "provenance": provenance("write-fixture", "fixture"),
            "conflict_examples": conflict_examples,
            "evidence_pointers": [],
        },
    )
    write_conflict_report(run_dir, leases)
    start_here = "\n".join(
        [
            metadata_comment("start-here", run_id, timestamp),
            f"# Patch Swarm Lease Run: {run_id}",
            "",
            "## What This Is",
            "A deterministic fixture for Patch Swarm path leasing and Workset compatibility.",
            "",
            "## Artifact Index",
            "- `split-plan.json`",
            "- `task-graph.json`",
            "- `path-leases.json`",
            "- `lease-conflicts.json`",
            "- `lease-validation.json`",
            "- `planned-operations.json`",
            "",
            "## Validation Result",
            f"`ok={validation['ok']}`",
            "",
            "## Next Operator Action",
            "Inspect `lease-validation-report.md` and conflict examples before enabling prompt emission.",
            "",
        ]
    )
    (run_dir / "start-here.md").write_text(start_here, encoding="utf-8")
    return {
        "ok": validation["ok"],
        "run_id": run_id,
        "run_dir": rel(run_dir),
        "path_leases": rel(run_dir / "path-leases.json"),
        "lease_validation": rel(run_dir / "lease-validation.json"),
        "conflict_examples": sorted(conflict_examples),
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


def create_from_files(
    run_dir: Path,
    split_plan_path: Path,
    task_graph_path: Path | None,
    *,
    timestamp: str | None = None,
    command: str = "patch-swarm leases",
) -> dict[str, Any]:
    split_plan = read_json(split_plan_path)
    task_graph = read_json(task_graph_path) if task_graph_path and task_graph_path.exists() else None
    git_status = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    ).stdout
    payload = create_leases(split_plan, task_graph, git_status_text=git_status, timestamp=timestamp or utc_now(), command=command)
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "path-leases.json", payload)
    write_workset_manifest_if_supported(run_dir, payload)
    write_json(run_dir / "lease-conflicts.json", {"schema_version": 1, "artifact_type": "lease-conflicts", "run_id": payload["run_id"], "created_at": payload["created_at"], "provenance": payload["provenance"], "conflicts": payload["conflicts"], "evidence_pointers": []})
    write_conflict_report(run_dir, payload)
    validation = validate_run_directory(run_dir)
    write_json(run_dir / "lease-validation.json", validation)
    write_validation_report(run_dir, validation)
    return {
        "ok": not validation["errors"],
        "run_id": payload["run_id"],
        "run_dir": rel(run_dir),
        "path_leases": rel(run_dir / "path-leases.json"),
        "errors": validation["errors"],
        "warnings": validation["warnings"],
    }


def print_policy() -> dict[str, Any]:
    """Return lease policy for CLI/test validation."""
    return lease_policy()


def add_write_fixture_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", default="lease-fixture")
    parser.add_argument("--fixed-timestamp", default="")
    parser.add_argument("--json", action="store_true")


def add_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--split-plan", default="")
    parser.add_argument("--task-graph", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--fixed-timestamp", default="")
    parser.add_argument("--json", action="store_true")


def add_validate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", default="")
    parser.add_argument("--path-leases", default="")
    parser.add_argument("--json", action="store_true")


def add_check_operations_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--operations", required=True)
    parser.add_argument("--json", action="store_true")


def run_write_fixture(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    timestamp = getattr(args, "fixed_timestamp", "") or utc_now()
    payload = build_lease_fixture(Path(args.run_dir), run_id=getattr(args, "run_id", "lease-fixture"), timestamp=timestamp)
    return payload, 0 if payload.get("ok") else 1


def run_create(args: argparse.Namespace, *, command: str = "patch-swarm leases") -> tuple[dict[str, Any], int]:
    timestamp = getattr(args, "fixed_timestamp", "") or utc_now()
    run_dir = Path(args.run_dir)
    if getattr(args, "fixture", False):
        payload = build_lease_fixture(run_dir, run_id=getattr(args, "run_id", "") or "lease-fixture", timestamp=timestamp)
        return payload, 0 if payload.get("ok") else 1
    split_plan = Path(getattr(args, "split_plan", "") or run_dir / "split-plan.json")
    task_graph_value = getattr(args, "task_graph", "") or str(run_dir / "task-graph.json")
    task_graph = Path(task_graph_value) if task_graph_value else None
    payload = create_from_files(run_dir, split_plan, task_graph, timestamp=timestamp, command=command)
    return payload, 0 if payload.get("ok") else 1


def run_validate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if getattr(args, "path_leases", ""):
        path = Path(args.path_leases)
        payload = read_json(path)
        errors = validate_path_leases(payload)
        result = {
            "ok": not errors,
            "run_id": payload.get("run_id", ""),
            "path_leases": rel(path),
            "checked_artifacts": [rel(path)],
            "errors": errors,
            "warnings": [],
        }
        return result, 0 if result["ok"] else 1
    run_dir = Path(getattr(args, "run_dir", "") or ".")
    result = validate_run_directory(run_dir)
    return result, 0 if result["ok"] else 1


def run_check_operations(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_dir = Path(args.run_dir)
    path_leases = read_json(run_dir / "path-leases.json")
    operations = read_json(Path(args.operations))
    errors = validate_planned_operations(path_leases, operations)
    payload = {
        "ok": not errors,
        "run_id": path_leases.get("run_id", ""),
        "run_dir": rel(run_dir),
        "operations": rel(Path(args.operations)),
        "errors": errors,
        "warnings": [],
    }
    return payload, 0 if payload["ok"] else 1


def print_payload(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(stable_json_dumps(payload), end="")
    else:
        print("ok" if payload.get("ok", True) else "failed")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and validate Patch Swarm path leases.")
    sub = parser.add_subparsers(dest="command", required=True)

    write_fixture = sub.add_parser("write-fixture", help="Write a deterministic lease fixture run.")
    add_write_fixture_args(write_fixture)

    create = sub.add_parser("create", help="Create path-leases.json from split-plan/task-graph.")
    add_create_args(create)

    validate = sub.add_parser("validate", help="Validate a path-leases.json artifact or run directory.")
    add_validate_args(validate)

    check_operations = sub.add_parser("check-operations", help="Validate planned patch operation metadata against leases.")
    add_check_operations_args(check_operations)

    policy = sub.add_parser("print-policy", help="Print Patch Swarm lease policy.")
    policy.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "write-fixture":
            payload, code = run_write_fixture(args)
        elif args.command == "create":
            payload, code = run_create(args)
        elif args.command == "validate":
            payload, code = run_validate(args)
        elif args.command == "check-operations":
            payload, code = run_check_operations(args)
        elif args.command == "print-policy":
            payload, code = print_policy(), 0
        else:  # pragma: no cover
            parser.error(f"unknown command: {args.command}")
        print_payload(payload, as_json=bool(getattr(args, "json", False)))
        return code
    except LeaseValidationError as exc:
        payload = {"ok": False, "errors": [str(exc)], "warnings": []}
        print_payload(payload, as_json=bool(getattr(args, "json", False)))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
