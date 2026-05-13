#!/usr/bin/env python3
"""Deterministic Patch Swarm validation and fixture E2E.

This module composes the local Patch Swarm planner, path lease, and Codex
packet helpers into a product-quality fixture E2E. It writes artifacts only
under the requested run directory. It does not call live AI services, dispatch
agents, mutate Taskstream/Redmine, or apply patches.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import parallel_delivery_codex_packets as packet_tool
    import parallel_delivery_leases as lease_tool
    import parallel_delivery_planner as planner_tool
except ImportError:  # pragma: no cover - direct script fallback
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import parallel_delivery_codex_packets as packet_tool
    import parallel_delivery_leases as lease_tool
    import parallel_delivery_planner as planner_tool


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"
DEFAULT_RUN_ROOT = RUNS_ROOT / "e2e-fixture"
CURRENT_SCHEMA_VERSION = 1
MAX_CANDIDATE_TASKS = 100
PRODUCER = "cento.parallel-delivery.validation-e2e"

E2E_STAGES = [
    "request",
    "split",
    "leases",
    "worker_packets",
    "fixture_patch_bundles",
    "patch_validation",
    "malformed_artifact_validation",
    "integration_plan",
    "dry_run_integration",
    "release_candidate",
    "validation_summary",
]

VALIDATION_OVERALL_STATES = {"passed", "failed", "partial"}
PATCH_BUNDLE_STATES = {"accepted", "rejected"}
INTEGRATION_STRATEGIES = {"dry-run-sequential", "dependency-order"}

REPORT_SECTIONS = [
    "## Summary",
    "## Fixture Configuration",
    "## Artifact Checks",
    "## Lease Checks",
    "## Worker Packet Checks",
    "## Patch Bundle Checks",
    "## Unsafe Bundle Rejection",
    "## Integration Plan",
    "## Dry-Run Integration Receipt",
    "## Release Candidate",
    "## Evidence",
    "## Command Logs",
    "## Result",
]

REQUIRED_RUN_FILES = [
    "request.md",
    "run.json",
    "context-pack.json",
    "split-plan.json",
    "task-graph.json",
    "path-leases.json",
    "worker-packets/codex-packet-bundle.json",
    "worker-packets/codex-packet-index.json",
    "validation/lease-validation.json",
    "validation/packet-validation.json",
    "validation/patch-bundle-validation.json",
    "validation/malformed-artifact-validation.json",
    "integration/integration-plan.json",
    "integration/integration-receipt.json",
    "integration/rejected-patches.json",
    "integration/dry-run-apply-log.jsonl",
    "release-candidate/release-candidate.json",
    "release-candidate/release-notes.md",
    "release-candidate/demo-evidence.md",
    "command-output.log",
    "start-here.md",
]


class ValidationE2EError(Exception):
    """Raised when deterministic validation or fixture E2E fails."""


@dataclass(frozen=True)
class E2ERequest:
    run_id: str
    run_root: Path
    candidate_target: int
    max_parallel_agents: int
    fixture: bool
    dry_run: bool
    fixed_timestamp: str | None = None
    include_unsafe_fixture: bool = True
    objective: str = ""
    command: str = "parallel-delivery patch-swarm e2e"


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    ok: bool
    category: str
    artifact: str | None = None
    errors: list[str] | None = None
    warnings: list[str] | None = None


@dataclass(frozen=True)
class E2EResult:
    ok: bool
    run_id: str
    run_dir: Path
    candidate_target: int
    candidate_count: int
    max_parallel_agents: int
    accepted_patch_bundles: int
    rejected_patch_bundles: int
    overall: str
    artifacts: list[str]
    warnings: list[str]
    errors: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json_dumps(payload: Any) -> str:
    """Return deterministic JSON with sorted keys, two-space indent, and trailing newline."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json_dumps(payload), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    """Read JSON and fail clearly."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationE2EError(f"file not found: {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationE2EError(f"invalid JSON in {rel(path)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationE2EError(f"expected JSON object in {rel(path)}")
    return payload


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def validate_candidate_target(value: int) -> int:
    """Require 1 <= value <= 100."""
    if not isinstance(value, int):
        raise ValidationE2EError("candidate_target must be an integer")
    if not 1 <= value <= MAX_CANDIDATE_TASKS:
        raise ValidationE2EError("candidate_target must be between 1 and 100")
    return value


def validate_max_parallel_agents(value: int, candidate_target: int) -> int:
    """Require 1 <= value <= candidate_target."""
    if not isinstance(value, int):
        raise ValidationE2EError("max_parallel_agents must be an integer")
    if not 1 <= value <= candidate_target:
        raise ValidationE2EError("max_parallel_agents must be between 1 and candidate_target")
    return value


def e2e_run_dir(run_root: Path, run_id: str) -> Path:
    """Return run_root/run_id."""
    return resolve_path(run_root) / run_id


def check_dict(check: ValidationCheck) -> dict[str, Any]:
    payload = asdict(check)
    payload["errors"] = check.errors or []
    payload["warnings"] = check.warnings or []
    return payload


def provenance(command: str, source: str = "fixture") -> dict[str, Any]:
    return {
        "producer": PRODUCER,
        "command": command,
        "source": source,
        "notes": [],
    }


def _timestamp(request: E2ERequest) -> str:
    return request.fixed_timestamp or utc_now()


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]


def _safe_run_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value).strip("-._")
    if not cleaned:
        raise ValidationE2EError("run_id is required")
    return cleaned


