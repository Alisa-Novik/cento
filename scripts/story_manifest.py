#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import deliverables_hub


ROOT = Path(__file__).resolve().parents[1]
VALID_ROLES = {"builder", "validator", "coordinator", "docs-evidence"}
VALIDATION_MODES = ("manual-planning", "no-model", "cheap-model", "strong-model")
VALIDATION_MODE_SET = set(VALIDATION_MODES)
VALIDATION_RISKS = ("low", "medium", "high")
VALIDATION_RISK_SET = set(VALIDATION_RISKS)
VALIDATION_ESCALATION_TRIGGERS = (
    "missing_manifest",
    "high_risk",
    "ux_judgment",
    "failed_deterministic_command",
    "ambiguity",
)
VALIDATION_ESCALATION_TRIGGER_SET = set(VALIDATION_ESCALATION_TRIGGERS)


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


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "story"


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def parse_json_value(value: str) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_key_value_spec(value: str, fields: list[str]) -> dict[str, Any]:
    if value.strip().startswith("{"):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise StoryManifestError(f"JSON spec must be an object: {value}")
        return parsed
    parts = value.split("::")
    item: dict[str, Any] = {}
    for index, field in enumerate(fields):
        if index < len(parts) and parts[index] != "":
            item[field] = parts[index]
    if len(parts) > len(fields):
        item[fields[-1]] = "::".join(parts[len(fields) - 1 :])
    return item


def parse_expected_output(value: str, default_owner: str) -> dict[str, Any]:
    if value.strip().startswith("{"):
        item = json.loads(value)
        if not isinstance(item, dict):
            raise StoryManifestError(f"expected output JSON must be an object: {value}")
    else:
        parts = value.split("::")
        item = {"path": parts[0]}
        if len(parts) >= 2 and parts[1]:
            item["description"] = parts[1]
        if len(parts) >= 3 and parts[2]:
            item["required"] = parse_bool(parts[2])
    if not item.get("path"):
        raise StoryManifestError("expected output requires a path")
    item.setdefault("owner", default_owner)
    item.setdefault("required", True)
    return item


def build_draft_manifest(args: argparse.Namespace) -> dict[str, Any]:
    title = args.title.strip()
    if not title:
        raise StoryManifestError("--title is required")
    package = args.package.strip() or "default"
    owner = args.owner.strip() or args.role
    run_dir = args.run_dir.strip() or f"workspace/runs/agent-work/drafts/{slugify(package + '-' + title)}"
    validation_manifest = args.validation_manifest.strip() or f"{run_dir}/validation.json"
    deliverables_manifest = args.deliverables_manifest.strip() or f"{run_dir}/deliverables.json"
    deliverables_hub = args.deliverables_hub.strip() or f"{run_dir}/start-here.html"

    acceptance = [item.strip() for item in args.acceptance if item.strip()]
    if not acceptance:
        acceptance = ["Explicit expected outputs and validation checks are produced."]
    expected_outputs = [parse_expected_output(item, owner) for item in args.expected_output]
    if not expected_outputs:
        raise StoryManifestError("at least one --expected-output is required")

    validation: dict[str, Any] = {
        "manifest": validation_manifest,
        "mode": "no-model",
        "no_model_eligible": True,
        "risk": args.risk,
        "escalation_triggers": args.escalation_trigger
        or ["missing_manifest", "failed_deterministic_command", "ambiguity"],
    }
    validation["commands"] = [
        item.strip()
        for item in (
            args.validation_command
            or [f"python3 -m json.tool {{root}}/{validation_manifest}"]
        )
        if item.strip()
    ]
    if args.required_text:
        validation["required_text"] = [
            parse_key_value_spec(item, ["path", "text", "name"]) for item in args.required_text if item.strip()
        ]
    if args.json_field:
        fields = []
        for item in args.json_field:
            parsed = parse_key_value_spec(item, ["path", "field", "expected"])
            if "expected" in parsed:
                parsed["expected"] = parse_json_value(str(parsed["expected"]))
            fields.append(parsed)
        validation["json_fields"] = fields
    if args.url:
        validation["urls"] = [parse_key_value_spec(item, ["url", "expected_status", "name"]) for item in args.url if item.strip()]

    screenshots = []
    for item in args.screenshot:
        parsed = parse_key_value_spec(item, ["output", "name", "viewport"])
        if parsed.get("output"):
            screenshots.append(parsed)

    manifest = {
        "schema_version": "1.0",
        "issue": {
            "id": int(args.issue_id),
            "title": title,
            "package": package,
        },
        "lane": {
            "owner": owner,
            "node": args.node.strip() or "unassigned",
            "agent": args.agent.strip(),
            "role": args.role,
        },
        "paths": {
            "run_dir": run_dir,
        },
        "scope": {
            "goal": args.goal.strip() or title,
            "acceptance": acceptance,
        },
        "expected_outputs": expected_outputs,
        "validation": validation,
        "deliverables": {
            "manifest": deliverables_manifest,
            "hub": deliverables_hub,
        },
        "review_gate": {
            "required_sections": ["Delivered", "Validation", "Evidence", "Residual risk"],
            "residual_risk_required": True,
        },
        "metadata": {
            "drafted_at": now_iso(),
            "draft_policy": "deterministic checks only; unresolved subjective criteria must stay in manual_review",
        },
    }
    if screenshots:
        manifest["screenshots"] = screenshots
    return manifest


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


