#!/usr/bin/env python3
"""Local Patch Swarm patch bundle collection and safety validation."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cento_build as build_safety  # noqa: E402


SCHEMA_PATCH_BUNDLE = "cento.patch_bundle.v1"
SCHEMA_LEASES = "cento.patch_bundle_leases.v1"
SCHEMA_RECEIPT = "cento.patch_bundle_receipt.v1"
SCHEMA_REPORT = "cento.patch_bundle_collection_report.v1"
VALIDATOR_VERSION = "patch-bundle-validator-v1"
DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z"

REASON_CODES = [
    "missing_required_field",
    "invalid_bundle_schema",
    "run_id_mismatch",
    "base_commit_mismatch",
    "missing_task_lease",
    "unsafe_path_traversal",
    "absolute_path",
    "path_outside_lease",
    "diff_path_not_declared",
    "declared_path_not_in_diff",
    "protected_path_edit",
    "local_secret_path_edit",
    "symlink_patch_prohibited",
    "submodule_patch_prohibited",
    "binary_patch_prohibited",
    "undeclared_delete",
    "unowned_rename",
    "broad_lockfile_change",
    "secret_like_content",
    "unsafe_evidence_path",
    "missing_evidence_file",
    "unsupported_patch_ref",
    "worker_validation_missing",
    "worker_validation_failed",
]

DEFAULT_PROTECTED_PATHS = [
    ".env",
    ".env.*",
    ".env.mcp",
    "**/.env",
    "**/.env.*",
    "*.pem",
    "*.key",
    "*secret*",
    "*token*",
    "*credential*",
]

REMOTE_REF_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
SECRET_LINE_RE = re.compile(
    r"(?i)(api[_-]?key|secret|token|credential|password|private[_-]?key|sk-[a-z0-9_-]{8,})"
)


class BundleValidationError(RuntimeError):
    """Expected patch bundle validation failure."""


class PathValidationError(BundleValidationError):
    """Path validation failure with a stable reason code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PatchBundle:
    schema: str
    bundle_id: str
    task_id: str
    worker_id: str
    run_id: str
    base_commit: str
    touched_paths: list[str]
    diff_path: str | None
    patch_content_ref: dict[str, Any] | str | None
    changed_file_summary: list[dict[str, Any]]
    validation_commands: list[dict[str, Any]]
    evidence_files: list[str]
    result_status: str
    risk_flags: list[str]


@dataclass(frozen=True)
class LeaseSpec:
    task_id: str
    allowed_paths: list[str]
    protected_paths: list[str]
    allowed_deletes: list[str]
    allowed_renames: list[dict[str, str]]
    allowed_lockfiles: list[str]
    allow_binary: bool = False
    allow_symlinks: bool = False
    allow_submodules: bool = False
    max_lockfile_changed_lines: int = 100


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str | None
    detail: str


@dataclass(frozen=True)
class DiffSummary:
    paths: list[str]
    path_errors: list[ValidationIssue]
    delete_paths: list[str]
    renames: list[dict[str, str]]
    binary: bool
    symlink_paths: list[str]
    submodule_paths: list[str]
    lockfile_line_deltas: dict[str, int]
    secret_like_added_paths: list[str]


@dataclass(frozen=True)
class BundleReceipt:
    schema: str
    receipt_id: str
    bundle_id: str
    task_id: str
    worker_id: str
    run_id: str
    base_commit: str
    validation_status: str
    integratable: bool
    reason_codes: list[str]
    issues: list[ValidationIssue]
    normalized_touched_paths: list[str]
    diff_paths: list[str]
    changed_file_summary: list[dict[str, Any]]
    worker_validation_commands: list[dict[str, Any]]
    evidence_files: list[str]
    risk_flags: list[str]
    patch_sha256: str | None
    validator_version: str
    validated_at: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BundleValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BundleValidationError(f"expected JSON object in {path}")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    return cleaned.strip("-") or "unknown"


def _path_code(raw: str) -> str:
    return "absolute_path" if raw.startswith("/") or WINDOWS_DRIVE_RE.match(raw) else "unsafe_path_traversal"


def normalize_repo_relative_path(raw: str) -> str:
    """Return a normalized POSIX repo-relative path or raise a coded error."""

    if not isinstance(raw, str):
        raise PathValidationError("unsafe_path_traversal", "path must be a string")
    if "\x00" in raw:
        raise PathValidationError("unsafe_path_traversal", "NUL byte is not allowed in paths")
    value = raw.strip()
    if not value:
        raise PathValidationError("unsafe_path_traversal", "empty path is not allowed")
    if REMOTE_REF_RE.match(value):
        raise PathValidationError("unsupported_patch_ref", "remote patch or artifact refs are not supported")
    if WINDOWS_DRIVE_RE.match(value):
        raise PathValidationError("absolute_path", "Windows drive paths are not allowed")
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    if value.startswith("/") or Path(value).is_absolute():
        raise PathValidationError("absolute_path", "absolute paths are not allowed")
    while "//" in value:
        value = value.replace("//", "/")
    value = value.rstrip("/") if value != "." else value
    if value in {"", ".", "*", "**", "./"}:
        raise PathValidationError("unsafe_path_traversal", "repo-root or broad cleanup path is not allowed")
    parts = PurePosixPath(value).parts
    if ".." in parts:
        raise PathValidationError("unsafe_path_traversal", "path traversal is not allowed")
    if parts and parts[0] == ".git":
        raise PathValidationError("unsafe_path_traversal", "git metadata paths are not allowed")
    return PurePosixPath(value).as_posix()


