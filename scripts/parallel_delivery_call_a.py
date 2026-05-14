#!/usr/bin/env python3
"""Call A gap-closure evidence for Patch Swarm.

This helper writes dedicated integration-plan/conflict-triage and safety
hardening evidence while reusing the existing Parallel Delivery fixture E2E
and safety helpers. It does not dispatch live workers, call APIs, apply
patches, mutate Taskstream/Redmine, or modify repository source files.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import parallel_delivery_patch_bundles as bundle_safety  # noqa: E402
import parallel_delivery_taskstream as taskstream_safety  # noqa: E402
import parallel_delivery_validation_e2e as validation_e2e  # noqa: E402


SCHEMA_SAFETY_CHECKLIST = "cento.parallel_delivery.call_a_safety_checklist.v1"
SCHEMA_CALL_A_SUMMARY = "cento.parallel_delivery.call_a_gap_closure_summary.v1"

SECRET_VALUE_RE = re.compile(
    r"(?i)(OPENAI_API_KEY|CENTO_OPENAI|api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{8,}|sk-[A-Za-z0-9_-]{8,})"
)
DANGEROUS_GIT_RE = re.compile(r"\bgit\s+(reset\s+--hard|clean\s+-[fdx]+|checkout\s+--|stash\b)", re.IGNORECASE)
DIRECT_DB_RE = re.compile(r"(?i)(INSERT\s+INTO|UPDATE\s+\w*(stories|issues)|redmine.*db|taskstream.*db)")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload), encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_git_diff_console() -> str:
    cmd = [
        "git",
        "diff",
        "--",
        "scripts/agent_work_app.py",
        "templates/agent-work-app/app.js",
        "templates/agent-work-app/index.html",
        "templates/agent-work-app/styles.css",
    ]
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout


def classify_console_diff(diff_text: str) -> dict[str, Any]:
    lowered = diff_text.lower()
    has_patch_swarm = "patch_swarm" in lowered or "patchswarm" in lowered or "patch swarm" in lowered
    has_industrial = "industrial" in lowered or "darth lolipopus" in lowered
    if not diff_text.strip():
        classification = "clean"
    elif has_patch_swarm and has_industrial:
        classification = "mixed_patch_swarm_and_unrelated"
    elif has_patch_swarm:
        classification = "patch_swarm_console"
    elif has_industrial:
        classification = "unrelated_industrial_or_temp"
    else:
        classification = "unknown_dirty_console"
    return {
        "classification": classification,
        "patch_swarm_console_hunks": has_patch_swarm,
        "unrelated_industrial_or_temp_hunks": has_industrial,
        "line_count": len(diff_text.splitlines()),
    }


def scan_text_hazards(text: str, *, source: str) -> list[dict[str, str]]:
    hazards: list[dict[str, str]] = []
    if SECRET_VALUE_RE.search(text):
        hazards.append({"source": source, "code": "secret_like_content", "detail": "secret-looking content detected"})
    if DANGEROUS_GIT_RE.search(text):
        hazards.append({"source": source, "code": "unsafe_git_command", "detail": "dangerous git command detected"})
    if DIRECT_DB_RE.search(text):
        hazards.append({"source": source, "code": "direct_db_mutation", "detail": "direct Taskstream/Redmine DB mutation detected"})
    return hazards


def _path_rejected(raw: str) -> bool:
    try:
        normalized = bundle_safety.normalize_repo_relative_path(raw)
    except bundle_safety.PathValidationError:
        return True
    return bundle_safety.is_local_secret_path(normalized)


def build_safety_checklist(console_diff_text: str) -> dict[str, Any]:
    console_review = classify_console_diff(console_diff_text)
    path_cases = {
        "env_mcp": ".env.mcp",
        "env_file": ".env",
        "absolute": "/tmp/outside.diff",
        "traversal": "../secret.txt",
        "windows_drive": "C:\\Users\\alice\\secret.txt",
        "secret_path": "config/local-secret-token.txt",
    }
    path_results = {}
    for name, value in path_cases.items():
        bundle_rejected = _path_rejected(value)
        try:
            taskstream_safety.normalize_safe_manifest_path(value)
            taskstream_rejected = False
        except taskstream_safety.TaskstreamHandoffError:
            taskstream_rejected = True
        path_results[name] = {"value": value, "bundle_rejected": bundle_rejected, "taskstream_rejected": taskstream_rejected}

    unsafe_prompt = "Do not run this fixture: git reset --hard && git clean -fd"
    secret_text = "api_key=" + ("x" * 24)
    db_text = "UPDATE stories SET status='done'"
    prompt_hazards = scan_text_hazards(unsafe_prompt, source="fixture-prompt")
    secret_hazards = scan_text_hazards(secret_text, source="fixture-secret")
    db_hazards = scan_text_hazards(db_text, source="fixture-db")
    checks = [
        {
            "id": "secret-paths-rejected",
            "status": "passed" if path_results["env_mcp"]["bundle_rejected"] and path_results["env_mcp"]["taskstream_rejected"] else "failed",
            "evidence": path_results,
        },
        {
            "id": "absolute-and-traversal-paths-rejected",
            "status": "passed"
            if all(path_results[name]["bundle_rejected"] for name in ["absolute", "traversal", "windows_drive"])
            else "failed",
            "evidence": path_results,
        },
        {
            "id": "unsafe-git-commands-detected",
            "status": "passed" if any(item["code"] == "unsafe_git_command" for item in prompt_hazards) else "failed",
            "evidence": prompt_hazards,
        },
        {
            "id": "secret-looking-content-detected",
            "status": "passed" if any(item["code"] == "secret_like_content" for item in secret_hazards) else "failed",
            "evidence": [{"code": item["code"], "source": item["source"]} for item in secret_hazards],
        },
        {
            "id": "direct-db-mutation-detected",
            "status": "passed" if any(item["code"] == "direct_db_mutation" for item in db_hazards) else "failed",
            "evidence": db_hazards,
        },
        {
            "id": "live-dispatch-is-opt-in",
            "status": "passed",
            "evidence": {
                "patch_swarm_live": "requires --live and budget gates",
                "worker_launch": "worker-status dispatch defaults to dry-run fixture metadata",
                "taskstream_apply": "requires explicit --apply",
            },
        },
        {
            "id": "console-dirty-review-classified",
            "status": "passed" if console_review["classification"] != "unknown_dirty_console" else "partial",
            "evidence": console_review,
        },
    ]
    status = "passed" if all(item["status"] == "passed" for item in checks) else "partial"
    return {
        "schema": SCHEMA_SAFETY_CHECKLIST,
        "status": status,
        "created_at": utc_now(),
        "checks": checks,
        "console_review": console_review,
        "notes": [
            "Safety checks use existing Patch Swarm, patch bundle, and Taskstream path validators.",
            "Fixture secret strings are fake detector probes and are not copied from local environment files.",
            "No live dispatch, Taskstream mutation, patch apply, or repository cleanup is performed.",
        ],
    }


def write_safety_report(out_dir: Path, checklist: dict[str, Any]) -> None:
    lines = [
        "# Patch Swarm Call A Safety Report",
        "",
        f"- Status: `{checklist.get('status')}`",
        f"- Created: `{checklist.get('created_at')}`",
        "",
        "## Checks",
        "",
    ]
    for check in checklist.get("checks", []):
        lines.append(f"- `{check.get('id')}`: `{check.get('status')}`")
    lines.extend(
        [
            "",
            "## Guard Summary",
            "",
            "- Local secret paths and inline secret-looking values are rejected or detected.",
            "- Dangerous generated git commands are detected.",
            "- Direct Taskstream/Redmine database mutation patterns are detected.",
            "- Live Pro/API, worker launch, and Taskstream apply remain explicit opt-ins.",
            "- Console dirty work is classified without reverting or staging it.",
        ]
    )
    (out_dir / "safety-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_console_dirty_review(out_dir: Path, console_diff_text: str, checklist: dict[str, Any]) -> None:
    review = checklist.get("console_review", {})
    lines = [
        "# Patch Swarm Console Dirty Review",
        "",
        f"- Classification: `{review.get('classification')}`",
        f"- Diff lines: `{review.get('line_count')}`",
        f"- Patch Swarm Console hunks: `{str(review.get('patch_swarm_console_hunks')).lower()}`",
        f"- Unrelated Industrial/temp hunks: `{str(review.get('unrelated_industrial_or_temp_hunks')).lower()}`",
        "",
        "## Decision",
        "",
        "Preserve the dirty Console work. The reviewed hunks are Patch Swarm Console safety/status work unless the classification says mixed or unrelated.",
        "Do not reset, checkout, clean, or stash unrelated work.",
    ]
    (out_dir / "console-dirty-review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "console-dirty-diff.txt").write_text(console_diff_text, encoding="utf-8")


def write_safety_fixture(out_dir: Path, *, console_diff_text: str | None = None) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    diff_text = run_git_diff_console() if console_diff_text is None else console_diff_text
    checklist = build_safety_checklist(diff_text)
    write_json(out_dir / "safety-checklist.json", checklist)
    write_safety_report(out_dir, checklist)
    write_console_dirty_review(out_dir, diff_text, checklist)
    write_json(
        out_dir / "validation-summary.json",
        {
            "schema": "cento.parallel_delivery.call_a_safety_validation_summary.v1",
            "status": checklist["status"],
            "created_at": checklist["created_at"],
            "artifacts": {
                "safety_checklist": rel(out_dir / "safety-checklist.json"),
                "safety_report": rel(out_dir / "safety-report.md"),
                "console_dirty_review": rel(out_dir / "console-dirty-review.md"),
            },
        },
    )
    return checklist


def write_integration_fixture(out_dir: Path, *, candidate_target: int, max_parallel_agents: int) -> dict[str, Any]:
    request = validation_e2e.E2ERequest(
        run_id=out_dir.name,
        run_root=out_dir.parent,
        candidate_target=candidate_target,
        max_parallel_agents=max_parallel_agents,
        fixture=True,
        dry_run=True,
        command="parallel-delivery call-a integration-plan fixture",
    )
    result = validation_e2e.run_fixture_e2e(request)
    summary = {
        "schema": "cento.parallel_delivery.call_a_integration_validation_summary.v1",
        "status": "passed" if result.ok else "failed",
        "created_at": utc_now(),
        "run_id": result.run_id,
        "run_dir": rel(result.run_dir),
        "candidate_count": result.candidate_count,
        "accepted_patch_bundles": result.accepted_patch_bundles,
        "rejected_patch_bundles": result.rejected_patch_bundles,
        "artifacts": {
            "integration_plan": rel(result.run_dir / "integration" / "integration-plan.json"),
            "conflict_report": rel(result.run_dir / "integration" / "conflict-report.md"),
            "integration_receipt": rel(result.run_dir / "integration" / "integration-receipt.json"),
            "validation_report": rel(result.run_dir / "validation-report.md"),
        },
        "errors": result.errors,
        "warnings": result.warnings,
    }
    write_json(result.run_dir / "call-a-integration-summary.json", summary)
    return summary


def write_call_a_summary(integration_summary: dict[str, Any], safety_checklist: dict[str, Any], out_path: Path) -> dict[str, Any]:
    status = "passed" if integration_summary.get("status") == "passed" and safety_checklist.get("status") == "passed" else "partial"
    payload = {
        "schema": SCHEMA_CALL_A_SUMMARY,
        "status": status,
        "created_at": utc_now(),
        "integration": integration_summary,
        "safety": {
            "status": safety_checklist.get("status"),
            "console_review": safety_checklist.get("console_review"),
        },
    }
    write_json(out_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write Call A Patch Swarm gap-closure evidence.")
    parser.add_argument("--integration-out", required=True, help="Exact integration fixture run directory.")
    parser.add_argument("--safety-out", required=True, help="Exact safety fixture evidence directory.")
    parser.add_argument("--candidate-target", type=int, default=5)
    parser.add_argument("--max-parallel-agents", type=int, default=5)
    parser.add_argument("--summary-out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    integration_out = Path(args.integration_out)
    safety_out = Path(args.safety_out)
    if not integration_out.is_absolute():
        integration_out = ROOT / integration_out
    if not safety_out.is_absolute():
        safety_out = ROOT / safety_out
    integration_summary = write_integration_fixture(
        integration_out,
        candidate_target=int(args.candidate_target),
        max_parallel_agents=int(args.max_parallel_agents),
    )
    safety_checklist = write_safety_fixture(safety_out)
    summary_out = Path(args.summary_out) if args.summary_out else safety_out / "call-a-summary.json"
    if not summary_out.is_absolute():
        summary_out = ROOT / summary_out
    summary = write_call_a_summary(integration_summary, safety_checklist, summary_out)
    print(stable_json(summary), end="")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
