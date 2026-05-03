#!/usr/bin/env python3
"""Manifest-driven local build packages for Cento."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODES_PATH = ROOT / ".cento" / "modes.yaml"
RUNTIMES_PATH = ROOT / ".cento" / "runtimes.yaml"
BUILD_ROOT = ROOT / ".cento" / "builds"
DEFAULT_WORKER_TIMEOUT = 180
SAFE_WORKER_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TZ",
    "TMPDIR",
)

SCHEMA_BUILD = "cento.build.v1"
SCHEMA_PATCH_BUNDLE = "cento.patch_bundle.v1"
SCHEMA_WORKER_ARTIFACT = "cento.worker_artifact.v1"
SCHEMA_INTEGRATION_RECEIPT = "cento.integration_receipt.v1"
SCHEMA_VALIDATION_RECEIPT = "cento.validation_receipt.v1"
SCHEMA_APPLY_RECEIPT = "cento.apply_receipt.v1"
SCHEMA_TASKSTREAM_EVIDENCE = "cento.taskstream_evidence.v1"

DEFAULT_PROTECTED_PATHS = [
    ".env",
    ".env.*",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
]

LOCKFILE_PATTERNS = [
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "npm-shrinkwrap.json",
    "Cargo.lock",
    "Gemfile.lock",
    "Pipfile.lock",
    "poetry.lock",
    "uv.lock",
    "go.sum",
]

DEFAULT_MODES: dict[str, dict[str, Any]] = {
    "fast": {
        "time_budget_minutes": 5,
        "validation_tier": "smoke",
        "ask_policy": "blockers_only",
        "commit_policy": "none",
        "push_policy": "none",
        "max_workers": 0,
        "max_files_changed": 3,
        "repair_attempts": 0,
        "risk_acceptance": "medium",
    },
    "standard": {
        "time_budget_minutes": 15,
        "validation_tier": "focused",
        "ask_policy": "one_batch_if_material",
        "commit_policy": "local_commit",
        "push_policy": "optional",
        "max_workers": 2,
        "max_files_changed": 8,
        "repair_attempts": 1,
        "risk_acceptance": "low_medium",
    },
    "thorough": {
        "time_budget_minutes": 30,
        "validation_tier": "product",
        "ask_policy": "requirements_or_options_first",
        "commit_policy": "local_commit",
        "push_policy": "branch",
        "max_workers": 4,
        "max_files_changed": None,
        "repair_attempts": 3,
        "risk_acceptance": "low",
    },
}


class BuildError(RuntimeError):
    """Expected command failure."""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BuildError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BuildError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BuildError(f"expected JSON object in {path}")
    return payload


def append_event(build_dir: Path, event_type: str, payload: dict[str, Any] | None = None) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    row = {"ts": now_iso(), "event": event_type}
    if payload:
        row.update(payload)
    with (build_dir / "events.ndjson").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def run(command: list[str], *, cwd: Path = ROOT, input_text: str | None = None, timeout: int = 120) -> dict[str, Any]:
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
        "exit_code": proc.returncode,
        "status": "passed" if proc.returncode == 0 else "failed",
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def git_value(args: list[str], fallback: str = "") -> str:
    result = run(["git", *args], timeout=30)
    if result["exit_code"] != 0:
        return fallback
    return str(result["stdout"]).strip()


def load_modes() -> dict[str, dict[str, Any]]:
    if not MODES_PATH.exists():
        return DEFAULT_MODES
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(MODES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return DEFAULT_MODES
    modes = data.get("modes") if isinstance(data, dict) else None
    if not isinstance(modes, dict):
        return DEFAULT_MODES
    merged = dict(DEFAULT_MODES)
    for name, mode in modes.items():
        if isinstance(name, str) and isinstance(mode, dict):
            merged[name] = {**merged.get(name, {}), **mode}
    return merged


def load_runtime_profiles() -> dict[str, dict[str, Any]]:
    if not RUNTIMES_PATH.exists():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(RUNTIMES_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise BuildError(f"failed to load runtime profiles from {rel(RUNTIMES_PATH)}: {exc}") from exc
    runtimes = data.get("runtimes") if isinstance(data, dict) else None
    if not isinstance(runtimes, dict):
        raise BuildError(f"{rel(RUNTIMES_PATH)} must contain a runtimes mapping")
    profiles: dict[str, dict[str, Any]] = {}
    for name, profile in runtimes.items():
        if isinstance(name, str) and isinstance(profile, dict):
            profiles[name] = dict(profile)
    return profiles


def _positive_int(value: Any, field: str, errors: list[str]) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        errors.append(f"{field} must be a positive integer")
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be a positive integer")
        return None
    if parsed <= 0:
        errors.append(f"{field} must be a positive integer")
        return None
    return parsed


def validate_runtime_profile(name: str, profile: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(profile, dict):
        return {"status": "failed", "errors": [f"runtime profile {name} must be an object"], "warnings": []}

    runtime_type = str(profile.get("type") or "")
    if runtime_type not in {"fixture", "command"}:
        errors.append("type must be fixture or command")

    timeout = _positive_int(profile.get("timeout_seconds"), "timeout_seconds", errors)
    if timeout is None:
        warnings.append(f"timeout_seconds missing; defaulting to {DEFAULT_WORKER_TIMEOUT}")

    for field in ("max_changed_files", "max_patch_lines"):
        if field in profile and profile.get(field) is not None:
            _positive_int(profile.get(field), field, errors)

    if runtime_type == "fixture":
        fixture_case = str(profile.get("fixture_case") or "valid")
        if fixture_case not in {"valid", "unowned", "protected", "delete", "lockfile", "binary"}:
            errors.append("fixture_case must be one of valid, unowned, protected, delete, lockfile, binary")

    if runtime_type == "command":
        argv = profile.get("argv")
        if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
            errors.append("command runtime profiles require a non-empty argv list")
        if "command" in profile:
            errors.append("command runtime profiles must use argv arrays, not raw shell strings")
        cwd = profile.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            errors.append("cwd must be a string when provided")
        env_allowlist = profile.get("env_allowlist")
        if env_allowlist is not None and (
            not isinstance(env_allowlist, list) or not all(isinstance(item, str) and item for item in env_allowlist)
        ):
            errors.append("env_allowlist must be a list of environment variable names")
        if bool(profile.get("allow_network")):
            warnings.append("allow_network is advisory only for local command profiles")

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
    }


def runtime_profile(name: str) -> dict[str, Any]:
    profiles = load_runtime_profiles()
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "<none>"
        raise BuildError(f"runtime profile not found: {name}; available profiles: {available}")
    profile = profiles[name]
    result = validate_runtime_profile(name, profile)
    if result["status"] != "passed":
        raise BuildError(f"runtime profile {name} is invalid: " + "; ".join([str(item) for item in result["errors"]]))
    return profile


def runtime_timeout(profile: dict[str, Any] | None, timeout: int | None) -> int:
    if timeout is not None:
        return int(timeout)
    if profile is not None and profile.get("timeout_seconds") is not None:
        return int(profile["timeout_seconds"])
    return DEFAULT_WORKER_TIMEOUT


def runtime_limit(profile: dict[str, Any] | None, field: str) -> int | None:
    if profile is None or profile.get(field) is None:
        return None
    return int(profile[field])


def runtime_context(
    *,
    manifest_path: Path,
    build_dir: Path,
    worker_dir: Path,
    worktree: Path,
    worker_id: str,
) -> dict[str, str]:
    return {
        "manifest": str(manifest_path),
        "prompt": str(build_dir / "builder.prompt.md"),
        "build_dir": str(build_dir),
        "worker_dir": str(worker_dir),
        "worktree": str(worktree),
        "worker": worker_id,
        "artifact_dir": str(worker_dir),
    }


def format_runtime_value(value: Any, context: dict[str, str]) -> str:
    text = str(value)
    for key, replacement in context.items():
        text = text.replace("{" + key + "}", replacement)
    return text


def build_worker_env(
    manifest: dict[str, Any],
    manifest_path: Path,
    worker_id: str,
    build_dir: Path,
    worker_dir: Path,
    worktree: Path,
    env_allowlist: list[str] | None = None,
) -> dict[str, str]:
    names = list(env_allowlist) if env_allowlist is not None else list(SAFE_WORKER_ENV_ALLOWLIST)
    env = {key: os.environ[key] for key in names if key in os.environ}
    env.update(
        {
            "CENTO_BUILD_ID": str(manifest.get("id") or ""),
            "CENTO_MANIFEST": str(manifest_path),
            "CENTO_WORKER_ID": worker_id,
            "CENTO_ALLOWED_WRITE_PATHS": json.dumps(worker_write_paths(manifest, worker_id)),
            "CENTO_MODE": str(manifest.get("mode") or ""),
            "CENTO_WORKER_ARTIFACT_DIR": str(worker_dir),
            "CENTO_BUILD_DIR": str(build_dir),
            "CENTO_WORKTREE": str(worktree),
            "CENTO_PROMPT": str(build_dir / "builder.prompt.md"),
        }
    )
    return env


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:52] or "task"


def normalize_path(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise BuildError("empty path is not allowed")
    path = Path(raw).expanduser()
    if path.is_absolute():
        try:
            raw = path.resolve().relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise BuildError(f"path must be inside repo: {value}") from exc
    raw = raw.replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    normalized = raw.rstrip("/") if raw != "." else raw
    if normalized in {"", "."}:
        raise BuildError("empty path is not allowed")
    parts = PurePosixPath(normalized).parts
    if ".." in parts:
        raise BuildError(f"path traversal is not allowed: {value}")
    if parts and parts[0] == ".git":
        raise BuildError(f"git metadata path is not allowed: {value}")
    return normalized


def normalize_patch_path(value: str) -> str:
    raw = value.strip().replace("\\", "/")
    if raw in {"/dev/null", "dev/null"}:
        raise BuildError("/dev/null is not a repo path")
    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]
    while raw.startswith("./"):
        raw = raw[2:]
    if not raw:
        raise BuildError("empty patch path is not allowed")
    if raw.startswith("/") or Path(raw).is_absolute():
        raise BuildError(f"absolute path in patch is not allowed: {value}")
    parts = PurePosixPath(raw).parts
    if ".." in parts:
        raise BuildError(f"path traversal in patch is not allowed: {value}")
    if parts and parts[0] == ".git":
        raise BuildError(f"git metadata path in patch is not allowed: {value}")
    if any(part == "" for part in parts):
        raise BuildError(f"invalid patch path: {value}")
    return PurePosixPath(raw).as_posix()


def normalize_paths(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        path = normalize_path(value)
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def has_glob(value: str) -> bool:
    return any(char in value for char in "*?[")


def path_exists(scope_path: str) -> bool:
    if has_glob(scope_path):
        return bool(list(ROOT.glob(scope_path)))
    return (ROOT / scope_path).exists()


def path_matches(path: str, pattern: str) -> bool:
    path = normalize_path(path)
    pattern = normalize_path(pattern)
    if pattern.endswith("/**"):
        prefix = pattern[:-3].rstrip("/")
        return path == prefix or path.startswith(prefix + "/")
    if has_glob(pattern):
        return fnmatch.fnmatch(path, pattern)
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def path_allowed(path: str, patterns: list[str]) -> bool:
    return any(path_matches(path, pattern) for pattern in patterns)


def path_is_protected(path: str, patterns: list[str]) -> bool:
    path = normalize_path(path)
    basename = Path(path).name
    for pattern in patterns:
        normalized = normalize_path(pattern)
        if path_matches(path, normalized):
            return True
        if "/" not in normalized and (fnmatch.fnmatch(basename, normalized) or basename == normalized):
            return True
    return False


def path_is_lockfile(path: str) -> bool:
    basename = Path(normalize_path(path)).name
    return any(fnmatch.fnmatch(basename, pattern) or basename == pattern for pattern in LOCKFILE_PATTERNS)


def path_explicitly_owned(path: str, patterns: list[str]) -> bool:
    normalized = normalize_path(path)
    for pattern in patterns:
        candidate = normalize_path(pattern)
        if candidate == normalized:
            return True
        if has_glob(candidate) and fnmatch.fnmatch(normalized, candidate):
            return True
    return False


def policy_allows_dirty_owned(policies: dict[str, Any]) -> bool:
    if policies.get("allow_dirty_owned"):
        return True
    dirty_policy = policies.get("dirty_repo_policy")
    if isinstance(dirty_policy, dict):
        return str(dirty_policy.get("owned_dirty") or "").lower() in {"allow", "allowed", "allow_and_preserve"}
    return False


def policy_allows_deletes(policies: dict[str, Any]) -> bool:
    return bool(policies.get("allow_deletes") or policies.get("allow_file_deletes"))


def policy_allows_creates(policies: dict[str, Any]) -> bool:
    return bool(policies.get("allow_creates") or policies.get("allow_file_creates"))


def status_path(line: str) -> str:
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip()


def git_status_lines() -> list[str]:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], timeout=30)
    if result["exit_code"] != 0:
        raise BuildError(str(result["stderr"]).strip() or "git status failed")
    return [line for line in str(result["stdout"]).splitlines() if line.strip()]


def git_status_lines_for(cwd: Path) -> list[str]:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=cwd, timeout=30)
    if result["exit_code"] != 0:
        raise BuildError(str(result["stderr"]).strip() or "git status failed")
    return [line for line in str(result["stdout"]).splitlines() if line.strip()]


def status_paths(lines: list[str]) -> list[str]:
    paths: list[str] = []
    for line in lines:
        try:
            paths.append(normalize_path(status_path(line)))
        except BuildError:
            paths.append(status_path(line))
    return sorted(set(paths))


def dirty_paths_for(write_paths: list[str]) -> tuple[list[str], list[str]]:
    dirty_owned: list[str] = []
    dirty_unrelated: list[str] = []
    for line in git_status_lines():
        changed = normalize_path(status_path(line))
        if path_allowed(changed, write_paths):
            dirty_owned.append(changed)
        else:
            dirty_unrelated.append(changed)
    return sorted(set(dirty_owned)), sorted(set(dirty_unrelated))


def derived_read_paths(write_paths: list[str]) -> list[str]:
    reads: list[str] = []
    for item in write_paths:
        path = Path(item)
        if has_glob(item):
            reads.append(item)
        elif "." in path.name and path.parent.as_posix() not in {"", "."}:
            reads.append(path.parent.as_posix().rstrip("/") + "/**")
        else:
            reads.append(item.rstrip("/") + "/**")
    return sorted(set(reads))


def build_dir_for_manifest(manifest: dict[str, Any], manifest_path: Path | None = None) -> Path:
    manifest_id = str(manifest.get("id") or "unknown_build")
    if manifest_path is not None:
        try:
            resolved = manifest_path.resolve()
            root = BUILD_ROOT.resolve()
            if root == resolved.parent or root in resolved.parent.parents:
                return resolved.parent
        except OSError:
            pass
    return BUILD_ROOT / manifest_id


def manifest_write_paths(manifest: dict[str, Any]) -> list[str]:
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    return normalize_paths([str(item) for item in scope.get("write_paths") or []])


def manifest_read_paths(manifest: dict[str, Any]) -> list[str]:
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    return normalize_paths([str(item) for item in scope.get("read_paths") or []])


def manifest_protected_paths(manifest: dict[str, Any]) -> list[str]:
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    protected = [str(item) for item in scope.get("protected_paths") or []]
    return normalize_paths(protected or DEFAULT_PROTECTED_PATHS)


def manifest_routes(manifest: dict[str, Any]) -> list[str]:
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    return [str(item) for item in scope.get("routes") or []]


def mode_policy(mode: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "time_budget_minutes",
        "validation_tier",
        "max_workers",
        "max_files_changed",
        "repair_attempts",
        "risk_acceptance",
        "behavior",
    ]
    return {key: mode.get(key) for key in keys if key in mode}


def create_manifest(args: argparse.Namespace) -> dict[str, Any]:
    modes = load_modes()
    mode_name = args.mode
    if mode_name not in modes:
        raise BuildError(f"unknown mode: {mode_name}")
    mode = modes[mode_name]
    write_paths = normalize_paths(args.write)
    read_paths = normalize_paths(args.read) if args.read else derived_read_paths(write_paths)
    protected_paths = normalize_paths(args.protect or DEFAULT_PROTECTED_PATHS)
    build_id = args.id or f"build_{slugify(args.task)}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    artifact_dir = f".cento/builds/{build_id}/workers/builder_1"
    validation_tier = args.validation or str(mode.get("validation_tier") or "smoke")
    base_ref = git_value(["rev-parse", "HEAD"], "HEAD")

    return {
        "schema_version": SCHEMA_BUILD,
        "id": build_id,
        "task": {
            "title": args.task,
            "description": args.description or args.task,
        },
        "mode": mode_name,
        "mode_policy": mode_policy(mode),
        "source": {
            "base_ref": base_ref,
            "created_at": now_iso(),
        },
        "scope": {
            "routes": [str(route) for route in args.route],
            "read_paths": read_paths,
            "write_paths": write_paths,
            "protected_paths": protected_paths,
        },
        "policies": {
            "ask_policy": mode.get("ask_policy", "blockers_only"),
            "dirty_repo_policy": mode.get(
                "dirty_repo_policy",
                {"unrelated_dirty": "allow_and_preserve", "owned_dirty": "block"},
            ),
            "commit_policy": mode.get("commit_policy", "none"),
            "push_policy": mode.get("push_policy", "none"),
            "allow_unowned_changes": False,
            "allow_protected_changes": False,
            "allow_dirty_owned": bool(args.allow_dirty_owned),
            "allow_creates": False,
            "allow_deletes": False,
        },
        "validation": {
            "tier": validation_tier,
            "commands": [
                {
                    "name": "diff_check",
                    "command": "git diff --check",
                }
            ],
        },
        "workers": [
            {
                "id": "builder_1",
                "type": "local",
                "runtime": "codex",
                "node": None,
                "role": "builder",
                "write_paths": write_paths,
                "artifact_dir": artifact_dir,
            }
        ],
        "acceptance": [
            "Only owned paths are modified.",
            "Patch applies cleanly.",
            "Integration receipt is written.",
            "Validation receipt is written.",
        ],
    }


def validate_manifest(manifest: dict[str, Any], *, allow_dirty_owned: bool = False) -> dict[str, Any]:
    modes = load_modes()
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("schema_version") != SCHEMA_BUILD:
        errors.append(f"schema_version must be {SCHEMA_BUILD}")
    manifest_id = manifest.get("id")
    if not isinstance(manifest_id, str) or not manifest_id:
        errors.append("id is required")
    task = manifest.get("task")
    if not isinstance(task, dict) or not task.get("title"):
        errors.append("task.title is required")
    mode_name = manifest.get("mode")
    if not isinstance(mode_name, str) or mode_name not in modes:
        errors.append(f"mode must exist in .cento/modes.yaml: {mode_name}")
    source = manifest.get("source")
    if not isinstance(source, dict) or not source.get("base_ref") or not source.get("created_at"):
        errors.append("source.base_ref and source.created_at are required")
    scope = manifest.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope is required")
        scope = {}
    routes = scope.get("routes")
    if not isinstance(routes, list):
        errors.append("scope.routes must be a list")
    write_paths = manifest_write_paths(manifest)
    read_paths = manifest_read_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    policies = manifest.get("policies")
    if not isinstance(policies, dict):
        policies = {}
    if not write_paths:
        errors.append("scope.write_paths must include at least one owned path")
    if not isinstance(scope.get("read_paths"), list):
        errors.append("scope.read_paths must be a list")
    for path in write_paths:
        if not path_exists(path) and not policy_allows_creates(policies):
            errors.append(f"owned write path does not exist: {path}")
        if path_is_protected(path, protected_paths):
            errors.append(f"owned write path is protected: {path}")
    for path in protected_paths:
        if path_allowed(path, write_paths):
            errors.append(f"protected path cannot be owned: {path}")
    raw_policies = manifest.get("policies")
    if not isinstance(raw_policies, dict):
        errors.append("policies is required")
    for key in ("ask_policy", "dirty_repo_policy", "commit_policy", "push_policy"):
        if key not in policies:
            errors.append(f"policies.{key} is required")
    for key in ("allow_unowned_changes", "allow_protected_changes"):
        if key not in policies or not isinstance(policies.get(key), bool):
            errors.append(f"policies.{key} must be a boolean")
    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation is required")
    elif "tier" not in validation:
        errors.append("validation.tier is required")
    workers = manifest.get("workers")
    if not isinstance(workers, list) or not workers:
        errors.append("workers must include at least one builder")
    else:
        for worker in workers:
            if not isinstance(worker, dict) or not worker.get("id"):
                errors.append("each worker must include id")
                continue
            worker_paths = worker.get("write_paths")
            if not isinstance(worker_paths, list) or not worker_paths:
                errors.append(f"workers[{worker.get('id')}].write_paths must include owned paths")
            else:
                normalized_worker_paths = normalize_paths([str(item) for item in worker_paths])
                for worker_path in normalized_worker_paths:
                    if not path_allowed(worker_path, write_paths):
                        errors.append(f"worker {worker.get('id')} owns path outside manifest scope: {worker_path}")
    if read_paths and not isinstance(read_paths, list):
        errors.append("scope.read_paths must be a list")

    if write_paths:
        try:
            dirty_owned, _dirty_unrelated = dirty_paths_for(write_paths)
        except BuildError as exc:
            warnings.append(str(exc))
            dirty_owned = []
        if dirty_owned:
            if allow_dirty_owned or policy_allows_dirty_owned(policies):
                warnings.append("dirty owned paths present (allow_dirty_owned): " + ", ".join(dirty_owned))
            else:
                errors.append("dirty owned paths present: " + ", ".join(dirty_owned))

    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
    }


def render_builder_prompt(manifest: dict[str, Any]) -> str:
    task = manifest.get("task") if isinstance(manifest.get("task"), dict) else {}
    workers = manifest.get("workers") if isinstance(manifest.get("workers"), list) else []
    worker = workers[0] if workers and isinstance(workers[0], dict) else {}
    write_paths = manifest_write_paths(manifest)
    read_paths = manifest_read_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    routes = manifest_routes(manifest)
    validation = manifest.get("validation") if isinstance(manifest.get("validation"), dict) else {}
    commands = validation.get("commands") if isinstance(validation.get("commands"), list) else []

    lines = [
        "# Cento Builder Prompt",
        "",
        "You are a Cento Builder working from a manifest-owned local work package.",
        "",
        "## Task",
        f"- Manifest: {manifest.get('id', '<unknown>')}",
        f"- Mode: {manifest.get('mode', '<unknown>')}",
        f"- Title: {task.get('title', '<missing>')}",
        f"- Description: {task.get('description', task.get('title', '<missing>'))}",
        "",
        "## Scope",
        "- Routes: " + (", ".join(routes) if routes else "<none>"),
        "- Owned write paths:",
        *[f"  - {path}" for path in (write_paths or ["<none>"])],
        "- Read paths:",
        *[f"  - {path}" for path in (read_paths or ["<none>"])],
        "- Protected paths:",
        *[f"  - {path}" for path in protected_paths],
        "",
        "## Builder Rules",
        "- Inspect read paths as needed.",
        "- Edit only owned write paths.",
        "- You must not edit unowned paths.",
        "- Stop and request scope expansion if an unowned file is required.",
        "- Preserve dirty unrelated files and staged unrelated files.",
        "- Do not commit, push, modify protected files, change lockfiles, or silently expand scope.",
        "- Do not hide validation failures.",
        "",
        "## Required Output",
        f"- Write artifacts under `{worker.get('artifact_dir', '<artifact_dir>')}`.",
        "- Produce `patch.diff` from current base with:",
        "  `git diff -- <owned_paths> > patch.diff`",
        "- Produce `patch_bundle.json` with touched paths, owned paths, unowned paths, protected paths touched, and summary.",
        "- Produce `worker_artifact.json` with status, manifest id, worker id, touched paths, assumptions, validation, risks, and patch path.",
        "- Produce a short `handoff.md` with changed files, assumptions, validation, and risks.",
        "",
        "## Validation Commands",
    ]
    if commands:
        for item in commands:
            if isinstance(item, dict):
                lines.append(f"- {item.get('name', 'command')}: `{item.get('command', '')}`")
    else:
        lines.append("- No validation commands declared.")
    return "\n".join(lines).rstrip() + "\n"


def parse_diff_path(raw: str) -> str | None:
    raw = raw.strip()
    if not raw or raw == "/dev/null":
        return None
    try:
        parts = shlex.split(raw)
        if parts:
            raw = parts[0]
    except ValueError:
        raw = raw.split("\t", 1)[0].split(" ", 1)[0]
    if raw in {"/dev/null", "dev/null"}:
        return None
    return normalize_patch_path(raw)


def analyze_patch(patch_path: Path) -> dict[str, Any]:
    try:
        text = patch_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise BuildError(f"patch file not found: {patch_path}") from exc
    lines = text.splitlines()
    paths: set[str] = set()
    path_errors: list[str] = []
    delete_paths: set[str] = set()
    symlink_paths: set[str] = set()
    submodule_paths: set[str] = set()
    renames: list[dict[str, str]] = []
    current_paths: set[str] = set()
    rename_from: str | None = None
    binary = False
    for line in lines:
        if line.startswith("diff --git "):
            current_paths = set()
            rename_from = None
            tail = line[len("diff --git ") :]
            if tail.startswith("a/") and " b/" in tail:
                left, right = tail.split(" b/", 1)
                for raw in (left, "b/" + right):
                    try:
                        parsed = parse_diff_path(raw)
                    except BuildError as exc:
                        path_errors.append(str(exc))
                        continue
                    if parsed:
                        paths.add(parsed)
                        current_paths.add(parsed)
            continue
        if line.startswith("Binary files") or line.startswith("GIT binary patch"):
            binary = True
            continue
        if line.startswith("rename from "):
            try:
                rename_from = normalize_patch_path(line[len("rename from ") :])
                paths.add(rename_from)
                current_paths.add(rename_from)
            except BuildError as exc:
                path_errors.append(str(exc))
            continue
        if line.startswith("rename to "):
            try:
                rename_to = normalize_patch_path(line[len("rename to ") :])
                paths.add(rename_to)
                current_paths.add(rename_to)
                if rename_from:
                    renames.append({"from": rename_from, "to": rename_to})
            except BuildError as exc:
                path_errors.append(str(exc))
            continue
        if line.startswith("deleted file mode "):
            delete_paths.update(current_paths)
            continue
        if line.startswith("old mode 120000") or line.startswith("new file mode 120000"):
            symlink_paths.update(current_paths)
            continue
        if line.startswith("Subproject commit "):
            submodule_paths.update(current_paths)
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            raw_path = line[4:]
            try:
                parsed = parse_diff_path(raw_path)
            except BuildError as exc:
                if raw_path.strip() not in {"/dev/null", "dev/null"}:
                    path_errors.append(str(exc))
                parsed = None
            if parsed:
                paths.add(parsed)
                current_paths.add(parsed)
            elif line.startswith("+++ "):
                delete_paths.update(current_paths)
    return {
        "paths": sorted(paths),
        "path_errors": path_errors,
        "delete_paths": sorted(delete_paths),
        "renames": renames,
        "binary": binary,
        "symlink_paths": sorted(symlink_paths),
        "submodule_paths": sorted(submodule_paths),
    }


def extract_patch_paths(patch_path: Path) -> list[str]:
    return list(analyze_patch(patch_path)["paths"])


def patch_policy_rejections(
    analysis: dict[str, Any],
    write_paths: list[str],
    protected_paths: list[str],
    policies: dict[str, Any],
) -> list[str]:
    rejections: list[str] = []
    path_errors = [str(item) for item in analysis.get("path_errors") or []]
    if path_errors:
        rejections.extend(path_errors)
    if analysis.get("binary"):
        rejections.append("binary patches are rejected")
    symlink_paths = [str(item) for item in analysis.get("symlink_paths") or []]
    if symlink_paths:
        rejections.append("symlink patch paths are rejected: " + ", ".join(symlink_paths))
    submodule_paths = [str(item) for item in analysis.get("submodule_paths") or []]
    if submodule_paths:
        rejections.append("submodule patch paths are rejected: " + ", ".join(submodule_paths))
    delete_paths = [str(item) for item in analysis.get("delete_paths") or []]
    if delete_paths and not policy_allows_deletes(policies):
        rejections.append("delete patches are rejected unless policies.allow_deletes is true: " + ", ".join(delete_paths))
    bad_renames: list[str] = []
    for rename in analysis.get("renames") or []:
        source = str(rename.get("from") or "")
        destination = str(rename.get("to") or "")
        if not source or not destination or not path_allowed(source, write_paths) or not path_allowed(destination, write_paths):
            bad_renames.append(f"{source}->{destination}")
    if bad_renames:
        rejections.append("renames require owned source and destination: " + ", ".join(bad_renames))
    lockfiles = [
        path
        for path in [str(item) for item in analysis.get("paths") or []]
        if path_is_lockfile(path) and not path_explicitly_owned(path, write_paths)
    ]
    if lockfiles:
        rejections.append("lockfile changes require explicit ownership: " + ", ".join(sorted(set(lockfiles))))
    return rejections


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return read_json(path)


def artifact_worker_id(manifest: dict[str, Any]) -> str:
    workers = manifest.get("workers") if isinstance(manifest.get("workers"), list) else []
    if workers and isinstance(workers[0], dict) and workers[0].get("id"):
        return str(workers[0]["id"])
    return "builder_1"


def manifest_worker(manifest: dict[str, Any], worker_id: str) -> dict[str, Any]:
    workers = manifest.get("workers") if isinstance(manifest.get("workers"), list) else []
    for worker in workers:
        if isinstance(worker, dict) and str(worker.get("id") or "") == worker_id:
            return worker
    raise BuildError(f"worker not found in manifest: {worker_id}")


def worker_artifact_dir(manifest: dict[str, Any], worker_id: str, build_dir: Path) -> Path:
    try:
        worker = manifest_worker(manifest, worker_id)
    except BuildError:
        worker = {}
    configured = worker.get("artifact_dir") if isinstance(worker, dict) else None
    if isinstance(configured, str) and configured:
        path = Path(configured)
        return path if path.is_absolute() else ROOT / path
    return build_dir / "workers" / worker_id


def worker_write_paths(manifest: dict[str, Any], worker_id: str) -> list[str]:
    worker = manifest_worker(manifest, worker_id)
    paths = worker.get("write_paths") if isinstance(worker.get("write_paths"), list) else manifest_write_paths(manifest)
    return normalize_paths([str(path) for path in paths])


def synthesize_patch_bundle(
    manifest: dict[str, Any],
    patch_path: Path,
    touched_paths: list[str],
    build_dir: Path,
    *,
    out_path: Path | None = None,
    worker_id: str | None = None,
    summary: str = "Synthesized from patch file for local dry-run integration.",
) -> Path:
    write_paths = manifest_write_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    patch_sha = hashlib.sha256(patch_path.read_bytes()).hexdigest()
    manifest_id = str(manifest.get("id") or "build")
    bundle_worker_id = worker_id or artifact_worker_id(manifest)
    bundle = {
        "schema_version": SCHEMA_PATCH_BUNDLE,
        "id": f"bundle_{slugify(manifest_id)}_{slugify(bundle_worker_id)}_{patch_sha[:12]}",
        "manifest_id": manifest.get("id"),
        "worker_id": bundle_worker_id,
        "base_ref": (manifest.get("source") or {}).get("base_ref") if isinstance(manifest.get("source"), dict) else "HEAD",
        "patch_file": rel(patch_path),
        "patch_sha256": patch_sha,
        "touched_paths": touched_paths,
        "owned_paths": write_paths,
        "unowned_paths": [path for path in touched_paths if not path_allowed(path, write_paths)],
        "protected_paths_touched": [path for path in touched_paths if path_is_protected(path, protected_paths)],
        "summary": summary,
        "requires_integration": True,
    }
    path = out_path or build_dir / "integration" / "patch_bundle.json"
    if not path.is_absolute():
        path = ROOT / path
    write_json(path, bundle)
    return path


def resolve_bundle_patch_path(bundle: dict[str, Any], bundle_path: Path | None = None) -> Path:
    patch_file = bundle.get("patch_file")
    if not isinstance(patch_file, str) or not patch_file:
        raise BuildError("patch bundle patch_file is required")
    patch_path = Path(patch_file)
    if not patch_path.is_absolute():
        root_candidate = ROOT / patch_path
        bundle_candidate = bundle_path.parent / patch_path if bundle_path is not None else root_candidate
        patch_path = root_candidate if root_candidate.exists() else bundle_candidate
    return patch_path


def validate_patch_bundle(
    bundle: dict[str, Any],
    manifest: dict[str, Any],
    bundle_path: Path | None,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if bundle.get("schema_version") != SCHEMA_PATCH_BUNDLE:
        errors.append("patch bundle schema mismatch")
    if not isinstance(bundle.get("id"), str) or not bundle.get("id"):
        warnings.append("patch bundle id is missing")
    if bundle.get("manifest_id") != manifest.get("id"):
        errors.append("patch bundle manifest id mismatch")
    if not isinstance(bundle.get("worker_id"), str) or not bundle.get("worker_id"):
        errors.append("patch bundle worker_id is required")
    elif bundle.get("worker_id") != artifact_worker_id(manifest):
        errors.append("patch bundle worker id mismatch")
    for key in ("patch_file", "touched_paths", "owned_paths"):
        if key not in bundle:
            errors.append(f"patch bundle {key} is required")
    touched_paths = normalize_paths([str(path) for path in bundle.get("touched_paths") or []])
    write_paths = manifest_write_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    unowned_paths = [path for path in touched_paths if not path_allowed(path, write_paths)]
    protected_touched = [path for path in touched_paths if path_is_protected(path, protected_paths)]
    if unowned_paths:
        errors.append("patch bundle touches unowned paths: " + ", ".join(unowned_paths))
    if protected_touched:
        errors.append("patch bundle touches protected paths: " + ", ".join(protected_touched))
    if analysis is not None:
        actual_paths = normalize_paths([str(path) for path in analysis.get("paths") or []])
        if sorted(actual_paths) != sorted(touched_paths):
            errors.append(
                "patch bundle touched_paths do not match patch: "
                + ", ".join(sorted(set(actual_paths).symmetric_difference(touched_paths)))
            )
        policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
        errors.extend(patch_policy_rejections(analysis, write_paths, protected_paths, policies))
    try:
        patch_path = resolve_bundle_patch_path(bundle, bundle_path)
    except BuildError as exc:
        errors.append(str(exc))
    else:
        if not patch_path.exists():
            errors.append(f"patch bundle patch_file not found: {patch_path}")
        elif bundle.get("patch_sha256"):
            actual_sha = hashlib.sha256(patch_path.read_bytes()).hexdigest()
            if str(bundle.get("patch_sha256")) != actual_sha:
                errors.append("patch bundle patch_sha256 mismatch")
    return {"status": "passed" if not errors else "failed", "errors": errors, "warnings": warnings}


def shell_validation_command(command: str) -> list[str]:
    return ["bash", "-lc", command]


def run_validation_receipt(
    manifest: dict[str, Any],
    build_dir: Path,
    *,
    skipped: bool = False,
    reason: str = "",
    cwd: Path = ROOT,
) -> dict[str, Any]:
    validation = manifest.get("validation") if isinstance(manifest.get("validation"), dict) else {}
    commands = validation.get("commands") if isinstance(validation.get("commands"), list) else []
    validation_dir = build_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    if skipped:
        for item in commands:
            if not isinstance(item, dict):
                continue
            records.append(
                {
                    "name": str(item.get("name") or "command"),
                    "command": str(item.get("command") or ""),
                    "exit_code": None,
                    "status": "skipped",
                    "reason": reason,
                }
            )
        status = "skipped"
    else:
        status = "passed"
        for item in commands:
            if not isinstance(item, dict):
                continue
            name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(item.get("name") or "command")).strip("_") or "command"
            command = str(item.get("command") or "")
            result = run(shell_validation_command(command), cwd=cwd, timeout=int(item.get("timeout_seconds") or 120))
            stdout_path = validation_dir / f"{name}.stdout"
            stderr_path = validation_dir / f"{name}.stderr"
            stdout_path.write_text(str(result["stdout"]), encoding="utf-8")
            stderr_path.write_text(str(result["stderr"]), encoding="utf-8")
            if result["exit_code"] != 0:
                status = "failed"
            records.append(
                {
                    "name": name,
                    "command": command,
                    "exit_code": result["exit_code"],
                    "status": result["status"],
                    "stdout_path": rel(stdout_path),
                    "stderr_path": rel(stderr_path),
                }
            )
    receipt = {
        "schema_version": SCHEMA_VALIDATION_RECEIPT,
        "manifest_id": manifest.get("id"),
        "tier": validation.get("tier", "smoke"),
        "status": status,
        "commands": records,
        "artifacts": [],
        "written_at": now_iso(),
    }
    write_json(build_dir / "validation_receipt.json", receipt)
    append_event(build_dir, "validation_receipt_written", {"status": status})
    return receipt


def add_check(checks: list[dict[str, Any]], name: str, status: str, details: str = "") -> None:
    row = {"name": name, "status": status}
    if details:
        row["details"] = details
    checks.append(row)


def base_ref_matches(expected: str, current: str, *, allow_head: bool = False) -> bool:
    if not expected:
        return False
    if expected == "HEAD":
        return allow_head
    return current == expected


def fixture_or_dev_path(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        return rel(path).startswith("tests/fixtures/")
    except OSError:
        return False


def write_integration_receipt(build_dir: Path, receipt: dict[str, Any]) -> Path:
    latest = build_dir / "integration_receipt.json"
    write_json(latest, receipt)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(build_dir / "integration" / "receipts" / f"{stamp}.json", receipt)
    return latest


def validate_worker_artifact(
    artifact: dict[str, Any],
    manifest: dict[str, Any] | None = None,
    *,
    allow_head_base: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = ["schema_version", "manifest_id", "worker_id", "role", "status", "touched_paths"]
    for key in required:
        if key not in artifact:
            errors.append(f"worker artifact {key} is required")
    if artifact.get("schema_version") != SCHEMA_WORKER_ARTIFACT:
        errors.append("worker artifact schema mismatch")
    artifact_status = str(artifact.get("status") or "")
    if artifact_status not in {"completed", "accepted"}:
        errors.append(f"worker artifact status is not completed: {artifact_status or '<missing>'}")
    touched = artifact.get("touched_paths")
    if not isinstance(touched, list):
        errors.append("worker artifact touched_paths must be a list")
        touched_paths: list[str] = []
    else:
        touched_paths = normalize_paths([str(path) for path in touched])

    if manifest is not None:
        if artifact.get("manifest_id") != manifest.get("id"):
            errors.append("worker artifact manifest id mismatch")
        if artifact.get("worker_id") != artifact_worker_id(manifest):
            errors.append("worker artifact worker id mismatch")
        write_paths = manifest_write_paths(manifest)
        protected_paths = manifest_protected_paths(manifest)
        unowned = [path for path in touched_paths if not path_allowed(path, write_paths)]
        protected_touched = [path for path in touched_paths if path_is_protected(path, protected_paths)]
        if unowned:
            errors.append("worker artifact touches unowned paths: " + ", ".join(unowned))
        if protected_touched:
            errors.append("worker artifact touches protected paths: " + ", ".join(protected_touched))
        artifact_base = str(artifact.get("base_ref") or "")
        manifest_base = str((manifest.get("source") or {}).get("base_ref") or "") if isinstance(manifest.get("source"), dict) else ""
        if artifact_base and manifest_base and not base_ref_matches(artifact_base, manifest_base, allow_head=allow_head_base):
            errors.append(f"worker artifact base ref mismatch: artifact={artifact_base} manifest={manifest_base}")
    return {"status": "passed" if not errors else "failed", "errors": errors, "warnings": warnings}


def add_rejections(checks: list[dict[str, Any]], rejections: list[str], name: str, errors: list[str]) -> None:
    if errors:
        add_check(checks, name, "failed", "; ".join(errors))
        rejections.extend(errors)
    else:
        add_check(checks, name, "passed")


def create_isolated_worktree(base_ref: str, build_id: str) -> tuple[Path | None, dict[str, Any]]:
    temp_root = ROOT / "workspace" / "tmp" / "cento-build-worktrees"
    temp_root.mkdir(parents=True, exist_ok=True)
    worktree_path = Path(tempfile.mkdtemp(prefix=f"{slugify(build_id)}-", dir=temp_root))
    worktree_path.rmdir()
    result = run(["git", "worktree", "add", "--detach", str(worktree_path), base_ref], timeout=120)
    if result["exit_code"] != 0:
        return None, result
    return worktree_path, result


def remove_isolated_worktree(worktree_path: Path | None) -> dict[str, Any] | None:
    if worktree_path is None:
        return None
    return run(["git", "worktree", "remove", "--force", str(worktree_path)], timeout=120)


def write_worker_handoff(
    path: Path,
    *,
    status: str,
    runtime: str,
    touched_paths: list[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    lines = [
        "# Cento Worker Handoff",
        "",
        f"- Status: {status}",
        f"- Runtime: {runtime}",
        "",
        "## Changed Files",
    ]
    lines.extend([f"- {item}" for item in touched_paths] or ["- <none>"])
    lines.extend(["", "## Risks / Rejections"])
    lines.extend([f"- {item}" for item in errors] or ["- <none>"])
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {item}" for item in warnings])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def fixture_append_or_replace(path: Path, marker: str) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    replacements = [
        ("Draft docs page.", "Production-ready docs page."),
        ("Cheap Spark/Codex workers are now an explicit coordination option.", "Cheap Spark/Codex workers remain an explicit coordination option."),
        ("debug copy", "production copy"),
    ]
    for old, new in replacements:
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            return
    path.write_text(text.rstrip() + f"\n{marker}\n", encoding="utf-8")


def run_fixture_worker_runtime(
    manifest: dict[str, Any],
    worker_id: str,
    cwd: Path,
    runtime: str,
    fixture_case: str = "valid",
) -> dict[str, Any]:
    write_paths = worker_write_paths(manifest, worker_id)
    protected_paths = manifest_protected_paths(manifest)
    target = cwd / write_paths[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    case = fixture_case
    if runtime.startswith("fixture-"):
        case = runtime.removeprefix("fixture-")

    if case == "valid":
        if not target.exists():
            raise BuildError(f"fixture target does not exist in worker worktree: {write_paths[0]}")
        fixture_append_or_replace(target, "<!-- cento fixture builder touched -->")
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture patch written\n", "stderr": ""}

    if case == "unowned":
        unowned = "README.md" if not path_allowed("README.md", write_paths) else "CLUSTER_NOTICE.md"
        fixture_append_or_replace(cwd / unowned, "<!-- cento unowned fixture touched -->")
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture unowned patch written\n", "stderr": ""}

    if case == "protected":
        protected = protected_paths[0] if protected_paths else ".env.fixture"
        protected_path = cwd / protected
        protected_path.parent.mkdir(parents=True, exist_ok=True)
        protected_path.write_text("CENTO_FIXTURE_PROTECTED=1\n", encoding="utf-8")
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture protected patch written\n", "stderr": ""}

    if case == "binary":
        target.write_bytes(b"\x00CENTO_BINARY_FIXTURE\n")
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture binary patch written\n", "stderr": ""}

    if case == "delete":
        if not target.exists():
            raise BuildError(f"fixture target does not exist in worker worktree: {write_paths[0]}")
        target.unlink()
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture delete patch written\n", "stderr": ""}

    if case == "lockfile":
        lockfile = next((path for path in LOCKFILE_PATTERNS if (cwd / path).exists()), "package-lock.json")
        fixture_path = cwd / lockfile
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        if fixture_path.exists():
            fixture_append_or_replace(fixture_path, "cento fixture lockfile touch")
        else:
            fixture_path.write_text('{"cento_fixture": true}\n', encoding="utf-8")
        return {"runtime": runtime, "fixture_case": case, "exit_code": 0, "status": "passed", "stdout": "fixture lockfile patch written\n", "stderr": ""}

    raise BuildError(f"unknown fixture case: {case}")


def run_worker_runtime(
    manifest: dict[str, Any],
    manifest_path: Path,
    worker_id: str,
    runtime: str,
    cwd: Path,
    build_dir: Path,
    worker_dir: Path,
    timeout: int,
    fixture_case: str = "valid",
    command_template: str | None = None,
    profile_name: str | None = None,
    profile_config: dict[str, Any] | None = None,
    allow_unsafe_command: bool = False,
) -> dict[str, Any]:
    prompt_path = build_dir / "builder.prompt.md"
    if not prompt_path.exists():
        prompt_path.write_text(render_builder_prompt(manifest), encoding="utf-8")

    context = runtime_context(
        manifest_path=manifest_path,
        build_dir=build_dir,
        worker_dir=worker_dir,
        worktree=cwd,
        worker_id=worker_id,
    )

    if profile_config is not None:
        runtime = str(profile_config.get("type") or runtime)
        profile_env_allowlist = profile_config.get("env_allowlist")
        env_allowlist = [str(item) for item in profile_env_allowlist] if isinstance(profile_env_allowlist, list) else None
        env = build_worker_env(manifest, manifest_path, worker_id, build_dir, worker_dir, cwd, env_allowlist)
        if runtime == "fixture":
            fixture_case = str(profile_config.get("fixture_case") or fixture_case)
            result = run_fixture_worker_runtime(manifest, worker_id, cwd, f"fixture-{fixture_case}", fixture_case)
            result["runtime_profile"] = profile_name
            return result
        if runtime == "command":
            argv = [format_runtime_value(item, context) for item in profile_config.get("argv") or []]
            if not argv:
                raise BuildError(f"runtime profile {profile_name} has no argv")
            cwd_value = profile_config.get("cwd") or "{worktree}"
            command_cwd = Path(format_runtime_value(cwd_value, context))
            if not command_cwd.is_absolute():
                command_cwd = cwd / command_cwd
            if not command_cwd.exists():
                raise BuildError(f"runtime profile cwd does not exist: {command_cwd}")
            started = time.perf_counter()
            try:
                proc = subprocess.run(
                    argv,
                    cwd=command_cwd,
                    shell=False,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout,
                    check=False,
                )
            except OSError as exc:
                raise BuildError(f"runtime command launch failed: {exc}") from exc
            return {
                "runtime": runtime,
                "runtime_profile": profile_name,
                "argv": argv,
                "cwd": str(command_cwd),
                "exit_code": proc.returncode,
                "status": "passed" if proc.returncode == 0 else "failed",
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        raise BuildError(f"unknown runtime profile type for {profile_name}: {runtime}")

    env = build_worker_env(manifest, manifest_path, worker_id, build_dir, worker_dir, cwd)
    if runtime.startswith("fixture"):
        return run_fixture_worker_runtime(manifest, worker_id, cwd, runtime, fixture_case)

    if runtime in {"command", "local-codex", "codex"}:
        if not allow_unsafe_command:
            raise BuildError("raw command runtime requires --allow-unsafe-command or --runtime-profile")
        command_template = (command_template or os.environ.get("CENTO_LOCAL_BUILDER", "")).strip()
        if not command_template:
            raise BuildError("runtime command requires --command or CENTO_LOCAL_BUILDER, e.g. `codex exec --prompt-file {prompt}`")
        formatted = command_template.format(
            prompt=shlex.quote(str(prompt_path)),
            manifest=shlex.quote(str(manifest_path)),
            build_dir=shlex.quote(str(build_dir)),
            worker_dir=shlex.quote(str(worker_dir)),
            worktree=shlex.quote(str(cwd)),
            worker=shlex.quote(worker_id),
            artifact_dir=shlex.quote(str(worker_dir)),
        )
        started = time.perf_counter()
        proc = subprocess.run(
            formatted,
            cwd=cwd,
            shell=True,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "runtime": runtime,
            "exit_code": proc.returncode,
            "status": "passed" if proc.returncode == 0 else "failed",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    raise BuildError(f"unknown worker runtime: {runtime}")


def run_build_worker(
    manifest_path: Path,
    *,
    worker_id: str,
    runtime: str,
    use_worktree: bool,
    timeout: int | None,
    allow_dirty_owned: bool = False,
    fixture_case: str = "valid",
    command_template: str | None = None,
    runtime_profile_name: str | None = None,
    allow_unsafe_command: bool = False,
) -> dict[str, Any]:
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    manifest = read_json(manifest_path)
    build_dir = build_dir_for_manifest(manifest, manifest_path)
    build_dir.mkdir(parents=True, exist_ok=True)
    worker = manifest_worker(manifest, worker_id)
    worker_dir = worker_artifact_dir(manifest, worker_id, build_dir)
    worker_dir.mkdir(parents=True, exist_ok=True)
    profile_config: dict[str, Any] | None = None
    if runtime_profile_name:
        profile_config = runtime_profile(runtime_profile_name)
        runtime = str(profile_config.get("type") or runtime)
        if runtime == "fixture":
            fixture_case = str(profile_config.get("fixture_case") or fixture_case)
        if runtime == "command" and not use_worktree:
            raise BuildError("command runtime profiles require --worktree")
    effective_timeout = runtime_timeout(profile_config, timeout)
    patch_path = worker_dir / "patch.diff"
    bundle_path = worker_dir / "patch_bundle.json"
    artifact_path = worker_dir / "worker_artifact.json"
    handoff_path = worker_dir / "handoff.md"
    for stale_path in (patch_path, bundle_path, artifact_path, handoff_path, worker_dir / "runtime.stdout", worker_dir / "runtime.stderr"):
        if stale_path.exists():
            stale_path.unlink()
    warnings: list[str] = []
    errors: list[str] = []
    worktree_path: Path | None = None
    worktree_removed = False
    started_at = now_iso()

    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    if allow_dirty_owned:
        policies = {**policies, "allow_dirty_owned": True}
        manifest = {**manifest, "policies": policies}
    manifest_result = validate_manifest(manifest, allow_dirty_owned=allow_dirty_owned)
    if manifest_result["status"] != "passed":
        try:
            failure_write_paths = worker_write_paths(manifest, worker_id)
            failure_dirty_owned, failure_dirty_unrelated = dirty_paths_for(failure_write_paths)
        except BuildError:
            failure_dirty_owned, failure_dirty_unrelated = [], []
        patch_path.write_text("", encoding="utf-8")
        (worker_dir / "runtime.stdout").write_text("", encoding="utf-8")
        (worker_dir / "runtime.stderr").write_text("; ".join(manifest_result["errors"]), encoding="utf-8")
        failure_artifact = {
            "schema_version": SCHEMA_WORKER_ARTIFACT,
            "manifest_id": manifest.get("id"),
            "manifest_path": rel(manifest_path),
            "worker_id": worker_id,
            "worker_type": str(worker.get("type") or "local"),
            "role": str(worker.get("role") or "builder"),
            "runtime": runtime,
            "runtime_profile": runtime_profile_name,
            "fixture_case": fixture_case if runtime.startswith("fixture") else None,
            "status": "failed",
            "base_ref": str((manifest.get("source") or {}).get("base_ref") or "HEAD") if isinstance(manifest.get("source"), dict) else "HEAD",
            "artifact_dir": rel(worker_dir),
            "patch_file": rel(patch_path),
            "patch_path": rel(patch_path),
            "patch_bundle": None,
            "handoff": rel(handoff_path),
            "touched_paths": [],
            "owned_paths": [],
            "unowned_paths": [],
            "protected_paths_touched": [],
            "staged_paths": [],
            "dirty_owned_paths": failure_dirty_owned,
            "dirty_unrelated_paths": failure_dirty_unrelated,
            "rejections": [str(item) for item in manifest_result["errors"]],
            "assumptions": [],
            "validation": {"status": "not_run", "reason": "manifest check failed before worker launch"},
            "risks": [str(item) for item in manifest_result["errors"]],
            "warnings": [str(item) for item in manifest_result["warnings"]],
            "stdout_path": rel(worker_dir / "runtime.stdout"),
            "stderr_path": rel(worker_dir / "runtime.stderr"),
            "duration_ms": 0,
            "runtime_limits": {
                "timeout_seconds": effective_timeout,
                "max_changed_files": runtime_limit(profile_config, "max_changed_files"),
                "max_patch_lines": runtime_limit(profile_config, "max_patch_lines"),
            },
            "runtime_result": {
                "status": "not_run",
                "exit_code": None,
                "stdout_path": rel(worker_dir / "runtime.stdout"),
                "stderr_path": rel(worker_dir / "runtime.stderr"),
            },
            "launch_head": "",
            "worker_head": "",
            "started_at": started_at,
            "completed_at": now_iso(),
        }
        write_json(artifact_path, failure_artifact)
        write_worker_handoff(
            handoff_path,
            status="failed",
            runtime=runtime,
            touched_paths=[],
            errors=[str(item) for item in manifest_result["errors"]],
            warnings=[str(item) for item in manifest_result["warnings"]],
        )
        append_event(
            build_dir,
            "worker_artifact_written",
            {
                "worker_id": worker_id,
                "runtime": runtime,
                "runtime_profile": runtime_profile_name,
                "status": "failed",
                "artifact": rel(artifact_path),
            },
        )
        raise BuildError("manifest check failed: " + "; ".join(manifest_result["errors"]))
    warnings.extend([str(item) for item in manifest_result["warnings"]])

    write_paths = worker_write_paths(manifest, worker_id)
    dirty_owned, dirty_unrelated = dirty_paths_for(write_paths)
    if dirty_owned and not policy_allows_dirty_owned(policies):
        raise BuildError("dirty owned paths present: " + ", ".join(dirty_owned))

    base_ref = str((manifest.get("source") or {}).get("base_ref") or "HEAD") if isinstance(manifest.get("source"), dict) else "HEAD"
    current_base = git_value(["rev-parse", "HEAD"], "HEAD")
    run_cwd = ROOT
    append_event(build_dir, "worker_started", {"worker_id": worker_id, "runtime": runtime, "runtime_profile": runtime_profile_name})
    runtime_result: dict[str, Any] = {
        "runtime": runtime,
        "runtime_profile": runtime_profile_name,
        "fixture_case": fixture_case if runtime.startswith("fixture") else None,
        "exit_code": None,
        "status": "failed",
        "stdout": "",
        "stderr": "",
        "duration_ms": 0,
    }
    runtime_failed = False
    skip_collection = False
    launch_head = ""
    worker_head = ""
    try:
        if use_worktree:
            worktree_ref = current_base if base_ref == "HEAD" else base_ref
            worktree_path, worktree_result = create_isolated_worktree(worktree_ref, f"{manifest.get('id')}-{worker_id}")
            if worktree_path is None:
                detail = (str(worktree_result["stderr"]) or str(worktree_result["stdout"])).strip()
                raise BuildError("isolated worker worktree creation failed: " + detail)
            run_cwd = worktree_path

        launch_head_result = run(["git", "rev-parse", "HEAD"], cwd=run_cwd, timeout=30)
        launch_head = str(launch_head_result["stdout"]).strip() if launch_head_result["exit_code"] == 0 else ""
        runtime_result = run_worker_runtime(
            manifest,
            manifest_path,
            worker_id,
            runtime,
            run_cwd,
            build_dir,
            worker_dir,
            effective_timeout,
            fixture_case=fixture_case,
            command_template=command_template,
            profile_name=runtime_profile_name,
            profile_config=profile_config,
            allow_unsafe_command=allow_unsafe_command,
        )
        if runtime_result.get("exit_code") != 0:
            runtime_failed = True
            errors.append("worker runtime failed")
    except (BuildError, subprocess.TimeoutExpired) as exc:
        runtime_failed = True
        if use_worktree and worktree_path is None:
            skip_collection = True
        errors.append(str(exc))
        runtime_result["stderr"] = str(exc)
        runtime_result["status"] = "failed"
    try:
        if skip_collection:
            status_lines = []
            status_touched_paths = []
            patch_text = ""
        else:
            worker_head_result = run(["git", "rev-parse", "HEAD"], cwd=run_cwd, timeout=30)
            worker_head = str(worker_head_result["stdout"]).strip() if worker_head_result["exit_code"] == 0 else ""
            if launch_head and worker_head and worker_head != launch_head:
                errors.append("worker commits are rejected")

            status_lines = git_status_lines_for(run_cwd)
            status_touched_paths = status_paths(status_lines)
        staged_paths = sorted(
            set(
                normalize_path(status_path(line))
                for line in status_lines
                if line and line[0] not in {" ", "?"}
            )
        )
        if staged_paths:
            errors.append("worker staged files are rejected: " + ", ".join(staged_paths))
        if not skip_collection:
            diff_result = run(["git", "diff", "--binary"], cwd=run_cwd, timeout=120)
            if diff_result["exit_code"] != 0:
                errors.append("git diff failed: " + (str(diff_result["stderr"]) or str(diff_result["stdout"])).strip())
                patch_text = ""
            else:
                patch_text = str(diff_result["stdout"])
        patch_path.write_text(patch_text, encoding="utf-8")

        analysis = analyze_patch(patch_path) if patch_text.strip() else {"paths": [], "path_errors": []}
        patch_touched_paths = [str(path) for path in analysis.get("paths") or []]
        touched_paths = sorted(set(status_touched_paths + patch_touched_paths))
        if not patch_text.strip():
            errors.append("worker produced no patch")
        max_changed_files = runtime_limit(profile_config, "max_changed_files")
        if max_changed_files is not None and len(touched_paths) > max_changed_files:
            errors.append(f"worker touched too many files: {len(touched_paths)} > {max_changed_files}")
        max_patch_lines = runtime_limit(profile_config, "max_patch_lines")
        if max_patch_lines is not None and len(patch_text.splitlines()) > max_patch_lines:
            errors.append(f"worker patch is too large: {len(patch_text.splitlines())} lines > {max_patch_lines}")

        protected_paths = manifest_protected_paths(manifest)
        unowned_paths = [path for path in touched_paths if not path_allowed(path, write_paths)]
        protected_touched = [path for path in touched_paths if path_is_protected(path, protected_paths)]
        if unowned_paths:
            errors.append("worker touched unowned paths: " + ", ".join(unowned_paths))
        if protected_touched:
            errors.append("worker touched protected paths: " + ", ".join(protected_touched))
        if patch_text.strip():
            errors.extend(patch_policy_rejections(analysis, write_paths, protected_paths, policies))
        if patch_text.strip() and not errors:
            synthesize_patch_bundle(
                manifest,
                patch_path,
                patch_touched_paths,
                build_dir,
                out_path=bundle_path,
                worker_id=worker_id,
                summary=f"Collected from {runtime_profile_name or runtime} worker runtime.",
            )
            append_event(build_dir, "patch_bundle_created", {"worker_id": worker_id, "patch_bundle": rel(bundle_path)})

        status = "failed" if runtime_failed or errors == ["worker produced no patch"] else ("rejected" if errors else "completed")
        artifact = {
            "schema_version": SCHEMA_WORKER_ARTIFACT,
            "manifest_id": manifest.get("id"),
            "manifest_path": rel(manifest_path),
            "worker_id": worker_id,
            "worker_type": str(worker.get("type") or "local"),
            "role": str(worker.get("role") or "builder"),
            "runtime": runtime,
            "runtime_profile": runtime_profile_name,
            "fixture_case": fixture_case if runtime.startswith("fixture") else None,
            "status": status,
            "base_ref": base_ref,
            "artifact_dir": rel(worker_dir),
            "patch_file": rel(patch_path) if patch_path.exists() else None,
            "patch_path": rel(patch_path) if patch_path.exists() else None,
            "patch_bundle": rel(bundle_path) if bundle_path.exists() else None,
            "handoff": rel(handoff_path),
            "touched_paths": touched_paths,
            "owned_paths": [path for path in touched_paths if path_allowed(path, write_paths)],
            "unowned_paths": unowned_paths,
            "protected_paths_touched": protected_touched,
            "staged_paths": staged_paths,
            "dirty_unrelated_paths": dirty_unrelated,
            "rejections": errors,
            "assumptions": [],
            "validation": {"status": "not_run", "reason": "worker collection only; integration validates patch"},
            "risks": errors,
            "warnings": warnings,
            "stdout_path": rel(worker_dir / "runtime.stdout"),
            "stderr_path": rel(worker_dir / "runtime.stderr"),
            "duration_ms": runtime_result.get("duration_ms", 0),
            "runtime_limits": {
                "timeout_seconds": effective_timeout,
                "max_changed_files": runtime_limit(profile_config, "max_changed_files"),
                "max_patch_lines": runtime_limit(profile_config, "max_patch_lines"),
            },
            "runtime_result": {
                "status": runtime_result.get("status"),
                "exit_code": runtime_result.get("exit_code"),
                "stdout_path": rel(worker_dir / "runtime.stdout"),
                "stderr_path": rel(worker_dir / "runtime.stderr"),
                "argv": runtime_result.get("argv"),
                "cwd": runtime_result.get("cwd"),
            },
            "launch_head": launch_head,
            "worker_head": worker_head,
            "started_at": started_at,
            "completed_at": now_iso(),
        }
        (worker_dir / "runtime.stdout").write_text(str(runtime_result.get("stdout") or ""), encoding="utf-8")
        (worker_dir / "runtime.stderr").write_text(str(runtime_result.get("stderr") or ""), encoding="utf-8")
        write_json(artifact_path, artifact)
        write_worker_handoff(handoff_path, status=status, runtime=runtime, touched_paths=touched_paths, errors=errors, warnings=warnings)
        append_event(
            build_dir,
            "worker_artifact_written",
            {
                "worker_id": worker_id,
                "runtime": runtime,
                "runtime_profile": runtime_profile_name,
                "status": status,
                "artifact": rel(artifact_path),
            },
        )
    except Exception:
        raise
    finally:
        remove_result = remove_isolated_worktree(worktree_path)
        if remove_result is not None:
            worktree_removed = remove_result["exit_code"] == 0
            if not worktree_removed:
                warnings.append("worker worktree cleanup failed: " + (str(remove_result["stderr"]) or str(remove_result["stdout"])).strip())

    result = {
        "status": "accepted" if artifact_path.exists() and read_json(artifact_path).get("status") == "completed" else "rejected",
        "worker_status": read_json(artifact_path).get("status") if artifact_path.exists() else "failed",
        "build_id": manifest.get("id"),
        "worker_id": worker_id,
        "runtime": runtime,
        "runtime_profile": runtime_profile_name,
        "worker_dir": rel(worker_dir),
        "worker_artifact": rel(artifact_path),
        "patch_bundle": rel(bundle_path) if bundle_path.exists() else None,
        "patch": rel(patch_path),
        "handoff": rel(handoff_path),
        "touched_paths": read_json(artifact_path).get("touched_paths", []) if artifact_path.exists() else [],
        "worktree_removed": worktree_removed if use_worktree else None,
    }
    if result["status"] != "accepted":
        artifact = read_json(artifact_path) if artifact_path.exists() else {}
        result["errors"] = artifact.get("risks") or ["worker run rejected"]
    return result


def write_apply_receipt(build_dir: Path, receipt: dict[str, Any]) -> Path:
    latest = build_dir / "apply_receipt.json"
    write_json(latest, receipt)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(build_dir / "apply" / "receipts" / f"{stamp}.json", receipt)
    return latest


def resolved_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def same_fileish_path(left: str | None, right: Path) -> bool:
    if not left:
        return False
    candidate = Path(left)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        return candidate.resolve() == right.resolve()
    except FileNotFoundError:
        return candidate.absolute() == right.absolute()


def write_taskstream_evidence(
    build_dir: Path,
    manifest: dict[str, Any],
    *,
    status: str,
    changed_files: list[str],
    risk_overrides: list[str] | None = None,
) -> Path:
    build_id = str(manifest.get("id") or build_dir.name)
    worker_artifacts = sorted(rel(path) for path in (build_dir / "workers").glob("*/worker_artifact.json"))
    patch_bundles = sorted(rel(path) for path in (build_dir / "workers").glob("*/patch_bundle.json"))
    evidence = {
        "schema_version": SCHEMA_TASKSTREAM_EVIDENCE,
        "type": "cento_build_evidence",
        "build_id": build_id,
        "task_id": None,
        "mode": manifest.get("mode"),
        "manifest": rel(build_dir / "manifest.json"),
        "worker_artifacts": worker_artifacts,
        "patch_bundles": patch_bundles,
        "integration_receipt": rel(build_dir / "integration_receipt.json") if (build_dir / "integration_receipt.json").exists() else None,
        "validation_receipt": rel(build_dir / "validation_receipt.json") if (build_dir / "validation_receipt.json").exists() else None,
        "apply_receipt": rel(build_dir / "apply_receipt.json") if (build_dir / "apply_receipt.json").exists() else None,
        "events": rel(build_dir / "events.ndjson") if (build_dir / "events.ndjson").exists() else None,
        "changed_files": changed_files,
        "status": status,
        "risk_overrides": risk_overrides or [],
        "screenshots": [],
        "written_at": now_iso(),
    }
    path = build_dir / "taskstream_evidence.json"
    write_json(path, evidence)
    append_event(build_dir, "taskstream_evidence_attached", {"status": status, "path": rel(path)})
    return path


def apply_build_bundle(
    manifest_path: Path,
    bundle_path: Path,
    receipt_path: Path,
    *,
    allow_dirty_owned: bool = False,
    allow_base_mismatch: bool = False,
) -> dict[str, Any]:
    manifest_path = resolved_repo_path(manifest_path)
    bundle_path = resolved_repo_path(bundle_path)
    receipt_path = resolved_repo_path(receipt_path)
    manifest = read_json(manifest_path)
    build_dir = build_dir_for_manifest(manifest, manifest_path)
    checks: list[dict[str, Any]] = []
    rejections: list[str] = []
    warnings: list[str] = []
    dirty_owned: list[str] = []
    dirty_unrelated: list[str] = []
    applied = False
    validation_receipt: dict[str, Any] | None = None

    def reject(name: str, detail: str) -> None:
        add_check(checks, name, "failed", detail)
        rejections.append(detail)

    try:
        bundle = read_json(bundle_path)
        add_check(checks, "patch_bundle_loaded", "passed", rel(bundle_path))
    except BuildError as exc:
        bundle = {}
        reject("patch_bundle_loaded", str(exc))

    try:
        integration = read_json(receipt_path)
        add_check(checks, "integration_receipt_loaded", "passed", rel(receipt_path))
    except BuildError as exc:
        integration = {}
        reject("integration_receipt_loaded", str(exc))

    if integration.get("schema_version") != SCHEMA_INTEGRATION_RECEIPT:
        reject("integration_receipt_schema", "integration receipt schema mismatch")
    elif integration.get("status") != "accepted":
        reject("integration_receipt_status", "integration receipt is not accepted")
    else:
        add_check(checks, "integration_receipt_status", "passed", rel(receipt_path))

    if integration.get("manifest_id") != manifest.get("id"):
        reject("manifest_match", "manifest id mismatch")
    else:
        add_check(checks, "manifest_match", "passed")

    if bundle.get("manifest_id") != manifest.get("id"):
        reject("bundle_manifest_match", "bundle manifest id mismatch")
    else:
        add_check(checks, "bundle_manifest_match", "passed")

    bundle_id = str(bundle.get("id") or "")
    receipt_bundle_id = str(integration.get("patch_bundle_id") or integration.get("bundle_id") or "")
    if bundle_id and receipt_bundle_id and bundle_id != receipt_bundle_id:
        reject("bundle_id_match", f"bundle id mismatch: bundle={bundle_id} receipt={receipt_bundle_id}")
    elif bundle_id:
        add_check(checks, "bundle_id_match", "passed", bundle_id)
    else:
        add_check(checks, "bundle_id_match", "warning", "bundle id missing")

    if not same_fileish_path(str(integration.get("patch_bundle") or ""), bundle_path):
        reject("bundle_receipt_match", "bundle path does not match accepted integration receipt")
    else:
        add_check(checks, "bundle_receipt_match", "passed", rel(bundle_path))

    patch_path: Path | None = None
    analysis: dict[str, Any] | None = None
    touched_paths: list[str] = []
    write_paths = manifest_write_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    if allow_dirty_owned:
        policies = {**policies, "allow_dirty_owned": True}
    try:
        patch_path = resolve_bundle_patch_path(bundle, bundle_path)
        analysis = analyze_patch(patch_path)
        touched_paths = [str(path) for path in analysis.get("paths") or []]
        add_check(checks, "patch_loaded", "passed", rel(patch_path))
    except BuildError as exc:
        reject("patch_loaded", str(exc))

    if analysis is not None:
        bundle_result = validate_patch_bundle(bundle, manifest, bundle_path, analysis)
        add_rejections(checks, rejections, "patch_bundle_contract", [str(error) for error in bundle_result.get("errors") or []])
        warnings.extend([str(warning) for warning in bundle_result.get("warnings") or []])

    try:
        dirty_owned, dirty_unrelated = dirty_paths_for(write_paths)
    except BuildError as exc:
        warnings.append(str(exc))
        add_check(checks, "dirty_owned_check", "warning", str(exc))
    else:
        if dirty_unrelated:
            add_check(checks, "dirty_unrelated_check", "passed", f"{len(dirty_unrelated)} unrelated dirty path(s) preserved")
        else:
            add_check(checks, "dirty_unrelated_check", "passed")
        if dirty_owned and not policy_allows_dirty_owned(policies):
            reject("dirty_owned_check", "dirty owned paths present: " + ", ".join(dirty_owned))
        elif dirty_owned:
            add_check(checks, "dirty_owned_check", "warning", ", ".join(dirty_owned))
            warnings.append("dirty owned paths present (allow_dirty_owned): " + ", ".join(dirty_owned))
        else:
            add_check(checks, "dirty_owned_check", "passed")

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    expected_base = str(source.get("base_ref") or "HEAD")
    current_base = git_value(["rev-parse", "HEAD"], "HEAD")
    base_match = allow_base_mismatch or base_ref_matches(expected_base, current_base, allow_head=fixture_or_dev_path(manifest_path))
    if base_match:
        add_check(checks, "base_ref_check", "passed" if not allow_base_mismatch else "warning", f"manifest={expected_base} current={current_base}")
    else:
        reject("base_ref_check", f"base ref mismatch: manifest={expected_base} current={current_base}")

    if not rejections and patch_path is not None:
        check_result = run(["git", "apply", "--check", str(patch_path)], cwd=ROOT, timeout=120)
        if check_result["exit_code"] != 0:
            reject("git_apply_check", (str(check_result["stderr"]) or str(check_result["stdout"])).strip() or "git apply --check failed")
        else:
            add_check(checks, "git_apply_check", "passed")
            apply_result = run(["git", "apply", str(patch_path)], cwd=ROOT, timeout=120)
            if apply_result["exit_code"] != 0:
                reject("git_apply", (str(apply_result["stderr"]) or str(apply_result["stdout"])).strip() or "git apply failed")
            else:
                applied = True
                add_check(checks, "git_apply", "passed")
                validation_receipt = run_validation_receipt(manifest, build_dir, cwd=ROOT)
                add_check(checks, "validation_receipt", validation_receipt["status"], rel(build_dir / "validation_receipt.json"))
    elif rejections:
        validation_receipt = run_validation_receipt(manifest, build_dir, skipped=True, reason="apply pre-checks failed")
        add_check(checks, "validation_receipt", "skipped", rel(build_dir / "validation_receipt.json"))

    status = "applied" if applied and not any(check["name"] == "git_apply" and check["status"] == "failed" for check in checks) else ("failed" if any(check["name"].endswith("_loaded") and check["status"] == "failed" for check in checks) else "rejected")
    risk_overrides = []
    if allow_dirty_owned:
        risk_overrides.append("allow_dirty_owned")
    if allow_base_mismatch:
        risk_overrides.append("allow_base_mismatch")
    receipt = {
        "schema_version": SCHEMA_APPLY_RECEIPT,
        "manifest_id": manifest.get("id"),
        "bundle_id": str(bundle.get("id") or ""),
        "status": status,
        "mode": manifest.get("mode"),
        "patch_bundle": rel(bundle_path),
        "patch_path": rel(patch_path) if patch_path else None,
        "integration_receipt": rel(receipt_path),
        "touched_paths": touched_paths,
        "changed_paths": touched_paths,
        "checks": checks,
        "applied": applied,
        "rejections": rejections,
        "warnings": warnings,
        "risk_overrides": risk_overrides,
        "dirty_owned_paths": dirty_owned,
        "dirty_unrelated_paths": dirty_unrelated,
        "base_ref_manifest": expected_base,
        "base_ref_current": current_base,
        "base_ref_match": base_match,
        "validation_receipt": rel(build_dir / "validation_receipt.json") if validation_receipt else None,
        "written_at": now_iso(),
    }
    apply_receipt_path = write_apply_receipt(build_dir, receipt)
    evidence_status = "review" if status == "applied" and (validation_receipt or {}).get("status") == "passed" else "blocked"
    write_taskstream_evidence(build_dir, manifest, status=evidence_status, changed_files=touched_paths, risk_overrides=risk_overrides)
    append_event(
        build_dir,
        "patch_applied" if status == "applied" else "patch_apply_rejected",
        {"status": status, "apply_receipt": rel(apply_receipt_path), "patch_bundle": rel(bundle_path), "rejections": rejections},
    )
    return receipt


def command_init(args: argparse.Namespace) -> int:
    manifest = create_manifest(args)
    build_dir = BUILD_ROOT / str(manifest["id"])
    if build_dir.exists() and not args.force:
        raise BuildError(f"build already exists: {rel(build_dir)}; use --force to overwrite manifest and prompt")
    build_dir.mkdir(parents=True, exist_ok=True)
    write_json(build_dir / "manifest.json", manifest)
    (build_dir / "builder.prompt.md").write_text(render_builder_prompt(manifest), encoding="utf-8")
    append_event(build_dir, "build_manifest_created", {"manifest_id": manifest["id"]})
    append_event(build_dir, "builder_prompt_created", {"path": rel(build_dir / "builder.prompt.md")})
    result = {"build_id": manifest["id"], "build_dir": rel(build_dir), "manifest": rel(build_dir / "manifest.json"), "prompt": rel(build_dir / "builder.prompt.md")}
    print(json.dumps(result, indent=2) if args.json else rel(build_dir / "manifest.json"))
    return 0


def command_check(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = read_json(manifest_path)
    result = validate_manifest(manifest)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"manifest check: {result['status']}")
        for warning in result["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        for error in result["errors"]:
            print(f"error: {error}", file=sys.stderr)
    return 0 if result["status"] == "passed" else 1


def command_prompt(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    manifest = read_json(manifest_path)
    text = render_builder_prompt(manifest)
    if args.write or args.out:
        build_dir = build_dir_for_manifest(manifest, manifest_path)
        out_path = Path(args.out) if args.out else build_dir / "builder.prompt.md"
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        append_event(build_dir, "builder_prompt_created", {"path": rel(out_path)})
        print(rel(out_path))
    else:
        print(text, end="")
    return 0


def command_integrate(args: argparse.Namespace) -> int:
    if args.apply:
        raise BuildError("cento build integrate v1 supports dry-run only; omit --apply")

    manifest_path = Path(args.manifest)
    checks: list[dict[str, Any]] = []
    rejections: list[str] = []
    warnings: list[str] = []
    touched_paths: list[str] = []
    manifest: dict[str, Any] = {"id": manifest_path.stem, "mode": "unknown"}
    build_dir = BUILD_ROOT / manifest_path.stem
    bundle: dict[str, Any] | None = None
    patch_bundle_path: Path | None = None
    patch_path: Path | None = None
    analysis: dict[str, Any] | None = None
    validation_receipt: dict[str, Any] | None = None
    worker_base_ref: str | None = None
    dirty_owned: list[str] = []
    dirty_unrelated: list[str] = []
    worktree_path: Path | None = None
    worktree_removed = False

    try:
        manifest = read_json(manifest_path)
        build_dir = build_dir_for_manifest(manifest, manifest_path)
        build_dir.mkdir(parents=True, exist_ok=True)
        add_check(checks, "manifest_loaded", "passed")
    except BuildError as exc:
        add_check(checks, "manifest_loaded", "failed", str(exc))
        rejections.append(str(exc))

    if not rejections:
        if args.allow_dirty_owned:
            policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
            policies = {**policies, "allow_dirty_owned": True}
            manifest = {**manifest, "policies": policies}
        manifest_result = validate_manifest(manifest)
        for warning in manifest_result["warnings"]:
            warnings.append(warning)
        if manifest_result["status"] == "passed":
            add_check(checks, "manifest_shape", "passed")
        else:
            add_check(checks, "manifest_shape", "failed", "; ".join(manifest_result["errors"]))
            rejections.extend(manifest_result["errors"])

    bundle_arg = getattr(args, "bundle", None) or getattr(args, "patch_bundle", None)
    raw_patch_arg = getattr(args, "patch", None)
    if bundle_arg:
        patch_bundle_path = Path(bundle_arg)
        if not patch_bundle_path.is_absolute():
            patch_bundle_path = ROOT / patch_bundle_path
        try:
            bundle = read_json(patch_bundle_path)
            add_check(checks, "patch_bundle_loaded", "passed", rel(patch_bundle_path))
            patch_path = resolve_bundle_patch_path(bundle, patch_bundle_path)
            worker_base_ref = str(bundle.get("base_ref") or "") or None
        except BuildError as exc:
            add_check(checks, "patch_bundle_loaded", "failed", str(exc))
            rejections.append(str(exc))
    elif raw_patch_arg:
        patch_path = Path(raw_patch_arg)
        if not patch_path.is_absolute():
            patch_path = ROOT / patch_path
        if not args.dev_raw_patch:
            add_check(checks, "raw_patch_policy", "failed", "use `cento build bundle synthesize` and integrate with --bundle")
            rejections.append("raw patch integration requires --dev-raw-patch or prior bundle synthesis")
        else:
            add_check(checks, "raw_patch_policy", "warning", "dev raw patch integration")
            warnings.append("raw patch integrated in dev mode")
    else:
        add_check(checks, "patch_source", "failed", "provide --bundle patch_bundle.json")
        rejections.append("provide --bundle patch_bundle.json")

    if patch_path is not None:
        if not patch_path.exists():
            add_check(checks, "patch_loaded", "failed", f"patch file not found: {patch_path}")
            rejections.append(f"patch file not found: {patch_path}")
        else:
            add_check(checks, "patch_loaded", "passed", rel(patch_path))
            analysis = analyze_patch(patch_path)
            touched_paths = [str(path) for path in analysis.get("paths") or []]
            if analysis.get("path_errors"):
                add_check(checks, "patch_path_parse", "failed", "; ".join([str(item) for item in analysis["path_errors"]]))
            else:
                add_check(checks, "patch_path_parse", "passed", ", ".join(touched_paths) if touched_paths else "no paths")

    write_paths = manifest_write_paths(manifest) if manifest.get("scope") else []
    protected_paths = manifest_protected_paths(manifest) if manifest.get("scope") else DEFAULT_PROTECTED_PATHS
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}

    if touched_paths:
        unowned_paths = [path for path in touched_paths if not path_allowed(path, write_paths)]
        protected_touched = [path for path in touched_paths if path_is_protected(path, protected_paths)]
        if unowned_paths:
            add_check(checks, "owned_path_check", "failed", ", ".join(unowned_paths))
            rejections.append("unowned paths touched: " + ", ".join(unowned_paths))
        else:
            add_check(checks, "owned_path_check", "passed")
        if protected_touched:
            add_check(checks, "protected_path_check", "failed", ", ".join(protected_touched))
            rejections.append("protected paths touched: " + ", ".join(protected_touched))
        else:
            add_check(checks, "protected_path_check", "passed")
    elif patch_path is not None and patch_path.exists():
        add_check(checks, "owned_path_check", "failed", "patch has no touched paths")
        rejections.append("patch has no touched paths")

    if analysis is not None:
        add_rejections(checks, rejections, "hostile_patch_check", patch_policy_rejections(analysis, write_paths, protected_paths, policies))

    if bundle is not None and patch_bundle_path is not None:
        try:
            bundle_result = validate_patch_bundle(bundle, manifest, patch_bundle_path, analysis)
        except BuildError as exc:
            bundle_result = {"status": "failed", "errors": [str(exc)], "warnings": []}
        warnings.extend([str(warning) for warning in bundle_result.get("warnings") or []])
        add_rejections(checks, rejections, "patch_bundle_contract", [str(error) for error in bundle_result.get("errors") or []])
    elif args.dev_raw_patch and patch_path is not None and analysis is not None and not rejections:
        patch_bundle_path = synthesize_patch_bundle(
            manifest,
            patch_path,
            touched_paths,
            build_dir,
            summary="Synthesized during explicit dev raw-patch integration.",
        )
        add_check(checks, "patch_bundle_contract", "warning", f"synthesized {rel(patch_bundle_path)}")

    if write_paths:
        try:
            dirty_owned, dirty_unrelated = dirty_paths_for(write_paths)
        except BuildError as exc:
            add_check(checks, "dirty_owned_check", "warning", str(exc))
            warnings.append(str(exc))
        else:
            if dirty_unrelated:
                add_check(checks, "dirty_unrelated_check", "passed", f"{len(dirty_unrelated)} unrelated dirty path(s) preserved")
            else:
                add_check(checks, "dirty_unrelated_check", "passed")
            if dirty_owned and not policy_allows_dirty_owned(policies):
                add_check(checks, "dirty_owned_check", "failed", ", ".join(dirty_owned))
                message = "dirty owned paths present: " + ", ".join(dirty_owned)
                if message not in rejections:
                    rejections.append(message)
            elif dirty_owned:
                add_check(checks, "dirty_owned_check", "warning", ", ".join(dirty_owned))
                warnings.append("dirty owned paths present (allow_dirty_owned): " + ", ".join(dirty_owned))
            else:
                add_check(checks, "dirty_owned_check", "passed")

    if patch_path is not None:
        worker_artifact_path = patch_path.parent / "worker_artifact.json"
        try:
            worker_artifact = load_optional_json(worker_artifact_path)
        except BuildError as exc:
            worker_artifact = None
            add_check(checks, "worker_artifact_loaded", "failed", str(exc))
            rejections.append(str(exc))
        if worker_artifact:
            add_check(checks, "worker_artifact_loaded", "passed", rel(worker_artifact_path))
            append_event(build_dir, "worker_artifact_received", {"path": rel(worker_artifact_path)})
            worker_result = validate_worker_artifact(
                worker_artifact,
                manifest,
                allow_head_base=args.dev_raw_patch or fixture_or_dev_path(manifest_path),
            )
            worker_base_ref = str(worker_artifact.get("base_ref") or worker_base_ref or "") or None
            add_rejections(checks, rejections, "worker_artifact_contract", [str(error) for error in worker_result.get("errors") or []])
        else:
            add_check(checks, "worker_artifact_loaded", "warning", "worker_artifact.json not found next to patch")

    source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    expected_base = str(source.get("base_ref") or "HEAD")
    current_base = git_value(["rev-parse", "HEAD"], "HEAD")
    allow_head_manifest = args.dev_raw_patch or fixture_or_dev_path(manifest_path)
    base_match = args.allow_base_mismatch or base_ref_matches(expected_base, current_base, allow_head=allow_head_manifest)
    if not base_match:
        add_check(checks, "base_ref_check", "failed", f"manifest={expected_base} current={current_base}")
        rejections.append("base ref mismatch")
    else:
        status = "warning" if args.allow_base_mismatch or expected_base == "HEAD" else "passed"
        add_check(checks, "base_ref_check", status, f"manifest={expected_base} current={current_base}")

    if worker_base_ref:
        allow_head_worker = args.dev_raw_patch or fixture_or_dev_path(manifest_path) or fixture_or_dev_path(patch_bundle_path)
        worker_base_match = base_ref_matches(worker_base_ref, expected_base, allow_head=allow_head_worker)
        if not worker_base_match:
            add_check(checks, "worker_base_ref_check", "failed", f"worker={worker_base_ref} manifest={expected_base}")
            rejections.append("worker base ref mismatch")
        else:
            add_check(checks, "worker_base_ref_check", "passed", f"worker={worker_base_ref} manifest={expected_base}")

    integration_mode = "isolated_worktree" if args.worktree else "current_worktree_check"
    validation_cwd = ROOT
    if not rejections and patch_path is not None:
        if args.worktree:
            worktree_base = current_base if expected_base == "HEAD" else expected_base
            worktree_path, worktree_result = create_isolated_worktree(worktree_base, str(manifest.get("id") or "build"))
            if worktree_path is None:
                detail = (str(worktree_result["stderr"]) or str(worktree_result["stdout"])).strip()
                add_check(checks, "worktree_create", "failed", detail)
                rejections.append("isolated worktree creation failed")
            else:
                add_check(checks, "worktree_create", "passed", rel(worktree_path))
                apply_check = run(["git", "apply", "--check", str(patch_path)], cwd=worktree_path, timeout=120)
                if apply_check["exit_code"] != 0:
                    detail = (str(apply_check["stderr"]) or str(apply_check["stdout"])).strip()
                    add_check(checks, "git_apply_check", "failed", detail)
                    rejections.append("git apply --check failed")
                else:
                    add_check(checks, "git_apply_check", "passed")
                    apply_result = run(["git", "apply", str(patch_path)], cwd=worktree_path, timeout=120)
                    if apply_result["exit_code"] != 0:
                        detail = (str(apply_result["stderr"]) or str(apply_result["stdout"])).strip()
                        add_check(checks, "worktree_patch_apply", "failed", detail)
                        rejections.append("isolated worktree patch apply failed")
                    else:
                        add_check(checks, "worktree_patch_apply", "passed")
                        validation_cwd = worktree_path
        else:
            apply_result = run(["git", "apply", "--check", str(patch_path)], timeout=120)
            if apply_result["exit_code"] == 0:
                add_check(checks, "git_apply_check", "passed")
            else:
                detail = (str(apply_result["stderr"]) or str(apply_result["stdout"])).strip()
                add_check(checks, "git_apply_check", "failed", detail)
                rejections.append("git apply --check failed")
    else:
        add_check(checks, "git_apply_check", "skipped", "pre-checks failed")

    if not rejections:
        validation_receipt = run_validation_receipt(manifest, build_dir, cwd=validation_cwd)
        if validation_receipt["status"] == "passed":
            add_check(checks, "validation_receipt", "passed", rel(build_dir / "validation_receipt.json"))
        else:
            add_check(checks, "validation_receipt", "failed", rel(build_dir / "validation_receipt.json"))
            rejections.append("validation failed")
    else:
        validation_receipt = run_validation_receipt(manifest, build_dir, skipped=True, reason="integration pre-checks failed")
        add_check(checks, "validation_receipt", "skipped", rel(build_dir / "validation_receipt.json"))

    remove_result = remove_isolated_worktree(worktree_path)
    if remove_result is not None:
        worktree_removed = remove_result["exit_code"] == 0
        if not worktree_removed:
            warnings.append("isolated worktree cleanup failed: " + (str(remove_result["stderr"]) or str(remove_result["stdout"])).strip())

    status = "accepted" if not rejections else "rejected"
    risk_overrides = []
    if getattr(args, "allow_dirty_owned", False):
        risk_overrides.append("allow_dirty_owned")
    if getattr(args, "allow_base_mismatch", False):
        risk_overrides.append("allow_base_mismatch")
    if getattr(args, "dev_raw_patch", False):
        risk_overrides.append("dev_raw_patch")
    receipt = {
        "schema_version": SCHEMA_INTEGRATION_RECEIPT,
        "manifest_id": manifest.get("id"),
        "status": status,
        "mode": manifest.get("mode"),
        "integration_mode": integration_mode,
        "patch_bundle": rel(patch_bundle_path) if patch_bundle_path else None,
        "patch_bundle_id": str(bundle.get("id") or "") if bundle else None,
        "patch_path": rel(patch_path) if patch_path else None,
        "touched_paths": touched_paths,
        "checks": checks,
        "applied": False,
        "dry_run": True,
        "rejections": rejections,
        "warnings": warnings,
        "risk_overrides": risk_overrides,
        "dirty_owned_paths": dirty_owned,
        "dirty_unrelated_paths": dirty_unrelated,
        "base_ref_manifest": expected_base,
        "base_ref_worker": worker_base_ref,
        "base_ref_current": current_base,
        "base_ref_match": base_match and (not worker_base_ref or base_ref_matches(worker_base_ref, expected_base, allow_head=args.dev_raw_patch or fixture_or_dev_path(manifest_path))),
        "worktree_path": rel(worktree_path) if worktree_path else None,
        "worktree_removed": worktree_removed if worktree_path else None,
        "validation_receipt": rel(build_dir / "validation_receipt.json") if validation_receipt else None,
        "written_at": now_iso(),
    }
    receipt_path = write_integration_receipt(build_dir, receipt)
    event_name = "integration_dry_run_passed" if status == "accepted" else "integration_dry_run_rejected"
    append_event(build_dir, event_name, {"status": status, "patch_path": rel(patch_path) if patch_path else None, "rejections": rejections})
    append_event(build_dir, "integration_dry_run_completed", {"status": status, "patch_path": rel(patch_path) if patch_path else None, "rejections": rejections})
    append_event(build_dir, "build_completed", {"status": status})
    print(rel(receipt_path))
    if status != "accepted":
        for rejection in rejections:
            print(f"rejected: {rejection}", file=sys.stderr)
    return 0 if status == "accepted" else 1


def command_worker_run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    try:
        result = run_build_worker(
            manifest_path,
            worker_id=args.worker,
            runtime=args.runtime,
            use_worktree=args.worktree,
            timeout=args.timeout,
            allow_dirty_owned=args.allow_dirty_owned,
            fixture_case=args.fixture_case,
            command_template=args.command,
            runtime_profile_name=args.runtime_profile,
            allow_unsafe_command=args.allow_unsafe_command,
        )
    except BuildError as exc:
        print(f"cento build worker run: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["worker_artifact"])
        if result.get("patch_bundle"):
            print(result["patch_bundle"])
    return 0 if result["status"] == "accepted" else 1


def command_apply(args: argparse.Namespace) -> int:
    try:
        receipt = apply_build_bundle(
            Path(args.manifest),
            Path(args.bundle),
            Path(args.from_receipt),
            allow_dirty_owned=args.allow_dirty_owned,
            allow_base_mismatch=args.allow_base_mismatch,
        )
    except BuildError as exc:
        print(f"cento build apply: {exc}", file=sys.stderr)
        return 1
    receipt_path = build_dir_for_manifest(read_json(resolved_repo_path(Path(args.manifest))), resolved_repo_path(Path(args.manifest))) / "apply_receipt.json"
    if args.json:
        print(json.dumps({"status": receipt["status"], "apply_receipt": rel(receipt_path), "applied": receipt["applied"]}, indent=2))
    else:
        print(rel(receipt_path))
        for rejection in receipt.get("rejections") or []:
            print(f"rejected: {rejection}", file=sys.stderr)
    return 0 if receipt["status"] == "applied" else 1


def command_artifact_check(args: argparse.Namespace) -> int:
    artifact_path = Path(args.artifact)
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path

    try:
        artifact = read_json(artifact_path)
    except BuildError as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1

    manifest: dict[str, Any] | None = None
    errors: list[str] = []
    warnings: list[str] = []
    manifest_arg = args.manifest or artifact.get("manifest_path")
    manifest_path: Path | None = None
    if manifest_arg:
        manifest_path = Path(str(manifest_arg))
        if not manifest_path.is_absolute():
            manifest_path = ROOT / manifest_path
        try:
            manifest = read_json(manifest_path)
        except BuildError as exc:
            errors.append(f"manifest load failed: {exc}")
            manifest = None
    else:
        warnings.append("no manifest provided; ownership checks are limited")

    if manifest is not None:
        result = validate_worker_artifact(
            artifact,
            manifest,
            allow_head_base=fixture_or_dev_path(manifest_path) or fixture_or_dev_path(artifact_path),
        )
    else:
        result = validate_worker_artifact(artifact, None)
    errors.extend([str(error) for error in result["errors"]])
    warnings.extend([str(warning) for warning in result["warnings"]])
    unowned = [str(path) for path in artifact.get("unowned_paths") or []]
    if unowned:
        errors.append("unowned paths in artifact: " + ", ".join(unowned))

    status = "passed" if not errors else "failed"
    result = {
        "status": status,
        "artifact": rel(artifact_path),
        "manifest": rel(manifest_path) if manifest_path else None,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"artifact check: {status}")
        for err in errors:
            print(f"  error: {err}", file=sys.stderr)
        for warn in warnings:
            print(f"  warning: {warn}")
    return 0 if not errors else 1


def command_bundle_synthesize(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    patch_path = Path(args.patch)
    if not patch_path.is_absolute():
        patch_path = ROOT / patch_path

    try:
        manifest = read_json(manifest_path)
    except BuildError as exc:
        print(f"cento build bundle synthesize: {exc}", file=sys.stderr)
        return 1

    try:
        analysis = analyze_patch(patch_path)
    except BuildError as exc:
        print(f"cento build bundle synthesize: {exc}", file=sys.stderr)
        return 1
    touched_paths = [str(path) for path in analysis.get("paths") or []]
    write_paths = manifest_write_paths(manifest)
    protected_paths = manifest_protected_paths(manifest)
    policies = manifest.get("policies") if isinstance(manifest.get("policies"), dict) else {}
    errors = []
    errors.extend(patch_policy_rejections(analysis, write_paths, protected_paths, policies))
    unowned_paths = [path for path in touched_paths if not path_allowed(path, write_paths)]
    protected_touched = [path for path in touched_paths if path_is_protected(path, protected_paths)]
    if unowned_paths:
        errors.append("patch touches unowned paths: " + ", ".join(unowned_paths))
    if protected_touched:
        errors.append("patch touches protected paths: " + ", ".join(protected_touched))
    if errors:
        for error in errors:
            print(f"cento build bundle synthesize: {error}", file=sys.stderr)
        return 1

    build_dir = build_dir_for_manifest(manifest, manifest_path)
    out_path = Path(args.out) if args.out else None
    if out_path is not None and not out_path.is_absolute():
        out_path = ROOT / out_path
    bundle_path = synthesize_patch_bundle(manifest, patch_path, touched_paths, build_dir, out_path=out_path)
    if args.json:
        print(json.dumps({"bundle": rel(bundle_path), "touched_paths": touched_paths}, indent=2))
    else:
        print(rel(bundle_path))
    return 0


def command_receipt(args: argparse.Namespace) -> int:
    target = Path(args.build)
    if not target.is_absolute():
        target = ROOT / target
    if target.is_file():
        manifest = read_json(target)
        build_dir = build_dir_for_manifest(manifest, target)
    else:
        build_dir = target
    manifest_path = build_dir / "manifest.json"
    integration_path = build_dir / "integration_receipt.json"
    validation_path = build_dir / "validation_receipt.json"
    apply_path = build_dir / "apply_receipt.json"
    evidence_path = build_dir / "taskstream_evidence.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    integration = read_json(integration_path) if integration_path.exists() else {}
    validation = read_json(validation_path) if validation_path.exists() else {}
    apply_receipt = read_json(apply_path) if apply_path.exists() else {}
    evidence = read_json(evidence_path) if evidence_path.exists() else {}
    payload = {
        "build_id": manifest.get("id") or build_dir.name,
        "build_dir": rel(build_dir),
        "manifest": rel(manifest_path) if manifest_path.exists() else None,
        "integration_receipt": rel(integration_path) if integration_path.exists() else None,
        "validation_receipt": rel(validation_path) if validation_path.exists() else None,
        "apply_receipt": rel(apply_path) if apply_path.exists() else None,
        "taskstream_evidence": rel(evidence_path) if evidence_path.exists() else None,
        "status": integration.get("status", "pending"),
        "integration": integration,
        "validation": validation,
        "apply": apply_receipt,
        "evidence": evidence,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"build: {payload['build_id']}")
        print(f"status: {payload['status']}")
        if payload["integration_receipt"]:
            print(f"integration_receipt: {payload['integration_receipt']}")
        if payload["validation_receipt"]:
            print(f"validation_receipt: {payload['validation_receipt']}")
        if payload["apply_receipt"]:
            print(f"apply_receipt: {payload['apply_receipt']}")
        if payload["taskstream_evidence"]:
            print(f"taskstream_evidence: {payload['taskstream_evidence']}")
        for rejection in integration.get("rejections") or []:
            print(f"rejection: {rejection}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    modes = sorted(load_modes())
    parser = argparse.ArgumentParser(
        prog="cento build",
        description="Create and dry-run integrate manifest-owned local build packages.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create a build manifest and Builder prompt.")
    init.add_argument("--task", required=True, help="Operator task title.")
    init.add_argument("--description", help="Longer task description.")
    init.add_argument("--mode", default="fast", choices=modes, help="Execution mode to copy into the manifest.")
    init.add_argument("--write", action="append", required=True, help="Owned writable path. Repeatable.")
    init.add_argument("--read", action="append", default=[], help="Read-only path. Repeatable.")
    init.add_argument("--route", action="append", default=[], help="Target route or URL. Repeatable.")
    init.add_argument("--protect", action="append", default=[], help="Protected path glob. Repeatable.")
    init.add_argument("--validation", help="Override validation tier.")
    init.add_argument("--id", help="Deterministic build id.")
    init.add_argument("--allow-dirty-owned", action="store_true", help="Record that dirty owned paths are allowed.")
    init.add_argument("--force", action="store_true", help="Overwrite existing manifest and prompt for the build id.")
    init.add_argument("--json", action="store_true", help="Print JSON result.")
    init.set_defaults(func=command_init)

    check = sub.add_parser("check", help="Validate manifest shape and local path policy.")
    check.add_argument("manifest", help="Manifest JSON path.")
    check.add_argument("--json", action="store_true", help="Print JSON result.")
    check.set_defaults(func=command_check)

    prompt = sub.add_parser("prompt", help="Print or rewrite the Builder prompt for a manifest.")
    prompt.add_argument("manifest", help="Manifest JSON path.")
    prompt.add_argument("--write", action="store_true", help="Write builder.prompt.md beside the build manifest.")
    prompt.add_argument("--out", help="Write prompt to a specific path.")
    prompt.set_defaults(func=command_prompt)

    integrate = sub.add_parser("integrate", help="Dry-run integrate a patch bundle against manifest-owned paths.")
    integrate.add_argument("manifest", help="Manifest JSON path.")
    integrate.add_argument("--bundle", help="patch_bundle.json path.")
    integrate.add_argument("--patch-bundle", help="Backward-compatible alias for --bundle.")
    integrate.add_argument("--patch", help="Raw patch diff path; rejected unless --dev-raw-patch is set.")
    integrate.add_argument("--dry-run", action="store_true", help="Document intent; v1 is always dry-run.")
    integrate.add_argument("--worktree", action="store_true", help="Run apply and validation in an isolated clean git worktree.")
    integrate.add_argument("--apply", action="store_true", help="Reserved for a future non-dry-run integrator.")
    integrate.add_argument("--allow-base-mismatch", action="store_true", help="Do not reject when manifest base_ref differs from HEAD.")
    integrate.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths; recorded as a risk override in the receipt.")
    integrate.add_argument("--dev-raw-patch", action="store_true", help="Local fixture/dev escape hatch for raw --patch integration.")
    integrate.set_defaults(func=command_integrate)

    worker = sub.add_parser("worker", help="Run or inspect a local build worker.")
    worker_sub = worker.add_subparsers(dest="worker_command", required=True)
    worker_run = worker_sub.add_parser("run", help="Run one local worker and collect patch artifacts.")
    worker_run.add_argument("manifest", help="Manifest JSON path.")
    worker_run.add_argument("--worker", default="builder_1", help="Worker id from the manifest.")
    worker_run.add_argument("--runtime", default="fixture", help="Worker runtime adapter, e.g. fixture or command.")
    worker_run.add_argument("--runtime-profile", help="Named runtime profile from .cento/runtimes.yaml.")
    worker_run.add_argument("--fixture-case", default="valid", choices=["valid", "unowned", "protected", "delete", "lockfile", "binary"], help="Deterministic fixture case for --runtime fixture.")
    worker_run.add_argument("--command", help="Command template for --runtime command; supports {manifest}, {prompt}, {build_dir}, {worker_dir}, {worktree}, {worker}, {artifact_dir}.")
    worker_run.add_argument("--worktree", action="store_true", help="Run the worker in an isolated git worktree.")
    worker_run.add_argument("--timeout", type=int, default=None, help="Worker timeout in seconds; runtime profiles can provide the default.")
    worker_run.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths before worker launch.")
    worker_run.add_argument("--allow-unsafe-command", action="store_true", help="Allow raw shell command runtime without a named profile.")
    worker_run.add_argument("--json", action="store_true", help="Print JSON result.")
    worker_run.set_defaults(func=command_worker_run)

    apply_cmd = sub.add_parser("apply", help="Apply an accepted patch bundle to the operator worktree.")
    apply_cmd.add_argument("manifest", help="Manifest JSON path.")
    apply_cmd.add_argument("--bundle", required=True, help="patch_bundle.json path.")
    apply_cmd.add_argument("--from-receipt", required=True, help="Accepted integration_receipt.json path.")
    apply_cmd.add_argument("--allow-dirty-owned", action="store_true", help="Allow dirty owned paths; recorded as a risk override.")
    apply_cmd.add_argument("--allow-base-mismatch", action="store_true", help="Apply even if manifest base_ref differs from HEAD.")
    apply_cmd.add_argument("--json", action="store_true", help="Print JSON result.")
    apply_cmd.set_defaults(func=command_apply)

    artifact = sub.add_parser("artifact", help="Check or inspect a worker artifact.")
    artifact_sub = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_check = artifact_sub.add_parser("check", help="Validate a worker_artifact.json against schema and optional manifest.")
    artifact_check.add_argument("artifact", help="worker_artifact.json path.")
    artifact_check.add_argument("--manifest", help="Optional manifest JSON path to cross-check ownership and base ref.")
    artifact_check.add_argument("--json", action="store_true", help="Print JSON result.")
    artifact_check.set_defaults(func=command_artifact_check)

    bundle = sub.add_parser("bundle", help="Synthesize or inspect patch bundles.")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    bundle_synth = bundle_sub.add_parser("synthesize", help="Synthesize a patch_bundle.json from a manifest and raw patch file.")
    bundle_synth.add_argument("--manifest", required=True, help="Manifest JSON path.")
    bundle_synth.add_argument("--patch", required=True, help="Patch diff path.")
    bundle_synth.add_argument("--out", help="Write the patch bundle to a specific path.")
    bundle_synth.add_argument("--json", action="store_true", help="Print JSON result.")
    bundle_synth.set_defaults(func=command_bundle_synthesize)

    receipt = sub.add_parser("receipt", help="Print the latest build receipt.")
    receipt.add_argument("build", help="Build directory or manifest path.")
    receipt.add_argument("--json", action="store_true", help="Print JSON result.")
    receipt.set_defaults(func=command_receipt)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BuildError as exc:
        print(f"cento build: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
