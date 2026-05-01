#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RUN_ROOT = ROOT / "workspace" / "runs" / "validator-tier0"
DEFAULT_TIMEOUT_SECONDS = 20


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve_path(value: str, base: Path | None = None) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    if base is not None:
        candidate = base / path
        if candidate.exists():
            return candidate
    return ROOT / path


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_field(data: Any, field: str) -> tuple[bool, Any]:
    cursor = data
    for part in field.split("."):
        if isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            return False, None
    return True, cursor


def status_for_checks(checks: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    required = [item for item in checks if item.get("required", True)]
    failed = [item for item in required if item["status"] == "failed"]
    missing = [item for item in required if item["status"] == "missing"]
    blocked = [item for item in required if item["status"] == "blocked"]
    if blocked:
        return "blocked", f"{len(blocked)} check(s) blocked validation", [item["name"] for item in blocked]
    if missing:
        return "blocked", f"{len(missing)} required evidence item(s) missing", [item["name"] for item in missing]
    if failed:
        return "needs_fix", f"{len(failed)} deterministic check(s) failed", [item["name"] for item in failed]
    return "approve", "All deterministic Tier 0 checks passed", []


def evaluate_file_exists(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    target = resolve_path(str(check.get("path", "")), manifest_dir)
    exists = target.exists()
    return {
        "evidence": rel(target),
        "observed": {"exists": exists},
        "status": "passed" if exists else "missing",
        "reason": "file exists" if exists else "file is missing",
    }


def evaluate_json_field(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    target = resolve_path(str(check.get("path", "")), manifest_dir)
    field = str(check.get("field", ""))
    if not target.exists():
        return {
            "evidence": rel(target),
            "observed": {"exists": False, "field": field},
            "status": "missing",
            "reason": "JSON file is missing",
        }
    try:
        data = read_json(target)
    except SystemExit as exc:
        return {
            "evidence": rel(target),
            "observed": {"exists": True, "field": field},
            "status": "failed",
            "reason": str(exc),
        }
    present, value = get_field(data, field)
    expected = check.get("expected")
    if not present:
        status = "missing"
        reason = "JSON field is missing"
    elif "expected" in check and value != expected:
        status = "failed"
        reason = f"JSON field value {value!r} did not equal {expected!r}"
    else:
        status = "passed"
        reason = "JSON field is present"
    return {
        "evidence": rel(target),
        "observed": {"exists": True, "field": field, "value": value if present else None},
        "status": status,
        "reason": reason,
    }


def evaluate_command(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    raw_command = check.get("command")
    if not raw_command:
        return {"evidence": "", "observed": {}, "status": "blocked", "reason": "command is missing"}

    cwd = resolve_path(str(check.get("cwd", ".")), manifest_dir)
    timeout = int(check.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    expected_exit = int(check.get("expect_exit", 0))
    shell = isinstance(raw_command, str)
    command = raw_command if shell else [str(item) for item in raw_command]
    printable = raw_command if shell else " ".join(shlex.quote(item) for item in command)
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "evidence": printable,
            "observed": {"timeout_seconds": timeout},
            "status": "failed",
            "reason": f"command timed out after {timeout}s",
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    return {
        "evidence": printable,
        "observed": {
            "cwd": rel(cwd),
            "exit_code": completed.returncode,
            "stdout_tail": stdout[-600:],
            "stderr_tail": stderr[-600:],
        },
        "status": "passed" if completed.returncode == expected_exit else "failed",
        "reason": f"exit code {completed.returncode}, expected {expected_exit}",
    }


def evaluate_contains_text(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    target = resolve_path(str(check.get("path", "")), manifest_dir)
    needle = str(check.get("text") or check.get("contains") or "")
    case_sensitive = bool(check.get("case_sensitive", True))
    if not needle:
        return {"evidence": rel(target), "observed": {}, "status": "blocked", "reason": "text is missing"}
    if not target.exists():
        return {
            "evidence": rel(target),
            "observed": {"exists": False},
            "status": "missing",
            "reason": "text file is missing",
        }
    try:
        haystack = target.read_text(encoding=str(check.get("encoding") or "utf-8"), errors="replace")
    except OSError as exc:
        return {
            "evidence": rel(target),
            "observed": {"exists": True},
            "status": "failed",
            "reason": str(exc),
        }
    search_haystack = haystack if case_sensitive else haystack.lower()
    search_needle = needle if case_sensitive else needle.lower()
    found = search_needle in search_haystack
    return {
        "evidence": rel(target),
        "observed": {"exists": True, "case_sensitive": case_sensitive, "text_found": found},
        "status": "passed" if found else "failed",
        "reason": "text found" if found else "text not found",
    }


def evaluate_http_status(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    del manifest_dir
    url = str(check.get("url") or "")
    if not url:
        return {"evidence": "", "observed": {}, "status": "blocked", "reason": "url is missing"}
    timeout = int(check.get("timeout_seconds", 10))
    expected = int(check.get("expected_status", 200))
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            body = response.read(256)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "evidence": url,
            "observed": {"timeout_seconds": timeout},
            "status": "failed",
            "reason": str(exc),
        }
    return {
        "evidence": url,
        "observed": {"status": status, "body_sample": body.decode("utf-8", errors="replace")},
        "status": "passed" if status == expected else "failed",
        "reason": f"status {status}, expected {expected}",
    }


def evaluate_image_nonblank(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    target = resolve_path(str(check.get("path", "")), manifest_dir)
    if not target.exists():
        return {
            "evidence": rel(target),
            "observed": {"exists": False},
            "status": "missing",
            "reason": "image file is missing",
        }
    try:
        from PIL import Image
    except ImportError:
        return {
            "evidence": rel(target),
            "observed": {"exists": True},
            "status": "blocked",
            "reason": "Pillow is required for image_nonblank checks",
        }
    try:
        image = Image.open(target).convert("RGB")
        extrema = image.getextrema()
    except Exception as exc:  # noqa: BLE001 - corrupted image details belong in validation evidence.
        return {
            "evidence": rel(target),
            "observed": {"exists": True},
            "status": "failed",
            "reason": f"image could not be read: {exc}",
        }
    nonblank = any(channel_min != channel_max for channel_min, channel_max in extrema)
    return {
        "evidence": rel(target),
        "observed": {"exists": True, "size": list(image.size), "extrema": extrema},
        "status": "passed" if nonblank else "failed",
        "reason": "image has non-uniform pixels" if nonblank else "image appears blank",
    }


def evaluate_check(check: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    start = time.perf_counter()
    check_type = str(check.get("type", ""))
    name = str(check.get("name") or check_type or "unnamed-check")
    if check_type == "file_exists":
        result = evaluate_file_exists(check, manifest_dir)
    elif check_type == "json_field":
        result = evaluate_json_field(check, manifest_dir)
    elif check_type == "command":
        result = evaluate_command(check, manifest_dir)
    elif check_type == "contains_text":
        result = evaluate_contains_text(check, manifest_dir)
    elif check_type == "http_status":
        result = evaluate_http_status(check, manifest_dir)
    elif check_type == "image_nonblank":
        result = evaluate_image_nonblank(check, manifest_dir)
    else:
        result = {
            "evidence": "",
            "observed": {"type": check_type},
            "status": "blocked",
            "reason": f"unsupported check type: {check_type or 'missing'}",
        }
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    return {
        "name": name,
        "type": check_type,
        "required": bool(check.get("required", True)),
        "duration_ms": duration_ms,
        **result,
    }


def load_manifest(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f"Manifest must be a JSON object: {path}")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        raise SystemExit(f"Manifest must include a non-empty checks array: {path}")
    return data


def markdown_summary(packet: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        "# Tier 0 Validation Summary",
        "",
        f"- Task: `{packet['task']}`",
        f"- Claim: {packet['claim']}",
        f"- Risk: `{packet['risk']}`",
        f"- Decision: `{result['decision']}`",
        f"- Reason: {result['reason']}",
        f"- Validator tier: `{result['validator_tier']}`",
        f"- AI calls used: `{result['ai_calls_used']}`",
        f"- Estimated AI cost: `{result['estimated_ai_cost']}`",
        f"- Total duration: `{result['stats']['total_duration_ms']} ms`",
        f"- Automation coverage: `{result['stats'].get('automation_coverage_percent', 0)}%`",
        f"- Manual review items: `{result['stats'].get('manual_review_count', 0)}`",
        "",
        "## Checks",
        "",
        "| Check | Type | Status | Duration | Reason | Evidence |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in result["checks"]:
        lines.append(
            f"| {item['name']} | {item['type']} | {item['status']} | "
            f"{item['duration_ms']} ms | {item['reason']} | `{item['evidence']}` |"
        )
    lines.extend(
        [
            "",
            "## Mandatory Timing Stats",
            "",
            "```json",
            json.dumps(result["stats"], indent=2, sort_keys=True),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_manifest(manifest_path: Path, run_dir: Path | None = None) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = load_manifest(manifest_path)
    manifest_dir = manifest_path.parent
    started_at = now_iso()
    total_start = time.perf_counter()
    task = str(manifest.get("task") or manifest_path.stem)
    safe_task = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in task).strip("-") or "task"
    if run_dir is None:
        run_dir = RUN_ROOT / safe_task
    run_dir.mkdir(parents=True, exist_ok=True)

    check_results = [evaluate_check(check, manifest_dir) for check in manifest["checks"]]
    decision, reason, missing_evidence = status_for_checks(check_results)
    ended_at = now_iso()
    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 3)
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
    manual_review = manifest.get("manual_review") if isinstance(manifest.get("manual_review"), list) else []
    stats = {
        "started_at": started_at,
        "ended_at": ended_at,
        "total_duration_ms": total_duration_ms,
        "checks_executed": len(check_results),
        "checks_passed": sum(1 for item in check_results if item["status"] == "passed"),
        "checks_failed": sum(1 for item in check_results if item["status"] == "failed"),
        "checks_missing": sum(1 for item in check_results if item["status"] == "missing"),
        "checks_blocked": sum(1 for item in check_results if item["status"] == "blocked"),
        "manual_review_count": len(manual_review),
        "automation_coverage_percent": coverage.get("automation_coverage_percent", 100 if check_results and not manual_review else 0),
        "check_durations_ms": {item["name"]: item["duration_ms"] for item in check_results},
    }
    packet = {
        "schema": "cento.validation-packet.v1",
        "task": task,
        "claim": str(manifest.get("claim") or ""),
        "risk": str(manifest.get("risk") or "low"),
        "checks": check_results,
        "decision_requested": str(manifest.get("decision_requested") or "approve"),
        "created_at": started_at,
        "source_manifest": rel(manifest_path),
    }
    result = {
        "schema": "cento.validation-result.v1",
        "task": task,
        "decision": decision,
        "reason": reason,
        "missing_evidence": missing_evidence,
        "validator_tier": "tier0",
        "ai_calls_used": 0,
        "estimated_ai_cost": 0,
        "escalation_reason": "" if decision == "approve" else reason,
        "manual_review": manual_review,
        "checks": check_results,
        "stats": stats,
        "outputs": {
            "packet": rel(run_dir / "validation-packet.json"),
            "result": rel(run_dir / "validation-result.json"),
            "summary": rel(run_dir / "validation-summary.md"),
            "stats": rel(run_dir / "stats.json"),
        },
    }
    write_json(run_dir / "validation-packet.json", packet)
    write_json(run_dir / "validation-result.json", result)
    write_json(run_dir / "stats.json", stats)
    (run_dir / "validation-summary.md").write_text(markdown_summary(packet, result), encoding="utf-8")
    return result


def story_payload() -> dict[str, Any]:
    return {
        "schema": "cento.validator-tier0.stories.v1",
        "created_at": now_iso(),
        "budget": {
            "implementation_cap_minutes": 60,
            "runtime_ai_calls_for_tier0": 0,
            "runtime_ai_cost_for_tier0": 0,
        },
        "stories": [
            {
                "id": "AI-VAL-001",
                "title": "Create minimal validation packet format",
                "acceptance": "A low-risk task has task, claim, risk, checks, requested decision, timestamp, and source manifest.",
            },
            {
                "id": "AI-VAL-002",
                "title": "Evaluate deterministic Tier 0 checks",
                "acceptance": "file_exists, command, json_field, contains_text, http_status, and image_nonblank checks return passed, failed, missing, or blocked.",
            },
            {
                "id": "AI-VAL-003",
                "title": "Emit mandatory timing and AI budget stats",
                "acceptance": "Each run records total_duration_ms, per-check duration_ms, ai_calls_used, and estimated_ai_cost.",
            },
            {
                "id": "AI-VAL-004",
                "title": "Prove E2E with pass and fail examples",
                "acceptance": "One passing sample approves and one failing sample returns a non-approve decision with reason.",
            },
            {
                "id": "AI-VAL-005",
                "title": "Generate Draft Manifests Conservatively",
                "acceptance": "Feature interpretation may generate draft Tier 0 manifests, but only explicit artifacts and commands become deterministic checks.",
            },
            {
                "id": "AI-VAL-006",
                "title": "Gate Dispatch With Preflight",
                "acceptance": "agent-work preflight blocks missing validation drafts, unresolved manual review, and automation coverage below the configured threshold.",
            },
        ],
    }


def command_stories(args: argparse.Namespace) -> int:
    output = resolve_path(args.output) if args.output else RUN_ROOT / "stories.json"
    payload = story_payload()
    write_json(output, payload)
    md = output.with_suffix(".md")
    lines = ["# Validator Tier 0 Stories", ""]
    lines.append(f"- Implementation cap: `{payload['budget']['implementation_cap_minutes']} minutes`")
    lines.append(f"- Runtime AI calls for Tier 0: `{payload['budget']['runtime_ai_calls_for_tier0']}`")
    lines.append("")
    for story in payload["stories"]:
        lines.extend([f"## {story['id']}: {story['title']}", "", story["acceptance"], ""])
    md.write_text("\n".join(lines), encoding="utf-8")
    print(rel(output))
    print(rel(md))
    return 0


def write_sample_manifests(run_dir: Path) -> tuple[Path, Path]:
    sample_dir = run_dir / "sample-data"
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_json = sample_dir / "sample.json"
    sample_text = sample_dir / "sample.html"
    write_json(sample_json, {"status": "ready", "nested": {"ok": True}})
    sample_text.write_text("<html><body><section>No-model validation ready</section></body></html>\n", encoding="utf-8")
    pass_manifest = run_dir / "sample-pass.json"
    fail_manifest = run_dir / "sample-fail.json"
    write_json(
        pass_manifest,
        {
            "task": "AI-VAL-E2E-PASS",
            "claim": "Tier 0 validator approves complete deterministic evidence.",
            "risk": "low",
            "checks": [
                {"name": "sample-json-exists", "type": "file_exists", "path": "sample-data/sample.json"},
                {"name": "sample-json-ready", "type": "json_field", "path": "sample-data/sample.json", "field": "status", "expected": "ready"},
                {"name": "sample-html-text", "type": "contains_text", "path": "sample-data/sample.html", "text": "No-model validation ready"},
                {"name": "json-load-command", "type": "command", "cwd": ".", "command": ["python3", "-m", "json.tool", "sample-data/sample.json"]},
            ],
        },
    )
    write_json(
        fail_manifest,
        {
            "task": "AI-VAL-E2E-FAIL",
            "claim": "Tier 0 validator rejects missing deterministic evidence.",
            "risk": "low",
            "checks": [
                {"name": "missing-file", "type": "file_exists", "path": "sample-data/missing.json"},
                {"name": "sample-json-not-done", "type": "json_field", "path": "sample-data/sample.json", "field": "status", "expected": "done"},
            ],
        },
    )
    return pass_manifest, fail_manifest


def command_run(args: argparse.Namespace) -> int:
    manifest = resolve_path(args.manifest)
    run_dir = resolve_path(args.run_dir) if args.run_dir else None
    result = run_manifest(manifest, run_dir)
    print(json.dumps({"decision": result["decision"], "reason": result["reason"], "outputs": result["outputs"], "stats": result["stats"]}, indent=2, sort_keys=True))
    return 0 if result["decision"] == "approve" else 2


def command_e2e(args: argparse.Namespace) -> int:
    run_dir = resolve_path(args.run_dir) if args.run_dir else RUN_ROOT / f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    total_start = time.perf_counter()
    command_stories(argparse.Namespace(output=str(run_dir / "stories.json")))
    pass_manifest, fail_manifest = write_sample_manifests(run_dir)
    pass_result = run_manifest(pass_manifest, run_dir / "pass")
    fail_result = run_manifest(fail_manifest, run_dir / "fail")
    total_duration_ms = round((time.perf_counter() - total_start) * 1000, 3)
    summary = {
        "schema": "cento.validator-tier0.e2e.v1",
        "run_dir": rel(run_dir),
        "started_at": pass_result["stats"]["started_at"],
        "ended_at": now_iso(),
        "total_duration_ms": total_duration_ms,
        "ai_calls_used": pass_result["ai_calls_used"] + fail_result["ai_calls_used"],
        "estimated_ai_cost": pass_result["estimated_ai_cost"] + fail_result["estimated_ai_cost"],
        "pass_decision": pass_result["decision"],
        "fail_decision": fail_result["decision"],
        "passed": pass_result["decision"] == "approve" and fail_result["decision"] != "approve",
        "outputs": {
            "stories": rel(run_dir / "stories.json"),
            "pass_result": pass_result["outputs"]["result"],
            "fail_result": fail_result["outputs"]["result"],
            "summary": rel(run_dir / "e2e-summary.json"),
        },
    }
    write_json(run_dir / "e2e-summary.json", summary)
    (run_dir / "e2e-summary.md").write_text(
        "\n".join(
            [
                "# Validator Tier 0 E2E",
                "",
                f"- Passed: `{summary['passed']}`",
                f"- Pass decision: `{summary['pass_decision']}`",
                f"- Fail decision: `{summary['fail_decision']}`",
                f"- AI calls used: `{summary['ai_calls_used']}`",
                f"- Estimated AI cost: `{summary['estimated_ai_cost']}`",
                f"- Total E2E duration: `{summary['total_duration_ms']} ms`",
                "",
                "## Outputs",
                "",
                f"- Stories: `{summary['outputs']['stories']}`",
                f"- Pass result: `{summary['outputs']['pass_result']}`",
                f"- Fail result: `{summary['outputs']['fail_result']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Cento Tier 0 deterministic validation packets with mandatory timing stats.")
    sub = parser.add_subparsers(dest="command", required=True)

    stories = sub.add_parser("stories", help="Write tiny implementation stories for the one-hour Tier 0 slice.")
    stories.add_argument("--output", default="", help="Output JSON path. Markdown is written beside it.")
    stories.set_defaults(func=command_stories)

    run = sub.add_parser("run", help="Evaluate one validation manifest.")
    run.add_argument("manifest", help="Validation manifest JSON path.")
    run.add_argument("--run-dir", default="", help="Output run directory.")
    run.set_defaults(func=command_run)

    e2e = sub.add_parser("e2e", help="Create stories, sample manifests, and run pass/fail Tier 0 validation.")
    e2e.add_argument("--run-dir", default="", help="Output run directory.")
    e2e.set_defaults(func=command_e2e)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
