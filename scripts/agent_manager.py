#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENT_WORK = ROOT / "scripts" / "agent_work.py"
REPORT_ROOT = ROOT / "workspace" / "runs" / "agent-manager"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
POOL_LATEST = STATE_DIR / "agent-pool-kick-latest.json"
COORDINATOR_LOG = STATE_DIR / "agent-coordinator.log"
POOL_LOG = STATE_DIR / "agent-pool-kick.log"

ACTIVE_STATUSES = {"planned", "launching", "running"}
TERMINAL_STATUSES = {"archived", "succeeded", "failed", "blocked", "dry_run", "stale", "exited_unknown"}
EMPTY_LOG_STUCK_SECONDS = 10 * 60
IDLE_CPU_THRESHOLD = 0.2
LONG_RUNNING_VALIDATOR_SECONDS = 30 * 60


def replacement_issue_link(issue_id: int) -> str:
    base = os.environ.get("CENTO_AGENT_WORK_API", "http://127.0.0.1:47910").rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return f"{base}/issues/{issue_id}"


class AgentManagerError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(args: list[str], *, timeout: int = 20, check: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise AgentManagerError(f"{shlex.join(args)} failed with exit {proc.returncode}: {detail}")
    return proc


def agent_work_json(*args: str, timeout: int = 30) -> dict[str, Any]:
    proc = run_command(["python3", str(AGENT_WORK), *args], timeout=timeout, check=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AgentManagerError(f"agent_work.py {' '.join(args)} returned invalid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def elapsed_seconds(started_at: Any, ended_at: Any | None = None) -> int:
    start = parse_datetime(started_at)
    if not start:
        return 0
    end = parse_datetime(ended_at) or datetime.now(timezone.utc)
    return max(0, int((end - start).total_seconds()))


def parse_etime(value: str) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    days = 0
    if "-" in text:
        day_text, text = text.split("-", 1)
        try:
            days = int(day_text)
        except ValueError:
            days = 0
    parts = text.split(":")
    try:
        nums = [int(part) for part in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        hours, minutes, seconds = nums
    elif len(nums) == 2:
        hours, minutes, seconds = 0, nums[0], nums[1]
    else:
        return 0
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d{hours:02d}h"
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}:{seconds:02d}"


def load_runs() -> list[dict[str, Any]]:
    payload = agent_work_json("runs", "--json", "--reconcile")
    runs = payload.get("runs") or []
    visible_statuses = ACTIVE_STATUSES | {"archived", "stale", "untracked_interactive"}
    return [item for item in runs if isinstance(item, dict) and str(item.get("status") or "") in visible_statuses]


def load_issues() -> dict[int, dict[str, Any]]:
    payload = agent_work_json("list", "--all", "--json")
    issues = payload.get("issues") or []
    indexed: dict[int, dict[str, Any]] = {}
    for item in issues:
        if not isinstance(item, dict):
            continue
        try:
            indexed[int(item["id"])] = item
        except (KeyError, TypeError, ValueError):
            continue
    return indexed


def read_process_table() -> dict[int, dict[str, Any]]:
    proc = run_command(["ps", "-eo", "pid=,ppid=,pgid=,stat=,etime=,pcpu=,pmem=,args="], timeout=5)
    processes: dict[int, dict[str, Any]] = {}
    if proc.returncode != 0:
        return processes
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 7)
        if len(parts) < 8:
            continue
        pid, ppid, pgid, stat, etime, pcpu, pmem, args = parts
        try:
            pid_i = int(pid)
            ppid_i = int(ppid)
            pgid_i = int(pgid)
            cpu_f = float(pcpu)
            mem_f = float(pmem)
        except ValueError:
            continue
        processes[pid_i] = {
            "pid": pid_i,
            "ppid": ppid_i,
            "pgid": pgid_i,
            "stat": stat,
            "etime": etime,
            "elapsed_seconds": parse_etime(etime),
            "pcpu": cpu_f,
            "pmem": mem_f,
            "args": args,
        }
    return processes


def descendants(processes: dict[int, dict[str, Any]], root_pid: int) -> list[dict[str, Any]]:
    children: dict[int, list[int]] = defaultdict(list)
    for proc in processes.values():
        children[int(proc["ppid"])].append(int(proc["pid"]))
    result: list[dict[str, Any]] = []
    stack = list(children.get(root_pid, []))
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        proc = processes.get(pid)
        if not proc:
            continue
        result.append(proc)
        stack.extend(children.get(pid, []))
    return result


def tmux_sessions() -> list[dict[str, str]]:
    proc = run_command(
        ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_created}\t#{session_attached}"],
        timeout=5,
    )
    if proc.returncode != 0:
        return []
    sessions = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        sessions.append({"name": parts[0], "created": parts[1], "attached": parts[2]})
    return sessions


def log_stats(path_value: Any) -> dict[str, Any]:
    path_text = str(path_value or "").strip()
    if not path_text:
        return {"path": "", "exists": False, "size": 0, "mtime": "", "age_seconds": 0}
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"path": path_text, "exists": False, "size": 0, "mtime": "", "age_seconds": 0}
    mtime = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {
        "path": path_text,
        "exists": True,
        "size": stat.st_size,
        "mtime": mtime.isoformat(),
        "age_seconds": max(0, int((datetime.now(timezone.utc) - mtime).total_seconds())),
    }


