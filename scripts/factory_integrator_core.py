#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import factory_dispatch_core as dispatch


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_WORKTREE_ROOT = ROOT / "workspace" / "factory-integration-worktrees"


class FactoryIntegratorError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return dispatch.rel(path)


def resolve_run_dir(value: str | Path) -> Path:
    return dispatch.resolve_run_dir(value)


def read_json(path: Path) -> dict[str, Any]:
    return dispatch.read_json(path)


def write_json(path: Path, payload: Any) -> None:
    dispatch.write_json(path, payload)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def run(command: list[str], *, cwd: Path, timeout: int = 120, input_text: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "cwd": rel(cwd),
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": proc.stdout[-1200:],
        "stderr_tail": proc.stderr[-1200:],
    }


def integration_dir(run_dir: Path) -> Path:
    return run_dir / "integration"


def default_branch(run_dir: Path) -> str:
    return f"factory/{run_dir.name}/integration"


def default_worktree(run_dir: Path) -> Path:
    return INTEGRATION_WORKTREE_ROOT / run_dir.name


def queue_task_map(run_dir: Path) -> dict[str, dict[str, Any]]:
    queue = dispatch.load_queue(run_dir)
    return {dispatch.task_id(item): item for item in dispatch.normalize_queue_tasks(queue)}


def plan_merge_order(run_dir: Path) -> list[str]:
    plan = dispatch.load_plan(run_dir)
    queue_ids = list(queue_task_map(run_dir))
    explicit = (plan.get("integration") or {}).get("merge_order") or []
    ordered = [str(item) for item in explicit if str(item) in queue_ids]
    for item in queue_ids:
        if item not in ordered:
            ordered.append(item)
    return ordered


def patch_json_path(run_dir: Path, task_id: str) -> Path:
    return run_dir / "patches" / task_id / "patch.json"


def patch_diff_path(run_dir: Path, patch: dict[str, Any]) -> Path:
    task = str(patch.get("task_id") or "")
    raw = str(patch.get("patch_file") or "patch.diff")
    path = Path(raw)
    return path if path.is_absolute() else run_dir / "patches" / task / path


def validation_result_path(run_dir: Path, patch: dict[str, Any]) -> Path:
    task = str(patch.get("task_id") or "")
    raw = str(patch.get("validation_result") or "validation-result.json")
    path = Path(raw)
    return path if path.is_absolute() else run_dir / "patches" / task / path


def validation_manifest_path(run_dir: Path, task_id: str) -> Path:
    return run_dir / "tasks" / task_id / "validation.json"


def risk_rank(item: dict[str, Any]) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(str(item.get("risk") or "medium"), 1)


def ordered_task_ids(run_dir: Path) -> list[str]:
    tasks = queue_task_map(run_dir)
    order = plan_merge_order(run_dir)
    return sorted(order, key=lambda task_id: (len(tasks.get(task_id, {}).get("dependencies") or []), risk_rank(tasks.get(task_id, {})), order.index(task_id)))


def docs_gate(changed_files: list[str]) -> tuple[str, str]:
    return dispatch.docs_gate_status(changed_files)


def render_template(path: Path, values: dict[str, str]) -> str:
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{ " + key + " }}", value)
    return text


