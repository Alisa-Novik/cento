#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "scripts" / "fixtures" / "factory-autopilot-e2e"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def fixture_path(name: str) -> Path:
    path = FIXTURE_ROOT / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"Unknown fixture: {name}")
    return path


def task_for_run(run_id: str, task: dict[str, Any]) -> dict[str, Any]:
    owned_scope = [str(path).replace("factory-autopilot-e2e", run_id) for path in task.get("owned_scope") or []]
    expected_outputs = []
    for item in task.get("expected_outputs") or []:
        if not isinstance(item, dict):
            continue
        expected_outputs.append(
            {
                **item,
                "path": str(item.get("path") or "").replace("factory-autopilot-e2e", run_id),
            }
        )
    return {
        **task,
        "owned_scope": owned_scope,
        "expected_outputs": expected_outputs,
    }


def create_factory_run(out: Path, fixture: dict[str, Any]) -> None:
    created = now_iso()
    run_id = out.name
    request = {
        "raw": "create an adaptive fanout autopilot contract e2e",
        "normalized_goal": str(fixture.get("goal") or "Create a Factory Autopilot contract E2E."),
    }
    plan = {
        "schema_version": "factory-plan/v1",
        "run_id": run_id,
        "request": request,
        "package": str(fixture.get("package") or "factory-autopilot-v1"),
        "mode": "dispatch_dry_run",
        "risk": "low",
        "budget": {
            "ai_call_budget": 0,
            "strong_model_calls_allowed": 0,
            "cheap_worker_calls_allowed": 0,
            "estimated_cost_usd": 0,
        },
        "shared_paths": [],
        "tasks": [task_for_run(run_id, task) for task in fixture.get("tasks") or []],
        "integration": {
            "strategy": "autopilot_contract_only",
            "merge_order": [str(task.get("id")) for task in fixture.get("tasks") or []],
            "required_docs": ["docs/factory-autopilot.md", "docs/factory.md", "README.md"],
        },
        "validation": {
            "minimum_tier": "tier0",
            "requires_screenshots": False,
            "requires_api_smoke": False,
            "requires_human_review": False,
        },
        "evidence": {"run_dir": rel(out), "summary": rel(out / "e2e-summary.md")},
        "created_at": created,
    }
    intake = {
        "schema_version": "factory-intake/v1",
        "run_id": run_id,
        "request": request,
        "package": plan["package"],
        "mode": "dispatch_dry_run",
        "created_at": created,
        "ai_calls_used": 0,
        "estimated_ai_cost_usd": 0,
    }
    (out / "request.md").write_text("# Factory Autopilot Contract E2E\n\nNo runtime Autopilot is implemented by this fixture.\n", encoding="utf-8")
    write_json(out / "intake.json", intake)
    write_json(out / "factory-plan.json", plan)


def queue_counts(out: Path) -> dict[str, int]:
    queue = read_json(out / "queue" / "queue.json")
    counts: dict[str, int] = {"queued": 0, "running": 0, "validating": 0, "ready_to_integrate": 0, "integrated": 0, "blocked": 0}
    for task in queue.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "planned")
        counts[status] = counts.get(status, 0) + 1
    return counts


def policy(cycles: int) -> dict[str, Any]:
    return {
        "schema_version": "factory-autopilot-policy/v1",
        "mode": "contract_e2e_only",
        "runtime_implemented": False,
        "dry_run_default": True,
        "max_cycles": cycles,
        "fanout": {
            "initial_builders": 2,
            "initial_validators": 2,
            "initial_integrators": 1,
            "max_builders": 4,
            "max_validators": 3,
            "max_integrators": 1,
        },
        "thresholds": {
            "max_integration_backlog": 4,
            "max_patch_rejection_rate": 0.2,
            "min_validation_pass_rate": 0.8,
            "max_run_budget_usd": 2.0,
        },
        "stop_rules": [
            "agent_manager_critical_issue",
            "duplicate_active_worker",
            "protected_shared_path_conflict",
            "integration_branch_invalid",
            "rollback_metadata_missing",
            "budget_exhausted",
            "same_task_fails_twice",
            "no_progress_for_two_cycles",
        ],
    }


