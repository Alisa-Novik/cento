#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import json
import shutil
import sqlite3
import os
import platform
import re
import shlex
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agent_work_app
import story_manifest
import validation_manifest as validation_manifest_tools


ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "cento"
AGENT_RUN_ROOT = ROOT / "workspace" / "runs" / "agent-runs"
REVIEW_GATE_DEFAULT_SECTIONS = ["Delivered", "Validation", "Evidence", "Residual risk"]
SCREENSHOT_EVIDENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
DEFAULT_PROJECT_IDENTIFIER = "cento-agent-work"
DEFAULT_PROJECT_NAME = "Cento Agent Work"
RUNTIME_REGISTRY_PATH = ROOT / "data" / "agent-runtimes.json"
CUTOVER_RUN_ROOT = ROOT / "workspace" / "runs" / "agent-work" / "cutover"
CUTOVER_STATE_FILE = CUTOVER_RUN_ROOT / "cutover-state.json"
CUTOVER_BACKUP_ROOT = CUTOVER_RUN_ROOT / "backups"
CUTOVER_ARCHIVE_ROOT = CUTOVER_RUN_ROOT / "archive"
TASK_TRACKER = "Agent Task"
EPIC_TRACKER = "Agent Epic"
STATUS_MAP = {
    "queued": ("Queued", False, 0),
    "running": ("Running", False, 10),
    "validating": ("Validating", False, 60),
    "review": ("Review", False, 80),
    "blocked": ("Blocked", False, 0),
    "done": ("Done", True, 100),
}
ROLE_CHOICES = ("builder", "validator", "coordinator")
VALIDATION_RESULT_CHOICES = ("pass", "fail", "blocked")
NO_MODEL_VALIDATION_RISKS = {"low", "medium"}
ACTIVE_RUN_STATUSES = {"planned", "launching", "running"}
ENDED_RUN_STATUSES = {"archived", "dry_run", "succeeded", "failed", "blocked", "stale", "exited_unknown"}
DEFAULT_RUNTIME_REGISTRY = {
    "routing": "weighted",
    "runtimes": [
        {
            "id": "codex",
            "display_name": "Codex",
            "provider": "openai",
            "model": "gpt-5.3-codex-spark",
            "agent": "codex",
            "weight": 75,
            "preferred": True,
            "command_env": "CENTO_CODEX_BIN",
            "default_binary": "codex",
            "budget_note": "Preferred runtime. Majority share because Codex budget is about 100 USD/month.",
        },
        {
            "id": "claude-code",
            "display_name": "Claude Code",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "agent": "claude-code",
            "weight": 25,
            "plan": "personal-pro",
            "command_env": "CENTO_CLAUDE_BIN",
            "default_binary": "claude",
            "budget_note": "Personal Pro plan budget is about 20-30 USD/month, so route about 20-30% of tasks here.",
        },
    ],
}
MODULES = ["issue_tracking", "time_tracking", "wiki", "calendar", "gantt"]
CUSTOM_FIELDS = [
    ("Agent Node", "string"),
    ("Agent Owner", "string"),
    ("Agent Role", "string"),
    ("Agent State", "string"),
    ("Cento Work Package", "string"),
    ("Cluster Dispatch", "text"),
    ("Validation Report", "text"),
]
BACKEND_ARCHIVE = "archive"
BACKEND_REDLINE = BACKEND_ARCHIVE
BACKEND_TASKSTREAM = "taskstream"
BACKEND_REPLACEMENT = BACKEND_TASKSTREAM
BACKEND_DUAL = "dual"
LEGACY_TRACKER_NAME = "red" + "mine"
KNOWN_BACKENDS = {BACKEND_ARCHIVE, BACKEND_TASKSTREAM, BACKEND_DUAL}
BOOTSTRAP_CACHE: dict[str, Any] | None = None
DEFAULT_REPLACEMENT_API = "http://127.0.0.1:47910"
TRACKER_DB_PATH = ROOT / "apps" / "agent-tracker" / "db" / "tracker.db"
REPLACEMENT_LOCAL_ID_FLOOR = int(os.environ.get("CENTO_TASKSTREAM_LOCAL_ID_FLOOR", "1000000"))
REPLACEMENT_API_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class AgentWorkError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def agent_work_backend() -> str:
    tracker_backend = os.environ.get("CENTO_TRACKER_BACKEND", "").strip().lower()
    if tracker_backend == "sqlite":
        return BACKEND_TASKSTREAM
    backend = os.environ.get("CENTO_AGENT_WORK_BACKEND", BACKEND_TASKSTREAM).strip().lower()
    if not backend:
        return BACKEND_TASKSTREAM
    if backend == "replacement":
        backend = BACKEND_TASKSTREAM
    if backend == LEGACY_TRACKER_NAME:
        backend = BACKEND_ARCHIVE
    if backend not in KNOWN_BACKENDS:
        allowed = ", ".join(sorted(KNOWN_BACKENDS))
        raise AgentWorkError(f"Unknown agent-work backend: {backend}. Use one of: {allowed}")
    return backend

def replacement_db_path() -> Path:
    tracker_backend = os.environ.get("CENTO_TRACKER_BACKEND", "").strip().lower()
    default = str(TRACKER_DB_PATH) if tracker_backend == "sqlite" else str(agent_work_app.DB_PATH)
    return Path(os.environ.get("CENTO_AGENT_WORK_DB", default))


def cutover_root(run_dir: str | Path | None = None) -> Path:
    if run_dir:
        return resolve_root_path(run_dir)
    return CUTOVER_RUN_ROOT


def cutover_state_path(run_dir: str | Path | None = None) -> Path:
    return cutover_root(run_dir) / "cutover-state.json"


def cutover_default_state() -> dict[str, Any]:
    return {
        "frozen": False,
        "finalized": False,
        "frozen_at": "",
        "finalized_at": "",
        "write_target": BACKEND_REPLACEMENT,
        "last_backup": "",
        "last_verified_at": "",
        "last_archive_export": "",
        "blockers": [],
        "notes": [],
    }


def load_cutover_state(run_dir: str | Path | None = None) -> dict[str, Any]:
    state = cutover_default_state()
    state_path = cutover_state_path(run_dir)
    if run_dir and not state_path.exists() and CUTOVER_STATE_FILE.exists():
        state_path = CUTOVER_STATE_FILE
    if state_path.exists():
        payload = read_json_file(state_path)
        if payload:
            state.update(payload)
    return state


def save_cutover_state(state: dict[str, Any], run_dir: str | Path | None = None) -> Path:
    path = cutover_state_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def cutover_write_target(state: dict[str, Any] | None = None) -> str:
    current = state or load_cutover_state()
    if bool(current.get("finalized")):
        return BACKEND_REPLACEMENT
    backend = agent_work_backend()
    if backend in KNOWN_BACKENDS:
        return backend
    return BACKEND_REPLACEMENT


def cutover_counts() -> dict[str, Any]:
    issues = list_issues_replacement(include_closed=True)
    open_issues = [item for item in issues if not bool(item.get("is_closed"))]
    closed_issues = [item for item in issues if bool(item.get("is_closed"))]
    status_counts = Counter(str(item.get("status") or "") for item in issues)
    tracker_counts = Counter(str(item.get("tracker") or "") for item in issues)
    return {
        "total": len(issues),
        "open": len(open_issues),
        "closed": len(closed_issues),
        "status_counts": dict(sorted(status_counts.items())),
        "tracker_counts": dict(sorted(tracker_counts.items())),
        "sample_issue_ids": [int(item["id"]) for item in issues[:5]],
    }


def cutover_rollback_steps(state: dict[str, Any] | None = None) -> list[str]:
    current = state or load_cutover_state()
    if bool(current.get("finalized")):
        return [
            "Restore the replacement DB and evidence bundle from the latest backup.",
            "Rehydrate the backup bundle into a fresh replacement DB path.",
            "Do not resume legacy migration writes after finalization.",
        ]
    return [
        "Set `CENTO_AGENT_WORK_BACKEND=redmine` only before finalization if a rollback is required.",
        "Preserve the last replacement backup and archive export before retrying cutover.",
        "Re-run parity and restore drills after any rollback.",
    ]


def cutover_write_guard(operation: str) -> None:
    state = load_cutover_state()
    if bool(state.get("finalized")) and agent_work_backend() != BACKEND_REPLACEMENT:
        raise AgentWorkError(
            f"Legacy migration writes are disabled after cutover finalization; {operation} must use the Taskstream or archive commands."
        )


def require_replacement_backend(operation: str) -> None:
    if agent_work_backend() == BACKEND_REDLINE:
        raise AgentWorkError(f"{operation} requires Taskstream. Set CENTO_AGENT_WORK_BACKEND=taskstream.")


