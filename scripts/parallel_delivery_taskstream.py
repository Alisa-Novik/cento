#!/usr/bin/env python3
"""Patch Swarm to agent-work/Taskstream handoff adapter.

The adapter is deliberately local-first. It generates story and validation
manifests that existing `cento agent-work preflight` understands, plus Patch
Swarm metadata for traceability. Live Taskstream changes are only attempted by
the explicit apply path.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

try:
    import story_manifest
    import validation_manifest as validation_manifest_tools
except ImportError:  # pragma: no cover - direct import fallback for unusual cwd
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import story_manifest
    import validation_manifest as validation_manifest_tools


ROOT = Path(__file__).resolve().parents[1]
TASKSTREAM_REPORT_SCHEMA = "cento.parallel_delivery.taskstream_handoff_report.v1"
TASKSTREAM_APPLY_RECEIPT_SCHEMA = "cento.parallel_delivery.taskstream_apply_receipt.v1"
PATCH_SWARM_SPLIT_SCHEMA = "cento.parallel_delivery.split_plan.v1"
STORY_COMPAT_SCHEMA = "cento.agent_work.story.v1"
VALIDATION_COMPAT_SCHEMA = "cento.agent_work.validation.v1"
DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z"
SECRET_PATH_NAMES = {
    ".env",
    ".env.mcp",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}


class TaskstreamHandoffError(Exception):
    """Raised when Patch Swarm handoff artifacts cannot be generated safely."""


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True)
class PatchSwarmTask:
    task_id: str
    title: str
    summary: str
    route: str
    worker_profile: str | None
    priority: str
    owned_paths: list[str]
    touched_path_candidates: list[str]
    acceptance_contract: list[str]
    validation_commands: list[str]
    evidence_files: list[str]
    handoff_notes: str
    risk_flags: list[str]
    lane: str
    risk_tier: str
    state: str


@dataclass(frozen=True)
class PatchSwarmSplitPlan:
    schema: str
    run_id: str
    request_id: str
    title: str
    base_commit: str | None
    tasks: list[PatchSwarmTask]


@dataclass(frozen=True)
class TaskstreamHandoffReport:
    schema: str
    run_id: str
    request_id: str
    mode: str
    transport: str
    split_plan: str
    task_count: int
    story_manifest_count: int
    validation_manifest_count: int
    agent_work_routed_count: int
    manifest_only_count: int
    preflight: dict[str, Any]
    live_creation_attempted: bool
    live_creation_blocked_without_apply: bool
    tasks: list[dict[str, Any]]
    created_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def resolve_root_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return slug or "patch-swarm-task"


def text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def looks_like_secret_value(value: str) -> bool:
    text = str(value or "")
    return bool(
        re.search(r"\bsk-[A-Za-z0-9_-]{20,}\b", text)
        or re.search(r"BEGIN [A-Z ]*PRIVATE KEY", text)
        or re.search(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}", text)
    )


def normalize_safe_manifest_path(raw: str) -> str:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        raise TaskstreamHandoffError("path is required")
    if "\x00" in value:
        raise TaskstreamHandoffError(f"path contains NUL byte: {raw!r}")
    if value.startswith("/"):
        raise TaskstreamHandoffError(f"absolute paths are not allowed: {raw}")
    if re.match(r"^[A-Za-z]:/", value):
        raise TaskstreamHandoffError(f"Windows drive paths are not allowed: {raw}")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if any(part == ".." for part in parts):
        raise TaskstreamHandoffError(f"path traversal is not allowed: {raw}")
    for part in parts:
        lower = part.lower()
        if lower in SECRET_PATH_NAMES or lower.startswith(".env."):
            raise TaskstreamHandoffError(f"local secret path is not allowed: {raw}")
        if lower in {"secrets", "private_keys"}:
            raise TaskstreamHandoffError(f"local secret-looking path is not allowed: {raw}")
    if looks_like_secret_value(value):
        raise TaskstreamHandoffError("secret-looking inline value is not allowed in manifest paths")
    return "/".join(parts)


def safe_path_list(values: list[str], field: str) -> list[str]:
    normalized: list[str] = []
    for value in values:
        try:
            normalized.append(normalize_safe_manifest_path(value))
        except TaskstreamHandoffError as exc:
            raise TaskstreamHandoffError(f"{field}: {exc}") from exc
    return sorted(dict.fromkeys(normalized))


def task_from_payload(payload: dict[str, Any], index: int) -> PatchSwarmTask:
    task_id = str(payload.get("task_id") or payload.get("id") or f"task-{index:04d}").strip()
    title = str(payload.get("title") or payload.get("name") or task_id).strip()
    summary = str(payload.get("summary") or payload.get("description") or payload.get("story") or title).strip()
    route = str(payload.get("route") or payload.get("taskstream_route") or "").strip()
    lane = str(payload.get("lane") or payload.get("role") or "").strip()
    worker_profile = str(payload.get("worker_profile") or payload.get("worker_profile_suggestion") or "").strip() or None
    priority = str(payload.get("priority") or "normal").strip() or "normal"
    risk_tier = str(payload.get("risk_tier") or payload.get("risk") or "medium").strip() or "medium"
    state = str(payload.get("state") or "ready").strip() or "ready"
    owned_paths = text_list(payload.get("owned_paths") or payload.get("write_paths") or payload.get("owned_scope"))
    touched = text_list(
        payload.get("touched_path_candidates")
        or payload.get("touched_paths")
        or payload.get("changed_paths")
        or payload.get("expected_artifacts")
    )
    if not touched:
        touched = list(owned_paths)
    acceptance = text_list(payload.get("acceptance_contract") or payload.get("acceptance_criteria") or payload.get("acceptance"))
    validation_commands = text_list(payload.get("validation_commands") or payload.get("commands"))
    evidence_files = text_list(payload.get("evidence_files") or payload.get("evidence_pointers") or payload.get("expected_evidence"))
    if not evidence_files:
        evidence_files = [f"workspace/runs/parallel-delivery/taskstream-fixture/evidence/{task_id}-validation.txt"]
    handoff_notes = str(payload.get("handoff_notes") or payload.get("handoff") or "Preserve unrelated hunks and leave deterministic evidence.").strip()
    risk_flags = text_list(payload.get("risk_flags") or payload.get("rejection_triggers"))
    return PatchSwarmTask(
        task_id=task_id,
        title=title,
        summary=summary,
        route=route,
        worker_profile=worker_profile,
        priority=priority,
        owned_paths=safe_path_list(owned_paths, "owned_paths"),
        touched_path_candidates=safe_path_list(touched, "touched_path_candidates"),
        acceptance_contract=acceptance,
        validation_commands=validation_commands,
        evidence_files=safe_path_list(evidence_files, "evidence_files"),
        handoff_notes=handoff_notes,
        risk_flags=risk_flags,
        lane=lane,
        risk_tier=risk_tier,
        state=state,
    )


def load_split_plan(path: Path) -> PatchSwarmSplitPlan:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TaskstreamHandoffError(f"split plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TaskstreamHandoffError(f"invalid split plan JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TaskstreamHandoffError("split plan root must be an object")

    raw_tasks = payload.get("tasks")
    if raw_tasks is None and isinstance(payload.get("task_graph"), dict):
        raw_tasks = payload["task_graph"].get("tasks") or payload["task_graph"].get("nodes")
    if raw_tasks is None:
        raw_tasks = payload.get("nodes")
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raise TaskstreamHandoffError("split plan must include a non-empty tasks list")
    tasks = []
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            raise TaskstreamHandoffError(f"task #{index} must be an object")
        tasks.append(task_from_payload(item, index))

    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    return PatchSwarmSplitPlan(
        schema=str(payload.get("schema") or payload.get("schema_version") or PATCH_SWARM_SPLIT_SCHEMA),
        run_id=str(payload.get("run_id") or path.parent.name or "taskstream-handoff"),
        request_id=str(payload.get("request_id") or request.get("id") or f"request-{path.parent.name}"),
        title=str(payload.get("title") or request.get("title") or request.get("normalized_goal") or "Patch Swarm taskstream handoff"),
        base_commit=str(payload.get("base_commit") or payload.get("base_ref") or ""),
        tasks=tasks,
    )


def choose_task_route(task: PatchSwarmTask, *, default_route: str = "agent-work") -> str:
    explicit = str(task.route or "").strip().lower()
    if explicit in {"manifest-only", "evidence-only", "planning-only", "blocked", "no-live-create"}:
        return "manifest-only"
    if explicit == "agent-work":
        return "agent-work" if task.validation_commands else "manifest-only"
    if task.state.lower() in {"blocked", "planning", "evidence-only"}:
        return "manifest-only"
    lane = task.lane.lower()
    if lane in {"human-handoff", "docs-evidence"} and not task.validation_commands:
        return "manifest-only"
    if task.validation_commands and task.acceptance_contract and default_route == "agent-work":
        return "agent-work"
    return "manifest-only"


def validate_patch_swarm_task(task: PatchSwarmTask, *, route: str | None = None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    selected_route = route or choose_task_route(task)
    if not task.task_id:
        issues.append(ValidationIssue("task_id", "task_id is required"))
    if not task.title:
        issues.append(ValidationIssue("title", "title is required"))
    if not task.acceptance_contract:
        issues.append(ValidationIssue("acceptance_contract", "acceptance contract is required"))
    if selected_route == "agent-work" and not task.validation_commands:
        issues.append(ValidationIssue("validation_commands", "validation commands are required for agent-work tasks"))
    for field, values in (
        ("owned_paths", task.owned_paths),
        ("touched_path_candidates", task.touched_path_candidates),
        ("evidence_files", task.evidence_files),
    ):
        for value in values:
            try:
                normalize_safe_manifest_path(value)
            except TaskstreamHandoffError as exc:
                issues.append(ValidationIssue(field, str(exc)))
    for field, values in (
        ("title", [task.title]),
        ("summary", [task.summary]),
        ("acceptance_contract", task.acceptance_contract),
        ("validation_commands", task.validation_commands),
        ("handoff_notes", [task.handoff_notes]),
    ):
        for value in values:
            if looks_like_secret_value(value):
                issues.append(ValidationIssue(field, "secret-looking value is not allowed"))
    return issues


def role_for_task(task: PatchSwarmTask, route: str) -> str:
    text = " ".join([task.lane, task.worker_profile or "", route]).lower()
    if "validator" in text:
        return "validator"
    if "coordinator" in text or "planner" in text:
        return "coordinator"
    if "docs" in text or "evidence" in text:
        return "docs-evidence"
    return "builder"


def risk_for_story(task: PatchSwarmTask) -> str:
    risk = task.risk_tier.lower()
    return risk if risk in {"low", "medium", "high"} else "medium"


def task_story_key(task: PatchSwarmTask) -> str:
    return f"patch-swarm-{slugify(task.task_id)}"


def task_run_dir(out_dir: Path, task: PatchSwarmTask) -> str:
    return rel(out_dir / "work-packages" / task.task_id)


def task_to_story_manifest(plan: PatchSwarmSplitPlan, task: PatchSwarmTask, *, out_dir: Path, route: str) -> dict[str, Any]:
    run_dir = task_run_dir(out_dir, task)
    validation_path = f"{run_dir}/validation.json"
    deliverables_path = f"{run_dir}/deliverables.json"
    hub_path = f"{run_dir}/start-here.html"
    role = role_for_task(task, route)
    risk = risk_for_story(task)
    if not task.validation_commands:
        validation_mode = "manual-planning"
    elif risk == "high":
        validation_mode = "strong-model"
    else:
        validation_mode = "no-model"
    no_model = validation_mode == "no-model"
    commands = task.validation_commands if task.validation_commands else []
    expected_outputs = [
        {
            "path": value,
            "owner": role,
            "description": f"Expected evidence for {task.task_id}",
            "required": True,
        }
        for value in task.evidence_files
    ]
    expected_outputs.append(
        {
            "path": f"{run_dir}/handoff.md",
            "owner": role,
            "description": "Patch Swarm task handoff note.",
            "required": True,
        }
    )
    return {
        "schema": STORY_COMPAT_SCHEMA,
        "schema_version": "1.0",
        "source": "parallel-delivery",
        "run_id": plan.run_id,
        "request_id": plan.request_id,
        "task_id": task.task_id,
        "story_key": task_story_key(task),
        "title": task.title,
        "summary": task.summary,
        "status": "ready_for_agent_work" if route == "agent-work" else "manifest_only",
        "route": route,
        "worker_profile": task.worker_profile or "",
        "priority": task.priority,
        "owned_paths": task.owned_paths,
        "touched_path_candidates": task.touched_path_candidates,
        "acceptance_contract": task.acceptance_contract,
        "handoff_notes_path": "handoff.md",
        "validation_manifest_path": "validation.json",
        "evidence_links": task.evidence_files,
        "risk_flags": task.risk_flags,
        "issue": {
            "id": 0,
            "title": task.title,
            "package": f"patch-swarm-{slugify(plan.run_id)}",
        },
        "lane": {
            "owner": role,
            "node": "linux",
            "agent": task.worker_profile or "codex",
            "role": role,
        },
        "paths": {
            "run_dir": run_dir,
        },
        "scope": {
            "goal": task.summary,
            "acceptance": task.acceptance_contract,
        },
        "expected_outputs": expected_outputs,
        "validation": {
            "manifest": validation_path,
            "mode": validation_mode,
            "risk": risk,
            "no_model_eligible": no_model,
            "escalation_triggers": [
                "missing_manifest",
                "failed_deterministic_command",
                "ambiguity",
            ],
            "commands": commands,
        },
        "deliverables": {
            "manifest": deliverables_path,
            "hub": hub_path,
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "base_commit": plan.base_commit or "",
            "created_by": "cento parallel-delivery taskstream emit",
            "split_plan_schema": plan.schema,
        },
    }


def task_to_validation_manifest(plan: PatchSwarmSplitPlan, task: PatchSwarmTask, story: dict[str, Any], story_path: Path) -> dict[str, Any]:
    if task.validation_commands:
        manifest = validation_manifest_tools.build_manifest(story, story_path)
    else:
        manifest = {
            "schema": "cento.validation-manifest.v1",
            "task": task.title,
            "story_manifest": rel(story_path),
            "claim": task.summary,
            "risk": risk_for_story(task),
            "decision_requested": "approve",
            "checks": [
                {
                    "name": "story-json-valid",
                    "type": "command",
                    "command": f"python3 -m json.tool {shlex.quote(rel(story_path))}",
                    "cwd": ".",
                    "timeout_seconds": 20,
                    "expect_exit": 0,
                    "required": True,
                }
            ],
            "manual_review": [],
            "coverage": {
                "deterministic_checks": 1,
                "manual_review_items": 0,
                "automation_coverage_percent": 100.0,
            },
            "stats_policy": {
                "ai_calls_used": 0,
                "estimated_ai_cost": 0,
                "requires_total_duration_ms": True,
                "requires_per_check_duration_ms": True,
            },
            "created_at": utc_now(),
        }
    manifest.update(
        {
            "compat_schema": VALIDATION_COMPAT_SCHEMA,
            "source": "parallel-delivery",
            "run_id": plan.run_id,
            "task_id": task.task_id,
            "story_key": task_story_key(task),
            "validation_commands": [
                {"cmd": command, "required": True, "working_directory": "repo"}
                for command in task.validation_commands
            ],
            "expected_evidence_files": task.evidence_files,
            "acceptance_contract": task.acceptance_contract,
            "record_back": {
                "preferred_transport": "mcp",
                "fallback_transport": "agent-work",
                "live_update_requires_apply": True,
            },
        }
    )
    return manifest


def write_handoff_note(path: Path, task: PatchSwarmTask) -> None:
    lines = [
        f"# Patch Swarm Handoff: {task.task_id}",
        "",
        "## Scope",
        task.summary,
        "",
        "## Owned Paths",
    ]
    lines.extend(f"- {item}" for item in (task.owned_paths or ["None declared."]))
    lines.extend(["", "## Candidate Touched Paths"])
    lines.extend(f"- {item}" for item in (task.touched_path_candidates or ["None declared."]))
    lines.extend(["", "## Acceptance Contract"])
    lines.extend(f"- {item}" for item in task.acceptance_contract)
    lines.extend(["", "## Validation"])
    lines.extend(f"- {item}" for item in (task.validation_commands or ["Manifest-only task; inspect generated evidence links."]))
    lines.extend(["", "## Evidence"])
    lines.extend(f"- {item}" for item in task.evidence_files)
    lines.extend(
        [
            "",
            "## Notes",
            task.handoff_notes,
            "",
            "## Guards",
            "Preserve unrelated dirty work. Do not edit secrets. Do not mutate Taskstream/Redmine directly.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def agent_work_create_command(story_path: Path, task: PatchSwarmTask, route: str) -> str:
    if route != "agent-work":
        return "manifest-only: no live agent-work create command is planned for this task."
    cmd = [
        "cento",
        "agent-work",
        "create",
        "--title",
        task.title,
        "--manifest",
        rel(story_path),
        "--description",
        task.summary,
        "--node",
        "linux",
        "--agent",
        task.worker_profile or "codex",
        "--role",
        role_for_task(task, route),
        "--package",
        "parallel-delivery",
    ]
    for owned in task.owned_paths:
        cmd.extend(["--owns", owned])
    return " ".join(shlex.quote(part) for part in cmd)


def discover_agent_work_preflight() -> dict[str, Any] | None:
    script = ROOT / "scripts" / "agent_work.py"
    if not script.exists():
        return None
    return {
        "command": f"{sys.executable} {rel(script)} preflight STORY --validation-manifest VALIDATION",
        "script": rel(script),
    }


def preflight_one_package(package_dir: Path, report_dir: Path) -> dict[str, Any]:
    story_path = package_dir / "story.json"
    validation_path = package_dir / "validation.json"
    task_id = package_dir.name
    report_path = report_dir / f"{task_id}.preflight.json"
    stdout_path = report_dir / f"{task_id}.preflight.stdout"
    stderr_path = report_dir / f"{task_id}.preflight.stderr"
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "agent_work.py"),
        "preflight",
        str(story_path),
        "--validation-manifest",
        str(validation_path),
        "--report",
        str(report_path),
        "--json",
    ]
    report_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    return {
        "task_id": task_id,
        "status": "passed" if completed.returncode == 0 else "blocked",
        "command": " ".join(shlex.quote(part) for part in cmd),
        "exit_code": completed.returncode,
        "report": rel(report_path),
        "stdout_path": rel(stdout_path),
        "stderr_path": rel(stderr_path),
    }


def run_agent_work_preflight(manifest_dir: Path, out_dir: Path) -> dict[str, Any]:
    discovery = discover_agent_work_preflight()
    if discovery is None:
        return {
            "available": False,
            "status": "skipped",
            "command": "",
            "exit_code": 0,
            "stdout_path": "",
            "stderr_path": "",
            "tasks": [],
        }
    package_dirs = sorted(path for path in manifest_dir.iterdir() if path.is_dir())
    report_dir = out_dir / "preflight-reports"
    task_results = [preflight_one_package(path, report_dir) for path in package_dirs]
    status = "passed" if all(item["exit_code"] == 0 for item in task_results) else "blocked"
    summary_stdout = out_dir / "logs" / "agent-work-preflight.stdout"
    summary_stderr = out_dir / "logs" / "agent-work-preflight.stderr"
    summary_stdout.parent.mkdir(parents=True, exist_ok=True)
    summary_stdout.write_text("\n".join(f"{item['task_id']}: {item['status']} exit={item['exit_code']}" for item in task_results) + "\n", encoding="utf-8")
    summary_stderr.write_text("\n".join(item["stderr_path"] for item in task_results if item["exit_code"] != 0) + ("\n" if task_results else ""), encoding="utf-8")
    return {
        "available": True,
        "status": status,
        "command": discovery["command"],
        "exit_code": 0 if status == "passed" else 1,
        "stdout_path": rel(summary_stdout),
        "stderr_path": rel(summary_stderr),
        "tasks": task_results,
    }


def validate_manifest_dir(manifest_dir: Path) -> list[str]:
    errors: list[str] = []
    if not manifest_dir.exists():
        return [f"manifest dir not found: {manifest_dir}"]
    for package_dir in sorted(path for path in manifest_dir.iterdir() if path.is_dir()):
        story_path = package_dir / "story.json"
        validation_path = package_dir / "validation.json"
        handoff_path = package_dir / "handoff.md"
        for path in (story_path, validation_path, handoff_path):
            if not path.exists():
                errors.append(f"missing {path.name}: {rel(path)}")
        if story_path.exists():
            try:
                story = story_manifest.load_manifest(story_path)
                errors.extend(f"{package_dir.name} story: {item}" for item in story_manifest.validate_manifest(story, check_links=False))
            except Exception as exc:  # noqa: BLE001 - surfaced as preflight error text
                errors.append(f"{package_dir.name} story: {exc}")
        if validation_path.exists():
            try:
                validation = validation_manifest_tools.load_validation(validation_path)
                errors.extend(f"{package_dir.name} validation: {item}" for item in validation_manifest_tools.validate_validation_manifest(validation))
            except Exception as exc:  # noqa: BLE001 - surfaced as preflight error text
                errors.append(f"{package_dir.name} validation: {exc}")
    return errors


def taskstream_report_payload(report: TaskstreamHandoffReport) -> dict[str, Any]:
    return {
        "schema": report.schema,
        "run_id": report.run_id,
        "request_id": report.request_id,
        "mode": report.mode,
        "transport": report.transport,
        "split_plan": report.split_plan,
        "task_count": report.task_count,
        "story_manifest_count": report.story_manifest_count,
        "validation_manifest_count": report.validation_manifest_count,
        "agent_work_routed_count": report.agent_work_routed_count,
        "manifest_only_count": report.manifest_only_count,
        "preflight": report.preflight,
        "live_creation_attempted": report.live_creation_attempted,
        "live_creation_blocked_without_apply": report.live_creation_blocked_without_apply,
        "tasks": report.tasks,
        "created_at": report.created_at,
    }


def write_handoff_report(report: TaskstreamHandoffReport, out_dir: Path) -> None:
    payload = taskstream_report_payload(report)
    write_json(out_dir / "taskstream-handoff-report.json", payload)
    lines = [
        "# Patch Swarm Taskstream Handoff",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Mode: `{report.mode}`",
        f"- Transport: `{report.transport}`",
        f"- Tasks: `{report.task_count}`",
        f"- Agent-work routed: `{report.agent_work_routed_count}`",
        f"- Manifest-only: `{report.manifest_only_count}`",
        f"- Preflight: `{report.preflight.get('status', 'unknown')}`",
        f"- Live creation attempted: `{str(report.live_creation_attempted).lower()}`",
        "",
        "## Work Packages",
        "",
    ]
    for item in report.tasks:
        lines.append(f"- `{item['task_id']}` route=`{item['route']}` story=`{item['story_manifest']}` validation=`{item['validation_manifest']}`")
    (out_dir / "taskstream-handoff-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_validation_summary(report, out_dir)


def write_validation_summary(report: TaskstreamHandoffReport, out_dir: Path) -> None:
    lines = [
        f"run ID: {report.run_id}",
        f"base commit: {(report.tasks[0].get('base_commit') if report.tasks else '') or 'unknown'}",
        f"split plan path: {report.split_plan}",
        f"generated work package count: {report.task_count}",
        f"story manifest count: {report.story_manifest_count}",
        f"validation manifest count: {report.validation_manifest_count}",
        f"agent-work routed count: {report.agent_work_routed_count}",
        f"manifest-only count: {report.manifest_only_count}",
        f"preflight availability/status: {report.preflight.get('available')} / {report.preflight.get('status')}",
        f"live creation attempted: {str(report.live_creation_attempted).lower()}",
        f"live creation refusal exit code: {'blocked' if report.live_creation_blocked_without_apply else 'not-applicable'}",
        f"report paths: {rel(out_dir / 'taskstream-handoff-report.json')}, {rel(out_dir / 'taskstream-handoff-report.md')}",
    ]
    (out_dir / "validation-summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_taskstream_manifests(
    *,
    split_plan_path: Path,
    out_dir: Path,
    mode: Literal["dry-run", "apply"] = "dry-run",
    transport: Literal["auto", "mcp", "agent-work", "manifest-only"] = "auto",
    run_preflight: bool = True,
    default_route: str = "agent-work",
    timestamp: str | None = None,
) -> TaskstreamHandoffReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = load_split_plan(split_plan_path)
    packages_dir = out_dir / "work-packages"
    packages_dir.mkdir(parents=True, exist_ok=True)
    task_rows: list[dict[str, Any]] = []
    agent_work_count = 0
    manifest_only_count = 0

    for task in plan.tasks:
        route = choose_task_route(task, default_route=default_route)
        issues = validate_patch_swarm_task(task, route=route)
        if issues:
            detail = "; ".join(f"{issue.field}: {issue.message}" for issue in issues)
            raise TaskstreamHandoffError(f"invalid task {task.task_id}: {detail}")
        package_dir = packages_dir / task.task_id
        package_dir.mkdir(parents=True, exist_ok=True)
        story_path = package_dir / "story.json"
        validation_path = package_dir / "validation.json"
        handoff_path = package_dir / "handoff.md"
        story = task_to_story_manifest(plan, task, out_dir=out_dir, route=route)
        validation = task_to_validation_manifest(plan, task, story, story_path)
        write_json(story_path, story)
        write_json(validation_path, validation)
        write_handoff_note(handoff_path, task)
        command_path = package_dir / "agent-work-command.txt"
        command_path.write_text(agent_work_create_command(story_path, task, route) + "\n", encoding="utf-8")
        if route == "agent-work":
            agent_work_count += 1
        else:
            manifest_only_count += 1
        task_rows.append(
            {
                "task_id": task.task_id,
                "route": route,
                "story_manifest": rel(story_path),
                "validation_manifest": rel(validation_path),
                "handoff": rel(handoff_path),
                "agent_work_command": rel(command_path),
                "base_commit": plan.base_commit or "",
            }
        )

    preflight = (
        run_agent_work_preflight(packages_dir, out_dir)
        if run_preflight
        else {"available": bool(discover_agent_work_preflight()), "status": "skipped", "command": "", "exit_code": 0}
    )
    report = TaskstreamHandoffReport(
        schema=TASKSTREAM_REPORT_SCHEMA,
        run_id=plan.run_id,
        request_id=plan.request_id,
        mode=mode,
        transport=transport,
        split_plan=rel(split_plan_path),
        task_count=len(plan.tasks),
        story_manifest_count=len(plan.tasks),
        validation_manifest_count=len(plan.tasks),
        agent_work_routed_count=agent_work_count,
        manifest_only_count=manifest_only_count,
        preflight=preflight,
        live_creation_attempted=False,
        live_creation_blocked_without_apply=True,
        tasks=task_rows,
        created_at=timestamp or utc_now(),
    )
    write_handoff_report(report, out_dir)
    return report


def run_preflight_command(manifest_dir: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    errors = validate_manifest_dir(manifest_dir)
    agent_work = run_agent_work_preflight(manifest_dir, out_dir) if not errors else {"available": True, "status": "blocked", "exit_code": 1, "tasks": []}
    payload = {
        "schema": "cento.parallel_delivery.taskstream_preflight.v1",
        "manifest_dir": rel(manifest_dir),
        "status": "passed" if not errors and agent_work.get("status") == "passed" else "blocked",
        "errors": errors,
        "agent_work_preflight": agent_work,
        "created_at": utc_now(),
    }
    write_json(out_dir / "preflight-report.json", payload)
    lines = ["# Patch Swarm Taskstream Preflight", "", f"- Status: `{payload['status']}`", f"- Manifest dir: `{payload['manifest_dir']}`", ""]
    if errors:
        lines.extend(["## Errors", ""])
        lines.extend(f"- {item}" for item in errors)
    (out_dir / "preflight-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def apply_taskstream_handoff(
    *,
    manifest_dir: Path,
    out_dir: Path,
    transport: Literal["auto", "mcp", "agent-work"],
    apply: bool,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not apply:
        receipt = {
            "schema": TASKSTREAM_APPLY_RECEIPT_SCHEMA,
            "mode": "dry-run",
            "transport": transport,
            "status": "refused",
            "reason": "taskstream apply requires explicit --apply",
            "manifest_dir": rel(manifest_dir),
            "created_at": utc_now(),
        }
        write_json(out_dir / "apply-refusal.json", receipt)
        raise TaskstreamHandoffError("taskstream apply requires explicit --apply")

    receipts: list[dict[str, Any]] = []
    receipts_dir = out_dir / "apply-receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    for package_dir in sorted(path for path in manifest_dir.iterdir() if path.is_dir()):
        story_path = package_dir / "story.json"
        validation_path = package_dir / "validation.json"
        story = json.loads(story_path.read_text(encoding="utf-8"))
        route = str(story.get("route") or "")
        if route != "agent-work":
            status = "skipped"
            command = "manifest-only"
            returncode = 0
            stdout = ""
            stderr = ""
        else:
            command = (package_dir / "agent-work-command.txt").read_text(encoding="utf-8").strip()
            completed = subprocess.run(shlex.split(command), cwd=ROOT, text=True, capture_output=True, check=False)
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            status = "submitted" if returncode == 0 else "blocked"
        stdout_path = receipts_dir / f"{package_dir.name}.apply.stdout"
        stderr_path = receipts_dir / f"{package_dir.name}.apply.stderr"
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        receipt = {
            "schema": TASKSTREAM_APPLY_RECEIPT_SCHEMA,
            "run_id": str(story.get("run_id") or ""),
            "task_id": package_dir.name,
            "mode": "apply",
            "transport": "agent-work" if transport == "auto" else transport,
            "status": status,
            "story_manifest": rel(story_path),
            "validation_manifest": rel(validation_path),
            "external_ref": {},
            "command_or_tool": command,
            "exit_code": returncode,
            "stdout_path": rel(stdout_path),
            "stderr_path": rel(stderr_path),
            "created_at": utc_now(),
        }
        write_json(receipts_dir / f"{package_dir.name}.json", receipt)
        receipts.append(receipt)
    write_json(
        out_dir / "apply-report.json",
        {
            "schema": "cento.parallel_delivery.taskstream_apply_report.v1",
            "manifest_dir": rel(manifest_dir),
            "transport": transport,
            "submitted_count": len([item for item in receipts if item["status"] == "submitted"]),
            "blocked_count": len([item for item in receipts if item["status"] == "blocked"]),
            "skipped_count": len([item for item in receipts if item["status"] == "skipped"]),
            "receipts": [rel(receipts_dir / f"{item['task_id']}.json") for item in receipts],
            "created_at": utc_now(),
        },
    )
    return receipts


def run_emit_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        report = emit_taskstream_manifests(
            split_plan_path=resolve_root_path(args.split_plan),
            out_dir=resolve_root_path(args.out),
            mode="dry-run",
            transport=args.transport,
            run_preflight=bool(args.run_preflight),
            default_route=args.default_route,
        )
        return taskstream_report_payload(report), 0
    except TaskstreamHandoffError as exc:
        return {"ok": False, "errors": [str(exc)]}, 1


def run_preflight_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    payload = run_preflight_command(resolve_root_path(args.manifest_dir), resolve_root_path(args.out))
    return payload, 0 if payload.get("status") == "passed" else 1


def run_apply_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        receipts = apply_taskstream_handoff(
            manifest_dir=resolve_root_path(args.manifest_dir),
            out_dir=resolve_root_path(args.out),
            transport=args.transport,
            apply=bool(args.apply),
        )
        return {"ok": True, "receipts": receipts}, 0
    except TaskstreamHandoffError as exc:
        return {"ok": False, "errors": [str(exc)]}, 2


def add_taskstream_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    taskstream = sub.add_parser("taskstream", help="Emit Patch Swarm task handoff manifests for cento agent-work.")
    taskstream_sub = taskstream.add_subparsers(dest="taskstream_command", required=True)

    emit = taskstream_sub.add_parser("emit", help="Generate local story/validation manifests from a Patch Swarm split plan.")
    emit.add_argument("--split-plan", required=True)
    emit.add_argument("--out", required=True)
    emit.add_argument("--transport", choices=["auto", "mcp", "agent-work", "manifest-only"], default="manifest-only")
    emit.add_argument("--run-preflight", action=argparse.BooleanOptionalAction, default=True)
    emit.add_argument("--default-route", choices=["agent-work", "manifest-only"], default="agent-work")
    emit.add_argument("--json", action="store_true")

    preflight = taskstream_sub.add_parser("preflight", help="Validate generated work packages and run safe agent-work preflight.")
    preflight.add_argument("--manifest-dir", required=True)
    preflight.add_argument("--out", required=True)
    preflight.add_argument("--json", action="store_true")

    apply_parser = taskstream_sub.add_parser("apply", help="Submit generated work packages through approved Taskstream surfaces.")
    apply_parser.add_argument("--manifest-dir", required=True)
    apply_parser.add_argument("--out", required=True)
    apply_parser.add_argument("--transport", choices=["auto", "mcp", "agent-work"], default="auto")
    apply_parser.add_argument("--apply", action="store_true", help="Required for live task creation.")
    apply_parser.add_argument("--json", action="store_true")


def build_fixture_split_plan(out_dir: Path, *, base_commit: str, timestamp: str = DEFAULT_TIMESTAMP) -> Path:
    input_dir = out_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    split_plan_path = input_dir / "split-plan.json"
    payload = {
        "schema": PATCH_SWARM_SPLIT_SCHEMA,
        "run_id": "taskstream-fixture",
        "request_id": "request-taskstream-fixture",
        "title": "Fixture Patch Swarm taskstream handoff",
        "base_commit": base_commit,
        "created_at": timestamp,
        "tasks": [
            {
                "task_id": "task-src-helper",
                "title": "Add bounded helper",
                "summary": "Implement a small helper in owned fixture source.",
                "route": "agent-work",
                "worker_profile": "codex",
                "priority": "normal",
                "owned_paths": ["src/fixture_helper.py"],
                "touched_path_candidates": ["src/fixture_helper.py", "tests/test_fixture_helper.py"],
                "acceptance_contract": ["Helper exists and returns deterministic output.", "Targeted pytest passes."],
                "validation_commands": ["python3 -m json.tool workspace/runs/parallel-delivery/taskstream-fixture/work-packages/task-src-helper/story.json"],
                "evidence_files": ["workspace/runs/parallel-delivery/taskstream-fixture/evidence/task-src-helper-validation.txt"],
                "handoff_notes": "Bounded implementation task. Preserve unrelated hunks.",
                "risk_flags": [],
            },
            {
                "task_id": "task-tests",
                "title": "Add fixture tests",
                "summary": "Add deterministic tests for the bounded helper.",
                "route": "agent-work",
                "worker_profile": "codex",
                "priority": "normal",
                "owned_paths": ["tests/test_fixture_helper.py"],
                "touched_path_candidates": ["tests/test_fixture_helper.py"],
                "acceptance_contract": ["Tests cover the helper behavior.", "Targeted pytest passes."],
                "validation_commands": ["python3 -m json.tool workspace/runs/parallel-delivery/taskstream-fixture/work-packages/task-tests/story.json"],
                "evidence_files": ["workspace/runs/parallel-delivery/taskstream-fixture/evidence/task-tests-validation.txt"],
                "handoff_notes": "Test-only task. Preserve unrelated hunks.",
                "risk_flags": [],
            },
            {
                "task_id": "task-evidence-only",
                "title": "Collect handoff evidence",
                "summary": "Write and review fixture taskstream handoff evidence.",
                "route": "manifest-only",
                "worker_profile": "docs-evidence-writer",
                "priority": "normal",
                "owned_paths": ["workspace/runs/parallel-delivery/taskstream-fixture/evidence"],
                "touched_path_candidates": ["workspace/runs/parallel-delivery/taskstream-fixture/evidence/task-evidence-only-validation.txt"],
                "acceptance_contract": ["Evidence path is declared.", "No live Taskstream mutation is required."],
                "validation_commands": [],
                "evidence_files": ["workspace/runs/parallel-delivery/taskstream-fixture/evidence/task-evidence-only-validation.txt"],
                "handoff_notes": "Evidence-only task. Keep as manifest-only unless explicitly promoted.",
                "risk_flags": ["manifest-only"],
            },
        ],
    }
    write_json(split_plan_path, payload)
    (input_dir / "README.md").write_text(
        "# Taskstream Fixture Input\n\nDeterministic Patch Swarm split plan for local agent-work handoff validation.\n",
        encoding="utf-8",
    )
    return split_plan_path