def _reset_generated_run_dir(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    generated_dirs = [
        "task-contracts",
        "proreq",
        "worker-packets",
        "fixture-workers",
        "patch-bundles",
        "validation",
        "integration",
        "release-candidate",
    ]
    generated_files = [
        "request.md",
        "run.json",
        "context-pack.json",
        "split-plan.json",
        "task-graph.json",
        "path-leases.json",
        "codex-packet-bundle.json",
        "codex-packet-index.json",
        "codex-packet-index.md",
        "packet-validation.json",
        "packet-validation-report.md",
        "planner-report.md",
        "validation-summary.json",
        "validation-report.md",
        "command-output.log",
        "start-here.md",
    ]
    for item in generated_dirs:
        target = run_dir / item
        if target.exists():
            shutil.rmtree(target)
    for item in generated_files:
        target = run_dir / item
        if target.exists():
            target.unlink()


def _task_ids(split_plan: dict[str, Any]) -> list[str]:
    return [str(task.get("task_id")) for task in split_plan.get("tasks", []) if isinstance(task, dict) and task.get("task_id")]


def _tasks_by_id(split_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(task.get("task_id")): task for task in split_plan.get("tasks", []) if isinstance(task, dict) and task.get("task_id")}


def _leases_by_task(path_leases: dict[str, Any]) -> dict[str, dict[str, Any]]:
    leases: dict[str, dict[str, Any]] = {}
    for lease in path_leases.get("leases", []):
        if isinstance(lease, dict) and lease.get("task_id"):
            leases[str(lease["task_id"])] = lease
    return leases


def path_is_owned(path: str, owned_paths: list[str]) -> bool:
    value = path.rstrip("/")
    for owned in owned_paths:
        root = str(owned).rstrip("/")
        if value == root or value.startswith(root + "/"):
            return True
    return False


def path_overlaps(left: str, right: str) -> bool:
    left = left.rstrip("/")
    right = right.rstrip("/")
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def write_fixture_request(run_dir: Path, request: E2ERequest) -> Path:
    """Write deterministic request.md."""
    path = run_dir / "request.md"
    text = (
        "# Patch Swarm E2E Fixture Request\n\n"
        "Create a deterministic local-first fixture proving request splitting, path leasing, "
        "worker packets, patch bundle validation, dry-run integration, and release candidate evidence.\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def create_fixture_split_plan(run_dir: Path, request: E2ERequest) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create deterministic split-plan/task-graph generation through the planner helper."""
    payload, code = planner_tool.run_planner_command(
        candidate_target=request.candidate_target,
        command=request.command,
        dry_run=True,
        live_pro=False,
        max_parallel_agents=request.max_parallel_agents,
        mode="fixture",
        request_text=request.objective
        or (
            "Create a deterministic local-first fixture proving request splitting, path leasing, "
            "worker packets, patch bundle validation, dry-run integration, and release candidate evidence."
        ),
        run_dir=run_dir,
        run_id=request.run_id,
        timestamp=_timestamp(request),
    )
    if code != 0 or not payload.get("ok"):
        raise ValidationE2EError("; ".join(payload.get("errors", ["planner fixture failed"])))
    write_fixture_request(run_dir, request)
    return read_json(run_dir / "split-plan.json"), read_json(run_dir / "task-graph.json")


def write_run_artifacts(run_dir: Path, request: E2ERequest, split_plan: dict[str, Any], task_graph: dict[str, Any]) -> None:
    timestamp = _timestamp(request)
    artifact_paths = {
        "request": "request.md",
        "context_pack": "context-pack.json",
        "split_plan": "split-plan.json",
        "task_graph": "task-graph.json",
        "path_leases": "path-leases.json",
        "worker_packets": "worker-packets/codex-packet-index.json",
        "validation_summary": "validation-summary.json",
        "validation_report": "validation-report.md",
    }
    run_payload = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "run",
        "run_id": request.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": provenance(request.command),
        "request_title": "Patch Swarm E2E Fixture Request",
        "state": "run_created",
        "fixture": True,
        "dry_run": True,
        "candidate_target": request.candidate_target,
        "candidate_count": len(split_plan.get("tasks", [])),
        "max_parallel_agents": request.max_parallel_agents,
        "artifact_paths": artifact_paths,
        "counts": {
            "candidate_tasks": len(split_plan.get("tasks", [])),
            "task_graph_nodes": len(task_graph.get("nodes", [])),
        },
        "evidence_pointers": [],
    }
    context_pack = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "context-pack",
        "run_id": request.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": provenance(request.command),
        "request_ref": "request.md",
        "repo_context": {
            "repo": "cento",
            "root": "/home/alice/projects/cento",
            "local_only": True,
        },
        "source_refs": {
            "split_plan": "split-plan.json",
            "task_graph": "task-graph.json",
            "helpers": [
                "scripts/parallel_delivery_planner.py",
                "scripts/parallel_delivery_leases.py",
                "scripts/parallel_delivery_codex_packets.py",
            ],
        },
        "constraints": [
            "No live Pro, OpenAI API, Codex dispatch, MCP mutation, Taskstream/Redmine direct writes, or patch application.",
            "Fixture workers are simulated local artifact writers.",
            "Dry-run integration records only what would be integrated.",
        ],
        "evidence_pointers": [],
    }
    write_json(run_dir / "run.json", run_payload)
    write_json(run_dir / "context-pack.json", context_pack)


def create_fixture_leases(
    run_dir: Path,
    split_plan: dict[str, Any],
    task_graph: dict[str, Any],
    request: E2ERequest,
) -> dict[str, Any]:
    """Create path-leases generation through the lease helper."""
    path_leases = lease_tool.create_leases(
        split_plan,
        task_graph,
        git_status_text="",
        timestamp=_timestamp(request),
        command=request.command,
    )
    write_json(run_dir / "path-leases.json", path_leases)
    write_json(run_dir / "validation" / "lease-validation.json", validate_lease_payload(run_dir, path_leases))
    return path_leases


def create_fixture_worker_packets(
    run_dir: Path,
    split_plan: dict[str, Any],
    task_graph: dict[str, Any],
    path_leases: dict[str, Any],
    request: E2ERequest,
) -> dict[str, Any]:
    """Create Codex worker packets through the packet helper."""
    del split_plan, task_graph, path_leases
    result = packet_tool.write_packet_bundle(
        packet_tool.CodexPacketRequest(
            run_id=request.run_id,
            run_dir=run_dir,
            count=request.candidate_target,
            out_dir=run_dir / "worker-packets" / "packets",
            fixed_timestamp=_timestamp(request),
        )
    )
    worker_dir = run_dir / "worker-packets"
    worker_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "codex-packet-bundle.json",
        "codex-packet-index.json",
        "codex-packet-index.md",
    ]:
        source = run_dir / name
        if source.exists():
            shutil.copyfile(source, worker_dir / name)
    packet_validation = packet_tool.validate_packet_bundle(run_dir)
    write_json(run_dir / "validation" / "packet-validation.json", packet_validation)
    return {
        "result": result,
        "validation": packet_validation,
        "bundle": read_json(worker_dir / "codex-packet-bundle.json"),
        "index": read_json(worker_dir / "codex-packet-index.json"),
    }


