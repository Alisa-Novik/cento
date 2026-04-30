#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import deliverables_hub


ROOT = Path(__file__).resolve().parents[1]
VALID_ROLES = {"builder", "validator", "coordinator", "docs-evidence"}


class StoryManifestError(Exception):
    pass


def repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def is_external_ref(value: str) -> bool:
    return value.startswith(("http://", "https://", "mailto:", "#"))


def local_ref_value(value: str) -> str:
    if value.startswith("file:///{root}/"):
        return value[len("file:///{root}/") :]
    if value.startswith(f"file://{ROOT}/"):
        return value[len("file://") :]
    return value


def href_for(value: str, base_dir: Path) -> str:
    value = local_ref_value(str(value or ""))
    if not value:
        return "#"
    if is_external_ref(value):
        return value
    if value.startswith("redmine://"):
        return "#"
    path = repo_path(value)
    return os.path.relpath(path, base_dir)


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


def short_text(value: str, limit: int = 96) -> str:
    value = " ".join(str(value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def card(title: str, href: str, description: str, *, code: str = "", primary: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": title,
        "href": href,
        "description": description,
    }
    if code:
        item["code"] = code
    if primary:
        item["primary"] = True
    return item


def generated_deliverables(payload: dict[str, Any], story_path: Path, deliverables_path: Path) -> dict[str, Any]:
    issue = payload.get("issue") or {}
    lane = payload.get("lane") or {}
    paths = payload.get("paths") or {}
    scope = payload.get("scope") or {}
    validation = payload.get("validation") or {}
    review_gate = payload.get("review_gate") or {}
    handoff = payload.get("handoff") or {}
    base_dir = deliverables_path.parent

    issue_id = issue.get("id") or "unknown"
    status = str(issue.get("status") or "Unknown")
    title = str(issue.get("title") or f"Agent Work #{issue_id}")
    story_rel = display_path(story_path)

    use_first = [
        card(
            "Story Contract",
            href_for(story_rel, base_dir),
            "Shared story.json used by Builder, Validator, Docs/Evidence, and Coordinator lanes.",
            code=story_rel,
            primary=True,
        ),
    ]
    issue_url = str(issue.get("url") or f"redmine://issues/{issue_id}")
    use_first.append(card("Redmine Issue", "#", f"Current status: {status}.", code=issue_url))

    validation_manifest = str(validation.get("manifest") or "")
    if validation_manifest:
        use_first.append(card("Validation Manifest", href_for(validation_manifest, base_dir), "Executable checks for validator-run.", code=validation_manifest))

    deliverables = payload.get("deliverables") or {}
    existing_hub = str(deliverables.get("hub") or "")
    if existing_hub and existing_hub != display_path(deliverables_path.with_name("start-here.html")):
        use_first.append(card("Existing Hub", href_for(existing_hub, base_dir), "Previously linked hub or manager-facing page.", code=existing_hub))

    for route in payload.get("routes") or []:
        if not isinstance(route, dict):
            continue
        route_url = str(route.get("url") or "")
        if not route_url:
            continue
        use_first.append(
            card(
                str(route.get("name") or "Route"),
                href_for(route_url, base_dir),
                str(route.get("purpose") or "Linked route from story.json."),
                code=route_url if is_external_ref(route_url) else "",
            )
        )

    output_cards = []
    for item in payload.get("expected_outputs") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not path:
            continue
        output_cards.append(
            card(
                str(item.get("description") or Path(path).name),
                href_for(path, base_dir),
                f"Owner: {item.get('owner') or 'unassigned'}. Required: {bool(item.get('required', True))}.",
                code=path,
            )
        )
    use_first.extend(output_cards[:8])

    screenshot_cards = []
    for item in payload.get("screenshots") or []:
        if not isinstance(item, dict):
            continue
        output = str(item.get("output") or item.get("path") or "")
        if not output:
            continue
        screenshot_cards.append(
            card(
                str(item.get("name") or Path(output).stem),
                href_for(output, base_dir),
                str(item.get("description") or f"Viewport: {item.get('viewport') or 'unspecified'}."),
                code=output,
            )
        )

    commands = [
        f"python3 scripts/story_manifest.py validate {story_rel} --check-links",
        f"python3 scripts/story_manifest.py render-hub {story_rel} --check-links",
    ]
    for item in validation.get("commands") or []:
        if isinstance(item, dict) and item.get("command"):
            commands.append(str(item["command"]))

    review = []
    for item in scope.get("acceptance") or []:
        review.append(f"Acceptance: {item}")
    for item in validation.get("required_evidence") or []:
        review.append(f"Evidence: {item}")
    if handoff.get("device_access") and handoff.get("device_access") != "none":
        review.append(f"Device access: {handoff.get('device_access')}")
    for step in handoff.get("human_steps") or []:
        review.append(f"Human handoff: {step}")
    for note in handoff.get("notes") or []:
        review.append(f"Note: {note}")
    sections = review_gate.get("required_sections") or []
    if sections:
        review.append("Review note must include: " + ", ".join(str(item) for item in sections))
    if review_gate.get("residual_risk_required"):
        review.append("Residual risk must be stated explicitly, even when the risk is none.")

    return {
        "title": f"#{issue_id} {title}",
        "subtitle": f"Package: {issue.get('package') or 'default'} | Lane: {lane.get('role') or '-'} on {lane.get('node') or '-'} | Generated from story.json.",
        "badge": status,
        "footer": f"Generated from {story_rel}. Deliverables manifest: {display_path(deliverables_path)}.",
        "use_first": use_first,
        "stories": [
            {"label": f"#{issue_id}", "description": short_text(title)},
            {"label": "Status", "description": status},
            {"label": "Owner", "description": f"{lane.get('agent') or '-'} / {lane.get('role') or '-'}"},
            {"label": "Run Dir", "description": str(paths.get("run_dir") or "-")},
        ],
        "commands": commands,
        "screenshots": screenshot_cards,
        "review": review or ["Review story.json acceptance criteria and linked evidence."],
    }


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


def command_render_hub(args: argparse.Namespace) -> int:
    story_path = repo_path(str(args.manifest))
    payload = load_manifest(story_path)
    # The hub command may be creating deliverables.manifest for the first time,
    # so link-check the generated hub below instead of requiring that output
    # manifest to exist before rendering.
    errors = validate_manifest(payload, check_links=False)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    run_dir = repo_path(str((payload.get("paths") or {}).get("run_dir") or story_path.parent))
    deliverables_value = args.deliverables or str((payload.get("deliverables") or {}).get("manifest") or "")
    output_value = args.output or str((payload.get("deliverables") or {}).get("hub") or "")
    deliverables_path = repo_path(deliverables_value) if deliverables_value else run_dir / "deliverables.json"
    output_path = repo_path(output_value) if output_value else run_dir / "start-here.html"

    deliverables_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = generated_deliverables(payload, story_path, deliverables_path)
    missing = deliverables_hub.validate_links(deliverables_path, manifest) if args.check_links else []
    if missing:
        print("missing local deliverable links:", file=sys.stderr)
        for href in missing:
            print(f"- {href}", file=sys.stderr)
        return 1

    if not args.check_only:
        deliverables_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        output_path.write_text(deliverables_hub.render(manifest), encoding="utf-8")

    if args.json:
        print(json.dumps({"ok": True, "deliverables": display_path(deliverables_path), "output": display_path(output_path)}, indent=2))
    else:
        print(f"deliverables: {display_path(deliverables_path)}")
        print(f"hub: {display_path(output_path)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Cento agent-work story.json manifests and generate story hubs.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a story.json manifest.")
    validate.add_argument("manifest", help="Path to story.json.")
    validate.add_argument("--check-links", action="store_true", help="Require referenced local manifest/output paths to exist.")
    validate.add_argument("--json", action="store_true", help="Print machine-readable validation result.")
    validate.set_defaults(func=command_validate)

    render_hub = sub.add_parser("render-hub", help="Generate deliverables.json and start-here.html from story.json.")
    render_hub.add_argument("manifest", help="Path to story.json.")
    render_hub.add_argument("--deliverables", default="", help="Output deliverables.json path. Defaults to <run_dir>/deliverables.json.")
    render_hub.add_argument("--output", default="", help="Output HTML hub path. Defaults to <run_dir>/start-here.html.")
    render_hub.add_argument("--check-links", action="store_true", help="Require generated local links to exist before writing.")
    render_hub.add_argument("--check-only", action="store_true", help="Validate without writing deliverables or HTML files.")
    render_hub.add_argument("--json", action="store_true", help="Print machine-readable result.")
    render_hub.set_defaults(func=command_render_hub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
