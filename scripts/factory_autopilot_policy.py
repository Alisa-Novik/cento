#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_policy(max_cycles: int) -> dict[str, Any]:
    return {
        "schema_version": "factory-autopilot-policy/v1",
        "mode": "dry_run_control_loop",
        "max_cycles": max_cycles,
        "dry_run_only": True,
        "primary_metric": "validated integrated output per dollar",
        "v1_metrics": [
            "simulated_validated_integrated_progress",
            "blocked_reasons",
            "readiness_for_real_execution",
            "cycle_decisions",
            "evidence_completeness",
        ],
        "actions": [
            "materialize",
            "queue",
            "dispatch_dry_run",
            "collect",
            "validate",
            "integrate_dry_run",
            "render",
            "hold",
            "stop",
        ],
        "priority": [
            "hard_safety_gates",
            "recovery_collection",
            "state_materialization",
            "validation_first_for_unvalidated_outputs",
            "integration_only_for_validated_candidates",
            "evidence_render",
            "dispatch_when_downstream_clear",
            "hold_stop",
        ],
        "limits": {
            "dispatch_dry_run_max_tasks_per_cycle": 1,
            "no_progress_cycles_before_stop": 2,
        },
        "forbidden": [
            "live_worker_dispatch",
            "patch_apply_to_main",
            "destructive_storage_action",
            "cloud_upload",
            "notifications",
        ],
        "generated_at": now_iso(),
    }


def decide(scan: dict[str, Any], state: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    factory_state = scan.get("factory_state") if isinstance(scan.get("factory_state"), dict) else {}
    backlogs = scan.get("backlogs") if isinstance(scan.get("backlogs"), dict) else {}
    queue_counts = factory_state.get("queue_counts") if isinstance(factory_state.get("queue_counts"), dict) else {}
    safety = scan.get("safety_gates") if isinstance(scan.get("safety_gates"), dict) else {}
    reasons: list[str] = []
    action = "hold"
    stop = False

    if not factory_state.get("plan_exists"):
        action = "stop"
        stop = True
        reasons.append("missing_factory_plan")
    elif int(factory_state.get("materialized_tasks", 0) or 0) < int(factory_state.get("task_count", 0) or 0):
        action = "materialize"
        reasons.append("task_manifests_missing")
    elif not factory_state.get("queue_exists"):
        action = "queue"
        reasons.append("queue_missing")
    elif factory_state.get("queue_errors"):
        action = "queue"
        reasons.append("queue_invalid")
    elif not safety.get("passed", True) and safety.get("reasons") != ["queue_invalid"]:
        action = "hold"
        reasons.extend(str(item) for item in safety.get("reasons") or ["safety_gate_failed"])
    elif int(backlogs.get("unvalidated_patch", 0) or 0) > 0:
        action = "validate"
        reasons.append("unvalidated_patch_backlog_before_integration")
    elif int(backlogs.get("validation", 0) or 0) > 0:
        action = "validate"
        reasons.append("validation_backlog_before_more_dispatch")
    elif int(backlogs.get("validated_patch", 0) or 0) > 0:
        action = "integrate_dry_run"
        reasons.append("validated_patch_backlog_ready_for_integration")
    elif int(backlogs.get("integration", 0) or 0) > 0:
        action = "integrate_dry_run"
        reasons.append("integration_backlog_before_more_dispatch")
    elif int(queue_counts.get("queued", 0) or 0) > 0:
        action = "dispatch_dry_run"
        reasons.append("runnable_tasks_and_downstream_clear")
    else:
        action = "render"
        reasons.append("nothing_runnable")

    no_progress_limit = int((policy.get("limits") or {}).get("no_progress_cycles_before_stop") or 2)
    if int(state.get("no_progress_cycles", 0) or 0) >= no_progress_limit:
        action = "stop"
        stop = True
        reasons.append("no_progress_limit_reached")

    return {
        "schema_version": "factory-autopilot-decision/v1",
        "run_id": scan.get("run_id", ""),
        "cycle": int(state.get("cycles_completed", 0) or 0) + 1,
        "action": action,
        "stop": stop,
        "reasons": reasons,
        "dry_run": True,
        "live_fanout_allowed": False,
        "storage_live_fanout_gate": ((scan.get("fanout_gate") or {}).get("storage_pressure") if isinstance(scan.get("fanout_gate"), dict) else "unknown"),
        "generated_at": now_iso(),
    }
