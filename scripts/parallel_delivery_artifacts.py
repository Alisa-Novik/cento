#!/usr/bin/env python3
"""Patch Swarm / Parallel Delivery artifact schema helper.

This module defines the durable artifact contract for Patch Swarm runs. It is a
schema and fixture helper only; it does not plan work, dispatch workers, apply
patches, or mutate Taskstream state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CURRENT_SCHEMA_VERSION = 1
PRODUCER = "cento.parallel-delivery.artifacts"

ARTIFACT_TYPES = {
    "run": "run.json",
    "request": "request.md",
    "context-pack": "context-pack.json",
    "split-plan": "split-plan.json",
    "task-graph": "task-graph.json",
    "path-leases": "path-leases.json",
    "worker-prompts-manifest": "worker-prompts/manifest.json",
    "worker-ledger": "worker-ledger.jsonl",
    "patch-bundles-manifest": "patch-bundles/manifest.json",
    "integration-plan": "integration-plan.json",
    "integration-receipt": "integration-receipt.json",
    "validation": "validation.json",
    "validation-report": "validation-report.md",
    "release-candidate": "release-candidate.json",
    "release-notes": "release-notes.md",
    "start-here": "start-here.md",
}

RUN_STATES = [
    "request_received",
    "run_created",
    "context_packed",
    "split_planned",
    "task_graph_ready",
    "paths_leased",
    "prompts_emitted",
    "workers_started",
    "patches_collected",
    "validation_started",
    "validation_passed",
    "validation_failed",
    "integration_planned",
    "integration_started",
    "integration_completed",
    "rc_built",
    "rc_validated",
    "completed",
    "failed",
    "aborted",
]

TASK_STATES = [
    "created",
    "context_ready",
    "leased",
    "prompt_emitted",
    "dispatched",
    "patch_submitted",
    "validation_running",
    "validation_passed",
    "validation_failed",
    "queued_for_integration",
    "integrated",
    "rejected",
    "superseded",
    "aborted",
]

LEASE_STATES = ["proposed", "active", "released", "conflict", "expired"]

RUN_STATE_TRANSITIONS = {
    "request_received": ["run_created", "failed", "aborted"],
    "run_created": ["context_packed", "split_planned", "failed", "aborted"],
    "context_packed": ["split_planned", "failed", "aborted"],
    "split_planned": ["task_graph_ready", "paths_leased", "failed", "aborted"],
    "task_graph_ready": ["paths_leased", "failed", "aborted"],
    "paths_leased": ["prompts_emitted", "failed", "aborted"],
    "prompts_emitted": ["workers_started", "patches_collected", "failed", "aborted"],
    "workers_started": ["patches_collected", "validation_started", "failed", "aborted"],
    "patches_collected": ["validation_started", "failed", "aborted"],
    "validation_started": ["validation_passed", "validation_failed", "failed", "aborted"],
    "validation_failed": ["integration_planned", "failed", "aborted"],
    "validation_passed": ["integration_planned", "failed", "aborted"],
    "integration_planned": ["integration_started", "failed", "aborted"],
    "integration_started": ["integration_completed", "failed", "aborted"],
    "integration_completed": ["rc_built", "failed", "aborted"],
    "rc_built": ["rc_validated", "failed", "aborted"],
    "rc_validated": ["completed", "failed", "aborted"],
    "completed": [],
    "failed": [],
    "aborted": [],
}

TASK_STATE_TRANSITIONS = {
    "created": ["context_ready", "leased", "aborted", "superseded"],
    "context_ready": ["leased", "aborted", "superseded"],
    "leased": ["prompt_emitted", "aborted", "superseded"],
    "prompt_emitted": ["dispatched", "patch_submitted", "aborted", "superseded"],
    "dispatched": ["patch_submitted", "validation_running", "aborted"],
    "patch_submitted": ["validation_running", "validation_failed", "aborted"],
    "validation_running": ["validation_passed", "validation_failed", "rejected", "aborted"],
    "validation_passed": ["queued_for_integration", "rejected", "aborted"],
    "validation_failed": ["rejected", "superseded", "aborted"],
    "queued_for_integration": ["integrated", "rejected", "aborted"],
    "integrated": [],
    "rejected": [],
    "superseded": [],
    "aborted": [],
}

EDGE_TYPES = ["depends_on", "blocks", "shares_context", "conflicts_with"]
WORKER_LEDGER_EVENT_TYPES = [
    "prompt_emitted",
    "dispatch_dry_run",
    "worker_started",
    "patch_submitted",
    "validation_started",
    "validation_completed",
    "integration_queued",
    "integrated",
    "rejected",
    "operator_note",
]
INTEGRATION_STRATEGIES = ["sequential", "dependency-order"]
INTEGRATION_FINAL_STATES = ["integration_completed", "integration_failed", "integration_aborted"]
VALIDATION_OVERALL_STATES = ["passed", "failed", "partial"]
RELEASE_CANDIDATE_STATES = ["rc_built", "rc_validated", "rc_failed"]
MARKDOWN_PREFIX = "<!-- cento-artifact:"
ISO_Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

COMMON_JSON_FIELDS = [
    "schema_version",
    "artifact_type",
    "run_id",
    "created_at",
    "provenance",
    "evidence_pointers",
]

REQUIRED_JSON_FIELDS = {
    "run": [
        *COMMON_JSON_FIELDS,
        "request_title",
        "state",
        "updated_at",
        "artifact_paths",
        "counts",
    ],
    "context-pack": [
        *COMMON_JSON_FIELDS,
        "request_ref",
        "repo_context",
        "source_refs",
        "constraints",
    ],
    "split-plan": [
        *COMMON_JSON_FIELDS,
        "max_candidate_tasks",
        "tasks",
    ],
    "task-graph": [
        *COMMON_JSON_FIELDS,
        "nodes",
        "edges",
    ],
    "path-leases": [
        *COMMON_JSON_FIELDS,
        "leases",
        "conflicts",
    ],
    "worker-prompts-manifest": [
        *COMMON_JSON_FIELDS,
        "prompts",
    ],
    "patch-bundles-manifest": [
        *COMMON_JSON_FIELDS,
        "bundles",
    ],
    "patch-bundle": [
        *COMMON_JSON_FIELDS,
        "task_id",
        "bundle_id",
        "base_ref",
        "changed_paths",
        "claimed_paths",
        "diff_path",
        "summary",
        "tests_run",
        "requires_manual_review",
    ],
    "integration-plan": [
        *COMMON_JSON_FIELDS,
        "strategy",
        "queue",
        "rejected",
    ],
    "integration-receipt": [
        *COMMON_JSON_FIELDS,
        "strategy",
        "started_at",
        "completed_at",
        "integrated",
        "rejected",
        "conflicts",
        "final_state",
    ],
    "validation": [
        *COMMON_JSON_FIELDS,
        "schema_checks",
        "command_checks",
        "task_checks",
        "overall",
    ],
    "release-candidate": [
        *COMMON_JSON_FIELDS,
        "rc_id",
        "source_integration_receipt",
        "included_tasks",
        "included_bundles",
        "validation_ref",
        "state",
    ],
}

REQUIRED_MD_SECTIONS = {
    "validation-report": [
        "# Patch Swarm Validation Report",
        "## Summary",
        "## Schema Checks",
        "## Command Checks",
        "## Failures",
        "## Evidence",
    ],
    "release-notes": [
        "# Release Notes",
        "## Request",
        "## Integrated Patches",
        "## Validation",
        "## Evidence",
    ],
    "start-here": [
        "# Patch Swarm Run:",
        "## What This Is",
        "## Artifact Index",
        "## Validation Result",
        "## Release Candidate",
        "## Next Operator Action",
    ],
}


class ArtifactValidationError(Exception):
    """Raised when a Patch Swarm artifact fails schema validation."""


def utc_now() -> str:
    """Return current UTC timestamp as ISO-8601 with trailing Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: dict) -> str:
    """Return deterministic JSON: sorted keys, two-space indent, trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json_artifact(path: Path, payload: dict) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def read_json_artifact(path: Path) -> dict:
    """Read JSON artifact and return object."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ArtifactValidationError(f"{path}: expected JSON object")
    return payload


