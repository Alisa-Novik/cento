#!/usr/bin/env python3
"""Run the ProReq-light variant through Codex Exec instead of live Pro API."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import dev_pipeline_hard_proreq as hard


SCHEMA_CLOSED_LOOP_DELIVERY = "cento.proreq_light.closed_loop_delivery.v1"
SCHEMA_CLOSED_LOOP_VALIDATION = "cento.proreq_light.closed_loop_validation.v1"
SCHEMA_CLOSED_LOOP_INCIDENT = "cento.proreq_light.closed_loop_incident.v1"


def command_all(args: argparse.Namespace) -> int:
    return hard.command_light_all(args)


def command_codex_plan(args: argparse.Namespace) -> int:
    return hard.command_codex_pro_plan(args)


def run_command(command: list[str], *, timeout: int | None = None) -> dict[str, Any]:
    started = hard.now_iso()
    try:
        result = subprocess.run(
            command,
            cwd=hard.ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "started_at": started,
            "completed_at": hard.now_iso(),
            "exit_code": result.returncode,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "status": "passed" if result.returncode == 0 else "failed",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "started_at": started,
            "completed_at": hard.now_iso(),
            "exit_code": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "status": "timeout",
            "timeout_seconds": timeout,
        }


def parse_stdout_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(result.get("stdout") or "{}"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def emit_json(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if bool(getattr(args, "json", False)):
        print(json.dumps(payload, indent=2, sort_keys=False))


def run_artifact_path(name: str) -> Path | None:
    current, latest = hard.artifact_dirs()
    for candidate in (current / name, latest / name):
        if candidate.exists():
            return candidate
    return None


def current_workset_path() -> Path | None:
    return run_artifact_path("parallel_patch_workset.json")


def ensure_light_planning(args: argparse.Namespace) -> int:
    if bool(getattr(args, "fresh", False)) or current_workset_path() is None:
        return command_all(args)
    return 0


def write_incident(
    *,
    incident_type: str,
    summary: str,
    failed_command: list[str] | None,
    details: dict[str, Any],
) -> dict[str, str]:
    payload = {
        "schema_version": SCHEMA_CLOSED_LOOP_INCIDENT,
        "run_id": hard.run_id(),
        "status": "blocked",
        "incident_type": incident_type,
        "summary": summary,
        "failed_command": failed_command or [],
        "details": details,
    }
    json_rel = hard.write_run_artifact("closed_loop_incident.json", payload)
    md = "\n".join(
        [
            f"# ProReq-light Closed-Loop Incident: {incident_type}",
            "",
            f"- run_id: `{hard.run_id()}`",
            f"- status: `blocked`",
            f"- summary: {summary}",
            f"- failed_command: `{ ' '.join(failed_command or []) }`",
            "",
            "## Details",
            "",
            "```json",
            json.dumps(details, indent=2, sort_keys=True),
            "```",
            "",
            "## Recovery",
            "",
            "Repair the underlying failure, then rerun `cento proreq-light deliver --fresh --json` or rerun without `--fresh` to reuse the existing ProReq-light workset.",
        ]
    )
    md_rel = hard.write_run_text("closed_loop_incident.md", md + "\n")
    return {"incident": json_rel, "incident_markdown": md_rel}


def write_validation(args: argparse.Namespace, workset_path: Path, *, delivery_status: str) -> tuple[str, dict[str, Any]]:
    if delivery_status != "completed":
        payload = {
            "schema_version": SCHEMA_CLOSED_LOOP_VALIDATION,
            "run_id": hard.run_id(),
            "status": "skipped",
            "delivery_status": delivery_status,
            "commands": [],
            "reason": "Final validation runs only after closed-loop delivery completes.",
        }
        return hard.write_run_artifact("closed_loop_validation.json", payload), payload
    story_index_path = run_artifact_path("story_index.json") or hard.artifact_dirs()[0] / "story_index.json"
    commands: list[list[str]] = [
        [sys.executable, "-m", "json.tool", str(story_index_path)],
        [sys.executable, "-m", "json.tool", str(workset_path)],
        [sys.executable, str(hard.ROOT / "scripts" / "cento_workset.py"), "check", hard.rel(workset_path), "--allow-creates", "--json"],
    ]
    if bool(getattr(args, "full_check", True)):
        commands.append(["make", "check"])
    results = [run_command(command, timeout=int(getattr(args, "validation_timeout", 600))) for command in commands]
    failed = [item for item in results if item.get("exit_code") != 0]
    status = "skipped" if delivery_status != "completed" else ("passed" if not failed else "failed")
    payload = {
        "schema_version": SCHEMA_CLOSED_LOOP_VALIDATION,
        "run_id": hard.run_id(),
        "status": status,
        "delivery_status": delivery_status,
        "commands": [
            {
                "command": item["command"],
                "exit_code": item.get("exit_code"),
                "status": item.get("status"),
                "stdout_tail": str(item.get("stdout") or "")[-2000:],
                "stderr_tail": str(item.get("stderr") or "")[-2000:],
            }
            for item in results
        ],
    }
    return hard.write_run_artifact("closed_loop_validation.json", payload), payload


def write_evidence(delivery: dict[str, Any], validation: dict[str, Any], incident_paths: dict[str, str] | None = None) -> str:
    incident_paths = incident_paths or {}
    payload = {
        "schema_version": "cento.proreq_light.closed_loop_evidence.v1",
        "run_id": hard.run_id(),
        "status": delivery.get("status"),
        "delivery": delivery,
        "validation": validation,
        "incident": incident_paths,
    }
    json_rel = hard.write_run_artifact("closed_loop_evidence.json", payload)
    receipt = str(delivery.get("workset_receipt") or "")
    changed = ", ".join([str(item) for item in delivery.get("changed_paths") or []]) or "none"
    md = "\n".join(
        [
            "# ProReq-light Closed-Loop Evidence",
            "",
            f"- run_id: `{hard.run_id()}`",
            f"- status: `{delivery.get('status')}`",
            f"- runtime: `{delivery.get('runtime_profile')}`",
            f"- workset_receipt: `{receipt}`",
            f"- changed_paths: {changed}",
            f"- validation: `{validation.get('status')}`",
            f"- evidence_json: `{json_rel}`",
        ]
    )
    if incident_paths:
        md += f"\n- incident: `{incident_paths.get('incident_markdown')}`\n"
    return hard.write_run_text("closed_loop_evidence.md", md + "\n")


def command_deliver(args: argparse.Namespace) -> int:
    planning_code = ensure_light_planning(args)
    if planning_code:
        incident_paths = write_incident(
            incident_type="planning_failed",
            summary="ProReq-light planning failed before worker dispatch.",
            failed_command=["proreq-light", "all"],
            details={"exit_code": planning_code},
        )
        delivery = {
            "schema_version": SCHEMA_CLOSED_LOOP_DELIVERY,
            "run_id": hard.run_id(),
            "status": "blocked",
            "stage": "planning",
            **incident_paths,
        }
        validation_rel, validation = write_validation(args, hard.artifact_dirs()[0] / "parallel_patch_workset.json", delivery_status="blocked")
        delivery["validation"] = validation_rel
        write_evidence(delivery, validation, incident_paths)
        hard.write_run_artifact("closed_loop_delivery.json", delivery)
        emit_json(args, delivery)
        return 1

    workset_path = current_workset_path()
    if workset_path is None:
        incident_paths = write_incident(
            incident_type="missing_workset",
            summary="ProReq-light did not produce parallel_patch_workset.json.",
            failed_command=None,
            details={},
        )
        delivery = {
            "schema_version": SCHEMA_CLOSED_LOOP_DELIVERY,
            "run_id": hard.run_id(),
            "status": "blocked",
            "stage": "preflight",
            **incident_paths,
        }
        validation_rel, validation = write_validation(args, hard.artifact_dirs()[0] / "parallel_patch_workset.json", delivery_status="blocked")
        delivery["validation"] = validation_rel
        write_evidence(delivery, validation, incident_paths)
        hard.write_run_artifact("closed_loop_delivery.json", delivery)
        emit_json(args, delivery)
        return 1

    check_command = [
        sys.executable,
        str(hard.ROOT / "scripts" / "cento_workset.py"),
        "check",
        hard.rel(workset_path),
        "--allow-creates",
        "--json",
    ]
    check_result = run_command(check_command, timeout=60)
    check_stdout_rel = hard.write_run_text("closed_loop_check_stdout.txt", str(check_result.get("stdout") or ""))
    check_stderr_rel = hard.write_run_text("closed_loop_check_stderr.txt", str(check_result.get("stderr") or ""))
    check_payload = parse_stdout_json(check_result)
    if check_result.get("exit_code") != 0:
        incident_paths = write_incident(
            incident_type="workset_preflight_failed",
            summary="ProReq-light workset failed preflight.",
            failed_command=check_command,
            details={"check": check_payload, "stderr": check_result.get("stderr", "")[-4000:]},
        )
        delivery = {
            "schema_version": SCHEMA_CLOSED_LOOP_DELIVERY,
            "run_id": hard.run_id(),
            "status": "blocked",
            "stage": "preflight",
            "workset": hard.rel(workset_path),
            "preflight": check_payload,
            "preflight_stdout": check_stdout_rel,
            "preflight_stderr": check_stderr_rel,
            **incident_paths,
        }
        validation_rel, validation = write_validation(args, workset_path, delivery_status="blocked")
        delivery["validation"] = validation_rel
        write_evidence(delivery, validation, incident_paths)
        hard.write_run_artifact("closed_loop_delivery.json", delivery)
        emit_json(args, delivery)
        return 1

    if bool(getattr(args, "plan_only", False)):
        delivery = {
            "schema_version": SCHEMA_CLOSED_LOOP_DELIVERY,
            "run_id": hard.run_id(),
            "status": "plan-only",
            "stage": "ready",
            "workset": hard.rel(workset_path),
            "preflight": check_payload,
            "preflight_stdout": check_stdout_rel,
            "preflight_stderr": check_stderr_rel,
            "runtime_profile": args.runtime_profile,
        }
        validation_rel, validation = write_validation(args, workset_path, delivery_status="plan-only")
        delivery["validation"] = validation_rel
        write_evidence(delivery, validation)
        hard.write_run_artifact("closed_loop_delivery.json", delivery)
        emit_json(args, delivery)
        return 0

    execute_command = [
        sys.executable,
        str(hard.ROOT / "scripts" / "cento_workset.py"),
        "execute",
        hard.rel(workset_path),
        "--runtime",
        "local-command",
        "--runtime-profile",
        args.runtime_profile,
        "--max-parallel",
        str(args.max_parallel),
        "--integrate",
        "sequential",
        "--validation",
        args.validation,
        "--worker-timeout",
        str(args.worker_timeout),
        "--allow-creates",
        "--json",
    ]
    if not bool(getattr(args, "no_apply", False)):
        execute_command.append("--apply")
    execute_result = run_command(execute_command, timeout=int(args.delivery_timeout))
    stdout_rel = hard.write_run_text("closed_loop_workset_stdout.txt", str(execute_result.get("stdout") or ""))
    stderr_rel = hard.write_run_text("closed_loop_workset_stderr.txt", str(execute_result.get("stderr") or ""))
    execute_payload = parse_stdout_json(execute_result)
    receipt_rel = str(execute_payload.get("workset_receipt") or "")
    receipt = hard.read_json(hard.ROOT / receipt_rel) if receipt_rel else {}
    delivery_status = "completed" if execute_result.get("exit_code") == 0 and str(receipt.get("status") or execute_payload.get("status")) == "completed" else "blocked"
    validation_rel, validation = write_validation(args, workset_path, delivery_status=delivery_status)
    incident_paths: dict[str, str] = {}
    if delivery_status == "completed" and validation.get("status") != "passed":
        delivery_status = "blocked"
        incident_paths = write_incident(
            incident_type="validation_failed",
            summary="Closed-loop worker delivery completed but final validation failed.",
            failed_command=None,
            details={"validation": validation},
        )
    elif delivery_status != "completed":
        incident_paths = write_incident(
            incident_type="workset_delivery_blocked",
            summary="Codex worker delivery did not complete cleanly.",
            failed_command=execute_command,
            details={
                "exit_code": execute_result.get("exit_code"),
                "stderr": str(execute_result.get("stderr") or "")[-4000:],
                "result": execute_payload,
                "receipt": receipt,
            },
        )
    delivery = {
        "schema_version": SCHEMA_CLOSED_LOOP_DELIVERY,
        "run_id": hard.run_id(),
        "status": delivery_status,
        "stage": "handoff" if delivery_status == "completed" else "blocked",
        "workset": hard.rel(workset_path),
        "runtime": "local-command",
        "runtime_profile": args.runtime_profile,
        "max_parallel": args.max_parallel,
        "apply": "none" if bool(getattr(args, "no_apply", False)) else "clean",
        "preflight": check_payload,
        "preflight_stdout": check_stdout_rel,
        "preflight_stderr": check_stderr_rel,
        "workset_result": execute_payload,
        "workset_receipt": receipt_rel,
        "workset_stdout": stdout_rel,
        "workset_stderr": stderr_rel,
        "changed_paths": [str(item) for item in receipt.get("changed_paths", []) if isinstance(item, str)],
        "validation": validation_rel,
        "cost_policy": "ProReq-light + Codex Exec local workers; no Hard Pro, image API, or OpenAI API workers.",
        **incident_paths,
    }
    hard.write_run_artifact("closed_loop_delivery.json", delivery)
    write_evidence(delivery, validation, incident_paths)
    emit_json(args, delivery)
    return 0 if delivery_status == "completed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate ProReq-light artifacts with Codex Exec planning.")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = {
        "intake": hard.command_intake,
        "context": hard.command_context,
        "screenshot": hard.command_light_screenshot,
        "pro-request": hard.command_pro_request,
        "codex-plan": command_codex_plan,
        "pro-plan": command_codex_plan,
        "backend-work": hard.command_backend_work,
        "integration-plan": hard.command_integration,
        "validation-plan": hard.command_validation,
        "evidence": hard.command_evidence,
        "all": command_all,
    }
    for name, func in commands.items():
        item = sub.add_parser(name)
        item.set_defaults(func=func)
    deliver = sub.add_parser("deliver", help="Run ProReq-light planning through Codex worker patch delivery.")
    deliver.add_argument("--fresh", action="store_true", help="Regenerate ProReq-light artifacts before worker dispatch.")
    deliver.add_argument("--plan-only", action="store_true", help="Stop after planning and workset preflight.")
    deliver.add_argument("--no-apply", action="store_true", help="Collect and integrate bundles without applying accepted patches.")
    deliver.add_argument("--runtime-profile", default="codex-fast", help="Named local runtime profile for Codex workers.")
    deliver.add_argument("--max-parallel", type=int, default=3, help="Maximum parallel Codex workers.")
    deliver.add_argument("--validation", default="smoke", help="Validation tier for generated build manifests.")
    deliver.add_argument("--worker-timeout", type=int, default=180, help="Per-worker timeout in seconds.")
    deliver.add_argument("--delivery-timeout", type=int, default=1800, help="Whole workset execution timeout in seconds.")
    deliver.add_argument("--validation-timeout", type=int, default=600, help="Timeout for each final validation command.")
    deliver.add_argument("--full-check", dest="full_check", action="store_true", default=True, help="Run make check after worker delivery.")
    deliver.add_argument("--no-full-check", dest="full_check", action="store_false", help="Skip make check in final validation.")
    deliver.add_argument("--json", action="store_true", help="Print closed-loop delivery JSON.")
    deliver.set_defaults(func=command_deliver)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
