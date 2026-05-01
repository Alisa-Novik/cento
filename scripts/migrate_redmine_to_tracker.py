#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_work import psql_json, sql_literal
import agent_work_app
from agent_work_replacement_migration import build_validation_evidence_rows, import_snapshot_to_replacement


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "apps" / "agent-tracker" / "db" / "schema.sql"
DEFAULT_DB_PATH = ROOT / "apps" / "agent-tracker" / "db" / "tracker.db"
DEFAULT_PROJECT_IDENTIFIER = "cento-agent-work"
DEFAULT_PROJECT_NAME = "Cento Agent Work"
DEFAULT_TRACKER_NAME = "Agent Task"
SYNC_META_KEY = "last_synced_at"


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", as_text(value).strip().lower()).strip().replace(" ", "_")


def psql_records(sql: str) -> list[dict[str, Any]]:
    payload = psql_json(sql)
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    raise ValueError(f"Expected JSON array from psql query, got {type(payload)!r}")


def sql_int_list(values: list[int] | set[int]) -> str:
    ids = sorted({int(value) for value in values})
    return ",".join(map(str, ids)) if ids else "NULL"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_checksum(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def fetch_issues(project_identifier: str, updated_since: str | None = None) -> list[dict[str, Any]]:
    updated_clause = ""
    if updated_since:
        updated_clause = f"and i.updated_on > {sql_literal(updated_since)}"
    sql = f"""
    with project as (
      select id from projects where identifier = {sql_literal(project_identifier)} limit 1
    )
    select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
    from (
      select
        i.id,
        coalesce(i.subject, '') as subject,
        coalesce(s.name, '') as status,
        coalesce(p.name, '') as priority,
        coalesce(trim(both ' ' from coalesce(u.firstname, '') || ' ' || coalesce(u.lastname, '')), '') as assignee,
        coalesce(c.name, '') as category,
        coalesce(i.done_ratio, 0) as done_ratio,
        coalesce(i.estimated_hours, 0) as story_points,
        coalesce((select coalesce(sum(te.hours), 0) from time_entries te where te.issue_id = i.id), 0) as spent_time,
        coalesce(i.due_date::text, '') as due_date,
        i.created_on::text as created_on,
        i.updated_on::text as updated_on,
        coalesce(i.description, '') as description
      from issues i
      join project p0 on p0.id = i.project_id
      left join issue_statuses s on s.id = i.status_id
      left join enumerations p on p.id = i.priority_id and p.type = 'IssuePriority'
      left join users u on u.id = i.assigned_to_id
      left join issue_categories c on c.id = i.category_id
      where 1 = 1
        {updated_clause}
      order by i.id
    ) row;
    """
    return psql_records(sql)


def fetch_statuses() -> dict[int, str]:
    rows = psql_records(
        """
        select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
        from (
          select id, name from issue_statuses
          order by id
        ) row;
        """
    )
    return {as_int(item.get("id")): as_text(item.get("name")) for item in rows}


def fetch_trackers(tracker_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(tracker_ids)
    if ids == "NULL":
        return []
    return psql_records(
        f"""
        select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
        from (
          select id, name, default_status_id, position, coalesce(is_in_roadmap, false) as is_in_roadmap, coalesce(fields_bits, 0) as fields_bits
          from trackers
          where id in ({ids})
          order by id
        ) row;
        """
    )


def fetch_users(user_ids: set[int]) -> dict[int, str]:
    ids = sql_int_list(user_ids)
    if ids == "NULL":
        return {}
    rows = psql_records(
        f"""
        select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
        from (
          select
            id,
            trim(both ' ' from coalesce(firstname, '') || ' ' || coalesce(lastname, '')) as name,
            coalesce(login, '') as login
          from users
          where id in ({ids})
          order by id
        ) row;
        """
    )
    output: dict[int, str] = {}
    for item in rows:
        user_id = as_int(item.get("id"), 0)
        label = as_text(item.get("login")).strip() or as_text(item.get("name")).strip()
        if user_id:
            output[user_id] = label
    return output


def fetch_custom_fields() -> list[dict[str, Any]]:
    return psql_records(
        """
        select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
        from (
          select id, name from custom_fields where type = 'IssueCustomField' order by id
        ) row;
        """
    )


def fetch_custom_values(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    return psql_records(
        f"""
        select coalesce(json_agg(to_jsonb(row) order by row.issue_id, row.custom_field_id), '[]'::json)
        from (
          select
            customized_id as issue_id,
            custom_field_id,
            coalesce(value, '') as value
          from custom_values
          where customized_type = 'Issue'
            and customized_id in ({ids})
          order by customized_id, custom_field_id
        ) row;
        """
    )


def fetch_journals(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    return psql_records(
        f"""
        select coalesce(json_agg(to_jsonb(row) order by row.issue_id, row.created_on, row.id), '[]'::json)
        from (
          select
            j.id,
            j.journalized_id as issue_id,
            coalesce(j.user_id, 0) as actor_id,
            coalesce(j.notes, '') as notes,
            j.created_on::text as created_on,
            coalesce(
              (
                select json_agg(
                  jsonb_build_object(
                    'property', d.property,
                    'prop_key', d.prop_key,
                    'old_value', d.old_value,
                    'value', d.value
                  )
                  order by d.id
                )
                from journal_details d
                where d.journal_id = j.id
              ),
              '[]'::json
            ) as details
          from journals j
          where j.journalized_type = 'Issue'
            and j.journalized_id in ({ids})
          order by j.id
        ) row;
        """
    )


def fetch_attachments(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    return psql_records(
        f"""
        select coalesce(json_agg(to_jsonb(row) order by row.issue_id, row.id), '[]'::json)
        from (
          select
            a.id,
            a.container_id as issue_id,
            coalesce(a.filename, '') as filename,
            coalesce(a.disk_directory, '') as disk_directory,
            coalesce(a.disk_filename, '') as disk_filename,
            coalesce(a.filesize, 0) as filesize,
            coalesce(a.content_type, '') as content_type,
            coalesce(a.description, '') as description,
            coalesce(a.digest, '') as digest,
            coalesce(a.author_id, 0) as author_id,
            a.created_on::text as created_on
          from attachments a
          where a.container_type = 'Issue'
            and a.container_id in ({ids})
          order by a.id
        ) row;
        """
    )


def read_sync_watermark(db_path: Path) -> str | None:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "select value from sync_meta where key = ?",
                (SYNC_META_KEY,),
            ).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    value = as_text(row["value"]).strip()
    return value or None


def write_sync_watermark(db_path: Path, value: str) -> None:
    with sqlite3.connect(db_path, timeout=120) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("pragma busy_timeout = 120000")
        conn.execute("pragma journal_mode = WAL")
        conn.execute("pragma foreign_keys = ON")
        conn.execute(
            """
            insert into sync_meta(key, value, updated_on)
            values (?, ?, ?)
            on conflict(key) do update set
              value = excluded.value,
              updated_on = excluded.updated_on
            """,
            (SYNC_META_KEY, value, utcnow()),
        )
        conn.commit()


def build_incremental_snapshot(
    project_identifier: str,
    updated_since: str | None,
) -> dict[str, Any]:
    issues = fetch_issues(project_identifier, updated_since=updated_since)
    issue_ids = {as_int(item.get("id"), 0) for item in issues}
    issue_ids.discard(0)
    custom_fields = fetch_custom_fields()
    custom_values = fetch_custom_values(issue_ids)
    custom_value_index = build_custom_value_index(custom_fields, custom_values)
    journals = fetch_journals(issue_ids)
    attachments = fetch_attachments(issue_ids)
    validation_evidences = build_validation_evidence_rows(issues, custom_value_index)
    tracker_ids = {as_int(item.get("tracker_id"), 0) for item in issues}
    tracker_ids.discard(0)
    trackers = fetch_trackers(tracker_ids)

    user_ids = {
        as_int(item.get("actor_id"), 0)
        for item in journals
    } | {
        as_int(item.get("author_id"), 0)
        for item in attachments
    }
    user_ids.discard(0)
    users = fetch_users(user_ids)
    status_by_id = fetch_statuses()

    transformed_issues = [
        {
            "id": as_int(item.get("id"), 0),
            "subject": as_text(item.get("subject")),
            "description": as_text(item.get("description")),
            "project_identifier": project_identifier,
            "project_name": DEFAULT_PROJECT_NAME,
            "tracker": DEFAULT_TRACKER_NAME,
            "status": as_text(item.get("status")),
            "done_ratio": as_int(item.get("done_ratio"), 0),
            "updated_on": as_text(item.get("updated_on")),
            "created_on": as_text(item.get("created_on")),
            "assignee_login": as_text(item.get("assignee")),
            "assignee_name": as_text(item.get("assignee")),
            "validation_report": as_text(custom_value_index.get(as_int(item.get("id"), 0), {}).get("Validation Report")),
        }
        for item in issues
        if as_int(item.get("id"), 0) > 0
    ]

    transformed_journals = []
    for journal in journals:
        details = journal.get("details") or []
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except json.JSONDecodeError:
                details = []
        transformed_details = []
        for detail in details or []:
            transformed_details.append(
                {
                    "property": as_text(detail.get("property")),
                    "prop_key": as_text(detail.get("prop_key")),
                    "old_value": as_text(detail.get("old_value")),
                    "value": as_text(detail.get("value")),
                }
            )
        transformed_journals.append(
            {
                "id": as_int(journal.get("id"), 0),
                "issue_id": as_int(journal.get("issue_id"), 0),
                "user_id": as_int(journal.get("actor_id"), 0),
                "notes": as_text(journal.get("notes")),
                "created_on": as_text(journal.get("created_on")),
                "details": transformed_details,
            }
        )

    transformed_users = [
        {
            "id": user_id,
            "login": label,
            "firstname": "",
            "lastname": "",
            "mail": "",
            "created_on": "",
            "updated_on": "",
            "admin": False,
        }
        for user_id, label in users.items()
    ]

    transformed_statuses = [
        {
            "id": status_id,
            "name": name,
        }
        for status_id, name in status_by_id.items()
    ]

    return {
        "captured_at": utcnow(),
        "project": project_identifier,
        "issues": transformed_issues,
        "journals": transformed_journals,
        "custom_fields": custom_fields,
        "custom_values": custom_values,
        "attachments": attachments,
        "validation_evidences": validation_evidences,
        "users": transformed_users,
        "trackers": trackers,
        "statuses": transformed_statuses,
    }


def build_custom_value_index(
    fields: list[dict[str, Any]],
    values: list[dict[str, Any]],
) -> dict[int, dict[str, str]]:
    index_by_field_id = {
        int(item.get("id", 0)): as_text(item.get("name"))
        for item in fields
        if item.get("id") is not None and as_text(item.get("name")).strip()
    }
    output: dict[int, dict[str, str]] = {}
    for value in values:
        issue_id = as_int(value.get("issue_id"), 0)
        field_id = as_int(value.get("custom_field_id"), 0)
        field_name = index_by_field_id.get(field_id)
        if issue_id <= 0 or not field_name:
            continue
        output.setdefault(issue_id, {})[field_name] = as_text(value.get("value"))
    return output


def summarize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    keys = ("issues", "journals", "custom_fields", "custom_values", "attachments", "validation_evidences", "users", "trackers", "statuses")
    return {
        "counts": {key: len(snapshot.get(key) or []) for key in keys},
        "checksums": {key: stable_checksum(snapshot.get(key) or []) for key in keys},
    }


def pick_custom_field(values_by_issue: dict[str, str], candidates: tuple[str, ...]) -> str:
    target = {normalize_key(candidate) for candidate in candidates}
    for key, value in values_by_issue.items():
        if normalize_key(key) in target:
            return as_text(value)
    return ""


def status_name(status_by_id: dict[int, str], raw_value: Any) -> str:
    if raw_value is None:
        return ""
    raw = as_text(raw_value).strip()
    if not raw:
        return ""
    if raw.isdigit():
        return status_by_id.get(as_int(raw), raw)
    return raw


def build_issue_records(
    issues: list[dict[str, Any]],
    custom_values: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in issues:
        issue_id = as_int(item.get("id"), 0)
        if issue_id <= 0:
            continue
        values_for_issue = custom_values.get(issue_id, {})
        acceptance_criteria = pick_custom_field(values_for_issue, ("acceptance_criteria", "acceptance criteria"))
        story_points_custom = pick_custom_field(values_for_issue, ("story_points", "story points"))
        rows.append(
            {
                "id": issue_id,
                "subject": as_text(item.get("subject")),
                "status": as_text(item.get("status")),
                "priority": as_text(item.get("priority")),
                "assignee": as_text(item.get("assignee")),
                "category": as_text(item.get("category")),
                "done_ratio": as_int(item.get("done_ratio"), 0),
                "story_points": as_float(story_points_custom, as_float(item.get("story_points"), 0.0)),
                "spent_time": as_float(item.get("spent_time"), 0.0),
                "due_date": as_text(item.get("due_date")),
                "created_on": as_text(item.get("created_on")),
                "updated_on": as_text(item.get("updated_on")),
                "description": as_text(item.get("description")),
                "acceptance_criteria": acceptance_criteria,
            }
        )
    return rows


def build_status_events(
    journals: list[dict[str, Any]],
    user_labels: dict[int, str],
    status_by_id: dict[int, str],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for journal in journals:
        issue_id = as_int(journal.get("issue_id"), 0)
        if issue_id <= 0:
            continue
        actor = user_labels.get(as_int(journal.get("actor_id"), 0), "")
        changed_on = as_text(journal.get("created_on"))
        for detail in journal.get("details") or []:
            if as_text(detail.get("property")).strip() != "attr":
                continue
            if as_text(detail.get("prop_key")).strip() != "status_id":
                continue
            old_status = status_name(status_by_id, detail.get("old_value"))
            new_status = status_name(status_by_id, detail.get("value"))
            if not old_status and not new_status:
                continue
            events.append(
                {
                    "issue_id": issue_id,
                    "actor": actor,
                    "changed_on": changed_on,
                    "old_status": old_status,
                    "new_status": new_status,
                    "source": "redmine",
                }
            )
    return events


def build_note_rows(
    journals: list[dict[str, Any]],
    user_labels: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for journal in journals:
        note = as_text(journal.get("notes"))
        if not note.strip():
            continue
        rows.append(
            {
                "id": as_int(journal.get("id"), 0),
                "issue_id": as_int(journal.get("issue_id"), 0),
                "author": user_labels.get(as_int(journal.get("actor_id"), 0), ""),
                "created_on": as_text(journal.get("created_on")),
                "note": note,
                "source": "redmine",
            }
        )
    return rows


def build_attachment_rows(
    attachments: list[dict[str, Any]],
    user_labels: dict[int, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for attachment in attachments:
        issue_id = as_int(attachment.get("issue_id"), 0)
        if issue_id <= 0:
            continue
        disk_directory = as_text(attachment.get("disk_directory")).strip("/")
        disk_filename = as_text(attachment.get("disk_filename"))
        if disk_directory and disk_filename:
            path = f"{disk_directory}/{disk_filename}"
        else:
            path = f"redmine://attachments/{as_int(attachment.get('id'), 0)}/{as_text(attachment.get('filename'))}"
        rows.append(
            {
                "id": as_int(attachment.get("id"), 0),
                "issue_id": issue_id,
                "filename": as_text(attachment.get("filename")),
                "path": path,
                "size": as_int(attachment.get("filesize"), 0),
                "mime_type": as_text(attachment.get("content_type")),
                "digest": as_text(attachment.get("digest")),
                "created_on": as_text(attachment.get("created_on")),
                "description": as_text(attachment.get("description")),
                "author": user_labels.get(as_int(attachment.get("author_id"), 0), ""),
                "source": "redmine",
            }
        )
    return rows


def setup_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not SCHEMA_PATH.is_file():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    conn = sqlite3.connect(path, timeout=120)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("pragma busy_timeout = 120000")
    conn.execute("pragma journal_mode = WAL")
    conn.execute("pragma foreign_keys = ON")
    conn.execute("pragma synchronous = NORMAL")
    return conn


def migrate_incremental(
    project_identifier: str,
    db_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    started_at = utcnow()
    watermark = read_sync_watermark(db_path)
    snapshot = build_incremental_snapshot(project_identifier, watermark)
    summary = summarize_snapshot(snapshot)
    counts = summary["counts"]
    if dry_run:
        return {
            **summary,
            "issues": counts["issues"],
            "notes": counts["journals"],
            "attachments": counts["attachments"],
            "status_history": counts["journals"],
            "validation_evidences": counts["validation_evidences"],
            "trackers": counts["trackers"],
            "last_synced_at": started_at,
        }

    run_id, manifest = import_snapshot_to_replacement(db_path, snapshot)
    write_sync_watermark(db_path, started_at)
    return {
        **summary,
        "issues": counts["issues"],
        "notes": counts["journals"],
        "attachments": counts["attachments"],
        "status_history": counts["journals"],
        "validation_evidences": counts["validation_evidences"],
        "trackers": counts["trackers"],
        "run_id": run_id,
        "manifest": manifest,
        "last_synced_at": started_at,
    }




def migrate(
    project_identifier: str,
    db_path: Path,
    *,
    clear: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    issues = fetch_issues(project_identifier)
    issue_ids = {as_int(item.get("id"), 0) for item in issues}
    issue_ids.discard(0)
    custom_fields = fetch_custom_fields()
    custom_values = build_custom_value_index(custom_fields, fetch_custom_values(issue_ids))
    tracker_ids = {as_int(item.get("tracker_id"), 0) for item in issues}
    tracker_ids.discard(0)
    trackers = fetch_trackers(tracker_ids)
    journals = fetch_journals(issue_ids)
    user_ids = {as_int(item.get("actor_id"), 0) for item in journals} | {
        as_int(item.get("author_id"), 0) for item in fetch_attachments(issue_ids)
    }
    user_ids.discard(0)
    users = fetch_users(user_ids)
    status_by_id = fetch_statuses()
    validation_evidences = build_validation_evidence_rows(issues, custom_values)

    prepared_issues = build_issue_records(issues, custom_values)
    notes = build_note_rows(journals, users)
    attachments = build_attachment_rows(fetch_attachments(issue_ids), users)
    status_events = build_status_events(journals, users, status_by_id)
    snapshot = {
        "issues": prepared_issues,
        "journals": notes,
        "custom_fields": custom_fields,
        "custom_values": custom_values,
        "attachments": attachments,
        "validation_evidences": validation_evidences,
        "users": [
            {
                "id": user_id,
                "login": label,
                "firstname": "",
                "lastname": "",
                "mail": "",
                "created_on": "",
                "updated_on": "",
                "admin": False,
            }
            for user_id, label in users.items()
        ],
        "trackers": trackers,
        "statuses": [
            {"id": status_id, "name": name}
            for status_id, name in status_by_id.items()
        ],
    }
    summary = summarize_snapshot(snapshot)
    counts = summary["counts"]

    if dry_run:
        return {
            **summary,
            "issues": counts["issues"],
            "notes": counts["journals"],
            "attachments": counts["attachments"],
            "status_history": len(status_events),
            "validation_evidences": counts["validation_evidences"],
            "trackers": counts["trackers"],
        }

    conn = setup_db(db_path)
    try:
        if clear:
            conn.execute("DELETE FROM notes")
            conn.execute("DELETE FROM attachments")
            conn.execute("DELETE FROM status_history")
            conn.execute("DELETE FROM validation_evidences")
            conn.execute("DELETE FROM issues")

        conn.executemany(
            ""
            "INSERT INTO issues (\n"
            "  id, subject, status, priority, assignee, category, done_ratio,\n"
            "  story_points, spent_time, due_date, created_on, updated_on, description,\n"
            "  acceptance_criteria, source, migrated_at\n"
            ") values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'redmine', datetime('now'))\n"
            "ON CONFLICT(id) DO UPDATE SET\n"
            "  subject = excluded.subject,\n"
            "  status = excluded.status,\n"
            "  priority = excluded.priority,\n"
            "  assignee = excluded.assignee,\n"
            "  category = excluded.category,\n"
            "  done_ratio = excluded.done_ratio,\n"
            "  story_points = excluded.story_points,\n"
            "  spent_time = excluded.spent_time,\n"
            "  due_date = excluded.due_date,\n"
            "  created_on = excluded.created_on,\n"
            "  updated_on = excluded.updated_on,\n"
            "  description = excluded.description,\n"
            "  acceptance_criteria = excluded.acceptance_criteria,\n"
            "  migrated_at = datetime('now')\n"
            "",
            [
                (
                    row["id"],
                    row["subject"],
                    row["status"],
                    row["priority"],
                    row["assignee"],
                    row["category"],
                    row["done_ratio"],
                    row["story_points"],
                    row["spent_time"],
                    row["due_date"],
                    row["created_on"],
                    row["updated_on"],
                    row["description"],
                    row["acceptance_criteria"],
                )
                for row in prepared_issues
            ],
        )
        conn.executemany(
            ""
            "INSERT INTO notes (id, issue_id, author, created_on, note, source)\n"
            "VALUES (?, ?, ?, ?, ?, ?)\n"
            "ON CONFLICT(id) DO UPDATE SET\n"
            "  issue_id = excluded.issue_id,\n"
            "  author = excluded.author,\n"
            "  created_on = excluded.created_on,\n"
            "  note = excluded.note,\n"
            "  source = excluded.source\n"
            "",
            [
                (
                    row["id"],
                    row["issue_id"],
                    row["author"],
                    row["created_on"],
                    row["note"],
                    row["source"],
                )
                for row in notes
            ],
        )
        conn.executemany(
            ""
            "INSERT INTO attachments (id, issue_id, filename, path, size, mime_type, digest, created_on, description, author, source)\n"
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n"
            "ON CONFLICT(id) DO UPDATE SET\n"
            "  issue_id = excluded.issue_id,\n"
            "  filename = excluded.filename,\n"
            "  path = excluded.path,\n"
            "  size = excluded.size,\n"
            "  mime_type = excluded.mime_type,\n"
            "  digest = excluded.digest,\n"
            "  created_on = excluded.created_on,\n"
            "  description = excluded.description,\n"
            "  author = excluded.author,\n"
            "  source = excluded.source\n"
            "",
            [
                (
                    row["id"],
                    row["issue_id"],
                    row["filename"],
                    row["path"],
                    row["size"],
                    row["mime_type"],
                    row["digest"],
                    row["created_on"],
                    row["description"],
                    row["author"],
                    row["source"],
                )
                for row in attachments
            ],
        )
        conn.executemany(
            ""
            "INSERT INTO status_history (issue_id, actor, changed_on, old_status, new_status, source)\n"
            "VALUES (?, ?, ?, ?, ?, ?)\n",
            [
                (
                    row["issue_id"],
                    row["actor"],
                    row["changed_on"],
                    row["old_status"],
                    row["new_status"],
                    row["source"],
                )
                for row in status_events
            ],
        )
        conn.executemany(
            """
            INSERT INTO validation_evidences (issue_id, label, path, url, created_on, source, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_id, path) DO UPDATE SET
              label = excluded.label,
              url = excluded.url,
              created_on = excluded.created_on,
              source = excluded.source,
              note = excluded.note
            """,
            [
                (
                    row["issue_id"],
                    row["label"],
                    row["path"],
                    row["url"],
                    row["created_on"],
                    row["source"],
                    row["note"],
                )
                for row in validation_evidences
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return {
        **summary,
        "issues": counts["issues"],
        "notes": counts["journals"],
        "attachments": counts["attachments"],
        "status_history": len(status_events),
        "validation_evidences": counts["validation_evidences"],
        "trackers": counts["trackers"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate a Redmine project into the tracker SQLite DB.")
    parser.add_argument("--project", default=DEFAULT_PROJECT_IDENTIFIER, help="Redmine project identifier to migrate.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite tracker database path.")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear existing tracker rows before loading.")
    parser.add_argument("--incremental", action="store_true", help="Incrementally import changed Redmine issues into the replacement DB.")
    parser.add_argument("--dry-run", action="store_true", help="Count migratable rows without writing the SQLite DB.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if args.incremental and str(db_path) == str(DEFAULT_DB_PATH):
        db_path = agent_work_app.DB_PATH
    if args.incremental:
        summary = migrate_incremental(
            args.project,
            db_path,
            dry_run=args.dry_run,
        )
        print(
            f"replacement sync: issues={summary['issues']} notes={summary['notes']} "
            f"attachments={summary['attachments']} status_history={summary['status_history']}"
        )
    else:
        summary = migrate(
            args.project,
            db_path,
            clear=not args.no_clear,
            dry_run=args.dry_run,
        )
        print(f"tracker migrated: issues={summary['issues']} notes={summary['notes']} attachments={summary['attachments']} status_history={summary['status_history']}")
    print(json.dumps({"counts": summary["counts"], "checksums": summary["checksums"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