def sha256_file(path: Path) -> str:
    """Return sha256 digest for artifact references."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provenance(command: str, source: str = "fixture") -> dict[str, Any]:
    return {
        "command": command,
        "notes": [],
        "producer": PRODUCER,
        "repo": "cento",
        "source": source,
    }


def _common(artifact_type: str, run_id: str, timestamp: str, command: str = "schema-fixture") -> dict[str, Any]:
    return {
        "artifact_type": artifact_type,
        "created_at": timestamp,
        "evidence_pointers": [],
        "provenance": _provenance(command),
        "run_id": run_id,
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


def _jsonl_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _require_fields(payload: dict[str, Any], fields: list[str], artifact: str) -> list[str]:
    return [f"{artifact}: missing required field {field}" for field in fields if field not in payload]


def _validate_iso_z(value: Any, field: str) -> list[str]:
    if not isinstance(value, str) or not ISO_Z_RE.match(value):
        return [f"{field} must be ISO-8601 UTC with trailing Z"]
    return []


def _validate_provenance(value: Any, artifact: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{artifact}.provenance must be an object"]
    for field in ["producer", "command", "source", "repo", "notes"]:
        if field not in value:
            errors.append(f"{artifact}.provenance missing {field}")
    for field in ["producer", "command", "source", "repo"]:
        if field in value and not isinstance(value[field], str):
            errors.append(f"{artifact}.provenance.{field} must be a string")
    if "notes" in value and not isinstance(value["notes"], list):
        errors.append(f"{artifact}.provenance.notes must be a list")
    return errors


def _validate_evidence_pointers(value: Any, artifact: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{artifact}.evidence_pointers must be a list"]
    for index, pointer in enumerate(value, start=1):
        label = f"{artifact}.evidence_pointers[{index}]"
        if not isinstance(pointer, dict):
            errors.append(f"{label} must be an object")
            continue
        if "path" in pointer:
            errors.extend(f"{label}.path: {error}" for error in validate_relative_artifact_path(str(pointer["path"])))
        if "sha256" in pointer and not re.fullmatch(r"[0-9a-f]{64}", str(pointer["sha256"])):
            errors.append(f"{label}.sha256 must be lowercase hex sha256")
    return errors


def validate_schema_version(payload: dict, *, allow_future: bool = False) -> list[str]:
    """Validate schema_version compatibility."""
    if "schema_version" not in payload:
        return ["schema_version missing"]
    version = payload.get("schema_version")
    if not isinstance(version, int):
        return ["schema_version must be an integer"]
    if version < CURRENT_SCHEMA_VERSION:
        return [f"schema_version {version} is older than supported version {CURRENT_SCHEMA_VERSION}"]
    if version > CURRENT_SCHEMA_VERSION and not allow_future:
        return [f"schema_version {version} is newer than supported version {CURRENT_SCHEMA_VERSION}"]
    return []


def validate_common_json_artifact(payload: dict, artifact_type: str) -> list[str]:
    """Validate common JSON fields."""
    errors = _require_fields(payload, COMMON_JSON_FIELDS, artifact_type)
    errors.extend(validate_schema_version(payload))
    if payload.get("artifact_type") != artifact_type:
        errors.append(f"artifact_type must be {artifact_type}")
    if not isinstance(payload.get("run_id"), str) or not payload.get("run_id"):
        errors.append("run_id must be a non-empty string")
    if "created_at" in payload:
        errors.extend(_validate_iso_z(payload["created_at"], "created_at"))
    if "updated_at" in payload:
        errors.extend(_validate_iso_z(payload["updated_at"], "updated_at"))
    if "provenance" in payload:
        errors.extend(_validate_provenance(payload["provenance"], artifact_type))
    if "evidence_pointers" in payload:
        errors.extend(_validate_evidence_pointers(payload["evidence_pointers"], artifact_type))
    return errors


def validate_relative_artifact_path(value: str) -> list[str]:
    """Reject absolute paths, '..', .env.mcp, and suspicious secret paths."""
    errors: list[str] = []
    if not value:
        return ["path must be non-empty"]
    path = Path(value)
    lowered = value.lower()
    parts = [part.lower() for part in path.parts]
    if path.is_absolute() or value.startswith("~"):
        errors.append(f"{value}: absolute or home-relative paths are not allowed")
    if ".." in path.parts:
        errors.append(f"{value}: parent traversal is not allowed")
    if ".env.mcp" in parts or lowered.endswith("/.env.mcp"):
        errors.append(f"{value}: .env.mcp is not allowed")
    secret_markers = [
        ".env",
        ".ssh",
        "secret",
        "secrets",
        "token",
        "credential",
        "credentials",
        "openai_api_key",
        "api_key",
        "private_key",
        "id_rsa",
    ]
    if any(marker in lowered for marker in secret_markers):
        errors.append(f"{value}: secret-like artifact paths are not allowed")
    return errors


def _validate_path_list(value: Any, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str):
            errors.append(f"{field}[{index}] must be a string")
            continue
        errors.extend(f"{field}[{index}]: {error}" for error in validate_relative_artifact_path(item))
    return errors


def validate_markdown_artifact(path: Path, artifact_type: str, run_id: str) -> list[str]:
    """Validate markdown/html metadata comment and required body."""
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return [f"{path}: missing markdown artifact"]
    if not text.strip():
        return [f"{path}: markdown artifact is empty"]
    first_line = text.splitlines()[0] if text.splitlines() else ""
    if not first_line.startswith(MARKDOWN_PREFIX) or not first_line.endswith("-->"):
        return [f"{path}: first line must be a cento-artifact metadata comment"]
    raw = first_line.removeprefix(MARKDOWN_PREFIX).removesuffix("-->").strip()
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"{path}: metadata JSON is invalid: {exc.msg}"]
    errors.extend(validate_schema_version(metadata))
    if metadata.get("artifact_type") != artifact_type:
        errors.append(f"{path}: artifact_type must be {artifact_type}")
    if metadata.get("run_id") != run_id:
        errors.append(f"{path}: run_id must be {run_id}")
    errors.extend(_validate_iso_z(metadata.get("created_at"), f"{path}: created_at"))
    body = "\n".join(text.splitlines()[1:]).strip()
    if not body:
        errors.append(f"{path}: body must be non-empty")
    for section in REQUIRED_MD_SECTIONS.get(artifact_type, []):
        if section not in text:
            errors.append(f"{path}: missing required section {section}")
    return errors


def validate_run_state_transition(old: str, new: str) -> None:
    """Validate run state transition."""
    if old not in RUN_STATE_TRANSITIONS:
        raise ArtifactValidationError(f"invalid run state: {old}")
    if new not in RUN_STATES:
        raise ArtifactValidationError(f"invalid run state: {new}")
    if new not in RUN_STATE_TRANSITIONS[old]:
        raise ArtifactValidationError(f"invalid run state transition: {old} -> {new}")


def validate_task_state_transition(old: str, new: str) -> None:
    """Validate task state transition."""
    if old not in TASK_STATE_TRANSITIONS:
        raise ArtifactValidationError(f"invalid task state: {old}")
    if new not in TASK_STATES:
        raise ArtifactValidationError(f"invalid task state: {new}")
    if new not in TASK_STATE_TRANSITIONS[old]:
        raise ArtifactValidationError(f"invalid task state transition: {old} -> {new}")


def validate_run_artifact(payload: dict) -> list[str]:
    """Validate run.json."""
    errors = validate_common_json_artifact(payload, "run")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["run"], "run"))
    if payload.get("state") not in RUN_STATES:
        errors.append("run.state must be a known run state")
    if not isinstance(payload.get("request_title"), str) or not payload.get("request_title"):
        errors.append("run.request_title must be a non-empty string")
    if not isinstance(payload.get("artifact_paths"), dict):
        errors.append("run.artifact_paths must be an object")
    else:
        for key, value in payload["artifact_paths"].items():
            errors.extend(f"run.artifact_paths.{key}: {error}" for error in validate_relative_artifact_path(str(value)))
    if not isinstance(payload.get("counts"), dict):
        errors.append("run.counts must be an object")
    return errors


def validate_context_pack(payload: dict) -> list[str]:
    """Validate context-pack.json."""
    errors = validate_common_json_artifact(payload, "context-pack")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["context-pack"], "context-pack"))
    if "request_ref" in payload:
        errors.extend(f"context-pack.request_ref: {error}" for error in validate_relative_artifact_path(str(payload["request_ref"])))
    repo_context = payload.get("repo_context")
    if not isinstance(repo_context, dict):
        errors.append("context-pack.repo_context must be an object")
    else:
        for required in ["repo_name", "relevant_surfaces", "dirty_work_policy"]:
            if required not in repo_context:
                errors.append(f"context-pack.repo_context missing {required}")
    source_refs = payload.get("source_refs")
    if not isinstance(source_refs, list):
        errors.append("context-pack.source_refs must be a list")
    else:
        for index, ref in enumerate(source_refs, start=1):
            if isinstance(ref, dict) and "path" in ref:
                errors.extend(f"context-pack.source_refs[{index}].path: {error}" for error in validate_relative_artifact_path(str(ref["path"])))
    text = json.dumps(payload, sort_keys=True).lower()
    for forbidden in [".env.mcp", "openai_api_key", "api key", "secret value"]:
        if forbidden in text:
            errors.append(f"context-pack must not include {forbidden}")
    return errors


def validate_split_plan(payload: dict) -> list[str]:
    """Validate split-plan.json."""
    errors = validate_common_json_artifact(payload, "split-plan")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["split-plan"], "split-plan"))
    max_tasks = payload.get("max_candidate_tasks")
    if not isinstance(max_tasks, int) or not 1 <= max_tasks <= 100:
        errors.append("split-plan.max_candidate_tasks must be between 1 and 100")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("split-plan.tasks must be a non-empty list")
        return errors
    if isinstance(max_tasks, int) and len(tasks) > max_tasks:
        errors.append("split-plan.tasks exceeds max_candidate_tasks")
    seen: set[str] = set()
    for index, task in enumerate(tasks, start=1):
        label = f"split-plan.tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in [
            "task_id",
            "title",
            "summary",
            "state",
            "acceptance_contract",
            "validation_commands",
            "owned_paths",
            "read_only_paths",
        ]:
            if field not in task:
                errors.append(f"{label} missing {field}")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{label}.task_id must be a non-empty string")
        elif task_id in seen:
            errors.append(f"{label}.task_id duplicates {task_id}")
        else:
            seen.add(task_id)
        if task.get("state") not in TASK_STATES:
            errors.append(f"{label}.state must be a known task state")
        for field in ["acceptance_contract", "validation_commands"]:
            if field in task and not isinstance(task[field], list):
                errors.append(f"{label}.{field} must be a list")
        errors.extend(_validate_path_list(task.get("owned_paths"), f"{label}.owned_paths"))
        errors.extend(_validate_path_list(task.get("read_only_paths"), f"{label}.read_only_paths"))
    return errors


def _has_depends_on_cycle(nodes: set[str], edges: list[dict[str, Any]]) -> bool:
    graph = {node: [] for node in nodes}
    for edge in edges:
        if edge.get("type") == "depends_on":
            graph.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(nodes))


def validate_task_graph(payload: dict) -> list[str]:
    """Validate task-graph.json."""
    errors = validate_common_json_artifact(payload, "task-graph")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["task-graph"], "task-graph"))
    nodes_value = payload.get("nodes")
    edges_value = payload.get("edges")
    nodes: set[str] = set()
    if not isinstance(nodes_value, list) or not nodes_value:
        errors.append("task-graph.nodes must be a non-empty list")
    else:
        for index, node in enumerate(nodes_value, start=1):
            if not isinstance(node, dict) or not isinstance(node.get("task_id"), str) or not node.get("task_id"):
                errors.append(f"task-graph.nodes[{index}] must include task_id")
            else:
                nodes.add(node["task_id"])
    if not isinstance(edges_value, list):
        errors.append("task-graph.edges must be a list")
        return errors
    for index, edge in enumerate(edges_value, start=1):
        label = f"task-graph.edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ["from", "to", "type"]:
            if field not in edge:
                errors.append(f"{label} missing {field}")
        if edge.get("type") not in EDGE_TYPES:
            errors.append(f"{label}.type must be one of {', '.join(EDGE_TYPES)}")
        for field in ["from", "to"]:
            if field in edge and edge[field] not in nodes:
                errors.append(f"{label}.{field} references unknown task {edge[field]}")
    if _has_depends_on_cycle(nodes, [edge for edge in edges_value if isinstance(edge, dict)]):
        errors.append("task-graph depends_on edges must be acyclic")
    return errors


def validate_path_leases(payload: dict) -> list[str]:
    """Validate path-leases.json."""
    errors = validate_common_json_artifact(payload, "path-leases")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["path-leases"], "path-leases"))
    leases = payload.get("leases")
    if not isinstance(leases, list):
        return errors + ["path-leases.leases must be a list"]
    active_owners: dict[str, str] = {}
    for index, lease in enumerate(leases, start=1):
        label = f"path-leases.leases[{index}]"
        if not isinstance(lease, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ["lease_id", "task_id", "state", "owned_paths", "read_only_paths", "created_at"]:
            if field not in lease:
                errors.append(f"{label} missing {field}")
        if lease.get("state") not in LEASE_STATES:
            errors.append(f"{label}.state must be a known lease state")
        errors.extend(_validate_iso_z(lease.get("created_at"), f"{label}.created_at"))
        if lease.get("expires_at"):
            errors.extend(_validate_iso_z(lease.get("expires_at"), f"{label}.expires_at"))
        errors.extend(_validate_path_list(lease.get("owned_paths"), f"{label}.owned_paths"))
        errors.extend(_validate_path_list(lease.get("read_only_paths"), f"{label}.read_only_paths"))
        if lease.get("state") == "active" and isinstance(lease.get("owned_paths"), list):
            for owned_path in lease["owned_paths"]:
                if owned_path in active_owners:
                    errors.append(
                        f"path-leases active overlap: {owned_path} owned by {active_owners[owned_path]} and {lease.get('lease_id')}"
                    )
                else:
                    active_owners[owned_path] = str(lease.get("lease_id"))
    if not isinstance(payload.get("conflicts"), list):
        errors.append("path-leases.conflicts must be a list")
    return errors


def _load_leased_paths(run_dir: Path) -> dict[str, set[str]]:
    try:
        leases_payload = read_json_artifact(run_dir / "path-leases.json")
    except (FileNotFoundError, json.JSONDecodeError, ArtifactValidationError):
        return {}
    leased: dict[str, set[str]] = {}
    for lease in leases_payload.get("leases", []):
        if isinstance(lease, dict) and lease.get("state") in {"active", "released"}:
            leased.setdefault(str(lease.get("task_id")), set()).update(str(path) for path in lease.get("owned_paths", []))
    return leased


def validate_worker_prompts(run_dir: Path) -> list[str]:
    """Validate worker-prompts directory and manifest."""
    errors: list[str] = []
    manifest_path = run_dir / ARTIFACT_TYPES["worker-prompts-manifest"]
    try:
        manifest = read_json_artifact(manifest_path)
    except FileNotFoundError:
        return [f"{manifest_path}: missing worker prompts manifest"]
    except (json.JSONDecodeError, ArtifactValidationError) as exc:
        return [f"{manifest_path}: {exc}"]
    errors.extend(validate_common_json_artifact(manifest, "worker-prompts-manifest"))
    errors.extend(_require_fields(manifest, REQUIRED_JSON_FIELDS["worker-prompts-manifest"], "worker-prompts-manifest"))
    prompts = manifest.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        return errors + ["worker-prompts-manifest.prompts must be a non-empty list"]
    for index, item in enumerate(prompts, start=1):
        label = f"worker-prompts-manifest.prompts[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ["task_id", "path", "sha256", "created_at"]:
            if field not in item:
                errors.append(f"{label} missing {field}")
        path_value = str(item.get("path", ""))
        errors.extend(f"{label}.path: {error}" for error in validate_relative_artifact_path(path_value))
        if not path_value.startswith("worker-prompts/"):
            errors.append(f"{label}.path must live under worker-prompts/")
        prompt_path = run_dir / path_value
        if prompt_path.exists():
            digest = sha256_file(prompt_path)
            if item.get("sha256") != digest:
                errors.append(f"{label}.sha256 does not match {path_value}")
            errors.extend(validate_markdown_artifact(prompt_path, "worker-prompt", str(manifest.get("run_id"))))
        else:
            errors.append(f"{label}.path missing file {path_value}")
        errors.extend(_validate_iso_z(item.get("created_at"), f"{label}.created_at"))
    return errors


def validate_worker_ledger(path: Path) -> list[str]:
    """Validate worker-ledger.jsonl with line-numbered failures."""
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [f"{path}: missing worker ledger"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}: line {line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            errors.append(f"{path}: line {line_number}: event must be an object")
            continue
        for field in ["schema_version", "artifact_type", "event_id", "run_id", "event_type", "created_at", "actor", "provenance", "details"]:
            if field not in event:
                errors.append(f"{path}: line {line_number}: missing {field}")
        errors.extend(f"{path}: line {line_number}: {error}" for error in validate_schema_version(event))
        if event.get("artifact_type") != "worker-ledger-event":
            errors.append(f"{path}: line {line_number}: artifact_type must be worker-ledger-event")
        if event.get("event_type") not in WORKER_LEDGER_EVENT_TYPES:
            errors.append(f"{path}: line {line_number}: unknown event_type {event.get('event_type')}")
        errors.extend(f"{path}: line {line_number}: {error}" for error in _validate_iso_z(event.get("created_at"), "created_at"))
    return errors


def _validate_patch_bundle_payload(payload: dict, leased_paths_by_task: dict[str, set[str]]) -> list[str]:
    errors = validate_common_json_artifact(payload, "patch-bundle")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["patch-bundle"], "patch-bundle"))
    task_id = str(payload.get("task_id", ""))
    changed_paths = payload.get("changed_paths")
    claimed_paths = payload.get("claimed_paths")
    errors.extend(_validate_path_list(changed_paths, "patch-bundle.changed_paths"))
    errors.extend(_validate_path_list(claimed_paths, "patch-bundle.claimed_paths"))
    if isinstance(changed_paths, list) and isinstance(claimed_paths, list):
        changed = {str(path) for path in changed_paths}
        claimed = {str(path) for path in claimed_paths}
        outside_claims = sorted(changed - claimed)
        if outside_claims:
            errors.append(f"patch-bundle.changed_paths outside claimed_paths: {', '.join(outside_claims)}")
        leased = leased_paths_by_task.get(task_id, set())
        outside_leases = sorted(changed - leased)
        if leased and outside_leases:
            errors.append(f"patch-bundle.changed_paths outside leased paths: {', '.join(outside_leases)}")
        if not leased:
            errors.append(f"patch-bundle task {task_id} has no leased paths")
    diff_path = str(payload.get("diff_path", ""))
    errors.extend(f"patch-bundle.diff_path: {error}" for error in validate_relative_artifact_path(diff_path))
    if "/" in diff_path or diff_path.startswith("patch-bundles/"):
        errors.append("patch-bundle.diff_path must be relative to patch-bundles/")
    if not isinstance(payload.get("tests_run"), list):
        errors.append("patch-bundle.tests_run must be a list")
    if not isinstance(payload.get("requires_manual_review"), bool):
        errors.append("patch-bundle.requires_manual_review must be a boolean")
    return errors


def validate_patch_bundles(run_dir: Path) -> list[str]:
    """Validate patch-bundles directory and manifest."""
    errors: list[str] = []
    manifest_path = run_dir / ARTIFACT_TYPES["patch-bundles-manifest"]
    try:
        manifest = read_json_artifact(manifest_path)
    except FileNotFoundError:
        return [f"{manifest_path}: missing patch bundles manifest"]
    except (json.JSONDecodeError, ArtifactValidationError) as exc:
        return [f"{manifest_path}: {exc}"]
    errors.extend(validate_common_json_artifact(manifest, "patch-bundles-manifest"))
    errors.extend(_require_fields(manifest, REQUIRED_JSON_FIELDS["patch-bundles-manifest"], "patch-bundles-manifest"))
    bundles = manifest.get("bundles")
    if not isinstance(bundles, list) or not bundles:
        return errors + ["patch-bundles-manifest.bundles must be a non-empty list"]
    leased_paths_by_task = _load_leased_paths(run_dir)
    for index, item in enumerate(bundles, start=1):
        label = f"patch-bundles-manifest.bundles[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ["task_id", "path", "sha256", "diff_path", "created_at"]:
            if field not in item:
                errors.append(f"{label} missing {field}")
        path_value = str(item.get("path", ""))
        errors.extend(f"{label}.path: {error}" for error in validate_relative_artifact_path(path_value))
        if not path_value.startswith("patch-bundles/"):
            errors.append(f"{label}.path must live under patch-bundles/")
        bundle_path = run_dir / path_value
        if bundle_path.exists():
            digest = sha256_file(bundle_path)
            if item.get("sha256") != digest:
                errors.append(f"{label}.sha256 does not match {path_value}")
            try:
                bundle = read_json_artifact(bundle_path)
                errors.extend(_validate_patch_bundle_payload(bundle, leased_paths_by_task))
                diff_path = run_dir / "patch-bundles" / str(bundle.get("diff_path", ""))
                if not diff_path.exists():
                    errors.append(f"{bundle_path}: diff_path missing {bundle.get('diff_path')}")
            except (json.JSONDecodeError, ArtifactValidationError) as exc:
                errors.append(f"{bundle_path}: {exc}")
        else:
            errors.append(f"{label}.path missing file {path_value}")
    return errors


def validate_integration_plan(payload: dict) -> list[str]:
    """Validate integration-plan.json."""
    errors = validate_common_json_artifact(payload, "integration-plan")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["integration-plan"], "integration-plan"))
    if payload.get("strategy") not in INTEGRATION_STRATEGIES:
        errors.append("integration-plan.strategy must be sequential or dependency-order")
    queue = payload.get("queue")
    if not isinstance(queue, list):
        return errors + ["integration-plan.queue must be a list"]
    seen_orders: set[int] = set()
    for index, item in enumerate(queue, start=1):
        label = f"integration-plan.queue[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in ["order", "task_id", "bundle_id", "reason", "validation_ref"]:
            if field not in item:
                errors.append(f"{label} missing {field}")
        if isinstance(item.get("order"), int):
            if item["order"] in seen_orders:
                errors.append(f"{label}.order duplicates {item['order']}")
            seen_orders.add(item["order"])
        else:
            errors.append(f"{label}.order must be an integer")
        if "validation_ref" in item:
            errors.extend(f"{label}.validation_ref: {error}" for error in validate_relative_artifact_path(str(item["validation_ref"])))
    if not isinstance(payload.get("rejected"), list):
        errors.append("integration-plan.rejected must be a list")
    return errors


def validate_integration_receipt(payload: dict) -> list[str]:
    """Validate integration-receipt.json."""
    errors = validate_common_json_artifact(payload, "integration-receipt")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["integration-receipt"], "integration-receipt"))
    if payload.get("strategy") not in INTEGRATION_STRATEGIES:
        errors.append("integration-receipt.strategy must be sequential or dependency-order")
    if payload.get("final_state") not in INTEGRATION_FINAL_STATES:
        errors.append("integration-receipt.final_state must be integration_completed, integration_failed, or integration_aborted")
    for field in ["started_at", "completed_at"]:
        if field in payload:
            errors.extend(_validate_iso_z(payload[field], f"integration-receipt.{field}"))
    for field in ["integrated", "rejected", "conflicts"]:
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"integration-receipt.{field} must be a list")
    return errors


def validate_validation_artifact(payload: dict) -> list[str]:
    """Validate validation.json."""
    errors = validate_common_json_artifact(payload, "validation")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["validation"], "validation"))
    if payload.get("overall") not in VALIDATION_OVERALL_STATES:
        errors.append("validation.overall must be passed, failed, or partial")
    schema_checks = payload.get("schema_checks")
    if not isinstance(schema_checks, list):
        errors.append("validation.schema_checks must be a list")
    else:
        for index, check in enumerate(schema_checks, start=1):
            label = f"validation.schema_checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{label} must be an object")
                continue
            for field in ["artifact", "ok", "errors", "warnings"]:
                if field not in check:
                    errors.append(f"{label} missing {field}")
            if "ok" in check and not isinstance(check["ok"], bool):
                errors.append(f"{label}.ok must be a boolean")
            for field in ["errors", "warnings"]:
                if field in check and not isinstance(check[field], list):
                    errors.append(f"{label}.{field} must be a list")
    for field in ["command_checks", "task_checks"]:
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"validation.{field} must be a list")
    return errors


def validate_release_candidate(payload: dict) -> list[str]:
    """Validate release-candidate.json."""
    errors = validate_common_json_artifact(payload, "release-candidate")
    errors.extend(_require_fields(payload, REQUIRED_JSON_FIELDS["release-candidate"], "release-candidate"))
    if payload.get("state") not in RELEASE_CANDIDATE_STATES:
        errors.append("release-candidate.state must be rc_built, rc_validated, or rc_failed")
    for field in ["source_integration_receipt", "validation_ref"]:
        if field in payload:
            errors.extend(f"release-candidate.{field}: {error}" for error in validate_relative_artifact_path(str(payload[field])))
    for field in ["included_tasks", "included_bundles"]:
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"release-candidate.{field} must be a list")
    return errors


def _read_and_validate_json_file(run_dir: Path, filename: str, validator) -> list[str]:
    path = run_dir / filename
    try:
        payload = read_json_artifact(path)
    except FileNotFoundError:
        return [f"{filename}: missing artifact"]
    except json.JSONDecodeError as exc:
        return [f"{filename}: invalid JSON: {exc.msg}"]
    except ArtifactValidationError as exc:
        return [f"{filename}: {exc}"]
    return validator(payload)


def _split_plan_task_ids(run_dir: Path) -> set[str]:
    try:
        payload = read_json_artifact(run_dir / "split-plan.json")
    except Exception:
        return set()
    return {str(task.get("task_id")) for task in payload.get("tasks", []) if isinstance(task, dict) and task.get("task_id")}


def _integration_plan_queue_keys(run_dir: Path) -> set[tuple[str, str]]:
    try:
        payload = read_json_artifact(run_dir / "integration-plan.json")
    except Exception:
        return set()
    return {
        (str(item.get("task_id")), str(item.get("bundle_id")))
        for item in payload.get("queue", [])
        if isinstance(item, dict) and item.get("task_id") and item.get("bundle_id")
    }


def validate_run_directory(run_dir: Path) -> dict:
    """Validate all known artifacts in a run directory and return a report dict."""
    checked: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    def add(artifact: str, artifact_errors: list[str], artifact_warnings: list[str] | None = None) -> None:
        nonlocal errors, warnings
        artifact_warnings = artifact_warnings or []
        checked.append(
            {
                "artifact": artifact,
                "errors": artifact_errors,
                "ok": not artifact_errors,
                "warnings": artifact_warnings,
            }
        )
        errors.extend(f"{artifact}: {error}" for error in artifact_errors)
        warnings.extend(f"{artifact}: {warning}" for warning in artifact_warnings)

    run_payload: dict[str, Any] = {}
    try:
        run_payload = read_json_artifact(run_dir / "run.json")
        run_id = str(run_payload.get("run_id", run_dir.name))
    except Exception:
        run_id = run_dir.name

    json_validators = [
        ("run.json", validate_run_artifact),
        ("context-pack.json", validate_context_pack),
        ("split-plan.json", validate_split_plan),
        ("task-graph.json", validate_task_graph),
        ("path-leases.json", validate_path_leases),
        ("integration-plan.json", validate_integration_plan),
        ("integration-receipt.json", validate_integration_receipt),
        ("validation.json", validate_validation_artifact),
        ("release-candidate.json", validate_release_candidate),
    ]
    for filename, validator in json_validators:
        add(filename, _read_and_validate_json_file(run_dir, filename, validator))

    for filename, artifact_type in [
        ("request.md", "request"),
        ("validation-report.md", "validation-report"),
        ("release-notes.md", "release-notes"),
        ("start-here.md", "start-here"),
    ]:
        add(filename, validate_markdown_artifact(run_dir / filename, artifact_type, run_id))

    add("worker-prompts/", validate_worker_prompts(run_dir))
    add("worker-ledger.jsonl", validate_worker_ledger(run_dir / "worker-ledger.jsonl"))
    add("patch-bundles/", validate_patch_bundles(run_dir))

    task_ids = _split_plan_task_ids(run_dir)
    if task_ids:
        try:
            graph = read_json_artifact(run_dir / "task-graph.json")
            graph_ids = {str(node.get("task_id")) for node in graph.get("nodes", []) if isinstance(node, dict)}
            missing = sorted(graph_ids - task_ids)
            if missing:
                add("task-graph.cross-ref", [f"task-graph nodes not in split-plan: {', '.join(missing)}"])
        except Exception as exc:
            add("task-graph.cross-ref", [str(exc)])

    queue_keys = _integration_plan_queue_keys(run_dir)
    if queue_keys:
        try:
            receipt = read_json_artifact(run_dir / "integration-receipt.json")
            missing_refs = []
            for item in receipt.get("integrated", []):
                if isinstance(item, dict):
                    key = (str(item.get("task_id")), str(item.get("bundle_id")))
                    if key not in queue_keys:
                        missing_refs.append(f"{key[0]}/{key[1]}")
            if missing_refs:
                add("integration-receipt.cross-ref", [f"integrated entries not in integration plan queue: {', '.join(missing_refs)}"])
        except Exception as exc:
            add("integration-receipt.cross-ref", [str(exc)])

    return {
        "checked_artifacts": checked,
        "errors": errors,
        "ok": not errors,
        "run_dir": run_dir.as_posix(),
        "run_id": run_id,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "warnings": warnings,
    }


def _write_markdown_artifact(path: Path, artifact_type: str, run_id: str, timestamp: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{_metadata_comment(artifact_type, run_id, timestamp)}\n{body.rstrip()}\n", encoding="utf-8")


def build_schema_fixture(run_dir: Path, *, run_id: str = "schema-fixture", timestamp: str | None = None) -> None:
    """Generate deterministic fixture artifacts for tests and evidence."""
    timestamp = timestamp or utc_now()
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir = run_dir / "worker-prompts"
    patch_dir = run_dir / "patch-bundles"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    patch_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = {
        "context_pack": "context-pack.json",
        "integration_plan": "integration-plan.json",
        "integration_receipt": "integration-receipt.json",
        "patch_bundles_manifest": "patch-bundles/manifest.json",
        "path_leases": "path-leases.json",
        "release_candidate": "release-candidate.json",
        "release_notes": "release-notes.md",
        "request": "request.md",
        "split_plan": "split-plan.json",
        "start_here": "start-here.md",
        "task_graph": "task-graph.json",
        "validation": "validation.json",
        "validation_report": "validation-report.md",
        "worker_ledger": "worker-ledger.jsonl",
        "worker_prompts_manifest": "worker-prompts/manifest.json",
    }

    request_body = """# Schema fixture request

