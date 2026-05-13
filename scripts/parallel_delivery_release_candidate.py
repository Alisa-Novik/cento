#!/usr/bin/env python3
"""Safe apply and release-candidate artifacts for Parallel Delivery."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs"

SCHEMA_INTEGRATION_RECEIPT = "cento.parallel_delivery.integration_receipt.v1"
SCHEMA_BUNDLE_RECEIPT = "cento.parallel_delivery.bundle_receipt.v1"
SCHEMA_APPLY_STEP_RECEIPT = "cento.parallel_delivery.apply_step_receipt.v1"
SCHEMA_APPLY_REPORT = "cento.parallel_delivery.apply_report.v1"
SCHEMA_ROLLBACK_METADATA = "cento.parallel_delivery.rollback_metadata.v1"
SCHEMA_RELEASE_CANDIDATE = "cento.parallel_delivery.release_candidate.v1"

FORBIDDEN_COMMAND_SNIPPETS = (
    "git reset",
    "git checkout",
    "git clean",
    "git stash",
    ".env.mcp",
    "taskstream db",
    "redmine db",
)


class ReleaseCandidateError(RuntimeError):
    """Expected safe-apply or release-candidate failure."""


@dataclass(frozen=True)
class AcceptedIntegrationReceipt:
    schema: str
    integration_id: str
    run_id: str
    base_commit: str
    status: str
    accepted_bundle_receipts: list[str]
    rejected_bundle_receipts: list[str]
    apply_order: list[str]
    final_validation_commands: list[dict[str, Any]]
    payload: dict[str, Any]
    path: Path


@dataclass(frozen=True)
class BundleApplyPlan:
    bundle_id: str
    task_id: str
    worker_id: str
    receipt_path: Path
    patch_path: Path
    patch_sha256: str
    touched_paths: list[str]
    validation_commands: list[dict[str, Any]]
    step_index: int


@dataclass(frozen=True)
class IntegrationTarget:
    target_repo: Path
    target_worktree: Path
    base_commit: str
    pre_apply_head: str
    rollback_strategy: str
    mode: str


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseCandidateError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseCandidateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseCandidateError(f"expected JSON object in {path}")
    return payload


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def out_rel(path: Path, out_dir: Path) -> str:
    try:
        return path.resolve().relative_to(out_dir.resolve()).as_posix()
    except ValueError:
        return rel(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_existing_path(value: str, roots: list[Path], *, field: str) -> Path:
    path = Path(value)
    candidates = [path] if path.is_absolute() else [root / path for root in roots]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    checked = ", ".join(str(candidate) for candidate in candidates)
    raise ReleaseCandidateError(f"{field} does not exist: {value} (checked {checked})")


def normalize_commands(values: Any) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    if values is None:
        return commands
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        raise ReleaseCandidateError("validation commands must be a list or string")
    for item in values:
        if isinstance(item, str):
            cmd = item.strip()
            timeout = 120
        elif isinstance(item, dict):
            cmd = str(item.get("cmd") or item.get("command") or "").strip()
            timeout = int(item.get("timeout_seconds") or item.get("timeout") or 120)
        else:
            raise ReleaseCandidateError("validation command entries must be strings or objects")
        if not cmd:
            continue
        lowered = cmd.lower()
        for forbidden in FORBIDDEN_COMMAND_SNIPPETS:
            if forbidden in lowered:
                raise ReleaseCandidateError(f"unsafe validation command refused: {cmd}")
        commands.append({"cmd": cmd, "timeout_seconds": timeout})
    return commands


def load_integration_receipt(path: Path) -> AcceptedIntegrationReceipt:
    path = path.resolve()
    payload = read_json(path)
    schema = str(payload.get("schema") or payload.get("schema_version") or "")
    if schema != SCHEMA_INTEGRATION_RECEIPT:
        raise ReleaseCandidateError(f"integration receipt schema mismatch: {schema or '<missing>'}")
    accepted = [str(item) for item in payload.get("accepted_bundle_receipts") or []]
    rejected = [str(item) for item in payload.get("rejected_bundle_receipts") or []]
    apply_order = [str(item) for item in payload.get("apply_order") or []]
    if not accepted:
        raise ReleaseCandidateError("integration receipt has no accepted_bundle_receipts")
    if not apply_order:
        raise ReleaseCandidateError("integration receipt has no apply_order")
    return AcceptedIntegrationReceipt(
        schema=schema,
        integration_id=str(payload.get("integration_id") or path.stem),
        run_id=str(payload.get("run_id") or path.parent.parent.name or path.parent.name),
        base_commit=str(payload.get("base_commit") or ""),
        status=str(payload.get("status") or ""),
        accepted_bundle_receipts=accepted,
        rejected_bundle_receipts=rejected,
        apply_order=apply_order,
        final_validation_commands=normalize_commands(payload.get("final_validation_commands") or []),
        payload=payload,
        path=path,
    )


def assert_integration_receipt_accepted(receipt: AcceptedIntegrationReceipt) -> None:
    if receipt.status != "accepted":
        raise ReleaseCandidateError(f"integration receipt is not accepted: {receipt.status or '<missing>'}")


def receipt_bundle_id(payload: dict[str, Any]) -> str:
    return str(payload.get("bundle_id") or payload.get("id") or payload.get("patch_bundle_id") or "")


def receipt_status(payload: dict[str, Any]) -> str:
    return str(payload.get("validation_status") or payload.get("status") or "").lower()


def receipt_bool(payload: dict[str, Any], key: str) -> bool:
    return payload.get(key) is True or str(payload.get(key)).lower() == "true"


def receipt_touched_paths(payload: dict[str, Any]) -> list[str]:
    values = payload.get("touched_paths") or payload.get("changed_paths") or payload.get("changed_files") or []
    return [str(item) for item in values if str(item)]


def load_receipt_list(paths: list[str], *, root: Path) -> dict[str, tuple[Path, dict[str, Any]]]:
    loaded: dict[str, tuple[Path, dict[str, Any]]] = {}
    for value in paths:
        path = resolve_existing_path(value, [root], field="bundle receipt")
        payload = read_json(path)
        bundle_id = receipt_bundle_id(payload)
        if not bundle_id:
            raise ReleaseCandidateError(f"bundle receipt missing bundle_id: {path}")
        loaded[bundle_id] = (path, payload)
    return loaded


def load_and_verify_bundle_receipts(
    integration_receipt: AcceptedIntegrationReceipt,
    *,
    receipt_root: Path | None = None,
    expected_base_commit: str | None = None,
) -> list[BundleApplyPlan]:
    receipt_root = receipt_root or integration_receipt.path.parent
    if expected_base_commit and integration_receipt.base_commit and integration_receipt.base_commit != expected_base_commit:
        raise ReleaseCandidateError(
            f"base commit mismatch: receipt={integration_receipt.base_commit} expected={expected_base_commit}"
        )
    accepted = load_receipt_list(integration_receipt.accepted_bundle_receipts, root=receipt_root)
    rejected = load_receipt_list(integration_receipt.rejected_bundle_receipts, root=receipt_root) if integration_receipt.rejected_bundle_receipts else {}
    rejected_in_order = [bundle_id for bundle_id in integration_receipt.apply_order if bundle_id in rejected]
    if rejected_in_order:
        raise ReleaseCandidateError("apply_order includes rejected bundle(s): " + ", ".join(rejected_in_order))

    plans: list[BundleApplyPlan] = []
    for index, bundle_id in enumerate(integration_receipt.apply_order, start=1):
        if bundle_id not in accepted:
            raise ReleaseCandidateError(f"apply_order bundle has no accepted receipt: {bundle_id}")
        receipt_path, payload = accepted[bundle_id]
        status = receipt_status(payload)
        if status not in {"accepted", "passed", "validated"}:
            raise ReleaseCandidateError(f"bundle receipt is not accepted: {bundle_id} status={status or '<missing>'}")
        if not receipt_bool(payload, "integratable"):
            raise ReleaseCandidateError(f"bundle receipt is not integratable: {bundle_id}")
        bundle_base = str(payload.get("base_commit") or payload.get("base_ref") or "")
        if expected_base_commit and bundle_base and bundle_base != expected_base_commit:
            raise ReleaseCandidateError(f"bundle base commit mismatch for {bundle_id}: {bundle_base}")
        patch_value = str(payload.get("patch_path") or payload.get("diff_path") or payload.get("patch_file") or "")
        if not patch_value:
            raise ReleaseCandidateError(f"bundle receipt missing patch path: {bundle_id}")
        patch_path = resolve_existing_path(patch_value, [receipt_path.parent, receipt_root], field="patch path")
        expected_sha = str(payload.get("patch_sha256") or payload.get("sha256") or "")
        actual_sha = sha256_file(patch_path)
        if not expected_sha:
            raise ReleaseCandidateError(f"bundle receipt missing patch_sha256: {bundle_id}")
        if expected_sha != actual_sha:
            raise ReleaseCandidateError(f"patch sha256 mismatch for {bundle_id}: receipt={expected_sha} actual={actual_sha}")
        validation_commands = normalize_commands(payload.get("validation_commands") or payload.get("validation") or [])
        if not validation_commands:
            validation_commands = [{"cmd": "test -d .", "timeout_seconds": 30}]
        plans.append(
            BundleApplyPlan(
                bundle_id=bundle_id,
                task_id=str(payload.get("task_id") or bundle_id),
                worker_id=str(payload.get("worker_id") or "worker"),
                receipt_path=receipt_path,
                patch_path=patch_path,
                patch_sha256=actual_sha,
                touched_paths=receipt_touched_paths(payload),
                validation_commands=validation_commands,
                step_index=index,
            )
        )
    return plans


def safe_target_path(path: Path) -> bool:
    resolved = path.resolve()
    allowed = [
        (ROOT / "workspace" / "runs").resolve(),
        (ROOT / "workspace" / "factory-integration-worktrees").resolve(),
        Path("/tmp").resolve(),
    ]
    return any(resolved == root or root in resolved.parents for root in allowed)


def target_head(path: Path, fallback: str) -> str:
    if not (path / ".git").exists():
        return fallback
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else fallback


def resolve_expected_base_commit(value: str | None) -> str | None:
    if not value:
        return None
    if value == "HEAD":
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else value
    return value


def prepare_integration_target(
    *,
    target_repo: Path,
    target_worktree: Path | None,
    base_commit: str,
    out_dir: Path,
    mode: Literal["dry-run", "apply"],
    use_factory: bool = False,
) -> IntegrationTarget:
    del use_factory
    target_repo = target_repo.resolve()
    if not target_repo.exists() or not target_repo.is_dir():
        raise ReleaseCandidateError(f"target repo does not exist: {target_repo}")
    if mode == "dry-run":
        return IntegrationTarget(
            target_repo=target_repo,
            target_worktree=target_repo,
            base_commit=base_commit,
            pre_apply_head=target_head(target_repo, base_commit),
            rollback_strategy="dry_run_no_changes",
            mode=mode,
        )
    if target_worktree is None:
        raise ReleaseCandidateError("apply mode requires --target-worktree")
    target_worktree = target_worktree.resolve()
    if not safe_target_path(target_worktree):
        raise ReleaseCandidateError(f"target worktree must be under workspace/runs, workspace/factory-integration-worktrees, or /tmp: {target_worktree}")
    if target_worktree.exists() and any(target_worktree.iterdir()):
        raise ReleaseCandidateError(f"target worktree already exists and is not empty: {target_worktree}")
    target_worktree.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache", "apply", "dry-run", "rejected-receipt")
    shutil.copytree(target_repo, target_worktree, ignore=ignore, dirs_exist_ok=True)
    return IntegrationTarget(
        target_repo=target_repo,
        target_worktree=target_worktree,
        base_commit=base_commit,
        pre_apply_head=target_head(target_worktree, base_commit),
        rollback_strategy="isolated_worktree_abandonment",
        mode=mode,
    )


def run_capture(command: str, *, cwd: Path, out_dir: Path, log_name: str, timeout: int = 120) -> dict[str, Any]:
    if command.startswith("python ") and shutil.which("python") is None and shutil.which("python3"):
        command = "python3 " + command[len("python ") :]
    lowered = command.lower()
    for forbidden in FORBIDDEN_COMMAND_SNIPPETS:
        if forbidden in lowered:
            raise ReleaseCandidateError(f"unsafe command refused: {command}")
    logs = out_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / f"{log_name}.stdout"
    stderr_path = logs / f"{log_name}.stderr"
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")
    return {
        "cmd": command,
        "exit_code": proc.returncode,
        "stdout_path": out_rel(stdout_path, out_dir),
        "stderr_path": out_rel(stderr_path, out_dir),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def dry_run_bundle_apply(target: IntegrationTarget, bundle: BundleApplyPlan, out_dir: Path) -> dict[str, Any]:
    command = f"git -C {sh_quote(target.target_worktree)} apply --check --whitespace=error-all {sh_quote(bundle.patch_path)}"
    return run_capture(command, cwd=ROOT, out_dir=out_dir, log_name=f"{bundle.bundle_id}.dry-run", timeout=120)


def apply_bundle(target: IntegrationTarget, bundle: BundleApplyPlan, out_dir: Path) -> dict[str, Any]:
    command = f"git -C {sh_quote(target.target_worktree)} apply --whitespace=nowarn {sh_quote(bundle.patch_path)}"
    return run_capture(command, cwd=ROOT, out_dir=out_dir, log_name=f"{bundle.bundle_id}.apply", timeout=120)


def run_bundle_validation(target: IntegrationTarget, bundle: BundleApplyPlan, out_dir: Path) -> list[dict[str, Any]]:
    results = []
    for index, command in enumerate(bundle.validation_commands, start=1):
        results.append(
            run_capture(
                str(command["cmd"]),
                cwd=target.target_worktree,
                out_dir=out_dir,
                log_name=f"{bundle.bundle_id}.validation.{index}",
                timeout=int(command.get("timeout_seconds") or 120),
            )
        )
        if results[-1]["exit_code"] != 0:
            break
    return results


def run_final_validation(target: IntegrationTarget, commands: list[dict[str, Any]], out_dir: Path) -> list[dict[str, Any]]:
    commands = commands or [{"cmd": "test -d .", "timeout_seconds": 30}]
    results = []
    for index, command in enumerate(commands, start=1):
        results.append(
            run_capture(
                str(command["cmd"]),
                cwd=target.target_worktree,
                out_dir=out_dir,
                log_name=f"final-validation.{index}",
                timeout=int(command.get("timeout_seconds") or 120),
            )
        )
        if results[-1]["exit_code"] != 0:
            break
    return results


def sh_quote(path: Path | str) -> str:
    return "'" + str(path).replace("'", "'\"'\"'") + "'"


def step_receipt_payload(
    *,
    receipt: AcceptedIntegrationReceipt,
    target: IntegrationTarget,
    bundle: BundleApplyPlan,
    mode: str,
    status: str,
    dry_run: dict[str, Any],
    apply_result: dict[str, Any] | None,
    validation: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_APPLY_STEP_RECEIPT,
        "integration_id": receipt.integration_id,
        "run_id": receipt.run_id,
        "bundle_id": bundle.bundle_id,
        "task_id": bundle.task_id,
        "worker_id": bundle.worker_id,
        "step_index": bundle.step_index,
        "mode": mode,
        "status": status,
        "base_commit": receipt.base_commit,
        "target_repo": rel(target.target_repo),
        "target_worktree": rel(target.target_worktree),
        "patch_path": rel(bundle.patch_path),
        "patch_sha256": bundle.patch_sha256,
        "dry_run": dry_run,
        "apply": apply_result,
        "validation": validation,
        "touched_paths": bundle.touched_paths,
        "created_at": timestamp,
    }


def write_step_receipt(out_dir: Path, bundle: BundleApplyPlan, payload: dict[str, Any]) -> str:
    path = out_dir / "apply-receipts" / f"step-{bundle.step_index:03d}-{bundle.bundle_id}.json"
    write_json(path, payload)
    return out_rel(path, out_dir)


def write_rollback_metadata(
    *,
    out_dir: Path,
    receipt: AcceptedIntegrationReceipt,
    target: IntegrationTarget | None,
    mode: str,
    applied_bundle_ids: list[str],
    failed_bundle_id: str | None,
    failure_reason: str | None,
    timestamp: str,
) -> str:
    target_repo = target.target_repo if target else Path("")
    target_worktree = target.target_worktree if target else Path("")
    payload = {
        "schema": SCHEMA_ROLLBACK_METADATA,
        "integration_id": receipt.integration_id,
        "run_id": receipt.run_id,
        "mode": mode,
        "rollback_strategy": target.rollback_strategy if target else "dry_run_no_changes",
        "factory_receipt": None,
        "target_repo": rel(target_repo) if target else "",
        "target_worktree": rel(target_worktree) if target else "",
        "pre_apply_head": target.pre_apply_head if target else receipt.base_commit,
        "post_apply_head": target_head(target_worktree, receipt.base_commit) if target else receipt.base_commit,
        "applied_bundle_ids": applied_bundle_ids,
        "failed_bundle_id": failed_bundle_id,
        "failure_reason": failure_reason,
        "safe_cleanup_owner": "factory_or_operator",
        "destructive_commands_used": False,
        "created_at": timestamp,
    }
    path = out_dir / "rollback-metadata.json"
    write_json(path, payload)
    return out_rel(path, out_dir)


def write_integrated_diff(target: IntegrationTarget, out_dir: Path) -> str:
    path = out_dir / "integrated.diff"
    command = [
        "diff",
        "-ruN",
        "--exclude=.git",
        "--exclude=__pycache__",
        "--exclude=.pytest_cache",
        str(target.target_repo),
        str(target.target_worktree),
    ]
    proc = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    path.write_text(proc.stdout if proc.stdout else proc.stderr, encoding="utf-8")
    return out_rel(path, out_dir)


def write_release_notes(
    *,
    out_dir: Path,
    receipt: AcceptedIntegrationReceipt,
    plans: list[BundleApplyPlan],
    rejected_bundle_ids: list[str],
    final_validation: list[dict[str, Any]],
) -> str:
    lines = [
        "# Parallel Delivery Release Notes Draft",
        "",
        f"- Integration ID: `{receipt.integration_id}`",
        f"- Run ID: `{receipt.run_id}`",
        f"- Base commit: `{receipt.base_commit}`",
        "",
        "## Accepted Bundles",
    ]
    for plan in plans:
        touched = ", ".join(plan.touched_paths) or "no touched paths recorded"
        lines.append(f"- `{plan.bundle_id}` (`{plan.task_id}`): {touched}")
    lines.extend(["", "## Rejected Bundles Not Included"])
    if rejected_bundle_ids:
        lines.extend(f"- `{bundle_id}`" for bundle_id in rejected_bundle_ids)
    else:
        lines.append("- none")
    lines.extend(["", "## Final Validation"])
    if final_validation:
        for item in final_validation:
            status = "passed" if item["exit_code"] == 0 else "failed"
            lines.append(f"- `{item['cmd']}`: {status} ({item['stdout_path']}, {item['stderr_path']})")
    else:
        lines.append("- not run")
    lines.extend(["", "## Rollback", "- Rollback is metadata-only through isolated worktree abandonment. No destructive cleanup was performed."])
    path = out_dir / "release-notes.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_rel(path, out_dir)


def create_release_candidate_packet(
    *,
    integration_receipt: AcceptedIntegrationReceipt,
    apply_report: dict[str, Any],
    target: IntegrationTarget,
    plans: list[BundleApplyPlan],
    out_dir: Path,
    final_validation: list[dict[str, Any]],
    timestamp: str,
) -> dict[str, Any]:
    integrated_diff = write_integrated_diff(target, out_dir)
    release_notes = write_release_notes(
        out_dir=out_dir,
        receipt=integration_receipt,
        plans=plans,
        rejected_bundle_ids=[receipt_bundle_id(read_json(resolve_existing_path(path, [integration_receipt.path.parent], field="rejected bundle receipt"))) for path in integration_receipt.rejected_bundle_receipts],
        final_validation=final_validation,
    )
    payload = {
        "schema": SCHEMA_RELEASE_CANDIDATE,
        "release_candidate_id": f"rc-{integration_receipt.run_id}-{integration_receipt.integration_id}",
        "integration_id": integration_receipt.integration_id,
        "run_id": integration_receipt.run_id,
        "status": "ready",
        "base_commit": integration_receipt.base_commit,
        "target_worktree": rel(target.target_worktree),
        "bundle_ids": [plan.bundle_id for plan in plans],
        "task_ids": [plan.task_id for plan in plans],
        "touched_paths": sorted({path for plan in plans for path in plan.touched_paths}),
        "apply_report": out_rel(out_dir / "apply-report.json", out_dir),
        "step_receipts": apply_report.get("step_receipts") or [],
        "integrated_diff": integrated_diff,
        "release_notes": release_notes,
        "final_validation_status": "passed",
        "created_at": timestamp,
    }
    write_json(out_dir / "release-candidate.json", payload)
    return payload


def write_apply_report_md(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Parallel Delivery Apply Report",
        "",
        f"- Integration ID: `{report.get('integration_id')}`",
        f"- Run ID: `{report.get('run_id')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Status: `{report.get('status')}`",
        f"- Accepted bundles: `{report.get('accepted_bundle_count')}`",
        f"- Applied bundles: `{report.get('applied_bundle_count')}`",
        f"- Failed bundle: `{report.get('failed_bundle_id') or 'none'}`",
        f"- Rollback metadata: `{report.get('rollback_metadata')}`",
    ]
    if report.get("release_candidate"):
        lines.append(f"- Release candidate: `{report.get('release_candidate')}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_validation_summary(root: Path, report: dict[str, Any]) -> None:
    path = root / "validation-summary.txt"
    previous = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = [
        f"integration ID: {report.get('integration_id')}",
        f"run ID: {report.get('run_id')}",
        f"base commit: {report.get('base_commit')}",
        f"{report.get('mode')} status: {report.get('status')}",
        f"accepted bundle count: {report.get('accepted_bundle_count')}",
        f"applied bundle count: {report.get('applied_bundle_count')}",
        f"rejected receipt refusal status: see rejected-receipt.exit-code if present",
        f"final validation: {(report.get('final_validation') or {}).get('status')}",
        f"release candidate artifact path: {report.get('release_candidate')}",
        f"release notes path: {report.get('release_notes')}",
        f"rollback metadata path: {report.get('rollback_metadata')}",
        "",
    ]
    path.write_text((previous + "\n" if previous else "") + "\n".join(lines), encoding="utf-8")


def create_release_candidate(
    *,
    integration_receipt_path: Path,
    out_dir: Path,
    mode: Literal["dry-run", "apply"],
    target_repo: Path,
    target_worktree: Path | None = None,
    expected_base_commit: str | None = None,
    final_validation_commands: list[str] | None = None,
    use_factory: bool = False,
    stop_on_first_failure: bool = True,
    fixed_timestamp: str | None = None,
) -> dict[str, Any]:
    del stop_on_first_failure
    timestamp = fixed_timestamp or now_iso()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "apply-receipts").mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    receipt = load_integration_receipt(integration_receipt_path)
    assert_integration_receipt_accepted(receipt)
    plans = load_and_verify_bundle_receipts(receipt, receipt_root=receipt.path.parent, expected_base_commit=expected_base_commit)
    target = prepare_integration_target(
        target_repo=target_repo,
        target_worktree=target_worktree,
        base_commit=receipt.base_commit or expected_base_commit or "",
        out_dir=out_dir,
        mode=mode,
        use_factory=use_factory,
    )

    step_receipts: list[str] = []
    applied_bundle_ids: list[str] = []
    failed_bundle_id: str | None = None
    failure_reason: str | None = None
    final_validation: list[dict[str, Any]] = []
    release_candidate: dict[str, Any] | None = None

    for plan in plans:
        dry_run = dry_run_bundle_apply(target, plan, out_dir)
        apply_result: dict[str, Any] | None = None
        validation: list[dict[str, Any]] = []
        status = "dry_run_passed"
        if dry_run["exit_code"] != 0:
            status = "dry_run_failed"
            failed_bundle_id = plan.bundle_id
            failure_reason = "apply_check_failed"
        elif mode == "apply":
            apply_result = apply_bundle(target, plan, out_dir)
            if apply_result["exit_code"] != 0:
                status = "apply_failed"
                failed_bundle_id = plan.bundle_id
                failure_reason = "apply_failed"
            else:
                validation = run_bundle_validation(target, plan, out_dir)
                if any(item["exit_code"] != 0 for item in validation):
                    status = "validation_failed"
                    failed_bundle_id = plan.bundle_id
                    failure_reason = "bundle_validation_failed"
                else:
                    status = "applied"
                    applied_bundle_ids.append(plan.bundle_id)
        step_payload = step_receipt_payload(
            receipt=receipt,
            target=target,
            bundle=plan,
            mode=mode,
            status=status,
            dry_run=dry_run,
            apply_result=apply_result,
            validation=validation,
            timestamp=timestamp,
        )
        step_receipts.append(write_step_receipt(out_dir, plan, step_payload))
        if failed_bundle_id:
            break

    if failed_bundle_id:
        report_status = "dry_run_failed" if mode == "dry-run" else "failed"
    elif mode == "dry-run":
        report_status = "dry_run_succeeded"
    else:
        final_commands = normalize_commands(final_validation_commands or []) + receipt.final_validation_commands
        final_validation = run_final_validation(target, final_commands, out_dir)
        if any(item["exit_code"] != 0 for item in final_validation):
            report_status = "final_validation_failed"
            failure_reason = "final_validation_failed"
        else:
            report_status = "succeeded"

    rollback_path = write_rollback_metadata(
        out_dir=out_dir,
        receipt=receipt,
        target=target,
        mode=mode,
        applied_bundle_ids=applied_bundle_ids,
        failed_bundle_id=failed_bundle_id,
        failure_reason=failure_reason,
        timestamp=timestamp,
    )

    report = {
        "schema": SCHEMA_APPLY_REPORT,
        "integration_id": receipt.integration_id,
        "run_id": receipt.run_id,
        "mode": mode,
        "status": report_status,
        "base_commit": receipt.base_commit,
        "target_repo": rel(target.target_repo),
        "target_worktree": rel(target.target_worktree),
        "accepted_bundle_count": len(plans),
        "applied_bundle_count": len(applied_bundle_ids),
        "failed_bundle_id": failed_bundle_id,
        "stopped_on_first_failure": bool(failed_bundle_id or failure_reason),
        "step_receipts": step_receipts,
        "final_validation": {
            "status": "passed" if final_validation and all(item["exit_code"] == 0 for item in final_validation) else ("skipped" if not final_validation else "failed"),
            "commands": final_validation,
        },
        "release_candidate": None,
        "release_notes": None,
        "rollback_metadata": rollback_path,
    }
    if mode == "apply" and report_status == "succeeded":
        release_candidate = create_release_candidate_packet(
            integration_receipt=receipt,
            apply_report=report,
            target=target,
            plans=plans,
            out_dir=out_dir,
            final_validation=final_validation,
            timestamp=timestamp,
        )
        report["release_candidate"] = out_rel(out_dir / "release-candidate.json", out_dir)
        report["release_notes"] = release_candidate["release_notes"]
    write_json(out_dir / "apply-report.json", report)
    write_apply_report_md(out_dir / "apply-report.md", report)
    write_validation_summary(out_dir.parent, report)
    return report


def write_refusal(out_dir: Path, message: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        out_dir / "refusal.json",
        {
            "schema": "cento.parallel_delivery.release_candidate_refusal.v1",
            "status": "refused",
            "reason": message,
            "created_at": now_iso(),
        },
    )


def fixture_patch_1() -> str:
    return """diff --git a/src/example.py b/src/example.py
