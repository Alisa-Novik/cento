#!/usr/bin/env python3
"""Patch Swarm console aggregation and static HTML rendering.

The console is intentionally artifact-backed: it reads an existing Patch Swarm
run directory, normalizes the operator status view, and writes only console
export files into the requested output directory.
"""

from __future__ import annotations

import argparse
import html
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "workspace" / "runs" / "parallel-delivery"
SCHEMA_VERSION = "cento.parallel_delivery.patch_swarm_console.v1"
VALIDATION_SCHEMA_VERSION = "cento.parallel_delivery.patch_swarm_console.validation.v1"


@dataclass(frozen=True)
class EvidenceLink:
    label: str
    path: str
    exists: bool
    kind: str


@dataclass(frozen=True)
class BundleBucketSummary:
    pending: int
    accepted: int
    rejected: int
    safe_apply: int
    needs_rebase: int
    needs_human_review: int
    reject: int


@dataclass(frozen=True)
class WorkerSummary:
    simulated: bool
    total_workers: int
    active_workers: int
    wave_count: int
    max_parallel_agents: int
    max_observed_parallel_workers: int
    bounded_parallelism_passed: bool


@dataclass(frozen=True)
class TaskGraphSummary:
    total_tasks: int
    dependency_edges: int
    root_tasks: int
    blocked_tasks: int
    conflict_tasks: int


@dataclass(frozen=True)
class IntegrationStatus:
    result: str
    groups: int
    conflicts: int
    safe_apply: int
    needs_rebase: int
    needs_human_review: int
    reject: int
    conflict_report_path: str | None


@dataclass(frozen=True)
class ValidationStatus:
    result: str
    passed_gates: int
    failed_gates: int
    failing_gates: tuple[str, ...]
    report_path: str | None


@dataclass(frozen=True)
class ReleaseCandidateStatus:
    created: bool
    status: str
    path: str | None
    demo_evidence_path: str | None


