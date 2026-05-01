#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sqlite3
import sys
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "workspace" / "runs"
DEFAULT_STORAGE_ROOT = ROOT / "workspace" / "storage"
DEFAULT_DB = DEFAULT_STORAGE_ROOT / "catalog.sqlite"
DEFAULT_REPORT_DIR = DEFAULT_STORAGE_ROOT / "reports"
DEFAULT_POLICIES = ROOT / "data" / "storage-policies.json"
DEFAULT_VAULT = Path("/mnt/cento-vault")

SCHEMA_VERSION = "cento-storage-catalog/v1"
RETENTION_SCHEMA_VERSION = "cento-storage-retention-plan/v1"

CONTROL_MANIFEST_NAMES = {
    "factory-plan.json",
    "story.json",
    "validation.json",
    "queue.json",
    "leases.json",
    "integration-state.json",
    "autopilot-state.json",
    "policy.json",
    "metrics.json",
    "stop-reason.json",
    "merge-readiness.json",
    "rollback-plan.json",
    "apply-plan.json",
    "delivery-status.json",
}

RELEASE_NAMES = {
    "release-candidate.md",
    "release-packet.md",
    "start-here.html",
    "autopilot-panel.html",
    "implementation-map.html",
}

PATCH_NAMES = {
    "patch.diff",
    "changed-files.txt",
    "diffstat.txt",
    "handoff.md",
    "patch.json",
}