Create a deterministic Patch Swarm schema fixture without live planning, worker dispatch, or patch application.
"""
    _write_markdown_artifact(run_dir / "request.md", "request", run_id, timestamp, request_body)

    context_pack = {
        **_common("context-pack", run_id, timestamp),
        "constraints": [
            "standard-library schema validation only",
            "no live dispatch",
            "no secrets",
        ],
        "repo_context": {
            "default_branch": "main",
            "dirty_work_policy": "preserve unrelated dirty work",
            "relevant_surfaces": ["parallel-delivery", "patch-swarm", "factory", "workset", "build"],
            "repo_name": "cento",
        },
        "request_ref": "request.md",
        "source_refs": [
            {"kind": "doc", "path": "docs/patch-swarm.md"},
            {"kind": "tool", "path": "scripts/parallel_delivery.py"},
        ],
    }
    write_json_artifact(run_dir / "context-pack.json", context_pack)

    tasks = [
        {
            "acceptance_contract": ["schema helper exists", "fixture validates"],
            "owned_paths": ["scripts/parallel_delivery_artifacts.py", "tests/test_parallel_delivery_artifact_schema.py"],
            "read_only_paths": ["docs/patch-swarm.md", "scripts/parallel_delivery.py"],
            "state": "queued_for_integration",
            "summary": "Implement schema validation and fixture generation.",
            "task_id": "task-0001",
            "title": "Schema helper",
            "validation_commands": ["python3 scripts/parallel_delivery_artifacts.py validate-run --run-dir workspace/runs/parallel-delivery/schema-fixture --json"],
        },
        {
            "acceptance_contract": ["artifact documentation exists"],
            "owned_paths": ["docs/parallel-delivery/patch-swarm-artifacts.md"],
            "read_only_paths": ["docs/patch-swarm.md"],
            "state": "prompt_emitted",
            "summary": "Document the artifact contract.",
            "task_id": "task-0002",
            "title": "Artifact documentation",
            "validation_commands": ["cento docs parallel-delivery"],
        },
    ]
    split_plan = {
        **_common("split-plan", run_id, timestamp),
        "max_candidate_tasks": 2,
        "tasks": tasks,
    }
    write_json_artifact(run_dir / "split-plan.json", split_plan)

    task_graph = {
        **_common("task-graph", run_id, timestamp),
        "edges": [
            {"from": "task-0002", "to": "task-0001", "type": "shares_context"},
        ],
        "nodes": [
            {"task_id": "task-0001"},
            {"task_id": "task-0002"},
        ],
    }
    write_json_artifact(run_dir / "task-graph.json", task_graph)

    path_leases = {
        **_common("path-leases", run_id, timestamp),
        "conflicts": [],
        "leases": [
            {
                "created_at": timestamp,
                "lease_id": "lease-task-0001",
                "owned_paths": ["scripts/parallel_delivery_artifacts.py", "tests/test_parallel_delivery_artifact_schema.py"],
                "read_only_paths": ["docs/patch-swarm.md", "scripts/parallel_delivery.py"],
                "state": "active",
                "task_id": "task-0001",
            },
            {
                "created_at": timestamp,
                "lease_id": "lease-task-0002",
                "owned_paths": ["docs/parallel-delivery/patch-swarm-artifacts.md"],
                "read_only_paths": ["docs/patch-swarm.md"],
                "state": "active",
                "task_id": "task-0002",
            },
        ],
    }
    write_json_artifact(run_dir / "path-leases.json", path_leases)

    prompt_items = []
    for task in tasks:
        prompt_path = prompt_dir / f"{task['task_id']}.md"
        _write_markdown_artifact(
            prompt_path,
            "worker-prompt",
            run_id,
            timestamp,
            f"""# Worker Prompt: {task['task_id']}