@dataclass(frozen=True)
class PatchSwarmConsoleData:
    schema_version: str
    run_id: str
    run_dir: str
    generated_at: str
    current_run: dict[str, Any]
    candidate_count: int
    task_graph: TaskGraphSummary
    workers: WorkerSummary
    bundles: BundleBucketSummary
    integration: IntegrationStatus
    validation: ValidationStatus
    release_candidate: ReleaseCandidateStatus
    evidence_links: tuple[EvidenceLink, ...]
    next_action: str
    warnings: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_json(payload: Any, *, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_run_dir(path: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = ROOT / expanded
    return expanded.resolve()


def load_json_file(path: Path) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except OSError as exc:
        return None, f"{rel(path)}: {exc}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, f"{rel(path)}: invalid JSON: {exc}"
    if not isinstance(payload, (dict, list)):
        return None, f"{rel(path)}: expected JSON object or array"
    return payload, None


def _as_dict(payload: Any) -> dict[str, Any] | None:
    return payload if isinstance(payload, dict) else None


def _as_list(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def _first_json(
    run_dir: Path,
    candidates: list[str],
    warnings: list[str],
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    for candidate in candidates:
        path = run_dir / candidate
        payload, error = load_json_file(path)
        if error:
            warnings.append(error)
        if payload is not None:
            return payload, candidate
    return None, None


def _first_existing(run_dir: Path, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if (run_dir / candidate).exists():
            return candidate
    return None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _result_from(*values: Any, default: str = "unknown") -> str:
    for value in values:
        clean = str(value or "").strip()
        if clean:
            if clean in {"ok", "true"}:
                return "passed"
            if clean in {"completed", "dry_run_completed", "rc_fixture_validated"}:
                return "passed"
            return clean
    return default


def _count_bucket(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        for key in ("count", "total", "size"):
            if key in value:
                return _int(value.get(key))
        return len(value)
    return _int(value)


def compute_task_graph_summary(tasks_data: Any, integration_plan: dict[str, Any] | None = None) -> TaskGraphSummary:
    data = _as_dict(tasks_data) or {}
    tasks = _as_list(data.get("tasks"))
    nodes = _as_list(data.get("nodes"))
    edges = _as_list(data.get("edges"))
    if tasks:
        total_tasks = len(tasks)
        edge_count = sum(len(_as_list(task.get("dependencies"))) + len(_as_list(task.get("depends_on"))) for task in tasks if isinstance(task, dict))
        blocked = sum(1 for task in tasks if isinstance(task, dict) and (task.get("blocked") or str(task.get("state") or "").lower() == "blocked"))
        roots = sum(
            1
            for task in tasks
            if isinstance(task, dict)
            and not _as_list(task.get("dependencies"))
            and not _as_list(task.get("depends_on"))
        )
        conflict_tasks = {
            str(task.get("task_id"))
            for task in tasks
            if isinstance(task, dict)
            and (
                task.get("requires_manual_review")
                or task.get("human_handoff")
                or str(task.get("state") or "").lower() in {"conflict", "blocked"}
            )
        }
    else:
        total_tasks = len(nodes)
        edge_count = len(edges)
        incoming = {str(edge.get("to")) for edge in edges if isinstance(edge, dict) and edge.get("to")}
        roots = sum(1 for node in nodes if isinstance(node, dict) and str(node.get("task_id")) not in incoming)
        blocked = sum(1 for node in nodes if isinstance(node, dict) and str(node.get("state") or "").lower() == "blocked")
        conflict_tasks = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        hay = " ".join(str(edge.get(key) or "").lower() for key in ("type", "reason", "status", "state"))
        if any(word in hay for word in ("conflict", "share", "manual", "human")):
            for key in ("from", "to", "source", "target"):
                if edge.get(key):
                    conflict_tasks.add(str(edge[key]))
    if integration_plan:
        for bucket_key in ("needs_human_review", "conflicts", "conflict_tasks"):
            for item in _as_list(integration_plan.get(bucket_key)):
                if isinstance(item, dict) and item.get("task_id"):
                    conflict_tasks.add(str(item["task_id"]))
                elif item:
                    conflict_tasks.add(str(item))
    return TaskGraphSummary(
        total_tasks=total_tasks,
        dependency_edges=edge_count,
        root_tasks=roots,
        blocked_tasks=blocked,
        conflict_tasks=len({item for item in conflict_tasks if item and item != "None"}),
    )


def compute_bundle_summary(
    validation_summary: dict[str, Any] | None,
    patch_validation: dict[str, Any] | None,
    integration_plan: dict[str, Any] | None,
) -> BundleBucketSummary:
    validation_summary = validation_summary or {}
    patch_validation = patch_validation or {}
    integration_plan = integration_plan or {}
    counts = validation_summary.get("counts") if isinstance(validation_summary.get("counts"), dict) else {}
    buckets = integration_plan.get("buckets") if isinstance(integration_plan.get("buckets"), dict) else {}
    accepted = _count_bucket(patch_validation.get("accepted"))
    rejected = _count_bucket(patch_validation.get("rejected"))
    if not accepted:
        accepted = _int(counts.get("accepted_patch_bundles") or validation_summary.get("accepted_patch_bundles"))
    if not rejected:
        rejected = _int(counts.get("rejected_patch_bundles") or validation_summary.get("rejected_patch_bundles"))
    safe_apply = _count_bucket(buckets.get("safe_apply")) or _count_bucket(integration_plan.get("safe_apply")) or len(_as_list(integration_plan.get("queue")))
    needs_rebase = _count_bucket(buckets.get("needs_rebase")) or _count_bucket(integration_plan.get("needs_rebase"))
    needs_human_review = _count_bucket(buckets.get("needs_human_review")) or _count_bucket(integration_plan.get("needs_human_review"))
    reject = _count_bucket(buckets.get("reject")) or _count_bucket(integration_plan.get("reject")) or len(_as_list(integration_plan.get("rejected")))
    candidate_count = _int(validation_summary.get("candidate_count") or validation_summary.get("candidate_target"))
    pending = max(0, candidate_count - accepted - rejected)
    return BundleBucketSummary(
        pending=pending,
        accepted=accepted,
        rejected=rejected,
        safe_apply=safe_apply,
        needs_rebase=needs_rebase,
        needs_human_review=needs_human_review,
        reject=reject,
    )


def compute_worker_summary(
    validation_summary: dict[str, Any] | None,
    worker_waves: dict[str, Any] | list[Any] | None,
) -> WorkerSummary:
    validation_summary = validation_summary or {}
    batches = _as_list(validation_summary.get("simulated_worker_batches"))
    waves = _as_list(worker_waves) or _as_list((_as_dict(worker_waves) or {}).get("waves"))
    max_parallel_agents = _int(validation_summary.get("max_parallel_agents") or (_as_dict(worker_waves) or {}).get("max_parallel_agents"))
    observed = 0
    for batch in [*batches, *waves]:
        if not isinstance(batch, dict):
            continue
        observed = max(observed, len(_as_list(batch.get("task_ids") or batch.get("workers"))))
    active_workers = sum(
        1
        for wave in waves
        if isinstance(wave, dict)
        for worker in _as_list(wave.get("workers"))
        if isinstance(worker, dict) and str(worker.get("status") or "").lower() in {"active", "running", "working"}
    )
    total_workers = max(max_parallel_agents, observed, _int((_as_dict(worker_waves) or {}).get("total_workers")))
    return WorkerSummary(
        simulated=bool(validation_summary.get("fixture") or batches),
        total_workers=total_workers,
        active_workers=active_workers,
        wave_count=len(waves) or len(batches),
        max_parallel_agents=max_parallel_agents,
        max_observed_parallel_workers=observed,
        bounded_parallelism_passed=not max_parallel_agents or observed <= max_parallel_agents,
    )


def compute_validation_status(
    validation_summary: dict[str, Any] | None,
    validation_report_path: str | None,
) -> ValidationStatus:
    if not validation_summary:
        return ValidationStatus("missing", 0, 1, ("validation-summary.json missing",), validation_report_path)
    gates: list[dict[str, Any]] = []
    for key, value in validation_summary.items():
        if key.endswith("_checks") and isinstance(value, list):
            gates.extend(item for item in value if isinstance(item, dict))
    failed = [
        str(item.get("name") or item.get("gate") or item.get("artifact") or "unnamed gate")
        for item in gates
        if item.get("ok") is False or item.get("status") == "failed"
    ]
    failed_count = len(failed) or _int((validation_summary.get("counts") or {}).get("failed_checks") if isinstance(validation_summary.get("counts"), dict) else 0)
    passed_count = max(0, len(gates) - failed_count)
    result = _result_from(validation_summary.get("overall"), validation_summary.get("result"), validation_summary.get("status"), default="unknown")
    return ValidationStatus(result, passed_count, failed_count, tuple(failed), validation_report_path)


def compute_integration_status(
    integration_plan: dict[str, Any] | None,
    integration_receipt: dict[str, Any] | None,
    dry_run_summary: dict[str, Any] | None,
    path_leases: dict[str, Any] | None,
    bundles: BundleBucketSummary,
    conflict_report_path: str | None,
) -> IntegrationStatus:
    integration_plan = integration_plan or {}
    integration_receipt = integration_receipt or {}
    dry_run_summary = dry_run_summary or {}
    path_leases = path_leases or {}
    groups = len(_as_list(integration_plan.get("groups"))) or len(_as_list(path_leases.get("parallel_groups")))
    conflicts = (
        len(_as_list(integration_plan.get("conflicts")))
        or len(_as_list(path_leases.get("conflicts")))
        or bundles.needs_human_review
    )
    result = _result_from(
        dry_run_summary.get("result"),
        dry_run_summary.get("status"),
        integration_receipt.get("final_state"),
        integration_receipt.get("status"),
        "passed" if integration_plan else "",
        default="missing",
    )
    return IntegrationStatus(
        result=result,
        groups=groups,
        conflicts=conflicts,
        safe_apply=bundles.safe_apply,
        needs_rebase=bundles.needs_rebase,
        needs_human_review=bundles.needs_human_review,
        reject=bundles.reject,
        conflict_report_path=conflict_report_path,
    )


def compute_release_candidate_status(
    release_candidate: dict[str, Any] | None,
    release_candidate_path: str | None,
    demo_evidence_path: str | None,
) -> ReleaseCandidateStatus:
    if not release_candidate:
        return ReleaseCandidateStatus(False, "missing", None, demo_evidence_path)
    status = _result_from(
        release_candidate.get("status"),
        release_candidate.get("state"),
        release_candidate.get("overall"),
        default="created",
    )
    if status == "passed":
        status = "ready_for_operator_review"
    return ReleaseCandidateStatus(True, status, release_candidate_path, demo_evidence_path)


def collect_evidence_links(run_dir: Path, console_data: PatchSwarmConsoleData | None = None) -> list[EvidenceLink]:
    del console_data
    specs = [
        ("Validation Summary", ["validation-summary.json", "validation_summary.json"], "json"),
        ("Validation Report", ["validation-report.md", "validation_report.md"], "markdown"),
        ("Request", ["00-request/request.json", "request.md", "run.json"], "markdown"),
        ("Task Graph", ["01-split/tasks.json", "task-graph.json", "split-plan.json"], "json"),
        ("Path Leases", ["02-leases/path-leases.json", "path-leases.json"], "json"),
        ("Worker Packets", ["03-worker-packets/worker-waves.json", "worker-packets/codex-packet-index.json"], "json"),
        ("Patch Validation", ["05-patch-validation/patch-validation-summary.json", "validation/patch-bundle-validation.json"], "json"),
        ("Integration Plan", ["06-integration-plan/integration-plan.json", "integration/integration-plan.json", "integration_execution/integration_execution.json"], "json"),
        ("Conflict Report", ["06-integration-plan/conflict-report.md", "integration/conflict-report.md", "integration/rejected-patches.json"], "markdown"),
        ("Dry Run Integration", ["07-dry-run-integration/dry-run-summary.json", "integration/integration-receipt.json"], "json"),
        ("Release Candidate", ["08-release-candidate/release-candidate.json", "release-candidate/release-candidate.json"], "json"),
        ("Demo Evidence", ["08-release-candidate/demo-evidence.md", "release-candidate/demo-evidence.md", "release-candidate/release-notes.md"], "markdown"),
        ("Console Data", ["console-data.json"], "json"),
    ]
    links: list[EvidenceLink] = []
    for label, candidates, kind in specs:
        chosen = _first_existing(run_dir, candidates) or candidates[0]
        exists = (run_dir / chosen).exists() or chosen == "console-data.json"
        links.append(EvidenceLink(label=label, path=chosen, exists=exists, kind=kind))
    return links


def compute_next_action(console_data: PatchSwarmConsoleData) -> str:
    if console_data.validation.result == "missing":
        return "Generate or repair fixture validation summary"
    if console_data.validation.result in {"failed", "error", "blocked"} or console_data.validation.failed_gates > 0:
        return "Inspect validation-report.md and failing stage"
    if console_data.bundles.rejected > 0 or console_data.bundles.reject > 0:
        return "Review rejected bundles before release candidate"
    if console_data.integration.needs_human_review > 0 or console_data.integration.conflicts > 0:
        return "Resolve conflicts in conflict-report.md"
    if console_data.integration.result in {"failed", "error", "blocked"}:
        return "Run rebase or dry-run repair for affected bundles"
    if not console_data.release_candidate.created:
        return "Create release candidate evidence"
    if console_data.validation.result == "passed" and console_data.release_candidate.created:
        return "Ready for operator demo/release review"
    return "Inspect run artifacts and repair missing status evidence"


def collect_patch_swarm_console_data(run_dir: Path) -> PatchSwarmConsoleData:
    resolved = normalize_run_dir(run_dir)
    warnings: list[str] = []
    validation_payload, validation_path = _first_json(resolved, ["validation-summary.json", "validation_summary.json"], warnings)
    split_payload, _split_path = _first_json(resolved, ["01-split/tasks.json", "split-plan.json"], warnings)
    task_graph_payload, _task_graph_path = _first_json(resolved, ["task-graph.json", "01-split/task-graph.json"], warnings)
    path_leases_payload, _path_leases_path = _first_json(resolved, ["02-leases/path-leases.json", "path-leases.json"], warnings)
    worker_waves_payload, _worker_waves_path = _first_json(resolved, ["03-worker-packets/worker-waves.json"], warnings)
    patch_validation_payload, _patch_validation_path = _first_json(
        resolved,
        ["05-patch-validation/patch-validation-summary.json", "validation/patch-bundle-validation.json"],
        warnings,
    )
    integration_payload, _integration_path = _first_json(
        resolved,
        ["06-integration-plan/integration-plan.json", "integration/integration-plan.json", "integration_execution/integration_execution.json"],
        warnings,
    )
    integration_receipt_payload, _integration_receipt_path = _first_json(resolved, ["integration/integration-receipt.json"], warnings)
    dry_run_payload, _dry_run_path = _first_json(resolved, ["07-dry-run-integration/dry-run-summary.json"], warnings)
    release_payload, release_path = _first_json(
        resolved,
        ["08-release-candidate/release-candidate.json", "release-candidate/release-candidate.json", "release_candidate/release-candidate.json"],
        warnings,
    )
    manifest_payload, _manifest_path = _first_json(resolved, ["patch_swarm_manifest.json", "run.json"], warnings)
    receipt_payload, _receipt_path = _first_json(resolved, ["patch_swarm_receipt.json"], warnings)

    validation_summary = _as_dict(validation_payload)
    split_data = _as_dict(split_payload)
    task_graph_data = _as_dict(task_graph_payload)
    tasks_data = split_data if split_data and split_data.get("tasks") else task_graph_data or split_data or {}
    path_leases = _as_dict(path_leases_payload)
    patch_validation = _as_dict(patch_validation_payload)
    integration_plan = _as_dict(integration_payload)
    integration_receipt = _as_dict(integration_receipt_payload)
    dry_run_summary = _as_dict(dry_run_payload)
    release_candidate = _as_dict(release_payload)
    manifest = _as_dict(manifest_payload) or {}
    receipt = _as_dict(receipt_payload) or {}

    bundles = compute_bundle_summary(validation_summary, patch_validation, integration_plan)
    validation_report_path = _first_existing(resolved, ["validation-report.md", "validation_report.md"])
    conflict_report_path = _first_existing(
        resolved,
        ["06-integration-plan/conflict-report.md", "integration/conflict-report.md", "integration/rejected-patches.json"],
    )
    demo_evidence_path = _first_existing(
        resolved,
        ["08-release-candidate/demo-evidence.md", "release-candidate/demo-evidence.md", "release-candidate/release-notes.md"],
    )
    candidate_count = (
        _int((validation_summary or {}).get("candidate_count"))
        or _int((validation_summary or {}).get("candidate_target"))
        or _int((split_data or {}).get("candidate_count"))
        or _int(receipt.get("candidate_count"))
        or bundles.accepted + bundles.pending
    )
    current_run = {
        "result": _result_from(
            (validation_summary or {}).get("overall"),
            (validation_summary or {}).get("result"),
            (validation_summary or {}).get("status"),
            receipt.get("status"),
            manifest.get("status"),
            default="unknown",
        ),
        "fixture": bool((validation_summary or {}).get("fixture") or manifest.get("fixture")),
        "offline": True,
        "dry_run": bool((manifest or {}).get("dry_run") or (integration_plan or {}).get("dry_run") or (integration_receipt or {}).get("dry_run")),
        "created_at": str((validation_summary or {}).get("created_at") or manifest.get("created_at") or ""),
        "updated_at": str((validation_summary or {}).get("updated_at") or manifest.get("updated_at") or ""),
    }
    data = PatchSwarmConsoleData(
        schema_version=SCHEMA_VERSION,
        run_id=str((validation_summary or {}).get("run_id") or manifest.get("run_id") or receipt.get("run_id") or resolved.name),
        run_dir=rel(resolved),
        generated_at=utc_now(),
        current_run=current_run,
        candidate_count=candidate_count,
        task_graph=compute_task_graph_summary(tasks_data, integration_plan),
        workers=compute_worker_summary(validation_summary, worker_waves_payload),
        bundles=bundles,
        integration=compute_integration_status(
            integration_plan,
            integration_receipt,
            dry_run_summary,
            path_leases,
            bundles,
            conflict_report_path,
        ),
        validation=compute_validation_status(validation_summary, validation_report_path),
        release_candidate=compute_release_candidate_status(release_candidate, release_path, demo_evidence_path),
        evidence_links=tuple(collect_evidence_links(resolved)),
        next_action="",
        warnings=tuple(warnings),
    )
    return replace(data, next_action=compute_next_action(data))


def console_data_to_dict(console_data: PatchSwarmConsoleData) -> dict[str, Any]:
    return asdict(console_data)


def write_console_data(console_data: PatchSwarmConsoleData, output_dir: Path) -> Path:
    resolved = normalize_run_dir(output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / "console-data.json"
    path.write_text(stable_json(console_data_to_dict(console_data), pretty=True), encoding="utf-8")
    return path


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _status_class(value: str) -> str:
    clean = str(value or "").lower()
    if clean in {"passed", "ready_for_operator_review", "rc_fixture_validated", "completed", "ok"}:
        return "good"
    if clean in {"failed", "blocked", "error", "missing"}:
        return "bad"
    return "warn"


def _metric(label: str, value: Any, detail: str = "") -> str:
    return (
        "<article>"
        f"<span>{_esc(label)}</span>"
        f"<strong>{_esc(value)}</strong>"
        f"<small>{_esc(detail)}</small>"
        "</article>"
    )


def _display_status(value: Any) -> str:
    return str(value if value is not None else "").replace("_", " ")


def _section_table(caption: str, rows: list[tuple[str, Any]]) -> str:
    body = "".join(f"<tr><th scope=\"row\">{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in rows)
    return f"<table><caption>{_esc(caption)}</caption><tbody>{body}</tbody></table>"


def _evidence_html(links: tuple[EvidenceLink, ...]) -> str:
    items = []
    for link in links:
        status = "available" if link.exists else "missing"
        if link.exists:
            items.append(
                "<li>"
                f"<a href=\"{_esc(link.path)}\">{_esc(link.label)}</a>"
                f"<span>{_esc(link.kind)} - {_esc(status)} - {_esc(link.path)}</span>"
                "</li>"
            )
        else:
            items.append(
                "<li class=\"missing\">"
                f"<span>{_esc(link.label)}</span>"
                f"<em>{_esc(link.kind)} - {_esc(status)} - {_esc(link.path)}</em>"
                "</li>"
            )
    return "<ul class=\"evidenceList\">" + "".join(items) + "</ul>"


def render_patch_swarm_html(console_data: PatchSwarmConsoleData, output_dir: Path) -> Path:
    resolved = normalize_run_dir(output_dir)
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / "start-here.html"
    result = str(console_data.current_run.get("result") or "unknown")
    css = """
    :root { color-scheme: dark; --bg: #101214; --panel: #181c20; --text: #f4f1eb; --muted: #aeb6bd; --line: #303840; --good: #2fc483; --warn: #e0b84e; --bad: #f07167; --accent: #65b7ff; }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 Arial, Helvetica, sans-serif; }
    header, main { max-width: 1180px; margin: 0 auto; padding: 24px; }
    header { display: grid; gap: 12px; border-bottom: 1px solid var(--line); }
    h1, h2 { margin: 0; line-height: 1.15; letter-spacing: 0; }
    h1 { font-size: 2rem; }
    h2 { font-size: 1.2rem; }
    p { margin: 0; color: var(--muted); }
    .badge { display: inline-flex; width: fit-content; border: 1px solid var(--line); padding: 4px 9px; font-weight: 700; text-transform: uppercase; font-size: 0.76rem; }
    .badge.good { color: var(--good); border-color: rgba(47,196,131,.55); }
    .badge.warn { color: var(--warn); border-color: rgba(224,184,78,.55); }
    .badge.bad { color: var(--bad); border-color: rgba(240,113,103,.55); }
    .nextAction { padding: 14px 16px; background: #1d2429; border-left: 4px solid var(--accent); }
    main { display: grid; gap: 18px; }
    section { border: 1px solid var(--line); background: var(--panel); padding: 18px; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; }
    article { min-width: 0; padding: 13px; border: 1px solid var(--line); background: #11161a; }
    article span, caption { display: block; color: var(--muted); font-size: .74rem; font-weight: 700; text-transform: uppercase; text-align: left; }
    article strong { display: block; margin-top: 4px; font-size: 1.3rem; overflow-wrap: anywhere; }
    article small { display: block; margin-top: 3px; color: var(--muted); overflow-wrap: anywhere; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 9px 10px; border-top: 1px solid var(--line); text-align: left; vertical-align: top; overflow-wrap: anywhere; }
    th { width: 42%; color: var(--muted); font-weight: 700; }
    a { color: var(--accent); }
    .evidenceList { list-style: none; padding: 0; margin: 12px 0 0; display: grid; gap: 8px; }
    .evidenceList li { display: grid; gap: 2px; padding: 10px; border: 1px solid var(--line); background: #11161a; }
    .evidenceList span, .evidenceList em { color: var(--muted); font-style: normal; overflow-wrap: anywhere; }
    .evidenceList .missing { opacity: .72; }
    .warnings { color: var(--warn); }
    @media (max-width: 760px) { header, main { padding: 16px; } h1 { font-size: 1.55rem; } section { padding: 14px; } }
    """
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Patch Swarm Console - {_esc(console_data.run_id)}</title>
  <style>{css}</style>
</head>
<body>
  <header>
    <span class="badge {_status_class(result)}">{_esc(result)}</span>
    <h1>Patch Swarm Current Run: {_esc(console_data.run_id)}</h1>
    <p>{_esc(console_data.run_dir)}</p>
    <div class="nextAction"><strong>Next Action</strong><p>{_esc(console_data.next_action)}</p></div>
  </header>
  <main>
    <section id="summary-cards" aria-labelledby="summary-title">
      <h2 id="summary-title">Patch Swarm Summary</h2>
      <div class="cards">
        {_metric("Candidate Count", console_data.candidate_count)}
        {_metric("Active Workers", console_data.workers.active_workers, f"max observed {console_data.workers.max_observed_parallel_workers}")}
        {_metric("Accepted Bundles", console_data.bundles.accepted)}
        {_metric("Rejected Bundles", console_data.bundles.rejected)}
        {_metric("Integration Status", _display_status(console_data.integration.result))}
        {_metric("Validation Status", _display_status(console_data.validation.result))}
        {_metric("Release Candidate", _display_status(console_data.release_candidate.status))}
      </div>
    </section>
    <section id="current-run" aria-labelledby="current-run-title">
      <h2 id="current-run-title">Current Run</h2>
      {_section_table("Current run details", list(console_data.current_run.items()) + [("generated_at", console_data.generated_at)])}
    </section>
    <section id="task-graph" aria-labelledby="task-graph-title">
      <h2 id="task-graph-title">Task Graph</h2>
      <div class="cards">
        {_metric("Tasks", console_data.task_graph.total_tasks)}
        {_metric("Dependency Edges", console_data.task_graph.dependency_edges)}
        {_metric("Root Tasks", console_data.task_graph.root_tasks)}
        {_metric("Blocked Tasks", console_data.task_graph.blocked_tasks)}
        {_metric("Conflict Tasks", console_data.task_graph.conflict_tasks)}
      </div>
    </section>
    <section id="workers" aria-labelledby="workers-title">
      <h2 id="workers-title">Workers</h2>
      {_section_table("Worker summary", [
        ("simulated", console_data.workers.simulated),
        ("total_workers", console_data.workers.total_workers),
        ("active_workers", console_data.workers.active_workers),
        ("wave_count", console_data.workers.wave_count),
        ("max_parallel_agents", console_data.workers.max_parallel_agents),
        ("max_observed_parallel_workers", console_data.workers.max_observed_parallel_workers),
        ("bounded_parallelism_passed", console_data.workers.bounded_parallelism_passed),
      ])}
    </section>
    <section id="bundles" aria-labelledby="bundles-title">
      <h2 id="bundles-title">Bundles</h2>
      <div class="cards">
        {_metric("Pending", console_data.bundles.pending)}
        {_metric("Accepted", console_data.bundles.accepted)}
        {_metric("Rejected", console_data.bundles.rejected)}
        {_metric("Safe Apply", console_data.bundles.safe_apply)}
        {_metric("Needs Rebase", console_data.bundles.needs_rebase)}
        {_metric("Needs Human Review", console_data.bundles.needs_human_review)}
        {_metric("Reject", console_data.bundles.reject)}
      </div>
    </section>
    <section id="integration" aria-labelledby="integration-title">
      <h2 id="integration-title">Integration</h2>
      {_section_table("Integration status", [
        ("result", console_data.integration.result),
        ("groups", console_data.integration.groups),
        ("conflicts", console_data.integration.conflicts),
        ("safe_apply", console_data.integration.safe_apply),
        ("needs_rebase", console_data.integration.needs_rebase),
        ("needs_human_review", console_data.integration.needs_human_review),
        ("reject", console_data.integration.reject),
        ("conflict_report_path", console_data.integration.conflict_report_path or ""),
      ])}
    </section>
    <section id="validation" aria-labelledby="validation-title">
      <h2 id="validation-title">Validation</h2>
      {_section_table("Validation status", [
        ("result", console_data.validation.result),
        ("passed_gates", console_data.validation.passed_gates),
        ("failed_gates", console_data.validation.failed_gates),
        ("failing_gates", ", ".join(console_data.validation.failing_gates)),
        ("report_path", console_data.validation.report_path or ""),
      ])}
    </section>
    <section id="evidence" aria-labelledby="evidence-title">
      <h2 id="evidence-title">Evidence</h2>
      {_evidence_html(console_data.evidence_links)}
    </section>
    <section id="release-candidate" aria-labelledby="release-candidate-title">
      <h2 id="release-candidate-title">Release Candidate</h2>
      {_section_table("Release candidate status", [
        ("created", console_data.release_candidate.created),
        ("status", console_data.release_candidate.status),
        ("path", console_data.release_candidate.path or ""),
        ("demo_evidence_path", console_data.release_candidate.demo_evidence_path or ""),
      ])}
    </section>
    <section id="raw-json" aria-labelledby="raw-json-title">
      <h2 id="raw-json-title">Raw JSON Links</h2>
      <p>Use console-data.json for stable machine-readable status.</p>
    </section>
    <section id="warnings" aria-labelledby="warnings-title">
      <h2 id="warnings-title">Warnings</h2>
      <p class="warnings">{_esc('; '.join(console_data.warnings) if console_data.warnings else 'No console aggregation warnings.')}</p>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_text, encoding="utf-8")
    return path


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        href = values.get("href")
        if href:
            self.links.append(href)


def validate_console_links(run_dir: Path, html_path: Path) -> dict[str, Any]:
    resolved_run_dir = normalize_run_dir(run_dir)
    resolved_html = normalize_run_dir(html_path)
    parser = _LinkParser()
    parser.feed(resolved_html.read_text(encoding="utf-8"))
    checked: list[dict[str, Any]] = []
    missing: list[str] = []
    escaped: list[str] = []
    external: list[str] = []
    for href in parser.links:
        parsed = urlparse(href)
        if parsed.scheme or parsed.netloc:
            external.append(href)
            continue
        if href.startswith("#"):
            continue
        target = (resolved_html.parent / unquote(parsed.path)).resolve()
        if resolved_run_dir not in target.parents and target != resolved_run_dir:
            escaped.append(href)
            continue
        exists = target.exists()
        checked.append({"href": href, "exists": exists})
        if not exists:
            missing.append(href)
    result = {
        "checked": checked,
        "missing": missing,
        "escaped": escaped,
        "external": external,
        "passed": not missing and not escaped and not external,
    }
    (resolved_run_dir / "link-check.json").write_text(stable_json(result, pretty=True), encoding="utf-8")
    return result


def emit_console_json(console_data: PatchSwarmConsoleData, *, output_dir: Path | None = None) -> dict[str, Any]:
    out = normalize_run_dir(output_dir) if output_dir else normalize_run_dir(Path(console_data.run_dir))
    return {
        "run_id": console_data.run_id,
        "result": console_data.current_run.get("result", "unknown"),
        "next_action": console_data.next_action,
        "candidate_count": console_data.candidate_count,
        "workers": {
            "active_workers": console_data.workers.active_workers,
            "max_observed_parallel_workers": console_data.workers.max_observed_parallel_workers,
            "max_parallel_agents": console_data.workers.max_parallel_agents,
        },
        "bundles": asdict(console_data.bundles),
        "integration": {
            "result": console_data.integration.result,
            "groups": console_data.integration.groups,
            "conflicts": console_data.integration.conflicts,
        },
        "validation": {
            "result": console_data.validation.result,
            "failed_gates": console_data.validation.failed_gates,
        },
        "release_candidate": {
            "created": console_data.release_candidate.created,
            "status": console_data.release_candidate.status,
        },
        "artifacts": {
            "run_dir": console_data.run_dir,
            "start_here": rel(out / "start-here.html"),
            "console_data": rel(out / "console-data.json"),
        },
    }


def render_console(
    run_dir: Path,
    *,
    output_dir: Path | None = None,
    write_html: bool = False,
    strict_links: bool = False,
) -> tuple[PatchSwarmConsoleData, dict[str, Any]]:
    resolved_run_dir = normalize_run_dir(run_dir)
    resolved_output_dir = normalize_run_dir(output_dir or run_dir)
    data = collect_patch_swarm_console_data(resolved_run_dir)
    write_console_data(data, resolved_output_dir)
    html_path: Path | None = None
    link_check: dict[str, Any] | None = None
    if write_html:
        html_path = render_patch_swarm_html(data, resolved_output_dir)
        link_check = validate_console_links(resolved_output_dir, html_path)
        if strict_links and not link_check.get("passed"):
            raise RuntimeError("console link validation failed")
    metadata = {
        "console_data": rel(resolved_output_dir / "console-data.json"),
        "start_here": rel(html_path) if html_path else "",
        "link_check": link_check or {},
    }
    return data, metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render Patch Swarm console data from run artifacts.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--write-html", action="store_true")
    parser.add_argument("--strict-links", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        data, _metadata = render_console(
            Path(args.run_dir),
            output_dir=Path(args.output_dir) if args.output_dir else None,
            write_html=args.write_html,
            strict_links=args.strict_links,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if args.json:
        print(stable_json(emit_console_json(data, output_dir=Path(args.output_dir) if args.output_dir else Path(args.run_dir)), pretty=False), end="")
    else:
        print(f"{data.current_run.get('result', 'unknown')} {data.candidate_count} candidates {data.run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
