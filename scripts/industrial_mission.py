#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import shlex
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from jobs_server import load_jobs
from network_web_server import build_cluster_panel_model, cluster_snapshot


ROOT_DIR = Path(__file__).resolve().parent.parent
ACTION_REGISTRY = ROOT_DIR / "data" / "industrial-actions.json"
MISSION_FIXTURE_ENV = "CENTO_INDUSTRIAL_MISSION_FIXTURE"
SAFE_COMMANDS = {"./scripts/cento.sh", "cento", "python", "python3", sys.executable}
UNSAFE_COMMANDS = {"sh", "bash", "zsh", "fish", "ksh", "csh", "tcsh", "dash"}
SAFE_GIT_SUBCOMMANDS = {"status", "diff", "log", "show", "branch", "rev-parse"}
ACTIVE_JOB_STATUSES = {"running", "planned", "queued", "dry-run", "invalid", "unknown"}


def normalize_platform_name(value: str) -> str:
    value = value.lower()
    if value == "darwin":
        return "macos"
    return value


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def command_to_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(piece) for piece in command)
    return str(command or "")


def normalize_command(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return [piece for piece in shlex.split(value) if piece]
        except ValueError:
            return []
    if isinstance(value, list):
        return [str(piece) for piece in value if str(piece).strip()]
    return []


def command_is_safe(command: Any) -> tuple[bool, str]:
    if not isinstance(command, list):
        return False, "invalid command"
    if not command:
        return False, "no command configured"
    first = str(command[0]).strip()
    if not first:
        return False, "no command configured"
    if first in UNSAFE_COMMANDS:
        return False, f"unsafe shell wrapper blocked: {first}"
    if first == "git":
        subcommand = str(command[1]).strip() if len(command) > 1 else ""
        if subcommand in SAFE_GIT_SUBCOMMANDS:
            return True, ""
        return False, f"unsafe git command blocked: {subcommand or 'missing subcommand'}"
    if first in SAFE_COMMANDS:
        return True, ""
    if first.startswith("./scripts/"):
        return True, ""
    return False, f"unsafe command blocked: {first}"


def run_json(command: list[str], timeout: int = 8) -> tuple[dict[str, Any], str | None]:
    try:
        result = subprocess.run(command, cwd=ROOT_DIR, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return {}, str(exc)
    output = (result.stdout or "").strip()
    if result.returncode != 0:
        error = (result.stderr or output or f"exit {result.returncode}").strip()
        return {}, error
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        return {}, f"invalid JSON from {command_to_text(command)}: {exc}"
    return payload if isinstance(payload, dict) else {}, None


def run_text(command: list[str], timeout: int = 5) -> tuple[str, str | None]:
    try:
        result = subprocess.run(command, cwd=ROOT_DIR, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        return "", str(exc)
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        return output, output or f"exit {result.returncode}"
    return output, None


def source_bucket(payload: dict[str, Any], key: str) -> tuple[dict[str, Any], str | None]:
    value = payload.get(key) or {}
    if not isinstance(value, dict):
        return {}, f"{key} source fixture must be an object"
    data = value.get("payload")
    if data is None:
        data = value.get("data", {})
    if not isinstance(data, dict):
        data = {}
    error = value.get("error")
    return data, str(error) if error else None


def gather_sources() -> dict[str, Any]:
    agent_payload, agent_error = run_json(["./scripts/cento.sh", "agent-work", "list", "--json"], timeout=10)
    runs_payload, runs_error = run_json(["./scripts/cento.sh", "agent-work", "runs", "--json", "--active"], timeout=10)
    try:
        cluster_payload = cluster_snapshot()
        cluster_error = None
    except Exception as exc:
        cluster_payload = {}
        cluster_error = str(exc)
    git_status, git_error = run_text(["git", "status", "--short"], timeout=5)
    try:
        jobs_payload = load_jobs()
        jobs_error = None
    except Exception as exc:
        jobs_payload = {}
        jobs_error = str(exc)
    try:
        actions_payload = read_json_file(ACTION_REGISTRY)
        actions_error = None
    except Exception as exc:
        actions_payload = []
        actions_error = str(exc)
    return {
        "agent_work": {"payload": agent_payload, "error": agent_error},
        "runs": {"payload": runs_payload, "error": runs_error},
        "cluster": {"payload": cluster_payload, "error": cluster_error},
        "git": {"status_short": git_status, "error": git_error},
        "jobs": {"payload": jobs_payload, "error": jobs_error},
        "actions": {"payload": actions_payload, "error": actions_error},
    }


def issue_status(issue: dict[str, Any]) -> str:
    return str(issue.get("status") or "").strip().lower()


def issue_id(issue: dict[str, Any]) -> str:
    value = issue.get("id")
    return str(value) if value is not None else "unknown"


def issue_label(issue: dict[str, Any]) -> str:
    summary = str(issue.get("tui_summary") or "").strip()
    if summary:
        return summary
    subject = str(issue.get("subject") or "").strip()
    if subject:
        return subject
    return f"Issue #{issue_id(issue)}"


def validation_report_status(issue: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    raw = str(issue.get("validation_report") or "").strip()
    if not raw:
        return False, "missing validation_report", {}
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        return False, "invalid validation_report JSON", {}
    if not isinstance(report, dict):
        return False, "validation_report is not an object", {}
    result = str(report.get("result_after_gate") or report.get("result") or "").strip().lower()
    if result != "pass":
        return False, f"validation result is {result or 'unknown'}", report
    failures = report.get("review_gate_failures") or []
    if failures:
        return False, "review gate failures present", report
    evidence = report.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list) or not any(str(item or "").strip() for item in evidence):
        return False, "validation evidence missing", report
    return True, "validation pass with evidence", report


def issue_context(issue: dict[str, Any], reason: str = "") -> list[str]:
    lines = [
        f"Issue #{issue_id(issue)}",
        f"Status: {issue.get('status') or 'unknown'}",
        f"Package: {issue.get('package') or 'default'}",
        f"Node: {issue.get('node') or 'unassigned'}",
        f"Agent: {issue.get('agent') or 'unassigned'}",
        f"Subject: {issue_label(issue)}",
    ]
    if reason:
        lines.append(f"Signal: {reason}")
    dispatch = str(issue.get("dispatch") or "").strip()
    if dispatch:
        lines.append(f"Dispatch: {dispatch}")
    passed, validation_reason, report = validation_report_status(issue)
    lines.append(f"Validation: {'pass' if passed else validation_reason}")
    evidence = report.get("evidence") if isinstance(report, dict) else []
    if isinstance(evidence, str):
        evidence = [evidence]
    for item in list(evidence or [])[:3]:
        lines.append(f"Evidence: {item}")
    return lines


def show_issue_command(issue: dict[str, Any]) -> list[str]:
    return ["./scripts/cento.sh", "agent-work", "show", issue_id(issue), "--json"]


def review_drain_dry_run_command(issue: dict[str, Any]) -> list[str]:
    package = str(issue.get("package") or "").strip()
    if not package:
        return show_issue_command(issue)
    return ["./scripts/cento.sh", "agent-work", "review-drain", "--package", package, "--dry-run"]


def dispatch_dry_run_command(issue: dict[str, Any]) -> list[str]:
    command = ["./scripts/cento.sh", "agent-work", "dispatch", issue_id(issue), "--dry-run"]
    node = str(issue.get("node") or "").strip()
    agent = str(issue.get("agent") or "").strip()
    if node:
        command.extend(["--node", node])
    if agent:
        command.extend(["--agent", agent])
    return command


def blocker_reason(issue: dict[str, Any]) -> str:
    _passed, reason, _report = validation_report_status(issue)
    if reason != "missing validation_report":
        return reason
    haystack = " ".join(
        str(issue.get(key) or "")
        for key in ("subject", "description", "package", "dispatch", "validation_report")
    ).lower()
    if any(term in haystack for term in ("evidence", "artifact", "validation", "manifest", "story.json")):
        return "artifact or validation gap"
    if any(term in haystack for term in ("cento", "taskstream", "dispatch", "agent-work")):
        return "internal Cento gap"
    return "blocked Taskstream item"


def queue_item(
    *,
    item_id: str,
    source: str,
    title: str,
    detail: str,
    group: str,
    command: list[str],
    dry_run_command: list[str] | None = None,
    context: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "source": source,
        "title": title,
        "detail": detail,
        "group": group,
        "key": "",
        "command": command,
        "dry_run_command": dry_run_command if dry_run_command is not None else command,
        "context": context or [],
    }


def review_ready_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if issue_status(issue) != "review":
            continue
        passed, reason, _report = validation_report_status(issue)
        if not passed:
            continue
        command = review_drain_dry_run_command(issue)
        rows.append(
            queue_item(
                item_id=f"issue-{issue_id(issue)}",
                source="taskstream",
                title=f"Review ready #{issue_id(issue)}",
                detail=f"{issue_label(issue)} | {reason}",
                group="REVIEW",
                command=command,
                dry_run_command=command,
                context=[*issue_context(issue, reason), f"Safe command: {command_to_text(command)}"],
            )
        )
    return rows


def review_gap_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if issue_status(issue) != "review":
            continue
        passed, reason, _report = validation_report_status(issue)
        if passed:
            continue
        command = show_issue_command(issue)
        rows.append(
            queue_item(
                item_id=f"issue-{issue_id(issue)}",
                source="taskstream",
                title=f"Review gate #{issue_id(issue)}",
                detail=f"{issue_label(issue)} | {reason}",
                group="REVIEW",
                command=command,
                dry_run_command=command,
                context=issue_context(issue, reason),
            )
        )
    return rows


def blocked_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if issue_status(issue) != "blocked":
            continue
        reason = blocker_reason(issue)
        command = show_issue_command(issue)
        rows.append(
            queue_item(
                item_id=f"issue-{issue_id(issue)}",
                source="taskstream",
                title=f"Blocked #{issue_id(issue)}",
                detail=f"{issue_label(issue)} | {reason}",
                group="BLOCKED",
                command=command,
                dry_run_command=command,
                context=issue_context(issue, reason),
            )
        )
    return rows


def queued_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for issue in issues:
        if issue_status(issue) != "queued":
            continue
        command = dispatch_dry_run_command(issue)
        safe, reason = command_is_safe(command)
        if not safe:
            continue
        rows.append(
            queue_item(
                item_id=f"issue-{issue_id(issue)}",
                source="taskstream",
                title=f"Dispatch dry-run #{issue_id(issue)}",
                detail=f"{issue_label(issue)} | dry-run dispatch to {issue.get('node') or 'default node'}",
                group="QUEUED",
                command=command,
                dry_run_command=command,
                context=[*issue_context(issue, "queued for dry-run dispatch"), f"Safety: {reason or 'dry-run only'}"],
            )
        )
    return rows


def manual_run_items(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    command = ["./scripts/cento.sh", "agent-work", "runs", "--json", "--active"]
    for run in runs:
        if str(run.get("status") or "") != "untracked_interactive":
            continue
        runtime = str(run.get("runtime") or "agent")
        pid = str(run.get("pid") or "")
        elapsed = str(run.get("elapsed") or "")
        run_id = str(run.get("run_id") or f"manual-{pid or runtime}")
        rows.append(
            queue_item(
                item_id=f"run-{run_id}",
                source="agent-runs",
                title=f"Manual {runtime} shell",
                detail=f"pid {pid or 'unknown'} | elapsed {elapsed or 'unknown'} | not attached to Taskstream",
                group="MANUAL",
                command=command,
                dry_run_command=command,
                context=[
                    f"Run: {run_id}",
                    f"Runtime: {runtime}",
                    f"Status: {run.get('status') or 'unknown'}",
                    f"Health: {run.get('health') or 'unknown'}",
                    f"Command: {run.get('command') or 'n/a'}",
                ],
            )
        )
    return rows


def command_from_text(value: str) -> list[str]:
    command = normalize_command(value)
    if not command:
        return []
    if command[0] == "cento":
        command = ["./scripts/cento.sh", *command[1:]]
    return command


def diagnostic_cluster_command(action: dict[str, Any]) -> list[str]:
    commands = [str(item) for item in (action.get("commands") or []) if str(item).strip()]
    for raw in commands:
        command = command_from_text(raw)
        if not command:
            continue
        lowered = [piece.lower() for piece in command]
        if "heal" in lowered:
            continue
        safe, _reason = command_is_safe(command)
        if safe:
            return command
    return ["./scripts/cento.sh", "cluster", "status"]


def cluster_items(cluster_payload: dict[str, Any], cluster_error: str | None) -> tuple[list[dict[str, Any]], int, list[str], str]:
    if cluster_error:
        command = ["./scripts/cento.sh", "cluster", "status"]
        return (
            [
                queue_item(
                    item_id="cluster-unavailable",
                    source="cluster",
                    title="Cluster status unavailable",
                    detail=cluster_error,
                    group="CLUSTER",
                    command=command,
                    dry_run_command=command,
                    context=[f"Cluster error: {cluster_error}", f"Safe command: {command_to_text(command)}"],
                )
            ],
            1,
            [cluster_error],
            "unavailable",
        )
    if not cluster_payload:
        return [], 0, [], "unknown"
    try:
        panel = build_cluster_panel_model(cluster_payload)
    except Exception as exc:
        command = ["./scripts/cento.sh", "cluster", "status"]
        return (
            [
                queue_item(
                    item_id="cluster-model-error",
                    source="cluster",
                    title="Cluster model error",
                    detail=str(exc),
                    group="CLUSTER",
                    command=command,
                    dry_run_command=command,
                    context=[f"Cluster model error: {exc}"],
                )
            ],
            1,
            [str(exc)],
            "degraded",
        )
    overall = str(panel.get("overall") or "unknown")
    counts = panel.get("counts") or {}
    issue_count = int(counts.get("offline", 0) or 0) + int(counts.get("degraded", 0) or 0)
    reasons = [str(reason) for reason in (panel.get("degraded_reasons") or []) if str(reason).strip()]
    if overall in {"healthy", "empty"} and issue_count == 0:
        return [], 0, reasons, overall
    rows = []
    for action in (panel.get("remediation_actions") or [])[:3]:
        if not isinstance(action, dict):
            continue
        node = str(action.get("node") or "cluster")
        label = str(action.get("action") or "inspect cluster")
        command = diagnostic_cluster_command(action)
        rows.append(
            queue_item(
                item_id=f"cluster-{node}",
                source="cluster",
                title=f"Cluster {node}: {label}",
                detail="; ".join(reasons[:2]) or f"overall={overall}",
                group="CLUSTER",
                command=command,
                dry_run_command=command,
                context=[
                    f"Overall: {overall}",
                    f"Node: {node}",
                    f"Action: {label}",
                    f"Owner: {action.get('owner') or 'local operator'}",
                    f"Reasons: {'; '.join(reasons[:4]) or 'n/a'}",
                    f"Safe command: {command_to_text(command)}",
                ],
            )
        )
    if not rows:
        command = ["./scripts/cento.sh", "cluster", "status"]
        rows.append(
            queue_item(
                item_id="cluster-status",
                source="cluster",
                title="Cluster status check",
                detail=f"overall={overall}",
                group="CLUSTER",
                command=command,
                dry_run_command=command,
                context=[f"Overall: {overall}", f"Reasons: {'; '.join(reasons[:4]) or 'n/a'}"],
            )
        )
    return rows, max(issue_count, len(rows)), reasons, overall


def git_items(status_short: str, git_error: str | None) -> tuple[list[dict[str, Any]], int, list[str]]:
    if git_error:
        command = ["git", "status", "--short"]
        return (
            [
                queue_item(
                    item_id="git-status-error",
                    source="git",
                    title="Git status unavailable",
                    detail=git_error,
                    group="GIT",
                    command=command,
                    dry_run_command=command,
                    context=[f"Git error: {git_error}"],
                )
            ],
            1,
            [git_error],
        )
    lines = [line for line in (status_short or "").splitlines() if line.strip()]
    if not lines:
        return [], 0, []
    command = ["git", "status", "--short"]
    detail = f"{len(lines)} dirty path(s): {lines[0].strip()}"
    return (
        [
            queue_item(
                item_id="git-dirty",
                source="git",
                title="Dirty worktree check",
                detail=detail,
                group="GIT",
                command=command,
                dry_run_command=command,
                context=["Dirty worktree:", *lines[:8], f"Safe command: {command_to_text(command)}"],
            )
        ],
        len(lines),
        lines,
    )


def load_action_rows(actions_payload: Any, cluster_payload: dict[str, Any], cluster_error: str | None) -> list[dict[str, Any]]:
    payload = actions_payload
    if isinstance(payload, dict):
        payload = payload.get("actions") or []
    if not isinstance(payload, list):
        return []
    platform_name = normalize_platform_name(platform.system())
    health = cluster_payload.get("health") if isinstance(cluster_payload, dict) else {}
    nodes = (health or {}).get("nodes") if isinstance(health, dict) else []
    rows = []
    for index, item in enumerate(payload, 1):
        if not isinstance(item, dict):
            continue
        command = normalize_command(item.get("command"))
        dry_run = normalize_command(item.get("dry_run_command")) or command
        allowlist = [str(value).lower() for value in (item.get("allowlist") or [])]
        if allowlist and platform_name not in allowlist:
            continue
        safe, _reason = command_is_safe(command)
        dry_safe, _dry_reason = command_is_safe(dry_run)
        if not safe or not dry_safe:
            continue
        policy = str(item.get("availability_check") or "always")
        if cluster_error and policy != "always":
            continue
        if policy == "non_empty_cluster" and not nodes:
            continue
        if policy == "degraded_nodes" and not any(str(node.get("state") or "") in {"degraded", "offline"} for node in nodes or []):
            continue
        rows.append(
            {
                "id": str(item.get("id") or f"action-{index}"),
                "label": str(item.get("label") or item.get("name") or f"Action {index}"),
                "command": command,
                "dry_run_command": dry_run,
            }
        )
    return rows


def active_job_count(jobs_payload: dict[str, Any]) -> int:
    jobs = [item for item in (jobs_payload.get("jobs") or []) if isinstance(item, dict)]
    count = 0
    for job in jobs:
        status = str(job.get("status") or (job.get("job_summary") or {}).get("status") or "").strip().lower()
        if status in ACTIVE_JOB_STATUSES:
            count += 1
    return count


def compute_context(
    *,
    git_lines: list[str],
    blocked_count: int,
    review_gap_count: int,
    manual_count: int,
    runs_count: int,
    active_jobs: int,
    cluster_overall: str,
    cluster_reasons: list[str],
    source_errors: list[str],
    packages: list[str],
) -> dict[str, str]:
    change = "clean worktree"
    if git_lines:
        change = f"{len(git_lines)} dirty path(s): {git_lines[0].strip()}"
    stall_parts = []
    if blocked_count:
        stall_parts.append(f"{blocked_count} blocked")
    if review_gap_count:
        stall_parts.append(f"{review_gap_count} review gate gap(s)")
    if manual_count:
        stall_parts.append(f"{manual_count} manual shell(s)")
    anti_stall = ", ".join(stall_parts) if stall_parts else "no stall signals from Taskstream"
    package_text = ", ".join(sorted(set(packages))[:4]) if packages else "none"
    blast = f"packages: {package_text}; runs={runs_count}; jobs={active_jobs}; cluster={cluster_overall}"
    blockers = "; ".join([*source_errors, *cluster_reasons][:3]) or "no blocker details"
    heat_score = min(9, blocked_count * 2 + review_gap_count + manual_count + active_jobs + (1 if cluster_overall not in {"healthy", "empty"} else 0))
    heat = ("#" * heat_score) + ("." * max(0, 9 - heat_score))
    return {
        "change_radar": change,
        "anti_stall": anti_stall,
        "blast_radius": blast,
        "blocker_watch": blockers,
        "session_heat": heat,
    }


def default_hub() -> list[dict[str, str]]:
    return [
        {"key": "j/k", "label": "SELECT", "detail": "move queue selection"},
        {"key": "arrows", "label": "SELECT", "detail": "move queue selection"},
        {"key": "1-9", "label": "JUMP", "detail": "select numbered item"},
        {"key": "a/enter", "label": "RUN", "detail": "run selected safe command"},
        {"key": "d", "label": "DRY RUN", "detail": "run selected dry-run command"},
        {"key": "o", "label": "CONTEXT", "detail": "show selected issue/run/cluster/git detail"},
        {"key": "u", "label": "NOTE", "detail": "draft status note from live state"},
        {"key": "r", "label": "REFRESH", "detail": "reload Cento state"},
        {"key": "?", "label": "HELP", "detail": "show key help"},
    ]


def normalize_model(payload: dict[str, Any]) -> dict[str, Any]:
    stats = dict(payload.get("stats") or {})
    for key in ("blocked", "review", "queued", "runs", "manual", "cluster", "actions"):
        try:
            stats[key] = int(stats.get(key) or 0)
        except (TypeError, ValueError):
            stats[key] = 0
    brief = dict(payload.get("brief") or {})
    brief.setdefault("objective", "Read Cento mission state.")
    brief.setdefault("next_action", "No actionable queue item selected.")
    brief.setdefault("project", "Cento")
    brief.setdefault("risk", "unknown")
    queue = []
    for index, raw in enumerate(payload.get("queue") or [], 1):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        item.setdefault("id", f"item-{index}")
        item.setdefault("source", "mission")
        item.setdefault("title", f"Mission item {index}")
        item.setdefault("detail", "")
        item.setdefault("group", "MISSION")
        item["key"] = str(index)
        item["command"] = normalize_command(item.get("command"))
        item["dry_run_command"] = normalize_command(item.get("dry_run_command")) or item["command"]
        context = item.get("context") or []
        if isinstance(context, str):
            context = [context]
        item["context"] = [str(line) for line in context if str(line).strip()]
        queue.append(item)
    context = payload.get("context") or {}
    if isinstance(context, list):
        context = {f"line_{index}": str(line) for index, line in enumerate(context, 1)}
    if not isinstance(context, dict):
        context = {}
    hub = payload.get("hub") or default_hub()
    if not isinstance(hub, list):
        hub = default_hub()
    return {
        "stats": stats,
        "brief": brief,
        "queue": queue[:9],
        "context": {str(key): str(value) for key, value in context.items()},
        "hub": [dict(item) for item in hub if isinstance(item, dict)],
        "updated_at": str(payload.get("updated_at") or datetime.now().astimezone().isoformat(timespec="seconds")),
        "sources": payload.get("sources") or {},
    }


def build_mission_model_from_sources(sources: dict[str, Any]) -> dict[str, Any]:
    agent_payload, agent_error = source_bucket(sources, "agent_work")
    runs_payload, runs_error = source_bucket(sources, "runs")
    cluster_payload, cluster_error = source_bucket(sources, "cluster")
    jobs_payload, jobs_error = source_bucket(sources, "jobs")
    actions_payload = (sources.get("actions") or {}).get("payload", []) if isinstance(sources.get("actions") or {}, dict) else []
    actions_error = (sources.get("actions") or {}).get("error") if isinstance(sources.get("actions") or {}, dict) else None
    git_source = sources.get("git") or {}
    if not isinstance(git_source, dict):
        git_source = {}
    git_status = str(git_source.get("status_short") or "")
    git_error = str(git_source.get("error")) if git_source.get("error") else None

    issues = [item for item in (agent_payload.get("issues") or []) if isinstance(item, dict)]
    runs = [item for item in (runs_payload.get("runs") or []) if isinstance(item, dict)]
    review_ready = review_ready_items(issues)
    review_gaps = review_gap_items(issues)
    blocked = blocked_items(issues)
    queued = queued_items(issues)
    manual = manual_run_items(runs)
    cluster_queue, cluster_count, cluster_reasons, cluster_overall = cluster_items(cluster_payload, cluster_error)
    git_queue, _dirty_count, git_lines = git_items(git_status, git_error)
    action_rows = load_action_rows(actions_payload, cluster_payload, cluster_error)
    queue = [*review_ready, *review_gaps, *blocked, *queued, *manual, *cluster_queue, *git_queue]

    source_errors = [
        f"agent-work unavailable: {agent_error}" if agent_error else "",
        f"agent-runs unavailable: {runs_error}" if runs_error else "",
        f"jobs unavailable: {jobs_error}" if jobs_error else "",
        f"actions unavailable: {actions_error}" if actions_error else "",
        f"git unavailable: {git_error}" if git_error else "",
    ]
    source_errors = [item for item in source_errors if item]
    packages = [str(issue.get("package") or "") for issue in issues if str(issue.get("package") or "").strip()]
    package_counts = Counter(packages)
    active_jobs = active_job_count(jobs_payload)
    stats = {
        "blocked": sum(1 for issue in issues if issue_status(issue) == "blocked"),
        "review": sum(1 for issue in issues if issue_status(issue) == "review"),
        "queued": sum(1 for issue in issues if issue_status(issue) == "queued"),
        "runs": len(runs),
        "manual": len(manual),
        "cluster": cluster_count,
        "actions": len(action_rows),
    }
    context = compute_context(
        git_lines=git_lines,
        blocked_count=stats["blocked"],
        review_gap_count=len(review_gaps),
        manual_count=stats["manual"],
        runs_count=stats["runs"],
        active_jobs=active_jobs,
        cluster_overall=cluster_overall,
        cluster_reasons=cluster_reasons,
        source_errors=source_errors,
        packages=packages,
    )
    if queue:
        next_action = f"{queue[0]['title']}: {queue[0]['detail']}"
    else:
        next_action = "No actionable mission items from Taskstream, active runs, cluster, git, or jobs."
    top_package = package_counts.most_common(1)[0][0] if package_counts else "Cento"
    if source_errors:
        risk = source_errors[0]
    elif stats["blocked"]:
        risk = f"{stats['blocked']} blocked Taskstream item(s)"
    elif stats["cluster"]:
        risk = f"cluster {cluster_overall}"
    elif git_lines:
        risk = f"{len(git_lines)} dirty worktree path(s)"
    else:
        risk = "low: board and cluster are quiet"
    objective = "Route the next Cento mission item from live state."
    if not queue:
        objective = "Keep Cento idle state visible without inventing work."
    model = {
        "stats": stats,
        "brief": {
            "objective": objective,
            "next_action": next_action,
            "project": top_package,
            "risk": risk,
        },
        "queue": queue,
        "context": context,
        "hub": default_hub(),
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sources": {
            "agent_work": "error" if agent_error else "ok",
            "runs": "error" if runs_error else "ok",
            "cluster": "error" if cluster_error else "ok",
            "git": "error" if git_error else "ok",
            "jobs": "error" if jobs_error else "ok",
            "actions": "error" if actions_error else "ok",
        },
    }
    return normalize_model(model)


def build_mission_model() -> dict[str, Any]:
    fixture = os.environ.get(MISSION_FIXTURE_ENV, "").strip()
    if fixture:
        try:
            payload = read_json_file(Path(fixture))
            if isinstance(payload, dict):
                return normalize_model(payload)
        except Exception as exc:
            return normalize_model(
                {
                    "stats": {"cluster": 1},
                    "brief": {
                        "objective": "Load deterministic mission fixture.",
                        "next_action": "Fix the mission fixture path or JSON.",
                        "project": "Cento",
                        "risk": f"mission fixture unavailable: {exc}",
                    },
                    "queue": [
                        {
                            "id": "mission-fixture-error",
                            "source": "fixture",
                            "title": "Mission fixture error",
                            "detail": str(exc),
                            "group": "FIXTURE",
                            "command": ["git", "status", "--short"],
                            "dry_run_command": ["git", "status", "--short"],
                            "context": [str(exc)],
                        }
                    ],
                    "context": {"blocker_watch": str(exc)},
                }
            )
    return build_mission_model_from_sources(gather_sources())
