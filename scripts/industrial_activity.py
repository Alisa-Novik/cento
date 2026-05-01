#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def strip_ansi(value: str) -> str:
    return ANSI_RE.sub("", value)


def parse_timestamp(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return time.time()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def age_text(timestamp: float, now: float | None = None) -> str:
    elapsed = max(1, int((now or time.time()) - timestamp))
    if elapsed < 60:
        return f"{elapsed}s"
    if elapsed < 3600:
        return f"{elapsed // 60}m"
    if elapsed < 86400:
        return f"{elapsed // 3600}h"
    return f"{elapsed // 86400}d"


def clean_message(source: str, line: str) -> str:
    plain = strip_ansi(line).replace("_", "-").strip()
    if plain.startswith("{") and plain.endswith("}"):
        try:
            payload = json.loads(plain)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            message = str(
                payload.get("message")
                or payload.get("summary")
                or payload.get("subject")
                or payload.get("detail")
                or payload.get("text")
                or ""
            ).strip()
            if message:
                return message
    if "GET /api/jobs " in plain:
        return "jobs dashboard completed"
    if "GET /api/network " in plain:
        return "cluster health check ok"
    if "GET /api/state " in plain:
        return "system state refreshed"
    if "Industrial workspace" in plain and "composed" in plain:
        return "workspace composed"
    if "Applied Kitty theme:" in plain:
        return "kitty theme applied"
    if plain.startswith("dashboard: running"):
        return "dashboard started"
    if "Completed successfully" in plain:
        return f"{source} completed"
    if "] " in plain:
        plain = plain.split("] ", 1)[1]
    return plain or source


def parse_log_record(source: str, line: str) -> dict[str, Any]:
    plain = strip_ansi(line).replace("_", "-").strip()
    if not plain:
        return {}
    if plain.startswith("{") and plain.endswith("}"):
        try:
            payload = json.loads(plain)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            message = clean_message(source, plain)
            kind = str(payload.get("kind") or payload.get("event") or "log").strip() or "log"
            severity = str(payload.get("severity") or "").strip().lower() or None
            timestamp = parse_timestamp(payload.get("timestamp") or payload.get("updated_at") or payload.get("created_at") or "")
            fingerprint = str(payload.get("fingerprint") or "").strip()
            return {
                "message": message or source,
                "kind": kind,
                "severity": severity,
                "timestamp": timestamp if timestamp else None,
                "fingerprint": fingerprint,
            }
    return {
        "message": clean_message(source, plain),
        "kind": "log",
        "severity": None,
        "timestamp": None,
        "fingerprint": "",
    }


def classify_severity(source: str, message: str, state: str = "") -> str:
    text = f"{source} {message} {state}".lower()
    if any(token in text for token in ("failed", "error", "critical", "offline", "disconnected", "traceback")):
        return "critical"
    if any(token in text for token in ("degraded", "missing", "stale", "warning", "warn", "unavailable")):
        return "warning"
    if any(token in text for token in ("running", "validating", "review", "queued")):
        return "info"
    return "ok"


def event(
    *,
    source: str,
    kind: str,
    message: str,
    timestamp: float,
    severity: str | None = None,
    fingerprint: str | None = None,
    path: str = "",
    metadata: dict[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    severity = severity or classify_severity(source, message)
    return {
        "source": source,
        "sources": [source],
        "kind": kind,
        "severity": severity,
        "timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        "epoch": timestamp,
        "stamp": datetime.fromtimestamp(timestamp).strftime("%H:%M"),
        "age": age_text(timestamp, now),
        "message": message,
        "path": path,
        "metadata": metadata or {},
        "fingerprint": fingerprint or f"{source}:{kind}:{message}",
    }


def merge_event_sources(target: dict[str, Any], source_event: dict[str, Any]) -> None:
    existing = [str(item) for item in target.get("sources") or [] if str(item).strip()]
    source = str(source_event.get("source") or "").strip()
    if source and source not in existing:
        existing.append(source)
    if not existing:
        fallback = str(target.get("source") or "").strip()
        if fallback:
            existing = [fallback]
    target["sources"] = existing or [str(target.get("source") or "")]
    target_sources = {item for item in target["sources"] if item}
    target["source"] = target["sources"][0] if target["sources"] else str(target.get("source") or "")
    existing_severity = str(target.get("severity") or "info").strip().lower() or "info"
    new_severity = str(source_event.get("severity") or "").strip().lower()
    severity_rank = {"critical": 4, "warning": 3, "info": 2, "ok": 1}
    if severity_rank.get(new_severity, 0) > severity_rank.get(existing_severity, 0):
        target["severity"] = new_severity
    target["metadata"] = dict(target.get("metadata") or {})
    if target_sources:
        target["metadata"]["sources"] = sorted(target_sources)


def last_meaningful_line(path: Path) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    for raw in reversed(lines):
        line = raw.strip()
        if line and "Log file:" not in line and "Log saved to:" not in line:
            return line
    return ""


def log_events(log_root: Path, now: float | None = None) -> list[dict[str, Any]]:
    if not log_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in log_root.glob("*/*.log"):
        try:
            stat = path.stat()
        except OSError:
            continue
        source = path.parent.name
        record = parse_log_record(source, last_meaningful_line(path))
        message = str(record.get("message") or source)
        kind = str(record.get("kind") or "log")
        severity = str(record.get("severity") or "").strip().lower() or None
        timestamp = float(record.get("timestamp") or stat.st_mtime)
        fingerprint = str(record.get("fingerprint") or "").strip() or f"log:{kind}:{message}:{int(timestamp)}"
        rows.append(
            event(
                source=source,
                kind=kind,
                message=message,
                timestamp=timestamp,
                severity=severity,
                fingerprint=fingerprint,
                path=str(path),
                now=now,
            )
        )
    return rows


def cluster_events(
    cluster_payload: dict[str, Any] | None,
    now: float | None = None,
    *,
    include_placeholder: bool = True,
) -> list[dict[str, Any]]:
    if not cluster_payload:
        if not include_placeholder:
            return []
        return [
            event(source="cluster", kind="state", message="cluster snapshot unavailable", timestamp=now or time.time(), severity="warning", now=now)
        ]
    timestamp = parse_timestamp(cluster_payload.get("updated_at"))
    health = cluster_payload.get("health") or {}
    rows = [
        event(
            source="cluster",
            kind="state",
            message=f"cluster {health.get('overall') or 'unknown'}",
            timestamp=timestamp,
            severity="ok" if health.get("overall") == "healthy" else "warning",
            metadata={"counts": health.get("counts") or {}},
            now=now,
        )
    ]
    for node in health.get("nodes") or []:
        state = str(node.get("state") or "unknown")
        if state == "online":
            continue
        reasons = ", ".join(str(item) for item in node.get("reasons") or []) or state
        rows.append(
            event(
                source="cluster",
                kind="node",
                message=f"{node.get('id')}: {reasons}",
                timestamp=timestamp,
                severity=classify_severity("cluster", reasons, state),
                metadata={"node": node.get("id"), "state": state, "remediation": node.get("remediation") or {}},
                now=now,
            )
        )
    return rows


def job_events(jobs_payload: dict[str, Any] | None, now: float | None = None) -> list[dict[str, Any]]:
    if not jobs_payload:
        return []
    rows: list[dict[str, Any]] = []
    for job in jobs_payload.get("jobs") or []:
        summary = job.get("job_summary") or job
        timestamp = parse_timestamp(summary.get("updated_at") or job.get("updated_at"))
        state = str(summary.get("state") or "ok")
        status = str(summary.get("status") or job.get("status") or "unknown")
        reasons = summary.get("degraded_reasons") or []
        feature = str(summary.get("feature") or job.get("feature") or job.get("id") or "job")
        message = f"{feature}: {status}"
        if reasons:
            message += f" ({'; '.join(map(str, reasons))})"
        rows.append(
            event(
                source="jobs",
                kind="job",
                message=message,
                timestamp=timestamp,
                severity=classify_severity("jobs", message, state),
                metadata={"job_id": job.get("id"), "status": status, "state": state},
                now=now,
            )
        )
    return rows


def agent_work_events(agent_payload: dict[str, Any] | None, now: float | None = None) -> list[dict[str, Any]]:
    if not agent_payload:
        return []
    rows: list[dict[str, Any]] = []
    for issue in agent_payload.get("issues") or []:
        timestamp = parse_timestamp(issue.get("updated_on"))
        status = str(issue.get("status") or "unknown")
        message = f"#{issue.get('id')} {status}: {issue.get('subject') or 'agent work'}"
        rows.append(
            event(
                source="agent-work",
                kind="issue",
                message=message,
                timestamp=timestamp,
                severity=classify_severity("agent-work", message, status),
                metadata={
                    "issue_id": issue.get("id"),
                    "status": status,
                    "agent": issue.get("agent") or "",
                    "role": issue.get("role") or "",
                    "package": issue.get("package") or "",
                },
                now=now,
            )
        )
    return rows


def dedupe_sort_events(events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    ordered = sorted(
        events,
        key=lambda row: (
            -float(row.get("epoch") or 0),
            str(row.get("source") or ""),
            str(row.get("kind") or ""),
            str(row.get("message") or ""),
            str(row.get("fingerprint") or ""),
        ),
    )
    for item in ordered:
        fingerprint = str(item.get("fingerprint") or "")
        if fingerprint in seen:
            merge_event_sources(seen[fingerprint], item)
            continue
        seen[fingerprint] = item
        rows.append(item)
        if len(rows) >= limit:
            break
    return rows


def filter_activity_events(
    events: list[dict[str, Any]],
    *,
    sources: list[str] | None = None,
    severities: list[str] | None = None,
    query: str = "",
) -> list[dict[str, Any]]:
    source_filter = {str(item).strip().lower() for item in sources or [] if str(item).strip()}
    severity_filter = {str(item).strip().lower() for item in severities or [] if str(item).strip()}
    query_text = str(query or "").strip().lower()
    if not source_filter and not severity_filter and not query_text:
        return events
    filtered: list[dict[str, Any]] = []
    for item in events:
        item_sources = [str(value).strip().lower() for value in item.get("sources") or [item.get("source") or ""] if str(value).strip()]
        if source_filter and not any(source in source_filter for source in item_sources):
            continue
        severity = str(item.get("severity") or "").strip().lower()
        if severity_filter and severity not in severity_filter:
            continue
        if query_text:
            haystack = " ".join(
                [
                    str(item.get("source") or ""),
                    " ".join(item_sources),
                    str(item.get("message") or ""),
                    str(item.get("kind") or ""),
                ]
            ).lower()
            if query_text not in haystack:
                continue
        filtered.append(item)
    return filtered


def load_agent_work_payload(root_dir: Path, timeout: int = 8) -> dict[str, Any]:
    command = ["python3", str(root_dir / "scripts" / "agent_work.py"), "list", "--json"]
    try:
        result = subprocess.run(command, cwd=root_dir, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception:
        return {}
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_activity_events(
    *,
    log_root: Path,
    cluster_payload: dict[str, Any] | None = None,
    jobs_payload: dict[str, Any] | None = None,
    agent_payload: dict[str, Any] | None = None,
    limit: int = 20,
    now: float | None = None,
    include_placeholders: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(log_events(log_root, now=now))
    rows.extend(cluster_events(cluster_payload, now=now, include_placeholder=include_placeholders))
    rows.extend(job_events(jobs_payload, now=now))
    rows.extend(agent_work_events(agent_payload, now=now))
    return dedupe_sort_events(rows, limit)