## Task
{task['summary']}

## Owned Paths
{chr(10).join(f'- `{path}`' for path in task['owned_paths'])}

## Validation
{chr(10).join(f'- `{command}`' for command in task['validation_commands'])}
""",
        )
        prompt_items.append(
            {
                "created_at": timestamp,
                "path": f"worker-prompts/{task['task_id']}.md",
                "sha256": sha256_file(prompt_path),
                "task_id": task["task_id"],
            }
        )
    worker_prompts_manifest = {
        **_common("worker-prompts-manifest", run_id, timestamp),
        "prompts": prompt_items,
    }
    write_json_artifact(prompt_dir / "manifest.json", worker_prompts_manifest)

    ledger_events = [
        {
            "actor": "fixture",
            "artifact_type": "worker-ledger-event",
            "created_at": timestamp,
            "details": {"path": "worker-prompts/task-0001.md"},
            "event_id": "event-0001",
            "event_type": "prompt_emitted",
            "provenance": _provenance("schema-fixture"),
            "run_id": run_id,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "task_id": "task-0001",
        },
        {
            "actor": "fixture",
            "artifact_type": "worker-ledger-event",
            "created_at": timestamp,
            "details": {"bundle": "patch-bundles/task-0001.bundle.json"},
            "event_id": "event-0002",
            "event_type": "patch_submitted",
            "provenance": _provenance("schema-fixture"),
            "run_id": run_id,
            "schema_version": CURRENT_SCHEMA_VERSION,
            "task_id": "task-0001",
        },
    ]
    (run_dir / "worker-ledger.jsonl").write_text("".join(_jsonl_dumps(event) for event in ledger_events), encoding="utf-8")

    patch_text = """diff --git a/scripts/parallel_delivery_artifacts.py b/scripts/parallel_delivery_artifacts.py