--- a/src/example.py
+++ b/src/example.py
@@ -1,2 +1,2 @@
 def greet():
-    return "hello"
+    return "hello patch swarm"
"""


def fixture_patch_2() -> str:
    return (
        "diff --git a/tests/test_example.py b/tests/test_example.py\n"
        "--- a/tests/test_example.py\n"
        "+++ b/tests/test_example.py\n"
        "@@ -1,4 +1,4 @@\n"
        " from src.example import greet\n"
        " \n"
        " def test_greet():\n"
        "-    assert greet() == \"hello\"\n"
        "+    assert greet() == \"hello patch swarm\"\n"
    )


def fixture_patch_rejected() -> str:
    return """diff --git a/README.md b/README.md
new file mode 100644
--- /dev/null
+++ b/README.md
@@ -0,0 +1 @@
+Rejected patch should never be applied.
"""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_release_candidate_fixture(out_dir: Path, *, base_commit: str, timestamp: str | None = None) -> dict[str, Any]:
    timestamp = timestamp or now_iso()
    input_dir = out_dir / "input"
    patches_dir = input_dir / "patches"
    receipts_dir = input_dir / "bundle-receipts"
    fixture_repo = out_dir / "fixture-repo"
    write_text(fixture_repo / "src" / "__init__.py", "")
    write_text(fixture_repo / "src" / "example.py", 'def greet():\n    return "hello"\n')
    write_text(fixture_repo / "tests" / "test_example.py", 'from src.example import greet\n\ndef test_greet():\n    assert greet() == "hello"\n')

    patches = {
        "bundle-safe-001": fixture_patch_1(),
        "bundle-safe-002": fixture_patch_2(),
        "bundle-rejected-001": fixture_patch_rejected(),
    }
    for bundle_id, text in patches.items():
        write_text(patches_dir / f"{bundle_id}.diff", text)

    receipt_specs = [
        {
            "bundle_id": "bundle-safe-001",
            "task_id": "task-owned-src",
            "worker_id": "worker-a",
            "validation_status": "accepted",
            "integratable": True,
            "patch_path": "../patches/bundle-safe-001.diff",
            "touched_paths": ["src/example.py"],
            "validation_commands": [{"cmd": "python3 -m py_compile src/example.py"}],
        },
        {
            "bundle_id": "bundle-safe-002",
            "task_id": "task-owned-tests",
            "worker_id": "worker-b",
            "validation_status": "accepted",
            "integratable": True,
            "patch_path": "../patches/bundle-safe-002.diff",
            "touched_paths": ["tests/test_example.py"],
            "validation_commands": [{"cmd": "python3 -m pytest -q tests"}],
        },
        {
            "bundle_id": "bundle-rejected-001",
            "task_id": "task-rejected",
            "worker_id": "worker-c",
            "validation_status": "rejected",
            "integratable": False,
            "patch_path": "../patches/bundle-rejected-001.diff",
            "touched_paths": ["README.md"],
            "validation_commands": [],
        },
    ]
    receipt_paths = []
    for spec in receipt_specs:
        patch_path = patches_dir / f"{spec['bundle_id']}.diff"
        payload = {
            "schema": SCHEMA_BUNDLE_RECEIPT,
            "base_commit": base_commit,
            "patch_sha256": sha256_file(patch_path),
            **spec,
        }
        receipt_path = receipts_dir / f"receipt-{spec['bundle_id']}.json"
        write_json(receipt_path, payload)
        receipt_paths.append(receipt_path)

    accepted = {
        "schema": SCHEMA_INTEGRATION_RECEIPT,
        "integration_id": "integration-fixture-001",
        "run_id": out_dir.name,
        "base_commit": base_commit,
        "status": "accepted",
        "accepted_bundle_receipts": [
            "bundle-receipts/receipt-bundle-safe-001.json",
            "bundle-receipts/receipt-bundle-safe-002.json",
        ],
        "rejected_bundle_receipts": ["bundle-receipts/receipt-bundle-rejected-001.json"],
        "apply_order": ["bundle-safe-001", "bundle-safe-002"],
        "final_validation_commands": [{"cmd": "python3 -m pytest -q tests"}],
        "accepted_by": "local-operator",
        "accepted_at": timestamp,
        "notes": "Fixture integration receipt.",
    }
    rejected = {**accepted, "status": "rejected", "integration_id": "integration-fixture-rejected-001"}
    write_json(input_dir / "integration-receipt.accepted.json", accepted)
    write_json(input_dir / "integration-receipt.rejected.json", rejected)
    summary = {
        "ok": True,
        "run_dir": rel(out_dir),
        "base_commit": base_commit,
        "integration_receipt": rel(input_dir / "integration-receipt.accepted.json"),
        "rejected_integration_receipt": rel(input_dir / "integration-receipt.rejected.json"),
        "bundle_receipts": [rel(path) for path in receipt_paths],
        "fixture_repo": rel(fixture_repo),
    }
    write_validation_summary(out_dir, {"integration_id": "integration-fixture-001", "run_id": out_dir.name, "base_commit": base_commit, "mode": "fixture", "status": "created", "accepted_bundle_count": 2, "applied_bundle_count": 0})
    return summary


def add_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--integration-receipt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--target-repo", default=str(ROOT))
    parser.add_argument("--target-worktree", default="")
    parser.add_argument("--base-commit", default="")
    parser.add_argument("--use-factory-worktree", action="store_true")
    parser.add_argument("--final-validation-cmd", action="append", default=[])
    parser.add_argument("--json", action="store_true")


def run_create_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    out_dir = Path(args.out)
    try:
        report = create_release_candidate(
            integration_receipt_path=Path(args.integration_receipt),
            out_dir=out_dir,
            mode=args.mode,
            target_repo=Path(args.target_repo),
            target_worktree=Path(args.target_worktree) if args.target_worktree else None,
            expected_base_commit=resolve_expected_base_commit(args.base_commit),
            final_validation_commands=list(args.final_validation_cmd or []),
            use_factory=bool(args.use_factory_worktree),
        )
    except ReleaseCandidateError as exc:
        write_refusal(out_dir, str(exc))
        return {"ok": False, "status": "refused", "error": str(exc), "out": rel(out_dir)}, 1
    ok = report["status"] in {"dry_run_succeeded", "succeeded"}
    return {"ok": ok, **report}, 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create Parallel Delivery release-candidate evidence from accepted integration receipts.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    add_create_args(create)
    fixture = sub.add_parser("fixture")
    fixture.add_argument("--out", required=True)
    fixture.add_argument("--base-commit", required=True)
    fixture.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "fixture":
        payload = build_release_candidate_fixture(Path(args.out), base_commit=resolve_expected_base_commit(args.base_commit) or args.base_commit)
        print(stable_json_dumps(payload) if args.json else payload["run_dir"], end="" if args.json else "\n")
        return 0
    payload, code = run_create_from_args(args)
    print(stable_json_dumps(payload) if args.json else payload.get("status", "failed"), end="" if args.json else "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