def normalize_validation_commands(value: Any, errors: list[str]) -> list[str]:
    if value is None:
        errors.append("missing field: validation.commands")
        return []
    if not isinstance(value, list):
        errors.append("field must be a list: validation.commands")
        return []

    commands: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            command = item.strip()
            if command:
                commands.append(command)
            else:
                errors.append(f"field must be non-empty text: validation.commands[{index}]")
            continue
        if isinstance(item, dict):
            name = item.get("name")
            if name is not None and (not isinstance(name, str) or not name.strip()):
                errors.append(f"field must be non-empty text: validation.commands[{index}].name")
            command = item.get("command")
            if isinstance(command, str) and command.strip():
                commands.append(command.strip())
            else:
                errors.append(f"field must be non-empty text: validation.commands[{index}].command")
            continue
        errors.append(f"validation.commands entries must be strings or objects with a command field: index {index}")
    return commands


def normalize_validation_triggers(value: Any, errors: list[str]) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("field must be a list: validation.escalation_triggers")
        return []

    triggers: list[str] = []
    allowed = ", ".join(VALIDATION_ESCALATION_TRIGGERS)
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"field must be non-empty text: validation.escalation_triggers[{index}]")
            continue
        trigger = item.strip()
        if trigger not in VALIDATION_ESCALATION_TRIGGER_SET:
            errors.append(f"validation.escalation_triggers entries must be one of {allowed}: {trigger}")
            continue
        triggers.append(trigger)
    return triggers


def validate_validation_policy(validation: dict[str, Any], errors: list[str]) -> None:
    mode = str(validation.get("mode") or "").strip()
    if not mode:
        errors.append("missing field: validation.mode")
    elif mode not in VALIDATION_MODE_SET:
        errors.append(f"validation.mode must be one of {', '.join(VALIDATION_MODES)}: {mode}")

    risk = str(validation.get("risk") or "").strip()
    if not risk:
        errors.append("missing field: validation.risk")
    elif risk not in VALIDATION_RISK_SET:
        errors.append(f"validation.risk must be one of {', '.join(VALIDATION_RISKS)}: {risk}")

    no_model_eligible = validation.get("no_model_eligible")
    if not isinstance(no_model_eligible, bool):
        errors.append("field must be boolean: validation.no_model_eligible")
    elif no_model_eligible is True and mode != "no-model":
        errors.append(f"validation.no_model_eligible must be false unless validation.mode is no-model: {mode}")

    commands = normalize_validation_commands(validation.get("commands"), errors)
    escalation_triggers = normalize_validation_triggers(validation.get("escalation_triggers"), errors)

    if mode == "manual-planning":
        return

    if not commands:
        errors.append("validation.commands must include at least one command when validation.mode is not manual-planning")
    if not escalation_triggers:
        errors.append("validation.escalation_triggers must be present when validation.mode is not manual-planning")

    if mode == "no-model":
        if no_model_eligible is not True:
            errors.append("validation.no_model_eligible must be true when validation.mode is no-model")
        if risk == "high":
            errors.append("validation.risk must be low or medium when validation.mode is no-model")
    elif risk == "high" and mode != "strong-model":
        errors.append("validation.mode must be strong-model when validation.risk is high")


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
        validate_validation_policy(validation, errors)

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