def cycle_action(index: int) -> str:
    sequence = ["dispatch", "collect", "integrate", "validate", "render"]
    return sequence[min(index - 1, len(sequence) - 1)]


def write_cycle(out: Path, index: int, counts: dict[str, int], policy_payload: dict[str, Any]) -> dict[str, Any]:
    cycle_id = f"{index:04d}"
    cycle_dir = out / "autopilot" / "cycles" / cycle_id
    action_name = cycle_action(index)
    scan = {
        "schema_version": "factory-autopilot-scan/v1",
        "run_id": out.name,
        "cycle": index,
        "contract_only": True,
        "run_state": {
            "queue": counts,
            "patch_backlog_count": 0,
            "integration_backlog_count": 0 if index == 1 else 1,
            "validation_backlog_count": 0,
        },
        "external_state": {
            "agent_manager": {"available": False, "critical": 0, "stale_runs": 0, "duplicate_runs": 0, "note": "not invoked by contract E2E"},
            "git": {"dirty_files_checked": False, "protected_path_conflicts": 0},
        },
        "pressure": {
            "queued_count": counts.get("queued", 0),
            "running_count": counts.get("running", 0),
            "validating_count": counts.get("validating", 0),
            "patch_backlog_count": 0,
            "integration_backlog_count": 0 if index == 1 else 1,
            "rejected_patch_rate": 0,
            "stale_run_count": 0,
            "duplicate_run_count": 0,
            "validator_saturation": 0,
            "integrator_saturation": 0,
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
        },
        "safety_gates": {"passed": True, "reasons": []},
        "generated_at": now_iso(),
    }
    decision = {
        "schema_version": "factory-autopilot-decision/v1",
        "run_id": out.name,
        "cycle": index,
        "action": action_name,
        "reason": "contract_e2e_action_sequence",
        "fanout": {
            "builders": min(policy_payload["fanout"]["initial_builders"] + max(0, index - 2), policy_payload["fanout"]["max_builders"]),
            "validators": policy_payload["fanout"]["initial_validators"],
            "integrators": policy_payload["fanout"]["initial_integrators"],
            "adjustment": "hold" if index == 1 else "increase" if index == 2 else "hold",
        },
        "skipped_actions": ["execute_workers", "merge_to_main"],
        "generated_at": now_iso(),
    }
    action = {
        "schema_version": "factory-autopilot-action/v1",
        "run_id": out.name,
        "cycle": index,
        "action": action_name,
        "dry_run": True,
        "execute": False,
        "command": f"cento factory {action_name} {out.name} --dry-run" if action_name == "dispatch" else f"cento factory {action_name} {out.name}",
        "bounded": True,
    }
    result = {
        "schema_version": "factory-autopilot-result/v1",
        "run_id": out.name,
        "cycle": index,
        "action": action_name,
        "executed": False,
        "decision": "contract_recorded",
        "reason": "Autopilot runtime intentionally not implemented in this E2E scaffold.",
        "output_paths": {
            "scan": rel(cycle_dir / "scan.json"),
            "decision": rel(cycle_dir / "decision.json"),
            "action": rel(cycle_dir / "action.json"),
        },
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "next_recommended_action": cycle_action(index + 1),
        "generated_at": now_iso(),
    }
    write_json(cycle_dir / "scan.json", scan)
    write_json(cycle_dir / "decision.json", decision)
    write_json(cycle_dir / "action.json", action)
    write_json(cycle_dir / "result.json", result)
    (cycle_dir / "summary.md").write_text(
        "\n".join(
            [
                f"# Autopilot Contract Cycle {cycle_id}",
                "",
                f"- Action: `{action_name}`",
                "- Executed: `false`",
                "- AI calls used: `0`",
                f"- Reason: {result['reason']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return result


def write_autopilot_contract(out: Path, cycles: int) -> dict[str, Any]:
    autopilot = out / "autopilot"
    autopilot.mkdir(parents=True, exist_ok=True)
    counts = queue_counts(out)
    policy_payload = policy(cycles)
    write_json(autopilot / "policy.json", policy_payload)
    results = [write_cycle(out, index, counts, policy_payload) for index in range(1, cycles + 1)]
    actions = {"dispatch": 0, "collect": 0, "validate": 0, "integrate": 0, "render": 0, "pause": 0, "escalate": 0, "stop": 0}
    for result in results:
        action = str(result.get("action") or "")
        actions[action] = actions.get(action, 0) + 1
    metrics = {
        "schema_version": "factory-autopilot-metrics/v1",
        "cycles_completed": cycles,
        "actions": actions,
        "tasks": counts,
        "quality": {
            "patches_collected": 0,
            "patches_applied": 0,
            "patches_rejected": 0,
            "patch_rejection_rate": 0,
            "validation_pass_rate": 1.0,
        },
        "cost": {
            "ai_calls_used": 0,
            "estimated_cost_usd": 0,
            "budget_remaining_usd": policy_payload["thresholds"]["max_run_budget_usd"],
        },
        "throughput": {
            "validated_patches_per_cycle": 0,
            "integrated_patches_per_cycle": 0,
        },
        "safety": {
            "stale_runs": 0,
            "duplicate_runs": 0,
            "protected_path_conflicts": 0,
            "manual_escalations": 0,
        },
    }
    stop_reason = {
        "schema_version": "factory-autopilot-stop-reason/v1",
        "run_id": out.name,
        "reason": "contract_e2e_complete",
        "details": "Autopilot E2E scaffold rendered contract artifacts only; runtime implementation is deferred.",
        "stopped_at": now_iso(),
    }
    state = {
        "schema_version": "factory-autopilot-state/v1",
        "run_id": out.name,
        "package": "factory-autopilot-v1",
        "mode": "contract_e2e_only",
        "runtime_implemented": False,
        "cycles_completed": cycles,
        "latest_action": results[-1]["action"] if results else "",
        "policy": rel(autopilot / "policy.json"),
        "metrics": metrics,
        "stop_reason": stop_reason,
        "cycle_paths": [rel(autopilot / "cycles" / f"{index:04d}") for index in range(1, cycles + 1)],
        "ai_calls_used": 0,
        "updated_at": now_iso(),
    }
    write_json(autopilot / "metrics.json", metrics)
    write_json(autopilot / "stop-reason.json", stop_reason)
    write_json(autopilot / "autopilot-state.json", state)
    with (autopilot / "events.jsonl").open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps({"ts": result["generated_at"], "event": "contract_cycle_recorded", "cycle": result["cycle"], "action": result["action"]}, sort_keys=True) + "\n")
        handle.write(json.dumps({"ts": stop_reason["stopped_at"], "event": "contract_e2e_complete", "cycles": cycles}, sort_keys=True) + "\n")
    summary_lines = [
        "# Factory Autopilot Contract E2E Summary",
        "",
        f"- Run: `{out.name}`",
        "- Mode: `contract_e2e_only`",
        "- Runtime implemented: `false`",
        f"- Cycles completed: `{cycles}`",
        "- AI calls used: 0",
        "",
        "## Fanout",
        "",
        f"- Initial builders: `{policy_payload['fanout']['initial_builders']}`",
        f"- Max builders: `{policy_payload['fanout']['max_builders']}`",
        "",
        "## Cycle Actions",
        "",
    ]
    summary_lines.extend(f"- `{result['cycle']:04d}`: `{result['action']}`" for result in results)
    summary_lines.extend(["", "## Deferred", "", "- Adaptive fanout runtime.", "- `cento factory autopilot` CLI facade.", "- Console Autopilot panel.", ""])
    (autopilot / "autopilot-summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (autopilot / "autopilot-panel.html").write_text(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>Autopilot Contract</title></head>"
        f"<body><main><h1>Factory Autopilot Contract</h1><p>Run: {out.name}</p><p>Cycles: {cycles}</p><p>AI calls used: 0</p></main></body></html>\n",
        encoding="utf-8",
    )
    return state


def validate_contract(out: Path, cycles: int) -> list[str]:
    required = [
        out / "factory-plan.json",
        out / "queue" / "queue.json",
        out / "autopilot" / "autopilot-state.json",
        out / "autopilot" / "policy.json",
        out / "autopilot" / "metrics.json",
        out / "autopilot" / "stop-reason.json",
        out / "autopilot" / "autopilot-summary.md",
    ]
    for index in range(1, cycles + 1):
        cycle = out / "autopilot" / "cycles" / f"{index:04d}"
        required.extend([cycle / "scan.json", cycle / "decision.json", cycle / "action.json", cycle / "result.json", cycle / "summary.md"])
    errors = [f"missing {rel(path)}" for path in required if not path.exists()]
    state = read_json(out / "autopilot" / "autopilot-state.json")
    if state.get("schema_version") != "factory-autopilot-state/v1":
        errors.append("autopilot-state schema_version mismatch")
    if state.get("runtime_implemented") is not False:
        errors.append("autopilot-state must mark runtime_implemented false for this contract E2E")
    if int(state.get("ai_calls_used", -1)) != 0:
        errors.append("autopilot-state ai_calls_used must be 0")
    policy_payload = read_json(out / "autopilot" / "policy.json")
    if not policy_payload.get("stop_rules"):
        errors.append("policy stop_rules missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the zero-AI Factory Autopilot contract E2E scaffold.")
    parser.add_argument("--fixture", default="career-consulting")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = repo_path(args.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    fixture = read_json(fixture_path(args.fixture))
    create_factory_run(out, fixture)
    run_arg = rel(out)
    checks = [
        run_step("validate-plan", ["python3", "scripts/factory_plan.py", "validate", rel(out / "factory-plan.json")]),
        run_step("materialize", ["python3", "scripts/factory.py", "materialize", run_arg]),
        run_step("queue", ["python3", "scripts/factory.py", "queue", run_arg]),
    ]
    state = write_autopilot_contract(out, max(1, args.cycles))
    contract_errors = validate_contract(out, max(1, args.cycles))
    checks.append(
        {
            "name": "autopilot-contract",
            "command": "internal contract validation",
            "exit_code": 0 if not contract_errors else 1,
            "passed": not contract_errors,
            "duration_ms": 0,
            "stdout_tail": "",
            "stderr_tail": "; ".join(contract_errors),
        }
    )
    total_duration_ms = round(sum(float(item["duration_ms"]) for item in checks), 3)
    decision = "approve" if all(item["passed"] for item in checks) else "blocked"
    summary = {
        "schema_version": "factory-autopilot-e2e-summary/v1",
        "fixture": args.fixture,
        "run_dir": run_arg,
        "decision": decision,
        "contract_only": True,
        "runtime_implemented": False,
        "autopilot_state": rel(out / "autopilot" / "autopilot-state.json"),
        "checks": checks,
        "stats": {
            "total_duration_ms": total_duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost_usd": 0,
            "validated_at": now_iso(),
        },
        "state": state,
    }
    write_json(out / "e2e-summary.json", summary)
    (out / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Factory Autopilot Zero-AI Contract E2E",
                "",
                f"- Fixture: `{args.fixture}`",
                f"- Decision: `{decision}`",
                "- Contract only: `true`",
                "- Runtime implemented: `false`",
                f"- Cycles completed: `{max(1, args.cycles)}`",
                f"- Total duration ms: `{total_duration_ms}`",
                "- AI calls used: 0",
                "",
                "## Checks",
                "",
                *[f"- {'PASS' if item['passed'] else 'FAIL'} `{item['name']}`" for item in checks],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"decision: {decision}")
        print("contract_only: true")
        print("runtime_implemented: false")
        print("AI calls used: 0")
        print(f"summary: {rel(out / 'e2e-summary.md')}")
    return 0 if decision == "approve" else 1


if __name__ == "__main__":
    raise SystemExit(main())
