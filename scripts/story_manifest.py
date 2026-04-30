#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALID_ROLES = {"builder", "validator", "coordinator", "docs-evidence"}


class StoryManifestError(Exception):
    pass


def repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StoryManifestError(f"story manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StoryManifestError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StoryManifestError("story manifest root must be an object")
    return payload


def require_object(payload: dict[str, Any], name: str) -> dict[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise StoryManifestError(f"missing object: {name}")
    return value


def require_text(payload: dict[str, Any], path: str) -> str:
    cursor: Any = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise StoryManifestError(f"missing field: {path}")
        cursor = cursor[part]
    if not isinstance(cursor, str) or not cursor.strip():
        raise StoryManifestError(f"field must be non-empty text: {path}")
    return cursor


def require_int(payload: dict[str, Any], path: str) -> int:
    cursor: Any = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise StoryManifestError(f"missing field: {path}")
        cursor = cursor[part]
    if not isinstance(cursor, int):
        raise StoryManifestError(f"field must be integer: {path}")
    return cursor


def require_list(payload: dict[str, Any], path: str) -> list[Any]:
    cursor: Any = payload
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise StoryManifestError(f"missing field: {path}")
        cursor = cursor[part]
    if not isinstance(cursor, list) or not cursor:
        raise StoryManifestError(f"field must be a non-empty list: {path}")
    return cursor


def validate_local_reference(path: str, label: str, errors: list[str]) -> None:
    if not path or path.startswith(("http://", "https://", "file://", "#")):
        return
    if not repo_path(path).exists():
        errors.append(f"missing {label}: {path}")


def validate_manifest(payload: dict[str, Any], *, check_links: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        require_text(payload, "schema_version")
        require_int(payload, "issue.id")
        require_text(payload, "issue.title")
        require_text(payload, "issue.package")
        require_text(payload, "lane.owner")
        require_text(payload, "lane.node")
        role = require_text(payload, "lane.role")
        if role not in VALID_ROLES:
            errors.append(f"lane.role must be one of {', '.join(sorted(VALID_ROLES))}: {role}")
        require_text(payload, "paths.run_dir")
        require_list(payload, "scope.acceptance")
        require_list(payload, "expected_outputs")
    except StoryManifestError as exc:
        errors.append(str(exc))

    issue = payload.get("issue")
    if isinstance(issue, dict) and issue.get("id") and str(issue["id"]) not in str(payload.get("paths", {}).get("run_dir", "")):
        errors.append("paths.run_dir should include the Redmine issue id")

    validation = payload.get("validation")
    if isinstance(validation, dict):
        manifest = str(validation.get("manifest") or "")
        if check_links and manifest:
            validate_local_reference(manifest, "validation manifest", errors)

    deliverables = payload.get("deliverables")
    if isinstance(deliverables, dict):
        manifest = str(deliverables.get("manifest") or "")
        if check_links and manifest:
            validate_local_reference(manifest, "deliverables manifest", errors)

    for section in ("routes", "api_endpoints", "screenshots", "expected_outputs"):
        value = payload.get(section, [])
        if value is not None and not isinstance(value, list):
            errors.append(f"{section} must be a list")

    if check_links:
        for item in payload.get("expected_outputs") or []:
            if not isinstance(item, dict):
                errors.append("expected_outputs entries must be objects")
                continue
            if item.get("required", True):
                validate_local_reference(str(item.get("path") or ""), "expected output", errors)

    return errors


def print_summary(payload: dict[str, Any], path: Path) -> None:
    issue = payload.get("issue") or {}
    lane = payload.get("lane") or {}
    paths = payload.get("paths") or {}
    print(f"story_manifest: {path}")
    print(f"issue: #{issue.get('id')} {issue.get('title')}")
    print(f"package: {issue.get('package')}")
    print(f"lane: {lane.get('role')} owner={lane.get('owner')} node={lane.get('node')} agent={lane.get('agent', '-')}")
    print(f"run_dir: {paths.get('run_dir')}")
    print(f"routes: {len(payload.get('routes') or [])}")
    print(f"api_endpoints: {len(payload.get('api_endpoints') or [])}")
    print(f"screenshots: {len(payload.get('screenshots') or [])}")
    print(f"expected_outputs: {len(payload.get('expected_outputs') or [])}")


def command_validate(args: argparse.Namespace) -> int:
    path = repo_path(str(args.manifest))
    payload = load_manifest(path)
    errors = validate_manifest(payload, check_links=args.check_links)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True, "manifest": str(path), "issue": payload.get("issue", {})}, indent=2))
    else:
        print_summary(payload, path)
        print("status: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Cento agent-work story.json manifests.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a story.json manifest.")
    validate.add_argument("manifest", help="Path to story.json.")
    validate.add_argument("--check-links", action="store_true", help="Require referenced local manifest/output paths to exist.")
    validate.add_argument("--json", action="store_true", help="Print machine-readable validation result.")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
