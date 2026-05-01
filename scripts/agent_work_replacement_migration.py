#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_work import sql_literal, psql_json
from agent_work_app import DB_PATH, init_db


DEFAULT_REDMINE_PROJECT = "cento-agent-work"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_checksum(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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


def fetch_issues(project_identifier: str) -> list[dict[str, Any]]:
    sql = f"""
    WITH project as (
      select id from projects where identifier = {sql_literal(project_identifier)} limit 1
    )
    select coalesce(json_agg(to_jsonb(row) order by (row.id)::int), '[]'::json)
    from (
      select
        i.id,
        i.project_id,
        i.subject,
        coalesce(i.description, '') as description,
        coalesce(i.done_ratio, 0) as done_ratio,
        coalesce(i.assigned_to_id, 0) as assigned_to_id,
        coalesce(i.status_id, 0) as status_id,
        coalesce(i.tracker_id, 0) as tracker_id,
        i.updated_on::text as updated_on,
        i.created_on::text as created_on,
        coalesce(s.name, 'Queued') as status,
        coalesce(t.name, 'Agent Task') as tracker,
        p.identifier as project_identifier,
        p.name as project_name,
        coalesce(u.login, '') as assignee_login,
        trim(both ' ' from coalesce(u.firstname, '') || ' ' || coalesce(u.lastname, '')) as assignee_name
      from issues i
      join project p on p.id = i.project_id
      join issue_statuses s on s.id = i.status_id
      join trackers t on t.id = i.tracker_id
      left join users u on u.id = i.assigned_to_id
      order by i.id
    ) row;
    """
    return psql_records(sql)


def fetch_statuses(status_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(status_ids)
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
    from (
      select id, name, coalesce(is_closed, false) as is_closed, position
      from issue_statuses
      where id in ({ids})
      order by id
    ) row;
    """
    return psql_records(sql)


def fetch_trackers(tracker_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(tracker_ids)
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
    from (
      select id, name, default_status_id, position, coalesce(is_in_roadmap, false) as is_in_roadmap, coalesce(fields_bits, 0) as fields_bits
      from trackers
      where id in ({ids})
      order by id
    ) row;
    """
    return psql_records(sql)


def fetch_custom_fields() -> list[dict[str, Any]]:
    sql = """
    select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
    from (
      select
        id,
        name,
        field_format,
        description,
        possible_values,
        regexp,
        coalesce(is_required, false) as is_required,
        coalesce(is_for_all, true) as is_for_all,
        coalesce(is_filter, true) as is_filter,
        position,
        coalesce(searchable, true) as searchable,
        coalesce(editable, true) as editable,
        coalesce(visible, true) as visible,
        coalesce(multiple, false) as multiple
      from custom_fields
      where type = 'IssueCustomField'
      order by id
    ) row;
    """
    return psql_records(sql)


def fetch_custom_values(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.customized_id, row.custom_field_id), '[]'::json)
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
    return psql_records(sql)


def fetch_journals(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.issue_id, row.created_on, row.id), '[]'::json)
    from (
      select
        j.id,
        j.journalized_id as issue_id,
        j.user_id,
        coalesce(j.notes, '') as notes,
        j.created_on::text as created_on,
        coalesce(
          (
            select json_agg(
              jsonb_build_object(
                'property', d.property,
                'prop_key', d.prop_key,
                'property_id', d.property_id,
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
    return psql_records(sql)


def fetch_attachments(issue_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(issue_ids)
    if ids == "NULL":
        return []
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.issue_id, row.id), '[]'::json)
    from (
      select
        a.id,
        a.container_id as issue_id,
        a.filename,
        coalesce(a.disk_directory, '') as disk_directory,
        coalesce(a.disk_filename, '') as disk_filename,
        coalesce(a.filesize, 0) as filesize,
        coalesce(a.content_type, '') as content_type,
        coalesce(a.description, '') as description,
        coalesce(a.digest, '') as digest,
        coalesce(a.author_id, 0) as author_id,
        a.created_on::text as created_on,
        a.updated_on::text as updated_on
      from attachments a
      where a.container_type = 'Issue'
        and a.container_id in ({ids})
      order by a.id
    ) row;
    """
    return psql_records(sql)


def fetch_users(user_ids: set[int]) -> list[dict[str, Any]]:
    ids = sql_int_list(user_ids)
    if ids == "NULL":
        return []
    sql = f"""
    select coalesce(json_agg(to_jsonb(row) order by row.id), '[]'::json)
    from (
      select
        id,
        coalesce(login, '') as login,
        coalesce(firstname, '') as firstname,
        coalesce(lastname, '') as lastname,
        coalesce(mail, '') as mail,
        created_on::text as created_on,
        updated_on::text as updated_on,
        coalesce(admin, false) as admin
      from users
      where id in ({ids})
      order by id
    ) row;
    """
    return psql_records(sql)


def build_custom_value_index(custom_fields: list[dict[str, Any]], values: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    field_name_by_id = {
        int(item["id"]): as_text(item.get("name"))
        for item in custom_fields
        if item.get("id") is not None and item.get("name")
    }
    output: dict[int, dict[str, str]] = {}
    for value in values:
        issue_id = int(value.get("issue_id", 0))
        field_id = int(value.get("custom_field_id", 0))
        name = field_name_by_id.get(field_id)
        if not issue_id or not name:
            continue
        entry = output.setdefault(issue_id, {})
        entry[name] = as_text(value.get("value"))
    return output


def build_validation_evidence_rows(
    issues: list[dict[str, Any]],
    custom_value_index: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for issue in issues:
        issue_id = int(issue.get("id", 0) or 0)
        if issue_id <= 0:
            continue
        values = custom_value_index.get(issue_id, {})
        path = as_text(values.get("Validation Report")).strip()
        status = as_text(issue.get("status")).strip().lower()
        if not path and status not in {"review", "validating", "done"}:
            continue
        if not path:
            path = f"workspace/runs/agent-work/{issue_id}/validation.md"
        rows.append(
            {
                "id": issue_id,
                "issue_id": issue_id,
                "label": Path(path).name or "validation-report.md",
                "path": path,
                "url": "",
                "created_on": as_text(issue.get("updated_on")),
                "source": "redmine",
                "note": "Migrated validation evidence link.",
            }
        )
    return rows


def build_snapshot(project_identifier: str) -> dict[str, Any]:
    issues = fetch_issues(project_identifier)
    issue_ids = {int(issue["id"]) for issue in issues if issue.get("id") is not None}
    status_ids = {int(issue["status_id"]) for issue in issues if issue.get("status_id") is not None}
    tracker_ids = {int(issue["tracker_id"]) for issue in issues if issue.get("tracker_id") is not None}

    statuses = fetch_statuses(status_ids)
    trackers = fetch_trackers(tracker_ids)
    custom_fields = fetch_custom_fields()
    custom_values = fetch_custom_values(issue_ids)
    custom_value_index = build_custom_value_index(custom_fields, custom_values)
    journals = fetch_journals(issue_ids)
    attachments = fetch_attachments(issue_ids)
    validation_evidences = build_validation_evidence_rows(issues, custom_value_index)

    user_ids = {
        int(issue.get("assigned_to_id", 0))
        for issue in issues
        if issue.get("assigned_to_id")
    } | {
        int(journal.get("user_id", 0))
        for journal in journals
        if journal.get("user_id")
    } | {
        int(attachment.get("author_id", 0))
        for attachment in attachments
        if attachment.get("author_id")
    }
    users = fetch_users(user_ids)

    snapshot = {
        "captured_at": utcnow(),
        "project": project_identifier,
        "issues": issues,
        "journals": journals,
        "custom_fields": custom_fields,
        "custom_values": custom_values,
        "attachments": attachments,
        "validation_evidences": validation_evidences,
        "users": users,
        "trackers": trackers,
        "statuses": statuses,
    }
    for key in ("issues", "journals", "custom_fields", "custom_values", "attachments", "validation_evidences", "users", "trackers", "statuses"):
        snapshot[f"{key}_checksum"] = stable_checksum(snapshot[key])
    snapshot["counts"] = {
        "issues": len(issues),
        "journals": len(journals),
        "custom_fields": len(custom_fields),
        "custom_values": len(custom_values),
        "attachments": len(attachments),
        "validation_evidences": len(validation_evidences),
        "users": len(users),
        "trackers": len(trackers),
        "statuses": len(statuses),
    }
    return snapshot


def snapshot_table_schema() -> str:
    return """
create table if not exists redmine_entity_snapshots (
  run_id integer not null,
  entity_type text not null,
  entity_key text not null,
  provenance_checksum text not null,
  payload text not null,
  captured_at text not null,
  source text not null default 'redmine',
  primary key (run_id, entity_type, entity_key)
);
"""


def import_snapshot_to_replacement(
    db_path: Path,
    snapshot: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    with sqlite3.connect(db_path, timeout=120) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 120000")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        conn.executescript(snapshot_table_schema())

        started = utcnow()
        run_cursor = conn.execute(
            """
            insert into migration_runs(source, started_at, finished_at, issue_count, status, detail)
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                "redmine",
                started,
                started,
                0,
                "running",
                "{}",
            ),
        )
        run_id = int(run_cursor.lastrowid)

        try:
            issues = snapshot.get("issues", [])
            journals = snapshot.get("journals", [])
            attachments = snapshot.get("attachments", [])
            validation_evidences = snapshot.get("validation_evidences", [])
            custom_fields = snapshot.get("custom_fields", [])
            custom_values = snapshot.get("custom_values", [])
            users = snapshot.get("users", [])
            trackers = snapshot.get("trackers", [])
            statuses = snapshot.get("statuses", [])

            custom_value_index = build_custom_value_index(custom_fields, custom_values)
            user_lookup = {int(user["id"]): user for user in users if user.get("id") is not None}
            status_lookup = {int(status["id"]): as_text(status.get("name")) for status in statuses}

            issue_ids = [int(issue["id"]) for issue in issues if issue.get("id") is not None]
            if issue_ids:
                placeholders = ",".join("?" for _ in issue_ids)
                conn.execute(f"delete from journals where source = 'migration' and issue_id in ({placeholders})", issue_ids)
                conn.execute(f"delete from attachments where issue_id in ({placeholders})", issue_ids)
                conn.execute(f"delete from validation_evidences where source = 'migration' and issue_id in ({placeholders})", issue_ids)

            for issue in issues:
                issue_id = int(issue["id"])
                issue_values = custom_value_index.get(issue_id, {})
                assignee_name = as_text(issue.get("assignee_name")) or as_text(issue.get("assignee_login")) or "Redmine Admin"
                project = as_text(issue.get("project_identifier")) or "cento-agent-work"
                conn.execute(
                    """
                    insert into issues(
                      id, subject, project, tracker, status, priority, assignee, node, agent, role,
                      package, done_ratio, updated_on, description, source, migrated_at
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'redmine', ?)
                    on conflict(id) do update set
                      subject = excluded.subject,
                      project = excluded.project,
                      tracker = excluded.tracker,
                      status = excluded.status,
                      priority = excluded.priority,
                      assignee = excluded.assignee,
                      node = excluded.node,
                      agent = excluded.agent,
                      role = excluded.role,
                      package = excluded.package,
                      done_ratio = excluded.done_ratio,
                      updated_on = excluded.updated_on,
                      description = excluded.description,
                      migrated_at = excluded.migrated_at
                    """,
                    (
                        issue_id,
                        as_text(issue.get("subject")),
                        project,
                        as_text(issue.get("tracker")),
                        as_text(issue.get("status")),
                        "Normal",
                        assignee_name,
                        as_text(issue_values.get("Agent Node", "")),
                        as_text(issue_values.get("Agent Owner", assignee_name)),
                        as_text(issue_values.get("Agent Role", "builder")),
                        as_text(issue_values.get("Cento Work Package", "")),
                        int(issue.get("done_ratio", 0) or 0),
                        as_text(issue.get("updated_on")),
                        as_text(issue.get("description")),
                        utcnow(),
                    ),
                )

            for journal in journals:
                issue_id = int(journal["issue_id"])
                details = journal.get("details") or []
                if isinstance(details, str):
                    try:
                        details = json.loads(details)
                    except json.JSONDecodeError:
                        details = []
                old_status = ""
                new_status = ""
                for detail in details or []:
                    if as_text(detail.get("property")) != "attr":
                        continue
                    if as_text(detail.get("prop_key")) != "status_id":
                        continue
                    if detail.get("old_value"):
                        old_status = status_lookup.get(int(detail["old_value"]), "")
                    if detail.get("value"):
                        new_status = status_lookup.get(int(detail["value"]), "")
                author = "Redmine Admin"
                user_id = int(journal.get("user_id", 0))
                if user_id and user_id in user_lookup:
                    user = user_lookup[user_id]
                    candidate = " ".join(
                        filter(None, [as_text(user.get("firstname")), as_text(user.get("lastname"))])
                    ).strip()
                    author = candidate or as_text(user.get("login")) or author
                conn.execute(
                    """
                    insert into journals(issue_id, author, created_on, notes, old_status, new_status, source)
                    values (?, ?, ?, ?, ?, ?, 'migration')
                    """,
                    (
                        issue_id,
                        author,
                        as_text(journal.get("created_on")),
                        as_text(journal.get("notes")) or "Migrated journal event.",
                        old_status,
                        new_status,
                    ),
                )

            for attachment in attachments:
                issue_id = int(attachment["issue_id"])
                filename = as_text(attachment.get("filename"))
                if attachment.get("disk_directory") and attachment.get("disk_filename"):
                    path = f"{as_text(attachment.get('disk_directory'))}/{as_text(attachment.get('disk_filename'))}"
                else:
                    path = f"redmine://attachments/{int(attachment.get('id'))}/{filename}"
                conn.execute(
                    """
                    insert into attachments(issue_id, filename, size, path, created_on)
                    values (?, ?, ?, ?, ?)
                    """,
                    (
                        issue_id,
                        filename,
                        as_text(attachment.get("filesize")),
                        path,
                        as_text(attachment.get("created_on")),
                    ),
                )

            for evidence in validation_evidences:
                issue_id = int(evidence["issue_id"])
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
                    (
                        issue_id,
                        as_text(evidence.get("label")),
                        as_text(evidence.get("path")),
                        as_text(evidence.get("url")),
                        as_text(evidence.get("created_on")) or utcnow(),
                        as_text(evidence.get("source")) or "migration",
                        as_text(evidence.get("note")),
                    ),
                )

            conn.executemany(
                """
                insert into redmine_entity_snapshots(run_id, entity_type, entity_key, provenance_checksum, payload, captured_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(run_id, entity_type, entity_key) do update set
                  provenance_checksum = excluded.provenance_checksum,
                  payload = excluded.payload,
                  captured_at = excluded.captured_at
                """,
                [
                    (
                        run_id,
                        entity_type,
                        as_text(entity_key),
                        stable_checksum(entity_payload),
                        json.dumps(entity_payload, ensure_ascii=False),
                        utcnow(),
                    )
                    for entity_type, rows in (
                        ("issue", issues),
                        ("journal", journals),
                        ("custom_field", custom_fields),
                        ("attachment", attachments),
                        ("validation_evidence", validation_evidences),
                        ("user", users),
                        ("tracker", trackers),
                        ("status", statuses),
                    )
                    for row in rows
                    for entity_key in [as_text(row.get("id"))]
                ]
                + [
                    (
                        run_id,
                        "custom_value",
                        f"{int(value.get('issue_id'))}:{int(value.get('custom_field_id'))}",
                        stable_checksum(value),
                        json.dumps(value, ensure_ascii=False),
                        utcnow(),
                    )
                    for value in custom_values
                ]
            )

            manifest = {
                "run_id": run_id,
                "captured_at": snapshot.get("captured_at"),
                "counts": snapshot.get("counts"),
                "project": snapshot.get("project"),
                "checksums": {
                    key: snapshot.get(f"{key}_checksum")
                    for key in ("issues", "journals", "custom_fields", "custom_values", "attachments", "validation_evidences", "users", "trackers", "statuses")
                },
            }
            conn.execute(
                """
                update migration_runs
                set issue_count = ?,
                    finished_at = ?,
                    status = ?,
                    detail = ?
                where id = ?
                """,
                (
                    len(issues),
                    utcnow(),
                    "ok",
                    json.dumps(manifest),
                    run_id,
                ),
            )
            return run_id, manifest
        except Exception:
            conn.execute(
                "update migration_runs set status = ?, finished_at = ? where id = ?",
                ("failed", utcnow(), run_id),
            )
            raise


def build_evidence(path: Path, snapshot: dict[str, Any], run_id: int, db_path: Path) -> None:
    evidence = {
        "ran_at": utcnow(),
        "run_id": run_id,
        "replacement_db": str(db_path),
        "project": snapshot.get("project"),
        "counts": snapshot.get("counts"),
        "checksums": {
            key: snapshot.get(f"{key}_checksum")
            for key in ("issues", "journals", "custom_fields", "custom_values", "attachments", "validation_evidences", "users", "trackers", "statuses")
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


def command_snapshot(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args.project)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


def command_import(args: argparse.Namespace) -> int:
    if args.snapshot:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    else:
        snapshot = build_snapshot(args.project)
    run_id, manifest = import_snapshot_to_replacement(Path(args.db), snapshot)
    print(f"migration_run_id={run_id}")
    if args.evidence:
        build_evidence(Path(args.evidence), snapshot, run_id, Path(args.db))
        print(args.evidence)
    if args.pretty:
        print(json.dumps(manifest, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Redmine issue payloads and import provenance snapshots into the replacement DB."
    )
    parser.add_argument("--project", default=DEFAULT_REDMINE_PROJECT, help="Redmine project identifier.")

    sub = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = sub.add_parser("snapshot", help="Export Redmine replacement entities to JSON.")
    snapshot_parser.add_argument("--output", required=True, help="Write JSON snapshot to this path.")
    snapshot_parser.set_defaults(func=command_snapshot)

    import_parser = sub.add_parser("import", help="Import Redmine snapshot into replacement SQLite DB.")
    import_parser.add_argument("--db", default=str(DB_PATH), help="Replacement database path.")
    import_parser.add_argument("--snapshot", default="", help="Optional input JSON snapshot; omit to fetch live from Redmine.")
    import_parser.add_argument("--evidence", default="", help="Optional output evidence JSON path.")
    import_parser.add_argument("--pretty", action="store_true", help="Print run manifest JSON.")
    import_parser.set_defaults(func=command_import)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