def candidate_record(run_dir: Path, task_id: str) -> dict[str, Any]:
    tasks = queue_task_map(run_dir)
    item = tasks.get(task_id, {})
    path = patch_json_path(run_dir, task_id)
    if not path.exists():
        return {
            "task_id": task_id,
            "candidate": False,
            "reasons": ["patch_bundle_missing"],
            "patch_bundle": rel(path),
        }
    patch = read_json(path)
    changed_files = [str(file) for file in patch.get("changed_files") or []]
    outside = [file for file in changed_files if not dispatch.path_allowed(file, dispatch.owned_paths_for(item))]
    protected = [file for file in changed_files if file in dispatch.PROTECTED_SHARED_PATHS and not dispatch.path_allowed(file, dispatch.owned_paths_for(item))]
    registry_status, registry_reason = docs_gate(changed_files)
    validation = read_json(validation_result_path(run_dir, patch)) if validation_result_path(run_dir, patch).exists() else {}
    reasons: list[str] = []
    if patch.get("collection_state") == "missing":
        reasons.append("patch_explicitly_missing")
    if not patch_diff_path(run_dir, patch).exists() or not patch_diff_path(run_dir, patch).read_text(encoding="utf-8", errors="ignore").strip():
        reasons.append("patch_diff_missing")
    if outside:
        reasons.append("changed_files_outside_owned_paths")
    if protected:
        reasons.append("protected_shared_files_touched")
    if registry_status == "failed":
        reasons.append("docs_registry_gate_failed")
    if validation.get("status") not in {"passed", "pass", "ok"}:
        reasons.append("validation_not_passed")
    return {
        "task_id": task_id,
        "candidate": not reasons,
        "reasons": reasons,
        "issue_id": item.get("issue_id"),
        "risk": item.get("risk"),
        "dependencies": item.get("dependencies") or [],
        "owned_paths": dispatch.owned_paths_for(item),
        "patch_bundle": rel(path),
        "patch_file": rel(patch_diff_path(run_dir, patch)),
        "changed_files": changed_files,
        "registry_gate": registry_status,
        "registry_reason": registry_reason,
        "validation_status": validation.get("status", "unknown"),
    }


def create_apply_plan(run_dir: Path) -> dict[str, Any]:
    ids = ordered_task_ids(run_dir)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_files: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for task_id in ids:
        record = candidate_record(run_dir, task_id)
        if record["candidate"]:
            task_conflicts = []
            for changed in record.get("changed_files") or []:
                if changed in seen_files:
                    task_conflicts.append({"file": changed, "first_task": seen_files[changed], "second_task": task_id})
                else:
                    seen_files[changed] = task_id
            if task_conflicts:
                conflicts.extend(task_conflicts)
                record["candidate"] = False
                record.setdefault("reasons", []).append("patch_conflict")
                rejected.append(record)
            else:
                candidates.append(record)
        else:
            rejected.append(record)
    payload = {
        "schema_version": "factory-apply-plan/v1",
        "run_id": run_dir.name,
        "base_sha": dispatch.git_sha(),
        "mode": "safe_integration",
        "merge_order": ids,
        "candidates": candidates,
        "rejected": rejected,
        "conflicts": conflicts,
        "generated_at": now_iso(),
        "ai_calls_used": 0,
    }
    write_json(integration_dir(run_dir) / "apply-plan.json", payload)
    update_integration_state(run_dir)
    return payload


def read_branch_metadata(run_dir: Path) -> dict[str, Any]:
    path = integration_dir(run_dir) / "integration-branch.json"
    return read_json(path) if path.exists() else {}


