#!/usr/bin/env python3
"""Minimal local workset runner for non-overlapping Cento Build tasks."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cento_build  # noqa: E402
import cento_openai_worker  # noqa: E402

SCHEMA_WORKSET = "cento.workset.v1"
SCHEMA_WORKSET_RECEIPT = "cento.workset_receipt.v1"
SCHEMA_MATERIALIZATION_RECEIPT = "cento.artifact_materialization_receipt.v1"
WORKSET_ROOT = ROOT / ".cento" / "worksets"
API_CONFIG_PATH = ROOT / ".cento" / "api_workers.yaml"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return cento_build.rel(path)


def write_json(path: Path, payload: Any) -> None:
    cento_build.write_json(path, payload)


def read_json(path: Path) -> dict[str, Any]:
    return cento_build.read_json(path)


def append_event(workset_dir: Path, event: str, payload: dict[str, Any] | None = None) -> None:
    workset_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": now_iso(), "event": event}
    if payload:
        row.update(payload)
    with (workset_dir / "events.ndjson").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def task_id(task: dict[str, Any]) -> str:
    value = task.get("id")
    if not isinstance(value, str) or not value:
        raise cento_build.BuildError("each workset task requires id")
    return value


def task_dependencies(task: dict[str, Any]) -> list[str]:
    raw = task.get("depends_on", task.get("dependencies", []))
    if raw is None:
        raw = []
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise cento_build.BuildError(f"task {task_id(task)} dependencies must be a list of task ids")
    return list(raw)


def task_write_paths(task: dict[str, Any]) -> list[str]:
    raw = task.get("write_paths")
    if not isinstance(raw, list) or not raw:
        raise cento_build.BuildError(f"task {task_id(task)} write_paths must be a non-empty list")
    paths = cento_build.normalize_paths([str(item) for item in raw])
    for path in paths:
        if cento_build.has_glob(path):
            raise cento_build.BuildError(f"task {task_id(task)} uses glob write_path; workset v1 requires explicit exclusive paths: {path}")
    return paths


def task_read_paths(task: dict[str, Any], workset: dict[str, Any]) -> list[str]:
    raw = task.get("read_paths", workset.get("read_paths", []))
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise cento_build.BuildError(f"task {task_id(task)} read_paths must be a list")
    return cento_build.normalize_paths([str(item) for item in raw])


def task_routes(task: dict[str, Any], workset: dict[str, Any]) -> list[str]:
    raw = task.get("routes", task.get("route", workset.get("routes", workset.get("route", []))))
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return [str(item) for item in raw]
    raise cento_build.BuildError(f"task {task_id(task)} routes must be a string or list")


def path_overlaps(left: str, right: str) -> bool:
    left = cento_build.normalize_path(left)
    right = cento_build.normalize_path(right)
    return cento_build.path_matches(left, right) or cento_build.path_matches(right, left)


def load_workset(path: Path) -> dict[str, Any]:
    if not path.is_absolute():
        path = ROOT / path
    return cento_build.read_json(path)


def validate_workset(workset: dict[str, Any], *, allow_missing_write_paths: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    schema = workset.get("schema_version")
    if schema not in {None, SCHEMA_WORKSET}:
        errors.append(f"schema_version must be {SCHEMA_WORKSET}")
    workset_id = workset.get("id")
    if not isinstance(workset_id, str) or not workset_id:
        errors.append("id is required")
    mode = str(workset.get("mode") or "fast")
    if mode not in cento_build.load_modes():
        errors.append(f"mode must exist in .cento/modes.yaml: {mode}")
    tasks = workset.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty list")
        tasks = []

    by_id: dict[str, dict[str, Any]] = {}
    writes_by_task: dict[str, list[str]] = {}
    for item in tasks:
        if not isinstance(item, dict):
            errors.append("each task must be an object")
            continue
        try:
            tid = task_id(item)
        except cento_build.BuildError as exc:
            errors.append(str(exc))
            continue
        if tid in by_id:
            errors.append(f"duplicate task id: {tid}")
            continue
        by_id[tid] = item
        try:
            writes_by_task[tid] = task_write_paths(item)
        except cento_build.BuildError as exc:
            errors.append(str(exc))
            continue
        for write_path in writes_by_task[tid]:
            if not allow_missing_write_paths and not cento_build.path_exists(write_path):
                errors.append(f"task {tid} write path does not exist: {write_path}")
            if cento_build.path_is_protected(write_path, cento_build.DEFAULT_PROTECTED_PATHS):
                errors.append(f"task {tid} write path is protected: {write_path}")

    task_ids = set(by_id)
    for tid, task in by_id.items():
        try:
            for dep in task_dependencies(task):
                if dep not in task_ids:
                    errors.append(f"task {tid} depends on unknown task: {dep}")
        except cento_build.BuildError as exc:
            errors.append(str(exc))

    ids = sorted(writes_by_task)
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1 :]:
            for left in writes_by_task[left_id]:
                for right in writes_by_task[right_id]:
                    if path_overlaps(left, right):
                        errors.append(
                            f"overlapping write paths are rejected in workset v1: {left_id}:{left} overlaps {right_id}:{right}"
                        )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(tid: str) -> None:
        if tid in visited:
            return
        if tid in visiting:
            errors.append(f"dependency cycle includes task: {tid}")
            return
        visiting.add(tid)
        for dep in task_dependencies(by_id[tid]):
            if dep in by_id:
                visit(dep)
        visiting.remove(tid)
        visited.add(tid)

    for tid in list(by_id):
        try:
            visit(tid)
        except cento_build.BuildError as exc:
            errors.append(str(exc))

    return {
        "status": "passed" if not errors else "failed",
        "errors": sorted(set(errors)),
        "warnings": warnings,
        "task_count": len(by_id),
        "write_paths": writes_by_task,
    }


def normalize_workset(workset: dict[str, Any]) -> dict[str, Any]:
    mode = str(workset.get("mode") or "fast")
    normalized_tasks: list[dict[str, Any]] = []
    for task in workset.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        normalized_tasks.append(
            {
                "id": task_id(task),
                "worker_id": str(task.get("worker_id") or task_id(task)),
                "task": str(task.get("task") or task.get("title") or task_id(task)),
                "description": str(task.get("description") or task.get("task") or task.get("title") or task_id(task)),
                "write_paths": task_write_paths(task),
                "read_paths": task_read_paths(task, workset),
                "routes": task_routes(task, workset),
                "depends_on": task_dependencies(task),
                "runtime_profile": str(task.get("runtime_profile") or task.get("profile") or ""),
                "api_profile": str(task.get("api_profile") or ""),
                "output_schema": str(task.get("output_schema") or ""),
                "artifact_type": str(task.get("artifact_type") or ""),
                "cost_usd_estimate": task.get("cost_usd_estimate"),
            }
        )
    return {
        "schema_version": SCHEMA_WORKSET,
        "id": str(workset.get("id")),
        "mode": mode,
        "max_parallel": int(workset.get("max_parallel") or 1),
        "tasks": normalized_tasks,
    }


def make_task_manifest(
    workset: dict[str, Any],
    task: dict[str, Any],
    *,
    run_id: str,
    validation_tier: str | None,
    allow_dirty_owned: bool,
    allow_creates: bool = False,
) -> tuple[Path, dict[str, Any]]:
    build_id = f"workset_{cento_build.slugify(run_id)}_{cento_build.slugify(task['id'])}"
    build_args = argparse.Namespace(
        task=task["task"],
        description=task["description"],
        mode=workset["mode"],
        write=task["write_paths"],
        read=task["read_paths"],
        route=task["routes"],
        protect=[],
        validation=validation_tier,
        id=build_id,
        allow_dirty_owned=allow_dirty_owned,
    )
    manifest = cento_build.create_manifest(build_args)
    if allow_creates:
        policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
        manifest["policies"] = {**policies, "allow_creates": True}
    manifest["workset"] = {"id": workset["id"], "run_id": run_id, "task_id": task["id"]}
    build_dir = cento_build.BUILD_ROOT / str(manifest["id"])
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = build_dir / "manifest.json"
    prompt_path = build_dir / "builder.prompt.md"
    write_json(manifest_path, manifest)
    prompt_path.write_text(cento_build.render_builder_prompt(manifest), encoding="utf-8")
    cento_build.append_event(build_dir, "build_manifest_created", {"manifest_id": manifest["id"], "source": "cento_workset"})
    cento_build.append_event(build_dir, "builder_prompt_created", {"path": rel(prompt_path)})
    return manifest_path, manifest


def run_task_worker(
    workset: dict[str, Any],
    task: dict[str, Any],
    *,
    run_id: str,
    runtime_profile: str,
    runtime: str,
    fixture_case: str,
    worker_timeout: int | None,
    validation_tier: str | None,
    allow_dirty_owned: bool,
    allow_unsafe_command: bool,
    command_template: str | None,
) -> dict[str, Any]:
    manifest_path, manifest = make_task_manifest(
        workset,
        task,
        run_id=run_id,
        validation_tier=validation_tier,
        allow_dirty_owned=allow_dirty_owned,
    )
    worker_result = cento_build.run_build_worker(
        manifest_path,
        worker_id="builder_1",
        runtime=runtime,
        use_worktree=True,
        timeout=worker_timeout,
        allow_dirty_owned=allow_dirty_owned,
        fixture_case=fixture_case,
        runtime_profile_name=runtime_profile,
        allow_unsafe_command=allow_unsafe_command,
        command_template=command_template,
    )
    return {
        "task_id": task["id"],
        "manifest": rel(manifest_path),
        "build_id": manifest.get("id"),
        "build_dir": rel(cento_build.build_dir_for_manifest(manifest, manifest_path)),
        "worker": worker_result,
    }


def load_api_worker_config(path: Path = API_CONFIG_PATH) -> dict[str, Any]:
    return cento_openai_worker.load_api_config(path)


def api_openai_config(config: dict[str, Any]) -> dict[str, Any]:
    raw = config.get("openai") if isinstance(config.get("openai"), dict) else {}
    return dict(raw)


def api_profile_name_for_task(task: dict[str, Any], default_profile: str) -> str:
    return str(task.get("api_profile") or task.get("runtime_profile") or default_profile)


def api_output_schema_for_profile(config: dict[str, Any], profile_name: str, task: dict[str, Any]) -> str:
    if task.get("output_schema"):
        return str(task["output_schema"])
    profile = cento_openai_worker.profile_config(config, profile_name)
    return str(profile.get("output_schema") or "docs_section.v1")


def api_cost_estimate(config: dict[str, Any], profile_name: str, task: dict[str, Any]) -> float:
    openai_config = api_openai_config(config)
    raw_default = openai_config.get("cost_usd_estimate_per_request")
    default_estimate = max(0.0, float(raw_default)) if isinstance(raw_default, (int, float)) else 0.10
    estimate = default_estimate
    raw_task = task.get("cost_usd_estimate")
    if isinstance(raw_task, (int, float)):
        estimate = max(0.0, float(raw_task))
    else:
        profile = cento_openai_worker.profile_config(config, profile_name)
        raw_profile = profile.get("cost_usd_estimate")
        if isinstance(raw_profile, (int, float)):
            estimate = max(0.0, float(raw_profile))
    raw_minimum = openai_config.get("minimum_cost_usd_estimate_per_request", default_estimate)
    minimum = max(0.0, float(raw_minimum)) if isinstance(raw_minimum, (int, float)) else default_estimate
    return max(estimate, minimum)


def api_positive_int_limit(config: dict[str, Any], profile_name: str, task: dict[str, Any], key: str, default: int) -> int:
    profile = cento_openai_worker.profile_config(config, profile_name)
    openai_config = api_openai_config(config)
    value: Any = task.get(key)
    if value is None:
        value = profile.get(key)
    if value is None:
        value = openai_config.get(key)
    if value is None:
        value = default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise cento_build.BuildError(f"{key} must be an integer") from exc
    if parsed <= 0:
        raise cento_build.BuildError(f"{key} must be greater than zero")
    return parsed


def write_zero_cost_receipt(worker_dir: Path, task: dict[str, Any], runtime: str, status: str) -> Path:
    path = worker_dir / "cost_receipt.json"
    write_json(
        path,
        {
            "schema_version": "cento.api_worker_cost_receipt.v1",
            "worker_id": str(task.get("worker_id") or task["id"]),
            "task_id": task["id"],
            "provider": runtime,
            "cost_usd_estimate": 0.0,
            "usage": {},
            "pricing": {},
            "estimate_method": "local_runtime_zero_cost",
            "status": status,
            "written_at": now_iso(),
        },
    )
    return path


def write_blocked_worker_receipts(
    worker_dir: Path,
    task: dict[str, Any],
    *,
    runtime: str,
    reason: str,
    cost_estimate: float,
) -> tuple[Path, Path]:
    worker_id = str(task.get("worker_id") or task["id"])
    worker_dir.mkdir(parents=True, exist_ok=True)
    cost_path = worker_dir / "cost_receipt.json"
    receipt_path = worker_dir / "worker_receipt.json"
    written_at = now_iso()
    write_json(
        cost_path,
        {
            "schema_version": "cento.api_worker_cost_receipt.v1",
            "worker_id": worker_id,
            "task_id": task["id"],
            "provider": runtime,
            "cost_usd_estimate": 0.0,
            "reserved_cost_usd_estimate": cost_estimate,
            "usage": {},
            "pricing": {},
            "estimate_method": "not_dispatched_budget_blocked",
            "status": "budget_blocked",
            "written_at": written_at,
        },
    )
    write_json(
        receipt_path,
        {
            "schema_version": "cento.api_worker_receipt.v1",
            "worker_id": worker_id,
            "task_id": task["id"],
            "status": "budget_blocked",
            "request": None,
            "response": None,
            "artifact": None,
            "cost_receipt": rel(cost_path),
            "started_at": written_at,
            "completed_at": written_at,
            "errors": [reason],
        },
    )
    return cost_path, receipt_path


def write_failed_api_worker_receipts(
    worker_dir: Path,
    task: dict[str, Any],
    *,
    reason: str,
    cost_estimate: float,
) -> tuple[Path, Path]:
    worker_id = str(task.get("worker_id") or task["id"])
    worker_dir.mkdir(parents=True, exist_ok=True)
    cost_path = worker_dir / "cost_receipt.json"
    receipt_path = worker_dir / "worker_receipt.json"
    written_at = now_iso()
    write_json(
        cost_path,
        {
            "schema_version": "cento.api_worker_cost_receipt.v1",
            "worker_id": worker_id,
            "task_id": task["id"],
            "provider": "openai",
            "cost_usd_estimate": 0.0,
            "reserved_cost_usd_estimate": cost_estimate,
            "usage": {},
            "pricing": {},
            "estimate_method": "api_worker_failed_before_cost_receipt",
            "status": "failed",
            "written_at": written_at,
        },
    )
    write_json(
        receipt_path,
        {
            "schema_version": "cento.api_worker_receipt.v1",
            "worker_id": worker_id,
            "task_id": task["id"],
            "status": "failed",
            "request": rel(worker_dir / "request.json") if (worker_dir / "request.json").exists() else None,
            "response": rel(worker_dir / "response.json") if (worker_dir / "response.json").exists() else None,
            "artifact": rel(worker_dir / "artifact.json") if (worker_dir / "artifact.json").exists() else None,
            "cost_receipt": rel(cost_path),
            "started_at": written_at,
            "completed_at": written_at,
            "errors": [reason],
        },
    )
    return cost_path, receipt_path


def read_context_snippets(paths: list[str], *, max_files: int = 8, max_bytes_per_file: int = 4000) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    for item in paths[:max_files]:
        try:
            normalized = cento_build.normalize_path(item)
        except cento_build.BuildError:
            continue
        path = ROOT / normalized
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()[:max_bytes_per_file]
            text = data.decode("utf-8", errors="replace")
        except OSError:
            continue
        snippets.append({"path": normalized, "content": text, "truncated": path.stat().st_size > max_bytes_per_file})
    return snippets


def build_api_task_request(
    workset: dict[str, Any],
    task: dict[str, Any],
    *,
    run_id: str,
    profile_name: str,
    output_schema: str,
) -> dict[str, Any]:
    read_paths = [*task.get("read_paths", []), *task.get("write_paths", [])]
    return {
        "schema_version": "cento.api_worker_request.v1",
        "workset_id": workset["id"],
        "run_id": run_id,
        "task_id": task["id"],
        "worker_id": str(task.get("worker_id") or task["id"]),
        "task": task["task"],
        "description": task["description"],
        "depends_on": task["depends_on"],
        "routes": task["routes"],
        "write_paths": task["write_paths"],
        "read_paths": task["read_paths"],
        "api_profile": profile_name,
        "output_schema": output_schema,
        "artifact_type": cento_openai_worker.artifact_type_for_schema(output_schema),
        "context_snippets": read_context_snippets(read_paths),
        "rules": [
            "Return only the structured output requested by the schema.",
            "Do not mutate repository files.",
            "If proposing file contents, include complete UTF-8 content for owned paths only.",
        ],
    }


def run_api_task_worker(
    workset: dict[str, Any],
    task: dict[str, Any],
    *,
    run_id: str,
    workset_dir: Path,
    api_config: dict[str, Any],
    api_config_path: Path,
    profile_name: str,
    output_schema: str,
    cost_estimate: float,
    max_input_chars: int,
    max_output_tokens: int,
    timeout: int | None,
    retry_attempts: int | None,
    validation_tier: str | None,
    allow_dirty_owned: bool,
) -> dict[str, Any]:
    manifest_path, manifest = make_task_manifest(
        workset,
        task,
        run_id=run_id,
        validation_tier=validation_tier,
        allow_dirty_owned=allow_dirty_owned,
        allow_creates=True,
    )
    worker_dir = workset_dir / "workers" / str(task.get("worker_id") or task["id"])
    worker_dir.mkdir(parents=True, exist_ok=True)
    task_request = build_api_task_request(workset, task, run_id=run_id, profile_name=profile_name, output_schema=output_schema)
    task_request_path = worker_dir / "task_request.json"
    write_json(task_request_path, task_request)
    openai_config = api_openai_config(api_config)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "cento_openai_worker.py"),
        "run",
        rel(task_request_path),
        "--out-dir",
        rel(worker_dir),
        "--profile",
        profile_name,
        "--config",
        rel(api_config_path),
        "--output-schema",
        output_schema,
        "--worker-id",
        str(task.get("worker_id") or task["id"]),
        "--reserved-cost-usd",
        f"{cost_estimate:.6f}",
        "--json",
    ]
    effective_timeout = timeout or int(openai_config.get("timeout_seconds") or 45)
    command.extend(["--timeout", str(effective_timeout)])
    effective_retries = retry_attempts if retry_attempts is not None else int(openai_config.get("retry_attempts") or 0)
    command.extend(["--retry-attempts", str(effective_retries)])
    command.extend(["--max-input-chars", str(max_input_chars)])
    command.extend(["--max-output-tokens", str(max_output_tokens)])
    started = time.perf_counter()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=effective_timeout * (effective_retries + 1) + 10, check=False)
    except subprocess.TimeoutExpired as exc:
        reason = f"api worker timed out after {exc.timeout} seconds"
        cost_path, receipt_path = write_failed_api_worker_receipts(worker_dir, task, reason=reason, cost_estimate=cost_estimate)
        return {
            "task_id": task["id"],
            "manifest": rel(manifest_path),
            "build_id": manifest.get("id"),
            "build_dir": rel(cento_build.build_dir_for_manifest(manifest, manifest_path)),
            "api_worker_dir": rel(worker_dir),
            "api_artifact": rel(worker_dir / "artifact.json") if (worker_dir / "artifact.json").exists() else None,
            "api_cost_receipt": rel(cost_path),
            "api_worker_receipt": rel(receipt_path),
            "profile": profile_name,
            "output_schema": output_schema,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "status": "failed",
            "errors": [reason],
        }
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    artifact_path = worker_dir / "artifact.json"
    cost_path = worker_dir / "cost_receipt.json"
    worker_receipt_path = worker_dir / "worker_receipt.json"
    result: dict[str, Any] = {
        "task_id": task["id"],
        "manifest": rel(manifest_path),
        "build_id": manifest.get("id"),
        "build_dir": rel(cento_build.build_dir_for_manifest(manifest, manifest_path)),
        "api_worker_dir": rel(worker_dir),
        "api_artifact": rel(artifact_path) if artifact_path.exists() else None,
        "api_cost_receipt": rel(cost_path) if cost_path.exists() else None,
        "api_worker_receipt": rel(worker_receipt_path) if worker_receipt_path.exists() else None,
        "profile": profile_name,
        "output_schema": output_schema,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_ms": duration_ms,
    }
    if proc.returncode != 0:
        errors: list[str] = []
        if artifact_path.exists():
            try:
                artifact = read_json(artifact_path)
                errors.extend([str(item) for item in artifact.get("errors") or []])
            except cento_build.BuildError:
                pass
        if not errors:
            errors.append(proc.stderr.strip() or proc.stdout.strip() or "api worker failed")
        result["status"] = "failed"
        result["errors"] = errors
        return result

    materialized = materialize_api_artifact(
        artifact_path,
        manifest_path=manifest_path,
        allow_dirty_owned=allow_dirty_owned,
    )
    result["status"] = "completed" if materialized.get("status") == "materialized" else "failed"
    result["materialization_receipt"] = materialized.get("materialization_receipt")
    result["worker"] = {
        "status": "accepted" if materialized.get("status") == "materialized" else "rejected",
        "worker_status": "completed" if materialized.get("status") == "materialized" else "failed",
        "build_id": manifest.get("id"),
        "worker_id": "builder_1",
        "runtime": "api-openai-materializer",
        "worker_dir": materialized.get("worker_dir"),
        "worker_artifact": materialized.get("worker_artifact"),
        "patch_bundle": materialized.get("patch_bundle"),
        "patch": materialized.get("patch"),
        "touched_paths": materialized.get("touched_paths") or [],
        "errors": materialized.get("errors") or [],
    }
    if result["status"] != "completed":
        result["errors"] = materialized.get("errors") or ["artifact materialization failed"]
    return result


def artifact_content_entries(artifact: dict[str, Any]) -> list[dict[str, str]]:
    content = artifact.get("content")
    if not isinstance(content, dict):
        raise cento_build.BuildError("artifact content must be an object")
    entries: list[dict[str, str]] = []
    for key in ("owned_path_contents", "files", "file_changes"):
        raw = content.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                raise cento_build.BuildError(f"artifact content {key} entries must be objects")
            path = item.get("path")
            file_content = item.get("content")
            if isinstance(path, str) and isinstance(file_content, str):
                entries.append({"path": cento_build.normalize_path(path), "content": file_content})
    if entries:
        return entries
    owned_paths = [cento_build.normalize_path(str(item)) for item in artifact.get("owned_paths") or []]
    if len(owned_paths) != 1:
        raise cento_build.BuildError("artifact without owned_path_contents must own exactly one path")
    return [{"path": owned_paths[0], "content": json.dumps(content, indent=2, sort_keys=False) + "\n"}]


def create_materialization_manifest(
    artifact: dict[str, Any],
    *,
    build_id: str | None,
    validation_tier: str | None,
    allow_dirty_owned: bool,
) -> tuple[Path, dict[str, Any]]:
    owned_paths = [cento_build.normalize_path(str(item)) for item in artifact.get("owned_paths") or []]
    if not owned_paths:
        raise cento_build.BuildError("artifact owned_paths must not be empty")
    task_id = str(artifact.get("task_id") or artifact.get("worker_id") or "api_artifact")
    build_args = argparse.Namespace(
        task=f"Materialize API artifact {task_id}",
        description=f"Materialize structured API worker artifact for {task_id}.",
        mode="fast",
        write=owned_paths,
        read=[],
        route=[],
        protect=[],
        validation=validation_tier,
        id=build_id or f"api_artifact_{cento_build.slugify(task_id)}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        allow_dirty_owned=allow_dirty_owned,
    )
    manifest = cento_build.create_manifest(build_args)
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    manifest["policies"] = {**policies, "allow_creates": True}
    build_dir = cento_build.BUILD_ROOT / str(manifest["id"])
    build_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = build_dir / "manifest.json"
    write_json(manifest_path, manifest)
    (build_dir / "builder.prompt.md").write_text(cento_build.render_builder_prompt(manifest), encoding="utf-8")
    return manifest_path, manifest


def materialize_api_artifact(
    artifact_path: Path,
    *,
    manifest_path: Path | None = None,
    build_id: str | None = None,
    validation_tier: str | None = None,
    allow_dirty_owned: bool = False,
) -> dict[str, Any]:
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    started_at = now_iso()
    errors: list[str] = []
    warnings: list[str] = []
    worktree_path: Path | None = None
    worktree_removed = False
    try:
        artifact = read_json(artifact_path)
        artifact_errors = cento_openai_worker.validate_json_schema(artifact, cento_openai_worker.api_worker_artifact_schema())
        if artifact_errors:
            raise cento_build.BuildError("api worker artifact schema validation failed: " + "; ".join(artifact_errors))
        if artifact.get("status") != "completed":
            raise cento_build.BuildError("api worker artifact is not completed: " + "; ".join([str(item) for item in artifact.get("errors") or []]))
        if manifest_path is None:
            manifest_path, manifest = create_materialization_manifest(
                artifact,
                build_id=build_id,
                validation_tier=validation_tier,
                allow_dirty_owned=allow_dirty_owned,
            )
        else:
            if not manifest_path.is_absolute():
                manifest_path = ROOT / manifest_path
            manifest = read_json(manifest_path)
            policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
            if not policies.get("allow_creates"):
                manifest["policies"] = {**policies, "allow_creates": True}
                write_json(manifest_path, manifest)
        build_dir = cento_build.build_dir_for_manifest(manifest, manifest_path)
        worker_id = cento_build.artifact_worker_id(manifest)
        worker_dir = cento_build.worker_artifact_dir(manifest, worker_id, build_dir)
        worker_dir.mkdir(parents=True, exist_ok=True)
        patch_path = worker_dir / "patch.diff"
        bundle_path = worker_dir / "patch_bundle.json"
        build_worker_artifact_path = worker_dir / "worker_artifact.json"
        handoff_path = worker_dir / "handoff.md"
        for stale in (patch_path, bundle_path, build_worker_artifact_path, handoff_path):
            if stale.exists():
                stale.unlink()

        entries = artifact_content_entries(artifact)
        artifact_owned = [cento_build.normalize_path(str(item)) for item in artifact.get("owned_paths") or []]
        manifest_owned = cento_build.manifest_write_paths(manifest)
        for entry in entries:
            path = entry["path"]
            if not cento_build.path_allowed(path, artifact_owned):
                raise cento_build.BuildError(f"artifact wants unowned path: {path}")
            if not cento_build.path_allowed(path, manifest_owned):
                raise cento_build.BuildError(f"artifact path outside manifest scope: {path}")
        current_base = cento_build.git_value(["rev-parse", "HEAD"], "HEAD")
        source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
        base_ref = str(source.get("base_ref") or "HEAD")
        worktree_ref = current_base if base_ref == "HEAD" else base_ref
        worktree_path, worktree_result = cento_build.create_isolated_worktree(worktree_ref, f"{manifest.get('id')}-materializer")
        if worktree_path is None:
            detail = (str(worktree_result["stderr"]) or str(worktree_result["stdout"])).strip()
            raise cento_build.BuildError("materializer worktree creation failed: " + detail)
        for entry in entries:
            target = worktree_path / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry["content"], encoding="utf-8")
        entry_paths = [entry["path"] for entry in entries]
        add_intent = cento_build.run(["git", "add", "-N", "--", *entry_paths], cwd=worktree_path, timeout=120)
        if add_intent["exit_code"] != 0:
            warnings.append("git add -N failed: " + (str(add_intent["stderr"]) or str(add_intent["stdout"])).strip())
        diff_result = cento_build.run(["git", "diff", "--binary", "--", *entry_paths], cwd=worktree_path, timeout=120)
        if diff_result["exit_code"] != 0:
            raise cento_build.BuildError("materializer diff failed: " + (str(diff_result["stderr"]) or str(diff_result["stdout"])).strip())
        patch_text = str(diff_result["stdout"])
        patch_path.write_text(patch_text, encoding="utf-8")
        if not patch_text.strip():
            raise cento_build.BuildError("artifact materializer produced no patch")
        analysis = cento_build.analyze_patch(patch_path)
        touched_paths = [str(item) for item in analysis.get("paths") or []]
        protected_paths = cento_build.manifest_protected_paths(manifest)
        policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
        patch_errors = cento_build.patch_policy_rejections(analysis, manifest_owned, protected_paths, policies)
        unowned_paths = [path for path in touched_paths if not cento_build.path_allowed(path, manifest_owned)]
        protected_touched = [path for path in touched_paths if cento_build.path_is_protected(path, protected_paths)]
        if patch_errors or unowned_paths or protected_touched:
            detail = patch_errors + [f"unowned paths touched: {', '.join(unowned_paths)}"] if unowned_paths else patch_errors
            if protected_touched:
                detail.append("protected paths touched: " + ", ".join(protected_touched))
            raise cento_build.BuildError("; ".join(detail))
        bundle_path = cento_build.synthesize_patch_bundle(
            manifest,
            patch_path,
            touched_paths,
            build_dir,
            out_path=bundle_path,
            worker_id=worker_id,
            summary=f"Materialized from API artifact {rel(artifact_path)}.",
        )
        build_worker_artifact = {
            "schema_version": cento_build.SCHEMA_WORKER_ARTIFACT,
            "manifest_id": manifest.get("id"),
            "manifest_path": rel(manifest_path),
            "worker_id": worker_id,
            "worker_type": "local",
            "role": "builder",
            "runtime": "api-openai-materializer",
            "runtime_profile": None,
            "fixture_case": None,
            "status": "completed",
            "base_ref": base_ref,
            "artifact_dir": rel(worker_dir),
            "patch_file": rel(patch_path),
            "patch_path": rel(patch_path),
            "patch_bundle": rel(bundle_path),
            "handoff": rel(handoff_path),
            "touched_paths": touched_paths,
            "owned_paths": [path for path in touched_paths if cento_build.path_allowed(path, manifest_owned)],
            "unowned_paths": [],
            "protected_paths_touched": [],
            "staged_paths": [],
            "dirty_unrelated_paths": [],
            "rejections": [],
            "assumptions": ["Source content came from a structured API worker artifact."],
            "validation": {"status": "not_run", "reason": "integration validates patch"},
            "risks": [],
            "warnings": warnings,
            "stdout_path": None,
            "stderr_path": None,
            "duration_ms": 0,
            "runtime_limits": {},
            "runtime_result": {"status": "passed", "exit_code": 0},
            "launch_head": worktree_ref,
            "worker_head": worktree_ref,
            "started_at": started_at,
            "completed_at": now_iso(),
        }
        write_json(build_worker_artifact_path, build_worker_artifact)
        cento_build.write_worker_handoff(handoff_path, status="completed", runtime="api-openai-materializer", touched_paths=touched_paths, errors=[], warnings=warnings)
        status = "materialized"
    except cento_build.BuildError as exc:
        status = "failed"
        errors.append(str(exc))
        touched_paths = []
        build_dir = cento_build.BUILD_ROOT / (build_id or "api_artifact_failed")
        worker_dir = build_dir / "workers" / "builder_1"
        patch_path = worker_dir / "patch.diff"
        bundle_path = worker_dir / "patch_bundle.json"
        build_worker_artifact_path = worker_dir / "worker_artifact.json"
        manifest_path = manifest_path
    finally:
        remove_result = cento_build.remove_isolated_worktree(worktree_path)
        if remove_result is not None:
            worktree_removed = remove_result["exit_code"] == 0
            if not worktree_removed:
                warnings.append("materializer worktree cleanup failed: " + (str(remove_result["stderr"]) or str(remove_result["stdout"])).strip())

    receipt = {
        "schema_version": SCHEMA_MATERIALIZATION_RECEIPT,
        "status": status,
        "artifact": rel(artifact_path),
        "manifest": rel(manifest_path) if manifest_path else None,
        "worker_dir": rel(worker_dir),
        "worker_artifact": rel(build_worker_artifact_path) if build_worker_artifact_path.exists() else None,
        "patch": rel(patch_path) if patch_path.exists() else None,
        "patch_bundle": rel(bundle_path) if bundle_path.exists() else None,
        "touched_paths": touched_paths,
        "errors": errors,
        "warnings": warnings,
        "worktree_removed": worktree_removed if worktree_path else None,
        "started_at": started_at,
        "completed_at": now_iso(),
    }
    build_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = build_dir / "materialization_receipt.json"
    write_json(receipt_path, receipt)
    receipt["materialization_receipt"] = rel(receipt_path)
    return receipt


def run_integrate(manifest_path: Path, bundle_path: Path, *, allow_dirty_owned: bool) -> tuple[int, str, str]:
    args = [
        sys.executable,
        str(ROOT / "scripts" / "cento_build.py"),
        "integrate",
        rel(manifest_path),
        "--bundle",
        rel(bundle_path),
        "--worktree",
        "--dry-run",
    ]
    if allow_dirty_owned:
        args.append("--allow-dirty-owned")
    proc = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def write_receipt(workset_dir: Path, receipt: dict[str, Any]) -> Path:
    path = workset_dir / "workset_receipt.json"
    write_json(path, receipt)
    return path


def final_status(task_records: dict[str, dict[str, Any]]) -> str:
    if all(record.get("status") == "applied" for record in task_records.values()):
        return "completed"
    if any(record.get("status") in {"blocked", "rejected", "failed", "dependency_blocked"} for record in task_records.values()):
        return "blocked"
    return "review"


def run_workset(args: argparse.Namespace) -> dict[str, Any]:
    workset_path = Path(args.workset)
    if not workset_path.is_absolute():
        workset_path = ROOT / workset_path
    source_workset = load_workset(workset_path)
    validation = validate_workset(source_workset)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    workset_id = str(source_workset.get("id") or workset_path.stem)
    run_id = f"{cento_build.slugify(workset_id)}_{run_stamp}"
    workset_dir = WORKSET_ROOT / run_id
    workset_dir.mkdir(parents=True, exist_ok=True)
    append_event(workset_dir, "workset_started", {"workset_id": workset_id, "source": rel(workset_path)})

    if validation["status"] != "passed":
        receipt = {
            "schema_version": SCHEMA_WORKSET_RECEIPT,
            "workset_id": workset_id,
            "run_id": run_id,
            "status": "rejected",
            "errors": validation["errors"],
            "warnings": validation["warnings"],
            "tasks": {},
            "started_at": now_iso(),
            "completed_at": now_iso(),
        }
        receipt_path = write_receipt(workset_dir, receipt)
        append_event(workset_dir, "workset_rejected", {"errors": validation["errors"]})
        return {"status": "rejected", "workset_receipt": rel(receipt_path), "errors": validation["errors"], "workset_dir": rel(workset_dir)}

    workset = normalize_workset(source_workset)
    max_parallel = int(args.max_workers or source_workset.get("max_parallel") or 1)
    if max_parallel <= 0:
        raise cento_build.BuildError("--max-workers must be greater than zero")
    max_parallel = min(max_parallel, int(source_workset.get("max_parallel") or max_parallel))
    apply_mode = args.apply
    write_json(workset_dir / "workset.json", workset)
    write_json(
        workset_dir / "leases.json",
        {
            "workset_id": workset["id"],
            "run_id": run_id,
            "exclusive": True,
            "leases": {task["id"]: task["write_paths"] for task in workset["tasks"]},
            "written_at": now_iso(),
        },
    )

    tasks_by_id = {task["id"]: task for task in workset["tasks"]}
    pending = set(tasks_by_id)
    running: dict[concurrent.futures.Future[dict[str, Any]], str] = {}
    records: dict[str, dict[str, Any]] = {
        tid: {
            "id": tid,
            "status": "pending",
            "depends_on": tasks_by_id[tid]["depends_on"],
            "write_paths": tasks_by_id[tid]["write_paths"],
            "build_dir": None,
            "manifest": None,
            "worker_artifact": None,
            "patch_bundle": None,
            "integration_receipt": None,
            "apply_receipt": None,
            "validation_receipt": None,
            "taskstream_evidence": None,
            "changed_paths": [],
            "errors": [],
        }
        for tid in tasks_by_id
    }
    completed_for_deps: set[str] = set()
    blocked: set[str] = set()
    changed_paths: list[str] = []

    runtime_profile_name = args.runtime_profile
    runtime = args.local_builder or "command"
    if runtime_profile_name:
        profile = cento_build.runtime_profile(runtime_profile_name)
        runtime = str(profile.get("type") or runtime)

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        while pending or running:
            made_progress = False
            ready = sorted(
                tid
                for tid in pending
                if all(dep in completed_for_deps for dep in tasks_by_id[tid]["depends_on"])
                and not any(dep in blocked for dep in tasks_by_id[tid]["depends_on"])
            )
            for tid in ready:
                if len(running) >= max_parallel:
                    break
                task = tasks_by_id[tid]
                records[tid]["status"] = "running"
                append_event(workset_dir, "task_dispatched", {"task_id": tid, "depends_on": task["depends_on"]})
                future = executor.submit(
                    run_task_worker,
                    workset,
                    task,
                    run_id=run_id,
                    runtime_profile=runtime_profile_name,
                    runtime=runtime,
                    fixture_case=args.fixture_case,
                    worker_timeout=args.worker_timeout,
                    validation_tier=args.validation,
                    allow_dirty_owned=args.allow_dirty_owned,
                    allow_unsafe_command=args.allow_unsafe_command,
                    command_template=args.command,
                )
                running[future] = tid
                pending.remove(tid)
                made_progress = True

            if not running:
                for tid in sorted(pending):
                    missing = [dep for dep in tasks_by_id[tid]["depends_on"] if dep not in completed_for_deps]
                    records[tid]["status"] = "dependency_blocked"
                    records[tid]["errors"].append("dependencies not completed: " + ", ".join(missing))
                    blocked.add(tid)
                    append_event(workset_dir, "task_dependency_blocked", {"task_id": tid, "missing": missing})
                pending.clear()
                break

            done, _not_done = concurrent.futures.wait(running, timeout=0.2, return_when=concurrent.futures.FIRST_COMPLETED)
            if not done and made_progress:
                continue
            if not done:
                continue

            for future in done:
                tid = running.pop(future)
                try:
                    worker_payload = future.result()
                except Exception as exc:
                    records[tid]["status"] = "failed"
                    records[tid]["errors"].append(str(exc))
                    blocked.add(tid)
                    append_event(workset_dir, "task_failed", {"task_id": tid, "error": str(exc)})
                    continue

                worker = worker_payload["worker"]
                records[tid].update(
                    {
                        "build_id": worker_payload.get("build_id"),
                        "build_dir": worker_payload.get("build_dir"),
                        "manifest": worker_payload.get("manifest"),
                        "worker_artifact": worker.get("worker_artifact"),
                        "patch_bundle": worker.get("patch_bundle"),
                        "patch": worker.get("patch"),
                        "changed_paths": worker.get("touched_paths") or [],
                    }
                )
                append_event(workset_dir, "worker_completed", {"task_id": tid, "status": worker.get("status"), "worker_status": worker.get("worker_status")})
                if worker.get("status") != "accepted" or not worker.get("patch_bundle"):
                    records[tid]["status"] = "blocked"
                    records[tid]["errors"].extend([str(item) for item in worker.get("errors") or ["worker rejected"]])
                    blocked.add(tid)
                    append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "worker rejected"})
                    continue

                manifest_path = ROOT / str(worker_payload["manifest"])
                bundle_path = ROOT / str(worker["patch_bundle"])
                code, stdout, stderr = run_integrate(manifest_path, bundle_path, allow_dirty_owned=args.allow_dirty_owned)
                build_dir = ROOT / str(worker_payload["build_dir"])
                integration_receipt = build_dir / "integration_receipt.json"
                records[tid]["integration_receipt"] = rel(integration_receipt) if integration_receipt.exists() else None
                append_event(workset_dir, "task_integration_completed", {"task_id": tid, "exit_code": code, "receipt": records[tid]["integration_receipt"]})
                if code != 0:
                    records[tid]["status"] = "blocked"
                    records[tid]["errors"].append(stderr or stdout or "integration rejected")
                    blocked.add(tid)
                    append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "integration rejected"})
                    continue

                if apply_mode == "sequential":
                    apply_receipt = cento_build.apply_build_bundle(
                        manifest_path,
                        bundle_path,
                        integration_receipt,
                        allow_dirty_owned=args.allow_dirty_owned,
                    )
                    records[tid]["apply_receipt"] = rel(build_dir / "apply_receipt.json")
                    records[tid]["validation_receipt"] = rel(build_dir / "validation_receipt.json")
                    records[tid]["taskstream_evidence"] = rel(build_dir / "taskstream_evidence.json")
                    if apply_receipt.get("status") != "applied":
                        records[tid]["status"] = "blocked"
                        records[tid]["errors"].extend([str(item) for item in apply_receipt.get("rejections") or ["apply rejected"]])
                        blocked.add(tid)
                        append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "apply rejected"})
                        continue
                    records[tid]["status"] = "applied"
                    completed_for_deps.add(tid)
                    changed_paths.extend([str(item) for item in apply_receipt.get("changed_paths") or []])
                    append_event(workset_dir, "task_applied", {"task_id": tid, "apply_receipt": records[tid]["apply_receipt"]})
                else:
                    records[tid]["status"] = "accepted"
                    completed_for_deps.add(tid)
                    append_event(workset_dir, "task_accepted", {"task_id": tid, "integration_receipt": records[tid]["integration_receipt"]})

    status = final_status(records)
    receipt = {
        "schema_version": SCHEMA_WORKSET_RECEIPT,
        "workset_id": workset["id"],
        "run_id": run_id,
        "source": rel(workset_path),
        "status": status,
        "mode": workset["mode"],
        "runtime_profile": runtime_profile_name,
        "max_parallel": max_parallel,
        "apply": apply_mode,
        "integration": "sequential",
        "no_shared_files": True,
        "tasks": records,
        "changed_paths": sorted(set(changed_paths)),
        "events": rel(workset_dir / "events.ndjson"),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "written_at": now_iso(),
    }
    receipt_path = write_receipt(workset_dir, receipt)
    append_event(workset_dir, "workset_completed", {"status": status, "receipt": rel(receipt_path)})
    write_json(
        workset_dir / "workset_evidence.json",
        {
            "schema_version": "cento.workset_evidence.v1",
            "workset_id": workset["id"],
            "run_id": run_id,
            "status": status,
            "workset_receipt": rel(receipt_path),
            "tasks": records,
            "events": rel(workset_dir / "events.ndjson"),
            "written_at": now_iso(),
        },
    )
    return {
        "status": status,
        "workset_id": workset["id"],
        "run_id": run_id,
        "workset_dir": rel(workset_dir),
        "workset_receipt": rel(receipt_path),
        "task_statuses": {tid: record["status"] for tid, record in records.items()},
        "changed_paths": sorted(set(changed_paths)),
    }


def task_records_summary(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    completed = sorted(tid for tid, record in records.items() if record.get("status") in {"applied", "accepted"})
    blocked = sorted(tid for tid, record in records.items() if record.get("status") in {"blocked", "dependency_blocked", "budget_blocked", "budget_exceeded", "rejected"})
    failed = sorted(tid for tid, record in records.items() if record.get("status") == "failed")
    return {
        "completed_tasks": completed,
        "blocked_tasks": blocked,
        "failed_tasks": failed,
        "completed_task_count": len(completed),
        "blocked_task_count": len(blocked),
        "failed_task_count": len(failed),
    }


def run_workset_execute(args: argparse.Namespace) -> dict[str, Any]:
    workset_path = Path(args.workset)
    if not workset_path.is_absolute():
        workset_path = ROOT / workset_path
    source_workset = load_workset(workset_path)
    runtime = str(args.runtime)
    allow_missing_paths = runtime == "api-openai"
    validation = validate_workset(source_workset, allow_missing_write_paths=allow_missing_paths)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    workset_id = str(source_workset.get("id") or workset_path.stem)
    run_id = f"{cento_build.slugify(workset_id)}_{run_stamp}"
    workset_dir = WORKSET_ROOT / run_id
    workset_dir.mkdir(parents=True, exist_ok=True)
    append_event(workset_dir, "workset_execute_started", {"workset_id": workset_id, "source": rel(workset_path), "runtime": runtime})

    def rejected_result(errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
        receipt = {
            "schema_version": SCHEMA_WORKSET_RECEIPT,
            "workset_id": workset_id,
            "run_id": run_id,
            "status": "rejected",
            "errors": errors,
            "warnings": warnings or [],
            "total_tasks": 0,
            "completed_tasks": [],
            "blocked_tasks": [],
            "failed_tasks": [],
            "total_cost_usd": 0.0,
            "target_budget_usd": args.budget_usd,
            "max_budget_usd": args.max_budget_usd,
            "elapsed_seconds": 0.0,
            "workers": [],
            "artifacts": [],
            "patch_bundles": [],
            "integration_receipts": [],
            "validation_receipts": [],
            "tasks": {},
            "started_at": now_iso(),
            "completed_at": now_iso(),
        }
        receipt_path = write_receipt(workset_dir, receipt)
        append_event(workset_dir, "workset_execute_rejected", {"errors": errors})
        return {"status": "rejected", "workset_receipt": rel(receipt_path), "errors": errors, "workset_dir": rel(workset_dir)}

    if validation["status"] != "passed":
        return rejected_result(validation["errors"], validation["warnings"])

    if args.integrate != "sequential":
        raise cento_build.BuildError("workset execute v1 only supports --integrate sequential")

    api_config: dict[str, Any] = {}
    api_config_path = Path(args.api_config)
    if not api_config_path.is_absolute():
        api_config_path = ROOT / api_config_path
    openai_config: dict[str, Any] = {}
    if runtime == "api-openai":
        api_config = load_api_worker_config(api_config_path)
        openai_config = api_openai_config(api_config)
        if openai_config.get("enabled") is False:
            raise cento_build.BuildError("OpenAI API workers are disabled in .cento/api_workers.yaml")

    workset = normalize_workset(source_workset)
    requested_parallel = int(args.max_parallel or source_workset.get("max_parallel") or 1)
    if requested_parallel <= 0:
        raise cento_build.BuildError("--max-parallel must be greater than zero")
    workset_limit = int(source_workset.get("max_parallel") or requested_parallel)
    max_parallel = min(requested_parallel, workset_limit)
    if runtime == "api-openai" and openai_config.get("max_parallel_requests") is not None:
        max_parallel = min(max_parallel, int(openai_config.get("max_parallel_requests") or max_parallel))

    default_budget = float(openai_config.get("budget_usd_default") or 3.0) if runtime == "api-openai" else 0.0
    configured_max_budget = float(openai_config.get("budget_usd_max") or 5.0) if runtime == "api-openai" else 0.0
    default_max_budget = configured_max_budget
    target_budget = float(args.budget_usd if args.budget_usd is not None else default_budget)
    requested_max_budget = float(args.max_budget_usd if args.max_budget_usd is not None else default_max_budget)
    if runtime == "api-openai" and requested_max_budget > configured_max_budget:
        return rejected_result([f"--max-budget-usd {requested_max_budget:.4f} exceeds configured openai.budget_usd_max {configured_max_budget:.4f}"])
    max_budget = requested_max_budget
    if runtime == "api-openai" and target_budget > max_budget:
        return rejected_result(["--budget-usd cannot exceed --max-budget-usd"])
    if runtime == "api-openai" and max_budget <= 0:
        return rejected_result(["--max-budget-usd must be greater than zero"])

    apply_mode = "sequential" if args.apply else "none"
    write_json(workset_dir / "workset.json", workset)
    write_json(
        workset_dir / "leases.json",
        {
            "workset_id": workset["id"],
            "run_id": run_id,
            "exclusive": True,
            "leases": {task["id"]: task["write_paths"] for task in workset["tasks"]},
            "written_at": now_iso(),
        },
    )

    tasks_by_id = {task["id"]: task for task in workset["tasks"]}
    pending = set(tasks_by_id)
    running: dict[concurrent.futures.Future[dict[str, Any]], str] = {}
    running_estimates: dict[str, float] = {}
    records: dict[str, dict[str, Any]] = {
        tid: {
            "id": tid,
            "worker_id": str(tasks_by_id[tid].get("worker_id") or tid),
            "status": "pending",
            "depends_on": tasks_by_id[tid]["depends_on"],
            "write_paths": tasks_by_id[tid]["write_paths"],
            "runtime": runtime,
            "build_dir": None,
            "manifest": None,
            "api_worker_dir": None,
            "api_artifact": None,
            "api_cost_receipt": None,
            "api_worker_receipt": None,
            "worker_artifact": None,
            "patch_bundle": None,
            "integration_receipt": None,
            "apply_receipt": None,
            "validation_receipt": None,
            "taskstream_evidence": None,
            "changed_paths": [],
            "cost_usd_estimate": 0.0,
            "errors": [],
        }
        for tid in tasks_by_id
    }
    completed_for_deps: set[str] = set()
    blocked: set[str] = set()
    changed_paths: list[str] = []
    total_cost_usd = 0.0
    artifacts: list[str] = []
    patch_bundles: list[str] = []
    integration_receipts: list[str] = []
    validation_receipts: list[str] = []
    workers: list[str] = []
    hard_budget_exceeded = False

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
        while pending or running:
            made_progress = False
            ready = sorted(
                tid
                for tid in pending
                if all(dep in completed_for_deps for dep in tasks_by_id[tid]["depends_on"])
                and not any(dep in blocked for dep in tasks_by_id[tid]["depends_on"])
            )
            for tid in ready:
                if len(running) >= max_parallel:
                    break
                task = tasks_by_id[tid]
                estimate = 0.0
                profile_name = ""
                output_schema = ""
                if runtime == "api-openai":
                    profile_name = api_profile_name_for_task(task, args.api_profile)
                    output_schema = api_output_schema_for_profile(api_config, profile_name, task)
                    estimate = api_cost_estimate(api_config, profile_name, task)
                    max_input_chars = api_positive_int_limit(api_config, profile_name, task, "max_input_chars", 20_000)
                    max_output_tokens = api_positive_int_limit(api_config, profile_name, task, "max_output_tokens", 2_000)
                    reserved = total_cost_usd + sum(running_estimates.values())
                    if hard_budget_exceeded or estimate > max_budget or reserved + estimate > max_budget:
                        if hard_budget_exceeded:
                            reason = f"hard budget already exceeded: total={total_cost_usd:.4f} max={max_budget:.4f}"
                        else:
                            reason = f"budget cap would be exceeded: reserved={reserved:.4f} estimate={estimate:.4f} max={max_budget:.4f}"
                        worker_dir = workset_dir / "workers" / str(task.get("worker_id") or tid)
                        cost_path, worker_receipt_path = write_blocked_worker_receipts(
                            worker_dir,
                            task,
                            runtime=runtime,
                            reason=reason,
                            cost_estimate=estimate,
                        )
                        records[tid]["status"] = "budget_blocked"
                        records[tid]["api_worker_dir"] = rel(worker_dir)
                        records[tid]["api_cost_receipt"] = rel(cost_path)
                        records[tid]["api_worker_receipt"] = rel(worker_receipt_path)
                        records[tid]["errors"].append(reason)
                        workers.extend([rel(cost_path), rel(worker_receipt_path)])
                        blocked.add(tid)
                        pending.remove(tid)
                        append_event(workset_dir, "task_budget_blocked", {"task_id": tid, "estimate": estimate, "max_budget_usd": max_budget})
                        made_progress = True
                        continue
                records[tid]["status"] = "running"
                records[tid]["cost_usd_estimate"] = estimate
                append_event(workset_dir, "task_dispatched", {"task_id": tid, "depends_on": task["depends_on"], "runtime": runtime})
                if runtime == "api-openai":
                    future = executor.submit(
                        run_api_task_worker,
                        workset,
                        task,
                        run_id=run_id,
                        workset_dir=workset_dir,
                        api_config=api_config,
                        api_config_path=api_config_path,
                        profile_name=profile_name,
                        output_schema=output_schema,
                        cost_estimate=estimate,
                        max_input_chars=max_input_chars,
                        max_output_tokens=max_output_tokens,
                        timeout=args.worker_timeout,
                        retry_attempts=args.retry_attempts,
                        validation_tier=args.validation,
                        allow_dirty_owned=args.allow_dirty_owned,
                    )
                    running_estimates[tid] = estimate
                else:
                    local_runtime = "fixture" if runtime == "fixture" else "command"
                    runtime_profile = args.runtime_profile or ""
                    if runtime == "local-command" and not runtime_profile and not args.command:
                        raise cento_build.BuildError("local-command runtime requires --runtime-profile or --command")
                    future = executor.submit(
                        run_task_worker,
                        workset,
                        task,
                        run_id=run_id,
                        runtime_profile=runtime_profile,
                        runtime=local_runtime,
                        fixture_case=args.fixture_case,
                        worker_timeout=args.worker_timeout,
                        validation_tier=args.validation,
                        allow_dirty_owned=args.allow_dirty_owned,
                        allow_unsafe_command=args.allow_unsafe_command or bool(args.command),
                        command_template=args.command,
                    )
                    running_estimates[tid] = 0.0
                running[future] = tid
                pending.remove(tid)
                made_progress = True

            if not running:
                for tid in sorted(pending):
                    missing = [dep for dep in tasks_by_id[tid]["depends_on"] if dep not in completed_for_deps]
                    records[tid]["status"] = "dependency_blocked"
                    records[tid]["errors"].append("dependencies not completed: " + ", ".join(missing))
                    blocked.add(tid)
                    append_event(workset_dir, "task_dependency_blocked", {"task_id": tid, "missing": missing})
                pending.clear()
                break

            done, _not_done = concurrent.futures.wait(running, timeout=0.2, return_when=concurrent.futures.FIRST_COMPLETED)
            if not done and made_progress:
                continue
            if not done:
                continue

            for future in done:
                tid = running.pop(future)
                running_estimates.pop(tid, None)
                try:
                    worker_payload = future.result()
                except Exception as exc:
                    records[tid]["status"] = "failed"
                    records[tid]["errors"].append(str(exc))
                    blocked.add(tid)
                    append_event(workset_dir, "task_failed", {"task_id": tid, "error": str(exc)})
                    continue

                if runtime != "api-openai":
                    local_worker_dir = workset_dir / "workers" / str(tasks_by_id[tid].get("worker_id") or tid)
                    local_worker_dir.mkdir(parents=True, exist_ok=True)
                    cost_path = write_zero_cost_receipt(local_worker_dir, tasks_by_id[tid], runtime, str(worker_payload.get("worker", {}).get("status") or "completed"))
                    records[tid]["api_cost_receipt"] = rel(cost_path)
                    workers.append(rel(cost_path))
                else:
                    if worker_payload.get("api_cost_receipt"):
                        try:
                            cost_payload = read_json(ROOT / str(worker_payload["api_cost_receipt"]))
                            actual_cost = float(cost_payload.get("cost_usd_estimate") or 0.0)
                        except Exception:
                            actual_cost = 0.0
                        total_cost_usd = round(total_cost_usd + actual_cost, 6)
                    if worker_payload.get("api_artifact"):
                        artifacts.append(str(worker_payload["api_artifact"]))
                    for key in ("api_worker_receipt", "api_cost_receipt"):
                        if worker_payload.get(key):
                            workers.append(str(worker_payload[key]))
                    if total_cost_usd > max_budget:
                        hard_budget_exceeded = True
                        reason = f"hard budget exceeded after worker usage: total={total_cost_usd:.6f} max={max_budget:.6f}"
                        records[tid].update(
                            {
                                "manifest": worker_payload.get("manifest"),
                                "build_id": worker_payload.get("build_id"),
                                "build_dir": worker_payload.get("build_dir"),
                                "api_worker_dir": worker_payload.get("api_worker_dir"),
                                "api_artifact": worker_payload.get("api_artifact"),
                                "api_cost_receipt": worker_payload.get("api_cost_receipt"),
                                "api_worker_receipt": worker_payload.get("api_worker_receipt"),
                            }
                        )
                        records[tid]["status"] = "budget_exceeded"
                        records[tid]["errors"].append(reason)
                        blocked.add(tid)
                        append_event(workset_dir, "hard_budget_exceeded", {"task_id": tid, "total_cost_usd": total_cost_usd, "max_budget_usd": max_budget})
                        continue

                if worker_payload.get("status") == "failed" and not worker_payload.get("worker"):
                    records[tid].update(
                        {
                            "manifest": worker_payload.get("manifest"),
                            "build_id": worker_payload.get("build_id"),
                            "build_dir": worker_payload.get("build_dir"),
                            "api_worker_dir": worker_payload.get("api_worker_dir"),
                            "api_artifact": worker_payload.get("api_artifact"),
                            "api_cost_receipt": worker_payload.get("api_cost_receipt"),
                            "api_worker_receipt": worker_payload.get("api_worker_receipt"),
                        }
                    )
                    records[tid]["status"] = "failed"
                    records[tid]["errors"].extend([str(item) for item in worker_payload.get("errors") or ["worker failed"]])
                    blocked.add(tid)
                    append_event(workset_dir, "task_failed", {"task_id": tid, "errors": records[tid]["errors"]})
                    continue

                worker = worker_payload["worker"]
                records[tid].update(
                    {
                        "build_id": worker_payload.get("build_id"),
                        "build_dir": worker_payload.get("build_dir"),
                        "manifest": worker_payload.get("manifest"),
                        "api_worker_dir": worker_payload.get("api_worker_dir"),
                        "api_artifact": worker_payload.get("api_artifact"),
                        "api_cost_receipt": worker_payload.get("api_cost_receipt") or records[tid].get("api_cost_receipt"),
                        "api_worker_receipt": worker_payload.get("api_worker_receipt"),
                        "worker_artifact": worker.get("worker_artifact"),
                        "patch_bundle": worker.get("patch_bundle"),
                        "patch": worker.get("patch"),
                        "changed_paths": worker.get("touched_paths") or [],
                    }
                )
                for path_key in ("api_artifact", "worker_artifact"):
                    if records[tid].get(path_key):
                        artifacts.append(str(records[tid][path_key]))
                if records[tid].get("patch_bundle"):
                    patch_bundles.append(str(records[tid]["patch_bundle"]))
                append_event(workset_dir, "worker_completed", {"task_id": tid, "status": worker.get("status"), "worker_status": worker.get("worker_status")})
                if worker.get("status") != "accepted" or not worker.get("patch_bundle"):
                    records[tid]["status"] = "blocked"
                    records[tid]["errors"].extend([str(item) for item in worker.get("errors") or ["worker rejected"]])
                    blocked.add(tid)
                    append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "worker rejected"})
                    continue

                manifest_path = ROOT / str(worker_payload["manifest"])
                bundle_path = ROOT / str(worker["patch_bundle"])
                code, stdout, stderr = run_integrate(manifest_path, bundle_path, allow_dirty_owned=args.allow_dirty_owned)
                build_dir = ROOT / str(worker_payload["build_dir"])
                integration_receipt = build_dir / "integration_receipt.json"
                records[tid]["integration_receipt"] = rel(integration_receipt) if integration_receipt.exists() else None
                if records[tid]["integration_receipt"]:
                    integration_receipts.append(str(records[tid]["integration_receipt"]))
                validation_receipt = build_dir / "validation_receipt.json"
                records[tid]["validation_receipt"] = rel(validation_receipt) if validation_receipt.exists() else None
                if records[tid]["validation_receipt"]:
                    validation_receipts.append(str(records[tid]["validation_receipt"]))
                append_event(workset_dir, "task_integration_completed", {"task_id": tid, "exit_code": code, "receipt": records[tid]["integration_receipt"]})
                if code != 0:
                    records[tid]["status"] = "blocked"
                    records[tid]["errors"].append(stderr or stdout or "integration rejected")
                    blocked.add(tid)
                    append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "integration rejected"})
                    continue

                if apply_mode == "sequential":
                    apply_receipt = cento_build.apply_build_bundle(
                        manifest_path,
                        bundle_path,
                        integration_receipt,
                        allow_dirty_owned=args.allow_dirty_owned,
                    )
                    records[tid]["apply_receipt"] = rel(build_dir / "apply_receipt.json")
                    records[tid]["validation_receipt"] = rel(build_dir / "validation_receipt.json")
                    records[tid]["taskstream_evidence"] = rel(build_dir / "taskstream_evidence.json")
                    if records[tid]["validation_receipt"] not in validation_receipts:
                        validation_receipts.append(str(records[tid]["validation_receipt"]))
                    if apply_receipt.get("status") != "applied":
                        records[tid]["status"] = "blocked"
                        records[tid]["errors"].extend([str(item) for item in apply_receipt.get("rejections") or ["apply rejected"]])
                        blocked.add(tid)
                        append_event(workset_dir, "task_blocked", {"task_id": tid, "reason": "apply rejected"})
                        continue
                    records[tid]["status"] = "applied"
                    completed_for_deps.add(tid)
                    changed_paths.extend([str(item) for item in apply_receipt.get("changed_paths") or []])
                    append_event(workset_dir, "task_applied", {"task_id": tid, "apply_receipt": records[tid]["apply_receipt"]})
                else:
                    records[tid]["status"] = "accepted"
                    completed_for_deps.add(tid)
                    append_event(workset_dir, "task_accepted", {"task_id": tid, "integration_receipt": records[tid]["integration_receipt"]})

    summary = task_records_summary(records)
    status = "completed" if summary["completed_task_count"] == len(records) else ("failed" if summary["failed_task_count"] and not summary["completed_task_count"] else "blocked")
    elapsed_seconds = round(time.perf_counter() - started, 3)
    receipt = {
        "schema_version": SCHEMA_WORKSET_RECEIPT,
        "workset_id": workset["id"],
        "run_id": run_id,
        "source": rel(workset_path),
        "status": status,
        "mode": workset["mode"],
        "runtime": runtime,
        "runtime_profile": args.runtime_profile,
        "max_parallel": max_parallel,
        "integration": args.integrate,
        "apply": apply_mode,
        "total_tasks": len(records),
        **summary,
        "total_cost_usd": round(total_cost_usd, 6),
        "target_budget_usd": target_budget,
        "max_budget_usd": max_budget,
        "target_budget_exceeded": runtime == "api-openai" and total_cost_usd > target_budget,
        "hard_budget_exceeded": hard_budget_exceeded,
        "elapsed_seconds": elapsed_seconds,
        "workers": sorted(set(workers)),
        "artifacts": sorted(set(artifacts)),
        "patch_bundles": sorted(set(patch_bundles)),
        "integration_receipts": sorted(set(integration_receipts)),
        "validation_receipts": sorted(set(validation_receipts)),
        "no_shared_files": True,
        "tasks": records,
        "changed_paths": sorted(set(changed_paths)),
        "events": rel(workset_dir / "events.ndjson"),
        "written_at": now_iso(),
    }
    receipt_path = write_receipt(workset_dir, receipt)
    append_event(workset_dir, "workset_execute_completed", {"status": status, "receipt": rel(receipt_path), "total_cost_usd": receipt["total_cost_usd"]})
    write_json(
        workset_dir / "workset_evidence.json",
        {
            "schema_version": "cento.workset_evidence.v1",
            "workset_id": workset["id"],
            "run_id": run_id,
            "status": status,
            "workset_receipt": rel(receipt_path),
            "tasks": records,
            "events": rel(workset_dir / "events.ndjson"),
            "written_at": now_iso(),
        },
    )
    return {
        "status": status,
        "workset_id": workset["id"],
        "run_id": run_id,
        "workset_dir": rel(workset_dir),
        "workset_receipt": rel(receipt_path),
        "task_statuses": {tid: record["status"] for tid, record in records.items()},
        "total_cost_usd": receipt["total_cost_usd"],
        "changed_paths": sorted(set(changed_paths)),
    }


def command_check(args: argparse.Namespace) -> int:
    try:
        workset = load_workset(Path(args.workset))
        result = validate_workset(workset)
    except cento_build.BuildError as exc:
        result = {"status": "failed", "errors": [str(exc)], "warnings": []}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"workset check: {result['status']}")
        for error in result.get("errors") or []:
            print(f"error: {error}", file=sys.stderr)
        for warning in result.get("warnings") or []:
            print(f"warning: {warning}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


def command_run(args: argparse.Namespace) -> int:
    try:
        result = run_workset(args)
    except cento_build.BuildError as exc:
        print(f"cento workset run: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["workset_receipt"])
        print(f"status: {result['status']}")
        for tid, status in result["task_statuses"].items():
            print(f"{tid}: {status}")
    return 0 if result["status"] in {"completed", "review"} else 1


def command_execute(args: argparse.Namespace) -> int:
    try:
        result = run_workset_execute(args)
    except cento_build.BuildError as exc:
        print(f"cento workset execute: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["workset_receipt"])
        print(f"status: {result['status']}")
        print(f"total_cost_usd: {result.get('total_cost_usd', 0.0):.6f}")
        for tid, status in result["task_statuses"].items():
            print(f"{tid}: {status}")
    return 0 if result["status"] == "completed" else 1


def command_materialize_artifact(args: argparse.Namespace) -> int:
    try:
        result = materialize_api_artifact(
            Path(args.artifact),
            manifest_path=Path(args.manifest) if args.manifest else None,
            build_id=args.build_id,
            validation_tier=args.validation,
            allow_dirty_owned=args.allow_dirty_owned,
        )
    except cento_build.BuildError as exc:
        print(f"cento workset materialize-artifact: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["materialization_receipt"])
        if result.get("patch_bundle"):
            print(result["patch_bundle"])
        for error in result.get("errors") or []:
            print(f"error: {error}", file=sys.stderr)
    return 0 if result["status"] == "materialized" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cento workset",
        description="Run a minimal local N-worker workset with exclusive paths and sequential integration.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validate workset shape, dependencies, and exclusive write paths.")
    check.add_argument("workset", help="workset.json path.")
    check.add_argument("--json", action="store_true", help="Print JSON result.")
    check.set_defaults(func=command_check)

    run_cmd = sub.add_parser("run", help="Run ready workset tasks in parallel and integrate patches sequentially.")
    run_cmd.add_argument("workset", help="workset.json path.")
    run_cmd.add_argument("--max-workers", type=int, help="Maximum parallel local workers.")
    run_cmd.add_argument("--runtime-profile", required=True, help="Named runtime profile from .cento/runtimes.yaml.")
    run_cmd.add_argument("--local-builder", help="Optional runtime adapter fallback; runtime profile type is preferred.")
    run_cmd.add_argument("--apply", choices=["sequential", "none"], default="sequential", help="Apply accepted patches sequentially or only dry-run integrate.")
    run_cmd.add_argument("--validation", help="Validation tier for generated build manifests.")
    run_cmd.add_argument("--worker-timeout", type=int, default=None, help="Worker timeout in seconds; runtime profiles can provide the default.")
    run_cmd.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"], help="Fixture case when using a fixture runtime.")
    run_cmd.add_argument("--command", help="Unsafe raw command template for command runtime.")
    run_cmd.add_argument("--allow-unsafe-command", action="store_true", help="Allow raw shell command runtime.")
    run_cmd.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths; recorded by build receipts.")
    run_cmd.add_argument("--json", action="store_true", help="Print JSON result.")
    run_cmd.set_defaults(func=command_run)

    execute = sub.add_parser("execute", help="Run ready workset tasks in parallel, including structured API workers.")
    execute.add_argument("workset", help="workset.json path.")
    execute.add_argument("--max-parallel", "--max-workers", dest="max_parallel", type=int, help="Maximum parallel workers.")
    execute.add_argument("--runtime", required=True, choices=["api-openai", "fixture", "local-command"], help="Worker runtime family.")
    execute.add_argument("--runtime-profile", help="Named local runtime profile for local-command or fixture execution.")
    execute.add_argument("--api-profile", default="api-section-worker", help="Default API worker profile from .cento/api_workers.yaml.")
    execute.add_argument("--api-config", default=str(API_CONFIG_PATH), help="API worker config path.")
    execute.add_argument("--budget-usd", type=float, default=None, help="Target API worker budget.")
    execute.add_argument("--max-budget-usd", type=float, default=None, help="Hard API worker budget cap.")
    execute.add_argument("--integrate", choices=["sequential"], default="sequential", help="Patch integration strategy.")
    execute.add_argument("--apply", action="store_true", help="Apply accepted patches sequentially after integration.")
    execute.add_argument("--validation", help="Validation tier for generated build manifests.")
    execute.add_argument("--worker-timeout", type=int, default=None, help="Worker timeout in seconds.")
    execute.add_argument("--retry-attempts", type=int, default=None, help="API retry attempts after the first request.")
    execute.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"], help="Fixture case for --runtime fixture.")
    execute.add_argument("--command", help="Raw command template for --runtime local-command.")
    execute.add_argument("--allow-unsafe-command", action="store_true", help="Allow raw shell command runtime.")
    execute.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths; recorded by build receipts.")
    execute.add_argument("--json", action="store_true", help="Print JSON result.")
    execute.set_defaults(func=command_execute)

    materialize = sub.add_parser("materialize-artifact", help="Convert a structured API worker artifact into a local patch bundle.")
    materialize.add_argument("artifact", help="artifact.json path.")
    materialize.add_argument("--manifest", help="Existing build manifest to materialize against.")
    materialize.add_argument("--build-id", help="Build id when creating a materialization manifest.")
    materialize.add_argument("--validation", help="Validation tier when creating a materialization manifest.")
    materialize.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths; recorded by build receipts.")
    materialize.add_argument("--json", action="store_true", help="Print JSON result.")
    materialize.set_defaults(func=command_materialize_artifact)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