--- a/scripts/parallel_delivery_artifacts.py
+++ b/scripts/parallel_delivery_artifacts.py
@@ -1 +1 @@
-# fixture placeholder
+# fixture schema helper
"""
    patch_path = patch_dir / "task-0001.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    bundle = {
        **_common("patch-bundle", run_id, timestamp),
        "base_ref": "fixture-base",
        "bundle_id": "bundle-task-0001",
        "changed_paths": ["scripts/parallel_delivery_artifacts.py"],
        "claimed_paths": ["scripts/parallel_delivery_artifacts.py"],
        "diff_path": "task-0001.patch",
        "requires_manual_review": False,
        "summary": "Fixture patch bundle for schema validation.",
        "task_id": "task-0001",
        "tests_run": [
            {
                "command": "python3 scripts/parallel_delivery_artifacts.py validate-run --run-dir workspace/runs/parallel-delivery/schema-fixture --json",
                "status": "passed",
            }
        ],
    }
    bundle_path = patch_dir / "task-0001.bundle.json"
    write_json_artifact(bundle_path, bundle)
    patch_bundles_manifest = {
        **_common("patch-bundles-manifest", run_id, timestamp),
        "bundles": [
            {
                "created_at": timestamp,
                "diff_path": "patch-bundles/task-0001.patch",
                "path": "patch-bundles/task-0001.bundle.json",
                "sha256": sha256_file(bundle_path),
                "task_id": "task-0001",
            }
        ],
    }
    write_json_artifact(patch_dir / "manifest.json", patch_bundles_manifest)

    integration_plan = {
        **_common("integration-plan", run_id, timestamp),
        "queue": [
            {
                "bundle_id": "bundle-task-0001",
                "order": 1,
                "reason": "fixture patch validates and owns its changed path",
                "task_id": "task-0001",
                "validation_ref": "validation.json",
            }
        ],
        "rejected": [],
        "strategy": "sequential",
    }
    write_json_artifact(run_dir / "integration-plan.json", integration_plan)

    integration_receipt = {
        **_common("integration-receipt", run_id, timestamp),
        "completed_at": timestamp,
        "conflicts": [],
        "final_state": "integration_completed",
        "integrated": [
            {
                "bundle_id": "bundle-task-0001",
                "order": 1,
                "task_id": "task-0001",
            }
        ],
        "rejected": [],
        "started_at": timestamp,
        "strategy": "sequential",
    }
    write_json_artifact(run_dir / "integration-receipt.json", integration_receipt)

    validation = {
        **_common("validation", run_id, timestamp),
        "command_checks": [
            {
                "command": "python3 scripts/parallel_delivery_artifacts.py validate-run --json",
                "ok": True,
            }
        ],
        "overall": "passed",
        "schema_checks": [
            {"artifact": "run.json", "errors": [], "ok": True, "warnings": []},
            {"artifact": "split-plan.json", "errors": [], "ok": True, "warnings": []},
            {"artifact": "path-leases.json", "errors": [], "ok": True, "warnings": []},
        ],
        "task_checks": [
            {"errors": [], "ok": True, "task_id": "task-0001"},
        ],
    }
    write_json_artifact(run_dir / "validation.json", validation)

    _write_markdown_artifact(
        run_dir / "validation-report.md",
        "validation-report",
        run_id,
        timestamp,
        """# Patch Swarm Validation Report