def worktree_is_safe_to_remove(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    allowed_roots = [INTEGRATION_WORKTREE_ROOT.resolve(), Path("/tmp").resolve()]
    return any(resolved == root or root in resolved.parents for root in allowed_roots)


def remove_existing_worktree(path: Path) -> None:
    if not path.exists():
        return
    if not worktree_is_safe_to_remove(path):
        raise FactoryIntegratorError(f"refusing to remove non-generated worktree path: {path}")
    run(["git", "worktree", "remove", "--force", str(path)], cwd=ROOT, timeout=60)
    if path.exists():
        shutil.rmtree(path)


def prepare_branch(run_dir: Path, *, branch: str = "", worktree: str | Path | None = None, dry_run: bool = False) -> dict[str, Any]:
    branch_name = branch or default_branch(run_dir)
    worktree_path = Path(worktree).expanduser() if worktree else default_worktree(run_dir)
    if not worktree_path.is_absolute():
        worktree_path = ROOT / worktree_path
    payload = {
        "schema_version": "factory-integration-branch/v1",
        "run_id": run_dir.name,
        "branch": branch_name,
        "base_sha": dispatch.git_sha(short=False),
        "worktree": rel(worktree_path),
        "status": "planned" if dry_run else "prepared",
        "created_at": now_iso(),
        "dry_run": dry_run,
        "commands": [],
    }
    if not dry_run:
        remove_existing_worktree(worktree_path)
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        result = run(["git", "worktree", "add", "-f", "-B", branch_name, str(worktree_path), "HEAD"], cwd=ROOT, timeout=120)
        payload["commands"].append(result)
        if result["exit_code"] != 0:
            payload["status"] = "failed"
            write_json(integration_dir(run_dir) / "integration-branch.json", payload)
            raise FactoryIntegratorError(result["stderr_tail"] or result["stdout_tail"] or "git worktree add failed")
    write_json(integration_dir(run_dir) / "integration-branch.json", payload)
    update_integration_state(run_dir)
    return payload


def shell_command(command: Any) -> tuple[list[str] | str, bool]:
    if isinstance(command, list):
        return [str(item) for item in command], False
    return str(command), True


def run_validation_commands(run_dir: Path, task_id: str, worktree: Path, changed_files: list[str]) -> dict[str, Any]:
    manifest_path = validation_manifest_path(run_dir, task_id)
    checks = []
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        checks = [item for item in manifest.get("checks") or [] if isinstance(item, dict) and item.get("type") == "command"]
    results: list[dict[str, Any]] = []
    for index, check in enumerate(checks, start=1):
        command, use_shell = shell_command(check.get("command"))
        cwd = worktree / str(check.get("cwd") or ".")
        if not cwd.exists():
            cwd = worktree
        started = time.perf_counter()
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=use_shell,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=int(check.get("timeout_seconds") or 20),
            check=False,
        )
        expect = int(check.get("expect_exit", 0) or 0)
        results.append(
            {
                "name": str(check.get("name") or f"command-{index}"),
                "command": command,
                "cwd": rel(cwd),
                "exit_code": proc.returncode,
                "expected_exit": expect,
                "passed": proc.returncode == expect,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "stdout_tail": proc.stdout[-800:],
                "stderr_tail": proc.stderr[-800:],
            }
        )
    if not results:
        for changed in changed_files:
            target = worktree / changed
            results.append(
                {
                    "name": f"file-exists-{Path(changed).name}",
                    "command": ["test", "-f", changed],
                    "cwd": rel(worktree),
                    "exit_code": 0 if target.exists() else 1,
                    "expected_exit": 0,
                    "passed": target.exists(),
                    "duration_ms": 0,
                    "stdout_tail": "",
                    "stderr_tail": "",
                }
            )
    return {
        "schema_version": "factory-per-patch-validation/v1",
        "task_id": task_id,
        "decision": "passed" if all(item["passed"] for item in results) else "failed",
        "commands": results,
        "ai_calls_used": 0,
        "duration_ms": round(sum(float(item.get("duration_ms") or 0) for item in results), 3),
    }


