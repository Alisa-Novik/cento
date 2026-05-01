#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse, unquote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
VALID_ROLES = {"builder", "validator", "coordinator", "docs-evidence"}
VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
ALLOWED_STATES = {"pass", "fail", "escalate"}


class ManifestValidationError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestValidationError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(f"invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestValidationError(f"{label} must be a JSON object")
    return value


def ensure_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ManifestValidationError(f"{label} must be a JSON array")
    return value


def text_value(value: Any) -> str:
    return str(value or "").strip()


def format_value(value: str, context: dict[str, str]) -> str:
    text = str(value or "")
    root = context.get("root") or ""
    if root:
        if text.startswith("file:///{root}/"):
            text = "file://" + root + "/" + text[len("file:///{root}/") :]
        elif text.startswith("file:///{root}"):
            text = "file://" + root + text[len("file:///{root}") :]
    for token in ("<issue-id>", "<story-dir>", "<validation-dir>", "<run-dir>"):
        replacement = context.get(token)
        if replacement is not None:
            text = text.replace(token, replacement)
    return text


def resolve_path(value: str, *, base_dir: Path, context: dict[str, str]) -> Path:
    formatted = format_value(value, context).strip()
    if not formatted:
        raise ManifestValidationError("path is missing")
    if formatted.startswith("file://"):
        parsed = urlparse(formatted)
        raw_path = unquote(parsed.path or "")
        if parsed.netloc and parsed.netloc not in {"", "localhost"}:
            raw_path = f"/{parsed.netloc}{raw_path}"
        return Path(raw_path or "/")
    path = Path(formatted).expanduser()
    if path.is_absolute():
        return path
    candidate = (base_dir / path).expanduser()
    if candidate.exists():
        return candidate
    return (ROOT / path).expanduser()


def field_value(data: Any, field: str) -> tuple[bool, Any]:
    cursor = data
    for part in field.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
            continue
        if isinstance(cursor, list) and part.isdigit():
            index = int(part)
            if 0 <= index < len(cursor):
                cursor = cursor[index]
                continue
            return False, None
        return False, None
    return True, cursor


def normalize_command(command: Any) -> tuple[str, bool]:
    if isinstance(command, str):
        return command.strip(), True
    if isinstance(command, list) and command and all(isinstance(item, str) for item in command):
        return shlex.join(command), False
    raise ManifestValidationError("command must be a string or a non-empty string list")


def markdown_escape(value: Any) -> str:
    return text_value(value).replace("|", "\\|").replace("\n", " ")


def make_check(
    name: str,
    check_type: str,
    status: str,
    reason: str,
    *,
    evidence: str = "",
    observed: dict[str, Any] | None = None,
    command: str = "",
    path: str = "",
    url: str = "",
    required: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "type": check_type,
        "status": status,
        "reason": reason,
        "required": required,
    }
    if evidence:
        payload["evidence"] = evidence
    if observed is not None:
        payload["observed"] = observed
    if command:
        payload["command"] = command
    if path:
        payload["path"] = path
    if url:
        payload["url"] = url
    return payload


def load_story(path: Path) -> dict[str, Any]:
    return ensure_dict(read_json(path), "story manifest")


def load_validation(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return ensure_dict(read_json(path), "validation manifest")


def default_validation_path(story: dict[str, Any], story_path: Path) -> Path | None:
    validation = story.get("validation")
    if isinstance(validation, dict):
        manifest = text_value(validation.get("manifest"))
        if manifest:
            return resolve_path(manifest, base_dir=story_path.parent, context={"root": str(ROOT)})
    candidate = story_path.parent / "validation.json"
    return candidate if candidate.exists() else None


def story_context(story: dict[str, Any], story_path: Path, validation_path: Path | None) -> dict[str, str]:
    issue = story.get("issue") or {}
    paths = story.get("paths") or {}
    run_dir = text_value(paths.get("run_dir")) or str(story_path.parent)
    context = {
        "root": str(ROOT),
        "<issue-id>": str(issue.get("id") or ""),
        "<story-dir>": str(story_path.parent),
        "<validation-dir>": str(validation_path.parent if validation_path else story_path.parent),
        "<run-dir>": run_dir,
    }
    return context


def validate_story_structure(story: dict[str, Any], *, story_path: Path, context: dict[str, str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    escalations: list[str] = []

    schema = text_value(story.get("schema_version"))
    if schema:
        checks.append(make_check("story.schema_version", "field", "pass", "present", observed={"value": schema}, evidence=rel(story_path)))
    else:
        missing.append("story.schema_version")
        escalations.append("story schema_version is missing")
        checks.append(make_check("story.schema_version", "field", "escalate", "missing", observed={"value": ""}, evidence=rel(story_path)))

    issue = ensure_dict(story.get("issue"), "story.issue") if isinstance(story.get("issue"), dict) else {}
    issue_id = issue.get("id")
    if isinstance(issue_id, int):
        checks.append(make_check("story.issue.id", "field", "pass", "present", observed={"value": issue_id}, evidence=rel(story_path)))
    else:
        missing.append("story.issue.id")
        escalations.append("story.issue.id must be an integer")
        checks.append(make_check("story.issue.id", "field", "escalate", "missing or invalid", observed={"value": issue_id}, evidence=rel(story_path)))

    for field in ("title", "package"):
        value = text_value(issue.get(field))
        if value:
            checks.append(make_check(f"story.issue.{field}", "field", "pass", "present", observed={"value": value}, evidence=rel(story_path)))
        else:
            missing.append(f"story.issue.{field}")
            escalations.append(f"story.issue.{field} is missing")
            checks.append(make_check(f"story.issue.{field}", "field", "escalate", "missing", observed={"value": ""}, evidence=rel(story_path)))

    lane = ensure_dict(story.get("lane"), "story.lane") if isinstance(story.get("lane"), dict) else {}
    for field in ("owner", "role", "node"):
        value = text_value(lane.get(field))
        if value:
            checks.append(make_check(f"story.lane.{field}", "field", "pass", "present", observed={"value": value}, evidence=rel(story_path)))
        else:
            missing.append(f"story.lane.{field}")
            escalations.append(f"story.lane.{field} is missing")
            checks.append(make_check(f"story.lane.{field}", "field", "escalate", "missing", observed={"value": ""}, evidence=rel(story_path)))

    role = text_value(lane.get("role"))
    if role and role not in VALID_ROLES:
        escalations.append(f"story.lane.role must be one of {', '.join(sorted(VALID_ROLES))}: {role}")
        checks.append(make_check("story.lane.role", "field", "escalate", "invalid lane role", observed={"value": role}, evidence=rel(story_path)))
    elif role:
        checks.append(make_check("story.lane.role", "field", "pass", "role is valid", observed={"value": role}, evidence=rel(story_path)))

    paths = ensure_dict(story.get("paths"), "story.paths") if isinstance(story.get("paths"), dict) else {}
    run_dir_text = text_value(paths.get("run_dir"))
    if run_dir_text:
        run_dir = resolve_path(run_dir_text, base_dir=story_path.parent, context=context)
        if run_dir.exists():
            checks.append(make_check("story.paths.run_dir", "field", "pass", "run_dir exists", observed={"value": run_dir_text}, evidence=rel(run_dir)))
        else:
            escalations.append(f"story.paths.run_dir does not exist: {run_dir_text}")
            checks.append(make_check("story.paths.run_dir", "field", "escalate", "run_dir is missing", observed={"value": run_dir_text}, evidence=rel(run_dir)))
    else:
        missing.append("story.paths.run_dir")
        escalations.append("story.paths.run_dir is missing")
        checks.append(make_check("story.paths.run_dir", "field", "escalate", "missing", observed={"value": ""}, evidence=rel(story_path)))

    scope = ensure_dict(story.get("scope"), "story.scope") if isinstance(story.get("scope"), dict) else {}
    acceptance = scope.get("acceptance")
    if isinstance(acceptance, list) and acceptance and all(text_value(item) for item in acceptance):
        checks.append(make_check("story.scope.acceptance", "field", "pass", "acceptance list is present", observed={"count": len(acceptance)}, evidence=rel(story_path)))
    else:
        missing.append("story.scope.acceptance")
        escalations.append("story.scope.acceptance must be a non-empty array of text")
        checks.append(make_check("story.scope.acceptance", "field", "escalate", "missing or empty", observed={"value": acceptance}, evidence=rel(story_path)))

    validation = story.get("validation")
    if isinstance(validation, dict):
        mode = text_value(validation.get("mode"))
        no_model_eligible = validation.get("no_model_eligible")
        if isinstance(no_model_eligible, bool) and no_model_eligible:
            checks.append(make_check("story.validation.no_model_eligible", "field", "pass", "explicitly eligible", observed={"value": True}, evidence=rel(story_path)))
        else:
            missing.append("story.validation.no_model_eligible")
            escalations.append("story.validation.no_model_eligible is false or missing")
            checks.append(make_check("story.validation.no_model_eligible", "field", "escalate", "story is not eligible for deterministic validation", observed={"value": no_model_eligible}, evidence=rel(story_path)))
        if mode and "manual" in mode.lower():
            escalations.append(f"story.validation.mode requests manual review: {mode}")
            checks.append(make_check("story.validation.mode", "field", "escalate", "manual mode", observed={"value": mode}, evidence=rel(story_path)))
        elif mode:
            checks.append(make_check("story.validation.mode", "field", "pass", "present", observed={"value": mode}, evidence=rel(story_path)))
        commands = validation.get("commands")
        if commands is not None:
            if isinstance(commands, list) and all(text_value(item) for item in commands):
                checks.append(make_check("story.validation.commands", "field", "pass", "command list present", observed={"count": len(commands)}, evidence=rel(story_path)))
            else:
                missing.append("story.validation.commands")
                escalations.append("story.validation.commands must be a list of text commands")
                checks.append(make_check("story.validation.commands", "field", "escalate", "invalid command list", observed={"value": commands}, evidence=rel(story_path)))
    else:
        escalations.append("story.validation object is missing")
        checks.append(make_check("story.validation", "field", "escalate", "missing validation object", observed={"value": None}, evidence=rel(story_path)))

    expected_outputs = story.get("expected_outputs")
    if isinstance(expected_outputs, list) and expected_outputs:
        checks.append(make_check("story.expected_outputs", "field", "pass", "present", observed={"count": len(expected_outputs)}, evidence=rel(story_path)))
    else:
        missing.append("story.expected_outputs")
        escalations.append("story.expected_outputs must be a non-empty array")
        checks.append(make_check("story.expected_outputs", "field", "escalate", "missing or empty", observed={"value": expected_outputs}, evidence=rel(story_path)))

    return checks, missing, escalations


def validate_story_api_endpoints(story: dict[str, Any], *, story_path: Path, context: dict[str, str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    escalations: list[str] = []
    api_endpoints = story.get("api_endpoints")
    if api_endpoints is None:
        return checks, missing, escalations
    if not isinstance(api_endpoints, list):
        missing.append("story.api_endpoints")
        escalations.append("story.api_endpoints must be an array")
        checks.append(make_check("story.api_endpoints", "api_spec", "escalate", "must be an array", observed={"value": api_endpoints}, evidence=rel(story_path)))
        return checks, missing, escalations

    for index, entry in enumerate(api_endpoints):
        name = f"story.api_endpoints[{index}]"
        if isinstance(entry, str):
            url = text_value(entry)
            if not url:
                missing.append(name)
                escalations.append(f"{name} is empty")
                checks.append(make_check(name, "api_spec", "escalate", "empty string", observed={"value": entry}, evidence=rel(story_path)))
                continue
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https", "file"}:
                missing.append(name)
                escalations.append(f"{name} must use http, https, or file: {url}")
                checks.append(make_check(name, "api_spec", "escalate", "invalid URL scheme", observed={"url": url}, evidence=rel(story_path), url=url))
                continue
            checks.append(make_check(name, "api_spec", "pass", "string URL spec is valid", observed={"url": url, "method": "GET"}, evidence=rel(story_path), url=url))
            continue
        if not isinstance(entry, dict):
            missing.append(name)
            escalations.append(f"{name} must be an object or a URL string")
            checks.append(make_check(name, "api_spec", "escalate", "invalid entry type", observed={"value": entry}, evidence=rel(story_path)))
            continue
        method = text_value(entry.get("method") or "GET").upper()
        url = text_value(entry.get("url"))
        endpoint_name = text_value(entry.get("name")) or name
        if not url:
            missing.append(name)
            escalations.append(f"{name} is missing url")
            checks.append(make_check(endpoint_name, "api_spec", "escalate", "missing url", observed={"value": entry}, evidence=rel(story_path)))
            continue
        if method not in VALID_METHODS:
            missing.append(name)
            escalations.append(f"{name} has unsupported method: {method}")
            checks.append(make_check(endpoint_name, "api_spec", "escalate", "unsupported method", observed={"method": method, "url": url}, evidence=rel(story_path), url=url))
            continue
        checks.append(make_check(endpoint_name, "api_spec", "pass", "API endpoint spec is explicit", observed={"method": method, "url": url}, evidence=rel(story_path), url=url))
    return checks, missing, escalations


def validate_story_expected_outputs(story: dict[str, Any], *, story_path: Path, context: dict[str, str]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    escalations: list[str] = []
    evidence_paths: list[str] = []
    expected_outputs = story.get("expected_outputs") or []
    if not isinstance(expected_outputs, list):
        missing.append("story.expected_outputs")
        escalations.append("story.expected_outputs must be an array")
        checks.append(make_check("story.expected_outputs", "artifact", "escalate", "must be an array", observed={"value": expected_outputs}, evidence=rel(story_path)))
        return checks, missing, escalations, evidence_paths

    run_dir_text = text_value((story.get("paths") or {}).get("run_dir"))
    base_dir = resolve_path(run_dir_text, base_dir=story_path.parent, context=context) if run_dir_text else story_path.parent

    for index, entry in enumerate(expected_outputs):
        name = f"story.expected_outputs[{index}]"
        if not isinstance(entry, dict):
            missing.append(name)
            escalations.append(f"{name} must be an object")
            checks.append(make_check(name, "artifact", "escalate", "invalid entry type", observed={"value": entry}, evidence=rel(story_path)))
            continue
        path_text = text_value(entry.get("path"))
        owner = text_value(entry.get("owner"))
        description = text_value(entry.get("description"))
        required = bool(entry.get("required", True))
        if not path_text:
            missing.append(name)
            escalations.append(f"{name} is missing path")
            checks.append(make_check(name, "artifact", "escalate", "missing path", observed={"value": entry}, evidence=rel(story_path), required=required))
            continue
        resolved = resolve_path(path_text, base_dir=base_dir, context=context)
        exists = resolved.exists()
        if exists and (not required or resolved.stat().st_size > 0 or resolved.is_dir()):
            evidence_paths.append(rel(resolved))
            checks.append(
                make_check(
                    name,
                    "artifact",
                    "pass",
                    "expected output exists",
                    evidence=rel(resolved),
                    observed={"owner": owner, "description": description, "required": required, "exists": True},
                    path=path_text,
                    required=required,
                )
            )
            continue
        if required:
            missing.append(path_text)
            checks.append(
                make_check(
                    name,
                    "artifact",
                    "fail",
                    "required output is missing",
                    observed={"owner": owner, "description": description, "required": required, "exists": False},
                    path=path_text,
                    required=required,
                )
            )
        else:
            checks.append(
                make_check(
                    name,
                    "artifact",
                    "pass",
                    "optional output is missing",
                    observed={"owner": owner, "description": description, "required": required, "exists": False},
                    path=path_text,
                    required=required,
                )
            )
    return checks, missing, escalations, evidence_paths


def validate_story_screenshots(story: dict[str, Any], *, story_path: Path, context: dict[str, str]) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    escalations: list[str] = []
    evidence_paths: list[str] = []
    screenshots = story.get("screenshots")
    if screenshots is None:
        return checks, missing, escalations, evidence_paths
    if not isinstance(screenshots, list):
        missing.append("story.screenshots")
        escalations.append("story.screenshots must be an array")
        checks.append(make_check("story.screenshots", "screenshot", "escalate", "must be an array", observed={"value": screenshots}, evidence=rel(story_path)))
        return checks, missing, escalations, evidence_paths

    run_dir_text = text_value((story.get("paths") or {}).get("run_dir"))
    base_dir = resolve_path(run_dir_text, base_dir=story_path.parent, context=context) if run_dir_text else story_path.parent
    for index, entry in enumerate(screenshots):
        name = f"story.screenshots[{index}]"
        if not isinstance(entry, dict):
            missing.append(name)
            escalations.append(f"{name} must be an object")
            checks.append(make_check(name, "screenshot", "escalate", "invalid entry type", observed={"value": entry}, evidence=rel(story_path)))
            continue
        output_text = text_value(entry.get("output") or entry.get("path"))
        viewport = text_value(entry.get("viewport"))
        url = text_value(entry.get("url"))
        if not output_text:
            missing.append(name)
            escalations.append(f"{name} is missing output path")
            checks.append(make_check(name, "screenshot", "escalate", "missing output path", observed={"value": entry}, evidence=rel(story_path), url=url))
            continue
        resolved = resolve_path(output_text, base_dir=base_dir, context=context)
        if resolved.exists() and (resolved.is_dir() or resolved.stat().st_size > 0):
            evidence_paths.append(rel(resolved))
            checks.append(
                make_check(
                    name,
                    "screenshot",
                    "pass",
                    "screenshot evidence exists",
                    evidence=rel(resolved),
                    observed={"output": output_text, "viewport": viewport, "url": url, "exists": True},
                    path=output_text,
                    url=url,
                )
            )
        else:
            missing.append(output_text)
            checks.append(
                make_check(
                    name,
                    "screenshot",
                    "fail",
                    "screenshot evidence is missing",
                    observed={"output": output_text, "viewport": viewport, "url": url, "exists": False},
                    path=output_text,
                    url=url,
                )
            )
    return checks, missing, escalations, evidence_paths


def validate_validation_manifest(
    *,
    story: dict[str, Any],
    story_path: Path,
    validation: dict[str, Any],
    validation_path: Path | None,
    context: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    escalations: list[str] = []
    failed_commands: list[str] = []
    evidence_paths: list[str] = []

    if validation_path is not None and not validation_path.exists():
        escalations.append(f"validation manifest not found: {validation_path}")
        checks.append(make_check("validation.manifest", "manifest", "escalate", "validation manifest is missing", observed={"path": rel(validation_path)}, evidence=rel(validation_path)))
        return checks, missing, escalations, failed_commands, evidence_paths

    checks_value = validation.get("checks")
    command_checks: list[dict[str, Any]] = []
    if isinstance(checks_value, list) and checks_value:
        for index, raw_check in enumerate(checks_value):
            if not isinstance(raw_check, dict):
                missing.append(f"validation.checks[{index}]")
                escalations.append(f"validation.checks[{index}] must be an object")
                checks.append(make_check(f"validation.checks[{index}]", "manifest", "escalate", "invalid check entry", observed={"value": raw_check}))
                continue
            command_checks.append(raw_check)
    else:
        story_validation = ensure_dict(story.get("validation"), "story.validation") if isinstance(story.get("validation"), dict) else {}
        fallback_commands = validation.get("commands") if isinstance(validation.get("commands"), list) else story_validation.get("commands")
        if isinstance(fallback_commands, list) and fallback_commands:
            for index, raw_command in enumerate(fallback_commands):
                if isinstance(raw_command, dict):
                    command_checks.append(raw_command)
                elif isinstance(raw_command, str) and raw_command.strip():
                    command_checks.append({"name": f"validation.command[{index}]", "type": "command", "command": raw_command})
                else:
                    missing.append(f"validation.commands[{index}]")
                    escalations.append(f"validation.commands[{index}] must be text or a command object")
                    checks.append(make_check(f"validation.commands[{index}]", "manifest", "escalate", "invalid command entry", observed={"value": raw_command}))
        elif validation_path is None:
            escalations.append("no validation manifest provided; using story structure checks only")
        else:
            escalations.append("validation manifest does not define checks or commands")

    story_validation = ensure_dict(story.get("validation"), "story.validation") if isinstance(story.get("validation"), dict) else {}
    allowed_commands = validation.get("allowed_commands")
    if not isinstance(allowed_commands, list) or not allowed_commands:
        allowed_commands = story_validation.get("commands") if isinstance(story_validation.get("commands"), list) else []
    allowed_command_strings = [text_value(item) for item in allowed_commands if text_value(item)]

    required_evidence = validation.get("required_evidence")
    if isinstance(required_evidence, list):
        for index, item in enumerate(required_evidence):
            path_text = text_value(item)
            if not path_text:
                missing.append(f"validation.required_evidence[{index}]")
                escalations.append(f"validation.required_evidence[{index}] is empty")
                checks.append(make_check(f"validation.required_evidence[{index}]", "artifact", "escalate", "missing evidence path", observed={"value": item}))
                continue
            resolved = resolve_path(path_text, base_dir=validation_path.parent if validation_path else story_path.parent, context=context)
            if resolved.exists() and (resolved.is_dir() or resolved.stat().st_size > 0):
                evidence_paths.append(rel(resolved))
                checks.append(make_check(f"validation.required_evidence[{index}]", "artifact", "pass", "required evidence exists", evidence=rel(resolved), observed={"value": path_text}, path=path_text))
            else:
                missing.append(path_text)
                checks.append(make_check(f"validation.required_evidence[{index}]", "artifact", "fail", "required evidence is missing", observed={"value": path_text}, path=path_text))

    required_outputs = validation.get("required_outputs")
    if isinstance(required_outputs, list):
        for index, item in enumerate(required_outputs):
            path_text = text_value(item)
            if not path_text:
                missing.append(f"validation.required_outputs[{index}]")
                escalations.append(f"validation.required_outputs[{index}] is empty")
                checks.append(make_check(f"validation.required_outputs[{index}]", "artifact", "escalate", "missing output path", observed={"value": item}))
                continue
            resolved = resolve_path(path_text, base_dir=validation_path.parent if validation_path else story_path.parent, context=context)
            if resolved.exists() and (resolved.is_dir() or resolved.stat().st_size > 0):
                evidence_paths.append(rel(resolved))
                checks.append(make_check(f"validation.required_outputs[{index}]", "artifact", "pass", "required output exists", evidence=rel(resolved), observed={"value": path_text}, path=path_text))
            else:
                missing.append(path_text)
                checks.append(make_check(f"validation.required_outputs[{index}]", "artifact", "fail", "required output is missing", observed={"value": path_text}, path=path_text))

    for check_index, raw_check in enumerate(command_checks):
        check_type = text_value(raw_check.get("type")) or "command"
        name = text_value(raw_check.get("name")) or f"validation.checks[{check_index}]"
        check_required = bool(raw_check.get("required", True))
        if check_type in {"file", "file_exists"}:
            try:
                result = run_file_check(raw_check, name=name, story_path=story_path, validation_path=validation_path, context=context, required=check_required)
            except ManifestValidationError as exc:
                missing.append(name)
                escalations.append(str(exc))
                checks.append(make_check(name, check_type, "escalate", str(exc)))
                continue
            checks.append(result["check"])
            if result.get("evidence"):
                evidence_paths.append(result["evidence"])
            if result["status"] == "fail" and result.get("missing"):
                missing.append(result["missing"])
            continue
        if check_type == "json_field":
            try:
                result = run_json_field_check(raw_check, name=name, story_path=story_path, validation_path=validation_path, context=context)
            except ManifestValidationError as exc:
                missing.append(name)
                escalations.append(str(exc))
                checks.append(make_check(name, check_type, "escalate", str(exc)))
                continue
            checks.append(result["check"])
            if result.get("evidence"):
                evidence_paths.append(result["evidence"])
            if result["status"] == "fail" and result.get("missing"):
                missing.append(result["missing"])
            continue
        if check_type == "url":
            try:
                result = run_url_check(raw_check, name=name, story_path=story_path, validation_path=validation_path, context=context)
            except ManifestValidationError as exc:
                missing.append(name)
                escalations.append(str(exc))
                checks.append(make_check(name, check_type, "escalate", str(exc)))
                continue
            checks.append(result["check"])
            if result.get("evidence"):
                evidence_paths.append(result["evidence"])
            if result["status"] == "fail" and result.get("missing"):
                missing.append(result["missing"])
            continue
        if check_type == "screenshot":
            try:
                result = run_screenshot_check(raw_check, name=name, story_path=story_path, validation_path=validation_path, context=context)
            except ManifestValidationError as exc:
                missing.append(name)
                escalations.append(str(exc))
                checks.append(make_check(name, check_type, "escalate", str(exc)))
                continue
            checks.append(result["check"])
            if result.get("evidence"):
                evidence_paths.append(result["evidence"])
            if result["status"] == "fail" and result.get("missing"):
                missing.append(result["missing"])
            continue
        if check_type == "command":
            try:
                result = run_command_check(
                    raw_check,
                    name=name,
                    story_path=story_path,
                    validation_path=validation_path,
                    context=context,
                    allowed_commands=allowed_command_strings,
                )
            except ManifestValidationError as exc:
                missing.append(name)
                escalations.append(str(exc))
                checks.append(make_check(name, check_type, "escalate", str(exc)))
                continue
            checks.append(result["check"])
            if result.get("evidence"):
                evidence_paths.append(result["evidence"])
            if result["status"] == "fail":
                failed_commands.append(result["command"])
            elif result["status"] == "escalate":
                escalations.append(result["reason"])
            continue

        missing.append(name)
        escalations.append(f"unsupported validation check type: {check_type}")
        checks.append(make_check(name, check_type, "escalate", "unsupported check type", observed={"value": raw_check}))

    return checks, missing, escalations, failed_commands, evidence_paths


def run_file_check(
    check: dict[str, Any],
    *,
    name: str,
    story_path: Path,
    validation_path: Path | None,
    context: dict[str, str],
    required: bool = True,
) -> dict[str, Any]:
    base_dir = validation_path.parent if validation_path else story_path.parent
    path_text = text_value(check.get("path") or check.get("output") or check.get("target"))
    if not path_text:
        raise ManifestValidationError(f"{name} is missing a path")
    resolved = resolve_path(path_text, base_dir=base_dir, context=context)
    non_empty = bool(check.get("non_empty", False))
    exists = resolved.exists()
    if exists and (not non_empty or resolved.is_dir() or resolved.stat().st_size > 0):
        return {
            "status": "pass",
            "evidence": rel(resolved),
            "check": make_check(
                name,
                text_value(check.get("type")) or "file",
                "pass",
                "file exists",
                evidence=rel(resolved),
                observed={"exists": True, "non_empty": non_empty},
                path=path_text,
                required=required,
            ),
        }
    if required:
        return {
            "status": "fail",
            "missing": path_text,
            "check": make_check(
                name,
                text_value(check.get("type")) or "file",
                "fail",
                "file is missing" if not exists else "file is empty",
                observed={"exists": exists, "non_empty": non_empty},
                path=path_text,
                required=required,
            ),
        }
    return {
        "status": "pass",
        "check": make_check(
            name,
            text_value(check.get("type")) or "file",
            "pass",
            "optional file is missing",
            observed={"exists": exists, "non_empty": non_empty},
            path=path_text,
            required=required,
        ),
    }


def run_json_field_check(
    check: dict[str, Any],
    *,
    name: str,
    story_path: Path,
    validation_path: Path | None,
    context: dict[str, str],
) -> dict[str, Any]:
    base_dir = validation_path.parent if validation_path else story_path.parent
    path_text = text_value(check.get("path"))
    field = text_value(check.get("field"))
    if not path_text or not field:
        raise ManifestValidationError(f"{name} requires path and field")
    resolved = resolve_path(path_text, base_dir=base_dir, context=context)
    if not resolved.exists():
        return {
            "status": "fail",
            "missing": path_text,
            "check": make_check(name, "json_field", "fail", "JSON file is missing", observed={"exists": False, "field": field}, path=path_text),
        }
    try:
        data = read_json(resolved)
    except ManifestValidationError as exc:
        return {
            "status": "fail",
            "missing": path_text,
            "check": make_check(name, "json_field", "fail", str(exc), observed={"exists": True, "field": field}, path=path_text),
        }
    present, value = field_value(data, field)
    if not present:
        return {
            "status": "fail",
            "missing": f"{path_text}#{field}",
            "check": make_check(name, "json_field", "fail", "JSON field is missing", observed={"exists": True, "field": field}, evidence=rel(resolved), path=path_text),
        }
    if "expected" in check and value != check.get("expected"):
        return {
            "status": "fail",
            "missing": f"{path_text}#{field}",
            "check": make_check(
                name,
                "json_field",
                "fail",
                "JSON field does not match expected value",
                observed={"exists": True, "field": field, "value": value, "expected": check.get("expected")},
                evidence=rel(resolved),
                path=path_text,
            ),
        }
    return {
        "status": "pass",
        "evidence": rel(resolved),
        "check": make_check(
            name,
            "json_field",
            "pass",
            "JSON field is present",
            evidence=rel(resolved),
            observed={"exists": True, "field": field, "value": value},
            path=path_text,
        ),
    }


def run_url_check(
    check: dict[str, Any],
    *,
    name: str,
    story_path: Path,
    validation_path: Path | None,
    context: dict[str, str],
) -> dict[str, Any]:
    base_dir = validation_path.parent if validation_path else story_path.parent
    url = text_value(check.get("url"))
    if not url:
        raise ManifestValidationError(f"{name} requires url")
    expected_status = int(check.get("expected_status", 200))
    parsed = urlparse(format_value(url, context))
    if parsed.scheme == "file":
        path = resolve_path(url, base_dir=base_dir, context=context)
        if path.exists():
            return {
                "status": "pass",
                "evidence": rel(path),
                "check": make_check(name, "url", "pass", "file URL exists", observed={"url": url, "status": 200}, evidence=rel(path), url=url),
            }
        return {
            "status": "fail",
            "missing": url,
            "check": make_check(name, "url", "fail", "file URL target is missing", observed={"url": url, "status": 404}, url=url),
        }
    timeout = int(check.get("timeout_seconds", 10))
    try:
        with urlopen(format_value(url, context), timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode() or 200))
            sample = response.read(512).decode("utf-8", errors="replace")
    except (URLError, TimeoutError, ValueError) as exc:
        return {
            "status": "fail",
            "missing": url,
            "check": make_check(name, "url", "fail", str(exc), observed={"url": url, "timeout_seconds": timeout}, url=url),
        }
    if status != expected_status:
        return {
            "status": "fail",
            "missing": url,
            "check": make_check(
                name,
                "url",
                "fail",
                "unexpected status code",
                observed={"url": url, "status": status, "expected_status": expected_status, "sample": sample},
                url=url,
            ),
        }
    return {
        "status": "pass",
        "check": make_check(name, "url", "pass", "URL is reachable", observed={"url": url, "status": status, "sample": sample}, url=url),
    }


def run_screenshot_check(
    check: dict[str, Any],
    *,
    name: str,
    story_path: Path,
    validation_path: Path | None,
    context: dict[str, str],
) -> dict[str, Any]:
    base_dir = validation_path.parent if validation_path else story_path.parent
    path_text = text_value(check.get("output") or check.get("path"))
    if not path_text:
        raise ManifestValidationError(f"{name} requires output")
    resolved = resolve_path(path_text, base_dir=base_dir, context=context)
    exists = resolved.exists()
    if exists and (resolved.is_dir() or resolved.stat().st_size > 0):
        return {
            "status": "pass",
            "evidence": rel(resolved),
            "check": make_check(
                name,
                "screenshot",
                "pass",
                "screenshot evidence exists",
                evidence=rel(resolved),
                observed={"output": path_text, "exists": True},
                path=path_text,
            ),
        }
    return {
        "status": "fail",
        "missing": path_text,
        "check": make_check(
            name,
            "screenshot",
            "fail",
            "screenshot evidence is missing",
            observed={"output": path_text, "exists": exists},
            path=path_text,
        ),
    }


def run_command_check(
    check: dict[str, Any],
    *,
    name: str,
    story_path: Path,
    validation_path: Path | None,
    context: dict[str, str],
    allowed_commands: list[str],
) -> dict[str, Any]:
    raw_command = check.get("command")
    if raw_command is None:
        raise ManifestValidationError(f"{name} is missing command")
    command_string, shell = normalize_command(raw_command)
    if allowed_commands and command_string not in allowed_commands:
        return {
            "status": "escalate",
            "reason": f"command is not in the allowed command list: {command_string}",
            "check": make_check(name, "command", "escalate", "command is not allowlisted", observed={"command": command_string, "allowed_commands": allowed_commands}, command=command_string),
            "command": command_string,
        }
    base_dir = validation_path.parent if validation_path else story_path.parent
    cwd_text = text_value(check.get("cwd") or ".")
    cwd = resolve_path(cwd_text, base_dir=base_dir, context=context)
    timeout = int(check.get("timeout_seconds") or check.get("timeout") or 60)
    expected_exit = int(check.get("expected_exit") or check.get("expect_exit") or 0)
    try:
        completed = subprocess.run(
            command_string if shell else shlex.split(command_string),
            cwd=str(cwd),
            text=True,
            shell=shell,
            executable="/bin/bash" if shell else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = text_value(exc.stdout)
        stderr = text_value(exc.stderr)
        return {
            "status": "fail",
            "reason": f"command timed out after {timeout}s",
            "command": command_string,
            "check": make_check(
                name,
                "command",
                "fail",
                f"command timed out after {timeout}s",
                observed={"cwd": rel(cwd), "timeout_seconds": timeout, "stdout_tail": stdout[-600:], "stderr_tail": stderr[-600:]},
                command=command_string,
            ),
        }
    stdout = text_value(completed.stdout)
    stderr = text_value(completed.stderr)
    if completed.returncode != expected_exit:
        return {
            "status": "fail",
            "reason": f"exit code {completed.returncode}, expected {expected_exit}",
            "command": command_string,
            "check": make_check(
                name,
                "command",
                "fail",
                f"exit code {completed.returncode}, expected {expected_exit}",
                observed={"cwd": rel(cwd), "exit_code": completed.returncode, "stdout_tail": stdout[-600:], "stderr_tail": stderr[-600:]},
                command=command_string,
            ),
        }
    return {
        "status": "pass",
        "command": command_string,
        "check": make_check(
            name,
            "command",
            "pass",
            "command succeeded",
            observed={"cwd": rel(cwd), "exit_code": completed.returncode, "stdout_tail": stdout[-600:], "stderr_tail": stderr[-600:]},
            command=command_string,
        ),
    }


def summarize(status: str, checks: list[dict[str, Any]], missing_items: list[str], failed_commands: list[str], escalation_reasons: list[str]) -> str:
    if status == "pass":
        return "All deterministic manifest checks passed."
    if status == "fail":
        failed = len([item for item in checks if item.get("status") == "fail"])
        return f"{failed} deterministic check(s) failed or required evidence was missing."
    return f"{len(escalation_reasons)} escalation reason(s) require human or coordinated follow-up."


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# No-Model Validation Report",
        "",
        f"- Status: **{result['status'].upper()}**",
        f"- Summary: {result['summary']}",
        f"- Story: `{result['story']}`",
        f"- Validation: `{result['validation'] or 'none'}`",
        f"- Report JSON: `{result['report_json']}`",
        f"- Evidence paths: `{len(result['evidence_paths'])}`",
        "",
    ]
    if result.get("allowed_commands"):
        lines.extend(["## Allowed Commands", ""])
        for item in result["allowed_commands"]:
            lines.append(f"- `{item}`")
        lines.append("")
    lines.extend(
        [
            "## Checks",
            "",
            "| Check | Type | Status | Reason | Evidence |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for check in result["checks"]:
        lines.append(
            f"| {markdown_escape(check['name'])} | {markdown_escape(check['type'])} | {check['status'].upper()} | "
            f"{markdown_escape(check.get('reason', ''))} | `{markdown_escape(check.get('evidence', ''))}` |"
        )
    for section_name, key in (
        ("Missing Items", "missing_items"),
        ("Failed Commands", "failed_commands"),
        ("Evidence Paths", "evidence_paths"),
        ("Escalation Reasons", "escalation_reasons"),
    ):
        lines.extend(["", f"## {section_name}", ""])
        items = result.get(key) or []
        if items:
            for item in items:
                if isinstance(item, dict):
                    lines.append(f"- `{markdown_escape(item.get('command') or item.get('path') or item)}`")
                else:
                    lines.append(f"- `{markdown_escape(item)}`")
        else:
            lines.append("- None.")
    lines.append("")
    return "\n".join(lines)


def run_engine(story_path: Path, validation_path: Path | None) -> dict[str, Any]:
    started_at = now_iso()
    started = time.perf_counter()
    story = load_story(story_path)
    if validation_path is None:
        validation_path = default_validation_path(story, story_path)
    validation = load_validation(validation_path)
    context = story_context(story, story_path, validation_path)

    story_checks, story_missing, story_escalations = validate_story_structure(story, story_path=story_path, context=context)
    api_checks, api_missing, api_escalations = validate_story_api_endpoints(story, story_path=story_path, context=context)
    expected_checks, output_missing, output_escalations, output_evidence = validate_story_expected_outputs(story, story_path=story_path, context=context)
    screenshot_checks, screenshot_missing, screenshot_escalations, screenshot_evidence = validate_story_screenshots(story, story_path=story_path, context=context)
    validation_checks, validation_missing, validation_escalations, failed_commands, validation_evidence = validate_validation_manifest(
        story=story,
        story_path=story_path,
        validation=validation,
        validation_path=validation_path,
        context=context,
    )

    checks = [*story_checks, *api_checks, *expected_checks, *screenshot_checks, *validation_checks]
    missing_items = [*story_missing, *api_missing, *output_missing, *screenshot_missing, *validation_missing]
    escalation_reasons = [*story_escalations, *api_escalations, *output_escalations, *screenshot_escalations, *validation_escalations]
    evidence_paths = []
    for item in [*output_evidence, *screenshot_evidence, *validation_evidence]:
        if item and item not in evidence_paths:
            evidence_paths.append(item)

    # Write the report evidence even for failure and escalation cases.
    report_path_text = text_value(validation.get("report"))
    if not report_path_text:
        report_base = validation_path.parent if validation_path else story_path.parent
        report_path = report_base / "validation-report.md"
    else:
        report_path = resolve_path(report_path_text, base_dir=validation_path.parent if validation_path else story_path.parent, context=context)
    report_json = report_path.with_suffix(".json")
    report_payload = {
        "schema": "cento.no-model-validation.report.v1",
        "status": "pass",
    }

    if any(item for item in escalation_reasons):
        status = "escalate"
    elif any(item for item in missing_items) or any(item.get("status") == "fail" for item in checks) or failed_commands:
        status = "fail"
    else:
        status = "pass"

    summary = summarize(status, checks, missing_items, failed_commands, escalation_reasons)
    duration_ms = round((time.perf_counter() - started) * 1000, 3)
    story_validation = ensure_dict(story.get("validation"), "story.validation") if isinstance(story.get("validation"), dict) else {}
    for item in [rel(report_path), rel(report_json)]:
        if item not in evidence_paths:
            evidence_paths.append(item)
    result = {
        "schema": "cento.no-model-validation.result.v1",
        "status": status,
        "decision": status,
        "summary": summary,
        "started_at": started_at,
        "ended_at": now_iso(),
        "duration_ms": duration_ms,
        "story": rel(story_path),
        "validation": rel(validation_path) if validation_path else "",
        "report": rel(report_path),
        "report_json": rel(report_json),
        "allowed_commands": [text_value(item) for item in (validation.get("allowed_commands") or story_validation.get("commands") or []) if text_value(item)],
        "checks": checks,
        "missing_items": missing_items,
        "failed_commands": failed_commands,
        "evidence_paths": evidence_paths,
        "escalation_reasons": escalation_reasons,
    }
    report_payload["status"] = status
    report_payload["result"] = result
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown_report(result), encoding="utf-8")
    write_json(report_json, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a deterministic story.json + validation.json validation engine without AI.")
    parser.add_argument("--story", required=True, help="Path to story.json.")
    parser.add_argument("--validation", default="", help="Optional validation.json path.")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable result to stdout.")
    parser.add_argument(
        "--report",
        nargs="?",
        const="",
        default=None,
        help="Write a Markdown report to the given path or to the default validation-report.md next to the validation manifest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    story_path = Path(args.story).expanduser()
    if not story_path.is_absolute():
        story_path = (ROOT / story_path).resolve()
    validation_path = None
    if args.validation:
        validation_path = Path(args.validation).expanduser()
        if not validation_path.is_absolute():
            validation_path = (ROOT / validation_path).resolve()
    try:
        result = run_engine(story_path, validation_path)
    except ManifestValidationError as exc:
        error = {
            "schema": "cento.no-model-validation.result.v1",
            "status": "escalate",
            "decision": "escalate",
            "summary": str(exc),
            "story": rel(story_path),
            "validation": rel(validation_path) if validation_path else "",
            "report": "",
            "report_json": "",
            "checks": [],
            "missing_items": [],
            "failed_commands": [],
            "evidence_paths": [],
            "escalation_reasons": [str(exc)],
        }
        if args.json:
            print(json.dumps(error, indent=2, sort_keys=True))
        else:
            print(error["summary"], file=sys.stderr)
        return 3

    report_override = args.report
    if report_override is not None:
        report_path = result["report"]
        if report_override:
            resolved = Path(report_override).expanduser()
            if not resolved.is_absolute():
                resolved = (ROOT / resolved).resolve()
            report_path = resolved
            report_json = report_path.with_suffix(".json")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(markdown_report(result), encoding="utf-8")
            write_json(report_json, result)
            result["report"] = rel(report_path)
            result["report_json"] = rel(report_json)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"status: {result['status']}")
        print(f"summary: {result['summary']}")
        print(f"report: {result['report']}")
        print(f"report_json: {result['report_json']}")
    if result["status"] == "pass":
        return 0
    if result["status"] == "fail":
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