LOG_SUFFIXES = {".log", ".out", ".err"}
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg"}
SQLITE_SUFFIXES = {".sqlite", ".sqlite3", ".db"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected object JSON: {path}")
    return payload


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_id_for_path(path: Path) -> str:
    return "artifact-" + hashlib.sha256(rel(path).encode("utf-8")).hexdigest()[:20]


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artifacts (
          artifact_id TEXT PRIMARY KEY,
          sha256 TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          path TEXT NOT NULL UNIQUE,
          normalized_path TEXT,
          class TEXT NOT NULL,
          mime_type TEXT,
          extension TEXT,
          run_id TEXT,
          task_id TEXT,
          issue_id TEXT,
          package TEXT,
          node TEXT,
          command TEXT,
          created_at TEXT,
          modified_at TEXT,
          first_seen_at TEXT NOT NULL,
          last_seen_at TEXT NOT NULL,
          last_accessed_at TEXT,
          temperature TEXT NOT NULL,
          retention_policy TEXT NOT NULL,
          sensitivity TEXT NOT NULL,
          pii_risk TEXT NOT NULL,
          storage_state TEXT NOT NULL,
          compression TEXT,
          compressed_path TEXT,
          content_addressed INTEGER DEFAULT 0,
          cas_path TEXT,
          duplicate_of TEXT,
          parent_artifact_id TEXT,
          derivative_kind TEXT,
          pinned INTEGER DEFAULT 0,
          reproducible INTEGER DEFAULT 0,
          expensive_to_reproduce INTEGER DEFAULT 0,
          validation_status TEXT,
          evidence_score INTEGER DEFAULT 0,
          restore_status TEXT,
          deletion_eligible_at TEXT,
          deletion_reason TEXT,
          notes TEXT
        );

        CREATE TABLE IF NOT EXISTS artifact_locations (
          artifact_id TEXT,
          location_type TEXT,
          uri TEXT,
          verified_at TEXT,
          restore_tested_at TEXT,
          PRIMARY KEY (artifact_id, location_type, uri)
        );

        CREATE TABLE IF NOT EXISTS artifact_events (
          event_id TEXT PRIMARY KEY,
          artifact_id TEXT,
          event_type TEXT,
          event_at TEXT,
          command TEXT,
          actor TEXT,
          details_json TEXT
        );

        CREATE TABLE IF NOT EXISTS run_storage_summary (
          run_id TEXT PRIMARY KEY,
          package TEXT,
          total_artifacts INTEGER,
          total_size_bytes INTEGER,
          hot_size_bytes INTEGER,
          warm_size_bytes INTEGER,
          cold_size_bytes INTEGER,
          duplicate_bytes INTEGER,
          deletion_candidate_bytes INTEGER,
          sensitive_artifacts INTEGER,
          generated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_artifacts_class ON artifacts(class);
        CREATE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);
        CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
        CREATE INDEX IF NOT EXISTS idx_artifacts_package ON artifacts(package);
        CREATE INDEX IF NOT EXISTS idx_artifacts_temperature ON artifacts(temperature);
        """
    )
    conn.commit()


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        raise SystemExit(f"Root does not exist: {root}")
    skipped_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item not in skipped_dirs]
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                continue
            files.append(path)
    return sorted(files)


def path_parts(path: Path) -> list[str]:
    return [part.lower() for part in rel(path).split(os.sep)]


def classify_artifact(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    parts = path_parts(path)
    part_set = set(parts)

    if name.endswith("-wal") or name.endswith("-shm"):
        return "sqlite_wal"
    if suffix in SQLITE_SUFFIXES:
        return "sqlite_db"
    if suffix == ".xwd":
        return "screenshot_raw"
    if suffix in IMAGE_SUFFIXES and any("screenshot" in part for part in parts):
        return "screenshot_normalized"
    if name in RELEASE_NAMES or "release" in name and suffix in {".md", ".html", ".json"}:
        return "release_packet"
    if name in PATCH_NAMES or "patches" in part_set:
        return "patch"
    if "research-map" in name or "implementation-map" in name:
        return "research_map"
    if suffix == ".pdf" or "research" in part_set and suffix in {".md", ".json"}:
        return "research_source"
    if "validation" in name or "validator" in part_set or "evidence" in part_set:
        return "validation"
    if name in CONTROL_MANIFEST_NAMES or name.endswith("-state.json"):
        return "manifest"
    if name == "run.json" or suffix == ".jsonl" or "ledger" in name or name == "events.jsonl":
        return "ledger"
    if "prompt" in name or "model-output" in name or "model-calls" in part_set:
        return "prompt"
    if suffix in LOG_SUFFIXES or "transcript" in name or "stdout" in name or "stderr" in name:
        return "log"
    if {"deriveddata", "build", "cache", "tmp", "temp"} & part_set:
        return "build_intermediate"
    if {"crm", "client", "clients", "resume", "invoice", "intake"} & part_set:
        return "client_data"
    if "summary" in name or "metrics" in name or "analytics" in part_set:
        return "analytics_summary"
    if "generated" in part_set:
        return "generated_reproducible"
    return "generated_reproducible"


def infer_context(path: Path) -> dict[str, str | None]:
    parts = rel(path).split(os.sep)
    lower = [part.lower() for part in parts]
    context: dict[str, str | None] = {"run_id": None, "task_id": None, "issue_id": None, "package": None}
    for marker in ("factory", "storage", "agent-manager"):
        if marker in lower:
            index = lower.index(marker)
            if index + 1 < len(parts):
                context["run_id"] = parts[index + 1]
                break
    if "agent-work" in lower:
        index = lower.index("agent-work")
        if index + 1 < len(parts):
            issue = parts[index + 1]
            context["run_id"] = issue
            if issue.isdigit():
                context["issue_id"] = issue
    if "tasks" in lower:
        index = lower.index("tasks")
        if index + 1 < len(parts):
            context["task_id"] = parts[index + 1]
    if "patches" in lower:
        index = lower.index("patches")
        if index + 1 < len(parts):
            context["task_id"] = context["task_id"] or parts[index + 1]
    return context


def sensitivity_for(path: Path, artifact_class: str) -> tuple[str, str]:
    parts = set(path_parts(path))
    name = path.name.lower()
    if artifact_class == "client_data" or {"client", "clients", "resume", "invoice", "contact"} & parts:
        return "client_sensitive", "high"
    if artifact_class in {"prompt", "model_output", "log", "transcript", "sqlite_db", "sqlite_wal"}:
        return "private", "medium"
    if "secret" in name or ".env" in name:
        return "secret_risk", "high"
    return "internal", "low"


def retention_policy_for(artifact_class: str) -> str:
    if artifact_class in {"manifest", "ledger", "patch", "validation", "release_packet", "research_source", "research_map"}:
        return "preserve"
    if artifact_class in {"screenshot_raw", "screenshot_normalized"}:
        return "screenshot-lifecycle"
    if artifact_class in {"log", "prompt"}:
        return "compress-after-hot-window"
    if artifact_class in {"sqlite_db", "sqlite_wal"}:
        return "sqlite-snapshot-required"
    if artifact_class == "build_intermediate":
        return "summarize-then-expire"
    if artifact_class == "client_data":
        return "client-sensitive-local-first"
    return "default-generated"


def temperature_for(artifact_class: str, modified_at: datetime) -> str:
    age = datetime.now(timezone.utc) - modified_at
    if artifact_class in {"manifest", "ledger", "patch", "validation", "release_packet", "client_data"}:
        return "hot" if age.days <= 180 else "warm"
    if age.days <= 30:
        return "hot"
    if age.days <= 180:
        return "warm"
    return "cold"


def evidence_score_for(artifact_class: str) -> int:
    scores = {
        "manifest": 95,
        "patch": 95,
        "validation": 90,
        "release_packet": 100,
        "screenshot_normalized": 80,
        "screenshot_raw": 65,
        "ledger": 85,
        "research_map": 80,
        "log": 45,
        "prompt": 50,
        "build_intermediate": 10,
    }
    return scores.get(artifact_class, 25)


def deletion_eligibility(artifact_class: str, modified_at: datetime) -> tuple[str | None, str | None]:
    age = datetime.now(timezone.utc) - modified_at
    if artifact_class == "build_intermediate" and age.days >= 14:
        return now_plus_days(0), "reproducible build intermediate after summary"
    if artifact_class == "screenshot_raw" and age.days >= 30:
        return now_plus_days(0), "raw screenshot candidate only after normalized derivative and verified catalog"
    if artifact_class == "log" and age.days >= 180:
        return now_plus_days(0), "old raw log candidate only after summary, compression, and verification"
    if artifact_class == "generated_reproducible" and age.days >= 180:
        return now_plus_days(0), "reproducible generated artifact after manifest/hash retention"
    return None, None


def now_plus_days(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")


def scan_artifacts(root: Path, db_path: Path) -> dict[str, Any]:
    scanned_at = now_iso()
    files = iter_files(root)
    conn = connect(db_path)
    existing_first_seen = {
        row["path"]: row["first_seen_at"]
        for row in conn.execute("SELECT path, first_seen_at FROM artifacts").fetchall()
    }
    first_by_sha: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for path in files:
        stat = path.stat()
        modified_dt = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        artifact_class = classify_artifact(path)
        sensitivity, pii_risk = sensitivity_for(path, artifact_class)
        sha256 = file_sha256(path)
        rel_path = rel(path)
        context = infer_context(path)
        duplicate_of = first_by_sha.get(sha256)
        if duplicate_of is None:
            first_by_sha[sha256] = artifact_id_for_path(path)
        deletion_at, deletion_reason = deletion_eligibility(artifact_class, modified_dt)
        mime_type, _ = mimetypes.guess_type(path)
        row = {
            "artifact_id": artifact_id_for_path(path),
            "sha256": sha256,
            "size_bytes": stat.st_size,
            "path": rel_path,
            "normalized_path": None,
            "class": artifact_class,
            "mime_type": mime_type,
            "extension": path.suffix.lower(),
            "run_id": context["run_id"],
            "task_id": context["task_id"],
            "issue_id": context["issue_id"],
            "package": context["package"],
            "node": None,
            "command": None,
            "created_at": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "modified_at": modified_dt.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "first_seen_at": existing_first_seen.get(rel_path, scanned_at),
            "last_seen_at": scanned_at,
            "last_accessed_at": None,
            "temperature": temperature_for(artifact_class, modified_dt),
            "retention_policy": retention_policy_for(artifact_class),
            "sensitivity": sensitivity,
            "pii_risk": pii_risk,
            "storage_state": "local_active",
            "compression": None,
            "compressed_path": None,
            "content_addressed": 0,
            "cas_path": None,
            "duplicate_of": duplicate_of,
            "parent_artifact_id": None,
            "derivative_kind": None,
            "pinned": 1 if artifact_class in {"manifest", "patch", "validation", "release_packet", "client_data"} else 0,
            "reproducible": 1 if artifact_class in {"build_intermediate", "generated_reproducible"} else 0,
            "expensive_to_reproduce": 1 if artifact_class in {"release_packet", "validation", "screenshot_raw", "research_source"} else 0,
            "validation_status": None,
            "evidence_score": evidence_score_for(artifact_class),
            "restore_status": "not_tested",
            "deletion_eligible_at": deletion_at,
            "deletion_reason": deletion_reason,
            "notes": None,
        }
        rows.append(row)

    columns = [
        "artifact_id",
        "sha256",
        "size_bytes",
        "path",
        "normalized_path",
        "class",
        "mime_type",
        "extension",
        "run_id",
        "task_id",
        "issue_id",
        "package",
        "node",
        "command",
        "created_at",
        "modified_at",
        "first_seen_at",
        "last_seen_at",
        "last_accessed_at",
        "temperature",
        "retention_policy",
        "sensitivity",
        "pii_risk",
        "storage_state",
        "compression",
        "compressed_path",
        "content_addressed",
        "cas_path",
        "duplicate_of",
        "parent_artifact_id",
        "derivative_kind",
        "pinned",
        "reproducible",
        "expensive_to_reproduce",
        "validation_status",
        "evidence_score",
        "restore_status",
        "deletion_eligible_at",
        "deletion_reason",
        "notes",
    ]
    placeholders = ",".join("?" for _ in columns)
    assignments = ",".join(f"{column}=excluded.{column}" for column in columns if column != "artifact_id")
    sql = (
        f"INSERT INTO artifacts ({','.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT(path) DO UPDATE SET {assignments}"
    )
    conn.executemany(sql, [[row[column] for column in columns] for row in rows])
    refresh_run_summaries(conn)
    conn.commit()
    conn.close()
    return {
        "schema_version": SCHEMA_VERSION,
        "root": rel(root),
        "db": rel(db_path),
        "scanned_at": scanned_at,
        "artifact_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "classes": summarize_counts(rows, "class"),
    }


def refresh_run_summaries(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM run_storage_summary")
    rows = conn.execute(
        """
        SELECT
          COALESCE(run_id, 'unassigned') AS run_id,
          package,
          COUNT(*) AS total_artifacts,
          SUM(size_bytes) AS total_size_bytes,
          SUM(CASE WHEN temperature='hot' THEN size_bytes ELSE 0 END) AS hot_size_bytes,
          SUM(CASE WHEN temperature='warm' THEN size_bytes ELSE 0 END) AS warm_size_bytes,
          SUM(CASE WHEN temperature='cold' THEN size_bytes ELSE 0 END) AS cold_size_bytes,
          SUM(CASE WHEN duplicate_of IS NOT NULL THEN size_bytes ELSE 0 END) AS duplicate_bytes,
          SUM(CASE WHEN deletion_reason IS NOT NULL THEN size_bytes ELSE 0 END) AS deletion_candidate_bytes,
          SUM(CASE WHEN sensitivity IN ('private', 'client_sensitive', 'secret_risk') THEN 1 ELSE 0 END) AS sensitive_artifacts
        FROM artifacts
        GROUP BY COALESCE(run_id, 'unassigned'), package
        """
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            INSERT INTO run_storage_summary (
              run_id, package, total_artifacts, total_size_bytes, hot_size_bytes,
              warm_size_bytes, cold_size_bytes, duplicate_bytes,
              deletion_candidate_bytes, sensitive_artifacts, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["run_id"],
                row["package"],
                row["total_artifacts"] or 0,
                row["total_size_bytes"] or 0,
                row["hot_size_bytes"] or 0,
                row["warm_size_bytes"] or 0,
                row["cold_size_bytes"] or 0,
                row["duplicate_bytes"] or 0,
                row["deletion_candidate_bytes"] or 0,
                row["sensitive_artifacts"] or 0,
                now_iso(),
            ),
        )


def summarize_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        value = str(row.get(field) or "unknown")
        summary[value] = summary.get(value, 0) + 1
    return dict(sorted(summary.items()))


def load_artifact_rows(db_path: Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    rows = [dict(row) for row in conn.execute("SELECT * FROM artifacts ORDER BY path").fetchall()]
    conn.close()
    return rows


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or DEFAULT_POLICIES
    if policy_path.exists():
        return read_json(policy_path)
    return {
        "schema_version": "cento-storage-policies/v1",
        "default_posture": "no_delete",
        "hot_days": 30,
        "warm_days": 180,
        "delete_execute_enabled": False,
    }


def retention_action(row: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    artifact_class = row["class"]
    action = "keep_hot" if row["temperature"] == "hot" else f"keep_{row['temperature']}"
    reason = "default retention"
    blockers: list[str] = []
    destructive = False

    if artifact_class in {"manifest", "ledger", "patch", "validation", "release_packet", "client_data"}:
        action = "preserve"
        reason = "high-value control, evidence, or client data"
    elif artifact_class == "screenshot_raw":
        action = "normalize_and_compress_candidate"
        reason = "raw screenshots need normalized derivatives before lifecycle movement"
        blockers.append("raw deletion blocked until derivative, hash verification, and restore test exist")
    elif artifact_class in {"log", "prompt"}:
        action = "compress_candidate"
        reason = "large text evidence should remain queryable but can be compressed after hot window"
    elif artifact_class in {"sqlite_db", "sqlite_wal"}:
        action = "snapshot_required"
        reason = "SQLite artifacts require backup/integrity handling before movement"
        blockers.append("never delete active DB/WAL from lifecycle planner")
    elif artifact_class == "build_intermediate":
        action = "delete_candidate_dry_run"
        reason = "reproducible build intermediate after summary"
        destructive = False
        blockers.append("v1 never deletes; future prune requires backup and deletion manifest")
    elif row.get("duplicate_of"):
        action = "dedupe_candidate"
        reason = "duplicate sha256 detected"
        blockers.append("v1 only plans CAS/dedupe, originals remain in place")

    if policy.get("default_posture") == "no_delete" and action.startswith("delete"):
        blockers.append("no-delete v1 posture")
    return {
        "artifact_id": row["artifact_id"],
        "path": row["path"],
        "class": artifact_class,
        "size_bytes": row["size_bytes"],
        "action": action,
        "reason": reason,
        "destructive": destructive,
        "blockers": blockers,
    }


def build_retention_plan(db_path: Path, policy_path: Path | None = None) -> dict[str, Any]:
    policy = load_policy(policy_path)
    rows = load_artifact_rows(db_path)
    actions = [retention_action(row, policy) for row in rows]
    vault_path = Path(str(policy.get("external_vault", DEFAULT_VAULT)))
    vault_mounted = vault_path.exists() and vault_path.is_dir()
    return {
        "schema_version": RETENTION_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "db": rel(db_path),
        "dry_run": True,
        "delete_execute_enabled": False,
        "external_vault": {
            "path": str(vault_path),
            "mounted": vault_mounted,
            "status": "available" if vault_mounted else "mocked_unmounted",
            "write_actions_enabled": False,
            "blocker": None if vault_mounted else "8TB Cento vault is not mounted; vault moves remain planned only",
        },
        "policy": policy.get("schema_version", "inline"),
        "summary": {
            "artifact_count": len(actions),
            "total_size_bytes": sum(int(item["size_bytes"]) for item in actions),
            "preserve_count": sum(1 for item in actions if item["action"] == "preserve"),
            "compress_candidates": sum(1 for item in actions if item["action"] == "compress_candidate"),
            "normalize_candidates": sum(1 for item in actions if item["action"] == "normalize_and_compress_candidate"),
            "dedupe_candidates": sum(1 for item in actions if item["action"] == "dedupe_candidate"),
            "delete_candidates_dry_run": sum(1 for item in actions if item["action"] == "delete_candidate_dry_run"),
            "destructive_actions": sum(1 for item in actions if item["destructive"]),
        },
        "actions": actions,
    }


def verify_artifacts(db_path: Path, all_rows: bool, sample: int | None) -> dict[str, Any]:
    rows = load_artifact_rows(db_path)
    if not all_rows:
        limit = sample or 20
        rows = rows[:limit]
    elif sample:
        rows = rows[:sample]
    checks = []
    for row in rows:
        path = repo_path(row["path"])
        if not path.exists():
            checks.append({"artifact_id": row["artifact_id"], "path": row["path"], "passed": False, "reason": "missing"})
            continue
        actual = file_sha256(path)
        checks.append(
            {
                "artifact_id": row["artifact_id"],
                "path": row["path"],
                "passed": actual == row["sha256"],
                "reason": "sha256_match" if actual == row["sha256"] else "sha256_mismatch",
                "expected_sha256": row["sha256"],
                "actual_sha256": actual,
            }
        )
    return {
        "schema_version": "cento-storage-verify/v1",
        "generated_at": now_iso(),
        "db": rel(db_path),
        "checks": checks,
        "summary": {
            "checked": len(checks),
            "passed": sum(1 for item in checks if item["passed"]),
            "failed": sum(1 for item in checks if not item["passed"]),
        },
    }


def snapshot_sqlite(source: Path, out: Path) -> dict[str, Any]:
    if not source.exists():
        raise SystemExit(f"SQLite source does not exist: {source}")
    out.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(source)
    dst_conn = sqlite3.connect(out)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    integrity_conn = sqlite3.connect(out)
    try:
        row = integrity_conn.execute("PRAGMA integrity_check;").fetchone()
        integrity = str(row[0]) if row else "missing"
    finally:
        integrity_conn.close()
    metadata = {
        "schema_version": "cento-storage-sqlite-snapshot/v1",
        "created_at": now_iso(),
        "source": rel(source),
        "snapshot": rel(out),
        "source_sha256": file_sha256(source),
        "snapshot_sha256": file_sha256(out),
        "size_bytes": out.stat().st_size,
        "integrity_check": integrity,
        "active_wal_deleted": False,
    }
    write_json(out.with_suffix(out.suffix + ".metadata.json"), metadata)
    return metadata


def restore_sample(db_path: Path, out: Path) -> dict[str, Any]:
    rows = load_artifact_rows(db_path)
    selected = [row for row in rows if row["class"] in {"manifest", "patch", "validation", "release_packet"}][:10]
    out.mkdir(parents=True, exist_ok=True)
    restored = []
    for row in selected:
        source = repo_path(row["path"])
        if not source.exists():
            restored.append({"artifact_id": row["artifact_id"], "path": row["path"], "passed": False, "reason": "missing"})
            continue
        target = out / row["artifact_id"] / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        restored.append(
            {
                "artifact_id": row["artifact_id"],
                "path": row["path"],
                "restored_to": rel(target),
                "passed": file_sha256(target) == row["sha256"],
                "reason": "sha256_match",
            }
        )
    report = {
        "schema_version": "cento-storage-restore-test/v1",
        "generated_at": now_iso(),
        "db": rel(db_path),
        "out": rel(out),
        "restored": restored,
        "summary": {
            "checked": len(restored),
            "passed": sum(1 for item in restored if item["passed"]),
            "failed": sum(1 for item in restored if not item["passed"]),
        },
    }
    write_json(out / "restore-test-report.json", report)
    return report


def query_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = load_artifact_rows(repo_path(args.db))
    if args.artifact_class:
        rows = [row for row in rows if row["class"] == args.artifact_class]
    if args.deletion_candidates:
        rows = [row for row in rows if retention_action(row, load_policy()).get("action") == "delete_candidate_dry_run"]
    if args.missing_derivative:
        normalized_stems = {
            Path(row["path"]).stem
            for row in rows
            if row["class"] == "screenshot_normalized"
        }
        rows = [row for row in rows if row["class"] == "screenshot_raw" and Path(row["path"]).stem not in normalized_stems]
    if args.largest:
        rows = sorted(rows, key=lambda row: int(row["size_bytes"]), reverse=True)
    limit = args.limit if args.limit is not None else 50
    return rows[:limit]


def render_markdown_report(db_path: Path, plan: dict[str, Any]) -> str:
    rows = load_artifact_rows(db_path)
    by_class = summarize_counts(rows, "class")
    by_temperature = summarize_counts(rows, "temperature")
    by_sensitivity = summarize_counts(rows, "sensitivity")
    largest = sorted(rows, key=lambda row: int(row["size_bytes"]), reverse=True)[:20]
    lines = [
        "# Cento Storage Summary",
        "",
        f"- generated_at: `{now_iso()}`",
        f"- catalog: `{rel(db_path)}`",
        f"- artifacts: `{len(rows)}`",
        f"- total_size_bytes: `{sum(int(row['size_bytes']) for row in rows)}`",
        f"- dry_run_delete_candidates: `{plan['summary']['delete_candidates_dry_run']}`",
        f"- destructive_actions_planned: `{plan['summary']['destructive_actions']}`",
        "",
        "## Classes",
        "",
    ]
    for key, value in by_class.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Temperature", ""])
    for key, value in by_temperature.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Sensitivity", ""])
    for key, value in by_sensitivity.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Largest Artifacts", ""])
    for row in largest:
        lines.append(f"- `{row['size_bytes']}` bytes `{row['class']}` `{row['path']}`")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- v1 is no-delete.",
            "- Raw screenshots are only normalization/compression candidates until derivatives are verified.",
            "- SQLite DB/WAL files require snapshot and integrity checks before movement.",
            "- Catalog metadata should outlive artifact bodies in future lifecycle versions.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def compute_pressure(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "schema_version": "cento-storage-pressure/v1",
            "generated_at": now_iso(),
            "db": rel(db_path),
            "storage_pressure": "critical",
            "catalog_integrity": "missing",
            "metrics": {},
            "recommendation": "run_storage_scan",
            "reasons": ["catalog database is missing"],
        }
    conn = connect(db_path)
    try:
        integrity_row = conn.execute("PRAGMA integrity_check;").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "missing"
        metrics = {
            "artifact_count": int(conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] or 0),
            "total_size_bytes": int(conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM artifacts").fetchone()[0] or 0),
            "raw_xwd_count": int(conn.execute("SELECT COUNT(*) FROM artifacts WHERE class='screenshot_raw'").fetchone()[0] or 0),
            "raw_xwd_bytes": int(conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM artifacts WHERE class='screenshot_raw'").fetchone()[0] or 0),
            "private_artifacts": int(
                conn.execute("SELECT COUNT(*) FROM artifacts WHERE sensitivity IN ('private', 'client_sensitive', 'secret_risk')").fetchone()[0]
                or 0
            ),
            "sqlite_artifacts": int(
                conn.execute("SELECT COUNT(*) FROM artifacts WHERE class IN ('sqlite_db', 'sqlite_wal')").fetchone()[0] or 0
            ),
            "delete_candidates_dry_run": int(
                conn.execute("SELECT COUNT(*) FROM artifacts WHERE deletion_reason IS NOT NULL").fetchone()[0] or 0
            ),
        }
    finally:
        conn.close()

    reasons: list[str] = []
    pressure = "low"
    recommendation = "storage_ok"
    if integrity != "ok":
        pressure = "critical"
        recommendation = "repair_catalog_before_fanout"
        reasons.append(f"catalog integrity check is {integrity}")
    if metrics["total_size_bytes"] >= 10 * 1024 * 1024 * 1024:
        pressure = "high" if pressure != "critical" else pressure
        recommendation = "pause_dispatch_and_run_storage_report"
        reasons.append("cataloged artifacts exceed 10 GiB")
    elif metrics["total_size_bytes"] >= 1 * 1024 * 1024 * 1024:
        pressure = "medium" if pressure == "low" else pressure
        recommendation = "review_storage_report_before_increasing_fanout"
        reasons.append("cataloged artifacts exceed 1 GiB")
    if metrics["raw_xwd_count"] > 0:
        pressure = "medium" if pressure == "low" else pressure
        recommendation = "plan_screenshot_normalization_before_large_fanout"
        reasons.append(f"{metrics['raw_xwd_count']} raw XWD screenshots need normalized derivative review")
    if metrics["raw_xwd_bytes"] >= 1 * 1024 * 1024 * 1024:
        pressure = "high" if pressure != "critical" else pressure
        recommendation = "pause_dispatch_and_normalize_raw_screenshots"
        reasons.append("raw XWD screenshots exceed 1 GiB")
    if not reasons:
        reasons.append("storage catalog is below initial pressure thresholds")

    return {
        "schema_version": "cento-storage-pressure/v1",
        "generated_at": now_iso(),
        "db": rel(db_path),
        "storage_pressure": pressure,
        "catalog_integrity": integrity,
        "metrics": metrics,
        "recommendation": recommendation,
        "reasons": reasons,
        "fanout_gate": {
            "may_increase_fanout": pressure in {"low"},
            "should_hold_fanout": pressure == "medium",
            "should_pause_dispatch": pressure in {"high", "critical"},
        },
    }


def screenshot_plan(db_path: Path, out: Path) -> dict[str, Any]:
    rows = [row for row in load_artifact_rows(db_path) if row["class"] == "screenshot_raw"]
    items = []
    for row in rows:
        target = DEFAULT_STORAGE_ROOT / "normalized" / "screenshots" / f"{row['sha256'][:16]}.png"
        items.append(
            {
                "artifact_id": row["artifact_id"],
                "source": row["path"],
                "target": rel(target),
                "action": "plan_normalized_derivative",
                "execute_supported": False,
                "reason": "v1 records the derivative plan without deleting or requiring xwd conversion dependencies",
            }
        )
    payload = {
        "schema_version": "cento-storage-screenshot-plan/v1",
        "generated_at": now_iso(),
        "dry_run": True,
        "items": items,
    }
    write_json(out, payload)
    return payload


def log_compression_plan(db_path: Path, out: Path) -> dict[str, Any]:
    rows = [row for row in load_artifact_rows(db_path) if row["class"] in {"log", "prompt"}]
    items = []
    for row in rows:
        target = DEFAULT_STORAGE_ROOT / "compressed" / "logs" / f"{row['artifact_id']}.zst"
        items.append(
            {
                "artifact_id": row["artifact_id"],
                "source": row["path"],
                "target": rel(target),
                "action": "plan_zstd_compression",
                "execute_supported": False,
                "reason": "v1 plans compression and summary retention; originals remain in place",
            }
        )
    payload = {
        "schema_version": "cento-storage-log-compression-plan/v1",
        "generated_at": now_iso(),
        "dry_run": True,
        "items": items,
    }
    write_json(out, payload)
    return payload


def command_scan(args: argparse.Namespace) -> int:
    root = repo_path(args.root)
    db_path = repo_path(args.db)
    result = scan_artifacts(root, db_path)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else f"Cataloged {result['artifact_count']} artifacts into {rel(db_path)}")
    return 0


def command_plan(args: argparse.Namespace) -> int:
    db_path = repo_path(args.db)
    plan = build_retention_plan(db_path, repo_path(args.policy) if args.policy else None)
    out = repo_path(args.out) if args.out else DEFAULT_REPORT_DIR / "retention-plan.json"
    write_json(out, plan)
    print(json.dumps(plan, indent=2, sort_keys=True) if args.json else rel(out))
    return 0


def command_query(args: argparse.Namespace) -> int:
    rows = query_rows(args)
    selected = [
        {
            "artifact_id": row["artifact_id"],
            "path": row["path"],
            "class": row["class"],
            "size_bytes": row["size_bytes"],
            "temperature": row["temperature"],
            "sensitivity": row["sensitivity"],
            "sha256": row["sha256"],
        }
        for row in rows
    ]
    if args.json:
        print(json.dumps({"artifacts": selected, "count": len(selected)}, indent=2, sort_keys=True))
    else:
        for row in selected:
            print(f"{row['size_bytes']:>10}  {row['class']:<22}  {row['path']}")
    return 0


def command_report(args: argparse.Namespace) -> int:
    db_path = repo_path(args.db)
    plan = build_retention_plan(db_path)
    out = repo_path(args.out) if args.out else DEFAULT_REPORT_DIR / "storage-summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown_report(db_path, plan), encoding="utf-8")
    print(rel(out))
    return 0


def command_pressure(args: argparse.Namespace) -> int:
    payload = compute_pressure(repo_path(args.db))
    out = repo_path(args.out) if args.out else None
    if out:
        write_json(out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json or not out else rel(out))
    return 0 if payload["storage_pressure"] != "critical" else 1


def command_verify(args: argparse.Namespace) -> int:
    db_path = repo_path(args.db)
    report = verify_artifacts(db_path, all_rows=args.all, sample=args.sample)
    out = repo_path(args.out) if args.out else DEFAULT_REPORT_DIR / "verify-report.json"
    write_json(out, report)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else rel(out))
    return 0 if report["summary"]["failed"] == 0 else 1


def command_normalize(args: argparse.Namespace) -> int:
    if args.target != "screenshots":
        raise SystemExit("Only `cento storage normalize screenshots` is supported in v1.")
    out = repo_path(args.out) if args.out else DEFAULT_REPORT_DIR / "screenshot-normalization-plan.json"
    payload = screenshot_plan(repo_path(args.db), out)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(out))
    return 0


def command_compress(args: argparse.Namespace) -> int:
    if args.target != "logs":
        raise SystemExit("Only `cento storage compress logs` is supported in v1.")
    out = repo_path(args.out) if args.out else DEFAULT_REPORT_DIR / "log-compression-plan.json"
    payload = log_compression_plan(repo_path(args.db), out)
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else rel(out))
    return 0


def command_snapshot_db(args: argparse.Namespace) -> int:
    metadata = snapshot_sqlite(repo_path(args.path), repo_path(args.out))
    print(json.dumps(metadata, indent=2, sort_keys=True) if args.json else rel(repo_path(args.out)))
    return 0 if metadata["integrity_check"] == "ok" else 1


def command_restore_test(args: argparse.Namespace) -> int:
    out = repo_path(args.out) if args.out else DEFAULT_STORAGE_ROOT / "restore-tests" / now_iso().replace(":", "")
    report = restore_sample(repo_path(args.db), out)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else rel(out / "restore-test-report.json"))
    return 0 if report["summary"]["failed"] == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cento no-delete artifact catalog and retention planner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", aliases=["catalog"], help="Scan artifacts into the SQLite catalog.")
    scan.add_argument("--root", default=str(DEFAULT_RUN_ROOT), help="Artifact root to scan.")
    scan.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    scan.add_argument("--json", action="store_true", help="Print machine-readable summary.")
    scan.set_defaults(func=command_scan)

    plan = subparsers.add_parser("plan", help="Write a no-delete retention/lifecycle dry-run plan.")
    plan.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    plan.add_argument("--policy", help="Retention policy JSON path.")
    plan.add_argument("--out", help="Output retention-plan.json path.")
    plan.add_argument("--older-than", help="Accepted for operator workflows; v1 records dry-run candidates only.")
    plan.add_argument("--dry-run", action="store_true", default=True, help="Retained for operator clarity; v1 is always dry-run.")
    plan.add_argument("--json", action="store_true", help="Print the plan.")
    plan.set_defaults(func=command_plan)

    query = subparsers.add_parser("query", help="Query cataloged artifacts.")
    query.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    query.add_argument("--class", dest="artifact_class", help="Filter by artifact class.")
    query.add_argument("--largest", action="store_true", help="Sort by size descending.")
    query.add_argument("--limit", type=int, default=50, help="Maximum rows.")
    query.add_argument("--deletion-candidates", action="store_true", help="Show no-delete deletion candidates.")
    query.add_argument("--missing-derivative", action="store_true", help="Show raw screenshots without normalized derivative.")
    query.add_argument("--json", action="store_true", help="Print JSON.")
    query.set_defaults(func=command_query)

    report = subparsers.add_parser("report", help="Render a Markdown storage summary.")
    report.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    report.add_argument("--out", help="Markdown report path.")
    report.set_defaults(func=command_report)

    pressure = subparsers.add_parser("pressure", help="Emit Autopilot-friendly storage pressure JSON.")
    pressure.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    pressure.add_argument("--out", help="JSON pressure report path.")
    pressure.add_argument("--json", action="store_true", help="Print JSON.")
    pressure.set_defaults(func=command_pressure)

    verify = subparsers.add_parser("verify", help="Verify catalog hashes against files on disk.")
    verify.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    verify.add_argument("--all", action="store_true", help="Verify all artifacts instead of a sample.")
    verify.add_argument("--sample", type=int, help="Number of artifacts to verify.")
    verify.add_argument("--out", help="JSON verification report path.")
    verify.add_argument("--json", action="store_true", help="Print verification report.")
    verify.set_defaults(func=command_verify)

    normalize = subparsers.add_parser("normalize", help="Plan additive artifact normalization.")
    normalize.add_argument("target", choices=["screenshots"])
    normalize.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    normalize.add_argument("--out", help="JSON plan output path.")
    normalize.add_argument("--dry-run", action="store_true", default=True, help="v1 is always dry-run.")
    normalize.add_argument("--json", action="store_true", help="Print JSON plan.")
    normalize.set_defaults(func=command_normalize)

    compress = subparsers.add_parser("compress", help="Plan additive compression.")
    compress.add_argument("target", choices=["logs"])
    compress.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    compress.add_argument("--out", help="JSON plan output path.")
    compress.add_argument("--dry-run", action="store_true", default=True, help="v1 is always dry-run.")
    compress.add_argument("--json", action="store_true", help="Print JSON plan.")
    compress.set_defaults(func=command_compress)

    snapshot = subparsers.add_parser("snapshot-db", help="Create a safe SQLite backup snapshot and metadata.")
    snapshot.add_argument("--path", required=True, help="SQLite database to snapshot.")
    snapshot.add_argument("--out", required=True, help="Snapshot output path.")
    snapshot.add_argument("--json", action="store_true", help="Print JSON metadata.")
    snapshot.set_defaults(func=command_snapshot_db)

    restore = subparsers.add_parser("restore-test", help="Copy a small high-value sample and verify hashes.")
    restore.add_argument("--db", default=str(DEFAULT_DB), help="SQLite catalog path.")
    restore.add_argument("--out", help="Restore-test output directory.")
    restore.add_argument("--sample", type=int, help="Reserved for future sample sizing.")
    restore.add_argument("--json", action="store_true", help="Print JSON report.")
    restore.set_defaults(func=command_restore_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