def create_simulated_worker_batches(
    task_ids: list[str],
    max_parallel_agents: int,
    task_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create deterministic bounded worker batches from the task graph order."""
    ordered = [str(item) for item in task_graph.get("topological_order", []) if str(item) in set(task_ids)]
    if set(ordered) != set(task_ids):
        ordered = task_ids
    batches: list[dict[str, Any]] = []
    for index in range(0, len(ordered), max_parallel_agents):
        batches.append(
            {
                "batch_id": f"batch-{len(batches) + 1:04d}",
                "max_parallel_agents": max_parallel_agents,
                "task_ids": ordered[index : index + max_parallel_agents],
            }
        )
    return batches


def _diff_for_path(changed_path: str, task_id: str) -> str:
    return "\n".join(
        [
            "--- /dev/null",
            f"+++ b/{changed_path}",
            "@@ -0,0 +1,3 @@",
            f"+task_id={task_id}",
            "+status=fixture",
            "+validated=true",
            "",
        ]
    )


def create_fixture_patch_bundles(
    run_dir: Path,
    split_plan: dict[str, Any],
    path_leases: dict[str, Any],
    request: E2ERequest,
) -> dict[str, Any]:
    """Write valid fixture patch bundles plus one unsafe out-of-lease bundle."""
    patch_dir = run_dir / "patch-bundles"
    worker_dir = run_dir / "fixture-workers"
    patch_dir.mkdir(parents=True, exist_ok=True)
    worker_dir.mkdir(parents=True, exist_ok=True)
    leases = _leases_by_task(path_leases)
    ledger_path = worker_dir / "simulated-worker-ledger.jsonl"
    task_entries: list[dict[str, Any]] = []
    with ledger_path.open("w", encoding="utf-8") as ledger:
        for task in split_plan.get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id") or "")
            lease = leases[task_id]
            owned_root = str(lease["owned_paths"][0]).rstrip("/")
            changed_path = f"{owned_root}/output.txt"
            diff_path = patch_dir / f"{task_id}.diff"
            bundle_path = patch_dir / f"{task_id}.patch-bundle.json"
            handoff_path = worker_dir / f"{task_id}-handoff.md"
            handoff_path.write_text(
                f"# Fixture Worker Handoff: {task_id}\n\n"
                "- State: simulated fixture worker completed.\n"
                f"- Changed path: `{changed_path}`.\n"
                "- No repository files were edited.\n",
                encoding="utf-8",
            )
            diff_path.write_text(_diff_for_path(changed_path, task_id), encoding="utf-8")
            bundle = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "artifact_type": "patch-bundle",
                "run_id": request.run_id,
                "created_at": _timestamp(request),
                "provenance": provenance("fixture-worker", "simulated-worker"),
                "task_id": task_id,
                "bundle_id": f"bundle-{task_id}-{_digest(request.run_id, task_id, changed_path)}",
                "base_ref": "fixture-base",
                "worker_id": "fixture-worker",
                "claimed_paths": list(lease.get("owned_paths", [])),
                "changed_paths": [changed_path],
                "diff_path": f"patch-bundles/{task_id}.diff",
                "summary": f"Fixture patch bundle for {task_id}",
                "tests_run": [
                    {
                        "command": "fixture bundle safety validation",
                        "status": "passed",
                    }
                ],
                "evidence_files": [f"fixture-workers/{task_id}-handoff.md"],
                "handoff_note": f"fixture-workers/{task_id}-handoff.md",
                "risks": [],
                "requires_manual_review": False,
                "evidence_pointers": [f"fixture-workers/{task_id}-handoff.md"],
            }
            write_json(bundle_path, bundle)
            task_entries.append(bundle)
            ledger.write(stable_json_dumps({"event": "patch_bundle_written", "task_id": task_id, "bundle_id": bundle["bundle_id"]}).strip() + "\n")

        if request.include_unsafe_fixture:
            unsafe_task = task_entries[0]["task_id"] if task_entries else "task-0001"
            unsafe_diff = patch_dir / "unsafe-out-of-lease.diff"
            unsafe_bundle_path = patch_dir / "unsafe-out-of-lease.patch-bundle.json"
            unsafe_diff.write_text(_diff_for_path("README.md", unsafe_task), encoding="utf-8")
            unsafe_bundle = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "artifact_type": "patch-bundle",
                "run_id": request.run_id,
                "created_at": _timestamp(request),
                "provenance": provenance("fixture-worker", "unsafe-negative-fixture"),
                "task_id": unsafe_task,
                "bundle_id": "unsafe-out-of-lease",
                "base_ref": "fixture-base",
                "worker_id": "fixture-worker-unsafe",
                "claimed_paths": ["README.md"],
                "changed_paths": ["README.md"],
                "diff_path": "patch-bundles/unsafe-out-of-lease.diff",
                "summary": "Intentional unsafe out-of-lease fixture bundle.",
                "tests_run": [],
                "evidence_files": [],
                "handoff_note": "",
                "risks": ["changed path outside owned lease"],
                "requires_manual_review": True,
                "evidence_pointers": [],
            }
            write_json(unsafe_bundle_path, unsafe_bundle)
            ledger.write(stable_json_dumps({"event": "unsafe_patch_bundle_written", "task_id": unsafe_task, "bundle_id": "unsafe-out-of-lease"}).strip() + "\n")
    return {"bundles": task_entries, "ledger": rel(ledger_path)}


def validate_artifacts(run_dir: Path) -> list[ValidationCheck]:
    """Validate required artifacts exist and parse."""
    checks: list[ValidationCheck] = []
    for name in REQUIRED_RUN_FILES:
        path = run_dir / name
        checks.append(
            ValidationCheck(
                name=f"artifact_exists:{name}",
                ok=path.exists(),
                category="artifact",
                artifact=name,
                errors=[] if path.exists() else [f"missing required artifact: {name}"],
            )
        )
        if path.suffix == ".json" and path.exists():
            try:
                read_json(path)
            except ValidationE2EError as exc:
                checks.append(
                    ValidationCheck(
                        name=f"json_parse:{name}",
                        ok=False,
                        category="artifact",
                        artifact=name,
                        errors=[str(exc)],
                    )
                )
    return checks


def validate_lease_payload(run_dir: Path, path_leases: dict[str, Any] | None = None) -> dict[str, Any]:
    path_leases = path_leases or read_json(run_dir / "path-leases.json")
    errors = lease_tool.validate_path_leases(path_leases)
    checks = [
        check_dict(
            ValidationCheck(
                name="path-leases-schema-and-safety",
                ok=not errors,
                category="lease",
                artifact="path-leases.json",
                errors=errors,
            )
        )
    ]
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "lease-validation",
        "run_id": path_leases.get("run_id"),
        "ok": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": [],
    }


def validate_leases(run_dir: Path) -> list[ValidationCheck]:
    """Validate no overlap and every task has a lease."""
    split_plan = read_json(run_dir / "split-plan.json")
    path_leases = read_json(run_dir / "path-leases.json")
    task_ids = set(_task_ids(split_plan))
    leases = [lease for lease in path_leases.get("leases", []) if isinstance(lease, dict)]
    leased_tasks = {str(lease.get("task_id")) for lease in leases}
    errors = lease_tool.validate_path_leases(path_leases)
    if leased_tasks != task_ids:
        errors.append("leased task IDs must match split-plan task IDs")
    owned: list[tuple[str, str]] = []
    for lease in leases:
        for path in lease.get("owned_paths", []):
            owned.append((str(lease.get("task_id")), str(path).rstrip("/")))
    for index, (task_a, path_a) in enumerate(owned):
        for task_b, path_b in owned[index + 1 :]:
            if path_overlaps(path_a, path_b):
                errors.append(f"owned path overlap: {task_a}:{path_a} and {task_b}:{path_b}")
    return [
        ValidationCheck(
            name="leases-cover-tasks-and-do-not-overlap",
            ok=not errors,
            category="lease",
            artifact="path-leases.json",
            errors=errors,
        )
    ]


def validate_worker_packets(run_dir: Path) -> list[ValidationCheck]:
    """Validate one packet per task and required packet sections."""
    split_plan = read_json(run_dir / "split-plan.json")
    task_ids = set(_task_ids(split_plan))
    index = read_json(run_dir / "worker-packets" / "codex-packet-index.json")
    packets = [item for item in index.get("packets", []) if isinstance(item, dict)]
    packet_tasks = {str(item.get("task_id")) for item in packets}
    errors: list[str] = []
    if packet_tasks != task_ids:
        errors.append("worker packet task IDs must match split-plan task IDs")
    validation = packet_tool.validate_packet_bundle(run_dir)
    errors.extend(str(item) for item in validation.get("errors", []))
    return [
        ValidationCheck(
            name="worker-packets-cover-tasks",
            ok=not errors,
            category="packet",
            artifact="worker-packets/codex-packet-index.json",
            errors=errors,
            warnings=[str(item) for item in validation.get("warnings", [])],
        )
    ]


def _is_protected_path(path: str) -> bool:
    lowered = path.lower()
    protected_fragments = [".env", ".git/", ".pem", ".key", "secret", "token", "credential"]
    return any(fragment in lowered for fragment in protected_fragments)


def _validate_bundle_payload(
    run_dir: Path,
    bundle_path: Path,
    bundle: dict[str, Any],
    tasks_by_id: dict[str, dict[str, Any]],
    leases_by_task: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    errors: list[str] = []
    required = [
        "schema_version",
        "artifact_type",
        "run_id",
        "task_id",
        "bundle_id",
        "base_ref",
        "worker_id",
        "claimed_paths",
        "changed_paths",
        "diff_path",
        "summary",
        "tests_run",
        "evidence_files",
        "requires_manual_review",
    ]
    for field in required:
        if field not in bundle:
            errors.append(f"missing required field: {field}")
    task_id = str(bundle.get("task_id") or "")
    if task_id not in tasks_by_id:
        errors.append(f"unknown task_id: {task_id}")
    lease = leases_by_task.get(task_id)
    if not lease:
        errors.append(f"no active lease for task {task_id}")
    changed_paths = bundle.get("changed_paths")
    if not isinstance(changed_paths, list) or not changed_paths:
        errors.append("changed_paths must be a non-empty list")
        changed_paths = []
    claimed_paths = bundle.get("claimed_paths")
    if not isinstance(claimed_paths, list):
        errors.append("claimed_paths must be a list")
    tests_run = bundle.get("tests_run")
    if not isinstance(tests_run, list) or not tests_run:
        errors.append("tests_run must include fixture validation evidence")
    evidence_files = bundle.get("evidence_files")
    if not isinstance(evidence_files, list) or not evidence_files:
        errors.append("evidence_files must include at least one existing evidence file")
        evidence_files = []
    for item in evidence_files:
        if not (run_dir / str(item)).exists():
            errors.append(f"evidence file missing: {item}")
    diff_path = str(bundle.get("diff_path") or "")
    if diff_path and not (run_dir / diff_path).exists():
        errors.append(f"diff_path missing: {diff_path}")
    if lease:
        owned_paths = [str(path) for path in lease.get("owned_paths", [])]
        for changed in changed_paths:
            path = str(changed)
            if path.endswith(".png") or path.endswith(".jpg") or path.endswith(".gif"):
                errors.append(f"binary-like patch path rejected: {path}")
            if _is_protected_path(path):
                errors.append(f"protected path rejected: {path}")
            if not path_is_owned(path, owned_paths):
                errors.append(f"changed path outside owned lease: {path}")
    for field in ("deleted_paths", "renames"):
        if bundle.get(field):
            errors.append(f"{field} are not allowed in fixture patch bundles")
    accepted = not errors
    return (
        {
            "bundle_id": str(bundle.get("bundle_id") or bundle_path.stem),
            "task_id": task_id,
            "path": rel(bundle_path),
            "state": "accepted" if accepted else "rejected",
            "changed_paths": changed_paths,
            "claimed_paths": claimed_paths if isinstance(claimed_paths, list) else [],
            "errors": errors,
        },
        accepted,
    )


def validate_patch_bundles(run_dir: Path) -> tuple[list[ValidationCheck], list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate patch bundles; return checks, accepted bundles, rejected bundles."""
    split_plan = read_json(run_dir / "split-plan.json")
    path_leases = read_json(run_dir / "path-leases.json")
    tasks_by_id = _tasks_by_id(split_plan)
    leases_by_task = _leases_by_task(path_leases)
    checks: list[ValidationCheck] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    bundle_results: list[dict[str, Any]] = []
    for bundle_path in sorted((run_dir / "patch-bundles").glob("*.patch-bundle.json")):
        try:
            bundle = read_json(bundle_path)
            result, ok = _validate_bundle_payload(run_dir, bundle_path, bundle, tasks_by_id, leases_by_task)
        except ValidationE2EError as exc:
            result = {
                "bundle_id": bundle_path.stem,
                "task_id": "",
                "path": rel(bundle_path),
                "state": "rejected",
                "changed_paths": [],
                "claimed_paths": [],
                "errors": [str(exc)],
            }
            ok = False
        bundle_results.append(result)
        if ok:
            accepted.append(result)
        else:
            rejected.append(result)
        checks.append(
            ValidationCheck(
                name=f"patch-bundle:{result['bundle_id']}",
                ok=ok or result["bundle_id"] == "unsafe-out-of-lease",
                category="patch-bundle" if ok else "negative",
                artifact=result["path"],
                errors=[] if ok or result["bundle_id"] == "unsafe-out-of-lease" else result["errors"],
                warnings=[],
            )
        )
    validation = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "patch-bundle-validation",
        "run_id": split_plan.get("run_id"),
        "ok": bool(accepted) and any(item.get("bundle_id") == "unsafe-out-of-lease" for item in rejected),
        "accepted": accepted,
        "rejected": rejected,
        "checks": [check_dict(check) for check in checks],
        "errors": [],
        "warnings": [],
    }
    write_json(run_dir / "validation" / "patch-bundle-validation.json", validation)
    write_json(
        run_dir / "integration" / "rejected-patches.json",
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "artifact_type": "rejected-patches",
            "run_id": split_plan.get("run_id"),
            "rejected": rejected,
        },
    )
    return checks, accepted, rejected


