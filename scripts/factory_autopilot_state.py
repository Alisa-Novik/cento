#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import factory_dispatch_core


ROOT = Path(__file__).resolve().parents[1]
AUTOPILOT_SCHEMA = "factory-autopilot-runtime-state/v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON: {path}")
    return payload


def autopilot_dir(run_dir: Path) -> Path:
    return run_dir / "autopilot"


def state_path(run_dir: Path) -> Path:
    return autopilot_dir(run_dir) / "factory-state.json"


def policy_path(run_dir: Path) -> Path:
    return autopilot_dir(run_dir) / "policy.json"


def metrics_path(run_dir: Path) -> Path:
    return autopilot_dir(run_dir) / "metrics.json"


def stop_reason_path(run_dir: Path) -> Path:
    return autopilot_dir(run_dir) / "stop-reason.json"


def default_state(run_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": AUTOPILOT_SCHEMA,
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "phase": "init",
        "cycles_completed": 0,
        "last_action": "",
        "last_progress": False,
        "no_progress_cycles": 0,
        "simulated": {
            "validation_backlog": None,
            "integration_backlog": None,
            "unvalidated_patch_backlog": None,
            "validated_patch_backlog": None,
            "validated_integrated_progress": 0,
            "blocked_reasons": [],
        },
        "artifacts": {},
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "updated_at": now_iso(),
    }


def load_state(run_dir: Path) -> dict[str, Any]:
    path = state_path(run_dir)
    if not path.exists():
        return default_state(run_dir)
    state = read_json(path)
    if state.get("schema_version") != AUTOPILOT_SCHEMA:
        state["schema_version"] = AUTOPILOT_SCHEMA
    state.setdefault("simulated", {})
    simulated = state["simulated"]
    if isinstance(simulated, dict) and "patch_backlog" in simulated and "unvalidated_patch_backlog" not in simulated:
        simulated["unvalidated_patch_backlog"] = simulated.get("patch_backlog")
        simulated["validated_patch_backlog"] = 0
    state.setdefault("artifacts", {})
    return state