def card(
    title: str,
    href: str,
    description: str,
    *,
    code: str = "",
    primary: bool = False,
    badge: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "title": title,
        "href": href,
        "description": description,
    }
    if code:
        item["code"] = code
    if primary:
        item["primary"] = True
    if badge:
        item["badge"] = badge
    return item


def coerce_report_spec(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        path = value.strip()
        if not path:
            return None
        return {"path": path}
    if not isinstance(value, dict):
        return None
    path = str(value.get("path") or value.get("href") or value.get("report") or "").strip()
    if not path:
        return None
    spec: dict[str, Any] = {"path": path}
    for key in ("json", "report_json", "result", "status", "badge", "label", "title", "description"):
        raw = value.get(key)
        if raw is not None and str(raw).strip():
            spec[key] = raw
    return spec


def validation_result_cards(spec: dict[str, Any], base_dir: Path) -> list[dict[str, Any]]:
    def report_title(companion: bool = False) -> str:
        label = str(spec.get("title") or spec.get("label") or "").strip()
        if label:
            return f"{label} JSON" if companion else label
        stem = Path(path).stem.lower()
        if "no-model" in stem:
            title = "No-model validation report"
        elif "validation" in stem or "report" in stem:
            title = "Validation report"
        else:
            title = Path(path).name
        return f"{title} JSON" if companion else title

    def report_description(companion: bool = False) -> str:
        description = str(spec.get("description") or "").strip()
        if description and not companion:
            return description
        if description:
            return f"{description} Machine-readable companion."
        return "Machine-readable companion validation report." if companion else "Validation report for review handoff."

    path = str(spec.get("path") or "").strip()
    if not path:
        return []

    badge = str(spec.get("badge") or spec.get("result") or spec.get("status") or "").strip()
    json_path = str(spec.get("json") or spec.get("report_json") or "").strip()
    if not json_path and not spec.get("skip_json_companion"):
        candidate = Path(path)
        json_path = str(candidate.with_suffix(".json")) if candidate.suffix else f"{path}.json"

    cards: list[dict[str, Any]] = [
        card(
            report_title(),
            href_for(path, base_dir),
            report_description(),
            code=path,
            badge=badge or None,
        )
    ]

    if json_path and json_path != path:
        cards.append(
            card(
                report_title(companion=True),
                href_for(json_path, base_dir),
                report_description(companion=True),
                code=json_path,
                badge=badge or None,
            )
        )

    return cards


def validation_results_from_story(payload: dict[str, Any], deliverables_path: Path) -> list[dict[str, Any]]:
    validation = payload.get("validation") or {}
    specs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in (validation.get("report"),):
        spec = coerce_report_spec(raw)
        if spec and spec["path"] not in seen:
            specs.append(spec)
            seen.add(spec["path"])

    manifest_path = str(validation.get("manifest") or "").strip()
    if manifest_path:
        validation_manifest_path = repo_path(manifest_path)
        if validation_manifest_path.exists():
            validation_manifest = load_manifest(validation_manifest_path)
            spec = coerce_report_spec(validation_manifest.get("report"))
            if spec and spec["path"] not in seen:
                specs.append(spec)
                seen.add(spec["path"])

    for item in payload.get("expected_outputs") or []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or path in seen:
            continue
        owner = str(item.get("owner") or "").strip().lower()
        description = str(item.get("description") or "").strip()
        path_lower = Path(path).name.lower()
        description_lower = description.lower()
        if owner != "validator" and "validation" not in path_lower and "validation" not in description_lower and "report" not in path_lower:
            continue
        spec: dict[str, Any] = {
            "path": path,
            "badge": "report",
            "title": description or Path(path).name,
            "description": description or "Linked expected output.",
            "skip_json_companion": True,
        }
        candidate = Path(path)
        json_path = str(candidate.with_suffix(".json")) if candidate.suffix else f"{path}.json"
        if repo_path(json_path).exists():
            spec["json"] = json_path
            spec.pop("skip_json_companion", None)
        specs.append(spec)
        seen.add(path)

    cards: list[dict[str, Any]] = []
    for spec in specs:
        cards.extend(validation_result_cards(spec, deliverables_path.parent))
    return cards


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
    validation_results = validation_results_from_story(payload, deliverables_path)

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
        "validation_results": validation_results,
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


def command_draft(args: argparse.Namespace) -> int:
    try:
        manifest = build_draft_manifest(args)
    except (StoryManifestError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(manifest, check_links=False)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    output = repo_path(args.output) if args.output else repo_path(str(manifest["paths"]["run_dir"])) / "story.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not args.check_only:
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": True, "story_manifest": display_path(output), "manifest": manifest}, indent=2, sort_keys=True))
    else:
        print(f"story_manifest: {display_path(output)}")
        print(f"validation_manifest: {manifest['validation']['manifest']}")
        print("status: ok")
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

    draft = sub.add_parser("draft", help="Create a conservative draft story.json from interpreted task fields.")
    draft.add_argument("--title", required=True)
    draft.add_argument("--package", default="default")
    draft.add_argument("--goal", default="")
    draft.add_argument("--issue-id", type=int, default=0, help="Use 0 before agent-work create; real issue ids are canonicalized later.")
    draft.add_argument("--owner", default="builder")
    draft.add_argument("--node", default="unassigned")
    draft.add_argument("--agent", default="")
    draft.add_argument("--role", choices=sorted(VALID_ROLES), default="builder")
    draft.add_argument("--risk", choices=["low", "medium", "high"], default="low")
    draft.add_argument("--run-dir", default="")
    draft.add_argument("--validation-manifest", default="")
    draft.add_argument("--deliverables-manifest", default="")
    draft.add_argument("--deliverables-hub", default="")
    draft.add_argument("--acceptance", action="append", default=[], help="Acceptance bullet. Repeat for multiple criteria.")
    draft.add_argument(
        "--expected-output",
        action="append",
        required=True,
        help="Expected artifact as PATH or PATH::DESCRIPTION::REQUIRED. JSON object is also accepted.",
    )
    draft.add_argument("--validation-command", action="append", default=[], help="Deterministic command to include in validation draft input.")
    draft.add_argument(
        "--escalation-trigger",
        action="append",
        choices=sorted(VALIDATION_ESCALATION_TRIGGERS),
        default=[],
        help="Reason to leave the no-model path. Repeat for multiple triggers.",
    )
    draft.add_argument("--required-text", action="append", default=[], help="Contains-text input as PATH::TEXT::NAME or JSON object.")
    draft.add_argument("--json-field", action="append", default=[], help="JSON-field input as PATH::FIELD::EXPECTED_JSON or JSON object.")
    draft.add_argument("--url", action="append", default=[], help="HTTP status input as URL::EXPECTED_STATUS::NAME or JSON object.")
    draft.add_argument("--screenshot", action="append", default=[], help="Screenshot artifact as OUTPUT::NAME::VIEWPORT or JSON object.")
    draft.add_argument("--output", default="", help="Output story.json path. Defaults to <run_dir>/story.json.")
    draft.add_argument("--check-only", action="store_true", help="Build and validate without writing the draft.")
    draft.add_argument("--json", action="store_true", help="Print machine-readable result.")
    draft.set_defaults(func=command_draft)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