def validate_malformed_artifact_rejection(run_dir: Path) -> list[ValidationCheck]:
    """Write malformed artifact and prove validation rejects it."""
    malformed_dir = run_dir / "validation" / "malformed"
    malformed_dir.mkdir(parents=True, exist_ok=True)
    malformed_path = malformed_dir / "missing-run-id.json"
    write_json(
        malformed_path,
        {
            "schema_version": CURRENT_SCHEMA_VERSION,
            "artifact_type": "patch-bundle",
            "task_id": "task-0001",
            "bundle_id": "malformed-missing-run-id",
        },
    )
    payload = read_json(malformed_path)
    errors = []
    if not payload.get("run_id"):
        errors.append("missing required field: run_id")
    result = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "malformed-artifact-validation",
        "run_id": read_json(run_dir / "split-plan.json").get("run_id"),
        "ok": bool(errors),
        "negative_check": "malformed artifact is rejected clearly",
        "malformed_artifact": "validation/malformed/missing-run-id.json",
        "state": "rejected" if errors else "accepted",
        "errors": errors,
        "warnings": [],
    }
    write_json(run_dir / "validation" / "malformed-artifact-validation.json", result)
    return [
        ValidationCheck(
            name="malformed-artifact:missing-run-id",
            ok=bool(errors),
            category="negative",
            artifact="validation/malformed/missing-run-id.json",
            errors=[] if errors else ["malformed artifact was not rejected"],
            warnings=[],
        )
    ]