def issue_id(run: dict[str, Any]) -> int | None:
    try:
        value = run.get("issue_id")
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def live_run(run: dict[str, Any]) -> bool:
    status = str(run.get("status") or "")
    return status in ACTIVE_STATUSES and bool(run.get("pid_alive") or run.get("tmux_alive"))


def run_process_summary(run: dict[str, Any], processes: dict[int, dict[str, Any]]) -> dict[str, Any]:
    pids = []
    for key in ("pid", "child_pid"):
        try:
            pid = int(run.get(key) or 0)
        except (TypeError, ValueError):
            pid = 0
        if pid > 0:
            pids.append(pid)
    roots = [processes[pid] for pid in pids if pid in processes]
    desc: list[dict[str, Any]] = []
    for pid in pids:
        desc.extend(descendants(processes, pid))
    all_procs = roots + desc
    commands = [str(proc.get("args") or "") for proc in all_procs]
    return {
        "root_pids": pids,
        "process_count": len(all_procs),
        "cpu": round(sum(float(proc.get("pcpu") or 0) for proc in all_procs), 3),
        "mem": round(sum(float(proc.get("pmem") or 0) for proc in all_procs), 3),
        "oldest_elapsed_seconds": max([int(proc.get("elapsed_seconds") or 0) for proc in all_procs] or [0]),
        "commands": commands[:12],
        "has_cat_child": any(Path(cmd.split()[0]).name == "cat" for cmd in commands if cmd.split()),
        "has_heredoc_command": any("<<" in cmd and "python" in cmd for cmd in commands),
        "has_playwright_command": any("playwright" in cmd.lower() for cmd in commands),
    }


