#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import factory_autopilot_policy as ap_policy
import factory_autopilot_render
import factory_autopilot_state as ap_state
import factory_dispatch_core


ROOT = Path(__file__).resolve().parents[1]


def run_dir_for(value: str | Path) -> Path:
    return factory_dispatch_core.resolve_run_dir(value)


def run_command(command: list[str]) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "command": command,
        "exit_code": proc.returncode,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def command_for_action(run_dir: Path, action: str) -> list[str]:
    run_arg = ap_state.rel(run_dir)
    if action == "materialize":
        return ["python3", "scripts/factory.py", "materialize", run_arg]
    if action == "queue":
        return ["python3", "scripts/factory.py", "queue", run_arg]
    if action == "dispatch_dry_run":
        return ["python3", "scripts/factory.py", "dispatch", run_arg, "--lane", "builder", "--max", "1", "--dry-run"]
    if action == "collect":
        return ["python3", "scripts/factory.py", "collect", run_arg, "--json"]
    if action == "validate":
        return ["python3", "scripts/factory.py", "validate", run_arg, "--json"]
    if action == "integrate_dry_run":
        return ["python3", "scripts/factory.py", "integrate", run_arg, "--dry-run"]
    if action == "render":
        return ["python3", "scripts/factory_autopilot.py", "render", run_arg]
    return []