def save_state(run_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(state_path(run_dir), state)


def run_json_command(command: list[str], *, timeout: int = 30) -> dict[str, Any]:
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("_command", command)
    payload.setdefault("_exit_code", proc.returncode)
    if proc.returncode != 0:
        payload.setdefault("_stderr_tail", proc.stderr[-1200:])
        payload.setdefault("_stdout_tail", proc.stdout[-1200:])
    return payload


def load_storage_pressure() -> dict[str, Any]:
    return run_json_command(["python3", "scripts/storage.py", "pressure", "--json"])


def load_agent_manager_health() -> dict[str, Any]:
    return run_json_command(["python3", "scripts/agent_manager.py", "scan", "--json"], timeout=45)


def queue_status_counts(queue: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in factory_dispatch_core.normalize_queue_tasks(queue):
        status = str(item.get("status") or "planned")
        counts[status] = counts.get(status, 0) + 1
    counts["total"] = sum(counts.values())
    return counts


def patch_counts(run_dir: Path) -> dict[str, int]:
    counts = {"candidate": 0, "missing": 0, "rejected": 0, "collected": 0, "validated": 0, "unvalidated": 0, "total": 0}
    for path in sorted((run_dir / "patches").glob("*/patch.json")):
        try:
            payload = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        counts["total"] += 1
        integration_status = str(payload.get("integration_status") or "")
        collection_state = str(payload.get("collection_state") or "")
        if integration_status in counts:
            counts[integration_status] += 1
        if collection_state == "collected":
            counts["collected"] += 1
        validation_status = ""
        validation_path = path.parent / str(payload.get("validation_result") or "validation-result.json")
        if validation_path.exists():
            try:
                validation_status = str(read_json(validation_path).get("status") or "")
            except (OSError, ValueError, json.JSONDecodeError):
                validation_status = ""
        if collection_state == "collected" and integration_status == "candidate" and validation_status in {"passed", "pass", "ok"}:
            counts["validated"] += 1
        elif collection_state == "collected" and integration_status in {"candidate", "missing", "rejected"}:
            counts["unvalidated"] += 1
    return counts


def integration_counts(run_dir: Path) -> dict[str, int]:
    path = run_dir / "integration" / "integration-plan.json"
    if not path.exists():
        return {"candidates": 0, "rejected": 0, "missing": 0, "conflicts": 0}
    payload = read_json(path)
    return {
        "candidates": len(payload.get("candidates") or []),
        "rejected": len(payload.get("rejected") or []),
        "missing": len(payload.get("missing") or []),
        "conflicts": len(payload.get("conflicts") or []),
    }


def materialized_count(run_dir: Path, task_ids: list[str]) -> int:
    return sum(1 for tid in task_ids if (run_dir / "tasks" / tid / "story.json").exists() and (run_dir / "tasks" / tid / "validation.json").exists())


def plan_owned_path_conflicts(plan: dict[str, Any]) -> list[dict[str, str]]:
    owners: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for task in plan.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        tid = str(task.get("id") or "")
        for raw in task.get("owned_scope") or []:
            path = str(raw)
            previous = owners.get(path)
            if previous and previous != tid:
                conflicts.append({"path": path, "first_task": previous, "second_task": tid})
            owners[path] = tid
    return conflicts


def scan(run_dir: Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or load_state(run_dir)
    plan_path = run_dir / "factory-plan.json"
    plan: dict[str, Any] = read_json(plan_path) if plan_path.exists() else {}
    tasks = [task for task in plan.get("tasks") or [] if isinstance(task, dict)]
    task_ids = [str(task.get("id") or "") for task in tasks]
    queue_path = run_dir / "queue" / "queue.json"
    queue = read_json(queue_path) if queue_path.exists() else {}
    queue_errors = factory_dispatch_core.validate_queue_payload(queue, run_dir) if queue else []
    counts = queue_status_counts(queue) if queue else {}
    patches = patch_counts(run_dir)
    integration = integration_counts(run_dir)
    simulated = state.get("simulated") if isinstance(state.get("simulated"), dict) else {}

    computed_validation = counts.get("validating", 0) + patches.get("unvalidated", 0)
    computed_integration = counts.get("ready_to_integrate", 0) + integration.get("candidates", 0)
    computed_unvalidated_patch = patches.get("unvalidated", 0) + counts.get("collecting", 0)
    computed_validated_patch = patches.get("validated", 0)
    validation_backlog = computed_validation if simulated.get("validation_backlog") is None else int(simulated.get("validation_backlog") or 0)
    integration_backlog = computed_integration if simulated.get("integration_backlog") is None else int(simulated.get("integration_backlog") or 0)
    unvalidated_patch_backlog = (
        computed_unvalidated_patch if simulated.get("unvalidated_patch_backlog") is None else int(simulated.get("unvalidated_patch_backlog") or 0)
    )
    validated_patch_backlog = computed_validated_patch if simulated.get("validated_patch_backlog") is None else int(simulated.get("validated_patch_backlog") or 0)

    storage_pressure = load_storage_pressure()
    agent_manager = load_agent_manager_health()
    storage_gate = storage_pressure.get("fanout_gate") if isinstance(storage_pressure.get("fanout_gate"), dict) else {}
    agent_summary = agent_manager.get("summary") if isinstance(agent_manager.get("summary"), dict) else {}
    safety_reasons: list[str] = []
    if int(agent_summary.get("critical", 0) or 0) > 0:
        safety_reasons.append("agent_manager_critical")
    if queue_errors:
        safety_reasons.append("queue_invalid")

    return {
        "schema_version": "factory-autopilot-scan/v1",
        "run_id": run_dir.name,
        "run_dir": rel(run_dir),
        "factory_state": {
            "plan_exists": plan_path.exists(),
            "task_count": len(tasks),
            "materialized_tasks": materialized_count(run_dir, task_ids),
            "queue_exists": queue_path.exists(),
            "queue_errors": queue_errors,
            "queue_counts": counts,
            "owned_path_conflicts": plan_owned_path_conflicts(plan),
        },
        "backlogs": {
            "unvalidated_patch": unvalidated_patch_backlog,
            "validated_patch": validated_patch_backlog,
            "patch": unvalidated_patch_backlog + validated_patch_backlog,
            "validation": validation_backlog,
            "integration": integration_backlog,
            "blocked": counts.get("blocked", 0),
            "ready_to_dispatch": counts.get("queued", 0),
        },
        "patches": patches,
        "integration": integration,
        "storage_pressure": storage_pressure,
        "agent_manager": {
            "available": agent_manager.get("_exit_code", 1) == 0,
            "summary": agent_summary,
            "recommendations": agent_manager.get("recommendations", [])[:5] if isinstance(agent_manager.get("recommendations"), list) else [],
        },
        "fanout_gate": {
            "storage_pressure": storage_pressure.get("storage_pressure", "unknown"),
            "should_hold_live_fanout": bool(storage_gate.get("should_hold_fanout") or storage_gate.get("should_pause_dispatch")),
            "dry_run_allowed": True,
        },
        "safety_gates": {
            "passed": not safety_reasons,
            "reasons": safety_reasons,
        },
        "generated_at": now_iso(),
    }
