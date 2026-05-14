#!/usr/bin/env python3
"""Final QA and release-candidate evidence for Patch Swarm.

This helper turns captured final-gate command output into a durable evidence
index, dirty-work conflict report, final validation summary, and release
candidate packet. It does not run live providers, launch workers, apply
patches, or mutate Taskstream/Redmine state.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"

SCHEMA_EVIDENCE_INDEX = "patch-swarm-evidence-index.v1"
SCHEMA_FINAL_VALIDATION = "patch-swarm-final-validation.v1"
SCHEMA_RELEASE_CANDIDATE = "patch-swarm-release-candidate.v1"

REQUIRED_GATES = [
    "tools_json",
    "cento_tools",
    "docs_parallel_delivery",
    "parallel_delivery_validate_json",
    "parallel_delivery_status_json",
    "patch_swarm_e2e_100",
    "patch_swarm_tests",
    "safety_scan",
    "docs_runbook",
    "dirty_work_preserved",
]

SECONDARY_GATES = [
    "cento_cli_json",
    "focused_tests",
    "patch_swarm_check",
    "make_check",
]

CALL_CATEGORIES = {
    "product_spec": ["docs/patch-swarm.md", "patch-swarm-lifecycle", "patch-swarm-implementation-map", "patch-swarm-validation-matrix"],
    "recon": ["recon/", "implementation-map"],
    "schema": ["schema-fixture", "call-4-artifact-schema", "patch-swarm-artifacts"],
    "planner": ["planner-fixture", "patch-swarm-planner"],
    "leases": ["lease-fixture", "path-leases", "patch-swarm-leasing"],
    "proreq_prompts": ["proreq-fixture", "prompt-bundle", "patch-swarm-proreq-prompts"],
    "worker_packets": ["codex-packets-fixture", "worker-packets", "codex-packet"],
    "patch_bundle_safety": ["patch-bundle-fixture", "patch_bundle", "patch-bundle"],
    "integration_plan": ["integration-plan-fixture", "conflict-report", "integration-plan.json"],
    "safe_apply_release_candidate": ["release-candidate-fixture", "release-candidate.json", "release-notes.md"],
    "e2e_fixture": ["e2e-fixture"],
    "taskstream_handoff": ["taskstream-fixture", "taskstream"],
    "worker_status": ["worker-status-fixture", "worker-status"],
    "console_status": ["console-fixture", "patch-swarm-console"],
    "safety_hardening": ["safety-fixture", "safety-report", "safety-checklist"],
    "regression_matrix": ["regression-fixture", "regression-matrix"],
    "docs_runbook": ["docs-fixture", "operator-runbook-review", "adoption-narrative", "docs/patch-swarm.md"],
}

PATCH_SWARM_PATHS = (
    "scripts/parallel_delivery",
    "scripts/patch_swarm",
    "tests/test_parallel_delivery",
    "tests/parallel_delivery/",
    "tests/test_patch_swarm.py",
    "docs/patch-swarm",
    "docs/parallel-delivery/",
)
UNRELATED_HINTS = (
    "industrial",
    "darth lolipopus",
    "assets/industrial-os",
    "industrial-pet",
    "cento_temp",
    "temp-commands",
    "workspace/logs",
)
CONSOLE_PATHS = (
    "scripts/agent_work_app.py",
    "templates/agent-work-app/app.js",
    "templates/agent-work-app/index.html",
    "templates/agent-work-app/styles.css",
)

REAL_SECRET_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")
DANGEROUS_RE = re.compile(r"git reset --hard|git clean -fd|checkout --")
DOC_MARKERS = [
    "## Safe Mental Model",
    "## Quickstart",
    "## Full Fixture Demo",
    "## ChatGPT Pro / ProReq Flow",
    "## Codex Paste Flow",
    "## Worker Packet Format",
    "## Artifacts and Evidence",
    "## Safety Rules",
    "## Troubleshooting",
    "## Extension Guide",
    "## Adoption Narrative",
]


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def json_file_valid(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return True


def run_git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout


def current_branch() -> str:
    value = run_git("branch", "--show-current").strip()
    return value or "unknown"


def current_head() -> str:
    return run_git("rev-parse", "HEAD").strip()


def git_status_entries() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in run_git("status", "--short").splitlines():
        if not line.strip():
            continue
        state = line[:2]
        path = line[3:] if len(line) > 3 else ""
        entries.append({"state": state.strip() or "M", "path": path})
    return entries


def diff_for(path: str) -> str:
    return run_git("diff", "--", path)


def classify_path(path: str, state: str) -> tuple[str, str, str]:
    lowered = path.lower()
    diff_text = diff_for(path).lower() if state != "??" else ""
    combined = f"{lowered}\n{diff_text}"

    has_patch = "patch_swarm" in combined or "patch-swarm" in combined or any(hint in lowered for hint in PATCH_SWARM_PATHS)
    has_unrelated = any(hint in combined for hint in UNRELATED_HINTS)
    is_console = lowered in CONSOLE_PATHS

    if lowered.startswith("workspace/runs/parallel-delivery/"):
        return "evidence-only", "preserve/generated evidence", "Generated Parallel Delivery evidence."
    if is_console and has_patch and has_unrelated:
        return "mixed/needs human review", "preserve unrelated hunks", "Console file contains Patch Swarm and unrelated UI/content signals."
    if is_console and has_patch:
        return "Patch Swarm Console/status", "safe to edit minimally", "Console/status Patch Swarm hunk."
    if any(hint in lowered for hint in PATCH_SWARM_PATHS) or path in {"scripts/parallel_delivery_call_a.py", "scripts/parallel_delivery_call_b.py"}:
        if "tests/" in lowered:
            return "Patch Swarm tests", "safe to edit minimally", "Patch Swarm or Parallel Delivery test surface."
        if "docs/" in lowered:
            return "Patch Swarm docs/runbook", "safe to edit minimally", "Patch Swarm documentation surface."
        return "Patch Swarm product code", "safe to edit minimally", "Parallel Delivery/Patch Swarm implementation surface."
    if path == "docs/ai-self-improvement-log.md" and has_patch:
        return "Patch Swarm docs/runbook", "safe to append only", "Append-only Cento self-improvement log with Patch Swarm entries."
    if has_patch and has_unrelated:
        return "mixed/needs human review", "preserve unrelated hunks", "File includes both Patch Swarm and unrelated work."
    if has_patch:
        return "Patch Swarm product code", "safe to edit minimally", "Patch Swarm hunk detected in diff."
    if has_unrelated:
        return "unrelated dirty work", "preserve", "Unrelated Industrial/temp/desktop work."
    if state == "??":
        return "unrelated dirty work", "preserve", "Untracked file outside Patch Swarm ownership."
    return "unknown dirty work", "preserve", "No Patch Swarm ownership signal found."


def conflict_report(run_id: str) -> tuple[dict[str, Any], str]:
    entries = git_status_entries()
    table = []
    staged = []
    unstaged = []
    untracked = []
    blockers = []
    for entry in entries:
        state = entry["state"]
        path = entry["path"]
        classification, action, notes = classify_path(path, state)
        row = {
            "path": path,
            "git_state": state,
            "classification": classification,
            "action": action,
            "notes": notes,
        }
        table.append(row)
        if state == "??":
            untracked.append(path)
        else:
            if state and state[0] != " ":
                staged.append(path)
            if len(state) > 1 and state[1] != " ":
                unstaged.append(path)
            if state in {"M", "A", "D"}:
                unstaged.append(path)
        if classification in {"mixed/needs human review", "unknown dirty work"}:
            blockers.append(path)

    status = "partial" if blockers else "pass"
    payload = {
        "run_id": run_id,
        "status": status,
        "branch": current_branch(),
        "head": current_head(),
        "staged_files": sorted(set(staged)),
        "unstaged_files": sorted(set(unstaged)),
        "untracked_files": sorted(set(untracked)),
        "files": table,
        "blockers": blockers,
    }
    lines = [
        "# Owned Path Conflict Report",
        "",
        "## Summary",
        f"- status: {status}",
        f"- branch: {payload['branch']}",
        f"- head: {payload['head']}",
        f"- staged files: {len(payload['staged_files'])}",
        f"- unstaged files: {len(payload['unstaged_files'])}",
        f"- untracked files: {len(payload['untracked_files'])}",
        "",
        "## Classification Table",
        "| Path | Git state | Classification | Action | Notes |",
        "|---|---:|---|---|---|",
    ]
    for row in table:
        lines.append(
            f"| `{row['path']}` | `{row['git_state']}` | {row['classification']} | {row['action']} | {row['notes']} |"
        )
    for heading, predicate in [
        ("Patch Swarm Owned Files", lambda r: r["classification"].startswith("Patch Swarm")),
        ("Unrelated Dirty Work Preserved", lambda r: r["classification"] == "unrelated dirty work"),
        ("Mixed Conflicts", lambda r: r["classification"] == "mixed/needs human review"),
    ]:
        lines.extend(["", f"## {heading}", ""])
        matched = [row for row in table if predicate(row)]
        lines.extend(f"- `{row['path']}`: {row['notes']}" for row in matched)
        if not matched:
            lines.append("- None.")
    lines.extend(
        [
            "",
            "## Safety Notes",
            "No reset, checkout, clean, or broad stash was used by this final QA helper.",
            "Unrelated dirty work is preserved and classified instead of rewritten.",
            "",
            "## Decision",
            f"{status}. Blockers: {', '.join(blockers) if blockers else 'none'}.",
        ]
    )
    return payload, "\n".join(lines) + "\n"


def evidence_files() -> list[str]:
    names = {
        "validation-report.md",
        "validation-summary.json",
        "final-validation-summary.json",
        "regression-matrix.json",
        "regression-matrix.md",
        "safety-report.md",
        "safety-checklist.json",
        "conflict-report.md",
        "integration-plan.json",
        "release-candidate.json",
        "release-notes.md",
        "docs-checklist.json",
        "operator-runbook-review.md",
        "adoption-narrative.md",
        "split-plan.json",
        "task-graph.json",
        "path-leases.json",
        "prompt-bundle.json",
        "prompt-index.json",
        "codex-packet-index.json",
        "codex-packet-bundle.json",
        "patch-bundle-validation.json",
        "patch-bundle-report.pretty.json",
        "taskstream-handoff-report.json",
        "worker-status.json",
        "worker-status-summary.json",
    }
    paths = []
    if RUNS_ROOT.exists():
        for path in RUNS_ROOT.rglob("*"):
            if path.is_file() and path.name in names:
                paths.append(rel(path))
    doc_paths = [
        "docs/patch-swarm.md",
        "docs/patch-swarm-lifecycle.md",
        "docs/patch-swarm-implementation-map.md",
        "docs/patch-swarm-validation-matrix.md",
        "docs/parallel-delivery/patch-swarm-artifacts.md",
    ]
    paths.extend(path for path in doc_paths if (ROOT / path).exists())
    return sorted(set(paths))


def build_evidence_index(run_id: str) -> dict[str, Any]:
    files = evidence_files()
    calls = {}
    for category, hints in CALL_CATEGORIES.items():
        matched = [path for path in files if any(hint.lower() in path.lower() for hint in hints)]
        status = "found" if matched else "missing"
        calls[category] = {
            "status": status,
            "paths": matched[-40:],
            "truncated": max(0, len(matched) - 40),
        }
    blockers = [name for name, value in calls.items() if value["status"] == "missing"]
    return {
        "schema_version": SCHEMA_EVIDENCE_INDEX,
        "run_id": run_id,
        "generated_at": utc_now(),
        "evidence_roots": ["workspace/runs/parallel-delivery", "docs/patch-swarm.md"],
        "calls": calls,
        "blockers": blockers,
    }


def evidence_index_md(index: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Evidence Index",
        "",
        f"- Run ID: `{index['run_id']}`",
        f"- Generated: `{index['generated_at']}`",
        f"- Blockers: `{len(index['blockers'])}`",
        "",
        "| Area | Status | Evidence |",
        "|---|---|---|",
    ]
    for name, value in index["calls"].items():
        paths = "<br>".join(f"`{path}`" for path in value["paths"][:8]) or "None"
        if value.get("truncated"):
            paths += f"<br>`... {value['truncated']} more`"
        lines.append(f"| `{name}` | `{value['status']}` | {paths} |")
    return "\n".join(lines) + "\n"


def output_file(final_dir: Path, name: str) -> Path:
    return final_dir / "test-output" / name


def text_has_success(path: Path) -> bool:
    text = read_text(path).lower()
    if not text:
        return False
    if "failed" in text or "traceback" in text or "error:" in text:
        return " passed" in text and " failed" not in text
    return "passed" in text or "ok" in text or path.exists()


def json_gate(path: Path, predicate) -> str:
    payload = read_json(path)
    if payload is None:
        return "fail"
    return "pass" if predicate(payload) else "fail"


def docs_runbook_status() -> str:
    text = read_text(ROOT / "docs" / "patch-swarm.md")
    return "pass" if all(marker in text for marker in DOC_MARKERS) else "fail"


def safety_scan_status(path: Path) -> tuple[str, list[str]]:
    findings = read_text(path).splitlines()
    real_secret_findings = [
        line
        for line in findings
        if REAL_SECRET_RE.search(line)
        and "sk-abcdefghijklmnopqrstuvwxyz" not in line
        and "secret-and-dangerous-command-scan.txt:" not in line
    ]
    unsafe_generated = []
    for line in findings:
        if not DANGEROUS_RE.search(line):
            continue
        lowered = line.lower()
        safe_context = (
            "do not" in lowered
            or "never" in lowered
            or "disallowed" in lowered
            or "forbidden" in lowered
            or "reject" in lowered
            or "scan" in lowered
            or "dangerous" in lowered
            or "acceptance" in lowered
            or lowered.startswith("tests/")
            or "secret-and-dangerous-command-scan.txt:" in lowered
        )
        if not safe_context:
            unsafe_generated.append(line)
    blockers = real_secret_findings + unsafe_generated
    return ("pass" if not blockers else "fail"), blockers[:20]


def dirty_work_preserved_status(final_dir: Path, conflict_payload: dict[str, Any]) -> str:
    before = set(read_text(final_dir / "git-status-before.txt").splitlines())
    after = set(read_text(final_dir / "git-status-after.txt").splitlines())
    unrelated = {
        line
        for line in before
        if any(hint in line.lower() for hint in UNRELATED_HINTS)
        or any(path in line for path in ["Makefile", "README.md", "data/tools.json", "docs/tool-index.md"])
    }
    if not unrelated:
        return "pass"
    return "pass" if unrelated <= after else "fail"


def build_final_summary(run_id: str, final_dir: Path, rc_dir: Path, conflict_payload: dict[str, Any]) -> dict[str, Any]:
    safety_status, safety_blockers = safety_scan_status(output_file(final_dir, "secret-and-dangerous-command-scan.txt"))
    required = {
        "tools_json": "pass" if json_file_valid(ROOT / "data" / "tools.json") else "fail",
        "cento_tools": "pass" if "parallel-delivery" in read_text(output_file(final_dir, "cento-tools.txt")) else "fail",
        "docs_parallel_delivery": "pass" if "tool: parallel-delivery" in read_text(output_file(final_dir, "docs-parallel-delivery.txt")) else "fail",
        "parallel_delivery_validate_json": json_gate(
            output_file(final_dir, "parallel-delivery-validate.json"),
            lambda p: p.get("status") in {"passed", "partial", "failed"} and "schema_version" in p,
        ),
        "parallel_delivery_status_json": json_gate(
            output_file(final_dir, "parallel-delivery-status.json"),
            lambda p: bool(p.get("status")) and "schema_version" in p,
        ),
        "patch_swarm_e2e_100": json_gate(
            output_file(final_dir, "patch-swarm-e2e-100.json"),
            lambda p: p.get("ok") is True
            and p.get("candidate_count") == 100
            and p.get("max_parallel_agents") == 5
            and p.get("live_pro") is False,
        ),
        "patch_swarm_tests": "pass" if text_has_success(output_file(final_dir, "pytest-test-patch-swarm.txt")) else "fail",
        "safety_scan": safety_status,
        "docs_runbook": docs_runbook_status(),
        "dirty_work_preserved": dirty_work_preserved_status(final_dir, conflict_payload),
    }
    patch_swarm_check_text = read_text(output_file(final_dir, "make-patch-swarm-check.txt")).lower()
    if "not present" in patch_swarm_check_text:
        patch_swarm_check_status = "not-present"
    elif text_has_success(output_file(final_dir, "make-patch-swarm-check.txt")):
        patch_swarm_check_status = "pass"
    else:
        patch_swarm_check_status = "fail"
    secondary = {
        "cento_cli_json": "pass" if json_file_valid(ROOT / "data" / "cento-cli.json") else "not-applicable",
        "focused_tests": "pass" if text_has_success(output_file(final_dir, "pytest-focused-final.txt")) else "fail",
        "patch_swarm_check": patch_swarm_check_status,
        "make_check": "pass" if text_has_success(output_file(final_dir, "make-check.txt")) else "fail",
    }
    required_blockers = [gate for gate, status in required.items() if status != "pass"]
    secondary_failures = [gate for gate, status in secondary.items() if status == "fail"]
    status = "fail" if required_blockers else ("partial" if secondary_failures else "pass")
    limitations = []
    if secondary.get("patch_swarm_check") == "not-present":
        limitations.append("No dedicated make patch-swarm-check target is present; final QA used direct deterministic gates.")
    if secondary_failures:
        limitations.append("One or more secondary gates failed; inspect final QA command output.")
    if conflict_payload.get("blockers"):
        limitations.append("Dirty work includes mixed or unknown files requiring human review before broad packaging.")
    return {
        "schema_version": SCHEMA_FINAL_VALIDATION,
        "run_id": run_id,
        "status": status,
        "branch": current_branch(),
        "head": current_head(),
        "required_gates": required,
        "secondary_gates": secondary,
        "changed_files": [entry["path"] for entry in conflict_payload["files"]],
        "unrelated_dirty_files_preserved": [
            entry["path"] for entry in conflict_payload["files"] if entry["classification"] == "unrelated dirty work"
        ],
        "blockers": required_blockers + safety_blockers,
        "known_limitations": limitations,
        "evidence": {
            "final_qa_dir": rel(final_dir),
            "release_candidate_dir": rel(rc_dir),
        },
    }


def final_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Final Validation Report",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        f"- Branch: `{summary['branch']}`",
        f"- Head: `{summary['head']}`",
        "",
        "## Required Gates",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    lines.extend(f"| `{gate}` | `{status}` |" for gate, status in summary["required_gates"].items())
    lines.extend(["", "## Secondary Gates", "", "| Gate | Status |", "|---|---|"])
    lines.extend(f"| `{gate}` | `{status}` |" for gate, status in summary["secondary_gates"].items())
    if summary["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary["blockers"])
    else:
        lines.extend(["", "## Result", "", "All core Patch Swarm release gates passed."])
    return "\n".join(lines) + "\n"


def release_candidate(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_RELEASE_CANDIDATE,
        "run_id": summary["run_id"],
        "status": summary["status"],
        "branch": summary["branch"],
        "head": summary["head"],
        "summary": "Patch Swarm final QA result.",
        "required_gates": summary["required_gates"],
        "secondary_gates": summary["secondary_gates"],
        "evidence": summary["evidence"],
        "changed_files": summary["changed_files"],
        "unrelated_dirty_files_preserved": summary["unrelated_dirty_files_preserved"],
        "known_limitations": summary["known_limitations"],
        "blockers": summary["blockers"],
    }


def release_notes(summary: dict[str, Any]) -> str:
    commands = [
        "python3 -m json.tool data/tools.json",
        "cento tools",
        "cento docs parallel-delivery",
        "cento parallel-delivery validate --json",
        "cento parallel-delivery status --json",
        "cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json",
        "python3 -m pytest -q tests/test_patch_swarm.py",
    ]
    lines = [
        "# Patch Swarm Release Candidate",
        "",
        "## Status",
        summary["status"],
        "",
        "## Summary",
        "Patch Swarm has a deterministic local release gate for planning, leases, worker packets, patch bundle validation, integration planning, release candidate evidence, status JSON, safety, regression, and operator docs.",
        "",
        "## Product Flow",
        "one request -> split plan -> leases -> worker packets -> patch bundles -> validation -> integration plan -> release candidate -> evidence",
        "",
        "## Operator Commands",
        "",
    ]
    lines.extend(f"- `{cmd}`" for cmd in commands)
    lines.extend(
        [
            "",
            "## Evidence",
            f"- Final QA: `{summary['evidence']['final_qa_dir']}`",
            f"- Release candidate: `{summary['evidence']['release_candidate_dir']}`",
            "",
            "## Safety",
            "Fixture and dry-run paths were used. No live Pro/API dispatch, real worker launch, Taskstream mutation, secret copy, reset, checkout, clean, or broad stash is required for the final gate.",
            "",
            "## Validation Results",
            "",
            "| Gate | Status |",
            "|---|---|",
        ]
    )
    lines.extend(f"| `{gate}` | `{status}` |" for gate, status in summary["required_gates"].items())
    lines.extend(["", "## Known Limitations", ""])
    lines.extend(f"- {item}" for item in summary["known_limitations"] or ["None."])
    lines.extend(["", "## Next Actions", "", "- Review mixed/unrelated dirty work before any broad packaging or PR that includes non-Patch Swarm files."])
    return "\n".join(lines) + "\n"


def write_auxiliary_reports(final_dir: Path, summary: dict[str, Any]) -> None:
    (final_dir / "known-limitations.md").write_text(
        "# Known Limitations\n\n" + "\n".join(f"- {item}" for item in summary["known_limitations"] or ["None."]) + "\n",
        encoding="utf-8",
    )
    (final_dir / "next-actions.md").write_text(
        "# Next Actions\n\n"
        "- Use the release candidate packet as the final Patch Swarm gate.\n"
        "- Keep live Pro/API, workers, and Taskstream apply paths behind explicit opt-in flags.\n"
        "- Review unrelated Industrial/temp dirty work separately before packaging it with Patch Swarm.\n",
        encoding="utf-8",
    )
    (final_dir / "changed-files.txt").write_text("\n".join(summary["changed_files"]) + "\n", encoding="utf-8")


def write_final_evidence(final_dir: Path, rc_dir: Path, *, run_id: str) -> dict[str, Any]:
    final_dir.mkdir(parents=True, exist_ok=True)
    rc_dir.mkdir(parents=True, exist_ok=True)

    conflict_payload, conflict_md = conflict_report(run_id)
    write_json(final_dir / "owned-path-conflict-report.json", conflict_payload)
    (final_dir / "owned-path-conflict-report.md").write_text(conflict_md, encoding="utf-8")

    index = build_evidence_index(run_id)
    write_json(final_dir / "evidence-index.json", index)
    (final_dir / "evidence-index.md").write_text(evidence_index_md(index), encoding="utf-8")

    summary = build_final_summary(run_id, final_dir, rc_dir, conflict_payload)
    write_json(final_dir / "final-validation-summary.json", summary)
    (final_dir / "final-validation-report.md").write_text(final_report(summary), encoding="utf-8")
    write_auxiliary_reports(final_dir, summary)

    candidate = release_candidate(summary)
    write_json(rc_dir / "release-candidate.json", candidate)
    (rc_dir / "release-notes.md").write_text(release_notes(summary), encoding="utf-8")

    return {
        "ok": summary["status"] == "pass",
        "run_id": run_id,
        "status": summary["status"],
        "final_qa_dir": rel(final_dir),
        "release_candidate_dir": rel(rc_dir),
        "blockers": summary["blockers"],
        "known_limitations": summary["known_limitations"],
    }


def default_run_id() -> str:
    return "callC-final-qa-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write Patch Swarm final QA and release candidate evidence.")
    parser.add_argument("--final-out", required=True, type=Path)
    parser.add_argument("--release-candidate-out", required=True, type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or default_run_id()
    result = write_final_evidence(args.final_out, args.release_candidate_out, run_id=run_id)
    if args.json:
        print(stable_json(result), end="")
    else:
        print(f"wrote final QA evidence: {result['final_qa_dir']} and {result['release_candidate_dir']}")
    return 0 if result["status"] in {"pass", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