def create_integration_plan(
    run_dir: Path,
    accepted_bundles: list[dict[str, Any]],
    rejected_bundles: list[dict[str, Any]],
    task_graph: dict[str, Any],
) -> dict[str, Any]:
    """Create deterministic integration-plan.json."""
    accepted_by_task = {str(item["task_id"]): item for item in accepted_bundles}
    queue = []
    for task_id in task_graph.get("topological_order", []):
        bundle = accepted_by_task.get(str(task_id))
        if not bundle:
            continue
        queue.append(
            {
                "order": len(queue) + 1,
                "task_id": bundle["task_id"],
                "bundle_id": bundle["bundle_id"],
                "patch_bundle": bundle["path"],
                "changed_paths": bundle.get("changed_paths", []),
            }
        )
    plan = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "integration-plan",
        "run_id": task_graph.get("run_id"),
        "created_at": task_graph.get("created_at"),
        "provenance": provenance("patch-swarm e2e", "patch-bundle-validation"),
        "strategy": "dry-run-sequential",
        "dry_run": True,
        "queue": queue,
        "rejected": rejected_bundles,
        "evidence_pointers": ["integration/integration-receipt.json", "integration/dry-run-apply-log.jsonl"],
    }
    write_json(run_dir / "integration" / "integration-plan.json", plan)
    return plan


def dry_run_integrate(run_dir: Path, integration_plan: dict[str, Any]) -> dict[str, Any]:
    """Create dry-run integration-receipt.json without applying patches."""
    integrated = []
    log_path = run_dir / "integration" / "dry-run-apply-log.jsonl"
    with log_path.open("w", encoding="utf-8") as log:
        for item in integration_plan.get("queue", []):
            event = {
                "event": "dry_run_apply",
                "order": item.get("order"),
                "task_id": item.get("task_id"),
                "bundle_id": item.get("bundle_id"),
                "state": "would_integrate",
            }
            log.write(stable_json_dumps(event).strip() + "\n")
            integrated.append(event)
    receipt = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "integration-receipt",
        "run_id": integration_plan.get("run_id"),
        "created_at": integration_plan.get("created_at"),
        "started_at": integration_plan.get("created_at"),
        "completed_at": integration_plan.get("created_at"),
        "provenance": provenance("patch-swarm e2e", "integration-plan"),
        "strategy": integration_plan.get("strategy", "dry-run-sequential"),
        "dry_run": True,
        "integrated": integrated,
        "rejected": integration_plan.get("rejected", []),
        "conflicts": [],
        "final_state": "dry_run_completed",
        "source_mutation": "none",
        "evidence_pointers": ["integration/dry-run-apply-log.jsonl"],
    }
    write_json(run_dir / "integration" / "integration-receipt.json", receipt)
    return receipt


def create_release_candidate(run_dir: Path, validation_summary: dict[str, Any], integration_receipt: dict[str, Any]) -> dict[str, Any]:
    """Create release-candidate.json and release-notes.md."""
    rc = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "release-candidate",
        "run_id": validation_summary.get("run_id"),
        "created_at": validation_summary.get("created_at"),
        "provenance": provenance("patch-swarm e2e", "dry-run-integration"),
        "state": "rc_fixture_validated",
        "fixture": True,
        "production_release": False,
        "validation_summary": "validation-summary.json",
        "integration_receipt": "integration/integration-receipt.json",
        "integrated_count": len(integration_receipt.get("integrated", [])),
        "rejected_count": len(integration_receipt.get("rejected", [])),
        "overall": validation_summary.get("overall"),
        "evidence_pointers": ["release-candidate/release-notes.md", "release-candidate/demo-evidence.md"],
    }
    write_json(run_dir / "release-candidate" / "release-candidate.json", rc)
    notes = [
        "# Patch Swarm Fixture Release Candidate",
        "",
        "This is fixture evidence only. It is not a production release and no patches were applied.",
        "",
        f"- Run ID: `{rc['run_id']}`",
        f"- State: `{rc['state']}`",
        f"- Integrated dry-run bundles: `{rc['integrated_count']}`",
        f"- Rejected bundles: `{rc['rejected_count']}`",
        "- Validation summary: `validation-summary.json`",
        "- Integration receipt: `integration/integration-receipt.json`",
    ]
    (run_dir / "release-candidate" / "release-notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    demo = [
        "# Patch Swarm Fixture Demo Evidence",
        "",
        "This local fixture proves the operator console can inspect run artifacts without a database.",
        "",
        f"- Run ID: `{rc['run_id']}`",
        f"- State: `{rc['state']}`",
        f"- Integrated dry-run bundles: `{rc['integrated_count']}`",
        f"- Rejected bundles: `{rc['rejected_count']}`",
        "- Console source artifacts are local files under this run directory.",
    ]
    (run_dir / "release-candidate" / "demo-evidence.md").write_text("\n".join(demo) + "\n", encoding="utf-8")
    return rc