def issue_evidence_paths(conn: sqlite3.Connection) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for table, column in (("attachments", "path"), ("validation_evidences", "path")):
        try:
            rows = conn.execute(f"select {column} as path from {table}").fetchall()
        except sqlite3.OperationalError:
            continue
        for row in rows:
            raw = str(row["path"] or "").strip()
            if not raw or raw in seen:
                continue
            seen.add(raw)
            if raw.startswith(("http://", "https://", "taskstream://", "validation://")):
                continue
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = resolve_root_path(candidate)
            if candidate.exists():
                paths.append(candidate)
    return paths


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_backup_evidence(paths: list[Path], destination: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    for source in sorted({path.resolve() for path in paths}):
        if not source.exists() or not source.is_file():
            continue
        relative = source.relative_to(ROOT) if ROOT in source.parents or source == ROOT else Path(source.name)
        target = destination / "evidence" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(
            {
                "source": display_path(source),
                "backup_path": display_path(target),
                "sha256": sha256_file(target),
                "size": target.stat().st_size,
            }
        )
    return copied


def build_backup_bundle(db_path: Path, run_dir: Path | None = None) -> dict[str, Any]:
    if not db_path.exists():
        raise AgentWorkError(f"Replacement database not found: {db_path}")
    bundle_root = run_dir or (CUTOVER_BACKUP_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    bundle_root.mkdir(parents=True, exist_ok=True)
    db_target = bundle_root / db_path.name
    if db_path.resolve() != db_target.resolve():
        shutil.copy2(db_path, db_target)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        evidence_files = issue_evidence_paths(conn)
    copied_evidence = copy_backup_evidence(evidence_files, bundle_root)
    manifest = {
        "generated_at": now_iso(),
        "source_db": str(db_path),
        "backup_db": display_path(db_target),
        "backup_db_checksum": sha256_file(db_target),
        "backup_db_size": db_target.stat().st_size,
        "evidence_files": copied_evidence,
        "counts": cutover_counts_for_db(db_path),
    }
    (bundle_root / "backup-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {"bundle_dir": bundle_root, "manifest": manifest, "backup_db": db_target}


def restore_backup_bundle(bundle_dir: Path, target_db: Path, *, overwrite: bool = True) -> dict[str, Any]:
    manifest_path = bundle_dir / "backup-manifest.json"
    if not manifest_path.exists():
        raise AgentWorkError(f"Backup manifest not found: {manifest_path}")
    manifest = read_json_file(manifest_path)
    source_db = bundle_dir / Path(str(manifest.get("backup_db") or "")).name
    if not source_db.exists():
        raise AgentWorkError(f"Backup database not found in bundle: {source_db}")
    target_db.parent.mkdir(parents=True, exist_ok=True)
    if target_db.exists() and not overwrite:
        raise AgentWorkError(f"Target database already exists: {target_db}")
    if source_db.resolve() != target_db.resolve():
        shutil.copy2(source_db, target_db)
    restored = {
        "restored_at": now_iso(),
        "bundle_dir": display_path(bundle_dir),
        "target_db": display_path(target_db),
        "target_db_checksum": sha256_file(target_db),
        "counts": cutover_counts_for_db(target_db),
    }
    (target_db.parent / f"{target_db.stem}-restore.json").write_text(json.dumps(restored, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return {"manifest": manifest, "restored": restored, "source_db": source_db}


def cutover_counts_for_db(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if conn.execute("select name from sqlite_master where type = 'table' and name = 'issues'").fetchone() is None:
            return {"total": 0, "open": 0, "closed": 0, "status_counts": {}, "tracker_counts": {}, "sample_issue_ids": []}
        rows = [dict(row) for row in conn.execute("select id, status, tracker, coalesce(closed_on, '') as closed_on from issues order by id").fetchall()]
    issues = [{"id": row["id"], "status": row["status"], "tracker": row["tracker"], "is_closed": bool(str(row.get("closed_on") or "").strip()) or str(row["status"] or "").lower() == "done"} for row in rows]
    status_counts = Counter(str(item.get("status") or "") for item in issues)
    tracker_counts = Counter(str(item.get("tracker") or "") for item in issues)
    open_issues = [item for item in issues if not item["is_closed"]]
    closed_issues = [item for item in issues if item["is_closed"]]
    return {
        "total": len(issues),
        "open": len(open_issues),
        "closed": len(closed_issues),
        "status_counts": dict(sorted(status_counts.items())),
        "tracker_counts": dict(sorted(tracker_counts.items())),
        "sample_issue_ids": [int(item["id"]) for item in issues[:5]],
    }


def launch_temporary_app(db_path: Path) -> tuple[subprocess.Popen[str], int]:
    host = "127.0.0.1"
    port = agent_work_app.find_port(host, 47910)
    proc = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "scripts" / "agent_work_app.py"),
            "serve",
            "--host",
            host,
            "--port",
            str(port),
            "--db",
            str(db_path),
            "--exact-port",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        agent_work_app.wait_for_health(host, port, timeout=20.0)
    except Exception as exc:
        proc.terminate()
        raise AgentWorkError(f"Temporary app failed health check: {exc}") from exc
    return proc, port


def verify_restored_bundle(bundle_dir: Path, target_db: Path) -> dict[str, Any]:
    restore_result = restore_backup_bundle(bundle_dir, target_db)
    proc, port = launch_temporary_app(target_db)
    issues: list[Any] = []
    sample_details: list[dict[str, Any]] = []
    health: dict[str, Any] = {}
    try:
        issue_list_payload = replacement_api_request("/api/issues?status=all", f"http://127.0.0.1:{port}")
        if isinstance(issue_list_payload, dict):
            issues = issue_list_payload.get("issues") or issue_list_payload.get("items") or []
        else:
            issues = issue_list_payload if isinstance(issue_list_payload, list) else []
        sample_ids = [int(item.get("id")) for item in issues[:3] if isinstance(item, dict) and item.get("id") is not None]
        for issue_id in sample_ids:
            detail = replacement_api_request(f"/api/issues/{issue_id}", f"http://127.0.0.1:{port}")
            sample_details.append({"issue_id": issue_id, "has_issue": bool(detail.get("issue")), "journal_count": len(detail.get("journals") or []), "attachment_count": len(detail.get("attachments") or [])})
        health = agent_work_app.probe_health("127.0.0.1", port)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    result = {
        "bundle_dir": display_path(bundle_dir),
        "target_db": display_path(target_db),
        "restore": restore_result["restored"],
        "health": health,
        "sample_details": sample_details,
        "contracts": {
            "issue_list_ok": isinstance(issues, list),
            "sample_detail_ok": all(item["has_issue"] for item in sample_details) if sample_details else True,
        },
    }
    return result


def archive_issue_index(issues: list[dict[str, Any]], bundle_dir: Path) -> tuple[list[dict[str, Any]], Path]:
    index_rows: list[dict[str, Any]] = []
    archive_dir = bundle_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for issue in issues:
        issue_id = int(issue["id"])
        detail_path = archive_dir / f"issue-{issue_id}.json"
        html_path = archive_dir / f"issue-{issue_id}.html"
        detail = show_issue_replacement(issue_id)
        detail_path.write_text(json.dumps(detail, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        html_path.write_text(
            "\n".join(
                [
                    "<html><body>",
                    f"<h1>#{issue_id} {detail.get('subject') or ''}</h1>",
                    f"<p>Status: {detail.get('status') or ''}</p>",
                    f"<p>Tracker: {detail.get('tracker') or ''}</p>",
                    f"<pre>{json.dumps(detail, indent=2, sort_keys=True, default=str)}</pre>",
                    "</body></html>",
                ]
            ),
            encoding="utf-8",
        )
        index_rows.append(
            {
                "id": issue_id,
                "subject": detail.get("subject") or "",
                "status": detail.get("status") or "",
                "tracker": detail.get("tracker") or "",
                "updated_on": detail.get("updated_on") or "",
                "json": display_path(detail_path),
                "html": display_path(html_path),
            }
        )
    (archive_dir / "index.json").write_text(json.dumps(index_rows, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return index_rows, archive_dir


def search_archive_entries(index_rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    if not needle:
        return index_rows
    matches: list[dict[str, Any]] = []
    for row in index_rows:
        haystack = " ".join(str(row.get(key) or "") for key in ("id", "subject", "status", "tracker", "updated_on")).lower()
        if needle in haystack:
            matches.append(row)
            continue
        try:
            detail = json.loads(Path(resolve_root_path(row["json"])).read_text(encoding="utf-8"))
        except Exception:
            continue
        text_parts = [json.dumps(detail, sort_keys=True, default=str)]
        for journal in detail.get("journals") or []:
            text_parts.append(json.dumps(journal, sort_keys=True, default=str))
        if needle in " ".join(text_parts).lower():
            matches.append(row)
    return matches


def status_name(status_key: str | None) -> str:
    if status_key is None:
        return "Queued"
    normalized = status_key.strip().lower()
    if normalized in STATUS_MAP:
        return STATUS_MAP[normalized][0]
    return status_key.strip()



def normalize_source_label(value: Any) -> str:
    raw = str(value or "taskstream")
    if raw == "replacement":
        return "taskstream"
    legacy_name = "red" + "mine"
    if raw == legacy_name:
        return "archive"
    return raw

def _replacement_issue_core(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    done_ratio = int(row.get("done_ratio") or 0)
    is_closed = status.strip().lower() == "done"
    issue = {
        "id": int(row["id"]),
        "subject": str(row.get("subject") or ""),
        "description": str(row.get("description") or ""),
        "project": str(row.get("project") or "cento-agent-work"),
        "tracker": str(row.get("tracker") or TASK_TRACKER),
        "status": status,
        "is_closed": is_closed,
        "done_ratio": done_ratio,
        "updated_on": str(row.get("updated_on") or ""),
        "closed_on": str(row.get("closed_on") or (str(row.get("updated_on") or "") if is_closed else "")),
        "node": str(row.get("node") or ""),
        "agent": str(row.get("agent") or ""),
        "role": str(row.get("role") or ""),
        "package": str(row.get("package") or ""),
        "dispatch": str(row.get("dispatch") or ""),
        "validation_report": str(row.get("validation_report") or ""),
        "source": normalize_source_label(row.get("source")),
    }
    issue.update(agent_work_app.issue_test_artifact_metadata(issue))
    return issue


def _replacement_status(status: str | None) -> str | None:
    if status is None:
        return None
    candidate = str(status).strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if lowered in STATUS_MAP:
        return STATUS_MAP[lowered][0]
    raise AgentWorkError(f"Unknown status: {candidate}. Use one of: {', '.join(sorted(STATUS_MAP))}")


def replacement_connection() -> sqlite3.Connection:
    conn = agent_work_app.connect(replacement_db_path())
    agent_work_app.init_db(conn)
    for field_name, ddl in {
        "closed_on": "text not null default ''",
        "dispatch": "text not null default ''",
        "validation_report": "text not null default ''",
        "agent": "text not null default ''",
        "project": "text not null default 'cento-agent-work'",
        "tracker": "text not null default 'Agent Task'",
        "node": "text not null default ''",
        "role": "text not null default ''",
        "package": "text not null default ''",
    }.items():
        agent_work_app.ensure_table_column(conn, "issues", field_name, ddl)
    conn.commit()
    return conn


def replacement_api_base() -> str:
    return os.environ.get("CENTO_AGENT_WORK_API", DEFAULT_REPLACEMENT_API)


def replacement_issue_link(issue_id: int) -> str:
    base = replacement_api_base().rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]
    return f"{base}/issues/{issue_id}"


def _retryable_replacement_api_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in REPLACEMENT_API_RETRYABLE_STATUS_CODES
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        text = str(reason).lower()
        return any(
            token in text
            for token in (
                "connection refused",
                "connection reset",
                "timed out",
                "timeout",
                "temporarily unavailable",
                "database is locked",
                "busy",
            )
        )
    if isinstance(exc, (OSError, TimeoutError)):
        text = str(exc).lower()
        return any(token in text for token in ("connection refused", "connection reset", "timed out", "timeout", "database is locked", "busy"))
    return False


def replacement_api_request(path: str, api: str) -> Any:
    base = replacement_api_base() if not api else api.rstrip("/")
    url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    delay = 0.15
    last_exc: BaseException | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.getcode() >= 400:
                    raise AgentWorkError(f"Replacement API request failed: {url} (HTTP {response.getcode()})")
                payload = response.read().decode("utf-8")
                break
        except (OSError, TimeoutError, urllib.error.URLError) as exc:
            last_exc = exc
            if attempt < 4 and _retryable_replacement_api_error(exc):
                time.sleep(delay)
                delay = min(delay * 2, 1.0)
                continue
            raise AgentWorkError(f"Replacement API request failed: {exc}") from exc
    else:
        raise AgentWorkError(f"Replacement API request failed: {last_exc}")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise AgentWorkError(f"Replacement API JSON decode failed for {url}: {exc}") from exc


def replacement_api_issue_list(api: str, *, include_closed: bool) -> list[dict[str, Any]]:
    query = "?status=open"
    if include_closed:
        query = "?status=all"
    payload = replacement_api_request(f"/api/issues{query}", api)
    if isinstance(payload, dict):
        issues = payload.get("issues")
    elif isinstance(payload, list):
        issues = payload
    else:
        raise AgentWorkError("Replacement API list payload is not valid")
    if issues is None:
        return []
    if not isinstance(issues, list):
        raise AgentWorkError("Replacement API list payload missing array at issues")
    return issues


def replacement_api_issue_detail(api: str, issue_id: int) -> dict[str, Any]:
    payload = replacement_api_request(f"/api/issues/{issue_id}", api)
    if not isinstance(payload, dict):
        raise AgentWorkError(f"Replacement API issue detail for #{issue_id} is invalid")
    return payload


def replacement_issue_rows(conn: sqlite3.Connection, include_closed: bool = False) -> list[sqlite3.Row]:
    where_clause = "" if include_closed else "where lower(i.status) != 'done'"
    return conn.execute(
        f"""
        select
            i.id,
            i.subject,
            i.project as project,
            i.tracker as tracker,
            i.status,
            i.done_ratio,
            i.updated_on,
            i.closed_on,
            coalesce(i.node, '') as node,
            coalesce(i.assignee, i.agent, '') as agent,
            coalesce(i.role, '') as role,
            coalesce(i.package, '') as package,
            coalesce(i.dispatch, '') as dispatch,
            coalesce(i.validation_report, '') as validation_report,
            coalesce(i.source, 'replacement') as source
        from issues i
        {where_clause}
        order by datetime(i.updated_on) desc, i.id desc
        """,
    ).fetchall()


def replacement_issue_detail(conn: sqlite3.Connection, issue_id: int) -> dict[str, Any]:
    payload = conn.execute(
        """
        select
            i.id,
            i.subject,
            i.description,
            i.project as project,
            i.tracker as tracker,
            i.status,
            i.done_ratio,
            i.updated_on,
            i.closed_on,
            coalesce(i.node, '') as node,
            coalesce(i.assignee, i.agent, '') as agent,
            coalesce(i.role, '') as role,
            coalesce(i.package, '') as package,
            coalesce(i.dispatch, '') as dispatch,
            coalesce(i.validation_report, '') as validation_report,
            coalesce(i.source, 'replacement') as source
        from issues i
        where i.id = ?
        """,
        (issue_id,),
    ).fetchone()
    if not payload:
        raise AgentWorkError(f"Issue not found: {issue_id}")
    return dict(payload)


def replacement_next_local_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "select coalesce(max(id), ? - 1) + 1 as next_id from issues where id >= ?",
        (REPLACEMENT_LOCAL_ID_FLOOR, REPLACEMENT_LOCAL_ID_FLOOR),
    ).fetchone()
    return int(row["next_id"]) if row else REPLACEMENT_LOCAL_ID_FLOOR


def is_replacement_local_issue_id(issue_id: int) -> bool:
    return issue_id >= REPLACEMENT_LOCAL_ID_FLOOR


def replacement_relocate_local_issue(conn: sqlite3.Connection, issue_id: int) -> int:
    new_id = replacement_next_local_id(conn)
    tables = (
        "attachments",
        "custom_values",
        "issue_custom_values",
        "issue_entities",
        "journals",
        "validation_evidences",
    )
    conn.execute("update issues set id = ? where id = ?", (new_id, issue_id))
    for table in tables:
        conn.execute(f"update {table} set issue_id = ? where issue_id = ?", (new_id, issue_id))
    return new_id


def replacement_find_or_create_ids(conn: sqlite3.Connection, issue_id: int | None) -> int:
    if issue_id is None:
        return replacement_next_local_id(conn)
    issue_id = int(issue_id)
    row = conn.execute("select source from issues where id = ?", (issue_id,)).fetchone()
    if row and str(row["source"] or "") == "taskstream":
        replacement_relocate_local_issue(conn, issue_id)
    return issue_id


def replacement_store_evidence(conn: sqlite3.Connection, issue_id: int, report: str | None) -> None:
    if not report:
        return
    try:
        payload = json.loads(report)
    except json.JSONDecodeError:
        return
    evidence_items = payload.get("evidence") or []
    if not isinstance(evidence_items, list):
        evidence_items = [evidence_items]
    now = now_iso()
    for item in evidence_items:
        path = str(item).strip()
        if not path:
            continue
        filename = Path(path).name or "validation-evidence"
        conn.execute(
            """
            insert into validation_evidences(issue_id, label, path, url, created_on, source, note)
            values (?, ?, ?, ?, ?, ?, ?)
            on conflict(issue_id, path) do update set
              label = excluded.label,
              url = excluded.url,
              created_on = excluded.created_on,
              source = excluded.source,
              note = excluded.note
            """,
            (issue_id, filename, path, "", now, "agent-work", "Validation evidence recorded from validation report."),
        )


def replacement_parity_diff(redmine: dict[str, Any], replacement: dict[str, Any]) -> list[str]:
    fields = ["subject", "project", "tracker", "status", "node", "agent", "role", "package", "dispatch"]
    diffs: list[str] = []
    for field in fields:
        left = _replacement_status(redmine.get("status")) if field == "status" else str(redmine.get(field) or "")
        right = _replacement_status(replacement.get("status")) if field == "status" else str(replacement.get(field) or "")
        if left != right:
            diffs.append(f"{field}: redmine={left!r} replacement={right!r}")
    if int(redmine.get("done_ratio") or 0) != int(replacement.get("done_ratio") or 0):
        diffs.append(f"done_ratio: redmine={int(redmine.get('done_ratio') or 0)} replacement={int(replacement.get('done_ratio') or 0)}")
    return diffs


def report_replacement_parity(action: str, mismatches: list[str], issue_id: int | None = None) -> None:
    if not mismatches:
        return
    target = f"issue #{issue_id}" if issue_id else "list"
    print(f"[agent-work parity] {action} mismatch for {target}: {'; '.join(mismatches[:6])}", file=sys.stderr)


def current_node() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Linux":
        return "linux"
    return system.lower()


def cento_command() -> str:
    default_cento = ROOT / "scripts" / "cento.sh"
    return os.environ.get("CENTO_BIN", str(default_cento) if default_cento.exists() else "cento")


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    return "'" + str(value).replace("'", "''") + "'"


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return result or "agent-work"


def normalize_role(value: str | None, *, default: str = "builder") -> str:
    role = (value or default).strip().lower()
    if role not in ROLE_CHOICES:
        raise AgentWorkError(f"Unknown role: {role}. Use one of: {', '.join(ROLE_CHOICES)}")
    return role


class FormatContext(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def format_manifest_value(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format_map(FormatContext(context))
    return value


def resolve_root_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def enforce_validator_authorized(agent: str, allowed: list[str] | None = None) -> None:
    env_allowed = split_csv(os.environ.get("CENTO_VALIDATOR_AGENTS", ""))
    allowed_agents = allowed or env_allowed
    if allowed_agents and agent not in allowed_agents:
        raise AgentWorkError(f"Validator agent {agent!r} is not authorized. Allowed validators: {', '.join(allowed_agents)}")


def load_runtime_registry() -> dict[str, Any]:
    path_value = os.environ.get("CENTO_AGENT_RUNTIME_CONFIG")
    path = resolve_root_path(path_value) if path_value else RUNTIME_REGISTRY_PATH
    if not path.exists():
        return DEFAULT_RUNTIME_REGISTRY
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgentWorkError(f"Invalid agent runtime registry JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkError("Agent runtime registry root must be an object")
    runtimes = payload.get("runtimes")
    if not isinstance(runtimes, list) or not runtimes:
        raise AgentWorkError("Agent runtime registry must include a non-empty runtimes list")
    return payload


def runtime_entries() -> list[dict[str, Any]]:
    registry = load_runtime_registry()
    entries = []
    for raw in registry.get("runtimes", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        entry = dict(raw)
        entry["weight"] = int(entry.get("weight") or 0)
        if entry["weight"] < 0:
            raise AgentWorkError(f"Runtime {entry['id']} has negative weight")
        entries.append(entry)
    if not entries:
        raise AgentWorkError("Agent runtime registry has no usable runtimes")
    return entries


def runtime_ids() -> list[str]:
    return [str(entry["id"]) for entry in runtime_entries()]


def runtime_by_id(runtime_id: str) -> dict[str, Any]:
    for entry in runtime_entries():
        if entry["id"] == runtime_id:
            return entry
    raise AgentWorkError(f"Unknown runtime: {runtime_id}. Use one of: {', '.join(runtime_ids())}")


def weighted_runtime(issue_id: int, role: str, package: str = "") -> dict[str, Any]:
    entries = runtime_entries()
    weighted = [entry for entry in entries if entry.get("weight", 0) > 0]
    if not weighted:
        preferred = next((entry for entry in entries if entry.get("preferred")), entries[0])
        return preferred
    total = sum(int(entry["weight"]) for entry in weighted)
    digest = hashlib.sha256(f"{issue_id}:{role}:{package}".encode("utf-8")).hexdigest()
    bucket = int(digest[:12], 16) % total
    cursor = 0
    for entry in weighted:
        cursor += int(entry["weight"])
        if bucket < cursor:
            return entry
    return weighted[-1]


def select_runtime(issue: dict[str, Any], role: str, requested: str = "auto") -> dict[str, Any]:
    runtime_override = os.environ.get("CENTO_AGENT_RUNTIME")
    runtime_id = (requested or runtime_override or "auto").strip()
    if runtime_id == "auto":
        runtime_id = runtime_override or "auto"
    if runtime_id and runtime_id != "auto":
        return runtime_by_id(runtime_id)
    return weighted_runtime(int(issue["id"]), role, str(issue.get("package") or ""))


def git_head() -> str:
    try:
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def agent_run_dir(run_id: str) -> Path:
    return AGENT_RUN_ROOT / run_id


def agent_run_path(run_id: str) -> Path:
    return agent_run_dir(run_id) / "run.json"


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise AgentWorkError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkError(f"Expected JSON object in {path}")
    return payload


def write_agent_run(record: dict[str, Any]) -> dict[str, Any]:
    run_id = str(record.get("run_id") or "").strip()
    if not run_id:
        raise AgentWorkError("agent run record is missing run_id")
    run_dir = agent_run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    path = agent_run_path(run_id)
    payload = dict(record)
    payload["run_id"] = run_id
    payload["ledger_path"] = display_path(path)
    payload["updated_at"] = now_iso()
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return payload


def update_agent_run(run_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    record = read_json_file(agent_run_path(run_id))
    if not record:
        record = {"run_id": run_id, "created_at": now_iso()}
    for key, value in updates.items():
        if value is not None:
            record[key] = value
    return write_agent_run(record)


def create_agent_run(
    *,
    run_id: str,
    issue: dict[str, Any],
    node: str,
    agent: str,
    role: str,
    runtime: dict[str, Any],
    model: str,
    command: str,
    prompt_path: str,
    log_path: str,
    tmux_session: str,
    status: str,
    dispatch_path: str,
) -> dict[str, Any]:
    package = str(issue.get("package") or "")
    record = {
        "run_id": run_id,
        "issue_id": int(issue["id"]),
        "issue_subject": issue.get("subject") or "",
        "package": package,
        "node": node,
        "agent": agent,
        "role": role,
        "runtime": str(runtime.get("id") or ""),
        "runtime_display_name": runtime.get("display_name", runtime.get("id", "")),
        "provider": runtime.get("provider", ""),
        "model": model,
        "command": command,
        "pid": None,
        "child_pid": None,
        "tmux_session": tmux_session,
        "status": status,
        "started_at": now_iso(),
        "ended_at": now_iso() if status in ENDED_RUN_STATUSES else None,
        "exit_code": 0 if status == "dry_run" else None,
        "prompt_path": prompt_path,
        "log_path": log_path,
        "cwd": str(ROOT),
        "git_head": git_head(),
        "dispatch_path": dispatch_path,
        "source": "agent-work-dispatch",
    }
    return write_agent_run(record)


def load_agent_run(run_id: str) -> dict[str, Any]:
    record = read_json_file(agent_run_path(run_id))
    if not record:
        raise AgentWorkError(f"Agent run not found: {run_id}")
    return record


def load_agent_runs() -> list[dict[str, Any]]:
    if not AGENT_RUN_ROOT.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(AGENT_RUN_ROOT.glob("*/run.json")):
        try:
            record = read_json_file(path)
        except AgentWorkError as exc:
            records.append({"run_id": path.parent.name, "status": "invalid", "health": "invalid_json", "error": str(exc), "ledger_path": display_path(path)})
            continue
        if record:
            records.append(record)
    return records


def pid_alive(value: Any) -> bool:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def tmux_session_alive(session: str | None) -> bool:
    if not session:
        return False
    try:
        proc = subprocess.run(["tmux", "has-session", "-t", session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def run_elapsed(started_at: Any, ended_at: Any | None = None) -> str:
    started = str(started_at or "").strip()
    if not started:
        return ""
    ended = str(ended_at or "").strip()
    try:
        start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00")) if ended else datetime.now(timezone.utc)
    except ValueError:
        return ""
    seconds = max(0, int((end_dt - start_dt).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def reconcile_agent_run(record: dict[str, Any], *, write: bool = False) -> dict[str, Any]:
    reconciled = dict(record)
    status = str(reconciled.get("status") or "unknown")
    pid_running = pid_alive(reconciled.get("pid")) or pid_alive(reconciled.get("child_pid"))
    tmux_running = tmux_session_alive(str(reconciled.get("tmux_session") or ""))
    reconciled["pid_alive"] = pid_running
    reconciled["tmux_alive"] = tmux_running
    if status in ACTIVE_RUN_STATUSES or status == "stale":
        if pid_running or tmux_running:
            reconciled["status"] = "running"
            reconciled["health"] = "running"
            reconciled["ended_at"] = None
            reconciled["exit_code"] = None
        else:
            reconciled["status"] = "stale"
            reconciled["health"] = "stale_no_process"
            if not reconciled.get("ended_at"):
                reconciled["ended_at"] = now_iso()
    elif status in {"succeeded", "dry_run"}:
        reconciled["health"] = "ok"
    elif status in {"archived", "failed", "blocked", "stale", "exited_unknown", "invalid"}:
        reconciled["health"] = reconciled.get("health") or status
    else:
        reconciled["health"] = "unknown"
    reconciled["elapsed"] = run_elapsed(reconciled.get("started_at"), reconciled.get("ended_at"))
    if write and reconciled != record and reconciled.get("source") != "ps":
        reconciled = write_agent_run(reconciled)
    return reconciled


def command_runtime(command: str) -> str:
    value = command.lower()
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    first = Path(tokens[0]).name.lower() if tokens else ""
    if first in {"rg", "grep", "ps", "bash", "sh", "zsh", "python", "python3"}:
        return ""
    if first == "claude" or "/claude" in value or "anthropic-ai/claude-code" in value:
        return "claude-code"
    if first == "codex" or "/codex" in value or "@openai/codex" in value:
        return "codex"
    if first == "node" and "codex" in value:
        return "codex"
    return ""


def read_agent_processes() -> list[dict[str, Any]]:
    try:
        proc = subprocess.run(["ps", "-eo", "pid=,ppid=,stat=,etime=,command="], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    processes: list[dict[str, Any]] = []
    for raw in proc.stdout.splitlines():
        parts = raw.strip().split(None, 4)
        if len(parts) < 5:
            continue
        pid, ppid, stat, elapsed, command = parts
        runtime = command_runtime(command)
        if not runtime:
            continue
        if "agent_work.py runs" in command or "agent_work.py run-status" in command:
            continue
        processes.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "stat": stat,
                "elapsed": elapsed,
                "command": command,
                "runtime": runtime,
            }
        )
    return processes


def untracked_interactive_runs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracked_pids: set[int] = set()
    for record in records:
        for key in ("pid", "child_pid"):
            try:
                pid = int(record.get(key) or 0)
            except (TypeError, ValueError):
                pid = 0
            if pid > 0:
                tracked_pids.add(pid)
    processes = read_agent_processes()
    agent_process_pids = {int(proc["pid"]) for proc in processes}
    synthetic: list[dict[str, Any]] = []
    for proc in processes:
        if proc["pid"] in tracked_pids or proc["ppid"] in tracked_pids:
            continue
        if proc["ppid"] in agent_process_pids:
            continue
        run_id = f"untracked-{proc['runtime']}-{proc['pid']}"
        synthetic.append(
            {
                "run_id": run_id,
                "issue_id": None,
                "package": "",
                "node": current_node(),
                "agent": os.environ.get("USER") or "",
                "role": "interactive",
                "runtime": proc["runtime"],
                "model": "",
                "command": proc["command"],
                "pid": proc["pid"],
                "ppid": proc["ppid"],
                "tmux_session": "",
                "status": "untracked_interactive",
                "health": "untracked",
                "started_at": "",
                "ended_at": None,
                "exit_code": None,
                "prompt_path": "",
                "log_path": "",
                "cwd": "",
                "git_head": "",
                "ledger_path": "",
                "source": "ps",
                "elapsed": proc["elapsed"],
            }
        )
    return synthetic


def print_agent_run_table(records: list[dict[str, Any]]) -> None:
    if not records:
        print("No agent runs.")
        return
    print(f"{'RUN ID':<34} {'STATUS':<22} {'ISSUE':<7} {'RUNTIME':<12} {'NODE':<7} {'PID':<8} {'HEALTH':<18} LOG")
    for record in records:
        issue = str(record.get("issue_id") or "-")
        pid = str(record.get("child_pid") or record.get("pid") or "-")
        print(
            f"{str(record.get('run_id') or '')[:34]:<34} "
            f"{str(record.get('status') or '')[:22]:<22} "
            f"{issue[:7]:<7} "
            f"{str(record.get('runtime') or '-')[:12]:<12} "
            f"{str(record.get('node') or '-')[:7]:<7} "
            f"{pid[:8]:<8} "
            f"{str(record.get('health') or '-')[:18]:<18} "
            f"{record.get('log_path') or ''}"
        )


def agent_run_records(*, include_untracked: bool = True, reconcile: bool = False) -> list[dict[str, Any]]:
    records = [reconcile_agent_run(record, write=reconcile) for record in load_agent_runs()]
    if include_untracked:
        records.extend(untracked_interactive_runs(records))
    status_rank = {
        "running": 0,
        "launching": 1,
        "planned": 2,
        "untracked_interactive": 3,
        "stale": 4,
        "failed": 5,
        "blocked": 6,
        "exited_unknown": 7,
        "succeeded": 8,
        "dry_run": 9,
    }
    records.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status") or ""), 20),
            str(item.get("updated_at") or item.get("started_at") or ""),
            str(item.get("run_id") or ""),
        ),
        reverse=False,
    )
    return records


def run_has_ended(record: dict[str, Any]) -> bool:
    ended_at = record.get("ended_at")
    if ended_at is None:
        return False
    if isinstance(ended_at, str):
        return bool(ended_at.strip())
    return bool(ended_at)


def is_active_run_record(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "")
    if status in ACTIVE_RUN_STATUSES or status == "untracked_interactive":
        return True
    if status == "stale":
        return not run_has_ended(record)
    return False


def docker_psql_args(sql: str) -> list[str]:
    return [
        "docker",
        "exec",
        f"cento-{LEGACY_TRACKER_NAME}-postgres",
        "psql",
        "-U",
        "red" + "mine",
        "-d",
        "red" + "mine",
        "-X",
        "-q",
        "-v",
        "ON_ERROR_STOP=1",
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]


def psql_commands(sql: str) -> list[list[str]]:
    cento = cento_command()
    transport = os.environ.get("CENTO_TASKSTREAM_TRANSPORT", "auto").lower()
    base = docker_psql_args(sql)
    commands: list[list[str]] = []

    if transport in {"auto", "local"} and current_node() == "linux":
        commands.append(base)
        commands.append(["sg", "docker", "-c", shlex.join(base)])

    if transport in {"auto", "direct"} and current_node() != "linux":
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        known_hosts = STATE_DIR / "agent-work-known-hosts"
        host = os.environ.get("CENTO_TASKSTREAM_SSH", "alice@alisapad.local")
        commands.append(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                f"UserKnownHostsFile={known_hosts}",
                "-o",
                "ConnectTimeout=5",
                host,
                shlex.join(base),
            ]
        )

    if transport in {"auto", "cluster"}:
        commands.append([cento, "cluster", "exec", "linux", "--", *base])

    if not commands:
        raise AgentWorkError(f"Unsupported CENTO_TASKSTREAM_TRANSPORT={transport!r}")
    return commands


def psql(sql: str, *, timeout: int = 30) -> str:
    last_error = ""
    for cmd in psql_commands(sql):
        for attempt in range(1, 3):
            try:
                proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                last_error = f"{cmd[0]} psql timed out after {timeout}s"
            else:
                if proc.returncode == 0:
                    return proc.stdout.strip()
                last_error = (proc.stderr or proc.stdout or f"psql failed with exit {proc.returncode}").strip()
                retryable = "Connection refused" in last_error or "Connection closed" in last_error or "No such file or directory" in last_error
                if not retryable:
                    break
            if attempt < 2:
                time.sleep(1)
    raise AgentWorkError(last_error)


def psql_json(sql: str) -> Any:
    output = psql(sql)
    if not output:
        return None
    return json.loads(output)


def scalar(sql: str) -> str:
    output = psql(sql)
    if not output:
        raise AgentWorkError("Expected one SQL row, got none")
    return output.splitlines()[0]


def ensure_status(name: str, closed: bool) -> int:
    found = psql(f"select id from issue_statuses where name = {sql_literal(name)} limit 1;")
    if found:
        return int(found.splitlines()[0])
    return int(
        scalar(
            f"""
            insert into issue_statuses(name, is_closed, position)
            values ({sql_literal(name)}, {sql_literal(closed)}, coalesce((select max(position) from issue_statuses), 0) + 1)
            returning id;
            """
        )
    )


def ensure_tracker(name: str, default_status_id: int) -> int:
    found = psql(f"select id from trackers where name = {sql_literal(name)} limit 1;")
    if found:
        tracker_id = int(found.splitlines()[0])
        psql(f"update trackers set default_status_id = {default_status_id} where id = {tracker_id};")
        return tracker_id
    return int(
        scalar(
            f"""
            insert into trackers(name, position, is_in_roadmap, fields_bits, default_status_id)
            values ({sql_literal(name)}, coalesce((select max(position) from trackers), 0) + 1, false, 0, {default_status_id})
            returning id;
            """
        )
    )


def ensure_custom_field(name: str, field_format: str, tracker_ids: list[int]) -> int:
    found = psql(f"select id from custom_fields where type = 'IssueCustomField' and name = {sql_literal(name)} limit 1;")
    if found:
        field_id = int(found.splitlines()[0])
    else:
        field_id = int(
            scalar(
                f"""
                insert into custom_fields(
                    type, name, field_format, possible_values, regexp, is_required, is_for_all,
                    is_filter, position, searchable, editable, visible, multiple, description
                )
                values (
                    'IssueCustomField', {sql_literal(name)}, {sql_literal(field_format)}, NULL, '',
                    false, true, true, coalesce((select max(position) from custom_fields), 0) + 1,
                    true, true, true, false, 'Managed by Cento agent-work'
                )
                returning id;
                """
            )
        )
    for tracker_id in tracker_ids:
        psql(
            f"""
            insert into custom_fields_trackers(custom_field_id, tracker_id)
            select {field_id}, {tracker_id}
            where not exists (
                select 1
                from custom_fields_trackers
                where custom_field_id = {field_id} and tracker_id = {tracker_id}
            );
            """
        )
    return field_id


def ensure_project(identifier: str = DEFAULT_PROJECT_IDENTIFIER, name: str = DEFAULT_PROJECT_NAME) -> int:
    found = psql(f"select id from projects where identifier = {sql_literal(identifier)} limit 1;")
    if found:
        project_id = int(found.splitlines()[0])
    else:
        project_id = int(
            scalar(
                f"""
                with bounds as (
                    select coalesce(max(rgt), 0) + 1 as lft_value from projects
                )
                insert into projects(
                    name, description, homepage, is_public, created_on, updated_on,
                    identifier, status, lft, rgt, inherit_members
                )
                select
                    {sql_literal(name)},
                    'Cento-managed work board for assigning tasks to coding agents across the Mac/Linux cluster.',
                    '',
                    false,
                    now(),
                    now(),
                    {sql_literal(identifier)},
                    1,
                    lft_value,
                    lft_value + 1,
                    false
                from bounds
                returning id;
                """
            )
        )
    return project_id


def ensure_bootstrap() -> dict[str, Any]:
    global BOOTSTRAP_CACHE
    cutover_write_guard("bootstrap")
    if BOOTSTRAP_CACHE is not None:
        return BOOTSTRAP_CACHE
    status_ids = {key: ensure_status(name, closed) for key, (name, closed, _ratio) in STATUS_MAP.items()}
    task_tracker_id = ensure_tracker(TASK_TRACKER, status_ids["queued"])
    epic_tracker_id = ensure_tracker(EPIC_TRACKER, status_ids["queued"])
    project_id = ensure_project()
    for tracker_id in [task_tracker_id, epic_tracker_id]:
        psql(
            f"""
            insert into projects_trackers(project_id, tracker_id)
            select {project_id}, {tracker_id}
            where not exists (
                select 1 from projects_trackers where project_id = {project_id} and tracker_id = {tracker_id}
            );
            """
        )
    for module in MODULES:
        psql(
            f"""
            insert into enabled_modules(project_id, name)
            select {project_id}, {sql_literal(module)}
            where not exists (
                select 1 from enabled_modules where project_id = {project_id} and name = {sql_literal(module)}
            );
            """
        )
    custom_field_ids = {name: ensure_custom_field(name, fmt, [task_tracker_id, epic_tracker_id]) for name, fmt in CUSTOM_FIELDS}
    BOOTSTRAP_CACHE = {
        "project_id": project_id,
        "project_identifier": DEFAULT_PROJECT_IDENTIFIER,
        "status_ids": status_ids,
        "task_tracker_id": task_tracker_id,
        "epic_tracker_id": epic_tracker_id,
        "custom_field_ids": custom_field_ids,
    }
    return BOOTSTRAP_CACHE


def priority_id() -> int:
    return int(scalar("select id from enumerations where type = 'IssuePriority' order by is_default desc, position limit 1;"))


def admin_user_id() -> int:
    return int(scalar("select id from users where login = 'admin' limit 1;"))


def issue_status_id(status_key: str) -> int:
    bootstrap = ensure_bootstrap()
    if status_key not in bootstrap["status_ids"]:
        raise AgentWorkError(f"Unknown status: {status_key}. Use one of: {', '.join(STATUS_MAP)}")
    return int(bootstrap["status_ids"][status_key])


def issue_done_ratio(status_key: str) -> int:
    if status_key not in STATUS_MAP:
        raise AgentWorkError(f"Unknown status: {status_key}")
    return STATUS_MAP[status_key][2]


def agent_description(title: str, description: str, node: str, agent: str, package: str, dispatch: str, role: str = "builder") -> str:
    body = description.strip() or "No description provided."
    role = normalize_role(role)
    return textwrap.dedent(
        f"""\
        h2. Cento Agent Work

        * Node: {node or "unassigned"}
        * Agent: {agent or "unassigned"}
        * Role: {role}
        * Package: {package or "default"}
        * Created: {now_iso()}

        h3. Objective

        {body}

        h3. Agent Protocol

        # Builder claim: @cento agent-work claim ISSUE_ID --node NODE --agent AGENT --role builder@.
        # Builder ready for validation: @cento agent-work update ISSUE_ID --status validating --role builder --note "..."@.
        # Validator claim: @cento agent-work claim ISSUE_ID --node NODE --agent AGENT --role validator@.
        # Validator pass: @cento agent-work validate ISSUE_ID --result pass --evidence PATH --note "..."@.
        # If that route is not registered on this node, use @python3 scripts/agent_work.py ...@ from the Cento repo.
        # Keep Taskstream updated with @cento agent-work update ISSUE_ID --status running --note "..."@.
        # Close only after verification: @cento agent-work update ISSUE_ID --status done --note "..."@.

        h3. Cluster Dispatch

        {dispatch or "Not dispatched yet."}
        """
    )


def set_custom_values(issue_id: int, values: dict[str, str]) -> None:
    bootstrap = ensure_bootstrap()
    for field_name, value in values.items():
        field_id = bootstrap["custom_field_ids"].get(field_name)
        if not field_id:
            continue
        psql(
            f"""
            delete from custom_values
            where customized_type = 'Issue' and customized_id = {issue_id} and custom_field_id = {field_id};
            insert into custom_values(customized_type, customized_id, custom_field_id, value)
            values ('Issue', {issue_id}, {field_id}, {sql_literal(value)});
            """
        )


def create_issue(
    title: str,
    description: str,
    node: str,
    agent: str,
    package: str,
    status: str = "queued",
    tracker: str = TASK_TRACKER,
    dispatch: str = "",
    role: str = "builder",
    forced_id: int | None = None,
) -> int:
    backend = agent_work_backend()
    if backend == BACKEND_REDLINE:
        return create_issue_redmine(title, description, node, agent, package, status=status, tracker=tracker, dispatch=dispatch, role=role)
    return create_issue_replacement(
        title,
        description,
        node,
        agent,
        package,
        status=status,
        tracker=tracker,
        dispatch=dispatch,
        role=role,
        forced_id=forced_id,
    )


def create_issue_redmine(
    title: str,
    description: str,
    node: str,
    agent: str,
    package: str,
    status: str = "queued",
    tracker: str = TASK_TRACKER,
    dispatch: str = "",
    role: str = "builder",
) -> int:
    cutover_write_guard("create")
    bootstrap = ensure_bootstrap()
    role = normalize_role(role)
    tracker_id = bootstrap["epic_tracker_id"] if tracker == EPIC_TRACKER else bootstrap["task_tracker_id"]
    status_id = issue_status_id(status)
    project_id = bootstrap["project_id"]
    author_id = admin_user_id()
    prio_id = priority_id()
    desc = agent_description(title, description, node, agent, package, dispatch, role)
    issue_id = int(
        scalar(
            f"""
            insert into issues(
                tracker_id, project_id, subject, description, status_id, assigned_to_id,
                priority_id, author_id, created_on, updated_on, start_date, done_ratio,
                is_private
            )
            values (
                {tracker_id},
                {project_id},
                {sql_literal(title)},
                {sql_literal(desc)},
                {status_id},
                {author_id},
                {prio_id},
                {author_id},
                now(),
                now(),
                current_date,
                {issue_done_ratio(status)},
                false
            )
            returning id;
            """
        )
    )
    psql(f"update issues set root_id = {issue_id}, lft = 1, rgt = 2 where id = {issue_id};")
    set_custom_values(
        issue_id,
        {
            "Agent Node": node,
            "Agent Owner": agent,
            "Agent Role": role,
            "Agent State": status,
            "Cento Work Package": package,
            "Cluster Dispatch": dispatch,
        },
    )
    add_journal(issue_id, f"Cento created agent work item. node={node or 'unassigned'} agent={agent or 'unassigned'} role={role} package={package or 'default'}")
    return issue_id


def create_issue_replacement(
    title: str,
    description: str,
    node: str,
    agent: str,
    package: str,
    status: str = "queued",
    tracker: str = TASK_TRACKER,
    dispatch: str = "",
    role: str = "builder",
    forced_id: int | None = None,
) -> int:
    if status:
        status = status.strip()
    status_label = _replacement_status(status)
    if status_label is None:
        status_label = STATUS_MAP["queued"][0]
    status_key = status_label.lower()
    done_ratio = issue_done_ratio(status_key)
    now = now_iso()
    conn = replacement_connection()
    issue_id = replacement_find_or_create_ids(conn, forced_id)
    source = "archive" if forced_id is not None else "taskstream"
    conn.execute(
        """
        insert into issues(
            id,
            subject,
            project,
            tracker,
            status,
            priority,
            assignee,
            node,
            agent,
            role,
            package,
            description,
            done_ratio,
            updated_on,
            closed_on,
            source,
            dispatch,
            validation_report,
            migrated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
            subject = excluded.subject,
            project = excluded.project,
            tracker = excluded.tracker,
            status = excluded.status,
            assignee = excluded.assignee,
            node = excluded.node,
            agent = excluded.agent,
            role = excluded.role,
            package = excluded.package,
            description = excluded.description,
            done_ratio = excluded.done_ratio,
            updated_on = excluded.updated_on,
            closed_on = excluded.closed_on,
            source = excluded.source,
            dispatch = excluded.dispatch,
            validation_report = excluded.validation_report,
            migrated_at = excluded.migrated_at
        """,
        (
            issue_id,
            title,
            DEFAULT_PROJECT_IDENTIFIER,
            tracker,
            status_label,
            "Normal",
            agent,
            node,
            agent,
            normalize_role(role),
            package,
            agent_description(title, description, node, agent, package, dispatch, role),
            done_ratio,
            now,
            now if status_key == "done" else "",
            source,
            dispatch,
            "",
            now,
        ),
    )
    conn.execute(
        "insert into journals(issue_id, author, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, ?, 'agent-work')",
        (issue_id, agent or "local operator", now, f"Replacement create issue. status={status_label}", "", status_label),
    )
    conn.commit()
    return issue_id


def add_journal(issue_id: int, note: str, *, old_status_id: int | None = None, new_status_id: int | None = None) -> None:
    note = note.strip()
    if not note and old_status_id is None:
        return
    journal_id = int(
        scalar(
            f"""
            insert into journals(journalized_id, journalized_type, user_id, notes, created_on, updated_on, private_notes)
            values ({issue_id}, 'Issue', {admin_user_id()}, {sql_literal(note)}, now(), now(), false)
            returning id;
            """
        )
    )
    if old_status_id is not None and new_status_id is not None and old_status_id != new_status_id:
        psql(
            f"""
            insert into journal_details(journal_id, property, prop_key, old_value, value)
            values ({journal_id}, 'attr', 'status_id', {sql_literal(old_status_id)}, {sql_literal(new_status_id)});
            """
        )


def update_issue(
    issue_id: int,
    status: str | None,
    note: str,
    node: str | None,
    agent: str | None,
    dispatch: str | None,
    role: str | None = None,
    validation_report: str | None = None,
) -> dict[str, Any]:
    backend = agent_work_backend()
    if backend == BACKEND_REDLINE:
        return update_issue_redmine(issue_id, status, note, node, agent, dispatch, role=role, validation_report=validation_report)
    return update_issue_replacement(issue_id, status, note, node, agent, dispatch, role=role, validation_report=validation_report)


def update_issue_redmine(
    issue_id: int,
    status: str | None,
    note: str,
    node: str | None,
    agent: str | None,
    dispatch: str | None,
    role: str | None = None,
    validation_report: str | None = None,
) -> dict[str, Any]:
    cutover_write_guard("update")
    ensure_bootstrap()
    normalized_role = normalize_role(role) if role is not None else None
    if status == "review" and normalized_role != "validator":
        raise AgentWorkError("Review is validator-gated. Use `agent_work.py validate ISSUE --result pass ...` or pass `--role validator`.")
    current = psql_json(
        f"""
        select json_build_object('id', i.id, 'status_id', i.status_id, 'subject', i.subject)
        from issues i
        where i.id = {issue_id};
        """
    )
    if not current:
        raise AgentWorkError(f"Issue not found: {issue_id}")
    old_status_id = int(current["status_id"])
    new_status_id = old_status_id
    done_ratio = None
    closed_expr = "closed_on"
    if status:
        new_status_id = issue_status_id(status)
        done_ratio = issue_done_ratio(status)
        closed_expr = "now()" if status == "done" else "NULL"
        psql(
            f"""
            update issues
            set status_id = {new_status_id},
                done_ratio = {done_ratio},
                closed_on = {closed_expr},
                updated_on = now()
            where id = {issue_id};
            """
        )
    else:
        psql(f"update issues set updated_on = now() where id = {issue_id};")
    custom_updates: dict[str, str] = {}
    if status:
        custom_updates["Agent State"] = status
    if node is not None:
        custom_updates["Agent Node"] = node
    if agent is not None:
        custom_updates["Agent Owner"] = agent
    if normalized_role is not None:
        custom_updates["Agent Role"] = normalized_role
    if dispatch is not None:
        custom_updates["Cluster Dispatch"] = dispatch
    if validation_report is not None:
        custom_updates["Validation Report"] = validation_report
    if custom_updates:
        set_custom_values(issue_id, custom_updates)
    add_journal(issue_id, note or f"Cento updated agent work item to {status or 'same status'}.", old_status_id=old_status_id, new_status_id=new_status_id)
    return show_issue(issue_id)


def update_issue_replacement(
    issue_id: int,
    status: str | None,
    note: str,
    node: str | None,
    agent: str | None,
    dispatch: str | None,
    role: str | None = None,
    validation_report: str | None = None,
) -> dict[str, Any]:
    conn = replacement_connection()
    current = replacement_issue_detail(conn, issue_id)
    old_status = str(current.get("status") or "")
    normalized_status = status
    if normalized_status is not None:
        normalized_status = _replacement_status(normalized_status)
    if normalized_status is None:
        normalized_status = old_status
    new_status = normalized_status
    updates: dict[str, Any] = {}
    if status is not None:
        updates["status"] = new_status
        updates["done_ratio"] = issue_done_ratio(new_status.lower())
        updates["closed_on"] = now_iso() if new_status.lower() == "done" else ""
    if node is not None:
        updates["node"] = node
    if agent is not None:
        updates["agent"] = agent
        updates["assignee"] = agent
    if role is not None:
        updates["role"] = normalize_role(role)
    if dispatch is not None:
        updates["dispatch"] = dispatch
    if validation_report is not None:
        updates["validation_report"] = validation_report
    updates["updated_on"] = now_iso()
    with conn:
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates.keys())
            conn.execute(f"update issues set {assignments} where id = ?", (*updates.values(), issue_id))
        if status is not None or note:
            conn.execute(
                "insert into journals(issue_id, author, created_on, notes, old_status, new_status, source) values (?, ?, ?, ?, ?, ?, 'agent-work')",
                (
                    issue_id,
                    agent or current.get("agent") or "local operator",
                    now_iso(),
                    note or f"Replacement updated status from {old_status} to {new_status}.",
                    old_status,
                    new_status,
                ),
            )
    if validation_report is not None:
        replacement_store_evidence(conn, issue_id, validation_report)
        conn.commit()
    row = replacement_issue_detail(conn, issue_id)
    return _replacement_issue_core(row)


def list_issues(include_closed: bool = False) -> list[dict[str, Any]]:
    backend = agent_work_backend()
    if backend == BACKEND_REDLINE:
        return list_issues_redmine(include_closed)
    return list_issues_replacement(include_closed)


def list_issues_redmine(include_closed: bool = False) -> list[dict[str, Any]]:
    closed_filter = "" if include_closed else "and s.is_closed = false"
    payload = psql_json(
        f"""
        select coalesce(json_agg(row_to_json(rows) order by rows.id), '[]'::json)
        from (
            select
                i.id,
                i.subject,
                p.identifier as project,
                t.name as tracker,
                s.name as status,
                s.is_closed,
                i.done_ratio,
                i.updated_on,
                i.closed_on,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Node' limit 1), '') as node,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Owner' limit 1), '') as agent,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Role' limit 1), '') as role,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Cento Work Package' limit 1), '') as package,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Cluster Dispatch' limit 1), '') as dispatch,
                coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Validation Report' limit 1), '') as validation_report
            from issues i
            join projects p on p.id = i.project_id
            join trackers t on t.id = i.tracker_id
            join issue_statuses s on s.id = i.status_id
            where p.identifier = {sql_literal(DEFAULT_PROJECT_IDENTIFIER)}
            {closed_filter}
            order by s.is_closed, i.updated_on desc, i.id desc
        ) rows;
        """
    )
    return payload or []


def list_issues_replacement(include_closed: bool = False) -> list[dict[str, Any]]:
    conn = replacement_connection()
    return [_replacement_issue_core(dict(row)) for row in replacement_issue_rows(conn, include_closed=include_closed)]


def show_issue(issue_id: int) -> dict[str, Any]:
    backend = agent_work_backend()
    if backend == BACKEND_REDLINE:
        return show_issue_redmine(issue_id)
    return show_issue_replacement(issue_id)


def show_issue_replacement(issue_id: int) -> dict[str, Any]:
    return _replacement_issue_core(replacement_issue_detail(replacement_connection(), issue_id))


def show_issue_redmine(issue_id: int) -> dict[str, Any]:
    payload = psql_json(
        f"""
        select json_build_object(
            'id', i.id,
            'subject', i.subject,
            'description', i.description,
            'project', p.identifier,
            'tracker', t.name,
            'status', s.name,
            'is_closed', s.is_closed,
            'done_ratio', i.done_ratio,
            'updated_on', i.updated_on,
            'closed_on', i.closed_on,
            'node', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Node' limit 1), ''),
            'agent', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Owner' limit 1), ''),
            'role', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Agent Role' limit 1), ''),
            'package', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Cento Work Package' limit 1), ''),
            'dispatch', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Cluster Dispatch' limit 1), ''),
            'validation_report', coalesce((select cv.value from custom_values cv join custom_fields cf on cf.id = cv.custom_field_id where cv.customized_type = 'Issue' and cv.customized_id = i.id and cf.name = 'Validation Report' limit 1), '')
        )
        from issues i
        join projects p on p.id = i.project_id
        join trackers t on t.id = i.tracker_id
        join issue_statuses s on s.id = i.status_id
        where i.id = {issue_id};
        """
    )
    if not payload:
        raise AgentWorkError(f"Issue not found: {issue_id}")
    return payload


def redmine_issue_detail(issue_id: int) -> dict[str, Any]:
    issue = show_issue_redmine(issue_id)
    journals = psql_json(
        f"""
        select coalesce(json_agg(row_to_json(rows) order by rows.created_on desc, rows.id desc), '[]'::json)
        from (
            select
                j.id,
                coalesce(u.login, '') as author,
                j.created_on,
                coalesce(j.notes, '') as notes,
                coalesce(old_status.name, '') as old_status,
                coalesce(new_status.name, '') as new_status
            from journals j
            left join users u on u.id = j.user_id
            left join journal_details old_detail
                on old_detail.journal_id = j.id
                and old_detail.property = 'attr'
                and old_detail.prop_key = 'status_id'
            left join issue_statuses old_status
                on old_status.id = CASE
                    WHEN old_detail.old_value ~ '^[0-9]+$' THEN old_detail.old_value::int
                    ELSE NULL
                END
            left join journal_details new_detail
                on new_detail.journal_id = j.id
                and new_detail.property = 'attr'
                and new_detail.prop_key = 'status_id'
                and new_detail.id = (
                    select nd2.id from journal_details nd2
                    where nd2.journal_id = j.id and nd2.property = 'attr' and nd2.prop_key = 'status_id'
                    order by nd2.id desc
                    limit 1
                )
            left join issue_statuses new_status
                on new_status.id = CASE
                    WHEN new_detail.value ~ '^[0-9]+$' THEN new_detail.value::int
                    ELSE NULL
                END
            where j.journalized_type = 'Issue' and j.journalized_id = {issue_id}
            order by j.created_on desc, j.id desc
        ) rows;
        """
    )
    attachments = psql_json(
        f"""
        select coalesce(json_agg(row_to_json(rows) order by rows.id), '[]'::json)
        from (
            select
                a.id,
                a.filename,
                coalesce(a.filesize::text, '') as size,
                coalesce(a.disk_filename, '') as path,
                a.created_on
            from attachments a
            where a.container_type = 'Issue'
                and a.container_id = {issue_id}
            order by a.id
        ) rows;
        """
    )
    issue["journals"] = journals or []
    issue["attachments"] = attachments or []
    return issue


def print_issue_table(items: list[dict[str, Any]]) -> None:
    if not items:
        print("No agent work items.")
        return
    print(f"{'ID':>5}  {'STATUS':<10} {'NODE':<7} {'ROLE':<10} {'AGENT':<12} {'PACKAGE':<18} TITLE")
    for item in items:
        print(
            f"{item['id']:>5}  {str(item['status'])[:10]:<10} "
            f"{str(item.get('node') or '-')[:7]:<7} "
            f"{str(item.get('role') or '-')[:10]:<10} "
            f"{str(item.get('agent') or '-')[:12]:<12} "
            f"{str(item.get('package') or '-')[:18]:<18} "
            f"{item['subject']}"
        )


def command_bootstrap(_args: argparse.Namespace) -> int:
    cutover_write_guard("bootstrap")
    payload = ensure_bootstrap()
    print(json.dumps({"ok": True, **payload}, indent=2))
    return 0


def append_ownership_section(description: str, owns: list[str]) -> str:
    entries = [item.strip() for item in owns if item and item.strip()]
    if not entries:
        return description
    body = "\n".join(f"* {item}" for item in entries)
    section = f"h3. Owned Files / Modules\n\n{body}"
    description = description.rstrip()
    if not description:
        return section
    return f"{description}\n\n{section}"


def ownership_for_split_task(entries: list[str], index: int) -> list[str]:
    if not entries:
        return []
    if len(entries) == 1:
        return entries
    if len(entries) >= index:
        return [entries[index - 1]]
    return [entries[-1]]


def extract_owned_files(description: str) -> list[str]:
    lines = str(description or "").splitlines()
    owned: list[str] = []
    in_section = False
    for raw in lines:
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("h3.") and "owned" in lowered and ("file" in lowered or "module" in lowered or "scope" in lowered):
            in_section = True
            continue
        if in_section and lowered.startswith("h") and "." in lowered[:4]:
            break
        if not in_section:
            continue
        if not line:
            continue
        if line.startswith(("*", "-", "•")):
            value = line[1:].strip()
        else:
            value = line
        if value:
            owned.append(value)
    return owned


def command_create(args: argparse.Namespace) -> int:
    manifest_path = resolve_root_path(args.manifest)
    manifest = validate_create_story_manifest(manifest_path)
    description = append_ownership_section(args.description or "", args.owns or [])
    description = append_story_manifest_section(description, manifest_path)
    tracker = EPIC_TRACKER if args.epic else TASK_TRACKER
    issue_id = create_issue(args.title, description, args.node or "", args.agent or "", args.package or "default", tracker=tracker, role=args.role)
    canonical_path = canonicalize_create_story_manifest(issue_id, manifest_path, manifest, args)
    update_issue(
        issue_id,
        None,
        f"Story manifest canonicalized: {display_path(canonical_path)}",
        args.node or None,
        args.agent or None,
        None,
        role=args.role,
    )
    issue = show_issue(issue_id)
    issue["story_manifest"] = display_path(canonical_path)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"created #{issue_id}: {issue['subject']}")
        print(f"story_manifest: {display_path(canonical_path)}")
    return 0


def command_split(args: argparse.Namespace) -> int:
    package = args.package or slug(args.title)
    nodes = [item.strip() for item in (args.nodes or args.node or "").split(",") if item.strip()]
    if not nodes:
        nodes = [args.node or ""]
    created = []
    epic_id = create_issue(args.title, args.goal or "", args.node or "", args.agent or "", package, tracker=EPIC_TRACKER, role="coordinator")
    created.append(show_issue(epic_id))
    for index, task in enumerate(args.task, start=1):
        node = nodes[(index - 1) % len(nodes)] if nodes else ""
        title = f"{args.title}: {task}"
        description = f"Part {index}/{len(args.task)} of package {package}.\n\nGoal:\n{args.goal or ''}\n\nTask:\n{task}"
        description = append_ownership_section(description, ownership_for_split_task(args.owns or [], index))
        issue_id = create_issue(title, description, node, args.agent or "", package, role=args.role)
        created.append(show_issue(issue_id))
    if args.json:
        print(json.dumps({"package": package, "issues": created}, indent=2, default=str))
    else:
        print(f"created package {package}")
        print_issue_table(created)
    return 0


def command_list(args: argparse.Namespace) -> int:
    items = list_issues(include_closed=args.all)
    if args.json:
        print(json.dumps({"issues": items}, indent=2, default=str))
    else:
        print_issue_table(items)
    return 0


def compare_record_lists(
    redmine_items: dict[int, dict[str, Any]],
    replacement_items: dict[int, dict[str, Any]],
    keys: list[str],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for issue_id in sorted(redmine_items.keys() & replacement_items.keys()):
        redmine_item = redmine_items[issue_id]
        replacement_item = replacement_items[issue_id]
        diffs: dict[str, dict[str, Any]] = {}
        for key in keys:
            redmine_value = redmine_item.get(key)
            replacement_value = replacement_item.get(key)
            if redmine_value != replacement_value:
                diffs[key] = {"red" + "mine": redmine_value, "replacement": replacement_value}
        status = "pass" if not diffs else "fail"
        results.append(
            {
                "issue_id": issue_id,
                "scope": "field-matching",
                "status": status,
                "differences": diffs,
            }
        )
    return results


def compare_sequences(
    redmine_items: list[dict[str, Any]],
    replacement_items: list[dict[str, Any]],
    key_fields: list[str],
) -> dict[str, Any]:
    redmine_norm = [{key: item.get(key) for key in key_fields} for item in redmine_items]
    replacement_norm = [{key: item.get(key) for key in key_fields} for item in replacement_items]
    redmine_norm = sorted(redmine_norm, key=lambda item: tuple(str(item.get(key) or "") for key in key_fields))
    replacement_norm = sorted(replacement_norm, key=lambda item: tuple(str(item.get(key) or "") for key in key_fields))
    return {
        "count_equal": len(redmine_norm) == len(replacement_norm),
        "redmine_only": [
            item
            for item in redmine_norm
            if item not in replacement_norm
        ],
        "replacement_only": [
            item
            for item in replacement_norm
            if item not in redmine_norm
        ],
    }


def command_cutover_parity(args: argparse.Namespace) -> int:
    backend_api = args.api.strip() or replacement_api_base()
    include_closed = bool(args.all)
    include_local = bool(getattr(args, "include_local", False))
    redmine_issues = list_issues_redmine(include_closed=include_closed)
    redmine_by_id = {int(item["id"]): item for item in redmine_issues if str(item.get("id")).isdigit()}
    replacement_issues = replacement_api_issue_list(backend_api, include_closed=include_closed)
    replacement_by_id = {}
    for item in replacement_issues:
        if not isinstance(item, dict):
            continue
        item_payload = item.get("issue", item) if "issue" in item else item
        item_id = item_payload.get("id")
        if item_id is None:
            continue
        issue_id = int(item_id)
        if not include_local and is_replacement_local_issue_id(issue_id):
            continue
        replacement_by_id[issue_id] = _replacement_issue_core(dict(item_payload))

    selected_requested = bool(args.issue)
    selected = [int(i) for i in args.issue or [] if str(i).isdigit()]
    if not selected:
        selected = sorted(redmine_by_id.keys() | replacement_by_id.keys())
        if not include_closed:
            selected = sorted([item["id"] for item in redmine_issues])
    if not include_local:
        selected = [issue_id for issue_id in selected if not is_replacement_local_issue_id(issue_id)]
    selected_set = set(selected)

    baseline_keys = [
        "id",
        "subject",
        "project",
        "tracker",
        "status",
        "done_ratio",
        "dispatch",
        "validation_report",
        "node",
        "agent",
        "role",
        "package",
        "is_closed",
        "updated_on",
    ]
    redmine_id_set = set(redmine_by_id)
    replacement_id_set = set(replacement_by_id)
    if selected_requested:
        redmine_compare_by_id = {issue_id: redmine_by_id[issue_id] for issue_id in sorted(redmine_id_set & selected_set)}
        replacement_compare_by_id = {issue_id: replacement_by_id[issue_id] for issue_id in sorted(replacement_id_set & selected_set)}
    else:
        redmine_compare_by_id = redmine_by_id
        replacement_compare_by_id = replacement_by_id
    list_diffs = compare_record_lists(redmine_compare_by_id, replacement_compare_by_id, baseline_keys)
    coverage_redmine_id_set = set(redmine_compare_by_id)
    coverage_replacement_id_set = set(replacement_compare_by_id)
    missing_in_redmine = coverage_replacement_id_set - coverage_redmine_id_set
    if include_local:
        missing_in_redmine = {issue_id for issue_id in missing_in_redmine if not is_replacement_local_issue_id(issue_id)}
    list_coverage = {
        "missing_in_replacement": sorted(coverage_redmine_id_set - coverage_replacement_id_set),
        "missing_in_redmine": sorted(missing_in_redmine),
        "extra_in_replacement": sorted(missing_in_redmine),
    }

    detail_results: list[dict[str, Any]] = []
    for issue_id in selected:
        result: dict[str, Any] = {"issue_id": issue_id}
        redmine_item = redmine_by_id.get(issue_id)
        replacement_item = replacement_by_id.get(issue_id)
        if not include_local and not redmine_item and replacement_item:
            result.update({"status": "skipped", "reason": "replacement-local issue excluded from migration parity"})
            detail_results.append(result)
            continue
        if include_local and is_replacement_local_issue_id(issue_id) and not redmine_item and replacement_item:
            rep_payload = replacement_api_issue_detail(backend_api, issue_id)
            replacement_detail = rep_payload.get("issue", rep_payload)
            result.update(
                {
                    "status": "pass",
                    "scope": "replacement-local",
                    "replacement_status": replacement_detail.get("status"),
                    "replacement_updated_on": replacement_detail.get("updated_on"),
                }
            )
            detail_results.append(result)
            continue
        if not redmine_item:
            result.update({"status": "fail", "error": "missing in redmine list"})
            detail_results.append(result)
            continue
        if not replacement_item:
            result.update({"status": "fail", "error": "missing in replacement list"})
            detail_results.append(result)
            continue
        rep_payload = replacement_api_issue_detail(backend_api, issue_id)
        replacement_detail = rep_payload.get("issue", rep_payload)
        replacement_journals = rep_payload.get("journals", [])
        replacement_attachments = rep_payload.get("attachments", [])
        redmine_detail = redmine_issue_detail(issue_id)
        redmine_journals = redmine_detail.get("journals", [])
        redmine_attachments = redmine_detail.get("attachments", [])
        detail_issue_diffs = {}
        for key in baseline_keys:
            replacement_value = replacement_detail.get(key)
            redmine_value = redmine_detail.get(key)
            if str(key) == "is_closed":
                replacement_value = str(replacement_value or "false").strip().lower() in {"1", "true", "yes", "on"}
                redmine_value = bool(redmine_value)
            if str(key) == "validation_report":
                replacement_value = str(replacement_value or "")
                redmine_value = str(redmine_value or "")
            if redmine_value != replacement_value:
                detail_issue_diffs[key] = {"red" + "mine": redmine_value, "replacement": replacement_value}
        journal_seq = compare_sequences(
            redmine_journals or [],
            replacement_journals or [],
            ["author", "created_on", "notes", "old_status", "new_status"],
        )
        attachment_seq = compare_sequences(
            redmine_attachments or [],
            replacement_attachments or [],
            ["filename", "size", "path", "created_on"],
        )
        result.update(
            {
                "status": "pass"
                if not detail_issue_diffs and journal_seq["count_equal"] and attachment_seq["count_equal"]
                else "fail",
                "differences": detail_issue_diffs,
                "journal_check": journal_seq,
                "attachment_check": attachment_seq,
            }
        )
        detail_results.append(result)

    list_ok = (
        not list_coverage["missing_in_replacement"]
        and not list_coverage["missing_in_redmine"]
        and all(item["status"] == "pass" for item in list_diffs)
    )
    detail_ok = all(item.get("status") in {"pass", "skipped"} for item in detail_results)
    payload = {
        "generated_at": now_iso(),
        "api": backend_api,
        "include_closed": include_closed,
        "include_local": include_local,
        "list": {
            "redmine_count": len(redmine_by_id),
            "replacement_count": len(replacement_by_id),
            "comparisons": list_diffs,
            "coverage": list_coverage,
            "status": "pass" if list_ok else "fail",
        },
        "details": {
            "issues": selected,
            "comparisons": detail_results,
            "status": "pass" if detail_ok else "fail",
        },
    }
    payload["status"] = "pass" if list_ok and detail_ok else "fail"

    run_dir = resolve_root_path(args.run_dir or "workspace/runs/agent-work/cutover")
    run_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = run_dir / "cutover-parity-report.json"
    report_md_path = run_dir / "cutover-parity-report.md"
    report_json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

    summary_lines = [
        f"# Cutover Parity Report for Agent Work",
        f"Generated: {payload['generated_at']}",
        f"Status: **{payload['status'].upper()}**",
        f"Replacement API: `{backend_api}`",
        "",
        "## List parity",
        f"- Archive count: {payload['list']['redmine_count']}",
        f"- Replacement count: {payload['list']['replacement_count']}",
        f"- Missing in replacement: {len(list_coverage['missing_in_replacement'])}",
        f"- Missing in redmine: {len(list_coverage['missing_in_redmine'])}",
        "",
        "## Detail parity",
        f"- Issues checked: {len(detail_results)}",
        f"- Failures: {len([item for item in detail_results if item.get('status') != 'pass'])}",
    ]
    if list_coverage["missing_in_replacement"] or list_coverage["missing_in_redmine"]:
        summary_lines.append(f"- Missing set (redmine-only): {list_coverage['missing_in_replacement'] or 'none'}")
        summary_lines.append(f"- Missing set (replacement-only): {list_coverage['missing_in_redmine'] or 'none'}")
    report_md_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"cutover report: {display_path(report_json_path)}")
        print(f"cutover report md: {display_path(report_md_path)}")
        print(f"status: {payload['status'].upper()}")
    return 0 if payload["status"] == "pass" else 1


def command_backup(args: argparse.Namespace) -> int:
    db_path = Path(args.db or replacement_db_path())
    run_dir = cutover_root(args.run_dir or CUTOVER_BACKUP_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    bundle = build_backup_bundle(db_path, run_dir=run_dir)
    state = load_cutover_state()
    state["last_backup"] = display_path(bundle["bundle_dir"])
    save_cutover_state(state)
    payload = {
        "bundle_dir": display_path(bundle["bundle_dir"]),
        "backup_db": display_path(bundle["backup_db"]),
        "manifest": bundle["manifest"],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(f"backup bundle: {payload['bundle_dir']}")
        print(f"backup db: {payload['backup_db']}")
        print(f"manifest: {display_path(bundle['bundle_dir'] / 'backup-manifest.json')}")
    return 0


def command_restore(args: argparse.Namespace) -> int:
    bundle_dir = cutover_root(args.bundle)
    target_db = Path(args.db or (cutover_root(args.run_dir or CUTOVER_RUN_ROOT) / "restored-agent-work.sqlite3"))
    if args.verify:
        result = verify_restored_bundle(bundle_dir, target_db)
    else:
        result = restore_backup_bundle(bundle_dir, target_db)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(f"restored db: {result['restored']['target_db'] if 'restored' in result else display_path(target_db)}")
        print(f"bundle: {display_path(bundle_dir)}")
        if args.verify and isinstance(result, dict) and "contracts" in result:
            print(f"health: {json.dumps(result['health'], sort_keys=True, default=str)}")
            print(f"contracts: {json.dumps(result['contracts'], sort_keys=True, default=str)}")
    return 0


def command_archive(args: argparse.Namespace) -> int:
    db_path = Path(args.db or replacement_db_path())
    bundle_dir = cutover_root(args.run_dir or CUTOVER_ARCHIVE_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    issues = list_issues_replacement(include_closed=True)
    selected_ids = [int(item) for item in args.issue or [] if str(item).isdigit()]
    if selected_ids:
        issues = [item for item in issues if int(item["id"]) in selected_ids]
    elif args.limit:
        issues = issues[: max(0, int(args.limit))]
    index_rows, archive_dir = archive_issue_index(issues, bundle_dir)
    matches = search_archive_entries(index_rows, args.query or "")
    archive_index_path = archive_dir / "index.json"
    search_path = archive_dir / "search.json"
    search_path.write_text(json.dumps(matches, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    state = load_cutover_state()
    state["last_archive_export"] = display_path(bundle_dir)
    save_cutover_state(state)
    payload = {
        "bundle_dir": display_path(bundle_dir),
        "archive_dir": display_path(archive_dir),
        "index": display_path(archive_index_path),
        "search": display_path(search_path),
        "query": args.query or "",
        "match_count": len(matches),
        "issue_count": len(index_rows),
        "db": str(db_path),
    }
    archive_html = archive_dir / "archive.html"
    archive_html.write_text(
        "\n".join(
            [
                "<html><body>",
                "<h1>Cento Taskstream Archive</h1>",
                f"<p>Issues exported: {len(index_rows)}</p>",
                f"<p>Matches: {len(matches)}</p>",
                "<ul>",
                *[
                    f"<li><a href=\"{row['html']}\">#{row['id']} {row['subject']}</a></li>"
                    for row in matches
                ],
                "</ul>",
                "</body></html>",
            ]
        ),
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(f"archive bundle: {payload['bundle_dir']}")
        print(f"archive html: {display_path(archive_html)}")
        print(f"matches: {payload['match_count']}")
    return 0


def command_cutover_status(args: argparse.Namespace) -> int:
    state = load_cutover_state(args.run_dir)
    report = {
        "generated_at": now_iso(),
        "state": state,
        "write_target": cutover_write_target(state),
        "counts": cutover_counts(),
        "rollback": cutover_rollback_steps(state),
        "blockers": list(state.get("blockers") or []),
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(f"write target: {report['write_target']}")
        print(f"frozen: {bool(state.get('frozen'))}")
        print(f"finalized: {bool(state.get('finalized'))}")
        print(f"counts: {json.dumps(report['counts'], sort_keys=True, default=str)}")
        print(f"blockers: {json.dumps(report['blockers'], sort_keys=True, default=str)}")
        print("rollback:")
        for item in report["rollback"]:
            print(f"- {item}")
    return 0


def command_cutover_freeze(args: argparse.Namespace) -> int:
    state = load_cutover_state(args.run_dir)
    if state.get("finalized"):
        raise AgentWorkError("Cutover is already finalized.")
    state["frozen"] = True
    state["frozen_at"] = now_iso()
    state["write_target"] = cutover_write_target(state)
    if args.note:
        state.setdefault("notes", []).append(args.note)
    path = save_cutover_state(state)
    if args.run_dir:
        save_cutover_state(state, args.run_dir)
    if args.json:
        print(json.dumps({"cutover_state": state, "path": display_path(path)}, indent=2, sort_keys=True, default=str))
    else:
        print(f"freeze recorded: {display_path(path)}")
        print(f"write target: {state['write_target']}")
    return 0


def command_cutover_verify(args: argparse.Namespace) -> int:
    run_dir = cutover_root(args.run_dir or CUTOVER_RUN_ROOT / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    run_dir.mkdir(parents=True, exist_ok=True)
    state = load_cutover_state(run_dir)
    backup_bundle = build_backup_bundle(Path(args.db or replacement_db_path()), run_dir=run_dir / "backup")
    restore_target = Path(args.restore_db or (run_dir / "restore.sqlite3"))
    restore_report = verify_restored_bundle(backup_bundle["bundle_dir"], restore_target)
    archive_bundle = run_dir
    archive_issues = list_issues_replacement(include_closed=True)
    selected_ids = [int(item) for item in args.issue or [] if str(item).isdigit()]
    if selected_ids:
        archive_issues = [item for item in archive_issues if int(item["id"]) in selected_ids]
    elif args.limit:
        archive_issues = archive_issues[: max(0, int(args.limit))]
    index_rows, archive_dir = archive_issue_index(archive_issues, archive_bundle)
    archive_matches = search_archive_entries(index_rows, args.query or "")
    (archive_dir / "search.json").write_text(json.dumps(archive_matches, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    archive_payload = {
        "bundle_dir": display_path(archive_bundle),
        "archive_dir": display_path(archive_dir),
        "index": display_path(archive_dir / "index.json"),
        "search": display_path(archive_dir / "search.json"),
        "match_count": len(archive_matches),
        "issue_count": len(index_rows),
    }
    report = {
        "generated_at": now_iso(),
        "write_target": cutover_write_target(state),
        "counts": cutover_counts(),
        "state": state,
        "backup": backup_bundle["manifest"],
        "restore": restore_report,
        "archive": archive_payload,
        "blockers": list(state.get("blockers") or []),
        "rollback": cutover_rollback_steps(state),
        "status": "pass",
    }
    if not restore_report["contracts"]["issue_list_ok"] or not restore_report["contracts"]["sample_detail_ok"]:
        report["status"] = "fail"
        report["blockers"] = report["blockers"] + ["Restored DB failed contract checks."]
    state["last_backup"] = display_path(backup_bundle["bundle_dir"])
    state["last_verified_at"] = report["generated_at"]
    state["last_archive_export"] = archive_payload["bundle_dir"]
    state["write_target"] = cutover_write_target(state)
    state["blockers"] = report["blockers"]
    save_cutover_state(state)
    save_cutover_state(state, run_dir)
    report_path = run_dir / "cutover-verify.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    report_md = run_dir / "cutover-verify.md"
    report_md.write_text(
        "\n".join(
            [
                "# Cutover Verify",
                f"Status: **{report['status'].upper()}**",
                f"Write target: `{report['write_target']}`",
                f"Counts: `{json.dumps(report['counts'], sort_keys=True, default=str)}`",
                f"Backup bundle: `{display_path(backup_bundle['bundle_dir'])}`",
                f"Restore target: `{display_path(restore_target)}`",
                f"Archive bundle: `{archive_payload['bundle_dir']}`",
                "",
                "## Blockers",
                *([f"- {item}" for item in report["blockers"]] or ["- none"]),
                "",
                "## Rollback",
                *[f"- {item}" for item in report["rollback"]],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(f"write target: {report['write_target']}")
        print(f"counts: {json.dumps(report['counts'], sort_keys=True, default=str)}")
        print(f"blockers: {json.dumps(report['blockers'], sort_keys=True, default=str)}")
        print(f"rollback: {json.dumps(report['rollback'], sort_keys=True, default=str)}")
        print(f"report: {display_path(report_path)}")
        print(f"report md: {display_path(report_md)}")
    return 0 if report["status"] == "pass" else 1


def command_cutover_finalize(args: argparse.Namespace) -> int:
    state = load_cutover_state(args.run_dir)
    if not state.get("frozen"):
        raise AgentWorkError("Cutover must be frozen before finalization.")
    if not state.get("last_verified_at") and not args.force:
        raise AgentWorkError("Cutover must be verified before finalization. Use --force to override.")
    state["finalized"] = True
    state["finalized_at"] = now_iso()
    state["write_target"] = BACKEND_REPLACEMENT
    state["blockers"] = []
    if args.note:
        state.setdefault("notes", []).append(args.note)
    path = save_cutover_state(state)
    if args.run_dir:
        save_cutover_state(state, args.run_dir)
    if args.json:
        print(json.dumps({"cutover_state": state, "path": display_path(path)}, indent=2, sort_keys=True, default=str))
    else:
        print(f"finalized: {display_path(path)}")
        print("write target: replacement")
        print("rollback: restore the replacement backup bundle; legacy migration writes stay disabled.")
    return 0


def command_show(args: argparse.Namespace) -> int:
    issue = show_issue(args.issue)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"#{issue['id']} {issue['subject']}")
        print(f"status: {issue['status']}  node: {issue.get('node') or '-'}  role: {issue.get('role') or '-'}  agent: {issue.get('agent') or '-'}  package: {issue.get('package') or '-'}")
        print()
        print(issue.get("description") or "")
    return 0


def command_claim(args: argparse.Namespace) -> int:
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "agent"
    role = normalize_role(args.role)
    issue = update_issue(args.issue, "running", args.note or f"Claimed by {agent} on {node} as {role}.", node, agent, None, role=role)
    print(f"claimed #{issue['id']} on {node} as {agent} ({role})")
    return 0


def command_update(args: argparse.Namespace) -> int:
    issue = update_issue(args.issue, args.status, args.note or "", args.node, args.agent, None, role=args.role)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"updated #{issue['id']}: {issue['status']}")
    return 0


def validation_note(result: str, note: str, evidence: list[str]) -> str:
    validation_items, screenshot_items = partition_evidence(evidence)
    section_notes = review_sections_from_note(note, ["Delivered", "Validation", "Evidence", "Residual risk"])
    delivered = section_notes.get("delivered", "").strip()
    validation_text = section_notes.get("validation", "").strip()
    evidence_text = section_notes.get("evidence", "").strip()
    residual = section_notes.get("residual risk", "").strip()

    validation_lines = (
        _as_note_bullets(_coerce_section_lines(validation_text), default="Validation performed and recorded in Cento notes.")
        if validation_text
        else (
            _as_note_bullets(_coerce_section_lines(note), default="Validation performed and recorded in Cento notes.")
            if note.strip()
            else ["* Validation note not provided."]
        )
    )
    delivered_lines = _as_note_bullets(
        _coerce_section_lines(delivered),
        default="Validation evidence was prepared for reviewer handoff.",
    )

    evidence_lines = ["* Validation evidence:"]
    if validation_items:
        evidence_lines.extend(f"*  - @{item}@" for item in validation_items)
    else:
        evidence_lines.append("*  - None")
    evidence_lines.append("* Screenshot evidence:")
    if screenshot_items:
        evidence_lines.extend(f"*  - @{item}@" for item in screenshot_items)
    else:
        evidence_lines.append("*  - None")
    if evidence_text:
        evidence_lines.extend(
            f"* {line}"
            for line in _coerce_section_lines(evidence_text)
            if line not in {"Validation evidence:", "Screenshot evidence:"}
        )
    residual_lines = _as_note_bullets(
        _coerce_section_lines(residual),
        default="None.",
    )
    result_label = result.upper()
    return textwrap.dedent(
        f"""\
        h3. Validator {result_label}

        *Delivered*
{_render_section_body(delivered_lines)}

        *Validation*
{_render_section_body(validation_lines)}

        *Evidence*
{_render_section_body(evidence_lines)}

        *Residual risk*
{_render_section_body(residual_lines)}
        """
    )


def _coerce_section_lines(value: str) -> list[str]:
    return [str(line).strip() for line in str(value or "").splitlines() if str(line).strip()]


def _as_note_bullets(lines: list[str], default: str) -> list[str]:
    if lines:
        return [f"* {line.lstrip('* ').rstrip()}" for line in lines]
    return [f"* {default}"]


def partition_evidence(values: list[str]) -> tuple[list[str], list[str]]:
    validation_paths: list[str] = []
    screenshot_paths: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        value_norm = normalize_evidence_entry(value)
        if not value_norm or value_norm in seen:
            continue
        seen.add(value_norm)
        if value_norm.startswith("http://") or value_norm.startswith("https://"):
            validation_paths.append(value_norm)
            continue
        target = _resolve_local_evidence_path(value_norm)
        is_screenshot = False
        if target and target.suffix.lower() in SCREENSHOT_EVIDENCE_SUFFIXES:
            is_screenshot = True
        if not is_screenshot and "screenshot" in value_norm.lower():
            is_screenshot = True
        if is_screenshot:
            screenshot_paths.append(value_norm)
        else:
            validation_paths.append(value_norm)
    return validation_paths, screenshot_paths


def _render_section_body(lines: list[str]) -> str:
    return "\n".join([line for line in lines]) if lines else "* None."


def validation_check_lines(checks: list[dict[str, Any]]) -> list[str]:
    if not checks:
        return []
    lines: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        status = "PASS" if item.get("ok") else "FAIL"
        name = item.get("name") or "check"
        message = item.get("message") or ""
        check_type = item.get("type") or "command"
        details = f"{status} {name} ({check_type})"
        if message:
            details = f"{details}: {message}"
        lines.append(details)
    return lines


def append_validation_summary(note: str, checks: list[dict[str, Any]]) -> str:
    lines = validation_check_lines(checks)
    if not lines:
        return note
    summary = "\n".join(f"* {line}" for line in lines)
    note_text = note.strip()
    if note_text:
        return f"{note_text}\nValidation checks:\n{summary}"
    return f"Validation checks:\n{summary}"


def review_summary_path(issue_id: int) -> Path:
    return ROOT / "workspace" / "runs" / "agent-work" / str(issue_id) / "review-summary.json"


def review_summary_evidence_type(path: str) -> str:
    value = str(path or "").strip().lower()
    if value.startswith(("http://", "https://")):
        return "url"
    suffix = Path(value).suffix
    if suffix in SCREENSHOT_EVIDENCE_SUFFIXES or "screenshot" in value:
        return "screenshot"
    if suffix in {".mp4", ".webm", ".mov"} or "video" in value:
        return "video"
    if suffix in {".log", ".txt"} or "log" in value:
        return "log"
    if suffix in {".json", ".ndjson"}:
        return "json"
    if suffix in {".md", ".markdown"} or "report" in value:
        return "report"
    return "artifact"


def review_summary_recommended_action(result: str) -> str:
    result_norm = str(result or "").lower()
    if result_norm == "pass":
        return "Approve"
    if result_norm == "blocked":
        return "Resolve blocker"
    return "Needs Fix"


def review_summary_text(result: str, checks: list[dict[str, Any]], gate_failures: list[str]) -> str:
    result_norm = str(result or "").lower()
    if gate_failures:
        return f"Validation needs another pass: the review gate found {len(gate_failures)} issue(s)."
    if checks:
        total = len(checks)
        passed = sum(1 for item in checks if item.get("ok"))
        if result_norm == "pass":
            return f"Validation passed: {passed}/{total} checks passed."
        if result_norm == "blocked":
            return f"Validation blocked: {passed}/{total} checks passed before the blocker."
        return f"Validation failed: {passed}/{total} checks passed."
    if result_norm == "pass":
        return "Validation passed."
    if result_norm == "blocked":
        return "Validation is blocked."
    return "Validation failed."


def build_review_summary(
    *,
    issue_id: int,
    subject: str,
    result: str,
    final_result: str,
    checks: list[dict[str, Any]],
    evidence: list[str],
    agent: str,
    node: str,
    gate_failures: list[str],
    note: str,
) -> dict[str, Any]:
    normalized_checks = []
    for item in checks or []:
        if not isinstance(item, dict):
            continue
        normalized_checks.append(
            {
                "name": str(item.get("name") or "check"),
                "status": "passed" if item.get("ok") else "failed",
                "detail": str(item.get("message") or ""),
                "type": str(item.get("type") or "command"),
            }
        )
    normalized_evidence = []
    seen: set[str] = set()
    for item in evidence or []:
        clean = normalize_evidence_entry(str(item or ""))
        if not clean or clean in seen:
            continue
        seen.add(clean)
        normalized_evidence.append({"type": review_summary_evidence_type(clean), "path": clean})
    return {
        "schema": "cento.review-summary.v1",
        "issue": {"id": issue_id, "subject": subject or ""},
        "result": result,
        "result_after_gate": final_result,
        "summary": review_summary_text(final_result, checks, gate_failures),
        "checks": normalized_checks,
        "evidence": normalized_evidence,
        "recommended_action": review_summary_recommended_action(final_result),
        "review_gate_failures": gate_failures,
        "note": str(note or "").strip(),
        "agent": agent,
        "node": node,
        "updated_at": now_iso(),
    }


def write_review_summary(issue_id: int, payload: dict[str, Any]) -> str:
    path = review_summary_path(issue_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return display_path(path)


def command_validate(args: argparse.Namespace) -> int:
    require_replacement_backend("validate")
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "validator"
    enforce_validator_authorized(agent)
    issue_snapshot = show_issue(args.issue)
    result = args.result.lower()
    story_payload = None
    story_manifest = None
    if args.story_manifest:
        story_manifest = resolve_root_path(args.story_manifest)
        story_payload = load_story_manifest(story_manifest)
    gate_failures = validate_review_gate(
        note=args.note or "",
        evidence=args.evidence or [],
        checks=None,
        story=story_payload,
    )
    final_result = result
    status = "review" if result == "pass" else "blocked"
    if result == "pass" and gate_failures:
        final_result = "fail"
        status = "blocked"
        for item in gate_failures:
            print(f"[agent-work-review-gate] {item}", file=sys.stderr)
    note = validation_note(final_result, args.note or "", args.evidence or [])
    note += review_gate_feedback_block(gate_failures)
    summary_payload = build_review_summary(
        issue_id=args.issue,
        subject=str(issue_snapshot.get("subject") or ""),
        result=result,
        final_result=final_result,
        checks=[],
        evidence=args.evidence or [],
        agent=agent,
        node=node,
        gate_failures=gate_failures,
        note=args.note or "",
    )
    summary_path = write_review_summary(args.issue, summary_payload)
    all_evidence = [*(args.evidence or []), summary_path]
    report = json.dumps(
        {
            "result": result,
            "result_after_gate": final_result,
            "agent": agent,
            "node": node,
            "story_manifest": str(story_manifest or ""),
            "review_gate_failures": gate_failures,
            "evidence": all_evidence,
            "review_summary": summary_path,
            "updated_at": now_iso(),
        },
        sort_keys=True,
    )
    issue = update_issue(args.issue, status, note, node, agent, None, role="validator", validation_report=report)
    if args.json:
        print(json.dumps(issue, indent=2, default=str))
    else:
        print(f"validated #{issue['id']}: {final_result.upper()} -> {issue['status']}")
    return 0 if final_result == "pass" else 1


def builder_report_text(args: argparse.Namespace, output: Path) -> str:
    lines = [
        f"# Builder Handoff For #{args.issue}",
        "",
        f"Generated: {now_iso()}",
        f"Agent: {args.agent or os.environ.get('USER') or 'builder'}",
        f"Node: {args.node or current_node()}",
        "",
        "## Summary",
        "",
        args.summary.strip() or "No summary provided.",
        "",
        "## Changed Files",
        "",
    ]
    if args.changed_file:
        lines.extend(f"- `{item}`" for item in args.changed_file)
    else:
        lines.append("- None listed.")
    lines.extend(["", "## Commands Run", ""])
    if args.command:
        lines.extend(f"- `{item}`" for item in args.command)
    else:
        lines.append("- None listed.")
    lines.extend(["", "## Evidence", ""])
    if args.evidence:
        lines.extend(f"- `{item}`" for item in args.evidence)
    else:
        lines.append("- None listed.")
    lines.extend(["", "## Risks / Limitations", ""])
    if args.risk:
        lines.extend(f"- {item}" for item in args.risk)
    else:
        lines.append("- None listed.")
    lines.extend(["", "## Validator Handoff", ""])
    if args.manifest:
        lines.append(f"- Manifest: `{args.manifest}`")
    lines.append(f"- Builder report: `{display_path(output)}`")
    return "\n".join(lines) + "\n"


def command_handoff(args: argparse.Namespace) -> int:
    require_replacement_backend("handoff")
    run_dir = resolve_root_path(args.run_dir or f"workspace/runs/agent-work/{args.issue}")
    run_dir.mkdir(parents=True, exist_ok=True)
    output = resolve_root_path(args.output) if args.output else run_dir / "builder-report.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(builder_report_text(args, output), encoding="utf-8")
    evidence = list(args.evidence or [])
    evidence.append(display_path(output))
    note = args.note or f"Builder handoff ready. Report: {display_path(output)}"
    issue = update_issue(args.issue, "validating", note, args.node or current_node(), args.agent or os.environ.get("USER") or "builder", None, role="builder")
    print(f"handoff #{issue['id']}: {issue['status']} report={display_path(output)}")
    if args.dispatch_validator:
        dispatch_args = argparse.Namespace(
            issue=args.issue,
            node=args.validator_node or "",
            agent=args.validator_agent or "",
            role="validator",
            runtime=args.validator_runtime or "auto",
            model=args.validator_model or "",
            dry_run=args.validator_dry_run,
            validation_manifest="",
            min_automation_coverage=95.0,
            skip_preflight=False,
        )
        command_dispatch(dispatch_args)
    return 0


def review_drain_command_line(packages: list[str], status: str, *, apply: bool, note: str, json_output: bool) -> str:
    parts = ["cento", "agent-work", "review-drain"]
    for package in packages:
        parts.extend(["--package", package])
    parts.extend(["--status", status])
    if note:
        parts.extend(["--note", note])
    parts.append("--apply" if apply else "--dry-run")
    if json_output:
        parts.append("--json")
    return shlex.join(parts)


def review_drain_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Review Drain Report",
        "",
        f"Generated: {payload['generated_at']}",
        f"Command: `{payload['command_line']}`",
        f"Node: {payload['node']}",
        f"Agent: {payload['agent']}",
        f"Mode: {'Apply' if payload['apply'] else 'Dry run'}",
        "",
        "## Filters",
        "",
        f"- Status: `{payload['status']}`",
    ]
    packages = payload.get("packages") or []
    if packages:
        lines.append(f"- Packages: {', '.join(f'`{item}`' for item in packages)}")
    else:
        lines.append("- Packages: none")
    lines.extend(
        [
            "",
            "## Matching Issues",
            "",
        ]
    )
    matches = payload.get("matches") or []
    if matches:
        for item in matches:
            action = "Would close" if item.get("dry_run") else "Closed"
            lines.append(
                f"- #{item['id']} `{item['status']}` `{item['package'] or '-'}` {action}: {item['subject']}"
            )
    else:
        lines.append("- No matching Review items.")
    skipped = payload.get("skipped") or []
    if skipped:
        lines.extend(["", "## Skipped", ""])
        for item in skipped:
            lines.append(
                f"- #{item['id']} `{item['status']}` `{item['package'] or '-'}` skipped: {item['reason']}"
            )
    failures = payload.get("failures") or []
    if failures:
        lines.extend(["", "## Failures", ""])
        for item in failures:
            lines.append(f"- #{item['id']}: {item['error']}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Markdown report: `{payload['report_path']}`",
            f"- JSON report: `{payload['json_path']}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def compact_issue_record(issue: dict[str, Any], *, reason: str = "") -> dict[str, Any]:
    record = {
        "id": int(issue["id"]),
        "subject": str(issue.get("subject") or ""),
        "status": str(issue.get("status") or ""),
        "package": str(issue.get("package") or ""),
        "node": str(issue.get("node") or ""),
        "agent": str(issue.get("agent") or ""),
        "role": str(issue.get("role") or ""),
        "done_ratio": int(issue.get("done_ratio") or 0),
        "updated_on": str(issue.get("updated_on") or ""),
        "link": replacement_issue_link(int(issue["id"])),
    }
    if reason:
        record["reason"] = reason
    return record


def issue_journal_latest_note(issue: dict[str, Any]) -> str:
    journals = issue.get("journals") or []
    if not isinstance(journals, list):
        return ""
    for journal in journals:
        if not isinstance(journal, dict):
            continue
        note = str(journal.get("notes") or "").strip()
        if note:
            return note
    return ""


def blocker_keywords(text: str) -> set[str]:
    lowered = text.lower()
    keywords: set[str] = set()
    for token in [
        "blocked because",
        "waiting on",
        "waiting for",
        "dependency",
        "dependencies",
        "missing evidence",
        "evidence",
        "validation",
        "review",
        "docs",
        "documentation",
        "story.json",
        "deliverables",
        "split",
        "separate",
        "smaller",
        "device",
        "simulator",
        "credential",
        "credentials",
        "access",
        "human",
        "lan",
        "credentials",
        "requeue",
    ]:
        if token in lowered:
            keywords.add(token)
    return keywords


def classify_blocker(issue: dict[str, Any]) -> dict[str, Any]:
    note = issue_journal_latest_note(issue)
    description = str(issue.get("description") or "")
    text = "\n".join(part for part in [note, description] if part).strip()
    dispatch = str(issue.get("dispatch") or "")
    keywords = blocker_keywords(text)
    cause = "unknown"
    summary = note or description or "No blocker note recorded."
    safe_action = ""
    follow_up = ""
    follow_up_description = ""

    if "gpt-5.3-codex-spark" in dispatch:
        cause = "stale-dispatch"
        summary = note or "Blocked by a stale Spark dispatch."
        safe_action = (
            f"cento agent-work update {issue['id']} --status queued --role "
            f"{shlex.quote(str(issue.get('role') or 'builder') or 'builder')} --note "
            f"{shlex.quote('Old Spark dispatch can be requeued after board recovery.')}"
        )
    elif {"device", "simulator", "credential", "credentials", "access", "lan", "human"} & keywords:
        cause = "external-blocker"
        safe_action = ""
    elif {"split", "separate", "smaller"} & keywords:
        cause = "split-needed"
        follow_up = f"Follow-up for #{issue['id']}: {issue.get('subject') or 'blocked story'}"
        follow_up_description = (
            f"Create a smaller follow-up task for issue #{issue['id']} because the blocker indicates "
            f"the story should be split or narrowed.\n\n"
            f"Original issue: #{issue['id']} {issue.get('subject') or ''}\n"
            f"Blocker note: {summary}\n"
            "Use this follow-up only if the current issue is too broad for a single bounded recovery step."
        )
        safe_action = ""
    elif {"evidence", "validation", "docs", "documentation", "story.json", "deliverables"} & keywords:
        cause = "internal-artifact-gap"
        follow_up = f"Follow-up for #{issue['id']}: {issue.get('subject') or 'artifact gap'}"
        follow_up_description = (
            f"Create a narrow follow-up task that closes the blocker for issue #{issue['id']}.\n\n"
            f"Original issue: #{issue['id']} {issue.get('subject') or ''}\n"
            f"Blocker note: {summary}\n"
            "This follow-up is only appropriate when the missing artifact is a bounded Cento task "
            "(for example, a validation artifact, story manifest, or recovery evidence bundle)."
        )
        safe_action = ""
    elif {"blocked because", "waiting on", "waiting for", "dependency", "dependencies"} & keywords:
        cause = "dependency-blocker"
        safe_action = ""
    else:
        cause = "general-blocker"

    if not summary:
        summary = "Blocked with no recorded note."

    return {
        "id": int(issue["id"]),
        "subject": str(issue.get("subject") or ""),
        "package": str(issue.get("package") or ""),
        "role": str(issue.get("role") or "builder") or "builder",
        "cause": cause,
        "summary": summary,
        "note": note,
        "dispatch": dispatch,
        "safe_action": safe_action,
        "follow_up_title": follow_up,
        "follow_up_description": follow_up_description,
    }


def board_snapshot(issues: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "open_count": len(issues),
        "status_counts": status_counts(issues),
        "package_counts": package_counts(issues),
        "queued_count": sum(1 for item in issues if str(item.get("status") or "").strip().lower() == "queued"),
        "running_count": sum(1 for item in issues if str(item.get("status") or "").strip().lower() == "running"),
        "validating_count": sum(1 for item in issues if str(item.get("status") or "").strip().lower() == "validating"),
        "review_count": sum(1 for item in issues if str(item.get("status") or "").strip().lower() == "review"),
        "blocked_count": sum(1 for item in issues if str(item.get("status") or "").strip().lower() == "blocked"),
    }


def project_board_snapshot(
    snapshot: dict[str, Any],
    *,
    requeued: int = 0,
    follow_ups: int = 0,
    follow_up_packages: list[str] | None = None,
) -> dict[str, Any]:
    projected = dict(snapshot)
    status_counts_map = dict(projected.get("status_counts") or {})
    status_counts_map["Blocked"] = max(0, int(status_counts_map.get("Blocked", 0)) - requeued)
    status_counts_map["Queued"] = int(status_counts_map.get("Queued", 0)) + requeued + follow_ups
    projected["status_counts"] = dict(sorted(status_counts_map.items(), key=lambda pair: pair[0].lower()))
    projected["queued_count"] = int(projected.get("queued_count") or 0) + requeued + follow_ups
    projected["blocked_count"] = max(0, int(projected.get("blocked_count") or 0) - requeued)
    projected["open_count"] = int(projected.get("open_count") or 0) + follow_ups
    package_counts_map = dict(projected.get("package_counts") or {})
    for package in follow_up_packages or []:
        package = str(package or "").strip()
        if not package:
            continue
        package_counts_map[package] = int(package_counts_map.get(package, 0)) + 1
    projected["package_counts"] = dict(sorted(package_counts_map.items(), key=lambda pair: (-pair[1], pair[0])))
    return projected


def recovery_plan_issue_detail(issue_id: int) -> dict[str, Any]:
    detail = show_issue_replacement(issue_id)
    detail["journals"] = []
    detail["attachments"] = []
    return detail


def compact_run_record(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": str(run.get("run_id") or ""),
        "issue_id": run.get("issue_id"),
        "issue_subject": str(run.get("issue_subject") or ""),
        "status": str(run.get("status") or ""),
        "health": str(run.get("health") or ""),
        "node": str(run.get("node") or ""),
        "agent": str(run.get("agent") or ""),
        "role": str(run.get("role") or ""),
        "runtime": str(run.get("runtime") or ""),
        "pid": run.get("pid"),
        "child_pid": run.get("child_pid"),
        "tmux_session": str(run.get("tmux_session") or ""),
        "command": str(run.get("command") or ""),
        "source": str(run.get("source") or ""),
        "log_path": str(run.get("log_path") or ""),
    }


def status_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in items:
        status = str(item.get("status") or "").strip()
        if status:
            counts[status] += 1
    return dict(sorted(counts.items(), key=lambda pair: pair[0].lower()))


def package_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter()
    for item in items:
        package = str(item.get("package") or "").strip()
        if package:
            counts[package] += 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def recovery_plan_command_line(args: argparse.Namespace) -> str:
    parts = ["cento", "agent-work", "recovery-plan"]
    if args.json:
        parts.append("--json")
    if args.apply:
        parts.append("--apply")
    if args.run_dir:
        parts.extend(["--run-dir", args.run_dir])
    if args.node:
        parts.extend(["--node", args.node])
    if args.agent:
        parts.extend(["--agent", args.agent])
    return shlex.join(parts)


def recovery_plan_report_markdown(payload: dict[str, Any]) -> str:
    board_before = (payload.get("board") or {}).get("before") or {}
    board_after = (payload.get("board") or {}).get("after") or {}
    review = payload.get("review") or {}
    runs = payload.get("runs") or {}
    commands = payload.get("commands") or []
    lines = [
        "# Recovery Plan",
        "",
        f"Generated: {payload['generated_at']}",
        f"Command: `{payload['command_line']}`",
        f"Node: {payload['node']}",
        f"Agent: {payload['agent']}",
        f"Run dir: `{payload['run_dir']}`",
        f"Mode: `{payload.get('mode') or 'report-only'}`",
        "",
        "## Before Snapshot",
        "",
        f"- Open issues: `{board_before.get('open_count', 0)}`",
        f"- Status counts: `{json.dumps(board_before.get('status_counts', {}), sort_keys=True)}`",
        f"- Package counts: `{json.dumps(board_before.get('package_counts', {}), sort_keys=True)}`",
        f"- Tracked active runs: `{runs.get('tracked_active', 0)}`",
        f"- Stale runs: `{runs.get('stale', 0)}`",
        f"- Manual interactive shells: `{runs.get('manual', 0)}`",
    ]
    if board_before.get("queued_count", 0):
        lines.append(f"- Queued: `{board_before.get('queued_count', 0)}`")
    if board_before.get("blocked_count", 0):
        lines.append(f"- Blocked: `{board_before.get('blocked_count', 0)}`")
    if board_before.get("review_count", 0):
        lines.append(f"- Review: `{board_before.get('review_count', 0)}`")
    lines.extend(
        [
            "",
            "## After Snapshot",
            "",
            f"- Basis: `{payload.get('after_basis') or 'projected'}`",
            f"- Open issues: `{board_after.get('open_count', 0)}`",
            f"- Status counts: `{json.dumps(board_after.get('status_counts', {}), sort_keys=True)}`",
            f"- Package counts: `{json.dumps(board_after.get('package_counts', {}), sort_keys=True)}`",
        ]
    )
    if board_after.get("queued_count", 0):
        lines.append(f"- Queued: `{board_after.get('queued_count', 0)}`")
    if board_after.get("blocked_count", 0):
        lines.append(f"- Blocked: `{board_after.get('blocked_count', 0)}`")
    if board_after.get("review_count", 0):
        lines.append(f"- Review: `{board_after.get('review_count', 0)}`")
    blocked_causes = payload.get("blocked_causes") or []
    if blocked_causes:
        lines.extend(["", "## Blocked Causes", ""])
        for item in blocked_causes:
            lines.append(
                f"- #{item['id']} `{item['package'] or '-'}`: {item['subject']} "
                f"({item.get('cause') or 'unknown'}) - {item.get('summary') or 'no summary'}"
            )
            if item.get("link"):
                lines.append(f"  - Link: `{item['link']}`")
            if item.get("safe_action"):
                lines.append(f"  - Safe action: `{item['safe_action']}`")
            if item.get("follow_up_title") and item.get("follow_up_description"):
                lines.append(f"  - Follow-up: `{item.get('follow_up_title')}`")
    lines.extend(["", "## Immediate Next Commands", ""])
    if commands:
        for command in commands[:12]:
            lines.append(f"- `{command}`")
    else:
        lines.append("- No recovery commands were generated.")
    ready = review.get("ready") or []
    if ready:
        lines.extend(["", "## Review Drain Candidates", ""])
        for item in ready:
            lines.append(
                f"- #{item['id']} `{item['package'] or '-'}`: {item['subject']} ({item.get('reason') or 'validation pass'})"
            )
            if item.get("link"):
                lines.append(f"  - Link: `{item['link']}`")
    blocked = review.get("needs_evidence") or []
    if blocked:
        lines.extend(["", "## Review Items Needing Evidence", ""])
        for item in blocked:
            lines.append(
                f"- #{item['id']} `{item['package'] or '-'}`: {item['subject']} ({item.get('reason') or 'needs validation'})"
            )
            if item.get("link"):
                lines.append(f"  - Link: `{item['link']}`")
    stale_runs = runs.get("stale_items") or []
    if stale_runs:
        lines.extend(["", "## Stale Runs", ""])
        for item in stale_runs:
            lines.append(
                f"- `{item['run_id']}` issue={item.get('issue_id')} status={item.get('status')} health={item.get('health')} tmux={item.get('tmux_session') or '-'}"
            )
    manual_runs = runs.get("manual_items") or []
    if manual_runs:
        lines.extend(["", "## Manual Interactive Shells", ""])
        for item in manual_runs:
            lines.append(
                f"- pid={item.get('pid')} `{item.get('runtime')}`: `{item.get('command')}`"
            )
    blocked_requeue = payload.get("blocked_requeue") or []
    if blocked_requeue:
        lines.extend(["", "## Requeue Candidates", ""])
        for item in blocked_requeue:
            lines.append(
                f"- #{item['id']} `{item['package'] or '-'}`: {item['subject']} ({item.get('reason') or 'requeue candidate'})"
            )
            if item.get("link"):
                lines.append(f"  - Link: `{item['link']}`")
    follow_up_candidates = payload.get("follow_up_candidates") or []
    if follow_up_candidates:
        lines.extend(["", "## Follow-up Candidates", ""])
        for item in follow_up_candidates:
            lines.append(
                f"- {item['title']} ({item.get('reason') or 'follow-up candidate'})\n"
                f"  `{item['command']}`"
            )
            if item.get("source_issue_id"):
                lines.append(f"  - Source issue: `{replacement_issue_link(int(item['source_issue_id']))}`")
    guardrails = payload.get("guardrails") or []
    if guardrails:
        lines.extend(["", "## Guardrails", ""])
        for item in guardrails:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Markdown report: `{payload['report_path']}`",
            f"- JSON report: `{payload['json_path']}`",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def command_recovery_plan(args: argparse.Namespace) -> int:
    require_replacement_backend("recovery-plan")
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "coordinator"
    run_id = f"recovery-plan-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = resolve_root_path(args.run_dir or f"workspace/runs/agent-work/recovery-plan/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)

    issues_before = list_issues_replacement(include_closed=False)
    runs = agent_run_records(include_untracked=True, reconcile=False)

    active_runs = [
        compact_run_record(run)
        for run in runs
        if str(run.get("status") or "") in ACTIVE_RUN_STATUSES and (bool(run.get("pid_alive")) or bool(run.get("tmux_alive")))
    ]
    stale_runs = [
        compact_run_record(run)
        for run in runs
        if str(run.get("status") or "") == "stale" or str(run.get("health") or "") == "stale_no_process"
    ]
    manual_runs = [
        compact_run_record(run)
        for run in runs
        if str(run.get("status") or "") == "untracked_interactive"
    ]

    review_items = [item for item in issues_before if str(item.get("status") or "").strip().lower() == "review"]
    review_ready: list[dict[str, Any]] = []
    review_needs_evidence: list[dict[str, Any]] = []
    review_packages: dict[str, list[dict[str, Any]]] = {}
    blocked_causes: list[dict[str, Any]] = []
    blocked_requeue: list[dict[str, Any]] = []
    follow_up_candidates: list[dict[str, Any]] = []
    active_issue_ids = {
        int(run["issue_id"])
        for run in active_runs
        if isinstance(run.get("issue_id"), int)
    }
    for item in review_items:
        detail = recovery_plan_issue_detail(int(item["id"]))
        raw = str(detail.get("validation_report") or "").strip()
        if not raw:
            review_needs_evidence.append(compact_issue_record(detail, reason="missing validation_report"))
            continue
        try:
            report = json.loads(raw)
        except json.JSONDecodeError:
            review_needs_evidence.append(compact_issue_record(detail, reason="invalid validation_report"))
            continue
        if not isinstance(report, dict):
            review_needs_evidence.append(compact_issue_record(detail, reason="validation_report is not an object"))
            continue
        result = str(report.get("result_after_gate") or report.get("result") or "").strip().lower()
        if result != "pass":
            review_needs_evidence.append(compact_issue_record(detail, reason=f"validation result is {result or 'unknown'}"))
            continue
        failures = report.get("review_gate_failures") or []
        if failures:
            review_needs_evidence.append(compact_issue_record(detail, reason="review gate failures present"))
            continue
        evidence = report.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        if not evidence:
            review_needs_evidence.append(compact_issue_record(detail, reason="validation evidence missing"))
            continue
        record = compact_issue_record(detail, reason="validation pass with evidence")
        review_ready.append(record)
        if record["package"]:
            review_packages.setdefault(record["package"], []).append(record)

    for item in issues_before:
        if str(item.get("status") or "").strip().lower() != "blocked":
            continue
        issue_id = int(item["id"])
        detail = recovery_plan_issue_detail(issue_id)
        blocker = classify_blocker(detail)
        blocker["active_run"] = issue_id in active_issue_ids
        if blocker["active_run"]:
            blocker["cause"] = "active-run"
            blocker["summary"] = "Active run exists; do not requeue."
        elif blocker["cause"] == "stale-dispatch":
            blocked_requeue.append(compact_issue_record(detail, reason="old Spark dispatch can be requeued"))
        elif blocker["cause"] in {"split-needed", "internal-artifact-gap"}:
            blocker["eligible_for_follow_up"] = True
            if len(follow_up_candidates) < 3 and sum(1 for item in blocked_causes if item.get("cause") == blocker["cause"]) < 2:
                title = blocker.get("follow_up_title") or f"Follow-up for #{issue_id}"
                description = blocker.get("follow_up_description") or blocker.get("summary") or ""
                follow_up_candidates.append(
                    {
                        "source_issue_id": issue_id,
                        "package": blocker.get("package") or "",
                        "title": title,
                        "description": description,
                        "reason": blocker.get("cause"),
                        "command": (
                            "cento agent-work create --title "
                            f"{shlex.quote(title)} --manifest workspace/runs/agent-work/drafts/<generated-story>.json --description {shlex.quote(description)}"
                            + (f" --package {shlex.quote(str(blocker.get('package') or 'default'))}" if blocker.get("package") else "")
                            + f" --role builder"
                        ),
                    }
                )
        blocked_causes.append(blocker)

    board_before = board_snapshot(issues_before)
    projected_after = project_board_snapshot(
        board_before,
        requeued=len(blocked_requeue),
        follow_ups=len(follow_up_candidates),
        follow_up_packages=[str(item.get("package") or "") for item in follow_up_candidates],
    )
    report_mode = "apply" if args.apply else "report-only"
    board_after = dict(projected_after)

    commands: list[str] = []
    for package in sorted(review_packages):
        commands.append(f"cento agent-work review-drain --package {shlex.quote(package)} --dry-run")
        commands.append(f"cento agent-work review-drain --package {shlex.quote(package)} --apply")
    for run in stale_runs[:6]:
        commands.append(f"cento agent-work run-status {run['run_id']} --json")
    for run in manual_runs[:4]:
        if run.get("pid"):
            commands.append(f"ps -fp {run['pid']}")
    for issue in blocked_requeue[:6]:
        role = issue.get("role") or "builder"
        commands.append(
            f"cento agent-work update {issue['id']} --status queued --role {shlex.quote(role)} --note {shlex.quote('Old Spark dispatch can be requeued after board recovery.')}"
        )
    for item in follow_up_candidates:
        commands.append(item["command"])
    commands.append("cento agent-work runs --json --active")

    guardrails = [
        "Do not dispatch new builders while review-ready closures and stale runs are still present.",
        "Prefer review-drain and stale-run reconciliation before creating new follow-up issues.",
        "Avoid requeueing blocked work unless the existing dispatch is clearly stale and no live run remains.",
        "Create follow-up work only for bounded internal Cento gaps or explicit split-needed blockers, and cap the command to three new issues.",
        "Do not create follow-up work for human, device, credential, or LAN blockers.",
    ]

    payload = {
        "generated_at": now_iso(),
        "command_line": recovery_plan_command_line(args),
        "node": node,
        "agent": agent,
        "run_dir": display_path(run_dir),
        "mode": report_mode,
        "after_basis": "actual" if args.apply else "projected",
        "board": {
            "before": board_before,
            "after": board_after,
        },
        "commands": commands,
        "runs": {
            "tracked_active": len(active_runs),
            "stale": len(stale_runs),
            "manual": len(manual_runs),
            "active_items": active_runs,
            "stale_items": stale_runs,
            "manual_items": manual_runs,
        },
        "review": {
            "ready": review_ready,
            "needs_evidence": review_needs_evidence,
            "packages_ready": [
                {
                    "package": package,
                    "count": len(items),
                    "issue_ids": [item["id"] for item in items],
                }
                for package, items in sorted(review_packages.items())
            ],
        },
        "blocked_causes": blocked_causes,
        "blocked_requeue": blocked_requeue,
        "follow_up_candidates": follow_up_candidates,
        "guardrails": guardrails,
    }
    report_path = run_dir / "recovery-plan.md"
    json_path = run_dir / "recovery-plan.json"
    payload["report_path"] = display_path(report_path)
    payload["json_path"] = display_path(json_path)
    if args.apply:
        applied_requeues: list[dict[str, Any]] = []
        for item in blocked_requeue[:6]:
            result = update_issue(
                item["id"],
                "queued",
                "Old Spark dispatch can be requeued after board recovery.",
                node,
                agent,
                None,
                role=str(item.get("role") or "builder"),
            )
            applied_requeues.append({"id": item["id"], "result": result})
        applied_follow_ups: list[dict[str, Any]] = []
        for item in follow_up_candidates[:3]:
            new_issue_id = create_issue(
                str(item.get("title") or "Recovery follow-up"),
                str(item.get("description") or ""),
                node,
                agent,
                str(item.get("package") or "default"),
                status="queued",
                role="builder",
            )
            applied_follow_ups.append({"source_issue_id": item.get("source_issue_id"), "issue_id": new_issue_id})
        issues_after = list_issues(include_closed=False)
        board_after = board_snapshot(issues_after)
        payload["board"]["after"] = board_after
        payload["applied"] = {
            "requeued": applied_requeues,
            "follow_ups": applied_follow_ups,
        }
    else:
        payload["applied"] = {"requeued": [], "follow_ups": []}
    report_path.write_text(recovery_plan_report_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(recovery_plan_report_markdown(payload), end="")
    return 0


def validation_report_passed(issue: dict[str, Any]) -> tuple[bool, str]:
    raw = str(issue.get("validation_report") or "").strip()
    if not raw:
        return False, "missing validation_report"
    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        return False, "invalid validation_report JSON"
    if not isinstance(report, dict):
        return False, "validation_report is not an object"

    result = str(report.get("result_after_gate") or report.get("result") or "").strip().lower()
    if result != "pass":
        return False, f"validation result is {result or 'unknown'}"

    failures = report.get("review_gate_failures") or []
    if failures:
        return False, "review gate failures present"

    evidence = report.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list) or not any(str(item or "").strip() for item in evidence):
        return False, "validation evidence missing"

    return True, "validation report passed"


def command_review_drain(args: argparse.Namespace) -> int:
    require_replacement_backend("review-drain")
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "coordinator"
    status = str(args.status or "review").strip().lower()
    if status != "review":
        raise AgentWorkError("review-drain only closes Review items. Use --status review.")
    packages = [package for value in (args.package or []) for package in split_csv(value)]
    if not packages:
        raise AgentWorkError("review-drain requires at least one --package.")
    run_id = f"review-drain-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    run_dir = resolve_root_path(args.run_dir or f"workspace/runs/agent-work/review-drain/{run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "review-drain.md"
    json_path = run_dir / "review-drain.json"
    command_line = review_drain_command_line(packages, status, apply=args.apply, note=args.note or "", json_output=args.json)
    issues = list_issues_replacement(include_closed=False)
    matches = [item for item in issues if str(item.get("status") or "").strip().lower() == "review" and str(item.get("package") or "") in packages]
    skipped: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for item in matches:
        issue_id = int(item["id"])
        ok, reason = validation_report_passed(item)
        if not ok:
            skipped.append({"id": issue_id, "subject": item.get("subject"), "package": item.get("package"), "reason": reason})
            continue
        eligible.append(
            {
                "id": issue_id,
                "subject": str(item.get("subject") or ""),
                "status": str(item.get("status") or ""),
                "package": str(item.get("package") or ""),
                "dry_run": True,
                "link": replacement_issue_link(issue_id),
            }
        )
    if args.apply:
        for item in eligible:
            issue_id = int(item["id"])
            note = args.note.strip() if args.note else "Review drain closed after approval."
            note = note.rstrip()
            if note:
                note += "\n\n"
            note += (
                f"Review drain transcript: {display_path(report_path)}\n"
                f"Review drain command: {command_line}\n"
                f"Replacement issue: {replacement_issue_link(issue_id)}"
            )
            try:
                updated = update_issue_replacement(issue_id, "done", note, node, agent, None, role="coordinator")
            except AgentWorkError as exc:
                failures.append({"id": issue_id, "error": str(exc)})
                continue
            applied.append(
                {
                    "id": int(updated["id"]),
                    "subject": str(updated.get("subject") or ""),
                    "status": str(updated.get("status") or ""),
                    "package": str(updated.get("package") or ""),
                    "dry_run": False,
                    "link": replacement_issue_link(issue_id),
                }
            )
    payload = {
        "generated_at": now_iso(),
        "command_line": command_line,
        "node": node,
        "agent": agent,
        "status": status,
        "packages": packages,
        "apply": bool(args.apply),
        "matches": applied if args.apply else eligible,
        "skipped": skipped,
        "failures": failures,
        "report_path": display_path(report_path),
        "json_path": display_path(json_path),
    }
    report_path.write_text(review_drain_report_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        match_count = len(payload["matches"])
        if args.apply:
            print(f"review-drain applied: {match_count} issue(s) closed")
        else:
            print(f"review-drain dry-run: {match_count} issue(s) match")
        for item in payload["matches"]:
            action = "closed" if args.apply else "would close"
            print(f"- #{item['id']} {action}: {item['subject']}")
        if failures:
            print("Failures:")
            for item in failures:
                print(f"- #{item['id']}: {item['error']}")
        print(f"report: {display_path(report_path)}")
    return 0 if not failures else 1


def load_validation_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentWorkError(f"Validation manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AgentWorkError(f"Invalid validation manifest JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkError("Validation manifest root must be an object")
    return payload


def load_story_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentWorkError(f"Story manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AgentWorkError(f"Invalid story manifest JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentWorkError(f"Story manifest root must be an object: {path}")
    return payload


def default_validation_manifest_path(story_path: Path, story: dict[str, Any]) -> Path:
    validation = story.get("validation") if isinstance(story.get("validation"), dict) else {}
    manifest_value = str(validation.get("manifest") or "")
    if manifest_value:
        manifest_value = validation_manifest_tools.replace_placeholders(manifest_value, story)
        return resolve_root_path(manifest_value)
    paths = story.get("paths") if isinstance(story.get("paths"), dict) else {}
    run_dir_value = str(paths.get("run_dir") or "")
    if run_dir_value:
        run_dir_value = validation_manifest_tools.replace_placeholders(run_dir_value, story)
        return resolve_root_path(run_dir_value) / "validation.json"
    return story_path.with_name("validation.json")


def preflight_owned_path_errors(story: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(story.get("expected_outputs") or [], start=1):
        if not isinstance(item, dict):
            errors.append(f"expected_outputs #{index} must be an object")
            continue
        if not str(item.get("path") or "").strip():
            errors.append(f"expected_outputs #{index} is missing path")
        if not str(item.get("owner") or "").strip():
            errors.append(f"expected_outputs #{index} is missing owner")
    return errors


def preflight_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Work Preflight",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Story manifest: `{payload['story_manifest']}`",
        f"- Validation manifest: `{payload['validation_manifest']}`",
        f"- Automation coverage: `{payload['automation_coverage_percent']}%`",
        f"- Manual review items: `{payload['manual_review_count']}`",
        f"- AI calls used: `{payload['stats']['ai_calls_used']}`",
        f"- Estimated AI cost: `{payload['stats']['estimated_ai_cost']}`",
        f"- Total duration: `{payload['stats']['total_duration_ms']} ms`",
        "",
        "## Errors",
        "",
    ]
    if payload["errors"]:
        lines.extend(f"- {item}" for item in payload["errors"])
    else:
        lines.append("- None.")
    lines.extend(["", "## Checks", ""])
    for item in payload.get("checks") or []:
        lines.append(f"- `{item.get('type')}` {item.get('name')}")
    return "\n".join(lines) + "\n"


def command_preflight(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    story_path = resolve_root_path(args.story_manifest)
    story = load_story_manifest(story_path)
    errors = story_manifest.validate_manifest(story, check_links=args.check_links)
    errors.extend(preflight_owned_path_errors(story))

    validation_path = resolve_root_path(args.validation_manifest) if args.validation_manifest else default_validation_manifest_path(story_path, story)
    validation_payload: dict[str, Any] | None = None
    if not validation_path.exists():
        if args.write_validation_draft:
            validation_payload = validation_manifest_tools.build_manifest(story, story_path)
            validation_path.parent.mkdir(parents=True, exist_ok=True)
            validation_path.write_text(json.dumps(validation_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        else:
            errors.append(f"validation manifest is missing: {display_path(validation_path)}")
    if validation_payload is None and validation_path.exists():
        try:
            validation_payload = validation_manifest_tools.load_validation(validation_path)
        except validation_manifest_tools.ValidationManifestError as exc:
            errors.append(str(exc))

    if validation_payload is not None:
        errors.extend(validation_manifest_tools.validate_validation_manifest(validation_payload, min_coverage=args.min_automation_coverage))
    coverage = (validation_payload or {}).get("coverage") or {}
    checks = (validation_payload or {}).get("checks") or []
    manual_review = (validation_payload or {}).get("manual_review") or []
    automation_coverage = float(coverage.get("automation_coverage_percent") or (100 if checks and not manual_review else 0))
    total_duration_ms = round((time.perf_counter() - start) * 1000, 3)
    decision = "pass" if not errors else "blocked"

    paths = story.get("paths") if isinstance(story.get("paths"), dict) else {}
    run_dir = resolve_root_path(validation_manifest_tools.replace_placeholders(str(paths.get("run_dir") or story_path.parent), story))
    report_path = resolve_root_path(args.report) if args.report else run_dir / "preflight.json"
    report_md = report_path.with_suffix(".md")
    payload = {
        "schema": "cento.agent-work.preflight.v1",
        "decision": decision,
        "errors": errors,
        "story_manifest": display_path(story_path),
        "validation_manifest": display_path(validation_path),
        "checks": checks,
        "manual_review": manual_review,
        "manual_review_count": len(manual_review) if isinstance(manual_review, list) else 0,
        "automation_coverage_percent": automation_coverage,
        "min_automation_coverage": args.min_automation_coverage,
        "stats": {
            "total_duration_ms": total_duration_ms,
            "ai_calls_used": 0,
            "estimated_ai_cost": 0,
        },
        "outputs": {
            "report": display_path(report_path),
            "summary": display_path(report_md),
        },
        "updated_at": now_iso(),
    }
    if not args.no_write:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        report_md.write_text(preflight_report_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(f"preflight: {decision.upper()} coverage={automation_coverage}% manual_review={payload['manual_review_count']}")
        print(f"story: {display_path(story_path)}")
        print(f"validation: {display_path(validation_path)}")
        if not args.no_write:
            print(f"report: {display_path(report_path)}")
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if decision == "pass" else 1


def validate_create_story_manifest(path: Path) -> dict[str, Any]:
    manifest = load_story_manifest(path)
    errors = story_manifest.validate_manifest(manifest, check_links=False)
    issue = manifest.get("issue") if isinstance(manifest, dict) else None
    if not isinstance(issue, dict) or issue.get("id") != 0:
        errors.append("create-time story manifest must use issue.id = 0; agent-work sets the real issue id after creation")
    if errors:
        detail = "\n".join(f"- {error}" for error in errors)
        raise AgentWorkError(f"Story manifest is required and must be valid before task creation: {display_path(path)}\n{detail}")
    return manifest


def append_story_manifest_section(description: str, manifest_path: Path) -> str:
    section = textwrap.dedent(
        f"""

        h3. Story Manifest

        * Source: {display_path(manifest_path)}
        * Guardrail: task creation requires a valid story manifest generated from the interpreted request before dispatch.
        * Create-time issue id: use 0 in the draft manifest; agent-work canonicalizes it after creation.
        """
    ).strip()
    if not description.strip():
        return section
    return description.rstrip() + "\n\n" + section


def canonical_story_manifest_path(issue_id: int) -> Path:
    return ROOT / "workspace" / "runs" / "agent-work" / str(issue_id) / "story.json"


def canonicalize_create_story_manifest(issue_id: int, source_path: Path, manifest: dict[str, Any], args: argparse.Namespace) -> Path:
    canonical_path = canonical_story_manifest_path(issue_id)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.loads(json.dumps(manifest))
    issue = payload.setdefault("issue", {})
    if isinstance(issue, dict):
        issue["id"] = issue_id
        issue["title"] = args.title
        issue["package"] = args.package or issue.get("package") or "default"
    lane = payload.setdefault("lane", {})
    if isinstance(lane, dict):
        lane["node"] = args.node or lane.get("node") or "unassigned"
        lane["agent"] = args.agent or lane.get("agent") or ""
        lane["role"] = args.role or lane.get("role") or "builder"
    paths = payload.setdefault("paths", {})
    if isinstance(paths, dict):
        paths["run_dir"] = display_path(canonical_path.parent)
    payload.setdefault("metadata", {})
    if isinstance(payload["metadata"], dict):
        payload["metadata"]["canonicalized_from"] = display_path(source_path)
        payload["metadata"]["canonicalized_at"] = now_iso()

    errors = story_manifest.validate_manifest(payload, check_links=False)
    if errors:
        detail = "\n".join(f"- {error}" for error in errors)
        raise AgentWorkError(f"Canonical story manifest failed validation for issue #{issue_id}: {display_path(canonical_path)}\n{detail}")

    canonical_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return canonical_path


def manifest_context(issue_id: int, manifest_path: Path, manifest: dict[str, Any], node: str, agent: str) -> dict[str, str]:
    run_dir = manifest.get("run_dir") or str(manifest_path.parent)
    return {
        "root": str(ROOT),
        "issue": str(issue_id),
        "manifest": display_path(manifest_path),
        "manifest_dir": display_path(manifest_path.parent),
        "run_dir": str(format_manifest_value(run_dir, {"root": str(ROOT), "issue": str(issue_id)})),
        "node": node,
        "agent": agent,
    }


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def manifest_value_with_source(
    key: str,
    *sources: tuple[str, dict[str, Any] | None],
) -> tuple[Any | None, str]:
    for source_name, payload in sources:
        if not isinstance(payload, dict):
            continue
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value, source_name
    return None, sources[0][0] if sources else "validation"


def validation_route_policy(manifest: dict[str, Any], story_payload: dict[str, Any] | None) -> dict[str, Any]:
    story_validation: dict[str, Any] | None = None
    if isinstance(story_payload, dict):
        validation = story_payload.get("validation")
        if isinstance(validation, dict):
            story_validation = validation
    manifest_validation = manifest if isinstance(manifest, dict) else {}
    eligible_value, eligible_source = manifest_value_with_source(
        "no_model_eligible",
        ("story.validation", story_validation),
        ("validation", manifest_validation),
    )
    risk_value, risk_source = manifest_value_with_source(
        "risk",
        ("story.validation", story_validation),
        ("validation", manifest_validation),
    )
    eligible = coerce_bool(eligible_value)
    risk = str(risk_value or "").strip().lower()
    no_model = eligible and risk in NO_MODEL_VALIDATION_RISKS
    if no_model:
        reason = f"{eligible_source}.no_model_eligible is true and {risk_source}.risk is {risk}"
        escalation = ""
    elif not eligible:
        reason = f"{eligible_source}.no_model_eligible is false or missing"
        escalation = "model-backed validation required"
    elif not risk:
        reason = f"{risk_source}.risk is missing"
        escalation = "risk must be explicit before validation routing"
    else:
        reason = f"{risk_source}.risk is {risk}; model-backed validation required"
        escalation = "risk exceeds the no-model threshold"
    return {
        "mode": "no-model" if no_model else "standard",
        "eligible": eligible,
        "risk": risk,
        "eligible_source": eligible_source,
        "risk_source": risk_source,
        "reason": reason,
        "escalation": escalation,
        "summary": f"Validation route: {'no-model' if no_model else 'standard'} ({reason}).",
        "story_no_model_eligible": story_validation.get("no_model_eligible") if story_validation else None,
        "story_risk": story_validation.get("risk") if story_validation else None,
        "validation_no_model_eligible": manifest_validation.get("no_model_eligible"),
        "validation_risk": manifest_validation.get("risk"),
    }


def normalize_review_section_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def review_sections_from_note(note: str, required_sections: list[str]) -> dict[str, str]:
    required = [normalize_review_section_name(item) for item in required_sections]
    required_set = set(required)
    header_re = re.compile(r"^\s*(?:h\d+\.\s*|#{1,6}\s*|\*+\s*)?(?P<section>[a-zA-Z][a-zA-Z0-9 _-]*)\s*:?\s*\*?\s*$")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in note.splitlines():
        line = raw.strip()
        match = header_re.match(line)
        if not match:
            if current is not None:
                sections.setdefault(current, []).append(raw)
            continue
        section_name = normalize_review_section_name(match.group("section"))
        if section_name in required_set:
            current = section_name
            if current not in sections:
                sections[current] = []
            continue
        if section_name.startswith("residual risk") and section_name in required_set:
            current = section_name
            if current not in sections:
                sections[current] = []
            continue
        if current is not None:
            sections.setdefault(current, []).append(raw)
    return {section: "\n".join(lines).strip() for section, lines in sections.items() if lines or section in required_set}


def note_evidence_paths(note: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"@([^@\\n]+)@", note)]


def review_gate_required_sections(story: dict[str, Any] | None) -> list[str]:
    if not story:
        return []
    review_gate = story.get("review_gate") or {}
    required = review_gate.get("required_sections")
    if isinstance(required, list) and required:
        normalized = [str(item) for item in required if str(item).strip()]
        if normalized:
            return normalized
    return []


def review_gate_residual_required(story: dict[str, Any] | None, required_sections: list[str]) -> bool:
    review_gate = (story or {}).get("review_gate") or {}
    configured = review_gate.get("residual_risk_required")
    if isinstance(configured, bool):
        return configured
    normalized = [normalize_review_section_name(item) for item in required_sections]
    return "residual risk" in normalized


def _resolve_local_evidence_path(value: str) -> Path | None:
    value = str(value or "").strip()
    if not value:
        return None
    low = value.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return None
    if value.startswith("file:///{root}/"):
        value = value[len("file:///{root}/") :]
    elif value.startswith("file://"):
        value = value[len("file://") :]
    try:
        return resolve_root_path(value)
    except OSError:
        return None


def normalize_evidence_entry(value: str) -> str:
    return os.path.normpath(str(value).strip())


def _has_pass_check(checks: list[dict[str, Any]], terms: list[str]) -> bool:
    if not checks:
        return False
    for item in checks:
        if not item.get("ok"):
            continue
        parts = [str(item.get("name") or ""), str(item.get("type") or ""), str(item.get("command") or ""), str(item.get("path") or ""), str(item.get("url") or "")]
        text = " ".join(parts).lower()
        if any(term in text for term in terms):
            return True
    return False


def validate_review_gate(
    *,
    note: str,
    evidence: list[str],
    checks: list[dict[str, Any]] | None,
    story: dict[str, Any] | None,
) -> list[str]:
    if story is None:
        return []
    required_sections = review_gate_required_sections(story) or REVIEW_GATE_DEFAULT_SECTIONS
    residual_required = review_gate_residual_required(story, required_sections)
    sections = review_sections_from_note(note, required_sections)
    section_set = {normalize_review_section_name(item): item for item in required_sections}
    missing: list[str] = []
    for item in required_sections:
        normalized = normalize_review_section_name(item)
        if normalized not in sections:
            missing.append(f"Review note is missing section: {item}")
            continue
        if normalized == "residual risk" and residual_required:
            text = sections[normalized].strip()
            if not text:
                missing.append("Review note residual risk section must be present and non-empty.")
    required_evidence = []
    validation = story.get("validation") or {}
    for raw in validation.get("required_evidence", []) if isinstance(validation.get("required_evidence"), list) else []:
        if isinstance(raw, str):
            required_evidence.append(raw.strip())
    for path_value in story.get("screenshots") or []:
        if not isinstance(path_value, dict):
            continue
        output = str(path_value.get("output") or "").strip()
        if output:
            required_evidence.append(output)
    provided_paths = {normalize_evidence_entry(item) for item in evidence}
    provided_paths.update({normalize_evidence_entry(item) for item in note_evidence_paths(note)})
    for item in required_evidence:
        normalized = normalize_evidence_entry(item)
        if _resolve_local_evidence_path(item):
            if _resolve_local_evidence_path(item) and _resolve_local_evidence_path(item).exists():
                continue
            missing.append(f"Required evidence path is missing: {item}")
        elif normalized in provided_paths:
            continue
        else:
            missing.append(f"Required evidence reference is missing or not attached: {item}")
    review_gate = story.get("review_gate") or {}
    categories = [str(item).strip().lower() for item in (review_gate.get("required_evidence_categories") or []) if str(item).strip()]
    api_required = bool(story.get("api_endpoints"))
    if categories:
        required_map = {
            "syntax-test": ("syntax", ["syntax", "test", "py_compile", "pytest"]),
            "syntax": ("syntax", ["syntax", "test", "py_compile", "pytest"]),
            "api": ("api", ["api", "endpoint", "http", "curl"]),
            "api-check": ("api", ["api", "endpoint", "http", "curl"]),
            "api-checks": ("api", ["api", "endpoint", "http", "curl"]),
            "screenshot": ("screenshot", ["screenshot", "playwright"]),
            "screenshots": ("screenshot", ["screenshot", "playwright"]),
            "visual": ("visual", ["visual", "inspection", "screenshot"]),
            "visual-inspection": ("visual", ["visual", "inspection", "screenshot"]),
            "visual-inspection-notes": ("visual", ["visual", "inspection", "screenshot"]),
        }
        seen = set()
        for category in categories:
            if category in seen:
                continue
            seen.add(category)
            label, terms = required_map.get(category, (None, []))
            if not label:
                continue
            if label == "api" and not api_required:
                continue
            if label == "syntax":
                if not _has_pass_check(checks or [], terms):
                    has_file = any(item for item in required_evidence if any(term in item.lower() for term in terms) and _resolve_local_evidence_path(item) and _resolve_local_evidence_path(item).exists())
                    if not has_file:
                        missing.append("Syntax/test evidence is required: no passing syntax/test check result found.")
            elif label == "api":
                if not _has_pass_check(checks or [], terms):
                    has_file = any(item for item in required_evidence if "api" in item.lower() and _resolve_local_evidence_path(item) and _resolve_local_evidence_path(item).exists())
                    if not has_file:
                        missing.append("API evidence is required: no passing API check found and no API evidence artifact exists.")
            elif label == "screenshot":
                missing_screens = []
                for path_value in required_evidence:
                    if "screenshot" not in path_value.lower():
                        continue
                    path_obj = _resolve_local_evidence_path(path_value)
                    if not path_obj or not path_obj.exists():
                        missing_screens.append(path_value)
                if missing_screens:
                    for item in missing_screens:
                        missing.append(f"Screenshot evidence missing: {item}")
            elif label == "visual":
                visual_text = " ".join(section for section in sections.values()).lower()
                if "visual" not in visual_text and "screenshot" not in visual_text:
                    if not any(_resolve_local_evidence_path(item) and _resolve_local_evidence_path(item).exists() for item in required_evidence if "visual" in item.lower() or "inspection" in item.lower()):
                        missing.append("Visual inspection evidence is required: note does not include visual inspection notes and no visual evidence artifact exists.")
    return missing


def review_gate_feedback_block(errors: list[str]) -> str:
    if not errors:
        return ""
    lines = ["", "Review gate failures:"]
    lines.extend(f"* {item}" for item in errors)
    return "\n".join(lines)


def run_command_check(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    command = str(format_manifest_value(check.get("command") or "", context)).strip()
    if not command:
        return {"ok": False, "message": "command check missing command"}
    timeout = int(check.get("timeout_seconds") or check.get("timeout") or 60)
    try:
        proc = subprocess.run(command, shell=True, cwd=ROOT, executable="/bin/bash", text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "message": f"timed out after {timeout}s", "command": command, "stdout": exc.stdout or "", "stderr": exc.stderr or ""}
    expected = int(check.get("expected_exit", 0))
    ok = proc.returncode == expected
    return {
        "ok": ok,
        "message": f"exit {proc.returncode}",
        "command": command,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def run_file_check(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    path_value = str(format_manifest_value(check.get("path") or "", context))
    if not path_value:
        return {"ok": False, "message": "file check missing path"}
    path = resolve_root_path(path_value)
    exists = path.exists()
    non_empty = bool(check.get("non_empty", False))
    ok = exists and (not non_empty or path.stat().st_size > 0)
    message = "exists" if ok else "missing" if not exists else "empty"
    return {"ok": ok, "message": message, "path": display_path(path), "evidence": display_path(path) if ok else ""}


def run_url_check(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    url = str(format_manifest_value(check.get("url") or "", context))
    if not url:
        return {"ok": False, "message": "url check missing url"}
    timeout = int(check.get("timeout_seconds") or check.get("timeout") or 10)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            body = response.read(512)
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"ok": False, "message": str(exc), "url": url}
    expected = int(check.get("expected_status", 200))
    ok = status == expected
    return {"ok": ok, "message": f"status {status}", "url": url, "sample": body.decode("utf-8", errors="replace")}


def run_screenshot_check(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    url = str(format_manifest_value(check.get("url") or "", context))
    output_value = str(format_manifest_value(check.get("output") or "", context))
    if not url or not output_value:
        return {"ok": False, "message": "screenshot check requires url and output"}
    output = resolve_root_path(output_value)
    output.parent.mkdir(parents=True, exist_ok=True)
    viewport = str(check.get("viewport") or "390,844")
    wait_ms = str(check.get("wait_ms") or check.get("wait") or "1000")
    cmd = [
        "npx",
        "--yes",
        "playwright",
        "screenshot",
        "--browser=chromium",
        f"--viewport-size={viewport}",
        f"--wait-for-timeout={wait_ms}",
        url,
        str(output),
    ]
    timeout = int(check.get("timeout_seconds") or check.get("timeout") or 60)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "message": f"timed out after {timeout}s", "command": shlex.join(cmd), "stdout": exc.stdout or "", "stderr": exc.stderr or ""}
    ok = proc.returncode == 0 and output.exists() and output.stat().st_size > 0
    return {
        "ok": ok,
        "message": f"exit {proc.returncode}",
        "command": shlex.join(cmd),
        "path": display_path(output),
        "evidence": display_path(output) if ok else "",
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def run_validation_check(check: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    kind = str(check.get("type") or "command").lower()
    name = str(check.get("name") or kind)
    if kind == "command":
        result = run_command_check(check, context)
    elif kind == "file":
        result = run_file_check(check, context)
    elif kind == "url":
        result = run_url_check(check, context)
    elif kind == "screenshot":
        result = run_screenshot_check(check, context)
    else:
        result = {"ok": False, "message": f"unknown check type: {kind}"}
    result["name"] = name
    result["type"] = kind
    return result


def validation_report_markdown(
    issue_id: int,
    manifest_path: Path,
    result: str,
    checks: list[dict[str, Any]],
    evidence: list[str],
    *,
    policy: dict[str, Any] | None = None,
) -> str:
    validation_evidence, screenshot_evidence = partition_evidence(evidence)
    lines = [
        f"# Validation Report For #{issue_id}",
        "",
        f"Generated: {now_iso()}",
        f"Manifest: `{display_path(manifest_path)}`",
        f"Result: **{result.upper()}**",
        "",
        "## Validation route",
        "",
    ]
    if policy:
        lines.extend(
            [
                f"- Mode: **{str(policy.get('mode') or 'standard').upper()}**",
                f"- Eligible: `{bool(policy.get('eligible'))}`",
                f"- Risk: `{str(policy.get('risk') or 'unknown')}`",
                f"- Source: `{str(policy.get('eligible_source') or 'validation')}` / `{str(policy.get('risk_source') or 'validation')}`",
                f"- Reason: {str(policy.get('reason') or 'Validation route selected.')}",
            ]
        )
    else:
        lines.append("- Standard validation path.")
    lines.extend(["", "## Checks", ""])
    for item in checks:
        status = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"- **{status}** `{item.get('type')}` {item.get('name')}: {item.get('message')}")
    lines.extend(["", "## Validation evidence", ""])
    if validation_evidence:
        lines.extend(f"- `{item}`" for item in validation_evidence)
    else:
        lines.append("- None.")
    lines.extend(["", "## Screenshot evidence", ""])
    if screenshot_evidence:
        lines.extend(f"- `{item}`" for item in screenshot_evidence)
    else:
        lines.append("- None.")
    lines.extend(["", "## All evidence", ""])
    if evidence:
        lines.extend(f"- `{item}`" for item in evidence)
    else:
        lines.append("- No evidence paths produced.")
    return "\n".join(lines) + "\n"


def command_validate_run(args: argparse.Namespace) -> int:
    require_replacement_backend("validate-run")
    issue = show_issue(args.issue)
    node = args.node or current_node()
    agent = args.agent or os.environ.get("USER") or "validator"
    manifest_path = resolve_root_path(args.manifest or f"workspace/runs/agent-work/{args.issue}/validation.json")
    manifest = load_validation_manifest(manifest_path)
    story_payload = None
    story_manifest = None
    if args.story_manifest:
        story_manifest = resolve_root_path(args.story_manifest)
        story_payload = load_story_manifest(story_manifest)
    validation_policy = validation_route_policy(manifest, story_payload)
    required = manifest.get("requires") or {}
    allowed = [str(item) for item in required.get("validator_agents") or []]
    enforce_validator_authorized(agent, allowed)
    context = manifest_context(args.issue, manifest_path, manifest, node, agent)
    checks = list(manifest.get("checks") or [])
    if required.get("ui_screenshots") and not any(str(item.get("type", "")).lower() == "screenshot" for item in checks):
        raise AgentWorkError("Validation manifest requires UI screenshots but has no screenshot checks")
    if required.get("builder_report"):
        checks.insert(0, {"name": "Builder report exists", "type": "file", "path": str(required["builder_report"]), "non_empty": True})

    results = [run_validation_check(check, context) for check in checks]
    evidence = [item.get("evidence") for item in results if item.get("ok") and item.get("evidence")]
    report_path = resolve_root_path(str(format_manifest_value(manifest.get("report") or str(manifest_path.parent / "validation-report.md"), context)))
    report_json_path = report_path.with_suffix(".json")
    report_evidence = [display_path(report_path), display_path(report_json_path)]
    evidence_with_reports = evidence + [item for item in report_evidence if item not in evidence]
    result = "pass" if all(item.get("ok") for item in results) else "fail"
    final_result = result
    gate_failures = validate_review_gate(
        note=args.note or "",
        evidence=evidence_with_reports,
        checks=results,
        story=story_payload,
    )
    if result == "pass" and gate_failures:
        final_result = "fail"
        for item in gate_failures:
            print(f"[agent-work-review-gate] {item}", file=sys.stderr)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    all_evidence = evidence_with_reports
    summary_payload = build_review_summary(
        issue_id=args.issue,
        subject=str(issue.get("subject") or ""),
        result=result,
        final_result=final_result,
        checks=results,
        evidence=all_evidence,
        agent=agent,
        node=node,
        gate_failures=gate_failures,
        note=args.note or "",
    )
    summary_path = write_review_summary(args.issue, summary_payload)
    if summary_path not in all_evidence:
        all_evidence = [*all_evidence, summary_path]
    payload = {
        "issue": args.issue,
        "subject": issue.get("subject"),
        "result": result,
        "result_after_gate": final_result,
        "validation_mode": validation_policy["mode"],
        "validation_policy": validation_policy,
        "agent": agent,
        "node": node,
        "manifest": display_path(manifest_path),
        "story_manifest": str(story_manifest or ""),
        "review_gate_failures": gate_failures,
        "evidence": all_evidence,
        "review_summary": summary_path,
        "checks": results,
        "updated_at": now_iso(),
    }
    report_path.write_text(
        validation_report_markdown(args.issue, manifest_path, result, results, all_evidence, policy=validation_policy),
        encoding="utf-8",
    )
    report_json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    note = args.note or f"validate-run {result.upper()} using {display_path(manifest_path)}"
    note = f"{validation_policy['summary']}\n\n{note}".strip()
    note = append_validation_summary(note, results)
    note = validation_note(final_result, note, all_evidence) + review_gate_feedback_block(gate_failures)
    if not args.no_update:
        status = "review" if final_result == "pass" else "blocked"
        update_issue(
            args.issue,
            status,
            note,
            node,
            agent,
            None,
            role="validator",
            validation_report=json.dumps(payload, sort_keys=True, default=str),
        )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"validate-run #{args.issue}: {final_result.upper()} report={display_path(report_path)}")
        for item in results:
            status = "PASS" if item.get("ok") else "FAIL"
            print(f"{status} {item.get('name')}: {item.get('message')}")
    if final_result == "pass":
        return 0
    return 1


def agent_prompt(issue: dict[str, Any], role: str = "builder") -> str:
    role = normalize_role(role)
    owned_files = extract_owned_files(str(issue.get("description") or ""))
    if owned_files:
        ownership_block = "\n".join(f"        - {item}" for item in owned_files)
    else:
        ownership_block = "        - Not declared. Before editing, add a note with the files/modules you intend to own, or ask the coordinator to split the work."
    if role == "validator":
        role_protocol = textwrap.dedent(
            f"""\
            Protocol:
            1. Start by running: cento agent-work claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role validator
            2. Do not implement product code unless the issue explicitly asks for validator tooling.
            3. If a validation manifest exists, run: cento agent-work validate-run {issue['id']} --manifest PATH
            4. If a matching story manifest is available, add `--story-manifest PATH` to enforce strict review-gate validation.
            5. Otherwise run the stated checks, inspect screenshots or rendered output, and verify evidence paths exist.
            6. Pass with: cento agent-work validate {issue['id']} --result pass --evidence PATH --note "..."
            7. Fail or block with: cento agent-work validate {issue['id']} --result fail --evidence PATH --note "..."

            Only a Validator pass moves the issue to Review.
            """
        )
    elif role == "coordinator":
        role_protocol = textwrap.dedent(
            f"""\
            Protocol:
            1. Start by running: cento agent-work claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role coordinator
            2. Inspect current issue/package state, active runs, validation gaps, and blockers. Compare any `story.json` or deliverables manifest in the run directory before dispatching new work. Split when routes, API endpoints, screenshots, or human/device steps differ. Combine only when the same evidence files, validation commands, and review gate can serve all related work. If Review is the bottleneck, dry-run `cento agent-work review-drain --package <package> --dry-run` before applying closure.
            3. Apply the coordinator checklist in `docs/agent-work-coordinator-lane.md`: verify the acceptance contract, route implementation to Builder, evidence to Validator, and hubs/logs to Docs/Evidence, then decide whether the story should be split, combined, or blocked.
            4. Dispatch or recommend specific builder, validator, or small-worker work without duplicating active runs. Use `cento agent-work dispatch ... --dry-run` for recommendations, not blind dispatches.
            5. Notify only on state changes. Keep Taskstream updated with `cento agent-work update {issue['id']} --status running --role coordinator --note "..."`, and send a short `cento notify ...` message only when the state actually changes, ownership changes, or human input is needed.
            6. If blocked, use: cento agent-work update {issue['id']} --status blocked --role coordinator --note "blocked because ..."
            7. When coordination is complete, add a concise report and move to validating with --role coordinator.

            Coordinators advance the pool and surface next actions; they do not validate builder work.
            """
        )
    else:
        role_protocol = textwrap.dedent(
            f"""\
            Protocol:
            1. Start by running: cento agent-work claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role builder
            2. If that route is not registered on this node, use: python3 scripts/agent_work.py claim {issue['id']} --node "$(uname -s)" --agent "$USER" --role builder
            3. Do the smallest coherent implementation for this issue only.
            4. Keep Taskstream updated with: cento agent-work update {issue['id']} --status running --role builder --note "..."
            5. When implementation is ready, create the handoff with: cento agent-work handoff {issue['id']} --summary "..." --changed-file PATH --command "..." --evidence PATH
            6. If blocked, use: cento agent-work update {issue['id']} --status blocked --role builder --note "blocked because ..."

            Builders do not move issues to Review. Review is reserved for Validator pass.
            """
        )
    return textwrap.dedent(
        f"""\
        You are a Cento {role} agent working a tracked Cento replacement issue.

        Issue: #{issue['id']} {issue['subject']}
        Project: {issue['project']}
        Status: {issue['status']}
        Node: {issue.get('node') or 'unassigned'}
        Agent: {issue.get('agent') or 'unassigned'}
        Role: {role}
        Package: {issue.get('package') or 'default'}

        Owned files/modules:
{ownership_block}

        Work instructions:
        {issue.get('description') or ''}

        {role_protocol}
        """
    )


def command_prompt(args: argparse.Namespace) -> int:
    issue = show_issue(args.issue)
    prompt = agent_prompt(issue, args.role)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
        print(path)
    else:
        print(prompt)
    return 0


def command_runtimes(args: argparse.Namespace) -> int:
    entries = runtime_entries()
    sample = max(int(args.sample or 0), 0)
    sample_counts: dict[str, int] = {}
    if sample:
        for issue_id in range(1, sample + 1):
            runtime = weighted_runtime(issue_id, args.role, args.package or "sample")
            runtime_id = str(runtime["id"])
            sample_counts[runtime_id] = sample_counts.get(runtime_id, 0) + 1
    payload = {
        "routing": load_runtime_registry().get("routing", "weighted"),
        "runtimes": entries,
        "sample": {
            "size": sample,
            "role": args.role,
            "package": args.package or "sample",
            "counts": sample_counts,
            "percentages": {key: round(value * 100 / sample, 2) for key, value in sample_counts.items()} if sample else {},
        },
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    print(f"routing: {payload['routing']}")
    for entry in entries:
        marker = " preferred" if entry.get("preferred") else ""
        print(f"- {entry['id']}: {entry.get('display_name', entry['id'])} model={entry.get('model', '')} weight={entry.get('weight', 0)}{marker}")
    if sample:
        print(f"sample: {sample} issues")
        for runtime_id, count in sorted(sample_counts.items()):
            pct = round(count * 100 / sample, 2)
            print(f"- {runtime_id}: {count} ({pct}%)")
    return 0


def command_runs(args: argparse.Namespace) -> int:
    records = agent_run_records(include_untracked=not args.no_untracked, reconcile=args.reconcile)
    if args.issue is not None:
        records = [item for item in records if item.get("issue_id") == args.issue]
    if args.active:
        records = [item for item in records if is_active_run_record(item)]
    if args.json:
        print(json.dumps({"runs": records, "count": len(records), "updated_at": now_iso()}, indent=2, default=str))
    else:
        print_agent_run_table(records)
    return 0


def command_run_status(args: argparse.Namespace) -> int:
    record = load_agent_run(args.run_id)
    record = reconcile_agent_run(record, write=args.reconcile)
    if args.json:
        print(json.dumps(record, indent=2, default=str))
        return 0
    print_agent_run_table([record])
    return 0


def command_run_update(args: argparse.Namespace) -> int:
    updates: dict[str, Any] = {}
    if args.status:
        updates["status"] = args.status
    if args.health:
        updates["health"] = args.health
    if args.pid is not None:
        updates["pid"] = args.pid
    if args.child_pid is not None:
        updates["child_pid"] = args.child_pid
    if args.tmux_session:
        updates["tmux_session"] = args.tmux_session
    if args.log_path:
        updates["log_path"] = args.log_path
    if args.exit_code is not None:
        updates["exit_code"] = args.exit_code
    if args.ended_now or args.status in ENDED_RUN_STATUSES:
        updates["ended_at"] = now_iso()
    if args.note:
        updates["note"] = args.note
    record = update_agent_run(args.run_id, updates)
    if args.json:
        print(json.dumps(record, indent=2, default=str))
    else:
        print(f"updated run {record['run_id']}: {record.get('status')}")
    return 0


def command_run_wrap(args: argparse.Namespace) -> int:
    if not args.command:
        raise AgentWorkError("run-wrap requires a command after --")
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise AgentWorkError("run-wrap requires a command after --")
    record = update_agent_run(args.run_id, {"status": "running", "pid": os.getpid(), "command": shlex.join(command), "started_at": now_iso()})
    log_path = record.get("log_path") or ""
    stdout_target = subprocess.PIPE
    stderr_target = subprocess.STDOUT
    log_handle = None
    if log_path:
        resolved = resolve_root_path(str(log_path))
        resolved.parent.mkdir(parents=True, exist_ok=True)
        log_handle = resolved.open("ab")
        stdout_target = log_handle
    try:
        proc = subprocess.Popen(command, cwd=ROOT, stdout=stdout_target, stderr=stderr_target)
        update_agent_run(args.run_id, {"child_pid": proc.pid, "status": "running"})
        stdout, _stderr = proc.communicate()
    finally:
        if log_handle:
            log_handle.close()
    if not log_path and stdout:
        sys.stdout.buffer.write(stdout)
    status = "succeeded" if proc.returncode == 0 else "failed"
    update_agent_run(args.run_id, {"status": status, "exit_code": proc.returncode, "ended_at": now_iso()})
    return int(proc.returncode)


def command_dispatch(args: argparse.Namespace) -> int:
    require_replacement_backend("dispatch")
    issue = show_issue(args.issue)
    role = normalize_role(args.role)
    runtime = select_runtime(issue, role, args.runtime)
    runtime_id = str(runtime["id"])
    run_id = f"issue-{issue['id']}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_dir = ROOT / "workspace" / "runs" / "agent-work" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.md"
    prompt_text = agent_prompt(issue, role)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    node = args.node or issue.get("node") or current_node()
    model = args.model or os.environ.get("CENTO_AGENT_MODEL") or str(runtime.get("model") or "gpt-5.3-codex-spark")
    agent = args.agent or str(runtime.get("agent") or runtime_id) or issue.get("agent") or os.environ.get("USER") or "agent"
    session = f"cento-agent-{issue['id']}-{datetime.now().strftime('%H%M%S')}"
    if not args.skip_preflight:
        story_path = canonical_story_manifest_path(int(issue["id"]))
        if not story_path.exists():
            message = f"Dispatch preflight blocked: canonical story manifest is missing at {display_path(story_path)}"
            if not args.dry_run:
                update_issue(args.issue, "blocked", message, node, agent, None, role=role)
            raise AgentWorkError(message + " (use --skip-preflight only for legacy/manual dispatch).")
        preflight_args = argparse.Namespace(
            story_manifest=str(story_path),
            validation_manifest=args.validation_manifest,
            min_automation_coverage=args.min_automation_coverage,
            write_validation_draft=False,
            check_links=False,
            report=str(run_dir / "preflight.json"),
            no_write=False,
            json=False,
        )
        preflight_result = command_preflight(preflight_args)
        if preflight_result != 0:
            message = f"Dispatch preflight blocked for #{issue['id']}. Report: {display_path(run_dir / 'preflight.json')}"
            if not args.dry_run:
                update_issue(args.issue, "blocked", message, node, agent, None, role=role)
            return preflight_result
    log_name = "codex.log" if runtime_id == "codex" else f"{runtime_id}.log"
    log_path = f"workspace/runs/agent-work/{run_id}/{log_name}"
    runtime_command = (
        f"claude --print --model {shlex.quote(model)} --permission-mode bypassPermissions --add-dir . < prompt"
        if runtime_id == "claude-code"
        else f"codex exec --model {shlex.quote(model)} --dangerously-bypass-approvals-and-sandbox -C . <prompt>"
    )
    ledger_record = create_agent_run(
        run_id=run_id,
        issue=issue,
        node=node,
        agent=agent,
        role=role,
        runtime=runtime,
        model=model,
        command=runtime_command,
        prompt_path=display_path(prompt_path),
        log_path=log_path,
        tmux_session=session,
        status="dry_run" if args.dry_run else "launching",
        dispatch_path=f"workspace/runs/agent-work/{run_id}/dispatch.json",
    )
    dispatch = f"run_id={run_id} runtime={runtime_id} node={node} model={model} session={session} ledger={ledger_record['ledger_path']} local_prompt={prompt_path}"
    metadata = {
        "run_id": run_id,
        "issue": issue["id"],
        "node": node,
        "agent": agent,
        "runtime": runtime_id,
        "runtime_display_name": runtime.get("display_name", runtime_id),
        "provider": runtime.get("provider", ""),
        "weight": runtime.get("weight", 0),
        "model": model,
        "role": role,
        "session": session,
        "ledger": ledger_record["ledger_path"],
        "local_prompt": str(prompt_path),
        "log": log_path,
        "created_at": now_iso(),
    }
    (run_dir / "dispatch.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(dispatch)
        print(prompt_path)
        print(ledger_record["ledger_path"])
        return 0
    update_issue(args.issue, "running", f"Dispatched {role} to {node} with {runtime_id} {model}. Prompt: {prompt_path}", node, agent, dispatch, role=role)
    encoded_prompt = base64.b64encode(prompt_text.encode("utf-8")).decode("ascii")
    repo_guess = "/home/alice/projects/cento" if node == "linux" else "/Users/anovik-air/cento" if node == "macos" else str(ROOT)
    remote_command = textwrap.dedent(
        f"""\
        set -euo pipefail
        repo_root={shlex.quote(repo_guess)}
        if [[ ! -d "$repo_root" ]]; then
          if [[ -d "$HOME/projects/cento" ]]; then
            repo_root="$HOME/projects/cento"
          elif [[ -d "$HOME/cento" ]]; then
            repo_root="$HOME/cento"
          else
            repo_root="$PWD"
          fi
        fi
        cd "$repo_root"
        run_dir={shlex.quote(f"workspace/runs/agent-work/{run_id}")}
        mkdir -p "$run_dir"
        prompt_file="$run_dir/prompt.md"
        log_file="$run_dir/{shlex.quote(log_name)}"
        python3 -c {shlex.quote("import base64,sys; sys.stdout.write(base64.b64decode(sys.argv[1]).decode('utf-8'))")} {shlex.quote(encoded_prompt)} > "$prompt_file"
        cat > "$run_dir/run.sh" <<'CENTO_AGENT_RUN'
        #!/usr/bin/env bash
        set -euo pipefail
        script_path="${{BASH_SOURCE[0]}}"
        run_dir="$(cd "$(dirname "$script_path")" && pwd)"
        repo_root="$(cd "$run_dir/../../../.." && pwd)"
        cd "$repo_root"
        prompt_file="$run_dir/prompt.md"
        log_file="$run_dir/{shlex.quote(log_name)}"
        runtime={shlex.quote(runtime_id)}
        if [[ -f ./scripts/agent_work.py ]]; then
          agent_work_cmd=(python3 ./scripts/agent_work.py)
        elif [[ -x ./scripts/cento.sh ]]; then
          agent_work_cmd=(./scripts/cento.sh agent-work)
        else
          agent_work_cmd=(cento agent-work)
        fi
        "${{agent_work_cmd[@]}}" run-update {shlex.quote(run_id)} --status running --pid $$ --tmux-session {shlex.quote(session)} --log-path {shlex.quote(log_path)} || true
        "${{agent_work_cmd[@]}}" claim {issue['id']} --node {shlex.quote(node)} --agent {shlex.quote(agent)} --role {shlex.quote(role)} --note {shlex.quote(f"tmux session {session} started")} || true
        set +e
        if [[ "$runtime" == "claude-code" ]]; then
          claude_bin="${{CENTO_CLAUDE_BIN:-claude}}"
          if [[ -x "$HOME/.npm-global/bin/claude" ]]; then
            claude_bin="$HOME/.npm-global/bin/claude"
          fi
          "$claude_bin" --print --model {shlex.quote(model)} --permission-mode bypassPermissions --add-dir "$PWD" < "$prompt_file" > "$log_file" 2>&1
        else
          codex_bin="${{CENTO_CODEX_BIN:-codex}}"
          if [[ -x "$HOME/.npm-global/bin/codex" ]]; then
            codex_bin="$HOME/.npm-global/bin/codex"
          fi
          "$codex_bin" exec --model {shlex.quote(model)} --dangerously-bypass-approvals-and-sandbox -C "$PWD" "$(cat "$prompt_file")" > "$log_file" 2>&1
        fi
        status=$?
        set -e
        if [[ $status -eq 0 ]]; then
          "${{agent_work_cmd[@]}}" run-update {shlex.quote(run_id)} --status succeeded --exit-code 0 --ended-now || true
          if [[ {shlex.quote(role)} == "validator" ]]; then
            "${{agent_work_cmd[@]}}" validate {issue['id']} --result pass --evidence {shlex.quote(log_path)} --note {shlex.quote(f"Validator session {session} passed with {runtime_id}; log: {log_path}")} || true
          elif [[ {shlex.quote(role)} == "coordinator" ]]; then
            "${{agent_work_cmd[@]}}" update {issue['id']} --status validating --role coordinator --note {shlex.quote(f"Coordinator session {session} finished with {runtime_id}; report/log: {log_path}")} || true
          else
            "${{agent_work_cmd[@]}}" update {issue['id']} --status validating --role {shlex.quote(role)} --note {shlex.quote(f"Builder session {session} finished with {runtime_id}; ready for validator; log: {log_path}")} || true
          fi
        else
          "${{agent_work_cmd[@]}}" run-update {shlex.quote(run_id)} --status failed --exit-code "$status" --ended-now || true
          "${{agent_work_cmd[@]}}" update {issue['id']} --status blocked --role {shlex.quote(role)} --note {shlex.quote(f"Agent session {session} failed with {runtime_id}; log: {log_path}")} || true
        fi
        exit "$status"
        CENTO_AGENT_RUN
        sed -i.bak 's/^        //' "$run_dir/run.sh" 2>/dev/null || true
        chmod +x "$run_dir/run.sh"
        tmux new-session -d -s {shlex.quote(session)} "$run_dir/run.sh"
        printf '%s\\n' "$run_dir"
        """
    )
    command = textwrap.dedent(
        remote_command
    )
    proc = subprocess.run([cento_command(), "cluster", "exec", node, "--", "bash", "-lc", command], check=False)
    if proc.returncode != 0:
        update_issue(args.issue, "blocked", f"Dispatch command failed on {node} with exit {proc.returncode}.", node, agent, dispatch)
        return proc.returncode
    print(dispatch)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Cento agent work on the Taskstream board, with separate archive and migration commands for legacy history.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap", help="Create the Taskstream project, statuses, tracker, and fields.")
    p.set_defaults(func=command_bootstrap)

    p = sub.add_parser("create", help="Create one agent task.")
    p.add_argument("--title", required=True)
    p.add_argument("--manifest", required=True, help="Required story.json generated from the interpreted request. Use issue.id=0 before creation.")
    p.add_argument("--description", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--package", default="default")
    p.add_argument("--epic", action="store_true", help="Create the item as an Agent Epic while still requiring a story manifest.")
    p.add_argument("--owns", action="append", default=[], help="Declare owned files, modules, or responsibility boundaries. Repeat for multiple entries.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_create)

    p = sub.add_parser(
        "preflight",
        help="Check story.json and validation.json before dispatch without using AI.",
        description="Check story.json and validation.json before dispatch without using AI.",
    )
    p.add_argument("story_manifest", help="Path to story.json.")
    p.add_argument("--validation-manifest", default="", help="Validation manifest path. Defaults to story.validation.manifest or <run_dir>/validation.json.")
    p.add_argument("--min-automation-coverage", type=float, default=95.0)
    p.add_argument("--write-validation-draft", action="store_true", help="Write a deterministic validation draft if it is missing.")
    p.add_argument("--check-links", action="store_true", help="Require linked local story outputs to exist.")
    p.add_argument("--report", default="", help="Output preflight JSON path. Markdown is written beside it.")
    p.add_argument("--no-write", action="store_true", help="Do not write preflight report artifacts.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_preflight)

    p = sub.add_parser("split", help="Create an agent work package and task issues.")
    p.add_argument("--title", required=True)
    p.add_argument("--goal", default="")
    p.add_argument("--task", action="append", required=True)
    p.add_argument("--node", default="")
    p.add_argument("--nodes", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--package", default="")
    p.add_argument("--owns", action="append", default=[], help="Declare owned files/modules for split tasks. Repeated values map by task order; one value applies to all tasks.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_split)

    p = sub.add_parser("list", help="List agent work items.")
    p.add_argument("--all", action="store_true", help="Include closed items.")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_list)

    p = sub.add_parser("show", help="Show one issue.")
    p.add_argument("issue", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_show)

    p = sub.add_parser("claim", help="Claim an issue for an agent.")
    p.add_argument("issue", type=int)
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--note", default="")
    p.set_defaults(func=command_claim)

    p = sub.add_parser("update", help="Update issue status and notes.")
    p.add_argument("issue", type=int)
    p.add_argument("--status", choices=sorted(STATUS_MAP), default=None)
    p.add_argument("--note", default="")
    p.add_argument("--node", default=None)
    p.add_argument("--agent", default=None)
    p.add_argument("--role", choices=ROLE_CHOICES, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_update)

    p = sub.add_parser("validate", help="Record Validator result and move PASS to Review.")
    p.add_argument("issue", type=int)
    p.add_argument("--result", choices=VALIDATION_RESULT_CHOICES, default="pass")
    p.add_argument("--note", default="")
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--story-manifest", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_validate)

    p = sub.add_parser(
        "handoff",
        help="Write Builder report and move an issue to Validating.",
        description="Write Builder report and move an issue to Validating.",
    )
    p.add_argument("issue", type=int)
    p.add_argument("--summary", default="")
    p.add_argument("--changed-file", action="append", default=[])
    p.add_argument("--command", action="append", default=[])
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--risk", action="append", default=[])
    p.add_argument("--manifest", default="")
    p.add_argument("--run-dir", default="")
    p.add_argument("--output", default="")
    p.add_argument("--note", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--dispatch-validator", action="store_true")
    p.add_argument("--validator-node", default="")
    p.add_argument("--validator-agent", default="")
    p.add_argument("--validator-runtime", default="auto")
    p.add_argument("--validator-model", default="")
    p.add_argument("--validator-dry-run", action="store_true")
    p.set_defaults(func=command_handoff)

    p = sub.add_parser(
        "review-drain",
        help="Close approved Review issues for one or more packages.",
        description="Close approved Review issues for one or more packages with a dry-run transcript and guarded apply path.",
    )
    p.add_argument("--package", action="append", required=True, help="Package slug to drain. Repeat for multiple packages.")
    p.add_argument("--status", choices=sorted(STATUS_MAP), default="review", help="Status filter. Review is the only mutable state.")
    p.add_argument("--note", default="", help="Optional note to record on each closed issue.")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--run-dir", default="", help="Directory for transcript outputs.")
    p.add_argument("--json", action="store_true", help="Emit the transcript as JSON.")
    review_drain_mode = p.add_mutually_exclusive_group()
    review_drain_mode.add_argument("--dry-run", dest="apply", action="store_false", help="Write a transcript without mutating issues.")
    review_drain_mode.add_argument("--apply", dest="apply", action="store_true", help="Close matching Review issues.")
    p.set_defaults(apply=False, func=command_review_drain)

    p = sub.add_parser(
        "recovery-plan",
        help="Summarize stalled board state and suggest safe recovery commands.",
        description="Summarize stalled board state, review-drain opportunities, stale runs, and safe next commands. The default mode is report-only; --apply performs only bounded safe actions.",
    )
    p.add_argument("--json", action="store_true", help="Emit the plan as JSON to stdout.")
    p.add_argument("--apply", action="store_true", help="Apply only the bounded safe actions and create capped follow-up work when appropriate.")
    p.add_argument("--run-dir", default="", help="Directory for plan outputs.")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.set_defaults(func=command_recovery_plan)

    p = sub.add_parser(
        "validate-run",
        help="Run validation.json checks and record Validator result.",
        description="Run validation.json checks and record Validator result.",
    )
    p.add_argument("issue", type=int)
    p.add_argument("--manifest", default="")
    p.add_argument("--story-manifest", default="")
    p.add_argument("--note", default="")
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--no-update", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_validate_run)

    p = sub.add_parser(
        "cutover-parity",
        help="Compare archive data and replacement API parity and write a machine-readable cutover report.",
        description="Compare archive data and replacement API list/detail output and write cutover/parity artifacts.",
    )
    p.add_argument("--api", default="", help="Replacement API base URL (default: env CENTO_AGENT_WORK_API).")
    p.add_argument("--issue", type=int, action="append", default=[], help="Issue IDs to compare in detail.")
    p.add_argument("--all", action="store_true", help="Include closed issues.")
    p.add_argument("--include-local", action="store_true", help="Include replacement-local issues in cutover parity comparisons.")
    p.add_argument("--run-dir", default="", help="Directory for cutover report outputs.")
    p.add_argument("--json", action="store_true", help="Emit report JSON to stdout.")
    p.set_defaults(func=command_cutover_parity)

    p = sub.add_parser(
        "backup",
        help="Create a replacement DB and evidence backup bundle.",
        description="Create a replacement DB snapshot plus copied local evidence files for cutover rollback.",
    )
    p.add_argument("--db", default="", help="Replacement DB path to back up.")
    p.add_argument("--run-dir", default="", help="Directory for the backup bundle.")
    p.add_argument("--json", action="store_true", help="Emit backup manifest JSON to stdout.")
    p.set_defaults(func=command_backup)

    p = sub.add_parser(
        "restore",
        help="Restore a backup bundle into a replacement DB.",
        description="Restore a previously created backup bundle into a target DB and optionally verify the UI contract.",
    )
    p.add_argument("--bundle", required=True, help="Backup bundle directory produced by `agent-work backup`.")
    p.add_argument("--db", default="", help="Target DB path for the restore.")
    p.add_argument("--run-dir", default="", help="Directory for verification outputs if --verify is used.")
    p.add_argument("--verify", action="store_true", help="Launch the restored app and run UI/API contract checks.")
    p.add_argument("--json", action="store_true", help="Emit restore results as JSON.")
    p.set_defaults(func=command_restore)

    p = sub.add_parser(
        "archive",
        help="Export and search a read-only archive bundle.",
        description="Export replacement issue history into a static archive bundle and optionally search the exported history.",
    )
    p.add_argument("--db", default="", help="Replacement DB path to export from.")
    p.add_argument("--query", default="", help="Search text to match in the exported archive.")
    p.add_argument("--issue", action="append", default=[], help="Specific issue IDs to export. Repeat for multiple issues.")
    p.add_argument("--limit", type=int, default=0, help="Limit the export to the first N issues.")
    p.add_argument("--run-dir", default="", help="Directory for the archive bundle.")
    p.add_argument("--json", action="store_true", help="Emit archive metadata as JSON.")
    p.set_defaults(func=command_archive)

    p = sub.add_parser(
        "cutover-status",
        help="Show cutover freeze/finalization state and rollback guidance.",
        description="Show the current cutover state, write target, counts, blockers, and rollback steps.",
    )
    p.add_argument("--run-dir", default="", help="Optional cutover state directory.")
    p.add_argument("--json", action="store_true", help="Emit the state report as JSON.")
    p.set_defaults(func=command_cutover_status)

    p = sub.add_parser(
        "cutover-freeze",
        help="Record the cutover freeze marker.",
        description="Record a cutover freeze marker before the final migration or rollback window closes.",
    )
    p.add_argument("--run-dir", default="", help="Optional cutover state directory.")
    p.add_argument("--note", default="", help="Optional note to append to cutover state.")
    p.add_argument("--json", action="store_true", help="Emit the updated state as JSON.")
    p.set_defaults(func=command_cutover_freeze)

    p = sub.add_parser(
        "cutover-verify",
        help="Run the backup, restore, and archive verification drill.",
        description="Run the replacement backup/restore drill, export a static archive, and write the cutover verification report.",
    )
    p.add_argument("--db", default="", help="Replacement DB path to verify.")
    p.add_argument("--restore-db", default="", help="Target DB path for the restored verification copy.")
    p.add_argument("--query", default="", help="Search text to include in the archive verification bundle.")
    p.add_argument("--issue", action="append", default=[], help="Specific issue IDs to include in the archive verification bundle.")
    p.add_argument("--limit", type=int, default=0, help="Limit archive verification to the first N issues.")
    p.add_argument("--run-dir", default="", help="Directory for verification outputs.")
    p.add_argument("--json", action="store_true", help="Emit the verification report as JSON.")
    p.set_defaults(func=command_cutover_verify)

    p = sub.add_parser(
        "cutover-finalize",
        help="Finalize the cutover and keep legacy migration writes disabled for the archive path.",
        description="Finalize the cutover after the verification drill and make the replacement DB the only write target.",
    )
    p.add_argument("--run-dir", default="", help="Optional cutover state directory.")
    p.add_argument("--note", default="", help="Optional note to append to cutover state.")
    p.add_argument("--force", action="store_true", help="Finalize even if no verification timestamp is recorded.")
    p.add_argument("--json", action="store_true", help="Emit the updated state as JSON.")
    p.set_defaults(func=command_cutover_finalize)

    p = sub.add_parser("prompt", help="Print or write an agent prompt for an issue.")
    p.add_argument("issue", type=int)
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--output", default="")
    p.set_defaults(func=command_prompt)

    p = sub.add_parser("runtimes", help="List registered agent runtimes and weighted routing sample.")
    p.add_argument("--sample", type=int, default=100)
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--package", default="sample")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_runtimes)

    p = sub.add_parser("runs", help="List observed agent runtime ledger entries and untracked sessions.")
    p.add_argument("--json", action="store_true")
    p.add_argument("--active", action="store_true", help="Only show active, stale, or untracked sessions.")
    p.add_argument("--issue", type=int, default=None)
    p.add_argument("--no-untracked", action="store_true", help="Do not scan ps for untracked interactive Codex/Claude sessions.")
    p.add_argument("--reconcile", action="store_true", help="Update stale ledger records based on ps/tmux state.")
    p.set_defaults(func=command_runs)

    p = sub.add_parser("run-status", help="Show one agent run ledger entry.")
    p.add_argument("run_id")
    p.add_argument("--reconcile", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_run_status)

    p = sub.add_parser("run-update", help="Update one agent run ledger entry.")
    p.add_argument("run_id")
    p.add_argument("--status", choices=sorted(ACTIVE_RUN_STATUSES | ENDED_RUN_STATUSES | {"untracked_interactive"}), default="")
    p.add_argument("--health", default="")
    p.add_argument("--pid", type=int, default=None)
    p.add_argument("--child-pid", type=int, default=None)
    p.add_argument("--tmux-session", default="")
    p.add_argument("--log-path", default="")
    p.add_argument("--exit-code", type=int, default=None)
    p.add_argument("--ended-now", action="store_true")
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=command_run_update)

    p = sub.add_parser("run-wrap", help="Run a command while updating an agent run ledger entry.")
    p.add_argument("run_id")
    p.add_argument("command", nargs=argparse.REMAINDER)
    p.set_defaults(func=command_run_wrap)

    p = sub.add_parser("dispatch", help="Mark an issue dispatched and optionally run a cluster agent runtime.")
    p.add_argument("issue", type=int)
    p.add_argument("--node", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--role", choices=ROLE_CHOICES, default="builder")
    p.add_argument("--runtime", default="auto", help="Runtime id, such as codex or claude-code. Default: auto weighted route.")
    p.add_argument("--model", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--validation-manifest", default="", help="Validation manifest used by dispatch preflight.")
    p.add_argument("--min-automation-coverage", type=float, default=95.0)
    p.add_argument("--skip-preflight", action="store_true", help="Bypass dispatch preflight for legacy/manual cases.")
    p.set_defaults(func=command_dispatch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except AgentWorkError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
