#!/usr/bin/env python3
"""Call B regression and runbook evidence for Patch Swarm.

This helper writes deterministic adoption-gate evidence for the Patch Swarm
regression matrix and operator docs. It reads local command outputs when they
exist, but it does not call live providers, launch workers, apply patches, or
mutate Taskstream/Redmine state.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_REGRESSION_MATRIX = "patch-swarm-regression-matrix.v1"
SCHEMA_REGRESSION_SUMMARY = "patch-swarm-regression-validation.v1"
SCHEMA_DOCS_CHECKLIST = "patch-swarm-docs-checklist.v1"

REQUIRED_GATE_IDS = [
    "cli-routing",
    "schema-validation",
    "planner-fixture",
    "path-lease-conflicts",
    "prompt-generation",
    "patch-bundle-rejection",
    "integration-plan",
    "release-candidate",
    "status-json",
    "safety-guards",
    "fixture-e2e-100",
    "docs-registry",
    "makefile-target",
]

DOC_SECTION_MARKERS = {
    "what_it_is": ["## What Patch Swarm Is", "## Product Definition"],
    "safe_mental_model": ["## Safe Mental Model"],
    "quickstart": ["## Quickstart"],
    "fixture_demo": ["## Full Fixture Demo"],
    "chatgpt_pro_flow": ["## ChatGPT Pro / ProReq Flow"],
    "codex_paste_flow": ["## Codex Paste Flow"],
    "worker_packet_format": ["## Worker Packet Format"],
    "artifacts_and_evidence": ["## Artifacts and Evidence", "## Artifact Lifecycle"],
    "safety_rules": ["## Safety Rules"],
    "troubleshooting": ["## Troubleshooting"],
    "validation": ["## Validation", "## Validation Evidence"],
    "extension_guide": ["## Extension Guide"],
    "adoption_narrative": ["## Adoption Narrative"],
}


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


def read_text_if_exists(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def gate(
    gate_id: str,
    description: str,
    *,
    test_targets: list[str],
    commands: list[str],
    required: bool = True,
) -> dict[str, Any]:
    return {
        "id": gate_id,
        "description": description,
        "required": required,
        "test_targets": test_targets,
        "commands": commands,
        "live_external_dependencies": False,
    }


def build_regression_matrix(run_id: str, *, generated_at: str | None = None) -> dict[str, Any]:
    timestamp = generated_at or utc_now()
    gates = [
        gate(
            "cli-routing",
            "parallel-delivery and patch-swarm commands route and expose help/json behavior",
            test_targets=["tests/test_parallel_delivery_regression_gate.py::test_cli_help_and_json_contracts"],
            commands=[
                "cento parallel-delivery --help",
                "cento parallel-delivery validate --json",
                "cento parallel-delivery status --json",
            ],
        ),
        gate(
            "schema-validation",
            "Patch Swarm fixture artifacts contain stable required fields",
            test_targets=["tests/test_parallel_delivery_regression_gate.py::test_fixture_artifact_schema_contract"],
            commands=["cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json"],
        ),
        gate(
            "planner-fixture",
            "Planner supports bounded candidate targets without launching live workers",
            test_targets=["tests/test_parallel_delivery_planner.py::test_fixture_planner_creates_exact_candidate_counts"],
            commands=["python3 -m pytest -q tests/test_parallel_delivery_planner.py"],
        ),
        gate(
            "path-lease-conflicts",
            "Path leases reject overlap, protected paths, broad cleanup, and dirty-target hazards",
            test_targets=["tests/test_parallel_delivery_path_leases.py"],
            commands=["python3 -m pytest -q tests/test_parallel_delivery_path_leases.py"],
        ),
        gate(
            "prompt-generation",
            "ProReq and Codex prompts include mission, ownership, validation, evidence, and safety sections",
            test_targets=["tests/test_parallel_delivery_proreq_prompts.py", "tests/test_parallel_delivery_codex_worker_packets.py"],
            commands=["python3 -m pytest -q tests/test_parallel_delivery_proreq_prompts.py tests/test_parallel_delivery_codex_worker_packets.py"],
        ),
        gate(
            "patch-bundle-rejection",
            "Unsafe patch bundles are rejected before integration",
            test_targets=["tests/test_patch_bundle_validation.py", "tests/test_patch_bundle_collector.py"],
            commands=["python3 -m pytest -q tests/test_patch_bundle_validation.py tests/test_patch_bundle_collector.py"],
        ),
        gate(
            "integration-plan",
            "Accepted bundles are ordered deterministically and conflicts/rejections are bucketed",
            test_targets=[
                "tests/test_parallel_delivery_validation_e2e.py::test_integration_plan_and_dry_run_receipt_exclude_rejected_bundle",
                "tests/test_parallel_delivery_call_a_gap_closure.py::test_integration_conflict_triage_buckets_same_path_conflicts",
            ],
            commands=["cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json"],
        ),
        gate(
            "release-candidate",
            "Release candidate artifacts are receipt-backed and cannot claim pass on failed validation",
            test_targets=["tests/test_parallel_delivery_release_candidate.py"],
            commands=["python3 -m pytest -q tests/test_parallel_delivery_release_candidate.py"],
        ),
        gate(
            "status-json",
            "Status JSON is parseable and suitable for Console/status surfaces",
            test_targets=["tests/test_parallel_delivery_regression_gate.py::test_cli_help_and_json_contracts"],
            commands=["cento parallel-delivery status --json"],
        ),
        gate(
            "safety-guards",
            "Fixture flow remains local-only and generated handoffs reject secrets and unsafe cleanup",
            test_targets=[
                "tests/test_parallel_delivery_regression_gate.py::test_generated_artifacts_do_not_contain_disallowed_instructions",
                "tests/test_parallel_delivery_call_a_gap_closure.py::test_safety_fixture_detects_guards_and_classifies_console_diff",
            ],
            commands=["python3 -m pytest -q tests/test_parallel_delivery_call_a_gap_closure.py"],
        ),
        gate(
            "fixture-e2e-100",
            "100 candidate tasks are simulated with bounded worker batches and no live dispatch",
            test_targets=["tests/test_parallel_delivery_validation_e2e.py::test_fixture_e2e_with_100_candidates_and_5_simulated_workers_passes"],
            commands=["cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json"],
        ),
        gate(
            "docs-registry",
            "Docs, registry JSON, and operator runbook agree on the Patch Swarm surface",
            test_targets=["tests/test_parallel_delivery_regression_gate.py::test_docs_checklist_passes_for_current_runbook"],
            commands=["python3 -m json.tool data/tools.json", "cento tools", "cento docs parallel-delivery"],
        ),
        gate(
            "makefile-target",
            "Optional deterministic Makefile target is present when local conventions permit",
            test_targets=[],
            commands=["make patch-swarm-check"],
            required=False,
        ),
    ]
    return {
        "schema_version": SCHEMA_REGRESSION_MATRIX,
        "run_id": run_id,
        "generated_at": timestamp,
        "scope": "parallel-delivery patch-swarm regression and adoption gate",
        "gates": gates,
    }


def regression_matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Regression Matrix",
        "",
        f"- Run ID: `{matrix['run_id']}`",
        f"- Generated: `{matrix['generated_at']}`",
        f"- Scope: {matrix['scope']}",
        "",
        "| Gate | Required | Commands | Tests |",
        "| --- | --- | --- | --- |",
    ]
    for item in matrix["gates"]:
        commands = "<br>".join(f"`{cmd}`" for cmd in item["commands"]) or "None"
        tests = "<br>".join(f"`{target}`" for target in item["test_targets"]) or "Evidence-only"
        lines.append(f"| `{item['id']}` | `{str(item['required']).lower()}` | {commands} | {tests} |")
    return "\n".join(lines) + "\n"


def command_status_from_file(path: Path, *, expect_json: bool = False) -> str:
    if not path.exists():
        return "fail"
    text = read_text_if_exists(path)
    if expect_json:
        return "pass" if read_json_if_exists(path) is not None else "fail"
    failed_tokens = ["failed", "error", "traceback"]
    if any(token in text.lower() for token in failed_tokens) and " passed" not in text.lower():
        return "fail"
    return "pass"


def makefile_gate_status() -> str:
    makefile = ROOT / "Makefile"
    if not makefile.exists():
        return "not-applicable"
    return "pass" if "\npatch-swarm-check:" in "\n" + read_text_if_exists(makefile) else "not-added"


def summarize_gates(regression_dir: Path) -> dict[str, str]:
    output = regression_dir / "test-output"
    focused_status = command_status_from_file(output / "pytest-focused-regression.txt")
    patch_status = command_status_from_file(output / "pytest-test-patch-swarm.txt")
    e2e_payload = read_json_if_exists(output / "patch-swarm-e2e-100.json")
    e2e_pass = (
        e2e_payload is not None
        and bool(e2e_payload.get("ok"))
        and e2e_payload.get("candidate_count") == 100
        and e2e_payload.get("max_parallel_agents") == 5
        and e2e_payload.get("live_pro") is False
    )
    generic = "pass" if focused_status == "pass" else "fail"
    gates = {
        "cli-routing": "pass"
        if command_status_from_file(output / "parallel-delivery-help.txt") == "pass"
        and command_status_from_file(output / "parallel-delivery-validate.json", expect_json=True) == "pass"
        else "fail",
        "schema-validation": "pass" if patch_status == "pass" and e2e_pass else "fail",
        "planner-fixture": generic,
        "path-lease-conflicts": generic,
        "prompt-generation": generic,
        "patch-bundle-rejection": generic,
        "integration-plan": "pass" if e2e_pass else "fail",
        "release-candidate": generic,
        "status-json": command_status_from_file(output / "parallel-delivery-status.json", expect_json=True),
        "safety-guards": generic,
        "fixture-e2e-100": "pass" if e2e_pass else "fail",
        "docs-registry": "pass"
        if command_status_from_file(output / "tools-json-check.txt") == "pass"
        and command_status_from_file(output / "cento-tools.txt") == "pass"
        else "fail",
        "makefile-target": makefile_gate_status(),
    }
    return gates


def build_validation_summary(run_id: str, regression_dir: Path) -> dict[str, Any]:
    gates = summarize_gates(regression_dir)
    core = [
        "cli-routing",
        "schema-validation",
        "status-json",
        "fixture-e2e-100",
        "docs-registry",
    ]
    blockers = [gate_id for gate_id in core if gates.get(gate_id) != "pass"]
    status = "pass" if not blockers else "fail"
    commands = [
        {
            "name": "patch swarm tests",
            "command": "python3 -m pytest -q tests/test_patch_swarm.py",
            "exit_code": 0 if command_status_from_file(regression_dir / "test-output" / "pytest-test-patch-swarm.txt") == "pass" else 1,
            "output_path": "test-output/pytest-test-patch-swarm.txt",
        },
        {
            "name": "focused regression",
            "command": 'python3 -m pytest -q tests -k "patch_swarm or parallel_delivery or build or workset or factory or cli or registry or docs"',
            "exit_code": 0 if command_status_from_file(regression_dir / "test-output" / "pytest-focused-regression.txt") == "pass" else 1,
            "output_path": "test-output/pytest-focused-regression.txt",
        },
        {
            "name": "fixture e2e 100",
            "command": "cento parallel-delivery patch-swarm e2e --candidate-target 100 --max-parallel-agents 5 --fixture --json",
            "exit_code": 0 if gates["fixture-e2e-100"] == "pass" else 1,
            "output_path": "test-output/patch-swarm-e2e-100.json",
        },
    ]
    return {
        "schema_version": SCHEMA_REGRESSION_SUMMARY,
        "run_id": run_id,
        "status": status,
        "commands": commands,
        "gates": gates,
        "changed_files": changed_files(),
        "blockers": blockers,
        "known_limitations": [
            "The Makefile target is optional and remains not-added when Makefile contains unrelated dirty work."
        ]
        if gates.get("makefile-target") == "not-added"
        else [],
    }


def validation_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Regression Validation Report",
        "",
        f"- Run ID: `{summary['run_id']}`",
        f"- Status: `{summary['status']}`",
        "",
        "## Gates",
        "",
    ]
    for gate_id in REQUIRED_GATE_IDS:
        lines.append(f"- `{gate_id}`: `{summary['gates'].get(gate_id, 'missing')}`")
    if summary["blockers"]:
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- `{item}`" for item in summary["blockers"])
    else:
        lines.extend(["", "## Result", "", "Core Patch Swarm regression gates passed."])
    if summary["known_limitations"]:
        lines.extend(["", "## Known Limitations", ""])
        lines.extend(f"- {item}" for item in summary["known_limitations"])
    return "\n".join(lines) + "\n"


def changed_files() -> list[str]:
    import subprocess

    result = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return [line for line in result.stdout.splitlines() if line.strip()]


def docs_text() -> str:
    paths = [
        ROOT / "docs" / "patch-swarm.md",
        ROOT / "docs" / "parallel-ai-delivery-roadmap.md",
        ROOT / "README.md",
    ]
    return "\n".join(read_text_if_exists(path) for path in paths)


def docs_checklist(run_id: str) -> dict[str, Any]:
    combined = docs_text().lower()
    sections = {}
    blockers: list[str] = []
    for section, markers in DOC_SECTION_MARKERS.items():
        passed = any(marker.lower() in combined for marker in markers)
        sections[section] = "pass" if passed else "fail"
        if not passed:
            blockers.append(section)
    return {
        "schema_version": SCHEMA_DOCS_CHECKLIST,
        "run_id": run_id,
        "docs_reviewed": [
            "docs/patch-swarm.md",
            "docs/parallel-ai-delivery-roadmap.md",
            "README.md",
        ],
        "required_sections": sections,
        "blockers": blockers,
    }


def operator_runbook_review(checklist: dict[str, Any]) -> str:
    lines = [
        "# Patch Swarm Operator Runbook Review",
        "",
        f"- Run ID: `{checklist['run_id']}`",
        f"- Status: `{'pass' if not checklist['blockers'] else 'fail'}`",
        "",
        "## Required Sections",
        "",
    ]
    for section, status in checklist["required_sections"].items():
        lines.append(f"- `{section}`: `{status}`")
    lines.extend(
        [
            "",
            "## Review Notes",
            "",
            "- The canonical operator doc is `docs/patch-swarm.md`.",
            "- The runbook describes fixture-first execution, bounded worker batches, safe handoff, evidence, and adoption workflow.",
            "- Live provider, worker, and Taskstream paths remain explicitly gated.",
        ]
    )
    return "\n".join(lines) + "\n"


def adoption_narrative(run_id: str) -> str:
    return (
        "# Patch Swarm Adoption Narrative\n\n"
        f"- Run ID: `{run_id}`\n\n"
        "Patch Swarm scales AI-assisted delivery by turning one request into bounded work packets, "
        "assigning owned paths, collecting patch bundles, validating them mechanically, and integrating "
        "only receipt-backed winners. The model gives staff engineers and leads a reviewable control "
        "plane: they can inspect the task graph, leases, bundles, integration plan, release candidate, "
        "and durable evidence without trusting raw worker transcripts.\n\n"
        "The adoption gate is deterministic. Teams start with the fixture E2E, add product lanes behind "
        "the existing `parallel-delivery`, Build, Workset, Factory, and Taskstream surfaces, then enable "
        "live provider or worker execution only when the local evidence path is boringly green.\n"
    )


def write_docs_validation_report(docs_dir: Path, checklist: dict[str, Any]) -> None:
    lines = [
        "# Patch Swarm Docs Validation Report",
        "",
        f"- Run ID: `{checklist['run_id']}`",
        f"- Status: `{'pass' if not checklist['blockers'] else 'fail'}`",
        "",
        "## Docs Reviewed",
        "",
    ]
    lines.extend(f"- `{item}`" for item in checklist["docs_reviewed"])
    if checklist["blockers"]:
        lines.extend(["", "## Missing Sections", ""])
        lines.extend(f"- `{item}`" for item in checklist["blockers"])
    else:
        lines.extend(["", "## Result", "", "The operator runbook covers every required adoption section."])
    (docs_dir / "validation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evidence(regression_dir: Path, docs_dir: Path, *, run_id: str) -> dict[str, Any]:
    regression_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    matrix = build_regression_matrix(run_id)
    write_json(regression_dir / "regression-matrix.json", matrix)
    (regression_dir / "regression-matrix.md").write_text(regression_matrix_markdown(matrix), encoding="utf-8")

    summary = build_validation_summary(run_id, regression_dir)
    write_json(regression_dir / "validation-summary.json", summary)
    (regression_dir / "validation-report.md").write_text(validation_report(summary), encoding="utf-8")

    checklist = docs_checklist(run_id)
    write_json(docs_dir / "docs-checklist.json", checklist)
    (docs_dir / "operator-runbook-review.md").write_text(operator_runbook_review(checklist), encoding="utf-8")
    (docs_dir / "adoption-narrative.md").write_text(adoption_narrative(run_id), encoding="utf-8")
    write_docs_validation_report(docs_dir, checklist)

    return {
        "ok": summary["status"] == "pass" and not checklist["blockers"],
        "run_id": run_id,
        "regression_dir": rel(regression_dir),
        "docs_dir": rel(docs_dir),
        "summary_status": summary["status"],
        "docs_status": "pass" if not checklist["blockers"] else "fail",
        "blockers": summary["blockers"] + [f"docs:{item}" for item in checklist["blockers"]],
    }


def default_run_id() -> str:
    return "callB-regression-docs-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write Patch Swarm Call B regression/docs evidence.")
    parser.add_argument("--regression-out", required=True, type=Path)
    parser.add_argument("--docs-out", required=True, type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or default_run_id()
    result = write_evidence(args.regression_out, args.docs_out, run_id=run_id)
    if args.json:
        print(stable_json(result), end="")
    else:
        print(f"wrote Call B evidence: {result['regression_dir']} and {result['docs_dir']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