def normalize_diff_path(raw: str) -> str | None:
    value = raw.strip()
    if value in {"/dev/null", "dev/null"}:
        return None
    try:
        parts = shlex.split(value)
        if parts:
            value = parts[0]
    except ValueError:
        value = value.split("\t", 1)[0].split(" ", 1)[0]
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return normalize_repo_relative_path(value)


def path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def path_allowed(path: str, patterns: list[str]) -> bool:
    return any(path_matches(path, pattern) for pattern in patterns)


def is_local_secret_path(path: str) -> bool:
    lowered = path.lower()
    name = PurePosixPath(path).name.lower()
    return (
        name == ".env"
        or name.startswith(".env.")
        or name == ".env.mcp"
        or lowered.endswith(".pem")
        or lowered.endswith(".key")
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
    )


def is_protected_path(path: str, protected_patterns: list[str]) -> bool:
    if is_local_secret_path(path):
        return True
    for pattern in protected_patterns:
        try:
            normalized_pattern = normalize_repo_relative_path(pattern)
        except PathValidationError:
            normalized_pattern = pattern.replace("\\", "/")
        if path_matches(path, normalized_pattern):
            return True
        if "/" not in normalized_pattern and fnmatch.fnmatch(PurePosixPath(path).name, normalized_pattern):
            return True
    return False


def normalize_optional_path_list(values: Any) -> tuple[list[str], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    result: list[str] = []
    seen: set[str] = set()
    if values is None:
        return [], []
    if not isinstance(values, list):
        return [], [ValidationIssue("missing_required_field", None, "path list must be an array")]
    for value in values:
        try:
            normalized = normalize_repo_relative_path(str(value))
        except PathValidationError as exc:
            issues.append(ValidationIssue(exc.code, str(value), exc.detail))
            continue
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result), issues


