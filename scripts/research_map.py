#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"implemented", "partial", "not_implemented", "deferred_deliberately", "not_applicable", "existing_capability"}


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def validate_map(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != "research-map/v1":
        errors.append("schema_version must be research-map/v1")
    source = payload.get("source")
    if not isinstance(source, dict) or not str(source.get("title") or ""):
        errors.append("source.title is required")
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        return errors
    ids: set[str] = set()
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            errors.append(f"section #{index} must be an object")
            continue
        section_id = str(section.get("id") or "")
        if not section_id:
            errors.append(f"section #{index} is missing id")
        elif section_id in ids:
            errors.append(f"duplicate section id: {section_id}")
        ids.add(section_id)
        if not str(section.get("title") or ""):
            errors.append(f"section {section_id or index} is missing title")
        status = str(section.get("status") or "")
        if status not in VALID_STATUSES:
            errors.append(f"section {section_id or index} status must be one of {', '.join(sorted(VALID_STATUSES))}")
        coverage = section.get("coverage")
        if not isinstance(coverage, int) or coverage < 0 or coverage > 100:
            errors.append(f"section {section_id or index} coverage must be integer 0..100")
        if status in {"partial", "not_implemented", "deferred_deliberately"} and not (section.get("gaps") or section.get("decision") or section.get("notes")):
            errors.append(f"section {section_id or index} needs gaps, decision, or notes for non-complete status")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    try:
        payload = json.loads(repo_path(args.map).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not isinstance(payload, dict):
        print("ERROR: research map root must be an object", file=sys.stderr)
        return 1
    errors = validate_map(payload)
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    result = {
        "ok": not errors,
        "errors": errors,
        "map": rel(repo_path(args.map)),
        "sections": len(payload.get("sections") or []),
        "stats": {"duration_ms": duration_ms, "ai_calls_used": 0, "estimated_ai_cost_usd": 0},
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"status: {'ok' if result['ok'] else 'blocked'}")
        print(f"duration_ms: {duration_ms}")
    return 0 if result["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate research/spec implementation maps.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate a research-map.json file.")
    validate.add_argument("map")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