def write_cycle_summary(cycle_dir: Path, decision: dict[str, Any], result: dict[str, Any]) -> None:
    lines = [
        f"# Autopilot Cycle {cycle_dir.name}",
        "",
        f"- Action: `{decision.get('action')}`",
        f"- Result: `{result.get('decision')}`",
        f"- Progress: `{str(result.get('progress', False)).lower()}`",
        "- AI calls used: 0",
        "",
        "## Reasons",
        "",
        *[f"- `{item}`" for item in decision.get("reasons") or []],
        "",
    ]
    (cycle_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def update_simulated_state(state: dict[str, Any], scan: dict[str, Any], action: str, success: bool) -> bool:
    simulated = state.setdefault("simulated", {})
    backlogs = scan.get("backlogs") if isinstance(scan.get("backlogs"), dict) else {}
    for key in ("patch", "validation", "integration"):
        field = f"{key}_backlog"
        if simulated.get(field) is None:
            simulated[field] = int(backlogs.get(key, 0) or 0)
    before = json.dumps(simulated, sort_keys=True)
    if success and action == "integrate_dry_run":
        if int(simulated.get("patch_backlog") or 0) > 0:
            simulated["patch_backlog"] = max(0, int(simulated.get("patch_backlog") or 0) - 1)
            simulated["integration_backlog"] = int(simulated.get("integration_backlog") or 0) + 1
        elif int(simulated.get("integration_backlog") or 0) > 0:
            simulated["integration_backlog"] = max(0, int(simulated.get("integration_backlog") or 0) - 1)
            simulated["validated_integrated_progress"] = int(simulated.get("validated_integrated_progress") or 0) + 1
    elif success and action == "validate":
        if int(simulated.get("validation_backlog") or 0) > 0:
            simulated["validation_backlog"] = max(0, int(simulated.get("validation_backlog") or 0) - 1)
            simulated["integration_backlog"] = int(simulated.get("integration_backlog") or 0) + 1
    elif success and action == "dispatch_dry_run":
        simulated["validation_backlog"] = int(simulated.get("validation_backlog") or 0) + 1
    elif success and action in {"materialize", "queue", "render"}:
        simulated["last_framework_progress"] = action
    return before != json.dumps(simulated, sort_keys=True)


def write_metrics(run_dir: Path, state: dict[str, Any], scan: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    autopilot = ap_state.autopilot_dir(run_dir)
    action_counts: dict[str, int] = {}
    for decision_path in sorted((autopilot / "cycles").glob("*/decision.json")):
        payload = ap_state.read_json(decision_path)
        action = str(payload.get("action") or "")
        action_counts[action] = action_counts.get(action, 0) + 1
    blocked_reasons = list(dict.fromkeys([*(state.get("simulated", {}).get("blocked_reasons") or []), *decision.get("reasons", [])]))
    cycle_count = int(state.get("cycles_completed", 0) or 0)
    expected_files = 4 * cycle_count + 4
    present_files = sum(1 for path in [ap_state.state_path(run_dir), ap_state.policy_path(run_dir), ap_state.metrics_path(run_dir), ap_state.stop_reason_path(run_dir)] if path.exists())
    present_files += sum(1 for path in (autopilot / "cycles").glob("*/*.json"))
    completeness = "complete" if expected_files and present_files >= expected_files else "partial"
    simulated = state.get("simulated") if isinstance(state.get("simulated"), dict) else {}
    metrics = {
        "schema_version": "factory-autopilot-metrics/v1",
        "mode": "dry_run_control_loop",
        "cycles_completed": cycle_count,
        "actions": action_counts,
        "latest_backlogs": scan.get("backlogs", {}),
        "progress": {
            "validated_integrated": int(simulated.get("validated_integrated_progress") or 0),
            "per_dollar": int(simulated.get("validated_integrated_progress") or 0),
        },
        "blocked_reasons": blocked_reasons,
        "readiness": {
            "ready_for_real_execution": bool(cycle_count and not blocked_reasons and int((scan.get("backlogs") or {}).get("blocked", 0) or 0) == 0),
            "storage_live_fanout_gate": (scan.get("fanout_gate") or {}).get("storage_pressure") if isinstance(scan.get("fanout_gate"), dict) else "unknown",
        },
        "evidence": {
            "completeness": completeness,
            "present_files": present_files,
            "expected_files": expected_files,
        },
        "cost": {"ai_calls_used": 0, "estimated_cost_usd": 0},
        "generated_at": ap_state.now_iso(),
    }
    ap_state.write_json(ap_state.metrics_path(run_dir), metrics)
    return metrics


def execute_cycle(run_dir: Path, max_cycles: int) -> dict[str, Any]:
    state = ap_state.load_state(run_dir)
    policy = ap_policy.default_policy(max_cycles)
    ap_state.write_json(ap_state.policy_path(run_dir), policy)
    scan = ap_state.scan(run_dir, state)
    decision = ap_policy.decide(scan, state, policy)
    cycle_no = int(state.get("cycles_completed", 0) or 0) + 1
    cycle_dir = ap_state.autopilot_dir(run_dir) / "cycles" / f"{cycle_no:04d}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    command = command_for_action(run_dir, str(decision.get("action") or ""))
    action = {
        "schema_version": "factory-autopilot-action/v1",
        "run_id": run_dir.name,
        "cycle": cycle_no,
        "action": decision.get("action"),
        "dry_run": True,
        "bounded": True,
        "command": command,
        "forbidden_effects": policy["forbidden"],
        "generated_at": ap_state.now_iso(),
    }
    if decision.get("action") == "stop":
        raw_result = {"command": [], "exit_code": 0, "duration_ms": 0, "stdout_tail": "", "stderr_tail": ""}
    elif decision.get("action") in {"hold"}:
        raw_result = {"command": [], "exit_code": 0, "duration_ms": 0, "stdout_tail": "", "stderr_tail": ""}
    elif decision.get("action") == "render":
        outputs = factory_autopilot_render.render(run_dir)
        raw_result = {"command": command, "exit_code": 0, "duration_ms": 0, "stdout_tail": json.dumps(outputs), "stderr_tail": ""}
    else:
        raw_result = run_command(command)
    success = int(raw_result["exit_code"]) == 0 or decision.get("action") in {"validate", "integrate_dry_run"}
    progress = update_simulated_state(state, scan, str(decision.get("action") or ""), success)
    state["cycles_completed"] = cycle_no
    state["last_action"] = decision.get("action")
    state["last_progress"] = progress
    state["no_progress_cycles"] = 0 if progress else int(state.get("no_progress_cycles", 0) or 0) + 1
    state["phase"] = "stopped" if decision.get("stop") else str(decision.get("action") or "running")
    state["artifacts"][f"cycle_{cycle_no:04d}"] = ap_state.rel(cycle_dir)
    result = {
        "schema_version": "factory-autopilot-result/v1",
        "run_id": run_dir.name,
        "cycle": cycle_no,
        "action": decision.get("action"),
        "decision": "completed" if success else "failed",
        "progress": progress,
        "raw_result": raw_result,
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
        "generated_at": ap_state.now_iso(),
    }
    ap_state.write_json(cycle_dir / "scan.json", scan)
    ap_state.write_json(cycle_dir / "decision.json", decision)
    ap_state.write_json(cycle_dir / "action.json", action)
    ap_state.write_json(cycle_dir / "result.json", result)
    write_cycle_summary(cycle_dir, decision, result)
    ap_state.save_state(run_dir, state)
    metrics = write_metrics(run_dir, state, scan, decision)
    return {"scan": scan, "decision": decision, "action": action, "result": result, "state": state, "metrics": metrics}


def run_autopilot(run_dir: Path, *, cycles: int, dry_run: bool) -> dict[str, Any]:
    if not dry_run:
        raise SystemExit("factory autopilot v1 only supports --dry-run")
    run_dir.mkdir(parents=True, exist_ok=True)
    completed: list[dict[str, Any]] = []
    stop_reason = "max_cycles"
    for _ in range(max(1, cycles)):
        cycle = execute_cycle(run_dir, max(1, cycles))
        completed.append(cycle)
        decision = cycle["decision"]
        result = cycle["result"]
        if decision.get("action") == "stop":
            stop_reason = ",".join(decision.get("reasons") or ["stop"])
            break
        if result.get("decision") == "failed":
            stop_reason = "bounded_action_failed"
            break
    state = ap_state.load_state(run_dir)
    stop = {
        "schema_version": "factory-autopilot-stop-reason/v1",
        "run_id": run_dir.name,
        "reason": stop_reason,
        "cycles_completed": state.get("cycles_completed", 0),
        "stopped_at": ap_state.now_iso(),
    }
    ap_state.write_json(ap_state.stop_reason_path(run_dir), stop)
    if ap_state.metrics_path(run_dir).exists():
        metrics = ap_state.read_json(ap_state.metrics_path(run_dir))
        autopilot = ap_state.autopilot_dir(run_dir)
        cycle_count = int(state.get("cycles_completed", 0) or 0)
        expected_files = 4 * cycle_count + 4
        present_files = sum(1 for path in [ap_state.state_path(run_dir), ap_state.policy_path(run_dir), ap_state.metrics_path(run_dir), ap_state.stop_reason_path(run_dir)] if path.exists())
        present_files += sum(1 for path in (autopilot / "cycles").glob("*/*.json"))
        metrics["evidence"] = {
            "completeness": "complete" if expected_files and present_files >= expected_files else "partial",
            "present_files": present_files,
            "expected_files": expected_files,
        }
        ap_state.write_json(ap_state.metrics_path(run_dir), metrics)
    outputs = factory_autopilot_render.render(run_dir)
    return {"run_id": run_dir.name, "cycles_completed": state.get("cycles_completed", 0), "stop_reason": stop, "summary": outputs["summary"]}


def status(run_dir: Path) -> dict[str, Any]:
    state = ap_state.load_state(run_dir)
    metrics = ap_state.read_json(ap_state.metrics_path(run_dir)) if ap_state.metrics_path(run_dir).exists() else {}
    stop = ap_state.read_json(ap_state.stop_reason_path(run_dir)) if ap_state.stop_reason_path(run_dir).exists() else {}
    return {
        "schema_version": "factory-autopilot-status/v1",
        "run_id": run_dir.name,
        "state": state,
        "metrics": metrics,
        "stop_reason": stop,
        "artifacts": {
            "factory_state": ap_state.rel(ap_state.state_path(run_dir)),
            "policy": ap_state.rel(ap_state.policy_path(run_dir)),
            "metrics": ap_state.rel(ap_state.metrics_path(run_dir)),
            "summary": ap_state.rel(ap_state.autopilot_dir(run_dir) / "autopilot-summary.md"),
        },
        "ai_calls_used": 0,
        "estimated_cost_usd": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Factory Autopilot deterministic dry-run runtime.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("run_id")
    run.add_argument("--dry-run", action="store_true", default=True)
    run.add_argument("--cycles", type=int, default=5)
    run.add_argument("--json", action="store_true")
    st = sub.add_parser("status")
    st.add_argument("run_id")
    st.add_argument("--json", action="store_true")
    render = sub.add_parser("render")
    render.add_argument("run_id")
    render.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    run_dir = run_dir_for(args.run_id)
    if args.command == "run":
        payload = run_autopilot(run_dir, cycles=args.cycles, dry_run=args.dry_run)
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["summary"])
    elif args.command == "status":
        payload = status(run_dir)
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload, indent=2, sort_keys=True))
    elif args.command == "render":
        payload = factory_autopilot_render.render(run_dir)
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