def bundle_from_payload(payload: dict[str, Any]) -> tuple[PatchBundle | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    required = [
        "schema",
        "bundle_id",
        "task_id",
        "worker_id",
        "run_id",
        "base_commit",
        "touched_paths",
        "changed_file_summary",
        "validation_commands",
        "evidence_files",
        "result_status",
        "risk_flags",
    ]
    for field in required:
        if field not in payload:
            issues.append(ValidationIssue("missing_required_field", None, f"{field} is required"))
    if payload.get("schema") != SCHEMA_PATCH_BUNDLE:
        issues.append(ValidationIssue("invalid_bundle_schema", None, f"schema must be {SCHEMA_PATCH_BUNDLE}"))
    for field in ("changed_file_summary", "validation_commands", "evidence_files", "risk_flags", "touched_paths"):
        if field in payload and not isinstance(payload.get(field), list):
            issues.append(ValidationIssue("missing_required_field", None, f"{field} must be an array"))
    if issues:
        return None, issues
    return (
        PatchBundle(
            schema=str(payload["schema"]),
            bundle_id=str(payload["bundle_id"]),
            task_id=str(payload["task_id"]),
            worker_id=str(payload["worker_id"]),
            run_id=str(payload["run_id"]),
            base_commit=str(payload["base_commit"]),
            touched_paths=[str(item) for item in payload.get("touched_paths") or []],
            diff_path=str(payload["diff_path"]) if payload.get("diff_path") else None,
            patch_content_ref=payload.get("patch_content_ref"),
            changed_file_summary=[dict(item) for item in payload.get("changed_file_summary") or [] if isinstance(item, dict)],
            validation_commands=[dict(item) for item in payload.get("validation_commands") or [] if isinstance(item, dict)],
            evidence_files=[str(item) for item in payload.get("evidence_files") or []],
            result_status=str(payload.get("result_status") or ""),
            risk_flags=[str(item) for item in payload.get("risk_flags") or []],
        ),
        [],
    )


def load_lease_manifest(path: Path) -> tuple[str, str, dict[str, LeaseSpec]]:
    payload = read_json(path)
    run_id = str(payload.get("run_id") or "")
    base_commit = str(payload.get("base_commit") or "")
    tasks = payload.get("tasks")
    if not isinstance(tasks, dict):
        raise BundleValidationError("lease manifest tasks must be an object")
    leases: dict[str, LeaseSpec] = {}
    for task_id, spec in tasks.items():
        if not isinstance(spec, dict):
            continue
        allowed, _ = normalize_optional_path_list(spec.get("allowed_paths") or [])
        protected, _ = normalize_optional_path_list(spec.get("protected_paths") or DEFAULT_PROTECTED_PATHS)
        deletes, _ = normalize_optional_path_list(spec.get("allowed_deletes") or [])
        lockfiles, _ = normalize_optional_path_list(spec.get("allowed_lockfiles") or [])
        renames = []
        for item in spec.get("allowed_renames") or []:
            if not isinstance(item, dict):
                continue
            try:
                renames.append(
                    {
                        "from": normalize_repo_relative_path(str(item.get("from") or "")),
                        "to": normalize_repo_relative_path(str(item.get("to") or "")),
                    }
                )
            except PathValidationError:
                continue
        leases[str(task_id)] = LeaseSpec(
            task_id=str(task_id),
            allowed_paths=allowed,
            protected_paths=protected or DEFAULT_PROTECTED_PATHS,
            allowed_deletes=deletes,
            allowed_renames=renames,
            allowed_lockfiles=lockfiles,
            allow_binary=bool(spec.get("allow_binary", False)),
            allow_symlinks=bool(spec.get("allow_symlinks", False)),
            allow_submodules=bool(spec.get("allow_submodules", False)),
            max_lockfile_changed_lines=int(spec.get("max_lockfile_changed_lines") or 100),
        )
    return run_id, base_commit, leases


def _resolve_local_ref(raw: str, bundle_dir: Path, run_root: Path) -> Path:
    if REMOTE_REF_RE.match(raw.strip()):
        raise PathValidationError("unsupported_patch_ref", "remote refs are not supported")
    normalized = normalize_repo_relative_path(raw)
    root_candidate = run_root / normalized
    bundle_candidate = bundle_dir / normalized
    if root_candidate.exists():
        return root_candidate
    return bundle_candidate


def load_patch_text(bundle: PatchBundle, bundle_dir: Path, run_root: Path) -> tuple[str | None, str | None, list[ValidationIssue]]:
    if bundle.result_status == "evidence_only":
        return None, None, []
    ref: str | None = bundle.diff_path
    if bundle.patch_content_ref:
        if isinstance(bundle.patch_content_ref, str):
            ref = bundle.patch_content_ref
        elif isinstance(bundle.patch_content_ref, dict):
            ref = str(bundle.patch_content_ref.get("path") or bundle.patch_content_ref.get("file") or "")
        else:
            return None, None, [ValidationIssue("unsupported_patch_ref", None, "patch_content_ref must be a local path")]
    if not ref:
        return None, None, [ValidationIssue("missing_required_field", None, "diff_path or local patch_content_ref is required")]
    try:
        patch_path = _resolve_local_ref(ref, bundle_dir, run_root)
    except PathValidationError as exc:
        return None, None, [ValidationIssue(exc.code, ref, exc.detail)]
    if not patch_path.exists():
        return None, None, [ValidationIssue("unsupported_patch_ref", ref, "local patch ref does not exist")]
    text = patch_path.read_text(encoding="utf-8", errors="replace")
    return text, sha256_text(text), []


def parse_git_diff(patch_text: str) -> DiffSummary:
    paths: set[str] = set()
    path_errors: list[ValidationIssue] = []
    delete_paths: set[str] = set()
    symlink_paths: set[str] = set()
    submodule_paths: set[str] = set()
    renames: list[dict[str, str]] = []
    lockfile_line_deltas: Counter[str] = Counter()
    secret_like_added_paths: set[str] = set()
    current_paths: set[str] = set()
    rename_from: str | None = None
    binary = False

    def add_path(raw: str) -> str | None:
        try:
            parsed = normalize_diff_path(raw)
        except PathValidationError as exc:
            path_errors.append(ValidationIssue(exc.code, raw, exc.detail))
            return None
        if parsed:
            paths.add(parsed)
            current_paths.add(parsed)
        return parsed

    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            current_paths = set()
            rename_from = None
            tail = line[len("diff --git ") :]
            try:
                parts = shlex.split(tail)
            except ValueError:
                parts = tail.split()
            for raw in parts[:2]:
                add_path(raw)
            continue
        if line.startswith("Binary files") or line.startswith("GIT binary patch"):
            binary = True
            continue
        if line.startswith("rename from "):
            rename_from = add_path(line[len("rename from ") :])
            continue
        if line.startswith("rename to "):
            rename_to = add_path(line[len("rename to ") :])
            if rename_from and rename_to:
                renames.append({"from": rename_from, "to": rename_to})
            continue
        if line.startswith("deleted file mode "):
            delete_paths.update(current_paths)
            continue
        if line.startswith(("old mode 120000", "new mode 120000", "new file mode 120000", "deleted file mode 120000")):
            symlink_paths.update(current_paths)
            continue
        if line.startswith(("old mode 160000", "new mode 160000", "new file mode 160000", "deleted file mode 160000", "Subproject commit ")):
            submodule_paths.update(current_paths)
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            before = set(current_paths)
            parsed = add_path(line[4:])
            if parsed is None and line.startswith("+++ "):
                delete_paths.update(before)
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            for path in current_paths:
                lockfile_line_deltas[path] += 1
            if SECRET_LINE_RE.search(line[1:]):
                secret_like_added_paths.update(current_paths or {"<unknown>"})
            continue
        if line.startswith("-") and not line.startswith("--- "):
            for path in current_paths:
                lockfile_line_deltas[path] += 1

    return DiffSummary(
        paths=sorted(paths),
        path_errors=path_errors,
        delete_paths=sorted(delete_paths),
        renames=renames,
        binary=binary,
        symlink_paths=sorted(symlink_paths),
        submodule_paths=sorted(submodule_paths),
        lockfile_line_deltas=dict(sorted(lockfile_line_deltas.items())),
        secret_like_added_paths=sorted(secret_like_added_paths),
    )


def _issue(code: str, path: str | None, detail: str) -> ValidationIssue:
    return ValidationIssue(code, path, detail)


def _append_path_safety_issues(paths: list[str], lease: LeaseSpec, issues: list[ValidationIssue]) -> None:
    for path in paths:
        if is_protected_path(path, lease.protected_paths):
            issues.append(_issue("protected_path_edit", path, "Protected path cannot be edited by patch bundle."))
        if is_local_secret_path(path):
            issues.append(_issue("local_secret_path_edit", path, "Local secret-looking path cannot be edited by patch bundle."))
        if not path_allowed(path, lease.allowed_paths):
            issues.append(_issue("path_outside_lease", path, "Path is outside the authoritative task lease."))


def _append_worker_validation_issues(bundle: PatchBundle, issues: list[ValidationIssue]) -> None:
    if bundle.result_status != "patch_ready":
        return
    if not bundle.validation_commands:
        issues.append(_issue("worker_validation_missing", None, "Patch bundle must include worker validation command evidence."))
        return
    for command in bundle.validation_commands:
        if "exit_code" not in command:
            issues.append(_issue("worker_validation_missing", None, "Worker validation command is missing exit_code."))
        elif int(command.get("exit_code") or 0) != 0:
            issues.append(_issue("worker_validation_failed", None, "Worker validation command exited non-zero."))


def validate_evidence_files(bundle: PatchBundle, run_root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for raw in bundle.evidence_files:
        try:
            normalized = normalize_repo_relative_path(raw)
        except PathValidationError as exc:
            issues.append(_issue("unsafe_evidence_path", raw, exc.detail))
            continue
        if is_local_secret_path(normalized):
            issues.append(_issue("unsafe_evidence_path", normalized, "Evidence refs cannot point to local secret-looking paths."))
            continue
        if not (run_root / normalized).exists():
            issues.append(_issue("missing_evidence_file", normalized, "Evidence file reference does not exist under the run root."))
    return issues


def _receipt_from_issues(
    bundle: PatchBundle | None,
    issues: list[ValidationIssue],
    *,
    bundle_id: str,
    task_id: str,
    worker_id: str,
    run_id: str,
    base_commit: str,
    touched_paths: list[str] | None = None,
    diff_paths: list[str] | None = None,
    evidence_files: list[str] | None = None,
    patch_sha256: str | None = None,
    timestamp: str | None = None,
) -> BundleReceipt:
    reason_codes = []
    seen: set[str] = set()
    for issue in issues:
        if issue.code not in seen:
            seen.add(issue.code)
            reason_codes.append(issue.code)
    accepted = not reason_codes
    return BundleReceipt(
        schema=SCHEMA_RECEIPT,
        receipt_id=f"receipt-{safe_id(bundle_id)}",
        bundle_id=bundle_id,
        task_id=task_id,
        worker_id=worker_id,
        run_id=run_id,
        base_commit=base_commit,
        validation_status="accepted" if accepted else "rejected",
        integratable=accepted and (bundle.result_status == "patch_ready" if bundle else False),
        reason_codes=reason_codes,
        issues=issues,
        normalized_touched_paths=touched_paths or [],
        diff_paths=diff_paths or [],
        changed_file_summary=bundle.changed_file_summary if bundle else [],
        worker_validation_commands=bundle.validation_commands if bundle else [],
        evidence_files=evidence_files or [],
        risk_flags=bundle.risk_flags if bundle else [],
        patch_sha256=patch_sha256,
        validator_version=VALIDATOR_VERSION,
        validated_at=timestamp or DEFAULT_TIMESTAMP,
    )


def validate_bundle(
    bundle: PatchBundle,
    lease: LeaseSpec,
    *,
    expected_run_id: str | None,
    expected_base_commit: str | None,
    bundle_dir: Path,
    run_root: Path,
    timestamp: str | None = None,
) -> BundleReceipt:
    issues: list[ValidationIssue] = []
    touched_paths, touched_issues = normalize_optional_path_list(bundle.touched_paths)
    issues.extend(touched_issues)
    evidence_files, evidence_path_issues = normalize_optional_path_list(bundle.evidence_files)
    issues.extend([_issue("unsafe_evidence_path", issue.path, issue.detail) for issue in evidence_path_issues])
    if expected_run_id and bundle.run_id != expected_run_id:
        issues.append(_issue("run_id_mismatch", None, f"bundle run_id {bundle.run_id} does not match {expected_run_id}"))
    if expected_base_commit and bundle.base_commit != expected_base_commit:
        issues.append(
            _issue("base_commit_mismatch", None, f"bundle base_commit {bundle.base_commit} does not match expected base")
        )
    _append_path_safety_issues(touched_paths, lease, issues)
    issues.extend(validate_evidence_files(bundle, run_root))
    _append_worker_validation_issues(bundle, issues)

    patch_text, patch_sha, load_issues = load_patch_text(bundle, bundle_dir, run_root)
    issues.extend(load_issues)
    diff_paths: list[str] = []
    if patch_text is not None:
        summary = parse_git_diff(patch_text)
        issues.extend(summary.path_errors)
        diff_paths = summary.paths
        _append_path_safety_issues(diff_paths, lease, issues)
        declared = set(touched_paths)
        actual = set(diff_paths)
        for path in sorted(actual - declared):
            issues.append(_issue("diff_path_not_declared", path, "Patch changes a path not declared in touched_paths."))
        for path in sorted(declared - actual):
            issues.append(_issue("declared_path_not_in_diff", path, "Declared touched_path is not present in the diff."))
        if summary.binary and not lease.allow_binary:
            issues.append(_issue("binary_patch_prohibited", None, "Binary patch markers are prohibited by the task lease."))
        for path in summary.symlink_paths:
            if not lease.allow_symlinks:
                issues.append(_issue("symlink_patch_prohibited", path, "Symlink patch modes are prohibited by the task lease."))
        for path in summary.submodule_paths:
            if not lease.allow_submodules:
                issues.append(_issue("submodule_patch_prohibited", path, "Submodule patch modes are prohibited by the task lease."))
        for path in summary.delete_paths:
            if path not in lease.allowed_deletes:
                issues.append(_issue("undeclared_delete", path, "Deletes must be explicitly allowed by the task lease."))
        for rename in summary.renames:
            source = rename.get("from", "")
            destination = rename.get("to", "")
            allowed_pair = any(item.get("from") == source and item.get("to") == destination for item in lease.allowed_renames)
            if not allowed_pair or not path_allowed(source, lease.allowed_paths) or not path_allowed(destination, lease.allowed_paths):
                issues.append(_issue("unowned_rename", f"{source}->{destination}", "Rename source and destination must be lease-owned and declared."))
        for path, delta in summary.lockfile_line_deltas.items():
            if build_safety.path_is_lockfile(path) and (path not in lease.allowed_lockfiles or delta > lease.max_lockfile_changed_lines):
                issues.append(_issue("broad_lockfile_change", path, "Lockfile changes must be explicitly leased and below the line budget."))
        for path in summary.secret_like_added_paths:
            issues.append(_issue("secret_like_content", path, "Patch adds secret-looking content; value redacted."))

    return _receipt_from_issues(
        bundle,
        issues,
        bundle_id=bundle.bundle_id,
        task_id=bundle.task_id,
        worker_id=bundle.worker_id,
        run_id=bundle.run_id,
        base_commit=bundle.base_commit,
        touched_paths=touched_paths,
        diff_paths=diff_paths,
        evidence_files=evidence_files,
        patch_sha256=patch_sha,
        timestamp=timestamp,
    )


def receipt_to_dict(receipt: BundleReceipt) -> dict[str, Any]:
    payload = asdict(receipt)
    payload["issues"] = [asdict(issue) for issue in receipt.issues]
    return payload


def validate_bundle_manifest(
    bundle_path: Path,
    lease_manifest: Path,
    out_dir: Path,
    *,
    expected_run_id: str | None = None,
    expected_base_commit: str | None = None,
    timestamp: str | None = None,
) -> BundleReceipt:
    lease_run_id, lease_base_commit, leases = load_lease_manifest(lease_manifest)
    payload = read_json(bundle_path)
    bundle, parse_issues = bundle_from_payload(payload)
    run_id = str(payload.get("run_id") or expected_run_id or lease_run_id or "")
    task_id = str(payload.get("task_id") or "")
    worker_id = str(payload.get("worker_id") or "")
    bundle_id = str(payload.get("bundle_id") or bundle_path.stem)
    base_commit = str(payload.get("base_commit") or expected_base_commit or lease_base_commit or "")
    if bundle is None:
        receipt = _receipt_from_issues(
            None,
            parse_issues,
            bundle_id=bundle_id,
            task_id=task_id,
            worker_id=worker_id,
            run_id=run_id,
            base_commit=base_commit,
            timestamp=timestamp,
        )
    else:
        lease = leases.get(bundle.task_id)
        if lease is None:
            receipt = _receipt_from_issues(
                bundle,
                [_issue("missing_task_lease", bundle.task_id, "No authoritative task lease was found.")],
                bundle_id=bundle.bundle_id,
                task_id=bundle.task_id,
                worker_id=bundle.worker_id,
                run_id=bundle.run_id,
                base_commit=bundle.base_commit,
                touched_paths=[],
                diff_paths=[],
                evidence_files=[],
                timestamp=timestamp,
            )
        else:
            receipt = validate_bundle(
                bundle,
                lease,
                expected_run_id=expected_run_id or lease_run_id,
                expected_base_commit=expected_base_commit or lease_base_commit,
                bundle_dir=bundle_path.parent,
                run_root=out_dir,
                timestamp=timestamp,
            )
    receipts_dir = out_dir / "receipts"
    write_json(receipts_dir / f"{receipt.receipt_id}.json", receipt_to_dict(receipt))
    return receipt


def write_markdown_report(out_dir: Path, report: dict[str, Any], receipts: list[BundleReceipt]) -> Path:
    lines = [
        "# Patch Bundle Collection Report",
        "",
        f"- Run ID: `{report.get('run_id')}`",
        f"- Base commit: `{report.get('base_commit')}`",
        f"- Accepted: {report.get('accepted_count')}",
        f"- Rejected: {report.get('rejected_count')}",
        f"- Evidence-only accepted: {report.get('evidence_only_count')}",
        "",
        "## Rejection Reasons",
        "",
    ]
    reasons = report.get("rejection_reason_counts") or {}
    if reasons:
        for code, count in sorted(reasons.items()):
            lines.append(f"- `{code}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Receipts", ""])
    for receipt in sorted(receipts, key=lambda item: item.bundle_id):
        codes = ", ".join(receipt.reason_codes) if receipt.reason_codes else "accepted"
        lines.append(f"- `{receipt.bundle_id}` `{receipt.validation_status}`: {codes}")
    path = out_dir / "patch-bundle-report.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def collect_patch_bundles(
    bundles_dir: Path,
    lease_manifest: Path,
    out_dir: Path,
    *,
    run_id: str,
    base_commit: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[BundleReceipt] = []
    for bundle_path in sorted(bundles_dir.glob("*.json")):
        receipt = validate_bundle_manifest(
            bundle_path,
            lease_manifest,
            out_dir,
            expected_run_id=run_id,
            expected_base_commit=base_commit,
            timestamp=timestamp,
        )
        receipts.append(receipt)
    reason_counts: Counter[str] = Counter()
    for receipt in receipts:
        for code in receipt.reason_codes:
            reason_counts[code] += 1
    accepted = [receipt for receipt in receipts if receipt.validation_status == "accepted"]
    rejected = [receipt for receipt in receipts if receipt.validation_status == "rejected"]
    evidence_only = [
        receipt
        for receipt in accepted
        if receipt.integratable is False and not receipt.diff_paths and receipt.patch_sha256 is None
    ]
    report = {
        "schema": SCHEMA_REPORT,
        "run_id": run_id,
        "base_commit": base_commit or "",
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "evidence_only_count": len(evidence_only),
        "receipt_count": len(receipts),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "receipts": [f"receipts/{receipt.receipt_id}.json" for receipt in sorted(receipts, key=lambda item: item.bundle_id)],
        "validator_version": VALIDATOR_VERSION,
    }
    write_json(out_dir / "patch-bundle-report.json", report)
    write_markdown_report(out_dir, report, receipts)
    (out_dir / "validation-summary.txt").write_text(
        f"accepted={len(accepted)} rejected={len(rejected)} evidence_only={len(evidence_only)}\n",
        encoding="utf-8",
    )
    return report


def _unified_diff(path: str, before: str, after: str) -> str:
    before_lines = before.splitlines(True)
    after_lines = after.splitlines(True)
    header = f"diff --git a/{path} b/{path}\n"
    body = "".join(
        __import__("difflib").unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    return header + body.replace("\n--- ", "--- ", 1) if body.startswith("--- ") else header + body


def fixture_patch(path: str, added: str = "print('fixture')\n") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1,2 @@\n"
        "-old line\n"
        f"+old line\n+{added}"
    )


def write_bundle(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def base_bundle(
    *,
    bundle_id: str,
    task_id: str,
    worker_id: str,
    run_id: str,
    base_commit: str,
    touched_paths: list[str],
    diff_path: str | None,
    result_status: str = "patch_ready",
    evidence_files: list[str] | None = None,
    validation_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA_PATCH_BUNDLE,
        "bundle_id": bundle_id,
        "task_id": task_id,
        "worker_id": worker_id,
        "run_id": run_id,
        "base_commit": base_commit,
        "touched_paths": touched_paths,
        "diff_path": diff_path,
        "patch_content_ref": None,
        "changed_file_summary": [
            {"path": path, "change_type": "modify", "summary": "Fixture patch bundle change."}
            for path in touched_paths
            if not path.startswith("/") and ".." not in path.split("/")
        ],
        "validation_commands": validation_commands if validation_commands is not None else [{"cmd": "python3 -m pytest -q tests/fixture.py", "exit_code": 0}],
        "evidence_files": evidence_files or ["input/evidence/worker-a-validation.txt"],
        "result_status": result_status,
        "risk_flags": [],
    }


def build_fixture_inputs(out_dir: Path, *, base_commit: str, run_id: str = "patch-bundle-fixture") -> dict[str, Any]:
    input_dir = out_dir / "input"
    bundles_dir = input_dir / "bundles"
    patches_dir = input_dir / "patches"
    evidence_dir = input_dir / "evidence"
    for path in (bundles_dir, patches_dir, evidence_dir):
        path.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "worker-a-validation.txt").write_text("fixture validation passed\n", encoding="utf-8")
    (evidence_dir / "research-note.md").write_text("Evidence-only fixture result.\n", encoding="utf-8")
    leases = {
        "schema": SCHEMA_LEASES,
        "run_id": run_id,
        "base_commit": base_commit,
        "tasks": {
            "task-owned-src": {
                "allowed_paths": ["src/owned/**", "tests/owned/**"],
                "protected_paths": DEFAULT_PROTECTED_PATHS,
                "allowed_deletes": [],
                "allowed_renames": [],
                "allowed_lockfiles": [],
                "allow_binary": False,
                "allow_symlinks": False,
                "allow_submodules": False,
                "max_lockfile_changed_lines": 100,
            },
            "task-research-only": {
                "allowed_paths": [],
                "protected_paths": DEFAULT_PROTECTED_PATHS,
                "allowed_deletes": [],
                "allowed_renames": [],
                "allowed_lockfiles": [],
                "allow_binary": False,
                "allow_symlinks": False,
                "allow_submodules": False,
                "max_lockfile_changed_lines": 100,
            },
            "task-lockfile": {
                "allowed_paths": ["package-lock.json"],
                "protected_paths": DEFAULT_PROTECTED_PATHS,
                "allowed_deletes": [],
                "allowed_renames": [],
                "allowed_lockfiles": ["package-lock.json"],
                "allow_binary": False,
                "allow_symlinks": False,
                "allow_submodules": False,
                "max_lockfile_changed_lines": 2,
            },
        },
    }
    write_json(input_dir / "leases.json", leases)
    patches: dict[str, str] = {
        "bundle-safe-001.diff": fixture_patch("src/owned/example.py", "def fixture_helper():\n    return 'ok'\n"),
        "bundle-outside-lease.diff": fixture_patch("src/unowned/outside.py"),
        "bundle-protected-path.diff": fixture_patch(".env"),
        "bundle-env-mcp.diff": fixture_patch(".env.mcp"),
        "bundle-traversal.diff": "diff --git a/../outside.txt b/../outside.txt\n--- a/../outside.txt\n+++ b/../outside.txt\n@@ -1 +1 @@\n-old\n+new\n",
        "bundle-symlink.diff": "diff --git a/src/owned/link b/src/owned/link\nnew file mode 120000\n--- /dev/null\n+++ b/src/owned/link\n@@ -0,0 +1 @@\n+target\n",
        "bundle-submodule.diff": "diff --git a/src/owned/submodule b/src/owned/submodule\nnew file mode 160000\n--- /dev/null\n+++ b/src/owned/submodule\n@@ -0,0 +1 @@\n+Subproject commit 0123456789abcdef0123456789abcdef01234567\n",
        "bundle-binary.diff": "diff --git a/src/owned/image.png b/src/owned/image.png\nBinary files /dev/null and b/src/owned/image.png differ\nGIT binary patch\nliteral 0\n",
        "bundle-undeclared-delete.diff": "diff --git a/src/owned/delete_me.py b/src/owned/delete_me.py\ndeleted file mode 100644\n--- a/src/owned/delete_me.py\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n",
        "bundle-unowned-rename.diff": "diff --git a/src/unowned/old.py b/src/owned/new.py\nsimilarity index 100%\nrename from src/unowned/old.py\nrename to src/owned/new.py\n",
        "bundle-broad-lockfile.diff": "diff --git a/package-lock.json b/package-lock.json\n--- a/package-lock.json\n+++ b/package-lock.json\n@@ -1 +1,5 @@\n-{}\n+{\n+  \"a\": 1,\n+  \"b\": 2,\n+  \"c\": 3\n+}\n",
        "bundle-secret-content.diff": fixture_patch("src/owned/secret_value.py", "FAKE_OPENAI_API_KEY='sk-fake-call9-not-a-real-secret'\n"),
    }
    for name, text in patches.items():
        (patches_dir / name).write_text(text, encoding="utf-8")
    bundle_specs = [
        ("bundle-safe-001", "task-owned-src", ["src/owned/example.py"], "input/patches/bundle-safe-001.diff"),
        ("bundle-outside-lease", "task-owned-src", ["src/unowned/outside.py"], "input/patches/bundle-outside-lease.diff"),
        ("bundle-protected-path", "task-owned-src", [".env"], "input/patches/bundle-protected-path.diff"),
        ("bundle-env-mcp", "task-owned-src", [".env.mcp"], "input/patches/bundle-env-mcp.diff"),
        ("bundle-traversal", "task-owned-src", ["../outside.txt"], "input/patches/bundle-traversal.diff"),
        ("bundle-absolute-path", "task-owned-src", ["/tmp/outside.txt"], "input/patches/bundle-safe-001.diff"),
        ("bundle-symlink", "task-owned-src", ["src/owned/link"], "input/patches/bundle-symlink.diff"),
        ("bundle-submodule", "task-owned-src", ["src/owned/submodule"], "input/patches/bundle-submodule.diff"),
        ("bundle-binary", "task-owned-src", ["src/owned/image.png"], "input/patches/bundle-binary.diff"),
        ("bundle-undeclared-delete", "task-owned-src", ["src/owned/delete_me.py"], "input/patches/bundle-undeclared-delete.diff"),
        ("bundle-unowned-rename", "task-owned-src", ["src/unowned/old.py", "src/owned/new.py"], "input/patches/bundle-unowned-rename.diff"),
        ("bundle-broad-lockfile", "task-lockfile", ["package-lock.json"], "input/patches/bundle-broad-lockfile.diff"),
        ("bundle-secret-content", "task-owned-src", ["src/owned/secret_value.py"], "input/patches/bundle-secret-content.diff"),
    ]
    for bundle_id, task_id, touched, diff_path in bundle_specs:
        write_bundle(
            bundles_dir / f"{bundle_id}.json",
            base_bundle(
                bundle_id=bundle_id,
                task_id=task_id,
                worker_id=f"worker-{bundle_id}",
                run_id=run_id,
                base_commit=base_commit,
                touched_paths=touched,
                diff_path=diff_path,
            ),
        )
    write_bundle(
        bundles_dir / "bundle-evidence-001.json",
        base_bundle(
            bundle_id="bundle-evidence-001",
            task_id="task-research-only",
            worker_id="worker-evidence",
            run_id=run_id,
            base_commit=base_commit,
            touched_paths=[],
            diff_path=None,
            result_status="evidence_only",
            evidence_files=["input/evidence/research-note.md"],
            validation_commands=[],
        ),
    )
    return {"run_id": run_id, "input_dir": input_dir.as_posix(), "bundle_count": 14}


def run_validate_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    out_dir = Path(args.out)
    receipt = validate_bundle_manifest(
        Path(args.bundle),
        Path(args.lease_manifest),
        out_dir,
        expected_run_id=getattr(args, "run_id", "") or None,
        expected_base_commit=getattr(args, "base_commit", "") or None,
    )
    payload = receipt_to_dict(receipt)
    return payload, 0 if receipt.validation_status == "accepted" else 1


def run_collect_from_args(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    report = collect_patch_bundles(
        Path(args.bundles_dir),
        Path(args.lease_manifest),
        Path(args.out),
        run_id=args.run_id,
        base_commit=getattr(args, "base_commit", "") or None,
    )
    return report, 0


def add_patch_bundle_args(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="patch_bundle_command", required=True)
    validate = sub.add_parser("validate", help="Validate one local Patch Swarm bundle without applying it.")
    validate.add_argument("--bundle", required=True)
    validate.add_argument("--lease-manifest", required=True)
    validate.add_argument("--out", required=True)
    validate.add_argument("--run-id", default="")
    validate.add_argument("--base-commit", default="")
    validate.add_argument("--json", action="store_true")
    collect = sub.add_parser("collect", help="Collect and validate all local Patch Swarm bundles from a directory.")
    collect.add_argument("--bundles-dir", required=True)
    collect.add_argument("--lease-manifest", required=True)
    collect.add_argument("--out", required=True)
    collect.add_argument("--run-id", required=True)
    collect.add_argument("--base-commit", default="")
    collect.add_argument("--json", action="store_true")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and validate local Patch Swarm patch bundles.")
    add_patch_bundle_args(parser)
    args = parser.parse_args(argv)
    if args.patch_bundle_command == "validate":
        payload, code = run_validate_from_args(args)
    else:
        payload, code = run_collect_from_args(args)
    print(stable_json_dumps(payload), end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