def classify_run(
    run: dict[str, Any],
    issues: dict[int, dict[str, Any]],
    processes: dict[int, dict[str, Any]],
    live_by_issue: dict[int, int],
) -> dict[str, Any]:
    run_id = str(run.get("run_id") or "")
    status = str(run.get("status") or "")
    health = str(run.get("health") or "")
    role = str(run.get("role") or "")
    iid = issue_id(run)
    issue = issues.get(iid or -1)
    issue_status = str(issue.get("status") or "") if issue else ""
    elapsed = elapsed_seconds(run.get("started_at"), run.get("ended_at"))
    if not elapsed:
        elapsed = parse_etime(str(run.get("elapsed") or ""))
    log = log_stats(run.get("log_path"))
    proc_summary = run_process_summary(run, processes)
    live = live_run(run)

    labels: list[str] = []
    severity = "ok"
    confidence = 0.4
    evidence: list[str] = []

    if status == "untracked_interactive":
        labels.append("manual")
        severity = "info"
        confidence = max(confidence, 0.8)
        evidence.append("untracked interactive shell without issue/log ledger")

    if status == "stale" or health == "stale_no_process":
        labels.append("stale")
        severity = "warning"
        confidence = max(confidence, 0.95)
        evidence.append("ledger has no live pid or tmux session")

    if status in {"failed", "blocked", "exited_unknown"}:
        labels.append("errored")
        severity = "warning"
        confidence = max(confidence, 0.9)
        evidence.append(f"run status is {status}")

    if live:
        labels.append("live")
        evidence.append("pid_alive or tmux_alive is true")

    if iid is not None and live_by_issue.get(iid, 0) > 1:
        labels.append("duplicate")
        severity = "critical"
        confidence = max(confidence, 0.9)
        evidence.append(f"{live_by_issue[iid]} live runs exist for issue #{iid}")

    if issue_status.lower() == "done" and status in ACTIVE_STATUSES | {"stale"}:
        labels.append("issue_done_mismatch")
        severity = "warning" if severity != "critical" else severity
        confidence = max(confidence, 0.85)
        evidence.append(f"issue #{iid} is Done while run status is {status}")

    if live and log["exists"] and int(log["size"] or 0) == 0 and elapsed >= EMPTY_LOG_STUCK_SECONDS:
        labels.append("stuck")
        severity = "critical"
        confidence = max(confidence, 0.92)
        evidence.append(f"log is empty after {format_duration(elapsed)}")

    if live and role == "validator" and elapsed >= LONG_RUNNING_VALIDATOR_SECONDS:
        labels.append("long_running_validator")
        severity = "critical" if "stuck" in labels else "warning"
        confidence = max(confidence, 0.78)
        evidence.append(f"validator has run for {format_duration(elapsed)}")

    if live and proc_summary["cpu"] <= IDLE_CPU_THRESHOLD and elapsed >= EMPTY_LOG_STUCK_SECONDS:
        labels.append("idle")
        severity = "critical" if "stuck" in labels else "warning"
        confidence = max(confidence, 0.75)
        evidence.append(f"process tree CPU is {proc_summary['cpu']}%")

    if live and proc_summary["has_heredoc_command"] and proc_summary["has_cat_child"]:
        labels.append("blocked_child_command")
        severity = "critical"
        confidence = max(confidence, 0.9)
        evidence.append("process tree contains heredoc-style python command and cat child")

    if status == "stale" and issue_status.lower() == "done":
        labels.append("historical_done_stale")
        evidence.append("stale ledger belongs to a closed issue")

    if status == "archived":
        labels.append("archived")
        severity = "ok"
        confidence = max(confidence, 0.95)
        evidence.append("historical ledger was archived out of active views")

    if not labels:
        labels.append("ok")

    actions = recommended_actions(run, iid, labels, severity)
    return {
        "run_id": run_id,
        "issue_id": iid,
        "issue_status": issue_status,
        "issue_subject": str((issue or {}).get("subject") or run.get("issue_subject") or ""),
        "status": status,
        "health": health,
        "role": role,
        "agent": str(run.get("agent") or ""),
        "runtime": str(run.get("runtime") or ""),
        "tmux_session": str(run.get("tmux_session") or ""),
        "pid": run.get("pid"),
        "child_pid": run.get("child_pid"),
        "elapsed_seconds": elapsed,
        "elapsed": format_duration(elapsed),
        "log": log,
        "process": proc_summary,
        "labels": labels,
        "severity": severity,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "actions": actions,
    }