## Summary
Fixture schema validation passed.

## Schema Checks
- `run.json`: passed
- `split-plan.json`: passed
- `path-leases.json`: passed

## Command Checks
- `validate-run --json`: passed

## Failures
None.

## Evidence
- `validation.json`
""",
    )

    release_candidate = {
        **_common("release-candidate", run_id, timestamp),
        "included_bundles": ["bundle-task-0001"],
        "included_tasks": ["task-0001"],
        "rc_id": "rc-schema-fixture",
        "source_integration_receipt": "integration-receipt.json",
        "state": "rc_validated",
        "validation_ref": "validation.json",
    }
    write_json_artifact(run_dir / "release-candidate.json", release_candidate)

    _write_markdown_artifact(
        run_dir / "release-notes.md",
        "release-notes",
        run_id,
        timestamp,
        """# Release Notes

## Request
Create a deterministic schema fixture.

## Integrated Patches
- `task-0001`: fixture schema helper bundle.

## Validation
Fixture validation passed.

## Evidence
- `validation-report.md`
- `release-candidate.json`
""",
    )

    _write_markdown_artifact(
        run_dir / "start-here.md",
        "start-here",
        run_id,
        timestamp,
        f"""# Patch Swarm Run: {run_id}

## What This Is
A deterministic fixture for the Patch Swarm artifact schema.