def quarantine_patch(run_dir: Path, record: dict[str, Any], reason: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    task_id = str(record.get("task_id") or "")
    dest = integration_dir(run_dir) / "quarantine" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    patch_json = patch_json_path(run_dir, task_id)
    if patch_json.exists():
        shutil.copy2(patch_json, dest / "patch.json")
        patch = read_json(patch_json)
        diff = patch_diff_path(run_dir, patch)
        if diff.exists():
            shutil.copy2(diff, dest / "patch.diff")
    payload = {
        "schema_version": "factory-quarantine/v1",
        "task_id": task_id,
        "reason": reason,
        "detail": detail or {},
        "quarantined_at": now_iso(),
        "recommendation": "Review the patch bundle, regenerate from the worker with narrower scope, then rerun Factory Safe Integrator.",
    }
    write_json(dest / "failure.json", payload)
    return {"task_id": task_id, "path": rel(dest), "reason": reason}


def rollback_patch(worktree: Path, patch_file: Path) -> dict[str, Any]:
    if not patch_file.exists():
        return {"command": ["git", "apply", "-R", str(patch_file)], "exit_code": 1, "passed": False, "stderr_tail": "patch file missing"}
    check = run(["git", "apply", "-R", "--check", str(patch_file)], cwd=worktree, timeout=60)
    if check["exit_code"] != 0:
        return check
    return run(["git", "apply", "-R", str(patch_file)], cwd=worktree, timeout=60)


def apply_patches(
    run_dir: Path,
    *,
    worktree: str | Path | None = None,
    branch: str = "",
    limit: int = 0,
    validate_each: bool = False,
) -> dict[str, Any]:
    apply_plan = create_apply_plan(run_dir)
    branch_meta = read_branch_metadata(run_dir)
    worktree_path = Path(worktree).expanduser() if worktree else Path(str(branch_meta.get("worktree") or default_worktree(run_dir)))
    if not worktree_path.is_absolute():
        worktree_path = ROOT / worktree_path
    if not worktree_path.exists():
        branch_meta = prepare_branch(run_dir, branch=branch or str(branch_meta.get("branch") or default_branch(run_dir)), worktree=worktree_path)
    applied: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in apply_plan.get("rejected") or []:
        reason = ",".join(record.get("reasons") or ["candidate_rejected_before_apply"])
        rejected.append({**record, "quarantine": quarantine_patch(run_dir, record, reason, {"phase": "apply_plan"})})
    validations: list[dict[str, Any]] = []
    apply_log = integration_dir(run_dir) / "apply-log.jsonl"
    if apply_log.exists():
        apply_log.unlink()
    candidates = list(apply_plan.get("candidates") or [])
    if limit > 0:
        candidates = candidates[:limit]
    for index, record in enumerate(candidates, start=1):
        task_id = str(record.get("task_id") or "")
        patch = read_json(patch_json_path(run_dir, task_id))
        patch_file = patch_diff_path(run_dir, patch)
        log_base = {"ts": now_iso(), "task_id": task_id, "patch_file": rel(patch_file), "index": index}
        check = run(["git", "apply", "--check", str(patch_file)], cwd=worktree_path, timeout=60)
        append_jsonl(apply_log, {**log_base, "event": "apply_check", "result": check})
        if check["exit_code"] != 0:
            reason = "git_apply_check_failed"
            quarantine = quarantine_patch(run_dir, record, reason, check)
            rejected.append({**record, "reasons": [*record.get("reasons", []), reason], "quarantine": quarantine})
            append_jsonl(apply_log, {**log_base, "event": "rejected", "reason": reason})
            continue
        apply_result = run(["git", "apply", str(patch_file)], cwd=worktree_path, timeout=60)
        append_jsonl(apply_log, {**log_base, "event": "applied_to_worktree", "result": apply_result})
        if apply_result["exit_code"] != 0:
            reason = "git_apply_failed"
            quarantine = quarantine_patch(run_dir, record, reason, apply_result)
            rejected.append({**record, "reasons": [*record.get("reasons", []), reason], "quarantine": quarantine})
            append_jsonl(apply_log, {**log_base, "event": "rejected", "reason": reason})
            continue
        validation = run_validation_commands(run_dir, task_id, worktree_path, list(record.get("changed_files") or [])) if validate_each else {
            "schema_version": "factory-per-patch-validation/v1",
            "task_id": task_id,
            "decision": "skipped",
            "commands": [],
            "ai_calls_used": 0,
            "duration_ms": 0,
        }
        validations.append(validation)
        if validate_each and validation["decision"] != "passed":
            rollback = rollback_patch(worktree_path, patch_file)
            reason = "validation_after_patch_failed"
            quarantine = quarantine_patch(run_dir, record, reason, {"validation": validation, "rollback": rollback})
            rejected.append({**record, "reasons": [*record.get("reasons", []), reason], "quarantine": quarantine})
            append_jsonl(apply_log, {**log_base, "event": "validation_failed_rolled_back", "validation": validation, "rollback": rollback})
            continue
        applied_record = {
            **record,
            "applied_at": now_iso(),
            "worktree": rel(worktree_path),
            "checkpoint": {
                "sequence": index,
                "base_sha": branch_meta.get("base_sha") or dispatch.git_sha(short=False),
            },
            "validation": validation,
        }
        applied.append(applied_record)
        append_jsonl(apply_log, {**log_base, "event": "accepted", "validation": validation})
    applied_payload = {"schema_version": "factory-applied-patches/v1", "run_id": run_dir.name, "patches": applied, "ai_calls_used": 0}
    rejected_payload = {"schema_version": "factory-rejected-patches/v1", "run_id": run_dir.name, "patches": rejected, "ai_calls_used": 0}
    validation_payload = {"schema_version": "factory-validation-after-each-patch/v1", "run_id": run_dir.name, "validations": validations, "ai_calls_used": 0}
    write_json(integration_dir(run_dir) / "applied-patches.json", applied_payload)
    write_json(integration_dir(run_dir) / "rejected-patches.json", rejected_payload)
    write_json(integration_dir(run_dir) / "validation-after-each-patch.json", validation_payload)
    rollback_plan(run_dir)
    registry_gate(run_dir)
    merge_readiness(run_dir)
    taskstream_sync_preview(run_dir)
    update_integration_state(run_dir)
    return {
        "schema_version": "factory-apply-result/v1",
        "run_id": run_dir.name,
        "worktree": rel(worktree_path),
        "applied": applied,
        "rejected": rejected,
        "validations": validations,
        "ai_calls_used": 0,
    }


def rollback_plan(run_dir: Path) -> dict[str, Any]:
    applied = read_json(integration_dir(run_dir) / "applied-patches.json") if (integration_dir(run_dir) / "applied-patches.json").exists() else {"patches": []}
    patches = []
    for item in applied.get("patches") or []:
        task_id = str(item.get("task_id") or "")
        patch_file = str(item.get("patch_file") or rel(run_dir / "patches" / task_id / "patch.diff"))
        patches.append(
            {
                "task_id": task_id,
                "patch_file": patch_file,
                "reverse_command": f"git apply -R {patch_file}",
                "checkpoint": item.get("checkpoint") or {},
            }
        )
    payload = {
        "schema_version": "factory-rollback/v1",
        "run_id": run_dir.name,
        "strategy": "reverse_patch_in_integration_worktree",
        "base_sha": dispatch.git_sha(short=False),
        "patches": patches,
        "generated_at": now_iso(),
    }
    write_json(integration_dir(run_dir) / "rollback-plan.json", payload)
    return payload


def registry_gate(run_dir: Path) -> dict[str, Any]:
    applied = read_json(integration_dir(run_dir) / "applied-patches.json") if (integration_dir(run_dir) / "applied-patches.json").exists() else {"patches": []}
    rows = []
    for item in applied.get("patches") or []:
        changed = [str(path) for path in item.get("changed_files") or []]
        status, reason = docs_gate(changed)
        rows.append({"task_id": item.get("task_id"), "status": status, "reason": reason, "changed_files": changed})
    payload = {
        "schema_version": "factory-registry-gate/v1",
        "run_id": run_dir.name,
        "status": "failed" if any(item["status"] == "failed" for item in rows) else "passed",
        "checks": rows,
        "generated_at": now_iso(),
    }
    write_json(integration_dir(run_dir) / "registry-gate.json", payload)
    return payload


def merge_readiness(run_dir: Path) -> dict[str, Any]:
    applied = read_json(integration_dir(run_dir) / "applied-patches.json") if (integration_dir(run_dir) / "applied-patches.json").exists() else {"patches": []}
    rejected = read_json(integration_dir(run_dir) / "rejected-patches.json") if (integration_dir(run_dir) / "rejected-patches.json").exists() else {"patches": []}
    validation = read_json(integration_dir(run_dir) / "validation-after-each-patch.json") if (integration_dir(run_dir) / "validation-after-each-patch.json").exists() else {"validations": []}
    registry = registry_gate(run_dir)
    branch = read_branch_metadata(run_dir)
    blockers = []
    if not applied.get("patches"):
        blockers.append("no_patches_applied")
    if rejected.get("patches"):
        blockers.append("rejected_patches_present")
    if any(item.get("decision") == "failed" for item in validation.get("validations") or []):
        blockers.append("validation_after_patch_failed")
    if registry.get("status") == "failed":
        blockers.append("registry_gate_failed")
    if not branch:
        blockers.append("integration_branch_missing")
    payload = {
        "schema_version": "factory-merge-readiness/v1",
        "run_id": run_dir.name,
        "decision": "ready_for_human_merge_review" if not blockers else "not_ready",
        "blockers": blockers,
        "applied_count": len(applied.get("patches") or []),
        "rejected_count": len(rejected.get("patches") or []),
        "validation_count": len(validation.get("validations") or []),
        "registry_gate": registry.get("status"),
        "branch": branch,
        "residual_risk": [
            "No automatic merge to main was performed.",
            "Human review is still required before merging the integration branch.",
            "Cross-node build farm validation is deferred.",
        ],
        "generated_at": now_iso(),
        "ai_calls_used": 0,
    }
    write_json(integration_dir(run_dir) / "merge-readiness.json", payload)
    residual = ["# Factory Integration Residual Risks", ""]
    residual.extend(f"- {item}" for item in payload["residual_risk"])
    (integration_dir(run_dir) / "residual-risks.md").write_text("\n".join(residual) + "\n", encoding="utf-8")
    return payload


def taskstream_sync_preview(run_dir: Path) -> dict[str, Any]:
    applied = read_json(integration_dir(run_dir) / "applied-patches.json") if (integration_dir(run_dir) / "applied-patches.json").exists() else {"patches": []}
    rejected = read_json(integration_dir(run_dir) / "rejected-patches.json") if (integration_dir(run_dir) / "rejected-patches.json").exists() else {"patches": []}
    tasks = queue_task_map(run_dir)
    transitions = []
    for item in applied.get("patches") or []:
        task = tasks.get(str(item.get("task_id")), {})
        transitions.append(
            {
                "task_id": item.get("task_id"),
                "issue_id": task.get("issue_id"),
                "from": "Validating",
                "to": "Review",
                "reason": "Patch applied in integration worktree and validation passed.",
                "dry_run": True,
            }
        )
    for item in rejected.get("patches") or []:
        task = tasks.get(str(item.get("task_id")), {})
        transitions.append(
            {
                "task_id": item.get("task_id"),
                "issue_id": task.get("issue_id"),
                "from": "Running",
                "to": "Blocked",
                "reason": ", ".join(item.get("reasons") or ["integration_rejected"]),
                "dry_run": True,
            }
        )
    payload = {
        "schema_version": "factory-taskstream-sync-preview/v1",
        "run_id": run_dir.name,
        "dry_run": True,
        "transitions": transitions,
        "generated_at": now_iso(),
        "ai_calls_used": 0,
    }
    write_json(integration_dir(run_dir) / "taskstream-sync-preview.json", payload)
    return payload


def render_release_candidate(run_dir: Path) -> dict[str, Any]:
    state = update_integration_state(run_dir)
    readiness = read_json(integration_dir(run_dir) / "merge-readiness.json") if (integration_dir(run_dir) / "merge-readiness.json").exists() else merge_readiness(run_dir)
    applied = state.get("applied_patches") or []
    rejected = state.get("rejected_patches") or []
    applied_text = "\n".join(f"- `{item.get('task_id')}`: {', '.join(item.get('changed_files') or [])}" for item in applied) or "- none"
    rejected_text = "\n".join(f"- `{item.get('task_id')}`: {', '.join(item.get('reasons') or [])}" for item in rejected) or "- none"
    template_values = {
        "run_id": run_dir.name,
        "branch": str((state.get("branch") or {}).get("branch") or ""),
        "worktree": str((state.get("branch") or {}).get("worktree") or ""),
        "merge_readiness": str(readiness.get("decision") or ""),
        "applied_count": str(len(applied)),
        "rejected_count": str(len(rejected)),
        "applied_patches": applied_text,
        "rejected_patches": rejected_text,
    }
    candidate = integration_dir(run_dir) / "release-candidate.md"
    candidate.write_text(render_template(ROOT / "templates" / "factory" / "release-candidate.md", template_values), encoding="utf-8")
    (integration_dir(run_dir) / "integration-summary.html").write_text(
        render_template(ROOT / "templates" / "factory" / "integration-summary.html", template_values),
        encoding="utf-8",
    )
    update_integration_state(run_dir)
    return {"release_candidate": rel(candidate), "integration_summary": rel(integration_dir(run_dir) / "integration-summary.html")}


def update_integration_state(run_dir: Path) -> dict[str, Any]:
    idir = integration_dir(run_dir)
    branch = read_json(idir / "integration-branch.json") if (idir / "integration-branch.json").exists() else {}
    apply_plan = read_json(idir / "apply-plan.json") if (idir / "apply-plan.json").exists() else {}
    applied = read_json(idir / "applied-patches.json") if (idir / "applied-patches.json").exists() else {"patches": []}
    rejected = read_json(idir / "rejected-patches.json") if (idir / "rejected-patches.json").exists() else {"patches": apply_plan.get("rejected") or []}
    validation = read_json(idir / "validation-after-each-patch.json") if (idir / "validation-after-each-patch.json").exists() else {"validations": []}
    rollback = read_json(idir / "rollback-plan.json") if (idir / "rollback-plan.json").exists() else {}
    readiness = read_json(idir / "merge-readiness.json") if (idir / "merge-readiness.json").exists() else {}
    taskstream = read_json(idir / "taskstream-sync-preview.json") if (idir / "taskstream-sync-preview.json").exists() else {}
    payload = {
        "schema_version": "factory-integration-state/v1",
        "run_id": run_dir.name,
        "base_sha": dispatch.git_sha(short=False),
        "branch": branch,
        "apply_plan": rel(idir / "apply-plan.json") if (idir / "apply-plan.json").exists() else "",
        "applied_patches": applied.get("patches") or [],
        "rejected_patches": rejected.get("patches") or [],
        "validation_after_each_patch": validation,
        "rollback_plan": rel(idir / "rollback-plan.json") if rollback else "",
        "merge_readiness": readiness,
        "taskstream_sync_preview": taskstream,
        "release_candidate": rel(idir / "release-candidate.md") if (idir / "release-candidate.md").exists() else "",
        "residual_risks": rel(idir / "residual-risks.md") if (idir / "residual-risks.md").exists() else "",
        "updated_at": now_iso(),
        "ai_calls_used": 0,
    }
    write_json(idir / "integration-state.json", payload)
    return payload


def validate_integration_state(path: Path) -> list[str]:
    payload = read_json(path)
    errors: list[str] = []
    if payload.get("schema_version") != "factory-integration-state/v1":
        errors.append("schema_version must be factory-integration-state/v1")
    for field in ("run_id", "base_sha", "branch", "applied_patches", "rejected_patches", "validation_after_each_patch", "rollback_plan", "merge_readiness"):
        if field not in payload:
            errors.append(f"missing field: {field}")
    if not payload.get("rollback_plan"):
        errors.append("rollback_plan must be present")
    if not isinstance(payload.get("applied_patches"), list):
        errors.append("applied_patches must be a list")
    if not isinstance(payload.get("rejected_patches"), list):
        errors.append("rejected_patches must be a list")
    return errors


def validate_integrated(run_dir: Path) -> dict[str, Any]:
    state = update_integration_state(run_dir)
    errors = validate_integration_state(integration_dir(run_dir) / "integration-state.json")
    readiness = merge_readiness(run_dir)
    payload = {
        "schema_version": "factory-integrated-validation/v1",
        "run_id": run_dir.name,
        "decision": "approve" if not errors and readiness.get("decision") == "ready_for_human_merge_review" else "blocked",
        "errors": errors,
        "merge_readiness": readiness,
        "integration_state": rel(integration_dir(run_dir) / "integration-state.json"),
        "ai_calls_used": 0,
        "generated_at": now_iso(),
    }
    write_json(integration_dir(run_dir) / "integrated-validation.json", payload)
    return payload