def recommended_actions(run: dict[str, Any], iid: int | None, labels: list[str], severity: str) -> list[dict[str, Any]]:
    run_id = str(run.get("run_id") or "")
    session = str(run.get("tmux_session") or "")
    actions: list[dict[str, Any]] = []
    if "stuck" in labels or "blocked_child_command" in labels:
        if session:
            actions.append(
                {
                    "id": "terminate_tmux",
                    "risk": "medium",
                    "dry_run": True,
                    "command": f"python3 scripts/agent_manager.py terminate-tmux {shlex.quote(session)} --reason {shlex.quote('stuck agent detected')} --dry-run",
                }
            )
        if iid is not None:
            actions.append(
                {
                    "id": "mark_blocked",
                    "risk": "low",
                    "dry_run": True,
                    "command": f"python3 scripts/agent_manager.py mark-blocked {iid} --reason {shlex.quote('stuck agent detected')} --evidence {shlex.quote(run_id)} --dry-run",
                }
            )
        if run_id:
            actions.append(
                {
                    "id": "mark_stale",
                    "risk": "low",
                    "dry_run": True,
                    "command": f"python3 scripts/agent_manager.py mark-stale {shlex.quote(run_id)} --reason {shlex.quote('stuck agent detected')} --dry-run",
                }
            )
    elif "historical_done_stale" in labels and run_id:
        actions.append(
            {
                "id": "archive_historical_stale",
                "risk": "low",
                "dry_run": True,
                "command": f"python3 scripts/agent_manager.py reconcile-ledger {shlex.quote(run_id)} --apply",
            }
        )
    elif "stale" in labels and run_id:
        actions.append(
            {
                "id": "reconcile_ledger",
                "risk": "low",
                "dry_run": True,
                "command": f"python3 scripts/agent_manager.py reconcile-ledger {shlex.quote(run_id)} --dry-run",
            }
        )
    elif "duplicate" in labels:
        actions.append(
            {
                "id": "review_duplicate",
                "risk": "medium",
                "dry_run": True,
                "command": f"python3 scripts/agent_manager.py classify --issue-id {iid}",
            }
        )
    elif severity == "ok":
        actions.append({"id": "none", "risk": "none", "dry_run": True, "command": ""})
    return actions


def build_scan() -> dict[str, Any]:
    runs = load_runs()
    issues = load_issues()
    processes = read_process_table()
    sessions = tmux_sessions()
    live_by_issue: dict[int, int] = Counter()
    for run in runs:
        iid = issue_id(run)
        if iid is not None and live_run(run):
            live_by_issue[iid] += 1

    classifications = [classify_run(run, issues, processes, live_by_issue) for run in runs]
    class_counts = Counter(label for item in classifications for label in item["labels"])
    severity_counts = Counter(str(item["severity"]) for item in classifications)
    role_counts = Counter(str(item.get("role") or "unknown") for item in classifications)
    runtime_counts = Counter(str(item.get("runtime") or "unknown") for item in classifications)
    live_items = [item for item in classifications if "live" in item["labels"] or "manual" in item["labels"]]
    risk_items = [item for item in classifications if item["severity"] in {"warning", "critical"}]
    historical_stale_items = [item for item in classifications if "archived" in item["labels"] or "historical_done_stale" in item["labels"]]
    actionable_stale_items = [item for item in classifications if "stale" in item["labels"] and "historical_done_stale" not in item["labels"]]
    pool_latest = read_json(POOL_LATEST)
    summary = {
        "total_runs": len(classifications),
        "live": len(live_items),
        "managed_live": sum(1 for item in live_items if "manual" not in item["labels"]),
        "manual": int(class_counts.get("manual", 0)),
        "stale": int(class_counts.get("stale", 0)),
        "actionable_stale": len(actionable_stale_items),
        "historical_stale": len(historical_stale_items),
        "archived": int(class_counts.get("archived", 0)),
        "stuck": int(class_counts.get("stuck", 0)),
        "idle": int(class_counts.get("idle", 0)),
        "errored": int(class_counts.get("errored", 0)),
        "duplicate": int(class_counts.get("duplicate", 0)),
        "critical": int(severity_counts.get("critical", 0)),
        "warning": int(severity_counts.get("warning", 0)),
        "ok": int(severity_counts.get("ok", 0)),
        "by_role": dict(sorted(role_counts.items())),
        "by_runtime": dict(sorted(runtime_counts.items())),
        "risk_count": len(risk_items),
        "pool_latest_at": str((pool_latest or {}).get("generated_at") or "") if isinstance(pool_latest, dict) else "",
        "pool_targets": (pool_latest or {}).get("targets") if isinstance(pool_latest, dict) else {},
        "tmux_sessions": len(sessions),
        "coordinator_log_exists": COORDINATOR_LOG.exists(),
        "pool_log_exists": POOL_LOG.exists(),
    }
    recommendations = build_recommendations(classifications)
    return {
        "generated_at": now_iso(),
        "root": str(ROOT),
        "summary": summary,
        "recommendations": recommendations,
        "runs": classifications,
        "tmux_sessions": sessions,
    }


