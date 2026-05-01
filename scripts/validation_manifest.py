#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import story_manifest


ROOT = Path(__file__).resolve().parents[1]
MANUAL_STATUSES = {"accepted", "covered", "waived"}


class ValidationManifestError(Exception):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def repo_path(value: str, base: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    if base is not None:
        candidate = base / path
        if candidate.exists():
            return candidate
    return ROOT / value


def replace_placeholders(value: str, story: dict[str, Any]) -> str:
    issue = story.get("issue") or {}
    paths = story.get("paths") or {}
    return (
        str(value or "")
        .replace("<issue-id>", str(issue.get("id") or 0))
        .replace("{issue}", str(issue.get("id") or 0))
        .replace("{run_dir}", str(paths.get("run_dir") or ""))
        .replace("{root}", str(ROOT))
    )


def check_name(prefix: str, value: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"{prefix}-{base[:60]}" if base else prefix


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_required_text(item: Any, story: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(item, str):
        parts = item.split("::")
        if len(parts) < 2:
            return None
        item = {"path": parts[0], "text": "::".join(parts[1:])}
    if not isinstance(item, dict):
        return None
    path = replace_placeholders(str(item.get("path") or ""), story)
    text = str(item.get("text") or item.get("contains_text") or "")
    if not path or not text:
        return None
    return {
        "name": str(item.get("name") or check_name("contains-text", Path(path).name)),
        "type": "contains_text",
        "path": path,
        "text": text,
        "case_sensitive": bool(item.get("case_sensitive", True)),
        "required": bool(item.get("required", True)),
    }


def parse_json_field(item: Any, story: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(item, str):
        parts = item.split("::")
        if len(parts) < 2:
            return None
        item = {"path": parts[0], "field": parts[1]}
        if len(parts) >= 3:
            try:
                item["expected"] = json.loads("::".join(parts[2:]))
            except json.JSONDecodeError:
                item["expected"] = "::".join(parts[2:])
    if not isinstance(item, dict):
        return None
    path = replace_placeholders(str(item.get("path") or ""), story)
    field = str(item.get("field") or "")
    if not path or not field:
        return None
    check: dict[str, Any] = {
        "name": str(item.get("name") or check_name("json-field", f"{Path(path).name}-{field}")),
        "type": "json_field",
        "path": path,
        "field": field,
        "required": bool(item.get("required", True)),
    }
    if "expected" in item:
        check["expected"] = item["expected"]
    return check


def parse_url(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        parts = item.split("::")
        item = {"url": parts[0]}
        if len(parts) >= 2 and parts[1]:
            item["expected_status"] = parse_int(parts[1], 200)
        if len(parts) >= 3 and parts[2]:
            item["name"] = parts[2]
    if not isinstance(item, dict):
        return None
    url = str(item.get("url") or "")
    if not url:
        return None
    return {
        "name": str(item.get("name") or check_name("http-status", url)),
        "type": "http_status",
        "url": url,
        "expected_status": parse_int(item.get("expected_status", item.get("status")), 200),
        "timeout_seconds": parse_int(item.get("timeout_seconds", item.get("timeout")), 10),
        "required": bool(item.get("required", True)),
    }


def output_check(item: dict[str, Any], story: dict[str, Any]) -> dict[str, Any] | None:
    path = replace_placeholders(str(item.get("path") or item.get("output") or ""), story)
    if not path:
        return None
    return {
        "name": str(item.get("name") or check_name("file-exists", Path(path).name)),
        "type": "file_exists",
        "path": path,
        "required": bool(item.get("required", True)),
    }


def screenshot_checks(item: dict[str, Any], story: dict[str, Any]) -> list[dict[str, Any]]:
    output = replace_placeholders(str(item.get("output") or item.get("path") or ""), story)
    if not output:
        return []
    name = str(item.get("name") or Path(output).stem)
    return [
        {
            "name": check_name("screenshot-exists", name),
            "type": "file_exists",
            "path": output,
            "required": bool(item.get("required", True)),
        },
        {
            "name": check_name("screenshot-nonblank", name),
            "type": "image_nonblank",
            "path": output,
            "required": bool(item.get("required", True)),
        },
    ]


def replace_command_value(value: Any, story: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return replace_placeholders(value, story)
    if isinstance(value, list):
        return [replace_placeholders(str(item), story) for item in value]
    return value


def command_check(item: Any, index: int, story: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(item, str):
        item = {"command": item}
    if not isinstance(item, dict):
        return None
    command = replace_command_value(item.get("command"), story)
    if not command:
        return None
    return {
        "name": str(item.get("name") or f"command-{index}"),
        "type": "command",
        "command": command,
        "cwd": replace_placeholders(str(item.get("cwd") or "."), story),
        "timeout_seconds": parse_int(item.get("timeout_seconds", item.get("timeout")), 20),
        "expect_exit": parse_int(item.get("expect_exit", item.get("expected_exit")), 0),
        "required": bool(item.get("required", True)),
    }


def manual_review_items(story: dict[str, Any], deterministic_count: int) -> list[dict[str, Any]]:
    validation = story.get("validation") or {}
    raw = validation.get("manual_review") or []
    items: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if isinstance(item, dict):
                review = dict(item)
            else:
                review = {"name": f"manual-review-{index}", "description": str(item)}
            review.setdefault("status", "pending")
            items.append(review)

    if deterministic_count == 0:
        scope = story.get("scope") or {}
        for index, item in enumerate(scope.get("acceptance") or [], start=1):
            items.append(
                {
                    "name": f"acceptance-{index}",
                    "description": str(item),
                    "reason": "No explicit deterministic output or command covers this acceptance item.",
                    "status": "pending",
                }
            )
    return items


def build_manifest(story: dict[str, Any], story_path: Path) -> dict[str, Any]:
    validation = story.get("validation") or {}
    checks: list[dict[str, Any]] = []

    for item in story.get("expected_outputs") or []:
        if not isinstance(item, dict):
            continue
        check = output_check(item, story)
        if check:
            checks.append(check)
        text = item.get("contains_text") or item.get("required_text") or item.get("text")
        if text:
            text_check = parse_required_text({"path": item.get("path"), "text": text, "name": item.get("name")}, story)
            if text_check:
                checks.append(text_check)
        field = item.get("json_field") or item.get("field")
        if field:
            field_payload = {"path": item.get("path"), "field": field, "name": item.get("name")}
            if "expected" in item:
                field_payload["expected"] = item["expected"]
            field_check = parse_json_field(field_payload, story)
            if field_check:
                checks.append(field_check)

    for index, item in enumerate(validation.get("commands") or [], start=1):
        check = command_check(item, index, story)
        if check:
            checks.append(check)
    for item in validation.get("required_text") or []:
        check = parse_required_text(item, story)
        if check:
            checks.append(check)
    for item in validation.get("json_fields") or []:
        check = parse_json_field(item, story)
        if check:
            checks.append(check)
    for item in validation.get("urls") or []:
        check = parse_url(item)
        if check:
            checks.append(check)
    for item in story.get("screenshots") or []:
        if isinstance(item, dict):
            checks.extend(screenshot_checks(item, story))

    manual_review = manual_review_items(story, len(checks))
    total_units = len(checks) + len(manual_review)
    coverage = round((len(checks) / total_units) * 100, 3) if total_units else 0.0
    issue = story.get("issue") or {}
    scope = story.get("scope") or {}
    return {
        "schema": "cento.validation-manifest.v1",
        "task": str(issue.get("title") or story_path.stem),
        "story_manifest": rel(story_path),
        "claim": str(scope.get("goal") or issue.get("title") or ""),
        "risk": str(validation.get("risk") or "low"),
        "decision_requested": "approve",
        "checks": checks,
        "manual_review": manual_review,
        "coverage": {
            "deterministic_checks": len(checks),
            "manual_review_items": len(manual_review),
            "automation_coverage_percent": coverage,
        },
        "stats_policy": {
            "ai_calls_used": 0,
            "estimated_ai_cost": 0,
            "requires_total_duration_ms": True,
            "requires_per_check_duration_ms": True,
        },
        "created_at": now_iso(),
    }


def load_story(path: Path) -> dict[str, Any]:
    payload = story_manifest.load_manifest(path)
    errors = story_manifest.validate_manifest(payload, check_links=False)
    if errors:
        raise ValidationManifestError("Invalid story manifest:\n" + "\n".join(f"- {item}" for item in errors))
    return payload


def load_validation(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationManifestError(f"validation manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationManifestError(f"invalid validation manifest JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationManifestError("validation manifest root must be an object")
    return payload


def validate_validation_manifest(payload: dict[str, Any], *, min_coverage: float = 95.0) -> list[str]:
    errors: list[str] = []
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("validation manifest must include at least one deterministic check")
    else:
        for index, item in enumerate(checks, start=1):
            if not isinstance(item, dict):
                errors.append(f"check #{index} must be an object")
                continue
            if not str(item.get("type") or ""):
                errors.append(f"check #{index} is missing type")
            if not str(item.get("name") or ""):
                errors.append(f"check #{index} is missing name")

    coverage_payload = payload.get("coverage") or {}
    coverage = float(coverage_payload.get("automation_coverage_percent") or 0)
    if coverage < min_coverage:
        errors.append(f"automation coverage {coverage}% is below required {min_coverage}%")

    manual_review = payload.get("manual_review") or []
    if not isinstance(manual_review, list):
        errors.append("manual_review must be a list when present")
    else:
        for index, item in enumerate(manual_review, start=1):
            if not isinstance(item, dict):
                errors.append(f"manual_review #{index} must be an object")
                continue
            status = str(item.get("status") or "").strip().lower()
            if status not in MANUAL_STATUSES:
                errors.append(f"manual_review #{index} status must be accepted, covered, or waived before dispatch")
    return errors


def command_draft(args: argparse.Namespace) -> int:
    story_path = repo_path(args.story)
    try:
        story = load_story(story_path)
        manifest = build_manifest(story, story_path)
    except (ValidationManifestError, story_manifest.StoryManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    output = repo_path(args.output) if args.output else repo_path(str((story.get("validation") or {}).get("manifest") or "")) if (story.get("validation") or {}).get("manifest") else story_path.with_name("validation.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not args.check_only:
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": True, "validation_manifest": rel(output), "coverage": manifest["coverage"], "manual_review": manifest["manual_review"]}, indent=2, sort_keys=True))
    else:
        print(f"validation_manifest: {rel(output)}")
        print(f"checks: {manifest['coverage']['deterministic_checks']}")
        print(f"manual_review: {manifest['coverage']['manual_review_items']}")
        print(f"automation_coverage_percent: {manifest['coverage']['automation_coverage_percent']}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    try:
        payload = load_validation(repo_path(args.manifest))
        errors = validate_validation_manifest(payload, min_coverage=args.min_automation_coverage)
    except ValidationManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    result = {
        "ok": not errors,
        "errors": errors,
        "manifest": rel(repo_path(args.manifest)),
        "coverage": payload.get("coverage") or {},
        "stats": {
            "total_duration_ms": duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost": 0,
        },
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"status: {'ok' if result['ok'] else 'blocked'}")
        print(f"total_duration_ms: {duration_ms}")
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Draft and validate no-model validation manifests from story.json.")
    sub = parser.add_subparsers(dest="command", required=True)

    draft = sub.add_parser("draft", help="Generate validation.json checks from explicit story.json artifacts.")
    draft.add_argument("story", help="Path to story.json.")
    draft.add_argument("--output", default="", help="Output validation.json path. Defaults to story validation.manifest or beside story.json.")
    draft.add_argument("--check-only", action="store_true", help="Build without writing.")
    draft.add_argument("--json", action="store_true")
    draft.set_defaults(func=command_draft)

    validate = sub.add_parser("validate", help="Validate validation.json coverage and manual-review status.")
    validate.add_argument("manifest", help="Path to validation.json.")
    validate.add_argument("--min-automation-coverage", type=float, default=95.0)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