## Artifact Index
- `run.json`
- `request.md`
- `context-pack.json`
- `split-plan.json`
- `task-graph.json`
- `path-leases.json`
- `worker-prompts/manifest.json`
- `worker-ledger.jsonl`
- `patch-bundles/manifest.json`
- `integration-plan.json`
- `integration-receipt.json`
- `validation.json`
- `release-candidate.json`

## Validation Result
Passed.

## Release Candidate
`release-candidate.json`

## Next Operator Action
Use this fixture to validate schema helpers and tests.
""",
    )

    run = {
        **_common("run", run_id, timestamp),
        "artifact_paths": artifact_paths,
        "compatibility": {
            "allows_unknown_extra_fields": True,
            "future_schema_versions": "rejected unless allow_future=True for generic checks",
        },
        "completed_at": timestamp,
        "counts": {
            "candidate_tasks": 2,
            "integrated_patches": 1,
            "leased_tasks": 2,
            "patch_bundles": 1,
            "prompts": 2,
            "rejected_patches": 0,
        },
        "current_phase": "completed",
        "description": "Deterministic fixture run for Patch Swarm artifact schema validation.",
        "request_title": "Schema fixture request",
        "state": "completed",
        "tags": ["schema", "fixture", "patch-swarm"],
        "updated_at": timestamp,
    }
    write_json_artifact(run_dir / "run.json", run)


def schema_summary() -> dict[str, Any]:
    return {
        "artifact_types": sorted(ARTIFACT_TYPES.keys()),
        "lease_states": LEASE_STATES,
        "producer_consumer_matrix": [
            {"artifact": "run.json", "consumed_by": ["status", "validator", "release evidence"], "produced_by": "patch-swarm init / fixture builder"},
            {"artifact": "request.md", "consumed_by": ["context packer", "splitter"], "produced_by": "operator / init"},
            {"artifact": "context-pack.json", "consumed_by": ["splitter", "prompt emitter"], "produced_by": "context packer"},
            {"artifact": "split-plan.json", "consumed_by": ["task graph builder", "lease planner"], "produced_by": "factory splitter"},
            {"artifact": "task-graph.json", "consumed_by": ["scheduler", "integrator"], "produced_by": "task graph builder"},
            {"artifact": "path-leases.json", "consumed_by": ["prompt emitter", "patch bundle validator"], "produced_by": "workset lease planner"},
            {"artifact": "worker-prompts/", "consumed_by": ["Codex/worker threads"], "produced_by": "prompt emitter"},
            {"artifact": "worker-ledger.jsonl", "consumed_by": ["status", "validation", "evidence"], "produced_by": "dispatcher/collector"},
            {"artifact": "patch-bundles/", "consumed_by": ["validation", "integrator"], "produced_by": "workers/collector"},
            {"artifact": "integration-plan.json", "consumed_by": ["safe integrator executor"], "produced_by": "safe integrator planner"},
            {"artifact": "integration-receipt.json", "consumed_by": ["release candidate builder"], "produced_by": "safe integrator"},
            {"artifact": "validation.json", "consumed_by": ["release candidate builder", "status"], "produced_by": "validator/build"},
            {"artifact": "validation-report.md", "consumed_by": ["operator", "evidence"], "produced_by": "validator/build"},
            {"artifact": "release-candidate.json", "consumed_by": ["release notes", "operator"], "produced_by": "RC builder"},
            {"artifact": "release-notes.md", "consumed_by": ["operator"], "produced_by": "RC builder"},
            {"artifact": "start-here.md", "consumed_by": ["operator"], "produced_by": "evidence writer"},
        ],
        "run_state_transitions": RUN_STATE_TRANSITIONS,
        "run_states": RUN_STATES,
        "schema_version": CURRENT_SCHEMA_VERSION,
        "task_state_transitions": TASK_STATE_TRANSITIONS,
        "task_states": TASK_STATES,
    }


def command_write_fixture(args: argparse.Namespace) -> int:
    build_schema_fixture(Path(args.run_dir), run_id=args.run_id, timestamp=args.fixed_timestamp)
    print(stable_json_dumps({"ok": True, "run_dir": args.run_dir, "run_id": args.run_id}), end="")
    return 0


def command_validate_run(args: argparse.Namespace) -> int:
    report = validate_run_directory(Path(args.run_dir))
    if args.json:
        print(stable_json_dumps(report), end="")
    else:
        status = "ok" if report["ok"] else "failed"
        print(f"{status}: {report['run_id']} ({len(report['checked_artifacts'])} artifacts checked)")
        for error in report["errors"]:
            print(f"error: {error}", file=sys.stderr)
    return 0 if report["ok"] else 1


def command_print_schema_summary(args: argparse.Namespace) -> int:
    summary = schema_summary()
    if args.json:
        print(stable_json_dumps(summary), end="")
    else:
        print(f"schema_version: {CURRENT_SCHEMA_VERSION}")
        print("artifact_types:")
        for artifact_type in summary["artifact_types"]:
            print(f"- {artifact_type}: {ARTIFACT_TYPES[artifact_type]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and generate Patch Swarm artifact schema fixtures.")
    sub = parser.add_subparsers(dest="command", required=True)

    write_fixture = sub.add_parser("write-fixture", help="Write a deterministic schema fixture run.")
    write_fixture.add_argument("--run-dir", required=True)
    write_fixture.add_argument("--run-id", default="schema-fixture")
    write_fixture.add_argument("--fixed-timestamp", default=None)
    write_fixture.set_defaults(func=command_write_fixture)

    validate_run = sub.add_parser("validate-run", help="Validate a Patch Swarm artifact run directory.")
    validate_run.add_argument("--run-dir", required=True)
    validate_run.add_argument("--json", action="store_true")
    validate_run.set_defaults(func=command_validate_run)

    summary = sub.add_parser("print-schema-summary", help="Print schema constants and producer/consumer summary.")
    summary.add_argument("--json", action="store_true")
    summary.set_defaults(func=command_print_schema_summary)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