def build_recommendations(items: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    ranked = sorted(
        [item for item in items if item["severity"] in {"critical", "warning"}],
        key=lambda item: (
            0 if item["severity"] == "critical" else 1,
            -float(item.get("confidence") or 0),
            -int(item.get("elapsed_seconds") or 0),
        ),
    )
    recommendations: list[dict[str, Any]] = []
    for item in ranked[:limit]:
        title = recommendation_title(item)
        recommendations.append(
            {
                "title": title,
                "severity": item["severity"],
                "confidence": item["confidence"],
                "run_id": item["run_id"],
                "issue_id": item["issue_id"],
                "labels": item["labels"],
                "evidence": item["evidence"],
                "actions": item["actions"],
            }
        )
    return recommendations


def recommendation_title(item: dict[str, Any]) -> str:
    issue = f"#{item['issue_id']}" if item.get("issue_id") is not None else "manual"
    if "stuck" in item["labels"]:
        return f"Investigate stuck {item.get('role') or 'agent'} on {issue}"
    if "blocked_child_command" in item["labels"]:
        return f"Child command appears blocked for {issue}"
    if "duplicate" in item["labels"]:
        return f"Resolve duplicate live agents for {issue}"
    if "stale" in item["labels"]:
        return f"Reconcile stale ledger for {issue}"
    if "errored" in item["labels"]:
        return f"Review errored agent run for {issue}"
    return f"Review agent risk for {issue}"


def markdown_report(scan: dict[str, Any]) -> str:
    summary = scan["summary"]
    lines = [
        "# Cento Agent Manager Report",
        "",
        f"Generated: `{scan['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Live: {summary['live']} ({summary['managed_live']} managed, {summary['manual']} manual)",
        f"- Risk: {summary['risk_count']} ({summary['critical']} critical, {summary['warning']} warning)",
        f"- Stale: {summary['stale']}",
        f"- Stuck: {summary['stuck']}",
        f"- Idle: {summary['idle']}",
        f"- Errored: {summary['errored']}",
        f"- Duplicate: {summary['duplicate']}",
        "",
        "## Recommendations",
        "",
    ]
    if not scan["recommendations"]:
        lines.append("- No actionable agent risks detected.")
    for rec in scan["recommendations"]:
        lines.append(f"- **{rec['severity'].upper()}** {rec['title']} (confidence {rec['confidence']})")
        if rec.get("run_id"):
            lines.append(f"  - Run: `{rec['run_id']}`")
        if rec.get("issue_id") is not None:
            lines.append(f"  - Issue: `#{rec['issue_id']}`")
            lines.append(f"  - Link: `{replacement_issue_link(int(rec['issue_id']))}`")
        for evidence in rec.get("evidence") or []:
            lines.append(f"  - Evidence: {evidence}")
        for action in rec.get("actions") or []:
            command = action.get("command")
            if command:
                lines.append(f"  - Action: `{command}`")
    lines.extend(["", "## Risk Items", ""])
    for item in scan["runs"]:
        if item["severity"] not in {"critical", "warning"}:
            continue
        lines.append(
            f"- `{item['run_id']}` issue={item.get('issue_id') or '-'} "
            f"status={item['status']} labels={','.join(item['labels'])} elapsed={item['elapsed']}"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(scan: dict[str, Any]) -> dict[str, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPORT_ROOT / f"report-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "agent-manager-report.json"
    md_path = run_dir / "agent-manager-report.md"
    json_path.write_text(json.dumps(scan, indent=2, default=str) + "\n")
    md_path.write_text(markdown_report(scan))
    return {"run_dir": str(run_dir), "json": str(json_path), "markdown": str(md_path)}


def command_scan(args: argparse.Namespace) -> int:
    scan = build_scan()
    if args.json:
        print(json.dumps(scan, indent=2, default=str))
    else:
        print_summary(scan)
    return 0


def print_summary(scan: dict[str, Any]) -> None:
    summary = scan["summary"]
    print(
        f"live={summary['live']} managed={summary['managed_live']} manual={summary['manual']} "
        f"stale={summary['stale']} stuck={summary['stuck']} critical={summary['critical']} warning={summary['warning']}"
    )
    for rec in scan["recommendations"][:10]:
        print(f"- [{rec['severity']}] {rec['title']} ({', '.join(rec['labels'])})")


def command_report(args: argparse.Namespace) -> int:
    scan = build_scan()
    paths = write_report(scan)
    payload = {"generated_at": scan["generated_at"], "paths": paths, "summary": scan["summary"], "recommendations": scan["recommendations"]}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"wrote {paths['markdown']}")
        print(f"wrote {paths['json']}")
        print_summary(scan)
    return 0


def write_janitor_report(payload: dict[str, Any]) -> dict[str, str]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = REPORT_ROOT / f"janitor-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "agent-manager-janitor.json"
    md_path = run_dir / "agent-manager-janitor.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    applied = sum(1 for item in payload["results"] if item.get("applied"))
    failed = sum(1 for item in payload["results"] if item.get("exit_code") not in (0, None))
    lines = [
        "# Cento Agent Manager Janitor",
        "",
        f"Generated: `{payload['generated_at']}`",
        f"Mode: `{'apply' if payload['apply'] else 'dry-run'}`",
        "",
        "## Summary",
        "",
        f"- Candidates: `{len(payload['candidates'])}`",
        f"- Applied: `{applied}`",
        f"- Failed: `{failed}`",
        "",
        "## Results",
        "",
    ]
    if not payload["results"]:
        lines.append("- No historical stale ledgers to archive.")
    for item in payload["results"]:
        mode = "APPLIED" if item.get("applied") else "DRY-RUN"
        lines.append(f"- **{mode}** `{item['run_id']}` issue=`#{item.get('issue_id') or '-'}` exit=`{item.get('exit_code')}`")
        if item.get("command"):
            command = " ".join(shlex.quote(str(part)) for part in item["command"])
            lines.append(f"  - Command: `{command}`")
    md_path.write_text("\n".join(lines).rstrip() + "\n")
    return {"run_dir": str(run_dir), "json": str(json_path), "markdown": str(md_path)}


def command_janitor(args: argparse.Namespace) -> int:
    scan = build_scan()
    candidates = [
        item
        for item in scan["runs"]
        if "historical_done_stale" in (item.get("labels") or [])
    ][: max(0, args.limit)]
    apply = bool(args.apply)
    results: list[dict[str, Any]] = []
    for item in candidates:
        run_id = str(item.get("run_id") or "")
        command = ["python3", str(Path(__file__).resolve()), "reconcile-ledger", run_id, "--apply" if apply else "--dry-run"]
        result: dict[str, Any] = {
            "run_id": run_id,
            "issue_id": item.get("issue_id"),
            "labels": item.get("labels") or [],
            "command": command,
            "applied": apply,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
        }
        if apply:
            proc = run_command(command, timeout=30)
            result.update({"exit_code": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()})
        results.append(result)
    payload = {
        "generated_at": now_iso(),
        "apply": apply,
        "limit": args.limit,
        "summary_before": scan["summary"],
        "candidates": candidates,
        "results": results,
    }
    paths = write_janitor_report(payload)
    payload["paths"] = paths
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"wrote {paths['markdown']}")
        print(f"wrote {paths['json']}")
        print(f"candidates={len(candidates)} mode={'apply' if apply else 'dry-run'}")
    return 0


def command_recommend(args: argparse.Namespace) -> int:
    scan = build_scan()
    recommendations = scan["recommendations"][: args.limit]
    if args.json:
        print(json.dumps({"recommendations": recommendations, "count": len(recommendations)}, indent=2, default=str))
        return 0
    if not recommendations:
        print("No actionable recommendations.")
        return 0
    for rec in recommendations:
        print(f"[{rec['severity']}] {rec['title']}")
        for evidence in rec.get("evidence") or []:
            print(f"  evidence: {evidence}")
        for action in rec.get("actions") or []:
            if action.get("command"):
                print(f"  action: {action['command']}")
    return 0


def command_classify(args: argparse.Namespace) -> int:
    scan = build_scan()
    items = scan["runs"]
    if args.run_id:
        items = [item for item in items if item["run_id"] == args.run_id]
    if args.issue_id is not None:
        items = [item for item in items if item.get("issue_id") == args.issue_id]
    payload = {"runs": items, "count": len(items)}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    elif not items:
        print("No matching runs.")
    else:
        for item in items:
            print(f"{item['run_id']} issue={item.get('issue_id') or '-'} severity={item['severity']} labels={','.join(item['labels'])}")
            for evidence in item.get("evidence") or []:
                print(f"  evidence: {evidence}")
    return 0


def command_pool_stats(args: argparse.Namespace) -> int:
    scan = build_scan()
    payload = {
        "generated_at": scan["generated_at"],
        "summary": scan["summary"],
        "pool_latest": read_json(POOL_LATEST),
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print_summary(scan)
    return 0


def dry_run_result(args: argparse.Namespace, command: list[str], evidence: dict[str, Any]) -> int:
    dry_run = bool(args.dry_run or not args.apply)
    payload = {"dry_run": dry_run, "command": command, "evidence": evidence}
    if dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    proc = run_command(command, timeout=20)
    payload["exit_code"] = proc.returncode
    payload["stdout"] = proc.stdout.strip()
    payload["stderr"] = proc.stderr.strip()
    print(json.dumps(payload, indent=2, default=str))
    return proc.returncode


def command_mark_stale(args: argparse.Namespace) -> int:
    scan = build_scan()
    match = next((item for item in scan["runs"] if item["run_id"] == args.run_id), None)
    command = [
        "python3",
        str(AGENT_WORK),
        "run-update",
        args.run_id,
        "--status",
        "stale",
        "--health",
        args.reason,
        "--ended-now",
        "--note",
        args.reason,
    ]
    return dry_run_result(args, command, {"classification": match})


def command_mark_blocked(args: argparse.Namespace) -> int:
    issue_link = replacement_issue_link(args.issue_id)
    command = [
        "python3",
        str(AGENT_WORK),
        "update",
        str(args.issue_id),
        "--status",
        "blocked",
        "--role",
        args.role,
        "--note",
        f"{args.reason}. Evidence: {args.evidence}. Issue: {issue_link}",
    ]
    return dry_run_result(args, command, {"issue_id": args.issue_id, "issue_link": issue_link, "evidence": args.evidence})


def command_terminate_tmux(args: argparse.Namespace) -> int:
    pane = run_command(["tmux", "capture-pane", "-pt", args.session, "-S", "-120"], timeout=5)
    evidence = {
        "session": args.session,
        "reason": args.reason,
        "tmux_capture": pane.stdout[-8000:] if pane.returncode == 0 else "",
    }
    command = ["tmux", "kill-session", "-t", args.session]
    return dry_run_result(args, command, evidence)


def command_reconcile_ledger(args: argparse.Namespace) -> int:
    scan = build_scan()
    match = next((item for item in scan["runs"] if item["run_id"] == args.run_id), None)
    if match and "historical_done_stale" in (match.get("labels") or []):
        command = [
            "python3",
            str(AGENT_WORK),
            "run-update",
            args.run_id,
            "--status",
            "archived",
            "--health",
            "historical_done_stale",
            "--ended-now",
            "--note",
            "Agent Manager archived historical stale ledger for a Done issue; no live pid or tmux session exists.",
            "--json",
        ]
        return dry_run_result(args, command, {"run_id": args.run_id, "classification": match, "mode": "archive_historical_done_stale"})

    command = ["python3", str(AGENT_WORK), "run-status", args.run_id, "--reconcile", "--json"]
    return dry_run_result(args, command, {"run_id": args.run_id, "classification": match, "mode": "reconcile_only"})


def command_open_evidence(args: argparse.Namespace) -> int:
    scan = build_scan()
    items = scan["runs"]
    if args.run_id:
        items = [item for item in items if item["run_id"] == args.run_id]
    if args.issue_id is not None:
        items = [item for item in items if item.get("issue_id") == args.issue_id]
    paths = []
    for item in items:
        log_path = item.get("log", {}).get("path")
        if log_path:
            paths.append(log_path)
    print(json.dumps({"paths": paths, "count": len(paths)}, indent=2))
    return 0


def command_create_ticket(args: argparse.Namespace) -> int:
    command = [
        "python3",
        str(AGENT_WORK),
        "create",
        "--json",
        "--title",
        f"{args.severity}: {args.title}",
        "--description",
        args.description,
        "--node",
        "linux",
        "--agent",
        "agent-manager",
        "--role",
        "coordinator",
        "--package",
        "agent-manager-follow-up",
    ]
    return dry_run_result(args, command, {"severity": args.severity})


def add_apply_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage and diagnose Cento agent processes.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="Scan agent runs, processes, tmux sessions, and issue state.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_scan)

    p = sub.add_parser("report", help="Write JSON and Markdown agent manager reports.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_report)

    p = sub.add_parser("janitor", help="Archive safe historical stale ledgers and write a hygiene report.")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--json", action="store_true")
    add_apply_flags(p)
    p.set_defaults(func=command_janitor)

    p = sub.add_parser("recommend", help="Print actionable recommendations.")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_recommend)

    p = sub.add_parser("classify", help="Classify one run or issue.")
    p.add_argument("--run-id")
    p.add_argument("--issue-id", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_classify)

    p = sub.add_parser("pool-stats", help="Print pool and agent run statistics.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_pool_stats)

    p = sub.add_parser("mark-stale", help="Mark a run ledger stale.")
    p.add_argument("run_id")
    p.add_argument("--reason", required=True)
    add_apply_flags(p)
    p.set_defaults(func=command_mark_stale)

    p = sub.add_parser("mark-blocked", help="Mark an issue blocked with evidence.")
    p.add_argument("issue_id", type=int)
    p.add_argument("--reason", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--role", choices=("builder", "validator", "coordinator"), default="validator")
    add_apply_flags(p)
    p.set_defaults(func=command_mark_blocked)

    p = sub.add_parser("terminate-tmux", help="Terminate a tmux session after evidence capture.")
    p.add_argument("session")
    p.add_argument("--reason", required=True)
    add_apply_flags(p)
    p.set_defaults(func=command_terminate_tmux)

    p = sub.add_parser("reconcile-ledger", help="Reconcile one run ledger.")
    p.add_argument("run_id")
    add_apply_flags(p)
    p.set_defaults(func=command_reconcile_ledger)

    p = sub.add_parser("open-evidence", help="List evidence paths for a run or issue.")
    p.add_argument("--run-id")
    p.add_argument("--issue-id", type=int)
    p.set_defaults(func=command_open_evidence)

    p = sub.add_parser("create-investigation-ticket", help="Create a follow-up investigation ticket.")
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--severity", default="SEV2")
    add_apply_flags(p)
    p.set_defaults(func=command_create_ticket)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AgentManagerError as exc:
        print(f"agent-manager: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"agent-manager: command timed out: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