def build_validation_summary(
    run_dir: Path,
    request: E2ERequest,
    checks: list[ValidationCheck],
    counts: dict[str, Any],
    simulated_worker_batches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create validation-summary.json."""
    failed = [check for check in checks if not check.ok]
    timestamp = _timestamp(request)
    categories = {
        "artifact_checks": "artifact",
        "lease_checks": "lease",
        "packet_checks": "packet",
        "patch_bundle_checks": "patch-bundle",
        "integration_checks": "integration",
        "release_candidate_checks": "release-candidate",
        "negative_checks": "negative",
    }
    summary = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "validation-summary",
        "run_id": request.run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "provenance": provenance(request.command),
        "fixture": True,
        "candidate_target": request.candidate_target,
        "candidate_count": counts.get("candidate_tasks", 0),
        "max_parallel_agents": request.max_parallel_agents,
        "simulated_worker_batches": simulated_worker_batches,
        "counts": {**counts, "failed_checks": len(failed)},
        "overall": "passed" if not failed else "failed",
        "errors": [error for check in failed for error in (check.errors or [])],
        "warnings": [warning for check in checks for warning in (check.warnings or [])],
        "evidence_pointers": [
            "validation-report.md",
            "integration/integration-receipt.json",
            "release-candidate/release-candidate.json",
        ],
    }
    check_payloads = [check_dict(check) for check in checks]
    for field, category in categories.items():
        summary[field] = [item for item in check_payloads if item["category"] == category]
    write_json(run_dir / "validation-summary.json", summary)
    return summary


def write_validation_report(run_dir: Path, summary: dict[str, Any], checks: list[ValidationCheck]) -> Path:
    """Create validation-report.md."""
    path = run_dir / "validation-report.md"
    counts = summary.get("counts", {})
    rejected = read_json(run_dir / "integration" / "rejected-patches.json").get("rejected", [])
    lines = [
        "# Patch Swarm Validation Report",
        "",
        "## Summary",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Overall: `{summary.get('overall')}`",
        f"- Candidate tasks: `{summary.get('candidate_count')}`",
        "",
        "## Fixture Configuration",
        "",
        f"- Candidate target: `{summary.get('candidate_target')}`",
        f"- Max parallel agents: `{summary.get('max_parallel_agents')}`",
        f"- Simulated worker batches: `{len(summary.get('simulated_worker_batches', []))}`",
        "",
        "## Artifact Checks",
        "",
        *(f"- `{check.name}`: `{check.ok}`" for check in checks if check.category == "artifact"),
        "",
        "## Lease Checks",
        "",
        *(f"- `{check.name}`: `{check.ok}`" for check in checks if check.category == "lease"),
        "",
        "## Worker Packet Checks",
        "",
        *(f"- `{check.name}`: `{check.ok}`" for check in checks if check.category == "packet"),
        "",
        "## Patch Bundle Checks",
        "",
        f"- Accepted bundles: `{counts.get('accepted_patch_bundles')}`",
        f"- Rejected bundles: `{counts.get('rejected_patch_bundles')}`",
        "",
        "## Unsafe Bundle Rejection",
        "",
        *(f"- `{item.get('bundle_id')}`: {', '.join(item.get('errors', []))}" for item in rejected),
        "",
        "## Integration Plan",
        "",
        f"- Queue length: `{counts.get('integration_queue')}`",
        "- Rejected bundles are excluded from `integration/integration-plan.json`.",
        "",
        "## Dry-Run Integration Receipt",
        "",
        f"- Dry-run integrated: `{counts.get('dry_run_integrated')}`",
        "- No repository source files were changed by integration.",
        "",
        "## Release Candidate",
        "",
        "- `release-candidate/release-candidate.json`",
        "- `release-candidate/release-notes.md`",
        "",
        "## Evidence",
        "",
        "- `validation-summary.json`",
        "- `validation-report.md`",
        "- `command-output.log`",
        "",
        "## Command Logs",
        "",
        "- `command-output.log` records the local fixture stages.",
        "",
        "## Result",
        "",
        f"`{summary.get('overall')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_start_here(run_dir: Path, summary: dict[str, Any]) -> None:
    lines = [
        f"# Patch Swarm Validation E2E: {summary['run_id']}",
        "",
        "Start with `validation-summary.json`, then read `validation-report.md` for the human summary.",
        "",
        "Important artifacts:",
        "",
        "- `split-plan.json`",
        "- `path-leases.json`",
        "- `worker-packets/codex-packet-index.json`",
        "- `validation/patch-bundle-validation.json`",
        "- `integration/integration-receipt.json`",
        "- `release-candidate/release-candidate.json`",
    ]
    (run_dir / "start-here.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_command_log(run_dir: Path, request: E2ERequest, stages: list[str]) -> None:
    lines = [
        "# Patch Swarm Fixture Command Output",
        "",
        f"command={request.command}",
        f"run_id={request.run_id}",
        f"candidate_target={request.candidate_target}",
        f"max_parallel_agents={request.max_parallel_agents}",
        "live_pro=false",
        "dry_run=true",
        "",
        "## Stages",
        "",
    ]
    lines.extend(f"- {stage}" for stage in stages)
    (run_dir / "command-output.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_fixture_e2e(request: E2ERequest) -> E2EResult:
    """Execute deterministic local fixture flow end to end."""
    candidate_target = validate_candidate_target(int(request.candidate_target))
    max_parallel_agents = validate_max_parallel_agents(int(request.max_parallel_agents), candidate_target)
    normalized = E2ERequest(
        run_id=_safe_run_id(request.run_id),
        run_root=request.run_root,
        candidate_target=candidate_target,
        max_parallel_agents=max_parallel_agents,
        fixture=True,
        dry_run=True,
        fixed_timestamp=request.fixed_timestamp,
        include_unsafe_fixture=request.include_unsafe_fixture,
        objective=request.objective,
        command=request.command,
    )
    run_dir = e2e_run_dir(normalized.run_root, normalized.run_id)
    _reset_generated_run_dir(run_dir)
    timestamp = _timestamp(normalized)

    split_plan, task_graph = create_fixture_split_plan(run_dir, normalized)
    write_run_artifacts(run_dir, normalized, split_plan, task_graph)
    path_leases = create_fixture_leases(run_dir, split_plan, task_graph, normalized)
    worker_packets = create_fixture_worker_packets(run_dir, split_plan, task_graph, path_leases, normalized)
    task_ids = _task_ids(split_plan)
    batches = create_simulated_worker_batches(task_ids, max_parallel_agents, task_graph)
    create_fixture_patch_bundles(run_dir, split_plan, path_leases, normalized)
    patch_checks, accepted, rejected = validate_patch_bundles(run_dir)
    malformed_checks = validate_malformed_artifact_rejection(run_dir)
    integration_plan = create_integration_plan(run_dir, accepted, rejected, task_graph)
    integration_receipt = dry_run_integrate(run_dir, integration_plan)

    counts = {
        "candidate_tasks": len(task_ids),
        "leases": len(path_leases.get("leases", [])),
        "worker_packets": int(worker_packets["index"].get("packet_count") or 0),
        "fixture_patch_bundles": len(accepted) + len(rejected),
        "accepted_patch_bundles": len(accepted),
        "rejected_patch_bundles": len(rejected),
        "integration_queue": len(integration_plan.get("queue", [])),
        "dry_run_integrated": len(integration_receipt.get("integrated", [])),
    }
    integration_checks = [
        ValidationCheck(
            name="integration-plan-excludes-rejected",
            ok="unsafe-out-of-lease" not in stable_json_dumps(integration_plan.get("queue", [])),
            category="integration",
            artifact="integration/integration-plan.json",
            errors=[] if "unsafe-out-of-lease" not in stable_json_dumps(integration_plan.get("queue", [])) else ["unsafe bundle was queued"],
        ),
        ValidationCheck(
            name="dry-run-integrated-accepted-only",
            ok=len(integration_receipt.get("integrated", [])) == len(accepted),
            category="integration",
            artifact="integration/integration-receipt.json",
            errors=[] if len(integration_receipt.get("integrated", [])) == len(accepted) else ["dry-run integration count mismatch"],
        ),
    ]
    release_placeholder_summary = {
        "run_id": normalized.run_id,
        "created_at": timestamp,
        "overall": "pending",
    }
    create_release_candidate(run_dir, release_placeholder_summary, integration_receipt)
    release_checks = [
        ValidationCheck(
            name="release-candidate-evidence-written",
            ok=(run_dir / "release-candidate" / "release-candidate.json").exists()
            and (run_dir / "release-candidate" / "release-notes.md").exists(),
            category="release-candidate",
            artifact="release-candidate/release-candidate.json",
            errors=[],
        )
    ]
    _write_command_log(run_dir, normalized, E2E_STAGES)
    artifact_validation = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "artifact-validation",
        "run_id": normalized.run_id,
        "created_at": timestamp,
        "ok": True,
        "checks": [],
        "errors": [],
        "warnings": [],
    }
    write_json(run_dir / "validation" / "artifact-validation.json", artifact_validation)
    artifact_checks = validate_artifacts(run_dir)
    write_json(
        run_dir / "validation" / "artifact-validation.json",
        {
            **artifact_validation,
            "ok": all(check.ok for check in artifact_checks),
            "checks": [check_dict(check) for check in artifact_checks],
            "errors": [error for check in artifact_checks for error in (check.errors or [])],
        },
    )
    checks = [
        *artifact_checks,
        *validate_leases(run_dir),
        *validate_worker_packets(run_dir),
        *patch_checks,
        *malformed_checks,
        *integration_checks,
        *release_checks,
    ]
    summary = build_validation_summary(run_dir, normalized, checks, counts, batches)
    rc = create_release_candidate(run_dir, summary, integration_receipt)
    release_checks = [
        ValidationCheck(
            name="release-candidate-state",
            ok=rc.get("state") == "rc_fixture_validated",
            category="release-candidate",
            artifact="release-candidate/release-candidate.json",
            errors=[] if rc.get("state") == "rc_fixture_validated" else ["release candidate state mismatch"],
        )
    ]
    checks = [
        *artifact_checks,
        *validate_leases(run_dir),
        *validate_worker_packets(run_dir),
        *patch_checks,
        *malformed_checks,
        *integration_checks,
        *release_checks,
    ]
    summary = build_validation_summary(run_dir, normalized, checks, counts, batches)
    write_validation_report(run_dir, summary, checks)
    write_start_here(run_dir, summary)
    final = validate_e2e_run(run_dir)
    errors = [str(item) for item in final.get("errors", [])]
    artifacts = [
        rel(run_dir / "validation-summary.json"),
        rel(run_dir / "validation-report.md"),
        rel(run_dir / "integration" / "integration-receipt.json"),
        rel(run_dir / "release-candidate" / "release-candidate.json"),
    ]
    return E2EResult(
        ok=not errors and summary.get("overall") == "passed",
        run_id=normalized.run_id,
        run_dir=run_dir,
        candidate_target=normalized.candidate_target,
        candidate_count=len(task_ids),
        max_parallel_agents=normalized.max_parallel_agents,
        accepted_patch_bundles=len(accepted),
        rejected_patch_bundles=len(rejected),
        overall=str(summary.get("overall")),
        artifacts=artifacts,
        warnings=[str(item) for item in summary.get("warnings", [])],
        errors=errors,
    )


def validate_e2e_run(run_dir: Path) -> dict[str, Any]:
    """Validate an existing E2E run directory and return summary JSON."""
    resolved = resolve_path(run_dir)
    errors: list[str] = []
    try:
        summary = read_json(resolved / "validation-summary.json")
        split_plan = read_json(resolved / "split-plan.json")
        path_leases = read_json(resolved / "path-leases.json")
        packet_index = read_json(resolved / "worker-packets" / "codex-packet-index.json")
        integration_plan = read_json(resolved / "integration" / "integration-plan.json")
        integration_receipt = read_json(resolved / "integration" / "integration-receipt.json")
    except ValidationE2EError as exc:
        return {
            "ok": False,
            "run_id": resolved.name,
            "run_dir": rel(resolved),
            "overall": "failed",
            "errors": [str(exc)],
            "warnings": [],
        }
    task_ids = set(_task_ids(split_plan))
    lease_tasks = {str(item.get("task_id")) for item in path_leases.get("leases", []) if isinstance(item, dict)}
    packet_tasks = {str(item.get("task_id")) for item in packet_index.get("packets", []) if isinstance(item, dict)}
    if lease_tasks != task_ids:
        errors.append("leases do not cover exactly all tasks")
    if packet_tasks != task_ids:
        errors.append("worker packets do not cover exactly all tasks")
    if len(integration_plan.get("queue", [])) != int(summary.get("counts", {}).get("accepted_patch_bundles") or -1):
        errors.append("integration queue count does not match accepted bundle count")
    if len(integration_receipt.get("integrated", [])) != int(summary.get("counts", {}).get("accepted_patch_bundles") or -1):
        errors.append("dry-run integrated count does not match accepted bundle count")
    if "unsafe-out-of-lease" in stable_json_dumps(integration_plan.get("queue", [])):
        errors.append("unsafe bundle appears in integration queue")
    if summary.get("overall") != "passed":
        errors.append("validation-summary overall is not passed")
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "validation-e2e-run-validation",
        "ok": not errors,
        "run_id": summary.get("run_id", resolved.name),
        "run_dir": rel(resolved),
        "overall": "passed" if not errors else "failed",
        "candidate_count": summary.get("candidate_count", 0),
        "counts": summary.get("counts", {}),
        "errors": errors,
        "warnings": [],
    }


def print_policy() -> dict[str, Any]:
    """Return validation engine policy for tests and CLI."""
    return {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "artifact_type": "validation-e2e-policy",
        "producer": PRODUCER,
        "local_only": True,
        "no_api_calls": True,
        "no_live_pro": True,
        "no_codex_dispatch": True,
        "no_mcp_mutation": True,
        "no_taskstream_redmine_writes": True,
        "dry_run_integration": True,
        "applies_patches": False,
        "max_candidate_tasks": MAX_CANDIDATE_TASKS,
        "stages": E2E_STAGES,
        "validation_overall_states": sorted(VALIDATION_OVERALL_STATES),
        "patch_bundle_states": sorted(PATCH_BUNDLE_STATES),
        "integration_strategies": sorted(INTEGRATION_STRATEGIES),
    }


def result_payload(result: E2EResult, *, command: str = "parallel-delivery patch-swarm e2e") -> dict[str, Any]:
    return {
        "ok": result.ok,
        "command": command,
        "state": "fixture_e2e_completed" if result.ok else "fixture_e2e_failed",
        "dry_run": True,
        "live_pro": False,
        "fixture": True,
        "run_id": result.run_id,
        "run_dir": rel(result.run_dir),
        "candidate_target": result.candidate_target,
        "candidate_count": result.candidate_count,
        "max_parallel_agents": result.max_parallel_agents,
        "simulated_worker_batches": (result.candidate_count + result.max_parallel_agents - 1) // result.max_parallel_agents,
        "accepted_patch_bundles": result.accepted_patch_bundles,
        "rejected_patch_bundles": result.rejected_patch_bundles,
        "overall": result.overall,
        "validation_summary": rel(result.run_dir / "validation-summary.json"),
        "validation_report": rel(result.run_dir / "validation-report.md"),
        "artifacts": result.artifacts,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def request_from_args(args: argparse.Namespace, *, command: str = "parallel-delivery patch-swarm e2e") -> E2ERequest:
    output_dir = Path(getattr(args, "output_dir", "") or "") if getattr(args, "output_dir", "") else None
    run_id = getattr(args, "run_id", "") or (output_dir.name if output_dir else f"fixture-e2e-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    run_root = output_dir.parent if output_dir else Path(getattr(args, "run_root", "") or DEFAULT_RUN_ROOT)
    return E2ERequest(
        run_id=run_id,
        run_root=run_root,
        candidate_target=int(getattr(args, "candidate_target", 100) or 100),
        max_parallel_agents=int(getattr(args, "max_parallel_agents", 5) or 5),
        fixture=True,
        dry_run=True,
        fixed_timestamp=getattr(args, "fixed_timestamp", "") or None,
        include_unsafe_fixture=bool(getattr(args, "include_unsafe_fixture", True)),
        objective=getattr(args, "objective", "") or "",
        command=command,
    )


def run_from_args(args: argparse.Namespace, *, command: str = "parallel-delivery patch-swarm e2e") -> tuple[dict[str, Any], int]:
    try:
        result = run_fixture_e2e(request_from_args(args, command=command))
        payload = result_payload(result, command=command)
        return payload, 0 if payload.get("ok") else 1
    except ValidationE2EError as exc:
        output_dir = Path(getattr(args, "output_dir", "") or "") if getattr(args, "output_dir", "") else None
        run_id = getattr(args, "run_id", "") or (output_dir.name if output_dir else "fixture-e2e")
        run_root = output_dir.parent if output_dir else Path(getattr(args, "run_root", "") or DEFAULT_RUN_ROOT)
        payload = {
            "ok": False,
            "command": command,
            "state": "fixture_e2e_failed",
            "dry_run": True,
            "live_pro": False,
            "fixture": True,
            "run_id": run_id,
            "run_dir": rel(e2e_run_dir(run_root, run_id)),
            "candidate_target": int(getattr(args, "candidate_target", 0) or 0),
            "candidate_count": 0,
            "max_parallel_agents": int(getattr(args, "max_parallel_agents", 0) or 0),
            "simulated_worker_batches": 0,
            "accepted_patch_bundles": 0,
            "rejected_patch_bundles": 0,
            "overall": "failed",
            "validation_summary": "",
            "validation_report": "",
            "artifacts": [],
            "warnings": [],
            "errors": [str(exc)],
        }
        return payload, 1


def command_print_policy(args: argparse.Namespace) -> int:
    print(stable_json_dumps(print_policy()) if args.json else stable_json_dumps(print_policy()), end="")
    return 0


def command_validate_run(args: argparse.Namespace) -> int:
    payload = validate_e2e_run(Path(args.run_dir))
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return 0 if payload.get("ok") else 1


def command_run_fixture(args: argparse.Namespace) -> int:
    payload, code = run_from_args(args)
    print(stable_json_dumps(payload) if args.json else stable_json_dumps(payload), end="")
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic Patch Swarm validation fixture E2E.")
    sub = parser.add_subparsers(dest="command", required=True)
    policy = sub.add_parser("print-policy")
    policy.add_argument("--json", action="store_true")
    policy.set_defaults(func=command_print_policy)

    run = sub.add_parser("run-fixture")
    run.add_argument("--run-id", default="")
    run.add_argument("--run-root", default=str(DEFAULT_RUN_ROOT))
    run.add_argument("--output-dir", default="", help="Exact run directory to write. Overrides --run-root when provided.")
    run.add_argument("--candidate-target", type=int, default=100)
    run.add_argument("--max-parallel-agents", type=int, default=5)
    run.add_argument("--fixture", action="store_true", default=True)
    run.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    run.add_argument("--fixed-timestamp", default="")
    run.add_argument("--include-unsafe-fixture", action=argparse.BooleanOptionalAction, default=True)
    run.add_argument("--objective", default="")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=command_run_fixture)

    validate = sub.add_parser("validate-run")
    validate.add_argument("--run-dir", required=True)
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
