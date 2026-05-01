#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALID_LANES = {"coordinator", "builder", "validator", "docs-evidence"}
VALID_RISKS = {"low", "medium", "high"}
VALID_MODES = {"plan_only", "dispatch_dry_run", "dispatch"}


class FactoryPlanError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FactoryPlanError(f"factory plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FactoryPlanError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FactoryPlanError("factory plan root must be an object")
    return payload


def require_text(payload: dict[str, Any], path: str, errors: list[str]) -> str:
    cursor: Any = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            errors.append(f"missing field: {path}")
            return ""
        cursor = cursor[part]
    if not isinstance(cursor, str) or not cursor.strip():
        errors.append(f"field must be non-empty text: {path}")
        return ""
    return cursor.strip()


def require_list(payload: dict[str, Any], path: str, errors: list[str]) -> list[Any]:
    cursor: Any = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            errors.append(f"missing field: {path}")
            return []
        cursor = cursor[part]
    if not isinstance(cursor, list) or not cursor:
        errors.append(f"field must be a non-empty list: {path}")
        return []
    return cursor


def validate_dependencies(tasks: list[dict[str, Any]], errors: list[str]) -> None:
    task_ids = [str(task.get("id") or "") for task in tasks]
    task_id_set = set(task_ids)
    if len(task_ids) != len(task_id_set):
        errors.append("task ids must be unique")
    graph: dict[str, list[str]] = {}
    for task in tasks:
        task_id = str(task.get("id") or "")
        deps = task.get("dependencies") or []
        if not isinstance(deps, list):
            errors.append(f"task {task_id}: dependencies must be a list")
            deps = []
        graph[task_id] = [str(dep) for dep in deps]
        for dep in graph[task_id]:
            if dep not in task_id_set:
                errors.append(f"task {task_id}: unknown dependency {dep}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            errors.append("dependency cycle: " + " -> ".join([*trail, task_id]))
            return
        visiting.add(task_id)
        for dep in graph.get(task_id, []):
            visit(dep, [*trail, task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_ids:
        visit(task_id, [])


def validate_owned_paths(tasks: list[dict[str, Any]], errors: list[str], shared_paths: set[str]) -> None:
    owners: dict[str, str] = {}
    for task in tasks:
        task_id = str(task.get("id") or "")
        for raw_path in task.get("owned_scope") or []:
            owned_path = str(raw_path).strip()
            if not owned_path:
                continue
            if owned_path in shared_paths:
                continue
            previous = owners.get(owned_path)
            if previous and previous != task_id:
                errors.append(f"owned path overlap: {owned_path} claimed by {previous} and {task_id}")
            owners[owned_path] = task_id


def validate_task(task: Any, index: int, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        errors.append(f"tasks[{index}] must be an object")
        return None
    task_id = require_text(task, "id", errors)
    require_text(task, "title", errors)
    require_text(task, "goal", errors)
    lane = require_text(task, "lane", errors)
    if lane and lane not in VALID_LANES:
        errors.append(f"task {task_id}: lane must be one of {', '.join(sorted(VALID_LANES))}")
    require_text(task, "node", errors)
    risk = require_text(task, "risk", errors)
    if risk and risk not in VALID_RISKS:
        errors.append(f"task {task_id}: risk must be one of {', '.join(sorted(VALID_RISKS))}")
    require_list(task, "owned_scope", errors)
    require_list(task, "expected_outputs", errors)
    require_list(task, "validation_commands", errors)
    if not isinstance(task.get("no_model_eligible"), bool):
        errors.append(f"task {task_id}: no_model_eligible must be boolean")
    if "dependencies" in task and not isinstance(task.get("dependencies"), list):
        errors.append(f"task {task_id}: dependencies must be a list")
    for output_index, output in enumerate(task.get("expected_outputs") or [], start=1):
        if isinstance(output, str):
            continue
        if isinstance(output, dict) and str(output.get("path") or "").strip():
            continue
        errors.append(f"task {task_id}: expected_outputs[{output_index}] must be a path string or object with path")
    return task


def validate_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    schema = require_text(payload, "schema_version", errors)
    if schema and schema != "factory-plan/v1":
        errors.append("schema_version must be factory-plan/v1")
    require_text(payload, "run_id", errors)
    require_text(payload, "request.raw", errors)
    require_text(payload, "request.normalized_goal", errors)
    require_text(payload, "package", errors)
    mode = require_text(payload, "mode", errors)
    if mode and mode not in VALID_MODES:
        errors.append(f"mode must be one of {', '.join(sorted(VALID_MODES))}")
    risk = require_text(payload, "risk", errors)
    if risk and risk not in VALID_RISKS:
        errors.append(f"risk must be one of {', '.join(sorted(VALID_RISKS))}")
    require_text(payload, "evidence.run_dir", errors)
    require_text(payload, "evidence.summary", errors)

    budget = payload.get("budget")
    if not isinstance(budget, dict):
        errors.append("missing object: budget")
    else:
        for field in ("ai_call_budget", "strong_model_calls_allowed", "cheap_worker_calls_allowed"):
            if not isinstance(budget.get(field), int):
                errors.append(f"budget.{field} must be integer")

    integration = payload.get("integration")
    if not isinstance(integration, dict):
        errors.append("missing object: integration")
    else:
        if not isinstance(integration.get("required_docs"), list):
            errors.append("integration.required_docs must be a list")

    validation = payload.get("validation")
    if not isinstance(validation, dict):
        errors.append("missing object: validation")
    else:
        if not isinstance(validation.get("requires_screenshots"), bool):
            errors.append("validation.requires_screenshots must be boolean")
        if not isinstance(validation.get("requires_api_smoke"), bool):
            errors.append("validation.requires_api_smoke must be boolean")
        if not isinstance(validation.get("requires_human_review"), bool):
            errors.append("validation.requires_human_review must be boolean")

    raw_tasks = require_list(payload, "tasks", errors)
    tasks = []
    for index, raw_task in enumerate(raw_tasks):
        task = validate_task(raw_task, index, errors)
        if task:
            tasks.append(task)
    shared_paths = {str(item) for item in payload.get("shared_paths") or []}
    validate_dependencies(tasks, errors)
    validate_owned_paths(tasks, errors, shared_paths)
    return errors


def command_validate(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    try:
        payload = load_json(Path(args.plan))
    except FactoryPlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    errors = validate_plan(payload)
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    result = {
        "ok": not errors,
        "errors": errors,
        "plan": rel(Path(args.plan)),
        "tasks": len(payload.get("tasks") or []),
        "stats": {
            "duration_ms": duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_by": "factory-plan",
            "validated_at": now_iso(),
        },
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"status: {'ok' if result['ok'] else 'blocked'}")
        print(f"tasks: {result['tasks']}")
        print(f"duration_ms: {duration_ms}")
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Cento Factory factory-plan.json artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate a factory-plan.json file.")
    validate.add_argument("plan")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
