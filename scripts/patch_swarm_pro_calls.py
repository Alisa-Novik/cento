#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "patch-swarm-pro-calls.json"
DEFAULT_EVIDENCE_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery" / "pro-call-registry"

SCHEMA_VERSION = "cento.patch_swarm.pro_call_registry.v1"
STATUSES = ("PENDING", "IN_PROGRESS", "CODEX_DONE", "CLOSED", "BLOCKED")
ALLOWED_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"CODEX_DONE", "BLOCKED"},
    "CODEX_DONE": {"CLOSED", "BLOCKED"},
    "CLOSED": set(),
    "BLOCKED": {"PENDING", "IN_PROGRESS", "CLOSED"},
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)\b(?:OPENAI_API_KEY|CENTO_OPENAI|ANTHROPIC_API_KEY)\s*=\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret)\s*[:=]\s*['\"]?(?:sk-)?[A-Za-z0-9_\-]{20,}"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("pro-call-registry-%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False)
        handle.write("\n")
    tmp.replace(path)


def call_by_id(registry: dict[str, Any], call_id: int) -> dict[str, Any]:
    for call in registry.get("calls", []):
        if isinstance(call, dict) and call.get("call_id") == call_id:
            return call
    raise ValueError(f"call_id {call_id} not found")


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if registry.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    calls = registry.get("calls")
    if not isinstance(calls, list):
        errors.append("calls must be a list")
        return errors
    expected_ids = list(range(0, 101))
    if len(calls) != len(expected_ids):
        errors.append(f"calls must contain exactly {len(expected_ids)} entries, found {len(calls)}")

    seen: set[int] = set()
    for index, call in enumerate(calls):
        if not isinstance(call, dict):
            errors.append(f"calls[{index}] must be an object")
            continue
        call_id = call.get("call_id")
        expected_call_id = expected_ids[index] if index < len(expected_ids) else index
        if call_id != expected_call_id:
            errors.append(f"calls[{index}] call_id must be {expected_call_id}, found {call_id!r}")
        if isinstance(call_id, int):
            if call_id in seen:
                errors.append(f"duplicate call_id {call_id}")
            seen.add(call_id)
        call_label = call.get("call_label")
        if call_label != f"CALL {call_id:02d}":
            errors.append(f"call {call_id} call_label must be CALL {call_id:02d}, found {call_label!r}")
        part = call.get("part")
        if call_id is not None:
            expected_part = 1 if call_id <= 30 else 2 if call_id <= 60 else 3
            if part != expected_part:
                errors.append(f"call {call_id} part must be {expected_part}, found {part!r}")
        status = call.get("status")
        if status not in STATUSES:
            errors.append(f"call {call_id} has invalid status {status!r}")
        if not isinstance(call.get("title"), str) or not call.get("title"):
            errors.append(f"call {call_id} title must be non-empty")
        prompt = call.get("prompt")
        placeholder = call.get("placeholder")
        if not isinstance(prompt, str):
            errors.append(f"call {call_id} prompt must be a string")
        if not isinstance(call.get("Pro_output"), str):
            errors.append(f"call {call_id} Pro_output must be a string")
        if placeholder not in (True, False):
            errors.append(f"call {call_id} placeholder must be boolean")
        if placeholder is True and prompt != "":
            errors.append(f"call {call_id} placeholder prompt must be empty")
        if placeholder is False and not prompt:
            errors.append(f"call {call_id} populated call prompt must be non-empty")
        for list_field in ("depends_on", "codex_evidence", "events"):
            if not isinstance(call.get(list_field), list):
                errors.append(f"call {call_id} {list_field} must be a list")
    return errors


def validate_output_text(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(f"secret-like content matched {pattern.pattern}")
    return findings


def status_counts(registry: dict[str, Any]) -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    for call in registry.get("calls", []):
        status = call.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def next_call(registry: dict[str, Any]) -> dict[str, Any] | None:
    for status in ("IN_PROGRESS", "PENDING", "BLOCKED"):
        for call in registry.get("calls", []):
            if call.get("status") == status:
                return call
    return None


def append_event(call: dict[str, Any], event: dict[str, Any]) -> None:
    events = call.setdefault("events", [])
    if not isinstance(events, list):
        raise ValueError(f"call {call.get('call_id')} events must be a list")
    events.append({"timestamp": utc_now(), **event})


def command_validate(args: argparse.Namespace) -> int:
    registry = load_json(Path(args.registry))
    errors = validate_registry(registry)
    payload = {
        "schema_version": "cento.patch_swarm.pro_call_registry.validation.v1",
        "registry": str(Path(args.registry)),
        "status": "fail" if errors else "pass",
        "counts": status_counts(registry),
        "errors": errors,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"{payload['status']}: {payload['counts']}")
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    return 1 if errors else 0


def command_stats(args: argparse.Namespace) -> int:
    registry = load_json(Path(args.registry))
    payload = {
        "schema_version": "cento.patch_swarm.pro_call_registry.stats.v1",
        "registry": str(Path(args.registry)),
        "calls": len(registry.get("calls", [])),
        "counts": status_counts(registry),
        "next": summarize_call(next_call(registry)),
    }
    print(json.dumps(payload, indent=2))
    return 0


def summarize_call(call: dict[str, Any] | None) -> dict[str, Any] | None:
    if call is None:
        return None
    return {
        "call_id": call.get("call_id"),
        "call_label": call.get("call_label"),
        "part": call.get("part"),
        "title": call.get("title"),
        "status": call.get("status"),
        "placeholder": call.get("placeholder"),
    }


def command_next(args: argparse.Namespace) -> int:
    registry = load_json(Path(args.registry))
    call = next_call(registry)
    if args.json:
        print(json.dumps({"next": summarize_call(call)}, indent=2))
    elif call is None:
        print("No actionable calls remain.")
    else:
        print(f"Call {call['call_id']}: {call['title']} [{call['status']}]")
    return 0


def command_ingest(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    registry = load_json(registry_path)
    errors = validate_registry(registry)
    if errors:
        raise SystemExit("registry validation failed before ingest:\n" + "\n".join(errors))
    text = Path(args.file).read_text(encoding="utf-8")
    findings = validate_output_text(text)
    call = call_by_id(registry, args.call_id)
    if findings and not args.allow_secret_like:
        append_event(
            call,
            {
                "actor": "pro-loop",
                "event": "pro_output_rejected",
                "previous_status": call.get("status"),
                "next_status": "BLOCKED",
                "findings": findings,
            },
        )
        call["status"] = "BLOCKED"
        registry["updated_at"] = utc_now()
        write_json(registry_path, registry)
        print(json.dumps({"status": "blocked", "findings": findings}, indent=2))
        return 2

    previous_status = call.get("status")
    call["Pro_output"] = text
    call["pro_output_received_at"] = utc_now()
    call["status"] = "IN_PROGRESS"
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else DEFAULT_EVIDENCE_ROOT / run_id()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    output_copy = evidence_dir / f"call-{args.call_id:03d}-pro-output.md"
    output_copy.write_text(text, encoding="utf-8")
    append_event(
        call,
        {
            "actor": "pro-loop",
            "event": "pro_output_ingested",
            "previous_status": previous_status,
            "next_status": "IN_PROGRESS",
            "evidence": str(output_copy.relative_to(ROOT)) if output_copy.is_relative_to(ROOT) else str(output_copy),
        },
    )
    registry["updated_at"] = utc_now()
    write_json(registry_path, registry)
    payload = {
        "status": "ingested",
        "call_id": args.call_id,
        "previous_status": previous_status,
        "next_status": "IN_PROGRESS",
        "evidence": str(output_copy),
    }
    print(json.dumps(payload, indent=2))
    return 0


def parse_prompt_title(text: str, call_id: int) -> str:
    pattern = re.compile(rf"^\s*#?\s*CALL\s+{call_id:02d}\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return f"CALL {call_id:02d} prompt"


def command_ingest_prompt(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    registry = load_json(registry_path)
    errors = validate_registry(registry)
    if errors:
        raise SystemExit("registry validation failed before prompt ingest:\n" + "\n".join(errors))
    text = Path(args.file).read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit("prompt file is empty")
    findings = validate_output_text(text)
    if findings and not args.allow_secret_like:
        print(json.dumps({"status": "blocked", "findings": findings}, indent=2))
        return 2

    call = call_by_id(registry, args.call_id)
    previous_placeholder = bool(call.get("placeholder"))
    call["prompt"] = text
    call["placeholder"] = False
    call["title"] = parse_prompt_title(text, args.call_id)
    call["summary"] = f"Operator-supplied prompt for CALL {args.call_id:02d}."
    append_event(
        call,
        {
            "actor": "pro-loop",
            "event": "prompt_ingested",
            "previous_placeholder": previous_placeholder,
            "next_placeholder": False,
        },
    )
    registry["updated_at"] = utc_now()
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else DEFAULT_EVIDENCE_ROOT / run_id()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    prompt_copy = evidence_dir / f"call-{args.call_id:03d}-prompt.md"
    prompt_copy.write_text(text, encoding="utf-8")
    call.setdefault("codex_evidence", []).append(str(prompt_copy.relative_to(ROOT)) if prompt_copy.is_relative_to(ROOT) else str(prompt_copy))
    write_json(registry_path, registry)
    print(
        json.dumps(
            {
                "status": "ingested",
                "call_id": args.call_id,
                "call_label": call.get("call_label"),
                "title": call.get("title"),
                "prompt_chars": len(text),
                "evidence": str(prompt_copy),
            },
            indent=2,
        )
    )
    return 0


def command_set_status(args: argparse.Namespace) -> int:
    registry_path = Path(args.registry)
    registry = load_json(registry_path)
    errors = validate_registry(registry)
    if errors:
        raise SystemExit("registry validation failed before status update:\n" + "\n".join(errors))
    call = call_by_id(registry, args.call_id)
    previous_status = call.get("status")
    next_status = args.status
    if next_status not in ALLOWED_TRANSITIONS.get(previous_status, set()) and not args.force:
        raise SystemExit(f"invalid transition {previous_status} -> {next_status}; use --force only for repair")
    call["status"] = next_status
    if args.note:
        call["notes"] = (str(call.get("notes") or "") + "\n" + args.note).strip()
    append_event(
        call,
        {
            "actor": "pro-loop",
            "event": "status_updated",
            "previous_status": previous_status,
            "next_status": next_status,
            "note": args.note or "",
            "forced": bool(args.force),
        },
    )
    registry["updated_at"] = utc_now()
    write_json(registry_path, registry)
    print(json.dumps({"status": "updated", "call_id": args.call_id, "previous_status": previous_status, "next_status": next_status}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patch Swarm Pro call registry helper")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="Path to patch-swarm Pro call registry JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate registry shape and lifecycle fields")
    validate.add_argument("--json", action="store_true", help="Print JSON validation payload")
    validate.set_defaults(func=command_validate)

    stats = sub.add_parser("stats", help="Print registry status counts")
    stats.set_defaults(func=command_stats)

    next_parser = sub.add_parser("next", help="Print next actionable call")
    next_parser.add_argument("--json", action="store_true", help="Print JSON output")
    next_parser.set_defaults(func=command_next)

    ingest = sub.add_parser("ingest-pro-output", help="Save Pro model output and mark a call IN_PROGRESS")
    ingest.add_argument("--call-id", type=int, required=True)
    ingest.add_argument("--file", required=True, help="Markdown/text file containing the Pro output")
    ingest.add_argument("--evidence-dir", default="", help="Optional evidence directory for a copy of the output")
    ingest.add_argument("--allow-secret-like", action="store_true", help="Repair-only override for secret-like text detection")
    ingest.set_defaults(func=command_ingest)

    ingest_prompt = sub.add_parser("ingest-prompt", help="Save an operator-supplied call prompt without touching Pro_output")
    ingest_prompt.add_argument("--call-id", type=int, required=True)
    ingest_prompt.add_argument("--file", required=True, help="Markdown/text file containing the call prompt")
    ingest_prompt.add_argument("--evidence-dir", default="", help="Optional evidence directory for a copy of the prompt")
    ingest_prompt.add_argument("--allow-secret-like", action="store_true", help="Repair-only override for secret-like text detection")
    ingest_prompt.set_defaults(func=command_ingest_prompt)

    set_status = sub.add_parser("set-status", help="Update a call lifecycle status")
    set_status.add_argument("--call-id", type=int, required=True)
    set_status.add_argument("--status", choices=STATUSES, required=True)
    set_status.add_argument("--note", default="")
    set_status.add_argument("--force", action="store_true", help="Allow repair transitions outside the normal lifecycle")
    set_status.set_defaults(func=command_set_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
